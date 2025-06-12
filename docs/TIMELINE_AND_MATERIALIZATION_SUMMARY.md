# Timeline Generation and Detailed Financial Materialization - Implementation Summary

## Overview

This document summarizes the implementation of two critical features for the Equity Financial Optimizer:

1. **Automated Timeline Generation** - Ensures equity position timelines match the active data source (demo vs user)
2. **Detailed Financial Materialization** - Provides comprehensive CSV output showing every calculation step

## Timeline Generation Feature

### Problem Solved

Previously, the system would fail when switching between demo and user data because:
- The equity position timeline contained lot IDs from one data source (e.g., "VCS-107" from user data)
- But scenarios referenced lot IDs from another data source (e.g., "RSU_2021_001" from demo data)
- This mismatch caused "Exercise dates missing for exercised lots" errors

### Solution Implemented

Created an automated timeline generation system that:

1. **Detects the active data source** when loading profiles (demo vs user)
2. **Generates data-source specific timelines** automatically
3. **Saves timelines to appropriate locations**:
   - `output/demo/timeline/equity_position_timeline.csv` for demo data
   - `output/user/timeline/equity_position_timeline.csv` for user data

### Key Components

#### `engine/timeline_generator.py`
A new module that:
- Generates timelines from the appropriate profile data
- Creates lot IDs that match the data source
- Handles vesting calendars and exercise dates correctly
- Provides consistent output structure

#### Integration with `PortfolioManager`
The portfolio manager now:
- Automatically generates timelines when loading user data
- Uses the `--demo` flag to determine which timeline to generate
- Ensures scenarios always have matching lot IDs

### Usage

The timeline generation is now automatic:

```bash
# Using demo data - generates demo timeline automatically
python3 run_portfolio_analysis.py portfolios/tax_strategies.json --demo

# Using user data - generates user timeline automatically
python3 run_portfolio_analysis.py portfolios/tax_strategies.json
```

No manual timeline generation is needed anymore!

## Detailed Financial Materialization Feature

### Problem Solved

Users needed to:
- Understand exactly how financial outcomes were calculated
- Trace differences between scenarios to specific actions/years
- See which calculators were used for each action
- Have full transparency into tax calculations

### Solution Implemented

Created a comprehensive materialization system that captures:

1. **Action-Level Details**
   - Every financial action with its calculations
   - Which calculator was used (ISO exercise, share sale, donation)
   - Gross proceeds, exercise costs, capital gains
   - Tax impacts and charitable deductions

2. **Annual Summaries**
   - Year-by-year financial progression
   - Income, expenses, taxes, ending cash
   - Equity position changes
   - Net worth tracking

3. **Comprehensive Detail CSV**
   - Combines action details with year summaries
   - Shows pre/post states for each action
   - Tracks lot-specific changes

### Key Components

#### `projections/detailed_materialization.py`
A new module that:
- Extracts detailed calculations from projection results
- Creates multiple views of the data (action-level, annual, comprehensive)
- Handles complex data structures gracefully
- Provides CSV output for easy analysis

#### Integration with Projection Output
The system now automatically generates three additional CSV files:
- `{scenario}_detailed_calculations.csv` - Complete detail with all fields
- `{scenario}_action_summary.csv` - Concise action-level view
- `{scenario}_annual_summary.csv` - Year-by-year financial summary

### Output Examples

**Action Summary CSV**:
```csv
year,date,type,lot_id,quantity,price,calculator,gross_proceeds,capital_gain,tax,donation_value
2025,2025-05-26,sell,RSU_2021_001,1000,25.0,share_sale_calculator,25000.0,25000.0,0.0,0.0
2027,2027-01-15,exercise,VESTED_ISO,6000,5.0,iso_exercise_calculator,0.0,0.0,0.0,0.0
```

**Annual Summary CSV**:
```csv
year,w2_income,exercise_costs,sale_proceeds,donations,total_tax,ending_cash,net_worth
2025,177500,0.0,25000.0,12500.0,0.0,175587.5,638087.5
2027,177500,30000.0,31250.0,15625.0,44281.85,453245.09,1041135.71
```

### Usage

The detailed materialization runs automatically with every scenario:

```bash
# Execute a scenario - detailed CSVs are generated automatically
python3 run_scenario_analysis.py 002_tender_and_donate --demo

# View the generated files
ls output/demo/moderate/scenario_002_tender_and_donate/*.csv
```

## Benefits for Users

### Educational Value
- **Transparency**: See exactly how each calculation works
- **Learning**: Understand tax implications of different actions
- **Debugging**: Trace unexpected results to specific calculations

### Decision Making
- **Comparison**: Easy to compare calculation differences between scenarios
- **Analysis**: Import CSVs into Excel/Google Sheets for custom analysis
- **Validation**: Verify calculations against other tools

### Composability
The detailed materialization respects the calculator architecture:
- ISO exercise calculations show AMT adjustments
- Share sales show capital gains calculations
- Donations show deduction calculations
- Each action clearly indicates which calculator was used

## Future Enhancements

While the current implementation provides comprehensive detail, potential enhancements include:

1. **More Granular Tax Breakdowns**
   - Federal vs state tax separation
   - AMT credit application details
   - Charitable deduction carryforward tracking

2. **Enhanced Action Tracking**
   - Holding period calculations for each lot
   - Cost basis adjustments
   - Exercise date tracking for tax qualification

3. **Scenario Comparison Views**
   - Side-by-side action comparisons
   - Differential analysis between scenarios
   - Key decision point identification

## Summary

These implementations solve two critical issues:
1. **Timeline Generation**: Automated, data-source aware timeline creation eliminates lot ID mismatch errors
2. **Detailed Materialization**: Comprehensive CSV output provides full calculation transparency

Together, they make the Equity Financial Optimizer more robust, educational, and useful for financial decision-making.