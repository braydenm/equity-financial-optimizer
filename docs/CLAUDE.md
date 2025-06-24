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

## Architecture Documentation
- TECHNICAL_ARCHITECTURE.md - System design and data flow
- CHANGELOG.md - Complete feature history
- PROJECT_SPEC.md - Original requirements
- DATA_CONTRACT.md - Profile format specification

## Current Status & Backlog

### Project Status
**Project Status**
Production-ready core with comprehensive test coverage and complete federal vs state tax separation.
Main calculators operational, handling complex scenarios including tender offers, ISO exercises,
charitable donations with basis elections, multi-year projections, Federal and California
charitable deductions and carryforward management with both fmv basis and basis election support,
and complete company match tracking with 3-year match window enforcement. Company match tracking
provides full visibility into charitable leverage with proper timing validation, lost opportunity
tracking, and comprehensive CSV reporting for strategic planning.

Some initial user scenarios ready with further exploration necessary to find optimal action strategy for specific user goals.

### Project History
See CHANGELOG.md for complete feature history and implementation details.


### Next Steps & Readiness

**Immediate Opportunities:**
- Real-world scenario validation with users to stress-test edge cases

### Known Issues
- CA AMT credit tracking not implemented (see TODO comment in annual_tax_calculator.py for future implementation when use cases arise)

### Inline TODOs in Code
(Search for each of these TODOs when fixing, then remove them from the comments after being resolved)
- Explain why simplified profile loader exists and whether regular loader can be used (natural_evolution_generator.py)
- Profile loading redundancy - loading profile twice in natural_evolution_generator.py
- Use regular profile loader and delete simplified version (natural_evolution_generator.py)
- Option expiration date hardcoded at 10 years, should pull from user profile (natural_evolution_generator.py)
- Load price projections from external source instead of no-change assumption (natural_evolution_generator.py) - 2 instances
- Forward reference in ProjectionResult needs documentation for simplest implementation (projection_state.py)
- Investment return rate hardcoded at 7%, should be user specified (projection_state.py)
- Search codebase systematically for other hardcoded tax values that should be in tax_constants.py (comprehensive audit needed)
- **Charitable giving refactor** - Move charitable_giving from profile-level to per-grant level within original_grants (see "Charitable Giving Per-Grant Refactor" section below)
- **Grant ID tracking in timeline** - Add grant_id column to equity_position_timeline.csv to track which grant each lot originated from (see "Grant ID Timeline Tracking" section below)
- **IPO timing configuration** - Add assumed_ipo field to profile for pledge expiration calculations (see "Comprehensive Output Improvements" section)
- **AMT credit carryforward** - Ensure first year uses profile carryforward values (see "Comprehensive Output Improvements" section)
- **NSO AMT adjustment bug** - Debug why NSO exercises show AMT adjustments (see "Bugs to Fix" section)
- **Transition timeline bug** - ISO marked as expiring when already exercised (see "Bugs to Fix" section)


### Immediate Priorities
**Partner on Real-World Scenarios** - Work with users on specific equity compensation scenarios to stress test the model end to end and provide feedback on accuracy and usability.

### E2E Testing Plan for Critical Financial Pathways
**High-Risk Areas Requiring E2E Tests:**

**Pledge Obligation & Company Match Tracking** (CRITICAL)
   - Risk: 3-year match window, company match not tracked, lost opportunities
   - Impact: Understated charitable impact, missed match deadlines, incorrect scenario comparison
   - Test Scenarios:
     * Sale creating 50% pledge with 3:1 match, verify total impact = 4x personal donation
     * Match window closing with partial fulfillment - verify lost match calculation
     * Multiple sales with different match ratios (3:1 vs 1:1)
     * Year 4 donation attempt - should fail with match window closed error
     * Verify summary_metrics includes total_charitable_impact
   - Specific Tests:
     * Sell 1000 shares at $100, 50% pledge, 3:1 match
       - Personal donation: $50,000 (500 shares)
       - Company match: $150,000
       - Total impact: $200,000
       - If only 250 shares donated by deadline: Lost match = $75,000
     * Verify CSV outputs show personal vs total impact
   - Validation: Ensure company match aggregates correctly across years

**ISO Disqualifying Disposition** (HIGH)
   - Risk: Complex date calculations (exercise + 2yr AND grant + 1yr)
   - Impact: Wrong tax treatment (ordinary income vs LTCG)
   - Test Scenarios:
     * Exercise and sell < 1 year (STCG + ordinary income)
     * Exercise and sell > 1 year but < 2 years from exercise (disqualifying)
     * Exercise and sell > 2 years from exercise AND > 1 year from grant (qualifying)
     * Edge case: Exactly 365 vs 366 days
   - Validation: Compare tax treatment against IRS Publication 525

**Cash Flow Viability** (CRITICAL)
   - Risk: Strategies requiring negative cash
   - Impact: Impossible-to-execute strategies
   - Test Scenarios:
     * Exercise costs exceeding available cash
     * Tax payments causing negative cash
     * Living expenses not covered
     * Sequence of actions depleting cash mid-year
   - Implementation: Add cash_flow_valid flag and warnings

**NSO Withholding Reconciliation** (MEDIUM)
   - Risk: Withholding ≠ actual tax owed
   - Impact: Surprise tax bills or phantom refunds
   - Test Scenarios:
     * High NSO exercise with supplemental withholding
     * Year-end true-up calculation
     * Estimated tax payment requirements
     * Refund vs additional payment due

**Implementation Priority:**
1. **Next**: Add pledge obligation E2E tests
2. **Then**: ISO disposition and cash flow validation tests
3. **Later**: NSO withholding reconciliation tests




### Charitable Giving Per-Grant Refactor

**Current Issue**: Charitable giving (pledge percentage and company match ratio) is currently stored at the profile level, but should be associated with individual grants based on employment timing.

**Background**: Different employees have different charitable programs based on when they joined:
- Earlier employees: 50% pledge with 3:1 match
- Newer employees: 25% pledge with 1:1 match
- Some employees: No pledge/match program available

**Proposed Structure**:
```json
"original_grants": [
  {
    "grant_id": "GRANT_001",
    "grant_date": "2020-01-01",
    "charitable_program": {
      "pledge_percentage": 0.50,
      "company_match_ratio": 3.0
    }
  }
]
```

**Implementation**: Part of Phase 4 - move charitable_giving from top-level to per-grant level.

### Grant ID Timeline Tracking

**Enhancement**: Add grant_id to equity_position_timeline.csv to track grant origins:
```csv
date,lot_id,grant_id,share_type,quantity,strike_price,lifecycle_state,tax_treatment
```

**Implementation**: Part of Phase 4 - enables proper charitable program tracking.

### Comprehensive Output Improvements Plan

**Goal**: Enable fully informed scenario comparisons by tracking all forms of value creation and destruction.

#### Value Tracking Framework

**1. Personal Net Worth Components**:
Assets:
- Cash position
- Investment balance (other (inc crypto) + investment growth)
- Equity value (vested exercised shares at current price)
- AMT credit value (full dollar amount of remaining accumulated credits)
- Charitable Deduction Carryfoward value (full dollar amount of remaining accumulated carryforward)
Liability:
- Unfulfilled pledge obligations (shares pledged but not yet donated)

**2. Charitable Impact Components**:
- Personal donations (shares donated × {recent tender price or FMV})
- Company match value (shares donated × match ratio × {recent tender price or FMV})
- Total charitable impact (personal + match)
- Lost match opportunity (expired match eligible share count × {recent tender price or FMV})

**3. Efficiency Metrics**:
- AMT credit utilization (credits used vs generated)
- Option expiration losses (value of expired in-the-money options)
- Pledge fulfilled (total shares matched vs original total pledge)
- Charitable deduction utilization (deductions used vs expired)

- Add recently expired pledge obligations that have passed deadlines, either from the 3 year post sale constraint or the 1 year post IPO constraint.

#### CSV Field Enhancements

**action_summary.csv**:
- **Add**: `lot_options_remaining` - unexercised options after action
- **Add**: `lot_shares_remaining` - exercised shares after action
- **Add**: `current_share_price` - FMV at action time
- **Add**: `action_value` - dollar value of action (shares × price)

**annual_summary.csv**:
- **Add**: `options_exercised_count` - quantity exercised this year
- **Add**: `shares_sold_count` - quantity sold this year
- **Add**: `shares_donated_count` - quantity donated this year
- **Add**: `amt_credits_generated` - new AMT credits this year
- **Add**: `amt_credits_consumed` - AMT credits used this year
- **Add**: `amt_credits_balance` - ending AMT credit balance
- **Add**: `charitable_total_impact` - personal donations + any company match, if applicable
- **Add**: `pledge_shares_expired` - count of shares that passed their pledge obligation window expiration before being donated
- **Add**: `expired_option_count` - quantity of expired options
- **Rename**: `expired_option_loss` - value of expired options (was: opportunity cost)

**portfolio_comparison.csv**:
- **Add**: `charitable_personal_value` - total personal donations $
- **Add**: `charitable_match_value` - total company match $
- **Add**: `charitable_total_impact` - total charitable value $
- **Add**: `pledge_fulfillment_rate` - percentage of pledged shares that were donated (up to 100% of fraction of total shares that were earmarked for donation)
- **Add**: `outstanding_amt_credits` - ending unused AMT credit balance $
- **Add**: `pledge_shares_expired` - share of lost match opportunities
- **Add**: `expired_charitable_deduction` - unused deductions that expired $
- **Add**: `expired_option_count` - share of lost match opportunities
- **Add**: `expired_option_loss` - total value of expired options (value at time of expiration, if in-the-money)

**comprehensive_cashflow.csv**:
- **Add**: `starting_cash` - beginning cash balance
- **Add**: `other_investments` - includes a bucket for crypto or other investments

#### Profile Configuration Enhancements

**Add to user profile (and placeholders to template and demo)**:
```json
"charitable_giving": {
    "pledge_percentage": 0.5,
    "company_match_ratio": 3.0,
    "post_sale_donation_window_months": 36,
    "assumed_ipo": "2033-03-24",
    "post_ipo_donation_window_months": 12
}
```

**Remove from user profile**:
- Delete entire `market_assumptions` section (lines 199+) and decision parameters.
- Inclused removing price scenarios from profile in favor of price_scenarios.json already in use
- Investment return rate remains hardcoded at 7% pending future fix

#### Warning System Enhancements

**1. Pledge Obligation Warnings**:
- **3-year window**: Warn expired due to 3 years post-sale without donation
- **IPO+1 year deadline**: Warn when expired due to remaining pledge obligations that have expired 1 year post-IPO

**2. Option Expiration Warnings** (implemented):
- Show option count and dollar value of potential loss

**3. AMT Credit Warnings**:
- Calculate: final_year_amt_credits / final_year_amt_consumption > 20
- If true, warn: "AMT credits of $X will take >20 years to consume at current rate of $Y/year"
- Implementation: In projection_output.py summary section

**4. Charitable Deduction Warnings**:
- Track 5-year carryforward expiration
- Warn when deductions have expired unused

#### Specific Improvements

**pledge_obligations.csv overhaul**:
- Primary unit: shares. Secondary unit: dollars.
- Track by lot: grant_id, lot_id, shares_sold, shares_pledged, shares_donated, shares_outstanding
- Match tracking: match_ratio, match_value_earned, match_value_potential, match_window_expiry
- Dollar values as secondary fields with price assumptions clearly stated
- **Calculation logic**:
  - **Current implementation**: In `projection_calculator.py`, when processing SELL actions:
    - Creates pledge via `PledgeCalculator.calculate_obligation()` in `pledge_calculator.py`
    - Currently uses hardcoded 3-year window: `deadline = sale_date + timedelta(days=pledge_window_years * 365)`
  - **Required changes** to `PledgeCalculator.calculate_obligation()`:
    - Add parameter `assumed_ipo: Optional[date]`
    - Change deadline calculation to: `deadline = min(sale_date + timedelta(days=3*365), assumed_ipo + timedelta(days=365))`
    - Pass `assumed_ipo` from UserProfile through projection_calculator
  - **FIFO tracking**: Already implemented in `PledgeState.discharge_donation()` in `projection_state.py`
  - **Expiration checking**: Add to `PledgeState.process_window_closures()` to mark expired when `current_date > match_window_closes`

**holding_period_tracking.csv replacement**:
- Create new `generate_holding_milestones_csv()` in `projection_output.py`
- For each lot, calculate milestone dates based on current state:
  - **Granted not vested**: option_expiration_date (expiration_date from user_profile)
  - **Vested not exercised**: option_expiration_date, ipo_pledge_deadline (assumed_ipo + post_ipo_donation_window_months)
  - **Exercised**: ltcg_date (exercise_date + 1 year), ipo_pledge_deadline
  - **Sold**: pledge_window_expiry (min(sale_date + post_sale_donation_window_months, assumed_ipo + post_ipo_donation_window_months))
  - **Donated**: deduction_expiry (donation_year + 5 years, EOY)
  - **ISO specific**: qualifying_disposition_date (max(grant_date + 1 year, exercise_date + 2 years))
- Include countdown years + days to each milestone as of the scenario end date for which this csv is being generated.

**Donation Value Calculation**:
- **Current implementation**: Donation pricing happens in `portfolio_manager._determine_action_price()`:
  - Currently only checks tender price for SELL actions (within 30 days)
  - For DONATE actions, uses projected price from price_projections
- **Required changes** to `portfolio_manager._determine_action_price()`:
  - Move tender price check before the action type check
  - Expand for donations specifically to change tender date check from 30 days to the most recent tender from the same calendar year:
    ```python
    if tender_date and tender_price:
        tender_date_obj = date.fromisoformat(tender_date)
        # Check if same calendar year
        if action_date.year == tender_date_obj.year:
            return tender_price
    ```
  - Keep the 30 day check for SELL actions, and use the same-year check for DONATE actions.
  - Add logging to indicate which price was used: "Using most recent same-year tender price" vs "Using projected FMV"
- **Price source tracking**: Add `price_source` field to donation records in CSV outputs
  - Add field `price_used` to donation records indicating "tender" or "fmv"
- Clear documentation of which price was used in CSV outputs

**Scenario Duration**:
- Default to 15 years for complete charitable deduction lifecycle
- Year 1 (2025): Current year
- Year 9 (2033): Assumed IPO (March 24, 2033 for user_profile.json)
- Year 10 (2034): Final match-eligible donation window (IPO + 1 year), initial charitable deduction consumption
- Years 11-15: Charitable deduction carryforward consumption period
- Year 16 (2040): First year where all carryforward deductions have expired
- Run 16 years to see final state after all expirations

#### Bugs to Fix

**1. NSO AMT Adjustment** (scenario 036, 2025-06-24):
- NSO exercise showing $27,838.72 AMT adjustment
- Debug in `iso_exercise_calculator.py`:
  - Add logging at AMT adjustment calculation line
  - Verify `share_type` is correctly identified as NSO not ISO
  - NSOs should have zero AMT adjustment by definition
  - Check if bargain element is being incorrectly added to AMT base
  - Trace through `calculate_exercise_tax()` with debug prints
- Expected: NSO exercises should not create AMT adjustments

**2. Transition Timeline Bug** (scenario 036, row 7):
- ISO marked as "expiring" when already exercised
- Fix lifecycle state tracking logic

**3. AMT Credit Initialization**:
- In `annual_tax_calculator.py`:
  - Year 1: Use `user_profile.tax_situation.carryforwards.amt_credit`
  - Years 2+: Use previous year's ending AMT credit balance
- Verify credits flow properly through YearlyState objects
- Test with both zero and non-zero initial AMT credit. Try demo_profile.json

#### Implementation Phases

**Phase 1: Profile & Data Model Updates** (Foundation)
1. Add `assumed_ipo` field to profile with 2033-03-24 default
2. Remove `market_assumptions` section from all profiles
3. Add grant_id tracking to ShareLot and timeline CSV
4. Update profile loader to handle new fields
5. No migration script - test-driven one-shot rewrite approach

**Phase 2: Value Tracking Enhancements** (Core Metrics)
1. Enhance annual_summary.csv with all new fields
2. Update portfolio_comparison.csv with comprehensive metrics
3. Add AMT credit tracking and warnings
4. Implement charitable impact calculations (personal + match)

**Phase 3: Warning System** (User Guidance)
1. Implement pledge obligation expiration warnings
2. Add IPO+1 year deadline warnings (LOUD)
3. Create AMT credit consumption trajectory warnings
4. Add charitable deduction expiration tracking

**Phase 4: Charitable System Refactor** (Complex)
1. Move charitable_giving to per-grant level
2. Implement grant-based pledge tracking
3. Update pledge_obligations.csv with share-based tracking
4. Add match window enforcement logic

**Phase 5: Bug Fixes & CSV Cleanup**
1. Fix NSO AMT adjustment bug
2. Fix transition timeline expiring/exercised bug
3. Replace holding_period_tracking.csv with simplified version
4. Consolidate CSV generation architecture

**Phase 6: Testing & Validation**
1. Create E2E tests for pledge obligations
2. Test 15-year scenarios for full lifecycle
3. Validate all warning triggers
4. Run comprehensive test suite before and after changes

**Priority Order**: Start with Phase 1-2 for immediate value, then Phase 5 for bug fixes, followed by Phase 3-4 for enhanced functionality.

### CSV Generation Architecture Consolidation Plan

**Current Architecture Issues**:
1. CSV generation split between `projection_output.py` and `detailed_materialization.py`
2. Multiple entry points with inconsistent CSV generation
3. `run_scenario_analysis.py` doesn't generate CSVs at all

**Current Split**:
- `projection_output.py`: Core financial CSVs (cashflow, tax, equity, charitable, pledge)
- `detailed_materialization.py`: Analysis CSVs (action_summary, annual_summary)

**Consolidation Plan**:

**Phase 1: Unify CSV Generation Functions**
1. Move `DetailedMaterializer` class from `detailed_materialization.py` to `projection_output.py`
2. Rename methods for consistency:
   - `save_action_level_csv()` → `save_action_summary_csv()`
   - `save_annual_summary_csv()` → keep as is
3. Update `save_all_projection_csvs()` to directly call these methods instead of delegating to `materialize_detailed_projection()`

**Phase 2: Standardize Entry Points**
1. Create `generate_complete_csv_suite()` as the single entry point
2. Update all callers:
   - `portfolio_manager.py`: Already uses `save_all_projection_csvs()`
   - `run_scenario_analysis.py`: Add CSV generation after projection
   - Test files: Use the unified entry point

**Phase 3: Clean Up Architecture**
1. Delete `detailed_materialization.py` after moving all functionality
2. Consolidate duplicate CSV field calculations
3. Standardize CSV field naming conventions

**Benefits**:
- Single source of truth for all CSV generation
- Consistent output regardless of entry point
- Easier to maintain and test
- Clear data flow from ProjectionResult → CSVs

**Migration Strategy**:
1. Add deprecation notices to `detailed_materialization.py`
2. Create parallel implementation in `projection_output.py`
3. Update callers one by one with tests
4. Remove old implementation once all callers migrated
