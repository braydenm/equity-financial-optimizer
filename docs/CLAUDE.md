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
- Option expiration handling needs natural state transition implementation
- Ordering rules for charitable deductions could be more explicit
- Action summary CSV incorrectly shows "iso_exercise_calculator" for all exercises (display issue only, calculations are correct)

### Inline TODOs in Code
(Search for each of these TODOs when fixing, then remove them from the comments after being resolved)
- Basis election 50% limit hardcoded, should pull from tax_constants.py (annual_tax_calculator.py)
- Option expiration tracking not implemented in projection calculator
- Lot ID parsing in pledge obligations assumes specific underscore convention
- Tax limit percentages in CSV generation should differentiate federal vs state
- Forward reference in ProjectionResult needs documentation
- Price projections loading from external source not implemented (natural_evolution_generator.py)
- Redundant profile loading check needed in natural evolution generator
- Use regular profile loader and delete simplified version (natural_evolution_generator.py)
- AMT credit carryforward timing - confirm which year the credits apply to (projection_calculator.py)
- Improve documentation for basis election logic (projection_calculator.py)
- Confirm whether investment growth should be considered liquid cash (projection_calculator.py)
- Rename VESTED_ISO/VESTED_NSO to ISO/NSO consistently upstream (projection_output.py)

### Immediate Priorities
**Partner on Detailed Scenarios** - Work with user on specific equity compensation scenarios to stress test the model end to end and provide feedback on accuracy and usability.

**Option Expiration Implementation** - Implement natural expiration through lifecycle state transitions as detailed in the plan below.

### Option Expiration Implementation Plan

**Overview**: Implement natural option expiration through lifecycle state transitions, ensuring expired options are properly tracked and removed from exercisable inventory while maintaining audit trail.

**1. Data Model Updates**
- Add `expiration_date` to ShareLot model (already exists in grants, needs to flow to lots)
- Add new lifecycle state: `EXPIRED` to LifecycleState enum
- Add `ExpirationEvent` class to track expiration transitions:
  ```python
  @dataclass
  class ExpirationEvent:
      lot_id: str
      shares_expired: int
      expiration_date: date
      original_grant_date: date
      strike_price: float
      was_exercisable: bool  # Track if expired while vested
  ```

**2. Natural State Transition Implementation**
- Update `process_natural_vesting()` in natural_evolution_generator.py to also check expiration:
  ```python
  def process_natural_transitions(lots, current_year):
      vesting_events = []
      expiration_events = []

      for lot in lots:
          # Existing vesting logic...

          # Check for expiration
          if lot.expiration_date and lot.expiration_date.year == current_year:
              if lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED:
                  lot.lifecycle_state = LifecycleState.EXPIRED
                  expiration_events.append(ExpirationEvent(...))
              elif lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                  lot.lifecycle_state = LifecycleState.EXPIRED
                  expiration_events.append(ExpirationEvent(...))

      return vesting_events, expiration_events
  ```

**3. Projection Calculator Updates**
- Update YearlyState to include expiration_events (already has placeholder)
- Modify evaluate_projection_plan to process expirations:
  - Remove expired shares from exercisable inventory
  - Track opportunity cost (expired in-the-money options)
  - Update equity value calculations to exclude expired lots

**4. CSV Output Enhancements**
- **transition_timeline.csv**: Ensure expiration events show up in the Expiring state transition aggregation
- **state_timeline.csv**: Ensure expiration events are aggregated into the Expired state category per year
- **action_summary.csv**: Include a 'let expire' event type for any lots that expire. Are there any implications for any of the other fields in that file?
- **holding_period_tracking.csv**: Remove any lots once expired


**5. Calculator Integration**
- No changes needed to tax calculators (expired options have no tax impact)
- Update portfolio valuation to exclude expired lots
- Add metrics for tracking:
  - Total shares expired by year
  - Opportunity cost (for vested options that expired ITM) with warning

**6. Testing Approach**
- Create test_option_expiration.py with scenarios:
  - Options expiring while unvested (no opportunity cost)
  - Options expiring while vested OTM (no opportunity cost)
  - Options expiring while vested ITM (calculate opportunity cost)
  - Mixed portfolio with staggered expiration dates
- Add expiration scenarios to demo data:
  - 905_expiring_options.json - Options expiring across multiple years
  - Update demo_profile.json grants to include expiration_date

**7. Implementation Order**
1. Add expiration_date to ShareLot and ensure it flows from grants
2. Add EXPIRED lifecycle state and ExpirationEvent class
3. Update natural transition processing to handle expirations
4. Update ProjectionCalculator to process expiration events
5. Add CSV outputs for expiration tracking
6. Create comprehensive tests
7. Update documentation and examples

**Success Criteria**
- Options automatically expire on expiration date
- Expired options removed from exercisable inventory
- Clear tracking of expiration events and opportunity costs
- All existing tests continue to pass
- New expiration-specific tests pass
- CSV outputs properly reflect expired options

### Completed Features

**Comprehensive Cash Flow Accuracy** ✓
- Updated ProjectionCalculator to include all income sources (spouse W2, interest, dividends, bonuses)
- Added living expenses from monthly_cash_flow section
- Implemented tax withholdings vs gross tax liability calculation
- AMT credit carryforward usage from tax_situation now flows through projections
- Investment growth modeling for taxable_investments implemented
- Accurate initial cash position from liquid_assets
- Enhanced CSV outputs and text summaries with realistic cash projections

**Base Withholding Implementation** ✓
- Added base_federal_withholding and base_state_withholding to UserProfile dataclass
- Implemented intelligent withholding calculation that uses base rates for future years
- Added supplemental withholding for stock compensation (NSO exercises, RSU vesting)
- Supplemental rate combines federal (22%), CA (10.23%), Medicare (1.45%), and CA SDI (1.2%)
- Updated all profile loaders (portfolio manager, scenario loader, natural evolution generator)
- Added base withholding example to demo_profile.json
- Solves problem of inflated withholding from stock exercise years affecting all projections
- Backward compatible - works without base withholding fields using existing withholding amounts

**NSO Bargain Element Fix** ✓
- Fixed portfolio_manager._determine_action_price() to return FMV for exercises instead of strike price
- NSO exercises now correctly calculate bargain element (FMV - strike price)
- Supplemental withholding automatically applied to NSO ordinary income (~34.88%)
- ISO exercises continue to work correctly with AMT adjustments
- All sales and donations continue using projected prices correctly
- Added test_nso_exercise_withholding.py to verify NSO withholding calculations
- All existing tests continue to pass
