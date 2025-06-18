# CLAUDE.md - AI Context for Equity Financial Optimizer

## Project Overview
Equity compensation optimizer for ISO/NSO/RSU tax planning. Uses component-based architecture
where individual calculators extract event components, and annual tax calculator aggregates them
for actual tax calculations using progressive brackets (not flat rates).

## Architecture Principles
- Calculators are pure functions returning components, not final tax amounts
- Tax calculations happen at annual level after aggregating all events
- All inputs from JSON, all outputs to CSV (no CSV as intermediate format)
- Progressive tax brackets throughout - no flat rate approximations
- Timing matters: 364 vs 366 days = STCG vs LTCG
- Direct JSON-to-object loading via loaders, no complex intermediate representations

## Key Components
- calculators/: Specialized calculators (ISO exercise, share sale, donation, annual tax)
- engine/: Portfolio manager for scenario execution
- projections/: Multi-year projection engine with cash flow tracking
- loaders/: Direct JSON-to-ShareLot loading (no CSV parsing for inputs)
- scenarios/: JSON scenario definitions with optional tax_elections
- output/: CSV outputs for analysis (data-source specific: demo/ vs user/)

## Working Guidelines

### Session Management
**Start with goals, not solutions** - Ask "What are you trying to achieve?" and distinguish "building forward" vs "cleaning up"
**Present trade-offs** - Frame decisions as "Option A vs B" with clear pros/cons, not single recommendations
**Use pause points** - Before major changes, stop and confirm approach. Break large tasks into atomic steps
**Define success upfront** - Establish clear criteria before starting work

### Code Changes
**Edit atomically** - Make isolated, in-place edits. Read files before editing. Use `mv` to move files
**Respect boundaries** - Each file has a specific purpose. Don't mix concerns across files
**Test before and after** - Run tests before changes and verify they pass after
**Understand before removing** - Investigate why code exists before deleting it
**Check changed files** - When notified "These files changed since last read", immediately read the changed files to understand what's different before proceeding with any analysis or modifications

### Documentation & State
**Document as you go** - Update docs inline with changes, not later. No time estimates in plans or dates in changelogs.
**Track state here** - Don't maintain separate todo lists. After commits, ask "what are the next steps?"

### Design Approach
**Keep it simple** - Aim for E2E validation over complex designs. Ask about abstraction preferences
**Use discovery questions** - Ask about constraints and risk tolerance rather than assuming

## Technical Standards
- Python 3 with type hints throughout
- Decimal for monetary precision
- ISO 8601 dates
- Comprehensive docstrings with examples
- Error messages user-friendly and actionable
- No external dependencies beyond numpy/pandas

## Data Flow
1. User profile (JSON) → loaders → ShareLot objects
2. Scenario (JSON) → planned actions + tax elections
3. Projection engine → processes actions → generates components
4. Annual tax calculator → aggregates components → calculates actual taxes
5. Results → CSV outputs for analysis

## Testing Approach
- Unit tests for each calculator with known values
- Integration tests with realistic scenarios
- All monetary assertions use exact values, not approximations
- Test both federal and California calculations
- Edge cases: negative values, missing data, boundary conditions

## Key Files for New Agents

### Project Directory Structure
```
equity-financial-optimizer/
├── calculators/               # Core tax calculation components
│   ├── annual_tax_calculator.py
│   ├── iso_exercise_calculator.py
│   ├── share_sale_calculator.py
│   ├── share_donation_calculator.py
│   ├── components.py         # Data structures for tax components
│   ├── amt_calculator.py
│   └── tax_constants.py
├── engine/                   # Scenario execution engine
│   ├── portfolio_manager.py
│   ├── timeline_generator.py
│   └── natural_evolution_generator.py
├── projections/              # Multi-year projection system
│   ├── projection_calculator.py
│   ├── projection_state.py   # Core data models
│   ├── projection_output.py  # CSV generation
│   └── pledge_calculator.py
├── loaders/                  # Data loading utilities
│   ├── equity_loader.py
│   ├── profile_loader.py
│   └── scenario_loader.py
├── scenarios/                # Scenario definitions (JSON)
│   ├── demo/                # Example scenarios
│   └── user/                # Personal scenarios (git-ignored)
├── tests/                    # Comprehensive test suite
├── docs/                     # Documentation
├── input_data/              # User profiles and market assumptions
├── portfolios/              # Portfolio comparison configurations
└── run_*.py                 # Main CLI tools
```

### Must-Read Documentation (in order)
1. **docs/CLAUDE.md** (this file) - Project context and working instructions
2. **docs/TECHNICAL_ARCHITECTURE.md** - System design, data flow, and architectural decisions
3. **docs/DATA_CONTRACT.md** - Profile format v2.0 specification
4. **docs/CHANGELOG.md** - Complete feature history to understand evolution

### Recommended Code Files to Study
1. **calculators/annual_tax_calculator.py** - Core tax engine showing component aggregation and bracket calculations
2. **projections/projection_calculator.py** - Multi-year scenario evaluation demonstrating the event processing pipeline
3. **engine/portfolio_manager.py** - Scenario execution orchestration showing how everything ties together
4. **tests/test_charitable_deduction_limits.py** - Example of comprehensive testing approach with basis election tests
5. **scenarios/demo/004_basis_election_example.json** - Example scenario showing tax election configuration

## Architecture Documentation
- TECHNICAL_ARCHITECTURE.md - System design and data flow
- CHANGELOG.md - Complete feature history
- PROJECT_SPEC.md - Original requirements
- DATA_CONTRACT.md - Profile format specification

## Current Status & Backlog

### Project Status
Production-ready core with comprehensive test coverage. Main calculators operational,
handling complex scenarios including tender offers, ISO exercises, charitable donations
with basis elections, and multi-year projections. Ready for enhancement with additional
state tax systems, ESPP support, and advanced optimization features.

### Project History
See CHANGELOG.md for complete feature history and implementation details.

### Implementation State
- Component-based tax calculation system fully operational
- Progressive brackets for federal/state income tax and LTCG
- AMT calculation with credit tracking across years
- Charitable deduction AGI limits (30% stock, 60% cash federal, 50% cash CA)
- Basis election for charitable donations (per-year configuration)
- Natural vesting through state transitions (no event detection needed)
- Comprehensive test suite with all tests passing
- Security model: demo vs user data separation with automatic fallback

### Known Issues
- Carryforwards not tracked separately by donation type (cash vs stock)
- Ordering rules for charitable deductions could be more explicit
- Action summary CSV incorrectly shows "iso_exercise_calculator" for all exercises (display issue only, calculations are correct)

### Inline TODOs in Code
(Search for each of these TODOs when fixing, then remove them from the comments after being resolved)
- Basis election 50% limit hardcoded, should pull from tax_constants.py (annual_tax_calculator.py) - 2 instances
- Explain why simplified profile loader exists and whether regular loader can be used (natural_evolution_generator.py)
- Profile loading redundancy - loading profile twice in natural_evolution_generator.py
- Use regular profile loader and delete simplified version (natural_evolution_generator.py)
- Option expiration date hardcoded at 10 years, should pull from user profile (natural_evolution_generator.py)
- Load price projections from external source instead of no-change assumption (natural_evolution_generator.py) - 2 instances
- Improve documentation for basis election logic (projection_calculator.py)
- Lot ID parsing in pledge obligations assumes specific underscore convention (projection_output.py)
- Tax limit percentages in CSV generation should differentiate federal vs state (projection_output.py)
- Forward reference in ProjectionResult needs documentation for simplest implementation (projection_state.py)
- Investment return rate hardcoded at 7%, should be user specified (projection_state.py)

### Immediate Priorities
**Partner on Detailed Scenarios** - Work with user on specific equity compensation scenarios to stress test the model end to end and provide feedback on accuracy and usability.

### Raw Data Table Implementation Plan
**Objective**: Replace formatted summary tables with raw data tables that map directly to CSV structure for better data analysis workflow.

**Current Problem**:
- Summary tables mix concepts (withholding vs tax liability vs cash flow)
- Overlap between Financial Summary and Cash Flow Waterfall reduces clarity
- Users want clean data that corresponds exactly to CSV outputs

**Proposed Solution**: Five raw data tables with 1:1 CSV mapping

**Implementation Plan**:

1. **Update run_scenario_analysis.py display logic**
   - Replace current summary tables with raw data format
   - Use actual CSV column names as table headers
   - Ensure data matches exactly what appears in generated CSVs
   - Remove calculated fields that don't exist in CSVs

2. **Five Raw Data Tables**:
   - **ANNUAL CASH FLOW** → yearly_cashflow.csv mapping
   - **TAX CALCULATION** → tax_timeline.csv mapping
   - **EQUITY POSITION** → equity_holdings.csv mapping
   - **ACTION SUMMARY** → action_summary.csv mapping
   - **ASSETS BREAKDOWN** → annual_summary.csv mapping (net worth components by year)

3. **Table Format Requirements**:
   - Clean, copy-pasteable format with consistent spacing
   - Column headers match CSV field names exactly
   - No formatting like "$" or "%" in data (raw numbers only)
   - Direct 1:1 correspondence between terminal and CSV data

4. **Implementation Steps**:
   - Modify `print_scenario_results()` function in run_scenario_analysis.py
   - Create helper functions for each raw data table
   - Ensure consistent number formatting across tables
   - Add brief table descriptions explaining corresponding CSV files
   - Test with existing scenarios to verify data accuracy

**Success Criteria**:
- Terminal output data can be copied directly into spreadsheets
- Every table value corresponds to exact CSV cell
- No duplicate information across tables
- Clear mapping between terminal display and CSV analysis files
