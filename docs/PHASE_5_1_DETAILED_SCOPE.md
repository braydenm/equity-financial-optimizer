# Phase 5.1 Detailed Scope: Remove detailed_materialization.py

## Current State Analysis

### Duplicate CSV Generation Issue
Currently, we have a critical issue where CSV files are being generated twice:

1. **Old System** (detailed_materialization.py):
   - Generates: `{scenario}_action_summary.csv`
   - Generates: `{scenario}_annual_summary.csv`
   - Called from: `projection_output.py` → `save_all_projection_csvs()`

2. **New System** (csv_generators.py):
   - Generates: `{scenario}_components.csv` (replacement for action_summary)
   - Generates: `{scenario}_annual_summary.csv` (DUPLICATE!)
   - Called from: `projection_output.py` → `save_all_projection_csvs()`

**Problem**: annual_summary.csv is being generated twice, potentially with different data!

### Dependencies on detailed_materialization.py

#### Direct Dependencies:
1. **projection_output.py**
   - Line 1278-1282: Imports but comments say "replacing detailed_materialization"
   - The import was removed and materialize_detailed_projection call was replaced

2. **test_action_summary_data_quality.py**
   - Lines 150-152: Imports and uses materialize_detailed_projection
   - Expects action_summary.csv to exist

#### Indirect Dependencies (files expecting old CSVs):
1. **copy_scenario_csvs.py** - References action_summary.csv
2. **examples/test_natural_evolution.py** - Expects action_summary.csv
3. **run_scenario_analysis.py** - Comments reference action_summary.csv
4. **tests/test_csv_generation.py** - Validates annual_summary.csv format
5. **tests/test_csv_generation_comprehensive.py** - Tests annual_summary.csv

### CSV Field Comparison

#### action_summary.csv vs components.csv

**Old action_summary.csv fields** (from detailed_materialization.py):
```
year, date, type, lot_id, quantity, price,
exercise_date, holding_period_days, tax_treatment,
calculator, gross_proceeds, exercise_cost, capital_gain,
amt_adjustment, tax, donation_value, company_match,
pledge_created, net_cash_change, vest_expiration_date, notes,
current_share_price, action_value, lot_options_remaining, lot_shares_remaining
```

**New components.csv fields** (from csv_generators.py):
```
year, component_type, lot_id, shares_exercised, shares_sold, shares_donated,
amount, action_date, action_type, calculator_name,
[All component-specific fields from dataclasses - automatically included]
```

**Key Differences**:
- `type` → `action_type` and `component_type`
- `date` → `action_date` 
- `quantity` → `shares_exercised`, `shares_sold`, or `shares_donated` (specific to action)
- `tax` → REMOVED (individual action tax impact cannot be accurately attributed)
- `calculator` → `calculator_name`
- `net_cash_change` → REMOVED (oversimplified calculation)
- All other component fields automatically included from dataclasses

**Migration Notes**:
- components.csv has MORE data (all dataclass fields included automatically)
- Financial calculations are more accurate (no flat tax rates)
- Field names are more descriptive
- No manual field mapping required for new fields

#### annual_summary.csv Compatibility

**Fields in both old and new versions**:
```
year, w2_income, total_income, exercise_costs, sale_proceeds, capital_gains,
donations, company_match, total_charitable_impact,
pledge_shares_obligated, pledge_shares_donated, pledge_shares_outstanding, pledge_shares_expired,
options_exercised_count, shares_sold_count, shares_donated_count, expired_option_count,
regular_tax, amt_tax, total_tax,
amt_credits_generated, amt_credits_consumed, amt_credits_balance,
ending_cash, equity_value, net_worth, expired_option_loss
```

**New fields in new version only**:
- `spouse_income` - Separate tracking of spouse W2 income
- `other_income` - Other income sources

**Compatibility**: The new annual_summary.csv is a superset of the old version, making it a drop-in replacement.

## Implementation Plan

### Step 1: Resolve Duplicate annual_summary.csv Generation

**Option A**: Keep old annual_summary.csv temporarily
- Rename new version to `{scenario}_annual_summary_v2.csv`
- Allows gradual migration
- No immediate breaking changes

**Option B**: Replace immediately (RECOMMENDED)
- Remove materialize_detailed_projection call entirely
- New annual_summary.csv takes over
- One-time breaking change

**Decision**: Option B - Clean break is better than maintaining two versions

### Step 2: Update projection_output.py

**Current Code** (lines 10-13 and 1278-1282):
```python
# Line 10-13
from projections.csv_generators import save_components_csv, save_annual_summary_csv

# Lines 1278-1282
# NEW: Component-based CSVs replacing detailed_materialization
save_components_csv(result, f"{output_dir}/{base_name}_components.csv")
save_annual_summary_csv(result, f"{output_dir}/{base_name}_annual_summary.csv")
```

**Required Changes**:
1. Remove any import of detailed_materialization (already done)
2. Remove any call to materialize_detailed_projection (already done)
3. No further changes needed - projection_output.py is already updated!

### Step 3: Update test_action_summary_data_quality.py

**Options**:
1. Delete the test entirely (it tests the old system)
2. Redirect it to test components.csv instead
3. Keep it but mark as legacy/deprecated

**Recommendation**: Option 2 - Redirect to components.csv

**Current Code** (lines 148-155):
```python
# Find the generated action summary CSV
from projections.detailed_materialization import materialize_detailed_projection
output_dir = tempfile.mkdtemp()
materialize_detailed_projection(result, output_dir, "test_action_summary")
action_summary_path = f"{output_dir}/test_action_summary_action_summary.csv"

# Read and analyze the CSV
with open(action_summary_path, 'r') as f:
    reader = csv.DictReader(f)
```

**Change To**:
```python
# Find the generated components CSV
from projections.projection_output import save_all_projection_csvs
output_dir = tempfile.mkdtemp()
save_all_projection_csvs(result, "test_action_summary", output_dir)
components_path = f"{output_dir}/test_action_summary_components.csv"

# Read and analyze the CSV
with open(components_path, 'r') as f:
    reader = csv.DictReader(f)
```

**Additional Changes**:
- Update field names in assertions:
  - `'type'` → `'action_type'`
  - `'date'` → `'action_date'`
  - `'quantity'` → `'shares_exercised'`, `'shares_sold'`, or `'shares_donated'`
  - Remove assertions for `'tax'` field (no longer included)
  - Remove assertions for `'net_cash_change'` field (no longer included)

### Step 4: Update Other Dependencies

#### copy_scenario_csvs.py

**Current Code** (lines 42-52):
```python
return {
    'annual_summary.csv': 1,
    'action_summary.csv': 2,
    'annual_tax_detail.csv': 3,
    'comprehensive_cashflow.csv': 4,
    'pledge_obligations.csv': 5,
    'charitable_carryforward.csv': 6,
    'holding_period_tracking.csv': 7,
    'state_timeline.csv': 8,
    'transition_timeline.csv': 9,
}
```

**Change To**:
```python
return {
    'annual_summary.csv': 1,
    'components.csv': 2,  # Replaces action_summary.csv
    'annual_tax_detail.csv': 3,
    'comprehensive_cashflow.csv': 4,
    'pledge_obligations.csv': 5,
    'charitable_carryforward.csv': 6,
    'holding_period_tracking.csv': 7,
    'state_timeline.csv': 8,
    'transition_timeline.csv': 9,
}
```

#### examples/test_natural_evolution.py

**Current Code** (lines 172-180):
```python
expected_files = [
    f"{output_dir}/natural_evolution_annual_tax_detail.csv",
    f"{output_dir}/natural_evolution_state_timeline.csv",
    f"{output_dir}/natural_evolution_transition_timeline.csv",
    f"{output_dir}/natural_evolution_action_summary.csv",
    f"{output_dir}/natural_evolution_annual_summary.csv",
    f"{output_dir}/natural_evolution_holding_period_tracking.csv",
    f"{output_dir}/natural_evolution_charitable_carryforward.csv"
]
```

**Change To**:
```python
expected_files = [
    f"{output_dir}/natural_evolution_annual_tax_detail.csv",
    f"{output_dir}/natural_evolution_state_timeline.csv",
    f"{output_dir}/natural_evolution_transition_timeline.csv",
    f"{output_dir}/natural_evolution_components.csv",  # Replaces action_summary.csv
    f"{output_dir}/natural_evolution_annual_summary.csv",
    f"{output_dir}/natural_evolution_holding_period_tracking.csv",
    f"{output_dir}/natural_evolution_charitable_carryforward.csv",
    f"{output_dir}/natural_evolution_comprehensive_cashflow.csv"  # Add missing file
]
```

#### run_scenario_analysis.py

**Current Code** (lines 499-503):
```python
# 4. ACTION SUMMARY TABLE
print(f"\n{'-'*80}")
print("ACTION SUMMARY (→ action_summary.csv)")
print(f"{'-'*80}")
print(f"{'Date':<12} {'Action_Type':<12} {'Lot_ID':<20} {'Quantity':<12}")
```

**Change To**:
```python
# 4. COMPONENT SUMMARY TABLE
print(f"\n{'-'*80}")
print("COMPONENT SUMMARY (→ components.csv)")
print(f"{'-'*80}")
print(f"{'Date':<12} {'Component':<15} {'Action':<10} {'Lot_ID':<20} {'Quantity':<12}")
```

Also update the data row formatting to match new column structure.

### Step 5: Migration Guide for Users

Create a migration notice:
```markdown
## CSV Output Changes

### Removed Files:
- `action_summary.csv` → Replaced by `components.csv`

### Changed Files:
- `annual_summary.csv` → Now generated by new system (format unchanged)

### New Files:
- `components.csv` → Comprehensive component data with automatic field inclusion

### Migration Steps:
1. Update any scripts reading `action_summary.csv` to use `components.csv`
2. The data is richer but column names may differ slightly
3. All financial calculations now use progressive tax brackets (no flat rates)
```

### Step 6: Delete detailed_materialization.py

Only after all above steps are complete:
1. Delete the file: `rm projections/detailed_materialization.py`
2. Verify no remaining imports: `grep -r "detailed_materialization" . --include="*.py"`
3. Run all tests: `python3 run_all_tests.py`
4. Verify CSV outputs: `python3 run_scenario_analysis.py 000 --demo`

**Expected Results**:
- No import errors
- All tests pass (except test_charitable_comprehensive_scenario.py which has incorrect expectations)
- CSV files generated without duplicates
- No action_summary.csv files created

## Risk Assessment

### High Risk:
- Breaking existing user scripts that depend on action_summary.csv
- Tests may fail if they expect specific CSV formats

### Medium Risk:
- annual_summary.csv format differences between old and new
- Documentation references to old CSV files

### Low Risk:
- Internal refactoring (no external API changes)
- New system is already tested and working

## Rollback Plan

If issues arise:
1. Revert the projection_output.py changes
2. Restore materialize_detailed_projection call
3. Keep both systems running temporarily
4. Address issues before re-attempting

## Testing Strategy

1. **Before Changes**:
   - Save example CSVs from current system
   - Document current column names and formats

2. **After Changes**:
   - Compare new CSV outputs with saved examples
   - Verify all expected columns exist
   - Run full test suite
   - Manual testing with demo scenarios

3. **Validation Checklist**:
   - [ ] All tests pass
   - [ ] components.csv contains all data from action_summary.csv
   - [ ] annual_summary.csv format unchanged
   - [ ] No duplicate files generated
   - [ ] Documentation updated

## Implementation Checklist

### Pre-Implementation
- [ ] Create backup of current CSV outputs for comparison
- [ ] Document current action_summary.csv consumers
- [ ] Review test dependencies

### Implementation Steps
- [ ] Step 1: Verify projection_output.py already updated (no changes needed)
- [ ] Step 2: Update test_action_summary_data_quality.py
  - [ ] Change import from detailed_materialization to projection_output
  - [ ] Update path from action_summary.csv to components.csv
  - [ ] Update field name assertions
- [ ] Step 3: Update copy_scenario_csvs.py
  - [ ] Replace 'action_summary.csv' with 'components.csv' in priority list
- [ ] Step 4: Update examples/test_natural_evolution.py
  - [ ] Replace action_summary.csv with components.csv in expected files
  - [ ] Add comprehensive_cashflow.csv to expected files
- [ ] Step 5: Update run_scenario_analysis.py
  - [ ] Update table header from "ACTION SUMMARY" to "COMPONENT SUMMARY"
  - [ ] Update column headers to match new format
- [ ] Step 6: Delete detailed_materialization.py
  - [ ] Run `rm projections/detailed_materialization.py`
  - [ ] Verify no remaining imports
- [ ] Step 7: Run full test suite
- [ ] Step 8: Test with demo scenarios
- [ ] Step 9: Update documentation

### Post-Implementation
- [ ] Create migration guide for users
- [ ] Update CSV_OUTPUT_GUIDE.md
- [ ] Commit changes with clear message about CSV migration

## Success Criteria

- Zero duplicate CSV files
- All tests passing
- Clean codebase with single CSV generation system
- Clear migration path documented
- No loss of functionality or data