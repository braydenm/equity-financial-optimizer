# CSV Generation Consolidation Plan

**Document Version:** 1.0  
**Created:** December 2024  
**Target Implementation:** Q1 2025  

## Executive Summary

This document outlines a comprehensive plan to consolidate the current split CSV generation architecture in the Equity Financial Optimizer. The consolidation will unify two separate systems (`projection_output.py` and `detailed_materialization.py`) into a single, component-driven architecture that eliminates code duplication and ensures data consistency across all CSV outputs.

## Current State Analysis

### Architecture Problems

**1. Split CSV Generation Systems**
- `projection_output.py`: 1,183 lines, handles 7 core financial CSVs
- `detailed_materialization.py`: 720 lines, handles 2 analysis CSVs
- No shared infrastructure or consistent data access patterns

**2. Data Source Inconsistency**
- `projection_output.py`: Uses rich component data from calculators
- `detailed_materialization.py`: Reconstructs data with basic calculations
- Results in different values for the same financial metrics

**3. Code Duplication**
- CSV writing boilerplate repeated across both systems
- Field calculation logic duplicated
- Similar data transformations implemented differently

**4. Integration Issues**
- `run_scenario_analysis.py` doesn't generate CSVs at all
- Multiple entry points with inconsistent behavior
- `save_all_projection_csvs()` delegates to separate system

### Current CSV Distribution

**`projection_output.py` CSVs:**
- `annual_tax_detail.csv` - Tax breakdown by year
- `state_timeline.csv` - Share quantity tracking
- `transition_timeline.csv` - State transition tracking  
- `holding_period_tracking.csv` - Milestone tracking
- `charitable_carryforward.csv` - Carryforward FIFO tracking
- `comprehensive_cashflow.csv` - Cash flow analysis

**`detailed_materialization.py` CSVs:**
- `action_summary.csv` - Transaction-level details ❌ BROKEN
- `annual_summary.csv` - Year-level aggregations ⚠️ PARTIALLY FIXED

### Component Data Flow Analysis

**Rich Component Data Available:**
```
YearlyState.annual_tax_components:
  ├── iso_exercise_components[]     # exercise_cost, bargain_element
  ├── nso_exercise_components[]     # exercise_cost, bargain_element  
  ├── sale_components[]             # gross_proceeds, gains, holding_period
  ├── donation_components[]         # company_match, donation_value
  └── cash_donation_components[]    # amount, company_match
```

**DetailedMaterializer Issues:**
- Ignores `annual_tax_components` rich data
- Recalculates `exercise_cost = quantity * strike_price` 
- Shows zeros for `amt_adjustment`, `tax`, `company_match`
- Cannot access individual action tax impacts

## Target Architecture

### High-Level Design Principles

**1. Single Source of Truth**
- All CSV generation in `projection_output.py`
- Component-driven data access throughout
- Consistent field calculations across all CSVs

**2. Layered Data Access**
```
Component Layer:    ISOExerciseComponents, SaleComponents, etc.
Aggregation Layer:  AnnualTaxComponents, CharitableState, etc.  
State Layer:        YearlyState, ProjectionResult
CSV Layer:          Unified CSV generation functions
```

**3. Unified Entry Point**
```python
def generate_complete_csv_suite(
    result: ProjectionResult, 
    scenario_name: str, 
    output_dir: str = "output"
) -> None:
    """Single entry point for all CSV generation."""
```

**4. Component-First Design**
- Action-level CSVs extract from individual components
- Annual CSVs aggregate from component collections
- No basic recalculation of component-calculated values

### Target File Structure

**Post-Consolidation:**
```
projection_output.py (1,900+ lines)
├── Core CSV Functions (existing, 7 CSVs)
├── DetailedCSVGenerator class (new, from DetailedMaterializer)
├── Component Extraction Functions (new)
├── Unified Entry Point (new)
└── Helper Functions (consolidated)
```

**Eliminated:**
- `detailed_materialization.py` (deleted)
- `materialize_detailed_projection()` function
- Duplicate CSV infrastructure

## Detailed Migration Plan

### Phase 1: Component Integration Analysis (1 day)

**1.1 Audit Component Usage Discrepancies**

**Exercise Cost Calculation:**
- Current DetailedMaterializer: `exercise_cost = action.quantity * lot.strike_price`
- Component Data: `ISOExerciseComponents.exercise_cost`, `NSOExerciseComponents.exercise_cost`
- **Resolution:** Use component values directly

**AMT Adjustment Calculation:**
- Current DetailedMaterializer: Basic FMV - strike calculation
- Component Data: `ISOExerciseComponents.bargain_element`  
- **Resolution:** Map `bargain_element` to `amt_adjustment` field

**Tax Calculation:**
- Current DetailedMaterializer: Shows 0.0 for all actions
- Component Data: No individual action tax (calculated annually)
- **Resolution:** Add action-level tax allocation from annual totals

**Company Match Calculation:**
- Current DetailedMaterializer: Attempts component lookup but shows 0.0
- Component Data: `DonationComponents.company_match_amount`
- **Resolution:** Fix component accessor logic

**1.2 Document Calculation Conflicts**

Create mapping table:
```
CSV Field                 | Current Logic          | Component Source        | Resolution
--------------------------|------------------------|-------------------------|------------------
exercise_cost            | quantity * strike      | component.exercise_cost | Use component
amt_adjustment           | Basic calculation      | component.bargain_ele   | Use component  
tax                      | 0.0 (broken)          | Allocate from annual    | New allocation logic
company_match            | 0.0 (broken)          | component.company_match | Fix accessor
capital_gain             | Basic proceeds-basis   | component.gains         | Use component
gross_proceeds           | quantity * price       | component.gross_proc    | Use component
```

### Phase 2: Core Infrastructure Migration (2 days)

**2.1 Move DetailedMaterializer to projection_output.py**

**2.1.1 Class Migration**
```python
# Move entire class structure:
class DetailedCSVGenerator:  # Renamed from DetailedMaterializer
    """Component-driven detailed CSV generation."""
    
    def __init__(self):
        self.detailed_years: List[DetailedYear] = []
    
    def generate_detailed_csvs(self, result: ProjectionResult) -> List[DetailedYear]:
        # Renamed from materialize_projection()
        
    def save_action_summary_csv(self, detailed_years: List[DetailedYear], output_path: str):
        # Renamed from save_action_level_csv()
        
    def save_annual_summary_csv(self, detailed_years: List[DetailedYear], result: ProjectionResult, output_path: str):
        # Keep existing name
```

**2.1.2 Data Structure Migration**
```python
# Move supporting classes:
@dataclass 
class DetailedAction:    # 80+ fields, no changes
@dataclass
class DetailedYear:      # 40+ fields, no changes
```

**2.2 Fix Component Data Access**

**2.2.1 Create Component Extractors**
```python
def extract_exercise_details(component: Union[ISOExerciseComponents, NSOExerciseComponents]) -> dict:
    """Extract standardized exercise details from components."""
    return {
        'exercise_cost': component.exercise_cost,
        'amt_adjustment': getattr(component, 'bargain_element', 0.0),
        'strike_price': component.strike_price,
        'fmv_at_exercise': component.fmv_at_exercise,
        'shares_exercised': component.shares_exercised
    }

def extract_sale_details(component: ShareSaleComponents) -> dict:
    """Extract standardized sale details from components."""
    return {
        'gross_proceeds': component.gross_proceeds,
        'cost_basis': component.cost_basis,
        'short_term_gain': component.short_term_gain,
        'long_term_gain': component.long_term_gain,
        'ordinary_income': component.ordinary_income,
        'holding_period_days': component.holding_period_days
    }

def extract_donation_details(component: DonationComponents) -> dict:
    """Extract standardized donation details from components."""
    return {
        'donation_value': component.donation_value,
        'company_match': component.company_match_amount,
        'deduction_type': component.deduction_type,
        'cost_basis': component.cost_basis,
        'holding_period_days': component.holding_period_days
    }
```

**2.2.2 Update Action Materialization**
```python
def _materialize_action(self, action: PlannedAction, yearly_state: YearlyState, prev_state: Optional[YearlyState]) -> DetailedAction:
    """Updated to use component data instead of basic calculations."""
    
    detailed = DetailedAction(...)
    
    # Find matching component in annual_tax_components
    if action.action_type == ActionType.EXERCISE:
        component = self._find_exercise_component(action, yearly_state.annual_tax_components)
        if component:
            exercise_details = extract_exercise_details(component)
            detailed.exercise_cost = exercise_details['exercise_cost']
            detailed.amt_adjustment = exercise_details['amt_adjustment']
        else:
            # Fallback to basic calculation with warning
            logger.warning(f"No component found for exercise action {action.lot_id}")
            
    elif action.action_type == ActionType.SELL:
        component = self._find_sale_component(action, yearly_state.annual_tax_components)
        if component:
            sale_details = extract_sale_details(component)
            detailed.gross_proceeds = sale_details['gross_proceeds']
            detailed.capital_gain = sale_details['short_term_gain'] + sale_details['long_term_gain']
            # ... etc
            
    elif action.action_type == ActionType.DONATE:
        component = self._find_donation_component(action, yearly_state.annual_tax_components)
        if component:
            donation_details = extract_donation_details(component)
            detailed.company_match = donation_details['company_match']
            detailed.donation_value = donation_details['donation_value']
```

**2.3 Add Component Lookup Functions**
```python
def _find_exercise_component(self, action: PlannedAction, components: AnnualTaxComponents) -> Optional[Union[ISOExerciseComponents, NSOExerciseComponents]]:
    """Find matching exercise component for action."""
    for component in components.iso_exercise_components + components.nso_exercise_components:
        if (component.lot_id == action.lot_id and 
            component.exercise_date == action.action_date and
            component.shares_exercised == action.quantity):
            return component
    return None

def _find_sale_component(self, action: PlannedAction, components: AnnualTaxComponents) -> Optional[ShareSaleComponents]:
    """Find matching sale component for action."""
    for component in components.sale_components:
        if (component.lot_id == action.lot_id and 
            component.sale_date == action.action_date and
            component.shares_sold == action.quantity):
            return component
    return None

def _find_donation_component(self, action: PlannedAction, components: AnnualTaxComponents) -> Optional[DonationComponents]:
    """Find matching donation component for action."""
    for component in components.donation_components:
        if (component.lot_id == action.lot_id and 
            component.donation_date == action.action_date and
            component.shares_donated == action.quantity):
            return component
    return None
```

### Phase 3: Tax Allocation Logic (1 day)

**3.1 Action-Level Tax Allocation Problem**

**Challenge:** Components calculate annual totals, but CSV needs individual action taxes.

**Current Issue:**
- `DetailedAction.total_tax_on_action` shows 0.0 for all actions
- Taxes are calculated annually, not per-action
- No existing allocation mechanism

**3.2 Tax Allocation Strategy**

**Option A: Proportional Allocation**
```python
def allocate_annual_tax_to_actions(self, detailed_year: DetailedYear, yearly_state: YearlyState):
    """Allocate annual tax totals proportionally to individual actions."""
    
    total_taxable_value = sum(
        action.gross_proceeds + action.ordinary_income 
        for action in detailed_year.actions 
        if action.action_type in ['sell', 'exercise']
    )
    
    if total_taxable_value > 0:
        annual_tax = yearly_state.tax_paid
        for action in detailed_year.actions:
            if action.action_type in ['sell', 'exercise']:
                action_taxable = action.gross_proceeds + action.ordinary_income
                action.total_tax_on_action = annual_tax * (action_taxable / total_taxable_value)
```

**Option B: Component-Specific Allocation**
```python
def allocate_tax_by_component_type(self, detailed_year: DetailedYear, yearly_state: YearlyState):
    """Allocate tax based on component type and marginal rates."""
    
    # Calculate marginal rates for different income types
    marginal_ordinary = self._calculate_marginal_ordinary_rate(yearly_state)
    marginal_ltcg = self._calculate_marginal_ltcg_rate(yearly_state) 
    marginal_stcg = marginal_ordinary  # STCG taxed as ordinary
    
    for action in detailed_year.actions:
        if action.action_type == 'exercise':
            action.total_tax_on_action = action.ordinary_income * marginal_ordinary
        elif action.action_type == 'sell':
            action.total_tax_on_action = (
                action.short_term_gain * marginal_stcg + 
                action.long_term_gain * marginal_ltcg
            )
```

**Recommendation:** Use Option B for more accurate tax attribution.

### Phase 4: Unified Entry Point Creation (0.5 days)

**4.1 Create Central CSV Generation Function**
```python
def generate_complete_csv_suite(result: ProjectionResult, scenario_name: str, output_dir: str = "output") -> None:
    """
    Single entry point for all CSV generation.
    
    Generates all 9 CSV types:
    - Core Financial CSVs (7): annual_tax_detail, state_timeline, etc.
    - Analysis CSVs (2): action_summary, annual_summary
    
    Args:
        result: ProjectionResult containing all calculation results
        scenario_name: Scenario name for file naming
        output_dir: Output directory path
    """
    base_name = scenario_name.lower().replace(' ', '_').replace('-', '_')
    
    # Generate core financial CSVs (existing functions)
    save_annual_tax_detail_csv(result, f"{output_dir}/{base_name}_annual_tax_detail.csv")
    save_state_timeline_csv(result, f"{output_dir}/{base_name}_state_timeline.csv")
    save_transition_timeline_csv(result, f"{output_dir}/{base_name}_transition_timeline.csv")
    generate_holding_milestones_csv(result, f"{output_dir}/{base_name}_holding_period_tracking.csv")
    save_charitable_carryforward_csv(result, f"{output_dir}/{base_name}_charitable_carryforward.csv")
    save_comprehensive_cashflow_csv(result, f"{output_dir}/{base_name}_comprehensive_cashflow.csv")
    
    # Generate analysis CSVs (new unified approach)
    detailed_generator = DetailedCSVGenerator()
    detailed_years = detailed_generator.generate_detailed_csvs(result)
    detailed_generator.save_action_summary_csv(detailed_years, f"{output_dir}/{base_name}_action_summary.csv")
    detailed_generator.save_annual_summary_csv(detailed_years, result, f"{output_dir}/{base_name}_annual_summary.csv")
    
    # Create metadata file
    _save_generation_metadata(result, f"{output_dir}/metadata.json")
```

**4.2 Update All Callers**
```python
# Before:
save_all_projection_csvs(result, scenario_name, output_dir)
materialize_detailed_projection(result, output_dir, scenario_name)

# After:
generate_complete_csv_suite(result, scenario_name, output_dir)
```

**4.3 Caller Update Locations**
- `engine/portfolio_manager.py` - Update `execute_single_scenario()`
- `run_scenario_analysis.py` - Add CSV generation call  
- Test files - Update to use new entry point

### Phase 5: Testing and Validation (1 day)

**5.1 Create Validation Suite**
```python
def test_csv_consolidation_equivalence():
    """Test that new system produces equivalent results to old system."""
    
    # Run scenario with old system (before consolidation)
    old_result = run_scenario_old_way("test_scenario")
    old_csvs = load_old_csvs()
    
    # Run scenario with new system (after consolidation)  
    new_result = run_scenario_new_way("test_scenario")
    new_csvs = load_new_csvs()
    
    # Compare all numeric fields (allowing small rounding differences)
    for csv_name in ['action_summary', 'annual_summary']:
        assert_csv_equivalence(old_csvs[csv_name], new_csvs[csv_name], tolerance=0.01)
```

**5.2 Component Data Validation**
```python
def test_component_data_usage():
    """Test that components are being used instead of basic calculations."""
    
    result = run_test_scenario()
    detailed_generator = DetailedCSVGenerator()
    detailed_years = detailed_generator.generate_detailed_csvs(result)
    
    # Verify exercise costs come from components
    for year in detailed_years:
        for action in year.actions:
            if action.action_type == 'exercise':
                assert action.exercise_cost > 0, "Exercise cost should not be 0"
                assert action.amt_adjustment != 0 or action.calculator_used == 'nso_exercise_calculator'
                
            if action.action_type == 'donate':
                assert action.company_match >= 0, "Company match should be populated"
```

**5.3 End-to-End Integration Test**
```python
def test_e2e_csv_generation():
    """Test complete CSV generation pipeline."""
    
    # Test all entry points
    result = create_test_projection_result()
    
    # Test main entry point
    generate_complete_csv_suite(result, "test_scenario", "/tmp/test_output")
    
    # Verify all 9 CSV files exist
    expected_files = [
        'test_scenario_annual_tax_detail.csv',
        'test_scenario_state_timeline.csv', 
        'test_scenario_transition_timeline.csv',
        'test_scenario_holding_period_tracking.csv',
        'test_scenario_charitable_carryforward.csv', 
        'test_scenario_comprehensive_cashflow.csv',
        'test_scenario_action_summary.csv',
        'test_scenario_annual_summary.csv',
        'metadata.json'
    ]
    
    for file in expected_files:
        assert os.path.exists(f"/tmp/test_output/{file}")
        assert os.path.getsize(f"/tmp/test_output/{file}") > 0
```

### Phase 6: Cleanup and Documentation (0.5 days)

**6.1 Remove Old System**
- Delete `detailed_materialization.py`
- Remove imports of `materialize_detailed_projection` 
- Update documentation references

**6.2 Update Documentation**
- Update `CLAUDE.md` to remove consolidation plan (completed)
- Update `TECHNICAL_ARCHITECTURE.md` with new unified approach
- Add docstring examples for new entry point

**6.3 Update CHANGELOG.md**
```markdown
## [Next Version] - CSV Generation Consolidation

### Major Changes
- **BREAKING:** Consolidated CSV generation into single system in `projection_output.py`
- **BREAKING:** Replaced `materialize_detailed_projection()` with `generate_complete_csv_suite()`
- **FIXED:** Action summary CSV now uses component data instead of basic calculations
- **FIXED:** Exercise costs, AMT adjustments, company match amounts now show correct values

### Migration Guide
- Replace calls to `materialize_detailed_projection()` with `generate_complete_csv_suite()`
- Update imports from `detailed_materialization` to `projection_output`
- No changes to CSV file formats or field names
```

## Risk Mitigation

### High-Risk Areas

**1. Component Lookup Failures**
- **Risk:** Action cannot find matching component
- **Mitigation:** Fallback to basic calculation with warning
- **Testing:** Verify all actions have matching components in test scenarios

**2. Tax Allocation Accuracy**
- **Risk:** Action-level tax allocation differs significantly from current (broken) values
- **Mitigation:** Accept that current values are wrong, validate new logic independently
- **Testing:** Compare total taxes (should match), verify action allocation is reasonable

**3. Data Type Mismatches**
- **Risk:** Component data types don't match DetailedAction expectations
- **Mitigation:** Add type conversion in extraction functions
- **Testing:** Type checking in validation suite

**4. Performance Regression**
- **Risk:** Component lookup adds processing time
- **Mitigation:** Use indexes for component lookup if needed
- **Testing:** Performance benchmarks before/after

### Medium-Risk Areas

**1. Import Dependencies**
- **Risk:** Moving DetailedMaterializer breaks existing imports
- **Mitigation:** Phased migration with temporary aliases
- **Testing:** Import verification in test suite

**2. CSV Field Order Changes**
- **Risk:** External tools expect specific column order
- **Mitigation:** Maintain exact field order during migration
- **Testing:** Field order verification tests

### Low-Risk Areas

**1. File Size Changes**
- **Risk:** Consolidated file becomes too large
- **Mitigation:** Split into logical modules if needed
- **Impact:** Development workflow only

## Testing Strategy

### Test Categories

**1. Unit Tests**
- Component extraction functions
- Tax allocation algorithms  
- CSV field calculations
- Component lookup functions

**2. Integration Tests**
- Complete CSV generation pipeline
- Entry point validation
- File existence and format verification

**3. Regression Tests**  
- Numeric equivalence (where current values are correct)
- Field presence verification
- Data type consistency

**4. Performance Tests**
- CSV generation time benchmarks
- Memory usage profiling
- Component lookup efficiency

### Test Data Requirements

**Scenarios Needed:**
- Simple scenario (1-2 actions per year)
- Complex scenario (10+ actions per year)  
- Edge cases (zero amounts, missing components)
- Multi-year scenarios (5+ years)
- All action types (exercise, sell, donate)

**Component Coverage:**
- ISO exercises (AMT adjustments)
- NSO exercises (ordinary income)
- Short-term sales (STCG)
- Long-term sales (LTCG)
- Charitable donations (company match)
- Cash donations

## Timeline and Resource Allocation

### Total Estimated Effort: 5-6 days

**Day 1: Analysis and Planning**
- Component usage audit
- Calculation conflict resolution
- Detailed design decisions

**Day 2-3: Core Migration**  
- Move DetailedMaterializer class
- Implement component extractors
- Fix component data access

**Day 4: Tax Allocation**
- Implement action-level tax allocation
- Test allocation accuracy
- Validate against annual totals

**Day 5: Integration and Testing**
- Create unified entry point
- Update all callers
- Run validation suite

**Day 6: Cleanup and Documentation**
- Remove old system
- Update documentation
- Final testing

### Prerequisites

**Required:**
- All existing tests must pass before starting
- No pending changes to component structures
- Backup of current system for comparison testing

**Recommended:**
- Detailed understanding of component data flow
- Access to multiple test scenarios
- Performance baseline measurements

## Success Criteria

### Functional Requirements

**1. Feature Parity**
- All 9 CSV files continue to be generated
- All CSV fields maintain current names and order
- No loss of data or functionality

**2. Data Accuracy Improvements**
- Action summary CSV shows non-zero values for key fields
- Exercise costs match component calculations exactly
- Company match amounts reflect actual component data

**3. Architectural Improvements**
- Single entry point for all CSV generation
- Component-driven data access throughout
- No code duplication between CSV generators

### Non-Functional Requirements

**1. Performance**
- CSV generation time within 10% of current performance
- Memory usage does not significantly increase
- Component lookup remains efficient

**2. Maintainability**
- Unified codebase easier to modify and extend
- Clear separation between component extraction and CSV formatting
- Comprehensive test coverage for all new functionality

**3. Reliability**
- Graceful handling of missing components
- Clear error messages for debugging
- Robust fallback mechanisms

## Post-Implementation Monitoring

### Validation Checkpoints

**Week 1:** Monitor for any regression reports
**Week 2:** Validate CSV outputs in production scenarios  
**Month 1:** Performance assessment and optimization if needed

### Metrics to Track

- CSV generation success rate
- Average processing time per scenario
- User reports of CSV data accuracy issues
- Development velocity for CSV-related features

## Conclusion

This consolidation plan addresses the fundamental architectural issues in the current CSV generation system while maintaining backward compatibility and improving data accuracy. The phased approach minimizes risk while providing clear checkpoints for validation.

The end result will be a unified, component-driven CSV generation system that eliminates code duplication, ensures data consistency, and provides a solid foundation for future enhancements.

**Next Steps:**
1. Review and approve this plan
2. Set up development environment with test scenarios
3. Begin Phase 1 implementation
4. Establish regular check-ins for progress tracking

---

*This document serves as the definitive specification for the CSV generation consolidation project. Any deviations from this plan should be documented and approved through the standard change control process.*