# Portfolio Architecture

## Overview

The Portfolio Architecture enables data-driven scenario planning where equity optimization strategies are defined in CSV files rather than code. A portfolio is a collection of scenarios that can be executed together with shared assumptions for comparative analysis.

## Core Concepts

### Scenario
A scenario is a directory containing an `actions.csv` file that defines a sequence of equity actions (exercise, sell, donate) over time. Scenarios are purely data-driven - no code required.

```
scenarios/exercise_all_vested/
└── actions.csv
```

### Portfolio
A portfolio groups multiple scenarios for comparative analysis with shared price growth assumptions and projection period.

```json
{
  "name": "Tax Strategy Comparison",
  "scenarios": [
    "scenarios/natural_evolution",
    "scenarios/exercise_all_vested",
    "scenarios/tender_and_donate"
  ],
  "price_scenario": "moderate",
  "projection_years": 5
}
```

## Architecture Principles

1. **Data-Driven Design**: Scenarios defined in CSV, not code
2. **Price Intelligence**: Automatic price determination based on action type
3. **Composability**: Reuse existing calculators without modification
4. **Flexibility**: Execute single scenarios or portfolios
5. **Dynamic Dates**: No hardcoded dates - uses current date as baseline

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Portfolio Manager                       │
│  - Loads user data once                                     │
│  - Manages price projections                                │
│  - Executes scenarios                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Price Projector                         │
│  - Linear growth from base price                           │
│  - Multiple growth scenarios                               │
│  - No duplication with user_profile                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Projection Calculator                      │
│  - Orchestrates year-by-year evaluation                    │
│  - Maintains state across years                            │
│  - Delegates to specialized calculators                    │
└─────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
┌───────────────────────────┐       ┌───────────────────────────┐
│   ISO Exercise Calculator │       │   Share Sale Calculator   │
│   - AMT calculations      │       │   - Capital gains tax     │
│   - Exercise costs        │       │   - Lot selection         │
└───────────────────────────┘       └───────────────────────────┘
                              │
                              ▼
                 ┌───────────────────────────┐
                 │ Share Donation Calculator │
                 │   - Charitable deductions │
                 │   - Company matching      │
                 └───────────────────────────┘
```

## Price Determination Logic

The system automatically determines appropriate prices based on action type and context:

### Exercise Actions
- Always use strike price from the share lot
- No market price needed for exercise

### Sell Actions
- Check if action date is within 30 days of known tender offer
- If yes → use tender price from user_profile.json
- If no → use projected market price for that year

### Donate Actions
- Always use projected market price for the year
- Ensures proper charitable deduction value

### Price Override
- Can manually specify price in CSV if needed
- Useful for modeling specific scenarios

## Data Flow

1. **User Data Loading**
   ```
   user_profile.json → UserProfile object
   equity_position_timeline.csv → Initial share lots
   ```

2. **Price Projection**
   ```
   Base price (from profile) + Growth rate → Yearly prices
   ```

3. **Scenario Loading**
   ```
   actions.csv → PlannedAction objects → ProjectionPlan
   ```

4. **Execution**
   ```
   ProjectionPlan → ProjectionCalculator → YearlyStates → Results
   ```

5. **Output**
   ```
   Results → CSV files (cashflow, tax, holdings, summary)
   ```

## Key Design Decisions

### Why CSV for Scenarios?
- Excel-friendly for non-programmers
- Version control friendly
- Easy to generate programmatically
- Clear audit trail

### Why Separate Price Scenarios?
- Avoid duplication with user_profile
- Easy to test sensitivity to growth assumptions
- Consistent across all scenarios in portfolio

### Why Portfolio Grouping?
- Natural way to compare strategies
- Shared assumptions ensure fair comparison
- Efficient execution (load data once)

### Why Automatic Price Determination?
- Reduces errors from manual price entry
- Scenarios remain valid as prices change
- Natural handling of tender offers

## Example: Complete Workflow

1. **Create Scenario**
   ```bash
   mkdir scenarios/ipo_exercise
   cat > scenarios/ipo_exercise/actions.csv << EOF
   action_date,action_type,lot_id,quantity,price,notes
   2027-06-01,exercise,VESTED_ISO,5000,,Exercise at IPO
   2027-06-01,exercise,VESTED_NSO,3000,,Exercise at IPO
   2028-06-01,sell,VESTED_ISO,2500,,Sell half after LTCG
   2028-12-01,donate,VESTED_ISO,1250,,Donate for match
   EOF
   ```

2. **Execute Single Scenario**
   ```python
   from engine.portfolio_manager import execute_single_scenario
   
   result = execute_single_scenario(
       scenario_path="scenarios/ipo_exercise",
       price_scenario="aggressive",  # 40% annual growth
       projection_years=7
   )
   ```

3. **Create Portfolio**
   ```json
   {
     "name": "IPO Strategies",
     "scenarios": [
       "scenarios/natural_evolution",
       "scenarios/ipo_exercise",
       "scenarios/ipo_exercise_and_sell"
     ],
     "price_scenario": "moderate",
     "projection_years": 7
   }
   ```

4. **Execute Portfolio**
   ```python
   from engine.portfolio_manager import execute_portfolio_from_json
   
   results = execute_portfolio_from_json(
       "portfolios/ipo_strategies.json",
       output_dir="output/ipo_analysis"
   )
   ```

## Best Practices

1. **Scenario Naming**
   - Use descriptive directory names
   - Group related scenarios in subdirectories
   - Include strategy type in name

2. **Action Timing**
   - Align with real dates (vesting, tender offers)
   - Consider tax implications (LTCG timing)
   - Account for exercise/settlement delays

3. **Portfolio Design**
   - Compare 3-5 scenarios at most
   - Use consistent projection periods
   - Include baseline (natural evolution)
   - Vary one dimension at a time

4. **Price Scenarios**
   - Test conservative and aggressive assumptions
   - Document rationale for growth rates
   - Consider company/industry benchmarks

## Extension Points

The architecture supports several extension mechanisms:

1. **Custom Price Projections**
   - Add new scenarios to price_scenarios.json
   - Implement non-linear growth models
   - Industry-specific projections

2. **Action Types**
   - Add new ActionType enum values
   - Implement handlers in projection_calculator
   - Extend CSV format as needed

3. **Output Formats**
   - Add new CSV output types
   - Generate charts/visualizations
   - Export to financial planning tools

4. **Scenario Generation**
   - Build tools to generate CSV files
   - Parameter sweeps for optimization
   - Monte Carlo variations

## Migration from Code-Based Scenarios

For teams migrating from hardcoded scenarios:

1. Extract action sequences to CSV format
2. Remove price hardcoding
3. Update to use portfolio manager
4. Test with multiple price scenarios
5. Document strategies in scenario README files

The portfolio architecture provides a powerful, flexible foundation for equity optimization while keeping complexity in check through data-driven design.