# Technical Architecture - Equity Financial Optimizer

## Core Purpose
Help users make optimal equity compensation decisions, with special focus on maximizing charitable impact through company donation matching programs.

## Current Architecture: Portfolio-Based Projection System

The system centers around **data-driven scenario planning** where users define strategies in CSV files and the system evaluates complete financial outcomes deterministically across multiple years.

### Core Philosophy
- **Data-driven scenarios**: Strategies defined in CSV files, not code
- **Portfolio execution**: Group and compare multiple scenarios with shared assumptions
- **Price intelligence**: Automatic price determination based on action type and context
- **Discovery through comparison**: Optimal strategies emerge from comparing concrete scenarios
- **Heavy-lifting calculators**: Core financial computations (AMT, capital gains, donations) provide the mathematical foundation
- **Private data isolation**: All user-specific data lives in `output/` directory and is never committed

## Data Flow: From CSV Actions to Financial Decisions

```
Input Data (version controlled):
├── data/user_profile.json                      # v2.0 financial profile
└── data/market_assumptions/price_scenarios.json # Growth rate assumptions

↓ (generate base inventory)

Working Files (generated):
└── output/working/equity_position_timeline.csv  # Base share inventory

↓ (human creates scenarios)

Scenario Definitions (CSV-based):
├── scenarios/natural_evolution/actions.csv      # Baseline: no actions
├── scenarios/exercise_all_vested/actions.csv    # Exercise strategy
├── scenarios/tender_and_donate/actions.csv      # Complex multi-year plan
└── scenarios/.../actions.csv                    # Many more strategies

↓ (portfolio manager executes)

Results (multi-year projections):
├── output/natural_evolution/
│   ├── yearly_cashflow.csv
│   ├── tax_timeline.csv
│   ├── equity_holdings.csv
│   └── summary.csv
└── output/portfolio_comparison.csv
```

## File Organization

```
scenarios/                               # Data-driven scenario definitions
├── README.md                           # How to create scenarios
├── natural_evolution/                  # Each scenario is a directory
│   └── actions.csv                    # CSV defining planned actions
├── exercise_all_vested/
│   └── actions.csv
└── tender_and_donate/
    └── actions.csv

portfolios/                             # Portfolio definitions (JSON)
└── tax_strategies.json                # Groups scenarios for comparison

calculators/                            # Core financial computations
├── iso_exercise_calculator.py          # AMT calculations, breakeven analysis
├── share_sale_calculator.py            # Capital gains tax computations
├── share_donation_calculator.py        # Charitable deduction calculations
└── __init__.py

projections/                            # Multi-year projection engine
├── projection_state.py                 # Data models: ProjectionPlan, ShareLot, etc.
├── projection_calculator.py            # Orchestrates calculators across years
├── projection_output.py                # CSV formatting for results
└── __init__.py

engine/                                 # Portfolio and scenario management
├── portfolio_manager.py                # Execute scenarios and portfolios
├── natural_evolution_generator.py      # Generate baseline scenarios
└── __init__.py

loaders/                                # Data loading utilities
├── csv_loader.py                       # Load equity timeline and actions
├── scenario_loader.py                  # Load scenario definitions
└── __init__.py

data/                                   # User data and assumptions
├── user_profile.json                   # v2.0 format financial data
├── market_assumptions/
│   └── price_scenarios.json           # Growth rate definitions
└── README.md

examples/                               # Usage demonstrations
├── portfolio_analysis.py               # Main CLI tool
├── projection_analysis.py              # Natural evolution demo
└── multi_scenario_analysis.py          # Legacy multi-scenario runner

tests/                                  # Unit tests with known values
├── test_iso_exercise_calculator.py
├── test_share_sale_calculator.py
├── test_share_donation_calculator.py
└── run_all_tests.py

docs/                                   # Documentation
├── CLAUDE.md                           # AI context and implementation state
├── TECHNICAL_ARCHITECTURE.md           # This file
├── PORTFOLIO_ARCHITECTURE.md           # Portfolio system design
├── DATA_CONTRACT.md                    # Profile format specification
├── PROJECT_SPEC.md                     # Original requirements
└── reference/                          # Reference implementations
```

## Architecture Components

### Portfolio Manager (New Central Component)
**Purpose**: Orchestrate scenario execution with intelligent defaults

- **Price Projector**: Linear growth from base 409A price
- **Scenario Loading**: Parse CSV actions into projection plans
- **Price Intelligence**: Determine appropriate prices by action type
- **Batch Execution**: Run multiple scenarios with shared assumptions

**Key Features**:
- No hardcoded prices in scenarios
- Dynamic date handling (current date + N years)
- Unified data loading (load profile once, use everywhere)
- Portfolio comparison outputs

### Core Calculators (Heavy Lifting)
**Purpose**: Pure financial computations with sophisticated tax modeling

- **`iso_exercise_calculator.py`**: AMT calculations, federal/state tax, breakeven analysis
- **`share_sale_calculator.py`**: Capital gains computations, lot selection
- **`share_donation_calculator.py`**: Charitable deductions, AGI limits, company match

**Key Functions**:
- `estimate_iso_exercise_tax()` - Full ISO exercise cost analysis
- `calculate_tender_tax()` - Capital gains with automatic validation
- `calculate_donation()` - Unified function for cash and share donations

**Design**: Stateless, composable functions with strong typing and validation.

### Projection System
**Purpose**: Multi-year scenario evaluation using core calculators

- **`projection_state.py`**: Data models with comprehensive state tracking
- **`projection_calculator.py`**: Year-by-year orchestration maintaining state
- **`projection_output.py`**: Structured CSV outputs for analysis

**Design**: Takes any `ProjectionPlan` and evaluates it deterministically.

### Price Intelligence System
**Purpose**: Eliminate manual price entry errors

1. **Exercise Actions**: Always use strike price from share lot
2. **Sell Actions**: 
   - Check if within 30 days of tender offer → use tender price
   - Otherwise → use projected market price
3. **Donate Actions**: Use projected market price for proper deduction

### Human-in-the-Loop Workflow
**Purpose**: Enable systematic exploration of strategy space

1. **Create scenario directory**: `mkdir scenarios/my_strategy`
2. **Define actions in CSV**: Simple, Excel-friendly format
3. **Execute scenario**: Automatic price determination
4. **Compare in portfolio**: Group related scenarios
5. **Analyze results**: CSV outputs for decision making

## Key Technical Decisions

### Data-Driven Architecture
- **CSV scenarios**: Non-programmers can create/modify strategies
- **No JSON configs**: Removed redundant configuration files
- **Price scenarios**: Separated from user profile (no duplication)
- **Portfolio grouping**: Natural way to organize comparisons

### Python Design Patterns
- **Dataclasses**: For all state objects with type hints
- **Pure functions**: Calculators remain stateless
- **Decimal precision**: For accurate financial calculations
- **Path handling**: Relative paths from project root

### Execution Patterns
```
Single Scenario:
portfolio_analysis.py scenario path/to/scenario --price moderate --years 5

Portfolio:
portfolio_analysis.py portfolio portfolios/tax_strategies.json

Quick Demo:
portfolio_analysis.py demo
```

## System Integration Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Portfolio Manager                             │
│  • Load user data once                                              │
│  • Generate price projections                                       │
│  • Execute scenario(s)                                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Projection Calculator                           │
│  • Parse CSV actions with intelligent pricing                       │
│  • Orchestrate year-by-year evaluation                             │
│  • Maintain state (cash, tax credits, pledge obligations)          │
└────────┬──────────────┬──────────────┬─────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ ISO Exercise    │ │ Share Sale      │ │ Share Donation  │
│ Calculator      │ │ Calculator      │ │ Calculator      │
│                 │ │                 │ │                 │
│ • AMT impact    │ │ • Capital gains │ │ • Tax deduction │
│ • Fed + CA tax  │ │ • LTCG vs STCG  │ │ • Company match │
│ • Cash needed   │ │ • Net proceeds  │ │ • AGI limits    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Typical User Journey

1. **Setup**: Ensure `user_profile.json` has current financial data
2. **Review timeline**: Check `equity_position_timeline.csv` is current
3. **Create scenario**: Write `actions.csv` with planned strategy
4. **Test scenario**: Run with different price assumptions
5. **Build portfolio**: Group related scenarios for comparison
6. **Execute portfolio**: Generate comprehensive projections
7. **Analyze results**: Review CSV outputs, understand trade-offs
8. **Make decision**: Choose strategy based on quantified outcomes

## Architectural Principles

### 1. Separation of Concerns
- **Data**: User profile, market assumptions (inputs)
- **Scenarios**: CSV action definitions (strategies)
- **Calculators**: Pure financial computations (math)
- **Projections**: Multi-year orchestration (state)
- **Portfolios**: Comparison framework (analysis)

### 2. Composability
- Calculators can be used independently
- Scenarios can be mixed into different portfolios
- Price scenarios can be swapped without changing actions
- Output formats can be extended

### 3. Maintainability
- No hardcoded values in scenarios
- Single source of truth for user data
- Clear separation of configuration and computation
- Comprehensive test coverage

### 4. Extensibility
- New action types can be added
- Additional calculators can be integrated
- Custom price models can be implemented
- Output formats can be enhanced

## Future Enhancements

### Near Term
- Annual tax aggregation for complex multi-action years
- Improved pledge tracking (maximalist vs minimalist)
- AMT credit carryforward across years
- Charitable deduction carryforward with expiration

### Medium Term
- Scenario generation tools (parameter sweeps)
- Monte Carlo price variations
- Integration with financial planning tools
- Web-based scenario builder

### Long Term
- AI-assisted scenario generation
- Optimization algorithms for specific goals
- Real-time market data integration
- Multi-user collaboration features

The portfolio-based architecture provides a solid foundation for equity optimization while maintaining simplicity through data-driven design and intelligent defaults.