# Equity Financial Optimizer

A comprehensive toolkit for optimizing equity compensation decisions with special focus on maximizing charitable impact through company donation matching programs and tax optimization strategies.

## 🚀 Quick Start

```bash
# Run a portfolio analysis comparing multiple strategies
python3 run_portfolio_analysis.py portfolios/tax_strategies.json

# Run a portfolio with demo data (safe example data)
python3 run_portfolio_analysis.py portfolios/tax_strategies.json --demo

# Execute a single scenario with moderate growth assumptions
python3 run_scenario_analysis.py 001_exercise_all_vested --price moderate --years 5

# Run a single scenario with demo data
python3 run_scenario_analysis.py 000_natural_evolution --demo
```

## 🔐 Secure Profile Setup

The system uses a secure three-file pattern for handling sensitive financial data:

### Files Explained
- **`user_profile.json`** ⚠️ **SENSITIVE** - Your real financial data (git-ignored, never committed)
- **`demo_profile.json`** 🧪 **SAFE** - Example data for demos and testing  
- **`user_profile_template.json`** 📋 **TEMPLATE** - Copy this to create your profile

### Getting Started with Your Data

**Option 1: Use Demo Data (Safe)**
```bash
# Run any analysis with demo data using --demo flag
python3 run_portfolio_analysis.py portfolios/tax_strategies.json --demo
python3 run_scenario_analysis.py 001_exercise_all_vested --demo
```

**Option 2: Use Your Real Data**
```bash
# 1. Copy template to create your private profile
cp input_data/user_profile_template.json input_data/user_profile.json

# 2. Edit user_profile.json with your real financial information
# (This file is git-ignored and stays private)

# 3. Run scenarios - system automatically detects and uses your data
python3 run_portfolio_analysis.py portfolios/tax_strategies.json
python3 run_scenario_analysis.py 001_exercise_all_vested
```

### Security Features
✅ **Private data isolation**: `user_profile.json` is git-ignored  
✅ **Automatic fallback**: Uses demo data when real profile unavailable  
✅ **Clear messaging**: System tells you which data source it's using  
✅ **No accidental commits**: Sensitive data never enters version control  

The system will automatically detect which profile to use and inform you:
- 🔒 "Using personal financial data" = Your real data
- 🧪 "Using demo financial data" = Safe example data

## 🎯 Data-Driven Scenario Planning

The system uses numbered scenarios organized by data source for security:

### Scenario Structure
```
scenarios/
├── demo/                    # Safe example scenarios (committable)
│   ├── 000_natural_evolution_actions.csv
│   ├── 001_exercise_all_vested_actions.csv
│   └── 002_tender_and_donate_actions.csv
└── user/                    # Your personal scenarios (git-ignored)
    ├── 000_natural_evolution_actions.csv
    ├── 001_exercise_all_vested_actions.csv
    └── 002_tender_and_donate_actions.csv
```

### Creating Scenarios

Define your strategy in CSV files with this format:

```csv
action_date,action_type,lot_id,quantity,price,notes
2025-05-26,sell,LOT-01,1000,,Tender offer participation
2025-12-01,donate,LOT-01,500,,Donate to fulfill pledge
2026-01-15,exercise,VESTED_ISO,5000,,Exercise vested ISOs
```

### Automatic Price Intelligence
- **Exercise**: Uses strike price from equity lots
- **Sell**: Uses tender price if near tender date, otherwise projected price
- **Donate**: Uses projected market price

### Action Types
- **exercise**: Convert vested options to shares (triggers AMT/tax calculations)
- **sell**: Sell shares (creates capital gains, pledge obligations)
- **donate**: Donate shares (tax deduction, company match, reduces pledge)

## 🎁 Why This Matters

Company donation matching programs (e.g. 3:1) can turn $1 of foregone proceeds into $4-8+ of charitable impact. But optimal equity management requires modeling:
- Multi-year scenarios with vesting schedules and exercise timing
- Complex tax interactions (AMT, capital gains, charitable deductions)
- Cash flow planning with liquidity constraints and exercise costs
- Pledge obligations from share sales with fulfillment tracking

This toolkit models complete multi-year scenarios so you can make data-driven decisions with confidence.

## 📊 Key Features

- **Portfolio-Based Analysis**: Group and compare multiple scenarios with shared assumptions
- **Data-Source Separation**: Demo vs user scenarios automatically detected for security
- **Numbered Scenarios**: Clear ordering (000_, 001_, 002_) for systematic strategy comparison
- **Multi-Year Projections**: Model complete equity lifecycle with dynamic date handling
- **Comprehensive Tax Modeling**: AMT, capital gains, charitable deductions with proper composability
- **Donation Impact Optimization**: Company match calculations with AGI limits and carryforward
- **Enhanced Traceability**: Complete metadata tracking for every scenario execution
- **Secure by Design**: User data isolation with automatic fallback to demo data

## 🏗️ Project Structure

```
# Main CLI Tools
run_portfolio_analysis.py          # Execute and compare multiple scenarios
run_scenario_analysis.py           # Execute individual scenarios

scenarios/                          # Data-driven scenario definitions
├── demo/                          # Safe example scenarios (committable)
│   ├── 000_natural_evolution_actions.csv
│   ├── 001_exercise_all_vested_actions.csv
│   └── 002_tender_and_donate_actions.csv
└── user/                          # Personal scenarios (git-ignored)
    ├── 000_natural_evolution_actions.csv
    ├── 001_exercise_all_vested_actions.csv
    └── 002_tender_and_donate_actions.csv

portfolios/                        # Collections of scenarios
└── tax_strategies.json           # Compare different tax approaches

output/                            # Results with full traceability
├── demo/moderate/scenario_000_natural_evolution/
├── user/moderate/scenario_001_exercise_all_vested/
└── {data_source}/portfolio_comparisons/

calculators/                       # Pure financial calculations
├── iso_exercise_calculator.py    # AMT calculations for ISOs
├── share_sale_calculator.py      # Capital gains tax calculations
└── share_donation_calculator.py  # Charitable deductions, company match

projections/                       # Multi-year projection engine
├── projection_calculator.py      # Orchestrates calculators across years
├── projection_state.py          # State tracking data structures
└── projection_output.py         # CSV output generation

engine/                           # Portfolio execution and price handling
├── portfolio_manager.py         # Execute scenarios and portfolios
└── natural_evolution_generator.py # Generate baseline scenarios

input_data/                       # User data and market assumptions
├── user_profile.json           # v2.0 format financial data (git-ignored)
├── demo_profile.json           # Safe example data
├── user_profile_template.json  # Template for new users
└── market_assumptions/
    └── price_scenarios.json    # Growth rate assumptions

examples/                        # Educational demonstrations
└── portfolio_analysis.py       # Educational example (use main CLI tools instead)
```

## 📋 Creating Custom Scenarios

1. **Create your scenario file** in the appropriate directory:
   ```bash
   # For demo scenarios (safe to commit)
   touch scenarios/demo/003_my_strategy_actions.csv
   
   # For personal scenarios (git-ignored, uses your real lot IDs)
   touch scenarios/user/003_my_strategy_actions.csv
   ```

2. **Define your strategy** in the CSV file:
   ```csv
   action_date,action_type,lot_id,quantity,price,notes
   2025-07-01,exercise,VESTED_ISO,5000,,Exercise portion of ISOs
   2026-05-26,sell,LOT-02,1000,,Participate in tender offer
   2026-12-01,donate,LOT-02,500,,Fulfill pledge obligation
   ```

3. **Run your scenario**:
   ```bash
   # Single scenario execution
   python3 run_scenario_analysis.py 003_my_strategy
   
   # Add to a portfolio for comparison
   # Edit portfolios/tax_strategies.json to include "003_my_strategy"
   python3 run_portfolio_analysis.py portfolios/tax_strategies.json
   ```

### Best Practices for Custom Scenarios
- **Use realistic dates**: Check vesting calendar in your user_profile.json
- **Match lot IDs**: Ensure lot IDs exist in your equity position timeline
- **Consider cash flow**: Ensure sufficient cash for exercises and taxes
- **Document strategy**: Use the notes column to explain your rationale
- **Test incrementally**: Start with simple scenarios before complex multi-year plans

## 💡 Price Projections

Price growth scenarios are defined in `input_data/market_assumptions/price_scenarios.json`:
- **conservative**: 15% annual growth
- **moderate**: 25% annual growth (default)
- **aggressive**: 40% annual growth
- **flat**: 0% growth
- **historical_tech**: 30% growth

Base prices come from `user_profile.json`. See `user_profile_template.json` to fill in your own, or use `demo_profile.json`.

## 📊 Analyzing Results

The system generates comprehensive CSV outputs organized by detail level:

### Core Analysis Files
- **annual_tax_detail.csv**: Complete tax breakdown by component (W2, capital gains, AMT, deductions)
- **action_summary.csv**: Every action with acquisition dates, holding periods, tax treatment, pledge tracking
- **annual_summary.csv**: Year-by-year financial summary with key metrics

### State & Transition Tracking
- **state_timeline.csv**: Share quantities in each lifecycle state over time
- **transition_timeline.csv**: Share movements between states (vesting, exercising, selling)

### Decision Support Tracking
- **holding_period_tracking.csv**: Acquisition dates and qualifying disposition status for each lot
- **pledge_obligations.csv**: Donation commitments from sales with deadlines and fulfillment
- **charitable_carryforward.csv**: Unused charitable deductions and expiration tracking
- **tax_component_breakdown.csv**: Detailed tax calculation by income type and lot

### Portfolio Comparison
- **comparison.csv**: Side-by-side scenario comparison for portfolio analysis

## 🚀 Advanced Usage

### Creating a Portfolio
Define multiple scenarios to compare in a JSON file:
```json
{
  "name": "Tax Strategy Comparison",
  "description": "Compare different tax optimization approaches",
  "scenarios": [
    "scenarios/natural_evolution",
    "scenarios/exercise_all_vested",
    "scenarios/tender_and_donate"
  ],
  "price_scenario": "moderate",
  "projection_years": 5
}
```

### Command Line Interface
```bash
# Show available scenarios and portfolios
python3 run_scenario_analysis.py
python3 run_portfolio_analysis.py

# Run single scenarios with custom assumptions
python3 run_scenario_analysis.py 001_exercise_all_vested --price aggressive --years 7
python3 run_scenario_analysis.py 000_natural_evolution --demo

# Execute portfolios
python3 run_portfolio_analysis.py portfolios/tax_strategies.json
python3 run_portfolio_analysis.py portfolios/tax_strategies.json --demo --output custom_results/
```

## 📋 Data Format

All user profiles use the v2.0 data contract format. Key fields:
- Personal information (tax rates, filing status)
- Income (W2, spouse, other)
- Equity position (grants, exercises, vesting schedule)
- Financial position (cash, investments)
- Goals and constraints (pledge percentage, liquidity needs)

See [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) for the complete specification.

## 🤝 Contributing

- See `docs/CLAUDE.md` for AI context and development guidelines
- See `scenarios/README.md` for scenario creation guide
- All calculators must be pure functions with no side effects
- Use type hints and comprehensive docstrings
- Test with multiple edge cases

## ⚠️ Important Disclaimers

- This is not financial, tax, or legal advice
- Consult qualified advisors before making decisions
- Tax laws and company programs can change
- All calculations are estimates based on current rules

## 🙏 Acknowledgments

Built for employees navigating complex equity compensation decisions. Special thanks to the financial planning community for sharing strategies to maximize charitable impact while managing personal financial goals.

---

*Remember: The best financial plan aligns your resources with your values. May your equity create positive change in the world.* 🌍
