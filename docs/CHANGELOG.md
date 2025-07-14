# CHANGELOG - Equity Financial Optimizer

## Initial Release
- Built equity optimizer for ISO/NSO/RSU tax planning with component-based architecture
- Created calculators for tender decisions, AMT estimation, and scenario planning
- Established company-agnostic design patterns and data-driven approach
- Implemented progressive tax brackets replacing flat rate approximations

## Tax Engine Foundation
- Built ISO Exercise Calculator with federal/state AMT and credit generation
- Created Share Sale Calculator with STCG/LTCG split and disqualifying dispositions
- Implemented Donation Calculator with 30% stock/60% cash AGI limits and carryforward
- Added Annual Tax Aggregator with proper federal/CA calculations and income-based LTCG brackets (0%/15%/20%)

## Architecture Evolution
- Split monolithic calculator into specialized components with clean separation
- Migrated from CSV-based actions to JSON scenario definitions
- Implemented portfolio system for multi-scenario comparison
- Created share lifecycle tracking (grant→vest→exercise→disposition)

## Tender Calculator Refactor
- Created unified TenderCalculator with pure calculation logic
- Built TenderStrategyGenerator with 7 selection strategies
- Implemented strategy discovery pattern (optimal emerges from comparison)
- Added comprehensive test coverage for all components

## Share Donation Calculator
- Implemented donation calculations with federal/state AGI limitations
- Added 5-year carryforward tracking and company match calculations
- Built donation_strategy_generator with multiple optimization strategies
- Integrated with scenario planner for comprehensive analysis

## Data Contract v2.0
- Created comprehensive DATA_CONTRACT.md defining canonical profile format
- Built profile migration utility for v1.x to v2.0 conversion
- Established JSON inputs only, CSV outputs only principle
- Created direct JSON→ShareLot loading eliminating CSV intermediate format

## Realistic Scenario Development
- Fixed lot naming consistency (VESTED_ISO/NSO → ISO/NSO) across loaders
- Added share quantity validation to prevent over-exercise/sale/donation
- Created fundamental strategies: aggressive exercise, AMT management, charitable, diversification
- Built portfolio comparison system for side-by-side evaluation

## Security & Organization
- Implemented demo/user data separation with automatic fallback
- Created numbered scenario format (000-999) with clear categorization
- Built secure ProfileLoader with three-file pattern (user/demo/template)
- Added output organization by data source and price scenario

## CSV Output Overhaul
- Enhanced action_summary.csv with full tax treatment details
- Added specialized tracking: holding periods, pledge obligations, charitable carryforward
- Created tax_component_breakdown.csv for detailed attribution
- Removed redundant outputs and standardized naming conventions

## Projection Engine
- Built multi-year ProjectionCalculator with cash flow tracking
- Implemented natural vesting through state transitions
- Added AMT credit and charitable deduction carryforward tracking
- Created comprehensive pledge tracking with FIFO discharge

## Tax Constants Consolidation
- Fixed AGI cash donation limit (50% → 60% per IRS 2025)
- Created centralized tax_constants.py eliminating duplication
- Built amt_calculator.py as single source of AMT calculations
- Added federal/state separation for all charitable calculations

## Charitable Basis Election
- Added per-year basis election configuration in scenario JSON
- When elected, stock donations use cost basis with 50% AGI limit
- Enhanced CSV outputs to show election status and deduction type
- Created comprehensive tests for high/low appreciation scenarios

## Withholding System Refactor
- Replaced 4 withholding fields with 2 rate-based fields
- Added intelligent supplemental withholding for stock compensation
- Improved future year projections using base withholding rates
- Maintained backward compatibility while improving accuracy

## Company Match Tracking
- Implemented comprehensive match tracking with 3-year window enforcement
- Added match window validation preventing expired donations from receiving match
- Built lost opportunity tracking when windows expire unfulfilled
- Enhanced CSVs with match visibility and leverage metrics

## Option Expiration
- Added EXPIRED lifecycle state and expiration_date to ShareLot
- Implemented automatic expiration processing with opportunity cost tracking
- Created ExpirationEvent class with proper warnings
- Added comprehensive test coverage for all scenarios

## Cash Flow Accuracy
- Updated projections to include all income sources (spouse, interest, dividends)
- Added living expenses and investment growth modeling
- Implemented proper withholding vs gross tax liability calculation
- Fixed AMT credit carryforward from user profile

## Charitable Deduction Compliance
- Implemented IRS-compliant FIFO consumption (earliest year first)
- Added 5-year expiration tracking with proper warnings
- Fixed ordering: cash before stock, current year before carryovers
- Created comprehensive test scenarios for validation

## Runtime Validation
- Added exercise plan validation preventing duplicate lot exercises
- Provides clear error messages for planning inconsistencies
- Validates total exercises don't exceed lot sizes upfront
- Eliminates confusing runtime errors with educational messages

## Asset Tracking Enhancement
- Added crypto and real estate to net worth calculations
- Enhanced text output with complete asset breakdown
- Fixed portfolio concentration calculations across all assets
- Updated CSVs to include non-equity holdings

## Pledge System Improvements
- Fixed pledge_elections processing from scenario JSON
- Enhanced action_summary.csv with accurate acquisition dates and holding periods
- Fixed charitable deduction calculation for zero-basis donations
- Standardized basis election logic eliminating false carryforwards

## Comprehensive Output Improvements
- Added assumed_ipo field for pledge deadline calculations
- Enhanced CSVs with AMT credit tracking and option exercise counts
- Implemented warning system for AMT credits, pledges, and expirations
- Created comprehensive value tracking across personal wealth and charitable impact

## IPO Pledge Obligations
- Implemented automatic IPO remainder obligation calculations
- Added FIFO donation tracking for accurate outstanding amounts
- Enhanced holding period CSV with chronological milestone sorting
- Fixed grant loading pipeline for proper pledge calculations

## Charitable Ordering Fix
- Implemented correct IRS waterfall: cash current→carryforward→stock current→carryforward
- Added complete FIFO tracking for all four carryforward types
- Enhanced CSV organization with logical federal/state separation
- Added expired deduction warnings with actionable guidance

## Enhanced Summary Format
- Redesigned output as professional balance sheet format
- Added structured equity position lifecycle analysis
- Implemented --verbose flag for detailed table control
- Restructured README for alpha testing onboarding

## 2025-06-30 Updates
- Fixed NSO tender exercises to use tender price as FMV
- Consolidated CSV generation to component-based architecture
- Fixed AMT credit bug preventing same-year generation and consumption
- Removed 1000+ lines of legacy CSV generation code

## 2025-07-01 Updates
- Added LiquidityEvent model for tender/IPO tracking
- Implemented IPO remainder obligations with automatic creation
- Migrated to grant-based profile structure (original_grants → grants)
- Fixed vesting calendar loading from new grant format

## 2025-07-02 Updates
- Fixed timeline generator to process ALL grants instead of just first grant
- Completed lot ID migration from old format (ISO/NSO/RSU) to grant-specific (ISO_GRANT_001)
- Created 47 atomic test scenarios for comprehensive coverage
- Reorganized portfolios into demo/ and user/ subdirectories
- Added validation errors for deprecated lot ID formats
- Enhanced cash flow tracking to identify insufficient cash years

## 2025-07-03 Updates
- Fixed marginal rate calculation to correctly use filing status for Additional Medicare Tax threshold
- Fixed company match calculation bug that always returned 0.0 in projection_calculator.py
- Added charitable_deduction_total column to annual_tax_detail.csv for easier deduction visibility
- Fixed missing action_date for donation events in components.csv output
- Refactored save_comprehensive_cashflow_csv from projection_output.py to csv_generators.py for better code organization
- Enhanced CLAUDE.md documentation for future agents
- Fixed test failures in test_amt_2035_issue.py and test_amt_charitable_deduction.py
- Refactored test_charitable_deduction_usage.py to be self-contained

## IPO Pledge Obligation Fix
- Fixed bug where IPO pledge obligations were calculated based only on shares vesting during projection
- Updated calculation to use total_options from grant (assumes IPO after full vesting)
- Added test_ipo_pledge_total_vested_bug.py demonstrating the issue and fix
- This prevents massive under-reporting of pledge obligations at IPO time

## Company Match Calculation Fix
- Fixed company match calculation to follow FAQ rules instead of pledge fulfillment
- Company match now based on: min((pledge% × vested_shares) - already_donated, shares_being_donated)
- Added proper 3-year liquidity event window validation
- Created test demonstrating the bug and verifying the fix

## CSV Output Cleanup
- Removed duplicate `pledge_shares_donated` field from CSV output (was duplicating `shares_donated_count`)
- Fixed `pledge_shares_outstanding` to properly decrease when obligations expire
- Outstanding shares now correctly show 0 after all windows have closed
- Added test to verify outstanding shares decrease after expiration

## Legacy Code Removal
- Removed legacy company match calculation fallback
- Simplified code to always use FAQ-based calculation formula
- Removed try/except block that fell back to pledge-based calculation
- All shares now require grant_id for company match tracking
- Updated tests to reflect correct FAQ-based behavior
- Deleted test_company_match_calculation_rules.py (documented legacy behavior)

## Vesting Schedule Validation
- Added test to verify vesting_schedule field validation works correctly
- User profiles use vesting_calendar (detailed schedule) instead of vesting_schedule (formula)
- Code properly handles both formats: vesting_calendar preferred, vesting_schedule as fallback
- Missing vesting_schedule fails loudly with clear error when vesting_status is absent
- No silent failures - proper error messages guide users to correct format

