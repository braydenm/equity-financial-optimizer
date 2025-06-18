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
- Explain why simplified profile loader exists and whether regular loader can be used (natural_evolution_generator.py)
- Profile loading redundancy - loading profile twice in natural_evolution_generator.py
- Use regular profile loader and delete simplified version (natural_evolution_generator.py)
- Option expiration date hardcoded at 10 years, should pull from user profile (natural_evolution_generator.py)
- Load price projections from external source instead of no-change assumption (natural_evolution_generator.py) - 2 instances
- Improve documentation for basis election logic (projection_calculator.py)
- Lot ID parsing in pledge obligations assumes specific underscore convention (projection_output.py)
- Forward reference in ProjectionResult needs documentation for simplest implementation (projection_state.py)
- Investment return rate hardcoded at 7%, should be user specified (projection_state.py)
- Search codebase systematically for other hardcoded tax values that should be in tax_constants.py (comprehensive audit needed)
- Federal vs state charitable deduction persistence: only federal charitable_deduction_result saved in AnnualTaxResult, CA result discarded (annual_tax_calculator.py)
- Projection calculator only uses federal charitable carryforwards, ignoring CA-specific carryforward rules (projection_calculator.py)
- CSV generation comment claims federal limits are "most restrictive" but CA cash limit (50%) < federal (60%) (projection_output.py)
- Consider separate federal vs state charitable deduction tracking in projection state for accurate multi-year planning (projection_state.py)

### Immediate Priorities
**Partner on Detailed Scenarios** - Work with user on specific equity compensation scenarios to stress test the model end to end and provide feedback on accuracy and usability.

### E2E Testing Plan for Critical Financial Pathways
**Context**: The AMT credit carryforward bug revealed a critical gap - multi-year state management wasn't properly tested. This could affect other financial calculations with similar patterns. We've already discovered a CRITICAL bug in charitable deduction carryforward where AGI limits are ignored!

**Discovered Bugs Requiring Immediate Fix:**
1. **Charitable Deduction AGI Limits Not Applied** - CRITICAL BUG affecting tax liability calculations
   - **Symptom**: Donations are deducted at 100% of value regardless of AGI limits
   - **Expected**: Stock donations limited to 30% of AGI, cash to 60% of AGI per IRS rules
   - **Root Cause**: In `projection_calculator.py`, the `_calculate_charitable_state` method sets `current_year_deduction=year_donation` without any AGI limit checks
   - **The Disconnect**: `annual_tax_calculator.py` correctly calculates `charitable_deduction_result` with proper AGI limits, but this result is never propagated back to `yearly_state.charitable_state`
   - **Impact**: Tax liability could be understated by $100K+ in high-donation scenarios
   - **Test Case**: $500K AGI with $400K donation shows $400K deduction (should be $150K)
   - **Fix Required**: Update `projection_calculator.py` to use `tax_result.charitable_deduction_result` instead of the naive calculation
   - **Pattern**: Similar to AMT credit bug - correct calculation exists but state management fails

**High-Risk Areas Requiring E2E Tests:**

1. **Charitable Deduction Carryforward** (CRITICAL - BUG CONFIRMED)
   - Risk: 5-year expiration, federal/state limit mixing, wrong year attribution
   - Impact: Phantom deductions, incorrect tax liability
   - Current Bug: AGI limits completely ignored - $400K donation shows as $400K deduction instead of $150K (30% limit)
   - Test Scenarios:
     * Large single-year donation exceeding 30% AGI limit
     * Multi-year donations with varying AGI
     * Mixed cash (60% limit) and stock (30% limit) donations
     * Carryforward expiration after 5 years
     * Basis election changing limits from 30% to 50%
   - Implementation: Fix `_calculate_charitable_state` to use tax_result.charitable_deduction_result

2. **Pledge Obligation Tracking** (CRITICAL)
   - Risk: 3-year fulfillment window, obligations not carrying forward
   - Impact: Missed obligations, incorrect company match calculations
   - Test Scenarios:
     * Sale creating 50% pledge, track for 3 years
     * Multiple sales with overlapping pledge windows
     * Partial fulfillment across years
     * Pledge expiration warnings and enforcement
     * Company match limit calculations
   - Validation: Ensure pledge_state properly carries forward like AMT credits

3. **ISO Disqualifying Disposition** (HIGH)
   - Risk: Complex date calculations (exercise + 2yr AND grant + 1yr)
   - Impact: Wrong tax treatment (ordinary income vs LTCG)
   - Test Scenarios:
     * Exercise and sell < 1 year (STCG + ordinary income)
     * Exercise and sell > 1 year but < 2 years from exercise (disqualifying)
     * Exercise and sell > 2 years from exercise AND > 1 year from grant (qualifying)
     * Edge case: Exactly 365 vs 366 days
   - Validation: Compare tax treatment against IRS Publication 525

4. **Cash Flow Viability** (CRITICAL)
   - Risk: Strategies requiring negative cash
   - Impact: Impossible-to-execute strategies
   - Test Scenarios:
     * Exercise costs exceeding available cash
     * Tax payments causing negative cash
     * Living expenses not covered
     * Sequence of actions depleting cash mid-year
   - Implementation: Add cash_flow_valid flag and warnings

5. **NSO Withholding Reconciliation** (MEDIUM)
   - Risk: Withholding ≠ actual tax owed
   - Impact: Surprise tax bills or phantom refunds
   - Test Scenarios:
     * High NSO exercise with supplemental withholding
     * Year-end true-up calculation
     * Estimated tax payment requirements
     * Refund vs additional payment due

**Implementation Priority:**
1. **IMMEDIATE**: Fix charitable deduction bug - propagate tax_result.charitable_deduction_result to yearly_state
2. **WEEK 1**: Create regression tests for charitable deduction carryforward
3. **WEEK 2**: Add pledge obligation E2E tests
4. **WEEK 3**: ISO disposition and cash flow validation tests
5. **WEEK 4**: NSO withholding reconciliation tests

**Test Structure Template:**
```python
def test_[pathway]_e2e():
    # 1. Setup multi-year scenario
    # 2. Execute projection
    # 3. Validate year 1 state
    # 4. Validate carryforward to year 2
    # 5. Check edge cases
    # 6. Assert against hand calculations
```

### Raw Data Table - Residual Work

**Residual Work** (from original 5-table plan):
1. **EQUITY POSITION table** (→ equity_holdings.csv) was not implemented
2. **Charitable donations table** would be valuable given the AGI limit bug discovered
3. **Column name validation** - Ensure terminal headers exactly match CSV headers

### TODO Burndown Plan - Structured Groups

**Current State: 12 TODOs Remaining** (Groups A1 & A2 completed, 4 new federal/state issues discovered)

#### Group A2: Tax Constants Consolidation (COMPLETED ✅)
*Priority: HIGH - Accuracy & maintainability*

**TODOs Completed:**
- ✅ Basis election 50% limit hardcoded, should pull from tax_constants.py (annual_tax_calculator.py) - 2 instances
- ✅ Tax limit percentages in CSV generation should differentiate federal vs state (projection_output.py)

**Resolution**: 
- Added FEDERAL_CHARITABLE_BASIS_ELECTION_AGI_LIMITS and CALIFORNIA_CHARITABLE_BASIS_ELECTION_AGI_LIMITS to tax_constants.py
- Replaced hardcoded 0.50 values in annual_tax_calculator.py with constants from tax_constants.py
- Updated projection_output.py to use constants and differentiate federal vs state tax limits
- Added comprehensive regression tests to prevent future hardcoded values

**Impact**: High - System maintainability improved for tax law changes, easier compliance updates

#### Group B: User Experience & Configuration (4 TODOs)
*Priority: MEDIUM - Scenario realism and flexibility*

**B1. User-Configurable Parameters:**
- Investment return rate hardcoded at 7%, should be user specified (projection_state.py)
- Option expiration date hardcoded at 10 years, should pull from user profile (natural_evolution_generator.py)

**B2. Market Intelligence:**
- Load price projections from external source instead of no-change assumption (natural_evolution_generator.py) - 2 instances

**Rationale**: Enable realistic scenario modeling with user control
**Impact**: Medium-High - Strategy accuracy

#### Group C: Code Quality & Robustness (4 TODOs)
*Priority: LOWER - Technical debt cleanup*

**C1. Profile Loading Cleanup:**
- Explain why simplified profile loader exists and whether regular loader can be used (natural_evolution_generator.py)
- Profile loading redundancy - loading profile twice in natural_evolution_generator.py
- Use regular profile loader and delete simplified version (natural_evolution_generator.py)

**C2. Documentation & Edge Cases:**
- Improve documentation for basis election logic (projection_calculator.py)
- Forward reference in ProjectionResult needs documentation for simplest implementation (projection_state.py)
- Lot ID parsing in pledge obligations assumes specific underscore convention (projection_output.py)

**Rationale**: Improve maintainability and prevent edge case failures
**Impact**: Low-Medium - Developer experience

#### Implementation Schedule
- **Sprint 1**: ✅ Fix charitable deduction bug (COMPLETED - discovered via E2E testing)
- **Sprint 2**: ✅ Group A2 - Tax constants consolidation (COMPLETED)
- **Sprint 3**: Group B - User experience & configuration
- **Sprint 4**: Group C - Code quality & robustness
