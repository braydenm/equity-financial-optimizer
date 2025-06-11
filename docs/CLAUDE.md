# CLAUDE.md - AI Context for Equity Financial Optimizer
# Instructions for Claude Code

You are helping set up a financial planning system for equity compensation management. This project is built using claude code who tracks implementation state in an orchestration file while we proceed through building out the specialized calculators are built independently and eventually integrated via MCP.

## Important: Initial Response
When the user starts a conversation with "begin" or similar initialization command, acknowledge that you have loaded the CLAUDE.md instructions and briefly state the current project context.

## Project Structure
Current simplified structure:
```
equity-financial-optimizer/
├── README.md
├── docs/
│   ├── CLAUDE.md (this file)
│   ├── PROJECT_SPEC.md
│   ├── TECHNICAL_ARCHITECTURE.md
│   └── reference/
│       ├── amt-breakeven-calculator.py
│       ├── equity-donation-matching-faq.md
│       ├── tender-offer-may-2025.md
│       └── pledge-calculator-*.{html,js,css}
├── data/
│   ├── user_profile_template.json
│   ├── user_profile.json
│   ├── market_assumptions/
│   │   └── price_scenarios.json
│   └── user_backgound_info.txt
├── scenarios/
│   ├── README.md
│   ├── natural_evolution/
│   │   └── actions.csv
│   ├── exercise_all_vested/
│   │   └── actions.csv
│   └── tender_and_donate/
│       └── actions.csv
├── portfolios/
│   └── tax_strategies.json
├── calculators/
├── engine/
├── projections/
├── loaders/
├── tests/
└── examples/
```

## Key Implementation Notes

1. **Stateless Design**: All calculators must be pure functions with no persistent state
2. **Type Hints**: Use Python type hints throughout for clarity
3. **No External Dependencies**: Stick to standard library + numpy/pandas only
4. **MCP Integration**: Each calculator should have a wrapper (when needed)

## Testing Requirements

Each calculator must include:
- Unit tests with known values from pledge calculator
- Integration tests with user profile data
- Performance benchmarks (target: <100ms per calculation)
- Validation against reference implementations

## Code Style

- Use descriptive variable names matching financial terminology
- Include comprehensive docstrings with examples
- Add inline comments for complex tax calculations
- Follow PEP 8 conventions

## Project Overview
The Equity Financial Optimizer is a modular toolkit of financial calculators designed for equity compensation and donation planning scenarios. Each calculator is built as a standalone module that can interact with other calculators and be exposed via MCP (Model Context Protocol) or other integration methods.

## Architecture Principles
1. **Modular Design**: Each calculator is a self-contained module with clear inputs/outputs
2. **Composability**: Calculators can call each other to build complex scenarios
3. **Integration-Ready**: All calculators expose standardized interfaces for MCP/API usage
4. **Type Safety**: Strong typing for all financial calculations
5. **Testability**: Each calculator has comprehensive unit tests

## Key Components
- `calculators/`: Individual calculator modules (equity, donation, tax optimization, etc.)
- `engine/`: Core scenario planning engine
- `tests/`: Test files for all calculators
- `examples/`: Example usage scenarios

## Technical Decisions
- Language: Python 3
- Testing Framework: pytest (when we get there)
- Documentation: Inline documentation + generated API docs
- Financial Precision: Decimal types for all monetary calculations

## Coding Standards
- Clear function names that describe financial operations
- Comprehensive error handling for edge cases
- All monetary values include currency designation
- Date handling follows ISO 8601 standards

## Important Context for Claude
- Always consider tax implications in calculations
- Ensure calculations can handle multiple currencies
- Prioritize accuracy over performance in financial calculations
- Each calculator should validate inputs rigorously
- Keep audit trails for all calculations

## Integration Notes
- MCP tools should follow the standard MCP schema
- Each calculator exposes a consistent API interface
- Error messages should be user-friendly and actionable

## Business Rules & Constraints

1. **Tax Optimization Priority**: Always prioritize long-term capital gains treatment
2. **STCG Holding Period**: MANDATORY - Cannot sell or donate shares until 12 months (LTCG status)
3. **Tender Offers**: Annual tender offers in May with ~10% premium
4. **Cashless Tender**: Available for vested options during tender offers only
5. **Donation Matching**: Company matches 3:1 up to certain limits
6. **Donation Timing**: Only donate LTCG shares (get full FMV deduction)
7. **Exercise Timing**: Consider AMT implications for ISOs
8. **Vesting Schedules**: Monthly vesting with 1-year cliff typical

## Working style
- Don't start drafting the content for new markdown docs without proposing that you are going to create a new one.
- Keep very simple iterations aiming at E2E validation rather than overspecifying or overdesigning for things that haven't been validated needs.
- Don't maintain a separate todo list outside of this file. This means don't perform the Read Todos or Update Todos function.
- make your edits atomic and isolated. prefer editing files in place, rather than overwriting with entire changes (unless you are editing a substantial fraction of that entire file. Read first to avoid errors.)
- use mv to move files instead of rewriting them
- document your updated state frequently in this while remaining focussed on the overarching core goal, don't rabbit hole.
- IMPORTANT: After every commit, ask "what are the next steps?" and ensure this file has sufficient detail for a fresh Claude instance to continue the work
- When a mistake is made, identify if there's an existing principle that should have prevented it. If not, propose a new principle to prevent similar mistakes in the future
- **Edit Reversion Strategy**: At the start of each Claude response that will modify files, create a single git stash containing all files that will be touched: `git stash push -m "undo-last-turn" -- file1.py file2.md ...`. This provides a quick reversion point if any changes in that turn are unwanted. The stash is overwritten on each new turn that modifies files, maintaining only the most recent undo point. To revert: `git stash pop`
- **Verify Before Committing**: Always review modified files against their intended purpose before committing
- **Respect File Boundaries**: Each file has a specific purpose - don't mix concerns across files
- **No Time Estimates in State Tracker**: When updating the project plans, don't include day/week estimates for work items - focus on what needs to be done, not how long it might take

## Model
- Default model: claude-opus-4 (currently claude-opus-4-20250514)
- Please ensure you are using claude-opus-4 every time during project initialization
- If unsure about current model, ask the user to verify with the /model command

## Tracking State Principles
- This file also tracks our implementation journey and current position
- Under "Completed": List major milestones and the key insights/decisions that got us there
- Focus on capturing the "why" behind decisions, not just the "what"
- Keep it high-level - implementation details belong in code or TECHNICAL_ARCHITECTURE.md
- DO NOT record specific calculation outputs or scenario results - only architectural decisions and implementation progress
- Scenario outputs belong in example files or test results, not here
- DO NOT record routine verification activities (Python version checks, file existence, test runs)
- Only track stateful changes to the codebase structure and design decisions

## Workflow Principles
1. Begin with Goal and Context Clarification, Not Solution Proposal
   Explanation: Always start by asking "What are you trying to achieve in this session?" and "What are your current pain points?" before suggesting any next steps. This prevents premature solutionizing and ensures alignment on objectives.

2. Distinguish Between "Building Forward" and "Cleaning Up" Early
   Explanation: Ask explicitly whether the focus is on adding new functionality or improving existing code quality. These require fundamentally different approaches and the choice significantly impacts the session strategy.

3. Validate Current System Capabilities Before Proposing Changes
   Explanation: Before suggesting improvements or new features, systematically analyze what the current system actually does well vs. poorly. Run existing tests and examples to understand baseline functionality.

4. Present Architectural Trade-offs, Not Just Solutions
   Explanation: When proposing technical approaches, frame them as "Option A vs Option B" with clear trade-offs rather than presenting a single recommended path. This enables informed decision-making.

5. Ask About Abstraction Level Preferences Before Implementation
   Explanation: When designing systems, explicitly ask whether the human prefers prescriptive (pre-defined scenarios) vs. composable (building blocks) approaches. This prevents over-specification of the wrong abstraction.

6. Use "Pause Points" for Major Direction Changes
   Explanation: Before executing any large-scale changes (like archiving code or restructuring), pause to confirm the approach and get explicit authorization. Break large tasks into atomic steps with approval gates.

7. Investigate "Why" Behind Existing Code Before Removal
   Explanation: When cleaning up apparent technical debt, first understand why code exists and what functionality it provides. Legacy systems often contain important capabilities that aren't immediately obvious.

8. Scope Enhancement Work Before Starting Implementation
   Explanation: When proposing to enhance existing systems, provide concrete effort estimates and explicitly ask whether to proceed with implementation or continue planning. Avoid building unless there's clear value demonstrated.

9. Verify Test Coverage Before and After Major Changes
   Explanation: Always run existing tests before making changes and verify they still pass after changes. This ensures no regressions are introduced during refactoring or cleanup work.

10. Document Architectural Decisions as You Go
    Explanation: When making structural changes, update documentation simultaneously rather than deferring it. This ensures the reasoning behind decisions is captured while it's fresh and clear.

11. Ask "What Would Success Look Like?" Before Starting Work
    Explanation: Establish clear success criteria for the session early on. This helps maintain focus and provides a clear endpoint for the work.

12. Use Discovery Questions to Understand Constraints
    Explanation: Ask about constraints like "How aggressive should we be with cleanup?" or "What are you comfortable removing?" rather than making assumptions about risk tolerance.

# State - Implementation Progress

### Completed ✅
- Project setup and initial commit
- Documentation structure established
- Simplified architecture from overspecified to pragmatic
- Established share timeline as core data model
- Created working tender_decision calculator with real data
- Validated MVP approach: direct JSON reading vs complex objects
- Enhanced tender calculator with multiple scenarios and formatted output
- Added per-lot tax breakdown to understand LTCG vs STCG impact
- Created comprehensive tender_analysis example showing decision factors
- Built advanced tender calculator with specific lot selection capabilities
- Added lot optimization to minimize tax for target proceeds
- Implemented side-by-side comparison of lot selection strategies
- Created tax_estimator.py with comprehensive AMT calculations:
  - Handles both federal and California AMT
  - Finds breakeven points before triggering AMT
  - Tracks AMT credits generated
  - Validated against reference calculator outputs
- Implemented scenario_planner.py for end-to-end optimization:
  - Orchestrates tender decisions and ISO exercises
  - Evaluates multiple scenarios with cash flow analysis
  - Compares trade-offs between liquidity and donation impact
  - Provides detailed breakdowns and recommendations
- Created MVP dataflow examples:
  - Complete flow showing all standard scenarios
  - Deep dive analysis for specific strategies
  - Removed company-specific references for generic use
- Started tender calculator refactor (Phase 1-2 complete):
  - Created unified TenderCalculator with pure calculation logic
  - Built TenderStrategyGenerator with 7 different selection strategies
  - Implemented strategy discovery pattern (optimal emerges from comparison)
  - Added evaluate_tender_strategies() to scenario planner
  - Created comprehensive tests for new components
  - Demonstrated how "tax optimal" is discovered, not predetermined
- Analyzed donation impact requirements:
  - Discovered oversimplified donation calc in wrong place (tender calculator)
  - Studied sophisticated pledge calculator reference implementation
  - Created comprehensive DONATION_CALCULATOR_PLAN.md
  - Identified complex AGI limitations, carryforward rules, and multiplier calculations
  - Removed incorrect implementation to prepare for proper calculator
- Completed tender calculator refactor (All phases complete):
  - Phase 1-2: Created new tender_calculator.py and tender_strategy_generator.py
  - Phase 3: Added migration layer for backward compatibility
  - Phase 4: Removed deprecated files and updated documentation
  - Architecture now follows clean separation: pure calculations → strategy generation → orchestration
  - Strategy discovery pattern fully implemented (tax optimal emerges from comparison)
  - All tests passing with new architecture
- Removed migration layer completely:
  - Updated all tests to use new API directly
  - Updated all examples to use new components
  - Deleted tender_migration.py (no longer needed)
  - Verified all tests still pass without migration utilities
- Completed calculator renaming for clearer taxonomy:
  - `tax_estimator.py` → `iso_exercise_calculator.py` (ISO exercise AMT calculations)
  - `tender_calculator.py` → `share_sale_calculator.py` (share sale capital gains)
  - Updated all imports and class names throughout codebase
  - Renamed test files to match new calculator names
  - All tests passing with new names
- Cleaned up examples to use API directly:
  - Removed unnecessary recalculation in scenario_deep_dive.py
  - Examples now demonstrate direct API usage without helper functions
  - Test helper function documented and kept in test file (test-specific logic)
  - All 5 example files tested and working
- Implemented share donation calculator:
  - Created `share_donation_calculator.py` with comprehensive donation calculations
  - Handles AGI limitations (30% stock, 50% cash), carryforward rules, company match
  - Built `donation_strategy_generator.py` with 7 different strategies
  - Integrated with scenario planner through `evaluate_donation_strategies()`
  - Created `donation_strategy_discovery.py` example showing real usage
  - Validated calculations against pledge calculator reference
  - Handles field name variations between user profiles
  - Strategy discovery pattern: optimal donation approach emerges from comparison
- Implemented v2.0 data contract:
  - Created comprehensive `DATA_CONTRACT.md` defining canonical profile format
  - Built `migrate_profile.py` utility to convert v1.x profiles to v2.0
  - Eliminated all conditional field checking throughout codebase
  - Standardized field names: `equity_position` (not `company_equity_position`),
    `ordinary_income_rate` (not `total_ordinary_income_rate`),
    `ltcg_rate` (not `total_ltcg_rate`), `shares` (not `shares_available`)
  - Updated all components to use v2.0 fields directly: scenario_planner.py,
    donation_strategy_generator.py, tender_strategy_generator.py, share_sale_calculator.py
  - Migrated all test data and examples to v2.0 format
  - All tests passing with simplified field access patterns
  - Created clean `profile_template_v2.json` as reference implementation
- Completed Agent-Driven Lifecycle Planning MVP:
  - Built `ShareLotLifecycle` data structure representing complete action plans from grant to disposition
  - Implemented `LifecycleCalculator` that evaluates full multi-year scenarios using existing calculators
  - Created working `mvp_lifecycle_demo.py` showing complete E2E functionality
  - Results format optimized for decision making with timeline views and cash flow analysis
  - Proven architecture: AI agents generate complete "screenplays", calculators evaluate them deterministically
  - Successfully integrates ISO exercise (AMT), share sales (capital gains), and donations (matching/deductions)
  - Shows clear trade-offs between liquidity needs and donation impact maximization
- Completed CSV Output and Real Data Integration:
  - Built `csv_lifecycle_analysis.py` that reads from user_profile.json v2.0 data contracts
  - Added structured CSV/table output formats for lifecycle analysis results
  - Created three output formats: strategy summary, detailed actions, yearly timeline
  - Saves results to CSV files for further analysis and decision making
- Completed Equity Position Timeline Architecture:
  - Built `equity_position_timeline_generator.py` creating clean input-focused CSV structure
  - Added hardcoded `vesting_calendar` to user_profile.json for precise control over vesting events
  - Created `equity_position_timeline.csv` with time-accurate base inventory of all share lots
  - Serves as foundation for scenario generation - base inventory without strategies
- Completed Calculator Cleanup & Composability (Phase 0):
  - Removed non-composable functions: `compare_donation_strategies()` (not suitable for scenario-based planning)
  - Commented out unused functions for future use: `find_amt_breakeven()`, `calculate_multiyear_optimization()`, `calculate_cost_basis_election_benefit()`
  - Enhanced calculator composability: automatic validation in `calculate_tender_tax()`, unified `calculate_donation()` function handles both cash and shares
  - Cleaned up project structure: removed empty `utils/` and `.ropeproject/` directories
  - All tests passing with improved validation and unified donation interface
  - Completed Portfolio-Based Scenario System:
    - Built data-driven scenario architecture: scenarios defined in CSV files, not code
    - Created `portfolio_manager.py` for executing single scenarios or portfolios
    - Implemented automatic price determination: exercises use strike price, sales near tender dates use tender price, other actions use projected prices
    - Separated price growth scenarios into `price_scenarios.json` (no duplication with user_profile)
    - Portfolio execution groups multiple scenarios with shared assumptions
    - Created comprehensive scenario documentation in `scenarios/README.md`
    - Built `portfolio_analysis.py` CLI tool for easy scenario execution and comparison
    - Scenarios are now just directories with `actions.csv` files - no JSON config needed
    - Price projections use simple linear growth from base 409A price
    - Dynamic date handling: uses current date as start, minimum 5-year projections

### In Progress 🔄

**Advanced Scenario Features** - Extending the projection engine capabilities:
- 🔄 Annual tax aggregation for complex multi-action years (W2 + exercises + sales + donations)
- 🔄 Pledge fulfillment tracking improvements (maximalist vs minimalist interpretation)
- 🔄 AMT credit carryforward tracking across years
- 🔄 Charitable deduction carryforward with 5-year expiration

### Up Next 📋

**IMMEDIATE - Tax Composability Improvements:**
1. **Annual tax aggregation pattern:**
   - Design year-end tax calculation that combines all actions in single year
   - Handle complex interactions: W2 + NSO exercise + capital gains + charitable deductions + AMT
   - Validate tax calculations compose correctly for multi-action years

**Phase 1 - Projection Engine Foundation:**
1. Create projection state models (YearlyState, ProjectionPlan)
2. Ask user to come up with scenarios
3. Implement ProjectionCalculator using existing calculators (modification allowed as needed)
4. Validate Natural Evolution scenario runs correctly

  **Related - Tax Composability Design:**
1. **Design year-end tax calculation pattern:**
   - Keep atomic calculators for individual actions (exercise, sale, donation)
   - Add annual tax aggregator that combines all year's actions:
     ```python
     def calculate_annual_tax_impact(actions: List[Action], profile: UserProfile) -> TaxSummary:
         # Aggregate ordinary income (W2 + NSO exercise)
         # Aggregate capital gains (LTCG/STCG from sales)
         # Calculate AMT on combined income vs regular tax
         # Apply charitable deductions against total AGI
         # Return comprehensive tax summary
     ```
   - Validate tax interactions work correctly for complex years

2. **Stress test composability:**
   - Create test scenarios with multiple actions in single year
   - Validate: exercise ISO + exercise NSO + tender NSO + donate shares
   - Ensure tax calculations are correct and composable

**Phase 2 - Basic Scenario Variants:**
1. Ask the user what variants they want to create
3. Generate CSV outputs: projection_comparison.csv, yearly_cashflow.csv, tax_timeline.csv
4. For MVP, read and compare raw output files rather than complex comparison engine

**Phase 3 - Calculator Gap Resolution:**
1. Enhance tax state tracking (AMT credit carryforward, charitable deduction carryforward with additional data structure)
2. Add pledge obligation tracking per company program rules (maximalist vs minimalist interpretation)
3. Address option expiration tracking if not already available in user_profile.json
4. Validate multi-year projections balance correctly

**Phase 4 - Testing & Validation:**
1. Main execution workflow (projection_analysis.py)
2. Generate equity_position_timeline.csv as product of user_profile.json
3. Testing with specified scenarios (to be defined when needed)
4. Documentation and validation

### Future Vision 🚀

**Lifecycle Optimization Engine** - A fundamental evolution from tactical to strategic planning:
- See [LIFECYCLE_VISION.md](./LIFECYCLE_VISION.md) for detailed technical vision
- Moves from "what should I do now?" to "what's the optimal path for every share?"
- Handles the combinatorial explosion of exercise/hold/sell/donate decisions over time
- Uses dynamic programming and policy learning instead of brute force enumeration
- Represents each share's journey from grant → vest → exercise → hold → disposition
- Enables true multi-year tax optimization and donation impact maximization

This would be a significant architectural evolution, building on top of the current calculators
but introducing stateful optimization, scenario modeling, and policy-based decision making.

### Architecture References 📚
- [TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md) - Overall system design principles
- [PORTFOLIO_ARCHITECTURE.md](./PORTFOLIO_ARCHITECTURE.md) - Portfolio-based scenario system design
- [TIMELINE_DATA_MODEL.md](./TIMELINE_DATA_MODEL.md) - Timeline data model for tracking share lifecycle states
- [CALCULATOR_ECOSYSTEM.md](./CALCULATOR_ECOSYSTEM.md) - How all calculators fit together
- [TENDER_ARCHITECTURE.md](./TENDER_ARCHITECTURE.md) - Tender calculator layered architecture
- [DONATION_CALCULATOR_PLAN.md](./DONATION_CALCULATOR_PLAN.md) - Donation calculator implementation plan
- [PROJECTION_ENGINE_PLAN.md](./PROJECTION_ENGINE_PLAN.md) - Multi-year projection engine implementation plan
- [PROJECT_SPEC.md](./PROJECT_SPEC.md) - Original project requirements and vision
- [LIFECYCLE_VISION.md](./LIFECYCLE_VISION.md) - Future vision for lifecycle optimization

### Open Questions
- How to best represent future vesting events in the timeline?
- Should the timeline include planned actions or just historical?
- What output format will be most actionable for decision-making?

---
*Last Updated: Current Session*
