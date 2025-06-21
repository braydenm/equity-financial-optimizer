# Charitable Deduction Tests

This directory contains comprehensive tests for charitable deduction calculations, including AGI limits, carryforward tracking, FIFO ordering, and 5-year expiration rules.

## Test Files

### test_charitable_deduction_limits.py
Tests basic AGI limit enforcement for charitable deductions:
- Federal: 60% for cash, 30% for stock donations
- California: 50% for cash, 30% for stock donations
- Basis election scenarios (using cost basis vs FMV)
- Mixed cash and stock donation limits

### test_charitable_carryforward_expiration.py
Tests the 5-year expiration rule for charitable deduction carryforwards:
- Basic expiration after 5 years
- Partial expiration with mixed creation years
- Federal vs California separate tracking
- CSV output includes expired amounts

### test_charitable_comprehensive_scenario.py
Comprehensive 7-year test scenario implementing detailed IRS rules:
- Varying AGI from $60K to $300K across years
- 50% limit organizations (overall limit is 50% of AGI)
- FIFO ordering (oldest carryforwards used first)
- Current year donations used before carryforwards
- Cash deductions applied before stock deductions
- 5-year expiration with proper tracking

### test_charitable_deduction_projection.py
Tests charitable deduction integration with multi-year projections:
- AGI limit enforcement in projection calculator
- Carryforward propagation across years
- Integration with annual tax calculations

## Key IRS Rules Implemented

### 1. AGI Limits
- **Federal**: 60% of AGI for cash, 30% for stock (or 50% overall for certain organizations)
- **California**: 50% of AGI for cash, 30% for stock
- Overall charitable deduction cannot exceed these limits

### 2. Deduction Ordering
1. Cash donations before stock donations
2. Current year donations before carryovers
3. When using carryovers, oldest first (FIFO)

### 3. Carryforward Rules
- Unused charitable deductions carry forward to future years
- Carryforwards expire after 5 years
- Creation year must be tracked for FIFO and expiration

### 4. 50% Limit Organizations
Some charitable organizations have an overall deduction limit of 50% of AGI instead of the standard 60% for federal taxes. The comprehensive test scenario uses this type of organization.

## Test Scenario Details

The comprehensive scenario (test_charitable_comprehensive_scenario.py) covers 7 years with:

**Year 2023**: AGI $200K, Cash $140K, Stock $70K
- Tests high donation amounts creating significant carryforwards

**Year 2024**: AGI $150K, Cash $100K, Stock $50K  
- Tests continued carryforward accumulation

**Year 2025**: AGI $80K, Cash $10K, Stock $5K
- Tests low AGI limiting deduction capacity

**Year 2026**: AGI $70K, Cash $8K, Stock $0
- Tests stock carryforward usage when cash is limited

**Year 2027**: AGI $60K, Cash $5K, Stock $0
- Tests minimum AGI scenario

**Year 2028**: AGI $180K, Cash $20K, Stock $40K
- Critical year: 2023 carryforwards expire after use
- Tests expiration tracking and reporting

**Year 2029**: AGI $300K, Cash $15K, Stock $5K
- Tests high AGI allowing full carryforward consumption

## Expected Outcomes

The test verifies:
1. **Correct AGI limit application** each year
2. **FIFO consumption** of carryforwards
3. **Proper expiration** of 2023 carryforwards in 2028
4. **Lost tax benefits** are tracked ($17K federal, $39K CA)
5. **Final carryforward balances** match expected values

## Running the Tests

Run individual test files:
```bash
python3 tests/test_charitable_comprehensive_scenario.py
```

Or run all tests:
```bash
python3 run_all_tests.py
```

## Implementation Notes

- The `fifty_pct_limit_org` parameter in `annual_tax_calculator.py` enables 50% limit organization calculations
- Carryforward tracking uses dictionaries mapping creation year to amount for FIFO compliance
- The projection calculator must carefully track carryforwards between years while preserving creation dates
- Cash and stock carryforwards are tracked separately as they have different AGI limits