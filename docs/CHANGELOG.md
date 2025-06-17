# CHANGELOG - Equity Financial Optimizer

## Initial Release
- Initial equity financial optimizer concept and architecture
- Basic tender decision calculator for equity liquidity events
- AMT (Alternative Minimum Tax) estimator for ISO exercises
- Simple scenario planning framework
- Company-agnostic design patterns established
- Built equity compensation optimizer for ISO/NSO/RSU tax optimization with component-based architecture separating event extraction from annual aggregation

## Tax Engine Foundation
- Built progressive bracket calculator replacing flat rate approximations throughout the system
- ISO Exercise Calculator with federal/state AMT calculations, bargain element tracking, and credit generation
- Share Sale Calculator with proper STCG/LTCG split and disqualifying disposition handling for ISOs
- Donation Calculator with component extraction respecting 30% stock/60% cash AGI limits with carryforward
- Annual Tax Aggregator combining all components with proper federal/CA calculations and AGI-based limits
- Implemented proper LTCG federal brackets (0%/15%/20%) based on income levels replacing flat rates
- Fixed NSO exercise calculations to use progressive brackets instead of incorrect 48.65% flat rate (~25% tax savings)

## Architecture Evolution
- Split monolithic calculator into specialized components with clean separation of concerns
- Migrated from CSV-based actions to JSON scenario definitions for better structure and validation
- Added portfolio system for multi-scenario comparison capabilities
- Implemented automatic equity position timeline generation through lifecycle states
- Created share lifecycle tracking from grant→vest→exercise→disposition with proper state transitions
- True component-based architecture where calculators extract components for annual aggregation

## Tender Calculator Refactor
- Created unified TenderCalculator with pure calculation logic
- Built TenderStrategyGenerator with 7 different selection strategies
- Implemented strategy discovery pattern (optimal emerges from comparison, not predetermined)
- Added evaluate_tender_strategies() to scenario planner
- Created comprehensive tests for new components

## Calculator Taxonomy Update
- Renamed tax_estimator.py to iso_exercise_calculator.py
- Renamed tender_calculator.py to share_sale_calculator.py
- Updated all imports and class names throughout codebase
- Cleaned up examples to use API directly

## Share Donation Calculator
- Implemented comprehensive donation calculations with AGI limitations
- Handles 30% stock / 60% cash federal limits and 50% CA limits
- Built donation_strategy_generator.py with 7 different strategies
- Added carryforward rules and company match calculations
- Integrated with scenario planner through evaluate_donation_strategies()

## Data Contract v2.0
- Created comprehensive DATA_CONTRACT.md defining canonical profile format
- Built migrate_profile.py utility to convert v1.x profiles to v2.0
- Eliminated all conditional field checking throughout codebase
- Standardized field names across all components
- Implemented v2.0 data contract with canonical field names
- Created direct JSON→ShareLot loading via EquityLoader removing CSV as intermediate format
- Built comprehensive UserProfile with separate federal/state rates replacing combined rate approximations
- Established principle: JSON for inputs only, CSV for outputs/visualization only

## Portfolio-Based Scenario System
- Built data-driven scenario architecture with actions defined in JSON files, not code
- Created portfolio_manager.py for executing single scenarios or portfolio comparisons
- Implemented automatic price determination (strike for exercises, tender/projected for sales)
- Separated price growth scenarios into configurable JSON removing hardcoded assumptions
- Added natural evolution baseline showing trajectory with no actions taken
- Added comprehensive scenario documentation

## Security & Organization Overhaul
- Implemented data-source specific scenarios (demo vs user)
- Created numbered scenario format (000_, 001_, 002_)
- Enhanced output structure with complete execution traceability
- Built secure ProfileLoader with automatic demo data fallback and three-file pattern
- Created main CLI tools: run_portfolio_analysis.py and run_scenario_analysis.py
- Implemented secure ProfileLoader with demo/user data separation and automatic fallback
- Created three-file pattern: user_profile.json (private), demo_profile.json (safe), template
- Built data-source aware timeline generation preventing lot ID mismatches
- Added output organization: output/{data_source}/{price_scenario}/scenario_{name}/
- Generated metadata.json for complete execution traceability

## Annual Tax Composition Refactor
- Created component data structures for all tax events (ISOExerciseComponents, NSOExerciseComponents, ShareSaleComponents, DonationComponents)
- Built AnnualTaxCalculator with proper progressive tax brackets
- Fixed critical bugs:
  - NSO exercises now use brackets instead of flat 48.65% rate
  - LTCG uses 0%/15%/20% federal brackets based on income
  - AMT properly calculated at annual level
  - Charitable deductions respect AGI limits

## CSV Output Overhaul
- Removed redundant CSVs and renamed for clarity
- Enhanced action_summary.csv with full tax treatment details
- Added specialized tracking CSVs:
  - annual_tax_detail.csv with full component breakdown
  - action_summary.csv with acquisition dates, holding periods, tax treatment
  - state_timeline.csv and transition_timeline.csv for lot tracking
  - holding_period_tracking.csv for qualifying disposition monitoring
  - pledge_obligations.csv tracking donation commitments and company match
  - charitable_carryforward.csv showing AGI limits and carryover amounts with 5-year expiration
  - tax_component_breakdown.csv attributing taxes to specific income types and lots
- No external dependencies on CSV outputs enabling flexible reporting evolution

## Projection Engine
- Built multi-year ProjectionCalculator orchestrating all component calculators with cash flow tracking
- Implemented natural vesting through state transitions eliminating complex event detection logic
- Added comprehensive pledge tracking with maximalist/minimalist interpretations and FIFO discharge
- Created AMT credit carryforward tracking across years with proper usage rules
- Built charitable deduction carryforward with 5-year expiration tracking

## Lifecycle Architecture Simplification
- Removed unnecessary lifecycle event detection complexity
- Created loaders/equity_loader.py for direct JSON-to-ShareLot loading
- Eliminated CSV as intermediate format (now output-only)
- Implemented natural vesting through state transitions
- Clean data flow: JSON input → Process → CSV output
- Deleted deprecated modules (lifecycle_events_deprecated.py, timeline_loader.py)
- Created proper VestingEvent data classes for clean contracts
- Future vesting loads as granted_not_vested lots transitioning naturally to vested

## Testing Infrastructure
- Comprehensive test suite with 9 modules covering all calculators and components
- Real-world demo scenarios including tender offers, charitable donations, ISO exercises
- CSV validation tests ensuring output correctness and data flow integrity
- Component-based tests replacing legacy flat-rate calculations
- Fixed all failing tests establishing clean baseline
- Fixed test data inconsistencies and improved validation

## Tax Constants Consolidation
- Fixed critical AGI cash donation limit bug (50% → 60% per IRS 2025 rules)
- Created centralized tax_constants.py eliminating ~200 lines of duplication
- Built amt_calculator.py for single source of AMT calculations
- Resolved AGI inconsistency between calculators
- Removed ~200 lines of duplicated code

## Charitable Basis Election
- Added per-year basis election configuration via tax_elections in scenario JSON
- Enhanced annual tax calculator with elect_basis_deduction parameter
- When elected, stock donations use cost basis instead of FMV for deduction
- When elected, AGI limit increases from 30% to 50% for stock donations
- CSV output shows basis election status and deduction type per year
- Created comprehensive tests for high/low appreciation scenarios
- Added example scenario (004_basis_election_example.json) demonstrating usage

## Architecture Achievements
- True component-based architecture where calculators extract components for annual aggregation
- Clean separation of concerns: calculators know their domain, annual calculator handles complexity
- Scenario discovery pattern: optimal strategies emerge from comparison, not predetermined
- Strong data contracts with well-defined classes replacing dictionary/object dual handling
- No external dependencies on CSV outputs enabling flexible reporting evolution