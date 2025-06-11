# Main Execution Workflow - Equity Financial Optimizer

## Overview

The Equity Financial Optimizer now centers around a **Multi-Year Projection Engine** that uses `equity_position_timeline.csv` as the foundation for comprehensive scenario modeling. This document describes the main execution workflow from data loading to actionable insights.

## Core Workflow: Timeline → Actions → Projections

### Step 1: Data Foundation
```
equity_position_timeline.csv  +  user_profile.json
           ↓
    BaseEquityState (28 lots, vesting schedule, financial constraints)
```

### Step 2: Scenario Generation
```
BaseEquityState
    ↓
+ PlannedActions (exercise, sell, donate, hold)
    ↓
ProjectionPlan (complete 5-year action sequence)
```

### Step 3: Financial Projection
```
ProjectionPlan
    ↓
ProjectionCalculator (uses existing ISO, Sale, Donation calculators)
    ↓
YearlyProjection (cash, taxes, donations, obligations, stock value)
```

### Step 4: Scenario Comparison
```
Multiple YearlyProjections
    ↓
ComparisonEngine
    ↓
CSV Reports + Insights + Recommendations
```

## Main Entry Points

### Primary Workflow: projection_analysis.py
```python
# examples/projection_analysis.py

def main():
    # 1. Load foundation data and generate timeline
    profile = load_user_profile("data/user_profile.json")
    timeline = generate_equity_timeline_from_profile(profile)

    # 2. Generate Natural Evolution scenario
    natural_evolution = generate_natural_evolution(timeline, profile)

    # 3. Load specified scenarios (defined separately/iteratively)
    specified_scenarios = load_specified_scenarios()  # To be defined based on optimization questions

    scenarios = [natural_evolution] + specified_scenarios

    # 4. Run multi-year projections
    calculator = ProjectionCalculator(profile)
    for scenario in scenarios:
        projection = calculator.evaluate_multi_year_plan(scenario)

        # 5. Output CSV for this scenario
        save_yearly_cashflow(projection, f"output/{scenario.name}_yearly_cashflow.csv")
        save_tax_timeline(projection, f"output/{scenario.name}_tax_timeline.csv")
        save_scenario_summary(projection, f"output/{scenario.name}_summary.csv")

    # 6. Read and compare raw output files manually for MVP
    print("Projection complete. Review output/*.csv files for comparison.")
```

### Scenario Definition Workflow: scenario_definition.py
```python
# examples/scenario_definition.py

def define_scenarios_iteratively():
    # Define specific scenarios based on optimization questions
    profile = load_user_profile("data/user_profile.json")
    timeline = generate_equity_timeline_from_profile(profile)

    # Example scenarios (to be customized based on specific questions):
    scenarios = []

    # Natural evolution baseline
    scenarios.append(generate_natural_evolution(timeline, profile))

    # Specific optimization scenarios
    scenarios.append(create_sell_all_end_variant(timeline, profile))
    scenarios.append(create_exercise_all_now_variant(timeline, profile))

    # Additional scenarios defined based on user's specific optimization questions
    # (to be added iteratively)

    return scenarios
```

## Data Flow Architecture

### Input Layer
- **user_profile.json**: Financial constraints, goals, tax rates, company match ratios, vesting schedule
- **equity_position_timeline.csv**: Generated as product of user_profile.json

### Processing Layer
- **Scenario Generators**: Create specified scenarios based on optimization questions
- **ProjectionCalculator**: Applies existing calculators year-by-year (modification allowed as needed)

### Output Layer
- **CSV Reports**: Raw projection data for each scenario
- **Manual Comparison**: Read and compare raw output files for MVP

## Key Components Integration

### Existing Calculators (Unchanged)
- `iso_exercise_calculator.py`: AMT calculations, exercise costs
- `share_sale_calculator.py`: Capital gains tax, proceeds calculations
- `share_donation_calculator.py`: Charitable deductions, company match impact

### New Projection Layer
- `projection_calculator.py`: Orchestrates existing calculators across 5-year timeline
- `scenario_variants.py`: Generates specified scenarios from base timeline
- `timeline_generator.py`: Creates equity_position_timeline.csv from user_profile.json

### Enhanced State Tracking
- `yearly_state.py`: Comprehensive state model for each year
- `tax_carryforward.py`: AMT credits and charitable deduction carryforward (consider additional data structure)
- `pledge_tracker.py`: Outstanding donation obligations per company program rules (maximalist vs minimalist interpretation)

## Output Specifications

### {scenario_name}_yearly_cashflow.csv
Year-by-year cash flow analysis for each scenario:
```csv
year,starting_cash,income,exercise_costs,tax_paid,donation_value,ending_cash
2025,2000,445000,0,0,0,447000
2026,447000,445000,0,0,0,892000
2027,892000,445000,55000,85000,0,1197000
```

### {scenario_name}_tax_timeline.csv
Multi-year tax planning for each scenario:
```csv
year,regular_tax,amt_tax,total_tax,amt_credits_generated,amt_credits_used,charitable_deduction
2025,150000,85000,235000,85000,0,0
2026,160000,0,160000,0,30000,0
2027,170000,0,170000,0,30000,0
```

### {scenario_name}_summary.csv
High-level metrics for each scenario:
```csv
total_cash_year_5,total_tax_5_years,total_donations,pledge_fulfillment_max,pledge_fulfillment_min,outstanding_obligation
1500000,400000,0,0.0,0.0,750000
```

## Decision Support Framework

### Key Metrics for Manual Comparison
1. **Total Impact**: Donation value × company match + tax savings
2. **Tax Efficiency**: Total taxes / total equity value
3. **Liquidity Management**: Cash position vs liquidity needs
4. **Pledge Fulfillment**: Progress toward donation commitments per maximalist/minimalist interpretation

### Optimization Opportunities
- **Exercise Timing**: AMT breakeven optimization, LTCG clock starting
- **Tender Participation**: Liquidity vs future donation potential trade-offs
- **Donation Scheduling**: Multi-year deduction utilization, match maximization
- **Tax Planning**: AMT credit utilization, carryforward optimization

## Success Metrics

### Workflow Success
- Generate 5-year projections for specified scenarios in <60 seconds
- Clear CSV outputs for decision making
- Deterministic evaluation of any specified action sequence

### Business Success
- Show quantified trade-offs between specified scenarios
- Enable data-driven equity compensation decisions
- Support evaluation of specific optimization questions

## Integration Points

### With Existing Architecture
- Uses existing calculators (modification allowed as needed to close gaps)
- Extends current CSV output patterns
- Builds on equity_position_timeline.csv (generated from user_profile.json)
- Maintains clean separation: data → calculation → results

## Next Steps

1. **Phase 1**: Implement ProjectionCalculator and Natural Evolution scenario
2. **Phase 2**: Create basic specified scenarios (sell-all-end, exercise-all-now)
3. **Phase 3**: Address calculator gaps (tax carryforward, pledge tracking)
4. **Phase 4**: Testing and validation with specified scenarios

This workflow provides deterministic projection capabilities for evaluating specified equity compensation strategies over five years.
