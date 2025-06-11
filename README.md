# Equity Financial Optimizer

A comprehensive toolkit for optimizing equity compensation decisions with special focus on maximizing charitable impact through company donation matching programs and tax optimization strategies.

## 🚀 Quick Start

```bash
# Run a demo comparing baseline with exercise strategies
python3 examples/portfolio_analysis.py demo

# Execute a single scenario with moderate growth assumptions
python3 examples/portfolio_analysis.py scenario scenarios/exercise_all_vested --price moderate --years 5

# Run a portfolio of tax optimization strategies
python3 examples/portfolio_analysis.py portfolio portfolios/tax_strategies.json
```

## 🎯 Data-Driven Scenario Planning

Create scenarios by defining actions in simple CSV files:

```csv
action_date,action_type,lot_id,quantity,price,notes
2025-05-26,sell,LOT-01,1000,,Tender offer participation
2025-12-01,donate,LOT-01,500,,Donate to fulfill pledge
2026-01-15,exercise,VESTED_ISO,5000,,Exercise vested ISOs
```

The system automatically determines prices:
- **Exercise**: Uses strike price from equity lots
    <!-- #Do we need to maintain a forecast of 409a prices for calculating the impacts of exercise decisions? what other factors are non-negotiable in forecasts based on what the calculators require? -->
- **Sell**: Uses tender price if near tender date, otherwise projected price
- **Donate**: Uses projected market price
<!-- What other forecasted values are needed for accurate tax planning for all of these actions? -->

## 🎁 Why This Matters

Company donation matching programs (e.g. 3:1) can turn $1 of foregone proceeds into $4-8+ of charitable impact. But optimal equity management requires modeling:
- Multi-year scenarios with vesting schedules and exercise timing
- Complex tax interactions (AMT, capital gains, charitable deductions)
- Cash flow planning with liquidity constraints and exercise costs
- Pledge obligations from share sales with fulfillment tracking

This toolkit models complete multi-year scenarios so you can make data-driven decisions with confidence.

## 📊 Key Features

- **Portfolio-Based Analysis**: Group and compare multiple scenarios with shared assumptions
- **Data-Driven Scenarios**: Define strategies in CSV files, not code
- **Multi-Year Projections**: Model complete equity lifecycle with dynamic date handling
- **Comprehensive Tax Modeling**: AMT, capital gains, charitable deductions with proper composability
- **Donation Impact Optimization**: Company match calculations with AGI limits and carryforward
- **Pledge Tracking**: Automatic obligation tracking from sales with FIFO discharge

## 🏗️ Project Structure

```
scenarios/                # Data-driven scenario definitions
├── README.md            # How to create scenarios
├── natural_evolution/   # Baseline do-nothing scenario
│   └── actions.csv
├── exercise_all_vested/ # Exercise all vested options
│   └── actions.csv
└── tender_and_donate/   # Complex multi-year strategy
    └── actions.csv

portfolios/              # Collections of scenarios
└── tax_strategies.json  # Compare different tax approaches

calculators/             # Pure financial calculations
├── iso_exercise_calculator.py     # AMT calculations for ISOs
├── share_sale_calculator.py       # Capital gains tax calculations
└── share_donation_calculator.py   # Charitable deductions, company match

projections/             # Multi-year projection engine
├── projection_calculator.py       # Orchestrates calculators across years
├── projection_state.py           # State tracking data structures
└── projection_output.py          # CSV output generation

engine/                  # Portfolio execution and price handling
├── portfolio_manager.py          # Execute scenarios and portfolios
└── natural_evolution_generator.py # Generate baseline scenarios

data/                    # User data and market assumptions
├── user_profile.json            # v2.0 format financial data
└── market_assumptions/
    └── price_scenarios.json     # Growth rate assumptions

examples/                # Usage demonstrations
├── portfolio_analysis.py        # Main CLI tool for analysis
├── projection_analysis.py       # Legacy natural evolution demo
└── multi_scenario_analysis.py   # Previous multi-scenario runner
```

## 📋 Creating Scenarios

1. **Create a directory** under `scenarios/`:
   ```bash
   mkdir scenarios/my_strategy
   ```

2. **Create actions.csv** defining your strategy:
   ```csv
   action_date,action_type,lot_id,quantity,price,notes
   2025-07-01,exercise,VESTED_ISO,5000,,Exercise portion of ISOs
   2026-05-26,sell,LOT-02,1000,,Participate in tender offer
   2026-12-01,donate,LOT-02,500,,Fulfill pledge obligation
   ```

3. **Run the scenario**:
   ```bash
   python3 examples/portfolio_analysis.py scenario scenarios/my_strategy
   ```

## 💡 Price Projections

Price growth scenarios are defined in `data/market_assumptions/price_scenarios.json`:
- **conservative**: 15% annual growth
- **moderate**: 25% annual growth (default)
- **aggressive**: 40% annual growth
- **flat**: 0% growth
- **historical_tech**: 30% growth

Base prices come from `user_profile.json`. See `user_profile_template.json` to fill in your own, or use `demo_profile.json`.

## 📊 Analyzing Results

The system generates comprehensive CSV outputs:
- **yearly_cashflow.csv**: Annual income, expenses, taxes, ending cash
- **tax_timeline.csv**: Regular tax, AMT, credits, deductions by year
- **equity_holdings.csv**: Final position of all share lots
- **summary.csv**: High-level metrics for decision making
- **comparison.csv**: Side-by-side portfolio comparison

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
python3 examples/portfolio_analysis.py

# Run with custom price assumptions
python3 examples/portfolio_analysis.py scenario scenarios/my_strategy --price aggressive --years 7

# Execute a portfolio
python3 examples/portfolio_analysis.py portfolio portfolios/tax_strategies.json --output output/my_analysis
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
