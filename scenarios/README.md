# Scenario Structure Guide

## Overview

Each scenario is a directory containing an `actions.csv` file that defines the sequence of equity actions to simulate. Scenarios are data-driven and can be created/edited without touching code.

## Directory Structure

```
scenarios/
├── natural_evolution/
│   └── actions.csv          # Empty - no actions taken
├── exercise_all_vested/
│   └── actions.csv          # Exercise all vested options
├── tender_and_donate/
│   └── actions.csv          # Participate in tender, then donate
└── amt_optimization/
    └── actions.csv          # Exercise up to AMT threshold
```

## Actions CSV Format

The `actions.csv` file defines what actions to take and when:

```csv
action_date,action_type,lot_id,quantity,price,notes
2025-05-26,sell,LOT-01,1000,,Tender offer participation
2025-12-01,donate,LOT-01,500,,Donate to fulfill pledge
2026-01-15,exercise,VESTED_ISO,5000,,Exercise vested ISOs
```

### Column Definitions

- **action_date**: ISO date format (YYYY-MM-DD)
- **action_type**: One of: `exercise`, `sell`, `donate`, `vest`, `hold`
- **lot_id**: The specific lot to act on (must match equity timeline)
- **quantity**: Number of shares for this action
- **price**: Price per share (optional - see Automatic Pricing below)
- **notes**: Optional description of the action

### Action Types

1. **exercise**: Convert vested options to shares
   - Triggers tax calculations (AMT for ISOs, ordinary income for NSOs)
   - Requires cash for exercise cost + taxes

2. **sell**: Sell shares (tender offer or market sale)
   - Creates capital gains (LTCG/STCG based on holding period)
   - Generates pledge obligations (based on user's pledge percentage)

3. **donate**: Donate shares to charity
   - Provides tax deduction
   - Triggers company match (if eligible)
   - Reduces pledge obligations

4. **vest**: Record vesting event (usually auto-generated from timeline)
5. **hold**: No action (placeholder)

## Automatic Pricing

The system automatically determines prices based on action type and date:

1. **Exercise actions**: Uses the strike price from the lot (no need to specify)
2. **Sell actions**: 
   - If within 30 days of a known tender offer date → uses tender price
   - Otherwise → uses projected market price for that year
3. **Donate actions**: Uses projected market price for that year

You can always override by providing an explicit price in the CSV.

### Price Sources:
- **Strike prices**: From equity_position_timeline.csv
- **Tender prices**: From user_profile.json (last_tender_offer_date/price)
- **Market prices**: From selected price growth scenario (e.g., 25% annual growth)

## Creating a Scenario

### Step 1: Create Directory
```bash
mkdir scenarios/my_new_scenario
```

### Step 2: Create actions.csv

Example: Exercise and Hold Strategy
```csv
action_date,action_type,lot_id,quantity,price,notes
2025-01-15,exercise,VESTED_ISO,5000,,Exercise portion of ISOs
2025-01-15,exercise,VESTED_NSO,3000,,Exercise all NSOs
```

Example: Tender Participation
```csv
action_date,action_type,lot_id,quantity,price,notes
2025-05-26,sell,LOT-01,1000,,Participate in tender offer
```

### Step 3: Run Scenario
```python
from engine.portfolio_manager import execute_single_scenario

result = execute_single_scenario(
    scenario_path="scenarios/my_new_scenario",
    price_scenario="moderate",  # or "conservative", "aggressive", etc.
    projection_years=5
)
```

## Price Projections

Price growth scenarios are defined separately in `data/market_assumptions/price_scenarios.json`:
- **conservative**: 15% annual growth
- **moderate**: 25% annual growth  
- **aggressive**: 40% annual growth
- **flat**: 0% growth
- **historical_tech**: 30% growth

Base prices come from `user_profile.json` (last 409A price).

## Why No JSON Config?

We originally included `scenario_config.json` files, but they're redundant because:

1. **Scenario name**: Can be derived from directory name
2. **Description**: Can be in the CSV notes or a README
3. **Dates**: Should use current date + projection years (not hardcoded)
4. **Price projections**: Shared across scenarios (in price_scenarios.json)
5. **User data**: Always from user_profile.json

The CSV file contains all the essential information needed to execute a scenario.

## Best Practices

1. **Use realistic dates**: Check vesting calendar and tender dates in user_profile.json
2. **Match lot IDs**: Lot IDs must exist in equity_position_timeline.csv
3. **Consider cash**: Ensure sufficient cash for exercises and taxes
4. **Document strategy**: Use the notes column to explain the rationale
5. **Test incrementally**: Start with simple scenarios before complex multi-year plans

## Example Scenarios

### 1. Natural Evolution (Baseline)
```csv
# Empty file - no actions taken
```

### 2. Exercise at IPO
```csv
action_date,action_type,lot_id,quantity,price,notes
2027-06-01,exercise,VESTED_ISO,5000,,Exercise all ISOs at IPO
2027-06-01,exercise,VESTED_NSO,3000,,Exercise all NSOs at IPO
```

### 3. Annual AMT Optimization
```csv
action_date,action_type,lot_id,quantity,price,notes
2025-12-15,exercise,VESTED_ISO,3000,,Exercise below AMT threshold
2026-12-15,exercise,VESTED_ISO,3000,,Exercise below AMT threshold
2027-12-15,exercise,VESTED_ISO,3000,,Exercise below AMT threshold
2028-12-15,exercise,VESTED_ISO,3427,,Exercise remaining ISOs
```

### 4. Liquidity + Charity Strategy
```csv
action_date,action_type,lot_id,quantity,price,notes
2025-05-26,sell,LOT-01,1000,,Tender for liquidity
2025-12-01,donate,LOT-01,500,,Fulfill pledge obligation
2026-06-15,donate,LOT-02,1000,,Maximize company match
2027-01-15,exercise,VESTED_ISO,5000,,Exercise ISOs
2028-01-15,sell,VESTED_ISO,2000,,Sell for liquidity after LTCG
2028-06-01,donate,VESTED_ISO,1000,,Continue charitable giving
```

## Tips for Analysis

- Compare scenarios using the same price growth assumptions
- Look at multiple metrics: cash, taxes, donations, net worth
- Consider risk: scenarios with more cash are less risky
- Remember pledge obligations from any sales
- Factor in life events that might need liquidity