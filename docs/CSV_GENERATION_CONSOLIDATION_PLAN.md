# CSV Generation Architecture Migration Plan

## Executive Summary

This plan migrates CSV generation from a dual-architecture system (projection_output.py + detailed_materialization.py) to a unified, component-based approach. The migration eliminates calculation duplication, removes incorrect flat tax rates, and establishes automatic field inclusion for maintainability while preserving specialized display logic where necessary.

## Current Architecture Issues

### 1. Dual CSV Generation Systems
- **projection_output.py**: Generates 6 CSVs using direct state access
- **detailed_materialization.py**: Generates 2 CSVs using reconstructed calculations

### 2. Calculation Duplication and Inconsistencies
- Tax calculations use flat rates (0.243/0.333) in CSV generation vs progressive brackets in calculators
- Charitable deduction ordering differs between CSV generator and calculator
- Data reconstruction attempts to recreate information already in components

### 3. Maintenance Burden
- Adding new fields requires updates in multiple locations
- Manual field mapping for each CSV column
- Complex reconstruction logic in DetailedMaterializer

## Migration Strategy

### Phase 1: Calculator Enhancements

#### 1.1 Update Charitable Deduction Ordering in AnnualTaxCalculator ✅

**Note**: During implementation, discovered that test_charitable_comprehensive_scenario.py has incorrect expected values that violate the 50% overall limit for 50% organizations. The calculator implementation is correct - the test needs to be updated.

**Current Implementation:**
```python
# Combines cash current + carryforward in single step
cash_used = min(total_cash_available, cash_limit)
```

**New Implementation:**
```python
def _apply_charitable_deduction_limits(self, ...):
    """Apply AGI limits using explicit IRS 4-step ordering."""

    # Step 1: Current year cash donations (up to cash limit)
    cash_current_used = min(cash_donations, cash_limit)
    remaining_cash_limit = cash_limit - cash_current_used

    # Step 2: Current year stock donations (up to stock limit)
    stock_current_used = min(stock_donations, stock_limit)
    remaining_stock_limit = stock_limit - stock_current_used

    # Step 3: Cash carryforward (up to remaining cash limit)
    cash_carryforward_used = min(carryforward_cash, remaining_cash_limit)

    # Step 4: Stock carryforward with FIFO (up to remaining stock limit)
    stock_carryforward_used = 0
    carryforward_consumed_by_creation_year = {}

    for creation_year in sorted(carryforward_stock_by_creation_year.keys()):
        if remaining_stock_limit <= 0:
            break
        available = carryforward_stock_by_creation_year[creation_year]
        used = min(available, remaining_stock_limit)
        stock_carryforward_used += used
        remaining_stock_limit -= used
        carryforward_consumed_by_creation_year[creation_year] = used

    # Return detailed usage breakdown
    return CharitableDeductionResult(
        cash_current_used=cash_current_used,
        stock_current_used=stock_current_used,
        cash_carryforward_used=cash_carryforward_used,
        stock_carryforward_used=stock_carryforward_used,
        # ... other fields
    )
```

**Rationale**: Explicit IRS 4-step ordering ensures compliance and consistency with tax law.

#### 1.2 Add ISO Qualifying Date Calculation ✅

**New Utility Function:**
```python
# In calculators/tax_utils.py (new file)
def calculate_iso_qualifying_disposition_date(grant_date: date, exercise_date: date) -> date:
    """
    Calculate when ISO shares become eligible for qualifying disposition.

    Requirements:
    - 2 years from grant date
    - 1 year from exercise date
    - Must satisfy BOTH conditions
    """
    two_years_from_grant = date(grant_date.year + 2, grant_date.month, grant_date.day)
    one_year_from_exercise = date(exercise_date.year + 1, exercise_date.month, exercise_date.day)

    # Handle leap year edge cases
    if grant_date.month == 2 and grant_date.day == 29:
        two_years_from_grant = date(grant_date.year + 2, 2, 28)
    if exercise_date.month == 2 and exercise_date.day == 29:
        one_year_from_exercise = date(exercise_date.year + 1, 2, 28)

    return max(two_years_from_grant, one_year_from_exercise)
```

**Add to ShareLot as Property:**
```python
@property
def iso_qualifying_date(self) -> Optional[date]:
    """Date when ISO shares become eligible for qualifying disposition."""
    if self.share_type != ShareType.ISO:
        return None
    if not self.exercise_date:
        return None
    return calculate_iso_qualifying_disposition_date(self.grant_date, self.exercise_date)
```

**Rationale**: Centralizes qualifying date calculation for use in both sale determination and milestone tracking.

#### 1.3 Extend CharitableDeductionResult for Display ✅

**Updated CharitableDeductionResult:**
```python
@dataclass
class CharitableDeductionResult:
    """Result of applying charitable deduction limits."""
    # Existing fields...

    # NEW: Explicit IRS ordering breakdown
    cash_current_used: float = 0.0
    stock_current_used: float = 0.0
    cash_carryforward_used: float = 0.0
    stock_carryforward_used: float = 0.0

    # NEW: For CSV display
    carryforward_used_by_year: Dict[int, float] = field(default_factory=dict)
    carryforward_remaining_by_year: Dict[int, float] = field(default_factory=dict)
```

### Phase 2: Component Enhancement for CSV Export ✅

#### 2.1 Add Source Action Reference to Components

**Update Component Classes:**
```python
@dataclass
class ISOExerciseComponents:
    # ... existing fields ...

    # NEW: Link to source action for CSV generation
    action_date: Optional[date] = None
    action_type: str = "exercise"
    calculator_name: str = "iso_exercise_calculator"

@dataclass
class ShareSaleComponents:
    # ... existing fields ...

    # NEW: Additional display fields
    tax_treatment: str = ""  # "STCG", "LTCG", "Qualifying", "Disqualifying"
    action_type: str = "sell"
    calculator_name: str = "share_sale_calculator"
```

**Update Calculator Methods:**
```python
def calculate_exercise_components(...) -> ISOExerciseComponents:
    # ... existing calculation ...

    return ISOExerciseComponents(
        # ... existing fields ...
        action_date=exercise_date,
        action_type="exercise",
        calculator_name="iso_exercise_calculator"
    )
```

### Phase 3: New CSV Generation Architecture ✅

#### 3.1 Component-Based CSV Generator

**New File: projections/csv_generators.py**
```python
import pandas as pd
from dataclasses import asdict, fields
from typing import List, Any, Dict
from projections.projection_state import ProjectionResult

def save_components_csv(result: ProjectionResult, output_path: str) -> None:
    """
    Generate comprehensive component CSV with automatic field inclusion.

    This replaces action_summary.csv with a more maintainable approach
    that automatically includes all component fields.
    """
    rows = []

    for yearly_state in result.yearly_states:
        components = yearly_state.annual_tax_components
        year_context = {
            'year': yearly_state.year,
            'current_share_price': yearly_state.current_share_price
        }

        # ISO Exercises
        for comp in components.iso_exercise_components:
            row = {
                'component_type': 'ISO Exercise',
                **year_context,
                **asdict(comp)
            }
            rows.append(row)

        # NSO Exercises
        for comp in components.nso_exercise_components:
            row = {
                'component_type': 'NSO Exercise',
                **year_context,
                **asdict(comp)
            }
            rows.append(row)

        # Sales
        for comp in components.sale_components:
            row = {
                'component_type': 'Sale',
                **year_context,
                **asdict(comp),
                # Add computed display fields
                'total_proceeds': comp.shares_sold * comp.sale_price,
                'total_gain': comp.short_term_gain + comp.long_term_gain + comp.ordinary_income
            }
            rows.append(row)

        # Donations
        for comp in components.donation_components:
            row = {
                'component_type': 'Stock Donation',
                **year_context,
                **asdict(comp),
                'total_impact': comp.donation_value + comp.company_match_amount
            }
            rows.append(row)

        # Cash Donations
        for comp in components.cash_donation_components:
            row = {
                'component_type': 'Cash Donation',
                **year_context,
                **asdict(comp),
                'total_impact': comp.amount + comp.company_match_amount
            }
            rows.append(row)

    # Convert to DataFrame for automatic type handling
    if rows:
        df = pd.DataFrame(rows)

        # Reorder columns for readability
        priority_cols = ['year', 'component_type', 'lot_id', 'shares_exercised',
                        'shares_sold', 'shares_donated', 'amount']
        other_cols = [col for col in df.columns if col not in priority_cols]
        ordered_cols = [col for col in priority_cols if col in df.columns] + other_cols

        df[ordered_cols].to_csv(output_path, index=False, date_format='%Y-%m-%d')
    else:
        # Empty file with minimal headers
        pd.DataFrame(columns=['year', 'component_type']).to_csv(output_path, index=False)
```

#### 3.2 Annual Summary Generator Using State Data

**New Annual Summary Generator:**
```python
def save_annual_summary_csv(result: ProjectionResult, output_path: str) -> None:
    """
    Generate annual summary using YearlyState data directly.
    No reconstruction or recalculation.
    """
    rows = []

    for yearly_state in result.yearly_states:
        # Calculate counts from components
        components = yearly_state.annual_tax_components

        options_exercised = (
            sum(c.shares_exercised for c in components.iso_exercise_components) +
            sum(c.shares_exercised for c in components.nso_exercise_components)
        )

        shares_sold = sum(c.shares_sold for c in components.sale_components)
        shares_donated = sum(c.shares_donated for c in components.donation_components)

        # Get pledge metrics from pledge state
        pledge_metrics = calculate_pledge_metrics(yearly_state.pledge_state)

        # Get expiration metrics
        expired_options = sum(e.quantity for e in yearly_state.expiration_events)
        expired_opportunity_cost = sum(e.opportunity_cost for e in yearly_state.expiration_events)

        row = {
            # Income
            'year': yearly_state.year,
            'w2_income': yearly_state.income,
            'spouse_income': yearly_state.spouse_income,
            'total_income': components.total_ordinary_income,

            # Actions
            'exercise_costs': yearly_state.exercise_costs,
            'sale_proceeds': sum(c.gross_proceeds for c in components.sale_components),
            'capital_gains': components.short_term_capital_gains + components.long_term_capital_gains,

            # Charitable
            'donations': yearly_state.donation_value,
            'company_match': yearly_state.company_match_received,
            'total_charitable_impact': yearly_state.donation_value + yearly_state.company_match_received,

            # Pledge tracking
            'pledge_shares_obligated': pledge_metrics['obligated'],
            'pledge_shares_donated': pledge_metrics['donated'],
            'pledge_shares_outstanding': pledge_metrics['outstanding'],
            'pledge_shares_expired': pledge_metrics['expired_window'],

            # Share counts
            'options_exercised_count': options_exercised,
            'shares_sold_count': shares_sold,
            'shares_donated_count': shares_donated,
            'expired_option_count': expired_options,

            # Tax details (from actual progressive calculations)
            'regular_tax': yearly_state.tax_state.regular_tax,
            'amt_tax': yearly_state.tax_state.amt_tax,
            'total_tax': yearly_state.tax_state.total_tax,
            'amt_credits_generated': yearly_state.tax_state.amt_credits_generated,
            'amt_credits_consumed': yearly_state.tax_state.amt_credits_used,
            'amt_credits_balance': yearly_state.tax_state.amt_credits_remaining,

            # Wealth tracking
            'ending_cash': yearly_state.ending_cash,
            'equity_value': yearly_state.total_equity_value,
            'net_worth': yearly_state.ending_cash + yearly_state.total_equity_value,
            'expired_option_loss': expired_opportunity_cost
        }
        rows.append(row)

    pd.DataFrame(rows).to_csv(output_path, index=False)
```

#### 3.3 Updated save_all_projection_csvs

**Updated Function:**
```python
def save_all_projection_csvs(result: ProjectionResult, scenario_name: str, output_dir: str = "output") -> None:
    """Save all projection CSVs for a scenario."""
    base_name = scenario_name.lower().replace(' ', '_').replace('-', '_')

    # Core timeline and state tracking CSVs (unchanged)
    save_annual_tax_detail_csv(result, f"{output_dir}/{base_name}_annual_tax_detail.csv")
    save_state_timeline_csv(result, f"{output_dir}/{base_name}_state_timeline.csv")
    save_transition_timeline_csv(result, f"{output_dir}/{base_name}_transition_timeline.csv")

    # Tracking CSVs (unchanged)
    generate_holding_milestones_csv(result, f"{output_dir}/{base_name}_holding_period_tracking.csv")
    save_charitable_carryforward_csv(result, f"{output_dir}/{base_name}_charitable_carryforward.csv")
    save_comprehensive_cashflow_csv(result, f"{output_dir}/{base_name}_comprehensive_cashflow.csv")

    # NEW: Component-based CSVs replacing detailed_materialization
    save_components_csv(result, f"{output_dir}/{base_name}_components.csv")
    save_annual_summary_csv(result, f"{output_dir}/{base_name}_annual_summary.csv")
```

### Phase 4: Specialized CSV Updates

#### 4.1 Enhanced Charitable Carryforward CSV ✅

**Completed**: Successfully implemented enhanced charitable carryforward CSV that:
- Added `federal_charitable_deduction_result` and `ca_charitable_deduction_result` fields to YearlyState
- Updated ProjectionCalculator to store CharitableDeductionResult in YearlyState
- Created `save_charitable_carryforward_csv_enhanced()` that uses stored results instead of duplicating logic
- Displays explicit IRS 4-step ordering breakdown (cash current, stock current, cash carryforward, stock carryforward)
- Shows carryforward tracking by creation year for FIFO compliance
- No silent fallbacks - raises errors if data is missing

**Updates to save_charitable_carryforward_csv:**
```python
# Use new CharitableDeductionResult fields
federal_deduction = yearly_state.tax_state.charitable_deduction_result

row = {
    # ... existing fields ...

    # NEW: Explicit IRS ordering breakdown
    'federal_cash_current_used': federal_deduction.cash_current_used,
    'federal_stock_current_used': federal_deduction.stock_current_used,
    'federal_cash_carryforward_used': federal_deduction.cash_carryforward_used,
    'federal_stock_carryforward_used': federal_deduction.stock_carryforward_used,

    # NEW: Year-by-year breakdown from calculator
    'federal_carryforward_used_by_year': str(federal_deduction.carryforward_used_by_year),
    'federal_carryforward_remaining_by_year': str(federal_deduction.carryforward_remaining_by_year),
}
```

#### 4.2 Add run_scenario_analysis CSV Generation ✅

**Update run_scenario_analysis.py:**
```python
def execute_scenario(scenario_input, price_scenario="moderate", projection_years=5, use_demo=False, verbose=False):
    # ... existing code ...

    result = manager.execute_single_scenario(
        scenario_path=scenario_path,
        price_scenario=price_scenario,
        projection_years=projection_years
    )

    print_scenario_results(result, detailed=True, verbose=verbose)

    # NEW: Generate CSV outputs
    if result:
        output_dir = manager._generate_output_path(scenario_name, price_scenario)
        save_all_projection_csvs(result, scenario_name, output_dir)
        print(f"\n📊 CSV files saved to: {output_dir}/")

    return result
```

### Phase 5: Cleanup ⚠️ (Partially Complete)

#### 5.1 Remove detailed_materialization.py ⏸️ (On Hold)

**Note**: Cannot remove yet as portfolio_manager.py still uses materialize_detailed_projection. This should be removed after portfolio_manager is updated to use the new CSV generation directly.
- Delete the entire file
- Remove import from projection_output.py
- Remove materialize_detailed_projection function call

#### 5.2 Update Tests ✅
- Update test_action_summary_data_quality.py to use new components.csv
- Update any tests checking for action_summary.csv to use components.csv

## Format Changes Summary

### Replaced CSVs

#### action_summary.csv → components.csv

**Old Format:**
- Fixed columns manually specified
- Reconstructed calculations with flat tax rates
- Missing new fields unless manually added

**New Format:**
- All component fields automatically included
- No tax calculations (those belong in annual_tax_detail.csv)
- New columns appear automatically when added to components
- Includes `component_type` column for filtering
- Progressive tax data available via year lookup in annual_tax_detail.csv

**Example Old Row:**
```csv
year,date,type,lot_id,quantity,tax,tax_rate_applied
2024,2024-06-01,sell,ISO_001,100,2430.00,0.243
```

**Example New Row:**
```csv
year,component_type,lot_id,sale_date,shares_sold,sale_price,short_term_gain,long_term_gain,disposition_type
2024,Sale,ISO_001,2024-06-01,100,50.00,0.0,2000.0,QUALIFYING_ISO
```

#### annual_summary.csv

**Old Format:**
- Some fields pulled from DetailedYear reconstruction
- Mix of calculated and state-based data

**New Format:**
- All data from YearlyState and components
- Consistent with other CSV data sources
- Tax amounts from progressive calculations only

### Unchanged CSVs

The following CSVs remain unchanged as they already pull directly from state:
- annual_tax_detail.csv
- state_timeline.csv
- transition_timeline.csv
- holding_period_tracking.csv
- charitable_carryforward.csv (enhanced with IRS ordering detail)
- comprehensive_cashflow.csv

## Fields Not Included in Migration

### From action_summary.csv

**Removed Fields:**
- `tax_rate_applied` - Was incorrect flat rate
- `tax` - Individual action tax impact cannot be accurately attributed
- `calculator` - Replaced by `component_type` which is more meaningful
- `net_cash_change` - Oversimplified, use comprehensive_cashflow.csv

**Rationale**: These fields either contained incorrect calculations or attempted to attribute annual-level calculations to individual actions.

### From DetailedAction/DetailedYear Classes

**Not Migrated:**
- Intermediate calculation fields
- Reconstructed state transitions
- Simplified tax calculations

**Rationale**: These were artifacts of the reconstruction process, not authoritative data.

## Key Improvements

### 1. Automatic Field Inclusion
New fields in component classes automatically appear in CSVs without code changes.

### 2. Single Source of Truth
All data comes from authoritative calculators and state objects.

### 3. Progressive Tax Calculations
Removes all flat tax rate approximations.

### 4. Explicit IRS Compliance
Charitable deduction ordering now follows explicit IRS rules.

### 5. Maintainability
Adding a new field requires only updating the component dataclass.

## Migration Validation

### 1. Component Coverage
Verify all component types appear in components.csv:
- ISO Exercise
- NSO Exercise
- Sale
- Stock Donation
- Cash Donation

### 2. Tax Calculation Validation
Compare annual_summary.csv tax totals with sum of component tax impacts to ensure consistency.

### 3. Field Completeness
Ensure critical fields are present:
- All date fields
- All quantity fields
- All financial amounts
- Disposition types for sales

### 4. Data Integrity
- Total shares in state_timeline.csv remain constant
- Cash flow in annual_summary.csv matches year-to-year
- Carryforward amounts track correctly across years

## Post-Migration User Guide Updates

### For Users
- `action_summary.csv` is now `components.csv` with all fields
- Tax calculations are in annual_tax_detail.csv, not individual actions
- New IRS ordering breakdown in charitable_carryforward.csv

### For Developers
- Add new fields to component dataclasses only
- CSV generation is automatic for component fields
- Custom display logic goes in CSV generators, not calculators

## Areas Potentially Needing Additional Detail

While this plan is comprehensive, the following areas might benefit from additional detail in implementation:

1. **Error Handling**: Specific error cases when components are missing expected fields
2. **Performance**: Whether DataFrame operations need optimization for large datasets
3. **Decimal Precision**: Exact rounding rules for financial amounts in CSV output
4. **Date Formatting**: Handling of timezone considerations if any exist
5. **Backward Compatibility**: Migration path for existing users with saved CSV files
6. **Column Ordering**: Detailed rules for column order in auto-generated CSVs
7. **Empty State Handling**: Behavior when no actions occur in a year
8. **Encoding**: UTF-8 vs other encodings for international users

These areas are likely straightforward to address during implementation but could be specified more precisely if needed.

## Implementation Summary

### Completed Items

#### Phase 1: Calculator Enhancements ✅
- **1.1 Update Charitable Deduction Ordering** ✅ - Implemented explicit IRS 4-step ordering
- **1.2 Add ISO Qualifying Date Calculation** ✅ - Added tax_utils.py and ShareLot.iso_qualifying_date property
- **1.3 Extend CharitableDeductionResult** ✅ - Fields already existed for IRS ordering breakdown

#### Phase 2: Component Enhancement ✅
- Added display fields to all component classes (action_date, action_type, calculator_name)
- Updated all calculators to populate these fields
- Tax treatment determination added to ShareSaleComponents

#### Phase 3: New CSV Generation Architecture ✅
- Created csv_generators.py with automatic field inclusion
- Implemented save_components_csv() and save_annual_summary_csv()
- Updated save_all_projection_csvs() to use new generators
- No pandas dependency - uses standard csv module

#### Phase 4: Specialized CSV Updates
- **4.1 Enhanced Charitable Carryforward CSV** ✅ - Successfully implemented with IRS 4-step ordering breakdown
  - Added `federal_charitable_deduction_result` and `ca_charitable_deduction_result` fields to YearlyState
  - Updated ProjectionCalculator to store CharitableDeductionResult objects
  - Created `save_charitable_carryforward_csv_enhanced()` that uses actual calculator results
  - Added explicit IRS 4-step ordering fields: cash_current_used, stock_current_used, cash_carryforward_used, stock_carryforward_used
  - Displays carryforward tracking by creation year for FIFO compliance
- **4.2 Add run_scenario_analysis CSV Generation** ✅ - CSV generation added to run_scenario_analysis.py

#### Phase 5: Cleanup ⚠️ (Partially Complete)
- **5.1 Remove detailed_materialization.py** ⏸️ - On hold (portfolio_manager.py still uses it)
- **5.2 Update Tests** ✅ - Created test_components_csv_data_quality.py

### Test Results
- Total tests: 31
- Passed: 30
- Failed: 1 (test_charitable_comprehensive_scenario.py has incorrect expected values)
- New test added: test_components_csv_data_quality.py

### Key Improvements Achieved

1. **Automatic Field Inclusion**: New fields in component dataclasses automatically appear in CSVs
2. **Single Source of Truth**: All data comes from authoritative calculators and state objects
3. **Progressive Tax Calculations**: Removed all flat tax rate approximations
4. **Maintainability**: Zero-maintenance CSV generation for component data
5. **IRS Compliance**: Charitable deduction ordering follows explicit IRS rules

### Remaining Work

1. **Portfolio Manager Update**: Remove materialize_detailed_projection usage
2. **Charitable Carryforward Enhancement**: Store full AnnualTaxResult in YearlyState
3. **Test Update**: Fix test_charitable_comprehensive_scenario.py expected values
4. **Complete Cleanup**: Remove detailed_materialization.py once no longer used

### Notes

- One test failure (test_charitable_comprehensive_scenario.py) is due to incorrect test expectations, not implementation issues
- The CSV consolidation successfully eliminates calculation duplication while preserving all functionality
- The new architecture makes it trivial to add new fields to CSVs without code changes
