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

# Summary instructions

When you are using compact, please write a comprehensive and detailed summary, include in your summary 1) what the original kickoff message was, 2) what task we set about solving originally, 3) any progress made or problems run into on that main task, 4) any diversions pursued and how deep down the tree we might be, 5) any tests run in the history that appeared to be failing 6) any tests that need to be run again now to confirm their state, 7) all files touched or edited this session along with an explaination of why and what the goal was, 8) any files that we are planning on touching but haven't edited yet, and the plans for these files, 9) the entire context of the users last 10 messages to you, along with a summary of what was achieved or problems ran into for each of those messages, 10) a list of tips of working with this codebase such as paths to specific files or instructions the user has recently given to you that you previously weren't doing so you can remember to keep doing them immediately after, 11) project basis such as the commands we frequently run 12) example files we should make sure to read from to understand key formatting or expected structure of the files we are likely to be working on in this upcoming session.


### Code Changes
**Edit atomically** - Make isolated, in-place edits. Read files before editing. Use `mv` to move files
**Respect boundaries** - Each file has a specific purpose. Don't mix concerns across files
**Test before and after** - Run tests before changes and verify they pass after
**Understand before removing** - Investigate why code exists before deleting it
**Check changed files** - When notified "These files changed since last read", immediately read the changed files to understand what's different before proceeding with any analysis or modifications

### Documentation & State
**Document as you go** - Update docs inline with changes, not later. No time estimates in plans or dates in changelogs.
**Track state here** - Don't maintain separate todo lists. After commits, ask "what are the next steps?"
- When completing a feature, prior to drafting a commit, add a short 5 bullet summary of what was completed to docs/CHANGELOG.md, while ensuring no personal, user, or sensitive data is mentioned.
- After completing and documenting a feature (including removing anything unnecessary from CLAUDE.md and adding the short summary to docs/CHANGELOG.md, draft a commit for the user to review and approve, ensuring no sensitive or personal information is included in the commit message especially from the user profile details.

### Design Approach
**Keep it simple** - Aim for E2E validation over complex designs. Ask about abstraction preferences
**Use discovery questions** - Ask about constraints and risk tolerance rather than assuming

## Technical Standards
- python3 (don't try pytest)
- Decimal for monetary precision
- ISO 8601 dates
- Comprehensive docstrings with examples
- Error messages user-friendly and actionable
- No external dependencies

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
- **Test-Driven Bug Fixes**: When a bug is found, first create a failing test that demonstrates the bug, then implement the fix to make the test pass

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

## Current Status & Backlog

### Project Status
**Project Status**
Production-ready core with comprehensive test coverage.
Main calculators operational, handling complex scenarios including tender offers, ISO exercises,
charitable donations with basis elections, multi-year projections, Federal and California
charitable deductions and carryforward management with both fmv basis and basis election support,
and complete company match tracking with 3-year match window enforcement. Grant-specific charitable
programs enable accurate modeling of different pledge percentages and match ratios per grant.
Company match tracking provides full visibility into charitable leverage with proper timing validation,
lost opportunity tracking, and comprehensive CSV reporting for strategic planning.

IPO pledge obligation feature fully implemented with automatic calculation of remaining total pledge
obligations due 3 year after any liquidity event such as tender or IPO date. Includes FIFO donation tracking, chronological milestone sorting, and enhanced CSV outputs with proper grant data loading pipeline.

Comprehensive output improvements complete with enhanced CSV tracking, warning systems,
grant-specific pledge obligations, and cleaned milestone tracking. All tests passing with full E2E validation.

### Project History
See CHANGELOG.md for complete feature history and implementation details.


### Next Steps & Readiness

**Immediate Opportunities:**
- Real-world scenario validation with users to stress-test edge cases

### Known Issues
- CA AMT credit tracking not implemented (see TODO comment in annual_tax_calculator.py for future implementation when use cases arise)
- Need to add an E2E test validating that a large NSO exercise drives up income
- Some details are only loaded from the first equity grant. If you have multiple grants, the first grant's charitable program is used may be used for all grants. A potential extension is to allow iterating through each grant and loading and processing all details separately.

### Inline TODOs in Code
(Search for each of these TODOs when fixing, then remove them from the comments after being resolved)
- Option expiration date hardcoded at 10 years, should pull from user profile (natural_evolution_generator.py)
- Explain why simplified profile loader exists and whether regular loader can be used (natural_evolution_generator.py)
- Load price projections from external source instead of no-change assumption (natural_evolution_generator.py) - 2 instances
- Forward reference in ProjectionResult needs documentation for simplest implementation (projection_state.py)
- Investment return rate hardcoded at 7%, should be user specified (projection_state.py)

### Recent TODOs & Action Items
- **AUDIT NEEDED**: Review cost_basis field usage across profile files and ensure correct flow/calculation for both regular and AMT tax on subsequent sale events. Verify ISOs use strike price as cost basis for regular tax but FMV at exercise for AMT calculations
- TODO: audit all fields in user_profile to find those not used by many downstream calculations and propose a comprehensive reduction plan to simplify this schema
