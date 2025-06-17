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
├── data/demo_profile.json                      # Safe example data (committable)
├── data/user_profile_template.json             # Template for new users
└── data/market_assumptions/price_scenarios.json # Growth rate assumptions

Input Data (git-ignored):
└── data/user_profile.json                      # v2.0 financial profile (private)

↓ (CLI auto-detects data source or uses --demo flag)

Data Source Detection:
├── ProfileLoader.load_profile(force_demo=flag)
├── Auto-detection: user_profile.json exists → user data
├── Fallback: user_profile.json missing → demo data
└── Force demo: --demo flag → demo data regardless

↓ (generate base inventory)

Working Files (data-source specific):
└── output/working/equity_position_timeline.csv  # Base share inventory

↓ (human creates scenarios)

Scenario Definitions (data-source specific):
├── scenarios/demo/000_natural_evolution_actions.csv    # Safe scenarios
├── scenarios/demo/001_exercise_all_vested_actions.csv  # Uses demo lot IDs
├── scenarios/user/000_natural_evolution_actions.csv    # Private scenarios
└── scenarios/user/001_exercise_all_vested_actions.csv  # Uses real lot IDs

↓ (portfolio manager executes with traceability)

Results (organized by data source + price scenario):
├── output/demo/moderate/scenario_000_natural_evolution/
│   ├── yearly_cashflow.csv
│   ├── tax_timeline.csv
│   ├── equity_holdings.csv
│   ├── summary.csv
│   └── metadata.json                           # Full execution traceability
├── output/user/aggressive/scenario_001_exercise_all_vested/
│   └── [same structure with user data results]
└── output/{data_source}/portfolio_comparisons/
    └── moderate_tax_strategy_comparison.csv
```

## File Organization

```
# Main CLI Tools (Root Level)
run_portfolio_analysis.py              # Execute and compare multiple scenarios
run_scenario_analysis.py               # Execute individual scenarios

scenarios/                              # Data-source specific scenario definitions
├── demo/                              # Safe example scenarios (committable)
│   ├── 000_natural_evolution_actions.csv     # Baseline: no actions taken
│   ├── 001_exercise_all_vested_actions.csv   # Exercise all vested options
│   └── 002_tender_and_donate_actions.csv     # Complex multi-year strategy
└── user/                              # Personal scenarios (git-ignored)
    ├── 000_natural_evolution_actions.csv     # Uses real user lot IDs
    ├── 001_exercise_all_vested_actions.csv   # Uses real user quantities
    └── 002_tender_and_donate_actions.csv     # Uses real user data

portfolios/                             # Portfolio definitions (JSON)
└── tax_strategies.json                # Groups scenarios for comparison

output/                                 # Results with full traceability
├── demo/moderate/scenario_000_natural_evolution/     # Demo data results
├── user/moderate/scenario_001_exercise_all_vested/   # User data results
├── {data_source}/portfolio_comparisons/              # Portfolio comparisons
└── working/equity_position_timeline/                 # Generated timelines

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
├── profile_loader.py                   # Secure profile loading with demo fallback
└── __init__.py

data/                                   # User data and assumptions
├── user_profile.json                   # v2.0 format financial data (git-ignored)
├── demo_profile.json                   # Safe example data (committable)
├── user_profile_template.json          # Template for new users
└── market_assumptions/
    └── price_scenarios.json           # Growth rate definitions

examples/                               # Educational demonstrations
└── portfolio_analysis.py               # Educational example (use main CLI tools)

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
├── TIMELINE_DATA_MODEL.md              # Timeline data model
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

### Design**: Stateless, composable functions with strong typing and validation.

### Projection System
**Purpose**: Multi-year scenario evaluation using core calculators

- **`projection_state.py`**: Data models with comprehensive state tracking
- **`projection_calculator.py`**: Year-by-year orchestration maintaining state
- **`projection_output.py`**: Structured CSV outputs for analysis

**Design**: Takes any `ProjectionPlan` and evaluates it deterministically.

## Main Execution Workflow

### Core Workflow: Data → Scenarios → Projections → Analysis

#### Step 1: Data Source Detection & Timeline Generation
```
CLI Tool (--demo flag or auto-detection)
    ↓
ProfileLoader.load_profile(force_demo=flag)
    ↓
{user|demo}_profile.json → equity_position_timeline.csv
    ↓
BaseEquityState (lots, vesting schedule, financial constraints)
```

#### Step 2: Scenario Resolution
```
Scenario Name (e.g., "001_exercise_all_vested")
    ↓
Data Source Detection → scenarios/{demo|user}/001_exercise_all_vested_actions.csv
    ↓
CSV Actions → ProjectionPlan (complete multi-year action sequence)
```

#### Step 3: Financial Projection
```
ProjectionPlan + UserProfile
    ↓
ProjectionCalculator (orchestrates ISO, Sale, Donation calculators)
    ↓
YearlyProjection (cash, taxes, donations, obligations, stock value)
```

#### Step 4: Traceability & Output
```
YearlyProjection
    ↓
Output Generation with metadata.json
    ↓
output/{data_source}/{price_scenario}/scenario_{name}/
├── yearly_cashflow.csv
├── tax_timeline.csv  
├── equity_holdings.csv
├── summary.csv
└── metadata.json (execution traceability)
```

### Enhanced Security & Traceability Features

#### Data Source Isolation
- **Demo scenarios**: Safe example data using demo lot IDs (committable)
- **User scenarios**: Personal data using real lot IDs (git-ignored)
- **Automatic detection**: System chooses appropriate scenario directory
- **Force demo**: `--demo` flag overrides auto-detection

#### Complete Execution Traceability
- **metadata.json**: Records data source, price scenario, timestamps, profile version
- **Structured output paths**: `output/{data_source}/{price_scenario}/scenario_{name}/`
- **Portfolio comparisons**: Grouped by data source with clear labeling
- **Audit trail**: Every execution tracked with complete parameter set

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

## Charitable Basis Election Implementation

### Overview
The charitable basis election feature allows users to elect IRC Section 170(b)(1)(C)(iii) treatment for stock donations, choosing to deduct cost basis instead of FMV in exchange for a higher AGI limit (50% vs 30%).

### Technical Design
- **Per-Year Configuration**: Elections specified in scenario JSON as `charitable_basis_election_years` array
- **All-or-Nothing Annual Choice**: Applies to all stock donations in specified tax years
- **Component-Based Flow**: Election flag flows from scenario → projection → annual tax calculator

### Data Flow
1. **Scenario Definition**: User specifies election years in `tax_elections` section
2. **Projection Processing**: `ProjectionCalculator` checks if current year has election
3. **Tax Calculation**: `AnnualTaxCalculator` receives `elect_basis_deduction` flag
4. **Deduction Logic**: When elected, uses `cost_basis * shares` instead of FMV
5. **AGI Limits**: Applies 50% limit for basis election vs 30% for FMV

### Implementation Details

#### Scenario JSON Structure
```json
{
  "tax_elections": {
    "charitable_basis_election_years": [2025, 2026, 2027]
  }
}
```

#### Calculator Updates
- **AnnualTaxCalculator._apply_charitable_deduction_limits()**:
  - Added `elect_basis_deduction` parameter
  - Calculates deduction as basis when elected
  - Applies appropriate AGI limit (50% vs 30%)

#### CSV Output Enhancement
- **charitable_carryforward.csv** includes:
  - `basis_election`: Yes/No indicator per year
  - `stock_deduction_type`: "Basis" or "FMV"
  - Correct stock limit display based on election

### Key Design Decisions
1. **Explicit Configuration**: No automatic recommendation - users must choose
2. **Annual Granularity**: Matches IRS rules for annual elections
3. **Transparent Reporting**: CSV clearly shows election impact

### When Basis Election Helps
- Stock donations exceed 30% AGI limit but within 50%
- Low appreciation stock (basis > 60% of FMV)
- Need to maximize current year deductions

### Testing Coverage
- High vs low appreciation scenarios
- Mixed stock and cash donations
- Federal and California calculations
- Portfolio comparison demonstrations

The portfolio-based architecture provides a solid foundation for equity optimization while maintaining simplicity through data-driven design and intelligent defaults.