# Equity Financial Optimizer

**Turn your equity compensation into maximum charitable impact while optimizing your taxes.**

Company donation matching programs (like 3:1 matching) can turn $1 of your equity into $4-8+ of charitable impact. But getting this right requires modeling complex interactions between vesting schedules, tax brackets, AMT, capital gains, and pledge obligations across multiple years.

This toolkit shows you exactly what happens with your equity under different strategies, so you can make confident data-driven decisions.

---

## 🚀 Quick Win: Try It in 2 Minutes

**Step 1: Run your first analysis** (uses safe demo data)
```bash
python3 run_portfolio_analysis.py portfolios/tax_strategies.json --demo
```

**Step 2: See what happened**
```bash
# Check the results folder
ls output/demo/moderate/
```

You'll see folders like `scenario_000_natural_evolution` and `scenario_001_exercise_all_vested` with complete financial projections.

**Step 3: Look at one result**
```bash
# Open the comparison to see strategy differences
open output/demo/portfolio_comparisons/moderate_tax_strategy_comparison.csv
```
The CSV shows a basic view of how different strategies impact your taxes, cash flow, and charitable giving potential.

---

## 🔒 Your Data Stays Private

**Before we go further, let's talk security** - because this deals with your personal financial information:

✅ **Your data never leaves your computer** - everything runs locally
✅ **No cloud uploads** - your sensitive info stays on your machine
✅ **Demo data included** - practice with safe example data first

**Two ways to use this tool:**
- 🧪 **Demo mode**: Use the --demo flag to run with example data (safe to share, perfect for learning)
- 🔒 **Personal mode**: Or, drop the flag to use your real financial data (private, git-ignored)

---

## 🎯 Using Your Real Data

Ready to analyze your actual equity situation? Here's how:

### Step 1: Create Your Profile
```bash
# Copy the template to create your private profile
cp input_data/user_profile_template.json input_data/user_profile.json
```

### Step 2: Fill In Your Information
Edit `input_data/user_profile.json` with your real data:

**Essential fields to update:**
- `personal_information`: Your tax filing status and rates
- `income`: Your W2 income and spouse income
- `equity_position.grants`: Your actual stock grants
- `equity_position.exercised_lots`: Any shares you've already exercised
- `equity_position.current_prices`: Current 409A price and expected growth

**Don't worry about perfection** - you can always refine the numbers later.

### Step 3: Run Analysis With Your Data
```bash
# Same command, but now it uses your real data automatically
python3 run_portfolio_analysis.py portfolios/tax_strategies.json
```

You'll see: 🔒 *"Using personal financial data"* - confirming it's using your real numbers.

### Step 4: Review Your Results
```bash
# Your results are now in the user folder
ls output/user/moderate/
open output/user/portfolio_comparisons/moderate_tax_strategy_comparison.csv
```

**Key insight**: Compare the tax impact and charitable potential across strategies. Often the "do nothing" approach leaves significant equity value and charitable impact on the table.

---

## 📊 Understanding Your Results

Now that you have both demo and real data results, let's decode what they mean:

### The Big Picture: Portfolio Comparison
**File**: `output/user/portfolio_comparisons/moderate_tax_strategy_comparison.csv` (or `output/demo/` for demo data)

This shows side-by-side comparison of different strategies:
- **Natural Evolution**: What happens if you do nothing / take no active action. All your options will expire!
- **Exercise All Vested**: Exercise your vested options early - has an immediate hit on cash and tax, but can lead to higher long-term equity value under a 'moderate' growth scenario.
- **Tender & Donate**: Participate in tender offers and donate shares to fulfill any match pledge you might have.

**Key columns to watch:**
- `total_tax_paid`: Total taxes across all years
- `charitable_impact`: Total charitable donations + company matching
- `ending_cash`: Cash remaining after 5 years
- `ending_equity_value`: Value of remaining (held) shares

### Deep Dive: Individual Scenarios

**Files**:
- Check `output/user/timeline/equity_position_timeline.csv` to check all anticipated future vesting events
- Inspect `output/user/moderate/scenario_XXX_*/` (or `output/demo/` for demo data) for detailed outputs of all calculators

Each scenario folder contains detailed year-by-year projections:
- **`annual_summary.csv`**: High-level financial summary by year
- **`action_summary.csv`**: Every action (exercise, sell, donate) with tax impact
- **`annual_tax_detail.csv`**: Complete tax breakdown by component
- and many more for the nitty gritty details

**Quick check**: Open `annual_summary.csv` - you'll see how cash, taxes, and equity value change each year.

---

## 🎛️ Creating Custom Strategies

This is where the real value of the tool lies. My personal strategies have upwards of 60+ actions defined over the next 10 years.
Want to test your own equity strategy? Here's how:

### Step 1: Create a New Scenario
```bash
# Create your strategy file
touch scenarios/user/100_my_strategy.json
```

### Step 2: Define Your Actions
Edit the file with your strategy:
```json
[
  {
    "action_date": "2025-07-01",
    "action_type": "exercise",
    "lot_id": "ISO", // "Use `ISO`, `NSO`, or `RSU` for vested unexercised options, or use specific lot IDs (like `LOT-02`) for already exercised shares"
    "quantity": 500,
    "price": null,
    "notes": "Exercise 500 of my already-vested ISOs"
  },
  {
    "action_date": "2026-05-26",
    "action_type": "sell",
    "lot_id": "LOT-02",
    "quantity": 750,
    "price": null,
    "notes": "Participate in a (hypothetical, assumed) tender offer"
  },
  {
    "action_date": "2026-12-01",
    "action_type": "donate",
    "lot_id": "LOT-02",
    "quantity": 250,
    "price": null,
    "notes": "Donate to meet pledge obligation"
  }
]
```
PRO TIP: Claude is great for creating strategy files! Describe what you are trying to do and Claude will probably be able to populate the json file.

**Action types:**
- `exercise`: Convert options to shares (triggers taxes. Exercising ISOs has potential AMT impact.)
- `sell`: Sell shares (creates capital gains, pledge obligations if applicable)
- `donate`: Donate shares (create charitable tax deduction, realize company match if applicable, discharge pledge obligation if applicable)

### Step 3: Test Your Strategy
```bash
python3 run_scenario_analysis.py 100_my_strategy
```

### Step 4: Compare to Other Strategies
Add your scenario to a portfolio for side-by-side comparison:
```bash
# Edit portfolios/tax_strategies.json or create a new portfolio that includes "100_my_strategy"
# Then run the full comparison
python3 run_portfolio_analysis.py portfolios/tax_strategies.json
```

---

## 🔧 Advanced Features

Once you're comfortable with the basics, explore these advanced capabilities:

### Price Scenario Analysis
Test different growth assumptions. You can define these in a price_scenarios file to specify custom growth rate scenarios.
```bash
cp input_data/market_assumptions/price_scenarios_template.json input_data/market_assumptions/price_scenarios.json

# Aggressive growth (40% annually)
python3 run_scenario_analysis.py 001_exercise_all_vested --price aggressive
```

### Extended Projections
Model longer time horizons - useful for seeing the impacts of the expiration of options, expiration of pledge obligations matching window, and expiration of the charitable deduction carryforward to make sure you are acting quickly enough and staggering your decisions appropriately.
```bash
# 15-year projection
python3 run_scenario_analysis.py 001_exercise_all_vested --years 15
```

---

## 📁 What's in This Project

```
📂 Main Tools
├── run_scenario_analysis.py     # Test an individual strategies
├── run_portfolio_analysis.py    # Compare multiple strategies
├── copy_scenario_csvs.py        # Open sheets.new and simply paste in the full output of any scenario for easy viewing.
└── run_all_tests.py             # Developers: Check the calculators are working if you make any changes.

📂 Your Data (Private)
├── input_data/user_profile.json           # Your financial data (git-ignored)
└── scenarios/user/*                       # Your custom strategies (git-ignored)

📂 Demo Data (Safe)
├── input_data/demo_profile.json           # Example data for testing
└── scenarios/demo/*                       # Example strategies

📂 Results
└── output/                                # All analysis results
    ├── demo/                              # Demo results (safe to share)
    └── user/                              # Your results (git-ignored)
```

---

## ⚡ Next Steps

**For your first alpha test:**
1. ✅ Run the demo analysis (you did this!)
2. ✅ Understand the results format
3. 🎯 **Next**: Create your user profile and run with real data
4. 🎯 **Then**: Create a custom strategy and compare results
5. 🎯 **Finally**: Share your feedback!

**Questions to explore:**
- How much tax could you save by exercising early vs. waiting?
- What's the charitable impact difference between strategies?
- How quickly do I need to act to ensure completion before I start hitting expiry deadlines?
- How do different market scenarios affect your optimal strategy? (Monte Carlo not yet implemented)
- When should you participate in tender offers vs. hodl?

---

## 🙏 Built for Impact

This tool exists because equity compensation decisions are complex, but the stakes are high. Every dollar optimized can create multiple dollars of charitable impact through company matching programs.

**Remember**: This provides analysis, not advice. Always consult qualified tax and financial advisors before making major financial decisions.

**Your feedback matters** - as an alpha tester, your experience helps make this tool better for everyone navigating equity compensation decisions.

---

*May your actions create positive change in the world.* 🌍
