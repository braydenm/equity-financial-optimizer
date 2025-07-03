#!/usr/bin/env python3
"""
Test to illustrate the current INCORRECT company match calculation behavior.

This test demonstrates that the current implementation incorrectly bases company
match on pledge obligation fulfillment rather than the actual rules from the FAQ.

Per the FAQ, the correct formula is:
At any given time, eligible for match = 
min(
  (pledge_percentage × total_vested_shares) - shares_already_donated,
  actual_shares_being_donated
) × share_price × match_ratio

The current implementation incorrectly only gives match for shares that fulfill
outstanding pledge obligations.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from projections.projection_calculator import ProjectionCalculator
from projections.projection_state import (
    ProjectionPlan, PlannedAction, ActionType, ShareLot, 
    UserProfile, ShareType, LifecycleState, TaxTreatment
)
from calculators.liquidity_event import LiquidityEvent


def create_test_profile(pledge_percentage: float = 0.5, match_ratio: float = 3.0) -> UserProfile:
    """Create a test user profile with grant-specific charitable programs."""
    profile = UserProfile(
        federal_tax_rate=0.24,
        federal_ltcg_rate=0.15,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        annual_w2_income=200000,
        current_cash=500000,
        exercise_reserves=100000,
        pledge_percentage=pledge_percentage,
        company_match_ratio=match_ratio,
        filing_status='single',
        state_of_residence='California',
        spouse_w2_income=0,
        monthly_living_expenses=5000,
        taxable_investments=0
    )
    
    # Add grant information
    profile.grants = [{
        'grant_id': 'GRANT_001',
        'grant_date': '2020-01-15',
        'total_options': 10000,
        'option_type': 'ISO',
        'strike_price': 5.0,
        'vesting_schedule': '4_year_monthly_with_cliff',
        'cliff_months': 12,
        'vesting_start_date': '2020-01-15',
        'charitable_program': {
            'pledge_percentage': pledge_percentage,
            'company_match_ratio': match_ratio
        }
    }]
    
    return profile


def test_case_1_donations_exceed_pledge_obligation():
    """
    Test Case 1: Donations exceed pledge obligation
    
    Scenario: User has vested 10k shares, sold 1k in year 1 (creating 500 share
    pledge obligation with 50% pledge), then donates 5k in year 2.
    
    Current (INCORRECT) behavior: Only 500 shares get company match
    Correct behavior: All 5k shares should get company match (up to vested cap)
    """
    print("=" * 80)
    print("TEST CASE 1: Donations Exceed Pledge Obligation")
    print("=" * 80)
    
    profile = create_test_profile(pledge_percentage=0.5, match_ratio=3.0)
    calculator = ProjectionCalculator(profile)
    
    # Create initial share lots - 10k vested shares
    initial_lots = [
        ShareLot(
            lot_id='VEST_20240115_ISO_GRANT_001',
            share_type=ShareType.ISO,
            quantity=10000,
            strike_price=5.0,
            grant_date=date(2020, 1, 15),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2030, 1, 15),
            grant_id='GRANT_001'
        )
    ]
    
    # Create projection plan
    plan = ProjectionPlan(
        name="Test Case 1",
        description="Test donations exceeding pledge obligation",
        start_date=date(2024, 1, 1),
        end_date=date(2026, 12, 31),
        initial_lots=initial_lots,
        initial_cash=500000,
        price_projections={
            2024: 50.0,
            2025: 55.0,
            2026: 60.0
        }
    )
    
    # Year 1: Exercise all 10k shares
    plan.add_action(PlannedAction(
        action_date=date(2024, 3, 1),
        action_type=ActionType.EXERCISE,
        lot_id='VEST_20240115_ISO_GRANT_001',
        quantity=10000,
        price=50.0
    ))
    
    # Year 1: Sell 1k shares (creates 500 share pledge obligation)
    plan.add_action(PlannedAction(
        action_date=date(2024, 6, 1),
        action_type=ActionType.SELL,
        lot_id='VEST_20240115_ISO_GRANT_001_EX_20240301',
        quantity=1000,
        price=50.0
    ))
    
    # Add liquidity event for the sale
    sale_event = LiquidityEvent(
        event_id="sale_2024-06-01",
        event_date=date(2024, 6, 1),
        event_type="tender_offer",
        price_per_share=50.0,
        shares_vested_at_event=10000
    )
    profile.liquidity_events = [sale_event]
    
    # Year 2: Donate 5k shares
    plan.add_action(PlannedAction(
        action_date=date(2025, 9, 1),
        action_type=ActionType.DONATE,
        lot_id='VEST_20240115_ISO_GRANT_001_EX_20240301',
        quantity=5000,
        price=55.0
    ))
    
    # Run projection
    result = calculator.evaluate_projection_plan(plan)
    
    # Analyze results
    year_2025 = result.get_state_for_year(2025)
    donations_2025 = year_2025.donation_value
    company_match_2025 = year_2025.company_match_received
    
    # Debug: Check pledge state
    pledge_state = year_2025.pledge_state
    if pledge_state.obligations:
        print(f"\nPledge State Debug:")
        for i, obligation in enumerate(pledge_state.obligations):
            print(f"  Obligation {i+1}:")
            print(f"    Shares obligated: {obligation.shares_obligated}")
            print(f"    Shares fulfilled: {obligation.shares_fulfilled}")
            print(f"    Shares remaining: {obligation.shares_remaining}")
    
    print(f"\nYear 2025 Results:")
    print(f"  Shares donated: 5,000")
    print(f"  Share price: $55")
    print(f"  Donation value: ${donations_2025:,.2f}")
    print(f"  Company match received: ${company_match_2025:,.2f}")
    
    # Calculate what should happen
    expected_match = 5000 * 55.0 * 3.0  # All 5k shares should get 3:1 match
    # Current logic: only credited shares (those fulfilling obligations) get match
    credited_shares = 1000  # From debug output above
    actual_based_match = credited_shares * 55.0 * 3.0
    
    print(f"\nExpected Behavior (per FAQ):")
    print(f"  Eligible shares for match: 5,000 (up to 50% of 10k vested = 5k cap)")
    print(f"  Expected match: ${expected_match:,.2f}")
    
    print(f"\nCurrent Behavior (pledge-based):")
    print(f"  Pledge obligation: 1,000 shares (misnamed - actually 100% of 1k sold)")
    print(f"  Shares credited: 1,000 (only these get match)")
    print(f"  Current match: ${company_match_2025:,.2f}")
    print(f"  Calculated as: 1,000 credited shares × $55 × 3.0 = ${actual_based_match:,.2f}")
    
    # Check if current behavior matches expected behavior
    is_correct = abs(company_match_2025 - expected_match) < 0.01
    
    print(f"\n{'✅ PASS' if is_correct else '❌ FAIL'}: Company match calculation")
    if not is_correct:
        print(f"  Current implementation incorrectly limits match to pledge obligations")
        print(f"  Missing match on {5000 - credited_shares:,} shares = ${(expected_match - company_match_2025):,.2f}")
    
    return is_correct


def test_case_2_donation_after_window_expires():
    """
    Test Case 2: Donation after sale window expires
    
    Scenario: User vests 10k shares, sells 1k in year 1, donates 1k in year 4
    (more than 3 years after sale).
    
    Current behavior: May incorrectly give match based on pledge logic
    Correct behavior: $0 match because donation is outside 3-year window
    """
    print("\n" + "=" * 80)
    print("TEST CASE 2: Donation After Sale Window Expires")
    print("=" * 80)
    
    profile = create_test_profile(pledge_percentage=0.5, match_ratio=3.0)
    calculator = ProjectionCalculator(profile)
    
    # Create initial share lots
    initial_lots = [
        ShareLot(
            lot_id='VEST_20240115_ISO_GRANT_001',
            share_type=ShareType.ISO,
            quantity=10000,
            strike_price=5.0,
            grant_date=date(2020, 1, 15),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2030, 1, 15),
            grant_id='GRANT_001'
        )
    ]
    
    # Create projection plan
    plan = ProjectionPlan(
        name="Test Case 2",
        description="Test donation after window expires",
        start_date=date(2024, 1, 1),
        end_date=date(2027, 12, 31),
        initial_lots=initial_lots,
        initial_cash=500000,
        price_projections={
            2024: 50.0,
            2025: 55.0,
            2026: 60.0,
            2027: 65.0
        }
    )
    
    # Year 1: Exercise all shares
    plan.add_action(PlannedAction(
        action_date=date(2024, 3, 1),
        action_type=ActionType.EXERCISE,
        lot_id='VEST_20240115_ISO_GRANT_001',
        quantity=10000
    ))
    
    # Year 1: Sell 1k shares
    plan.add_action(PlannedAction(
        action_date=date(2024, 6, 1),
        action_type=ActionType.SELL,
        lot_id='VEST_20240115_ISO_GRANT_001_EX_20240301',
        quantity=1000,
        price=50.0
    ))
    
    # Add liquidity event with 3-year window
    sale_event = LiquidityEvent(
        event_id="sale_2024-06-01",
        event_date=date(2024, 6, 1),
        event_type="tender_offer",
        price_per_share=50.0,
        shares_vested_at_event=10000
    )
    profile.liquidity_events = [sale_event]
    
    # Year 4: Donate 1k shares (after window expires on 2027-06-01)
    plan.add_action(PlannedAction(
        action_date=date(2027, 7, 1),  # 1 month after window closes
        action_type=ActionType.DONATE,
        lot_id='VEST_20240115_ISO_GRANT_001_EX_20240301',
        quantity=1000,
        price=65.0
    ))
    
    # Run projection
    result = calculator.evaluate_projection_plan(plan)
    
    # Analyze results
    year_2027 = result.get_state_for_year(2027)
    donations_2027 = year_2027.donation_value
    company_match_2027 = year_2027.company_match_received
    
    print(f"\nYear 2027 Results:")
    print(f"  Sale date: 2024-06-01")
    print(f"  Window expires: 2027-06-01")
    print(f"  Donation date: 2027-07-01 (after window)")
    print(f"  Shares donated: 1,000")
    print(f"  Company match received: ${company_match_2027:,.2f}")
    
    print(f"\nExpected Behavior (per FAQ):")
    print(f"  Match window: 3 years from sale")
    print(f"  Expected match: $0 (outside window)")
    
    # Check if match was incorrectly given
    is_correct = company_match_2027 == 0
    
    print(f"\n{'✅ PASS' if is_correct else '❌ FAIL'}: Window expiration check")
    if not is_correct:
        print(f"  ERROR: Company match given for donation outside 3-year window")
    
    return is_correct


def test_case_3_ipo_window_interaction():
    """
    Test Case 3: IPO window interaction
    
    Scenario: User vests 10k shares, exercises all, IPO in year 8 with 5k sale.
    Donation after IPO window should get no match.
    """
    print("\n" + "=" * 80)
    print("TEST CASE 3: IPO Window Interaction")
    print("=" * 80)
    
    profile = create_test_profile(pledge_percentage=0.5, match_ratio=3.0)
    profile.assumed_ipo = date(2031, 6, 1)  # IPO in year 8
    calculator = ProjectionCalculator(profile)
    
    # Create initial share lots
    initial_lots = [
        ShareLot(
            lot_id='VEST_20240115_ISO_GRANT_001',
            share_type=ShareType.ISO,
            quantity=10000,
            strike_price=5.0,
            grant_date=date(2020, 1, 15),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2030, 1, 15),
            grant_id='GRANT_001'
        )
    ]
    
    # Create projection plan
    plan = ProjectionPlan(
        name="Test Case 3",
        description="Test IPO window interaction",
        start_date=date(2024, 1, 1),
        end_date=date(2035, 12, 31),
        initial_lots=initial_lots,
        initial_cash=500000,
        price_projections={year: 50.0 + (year - 2024) * 5 for year in range(2024, 2036)}
    )
    
    # Year 1: Exercise all shares
    plan.add_action(PlannedAction(
        action_date=date(2024, 3, 1),
        action_type=ActionType.EXERCISE,
        lot_id='VEST_20240115_ISO_GRANT_001',
        quantity=10000
    ))
    
    # Year 8 (IPO year): Sell 5k shares
    plan.add_action(PlannedAction(
        action_date=date(2031, 6, 1),
        action_type=ActionType.SELL,
        lot_id='VEST_20240115_ISO_GRANT_001_EX_20240301',
        quantity=5000,
        price=85.0
    ))
    
    # Year 11: Donate 2k shares (after IPO window)
    plan.add_action(PlannedAction(
        action_date=date(2034, 7, 1),  # More than 3 years after IPO
        action_type=ActionType.DONATE,
        lot_id='VEST_20240115_ISO_GRANT_001_EX_20240301',
        quantity=2000,
        price=100.0
    ))
    
    # Run projection
    result = calculator.evaluate_projection_plan(plan)
    
    # Analyze results
    year_2034 = result.get_state_for_year(2034)
    donations_2034 = year_2034.donation_value
    company_match_2034 = year_2034.company_match_received
    
    print(f"\nYear 2034 Results:")
    print(f"  IPO date: 2031-06-01")
    print(f"  IPO window expires: 2034-06-01")
    print(f"  Donation date: 2034-07-01 (after window)")
    print(f"  Shares donated: 2,000")
    print(f"  Company match received: ${company_match_2034:,.2f}")
    
    print(f"\nExpected Behavior:")
    print(f"  Match window: 3 years from IPO")
    print(f"  Expected match: $0 (outside window)")
    
    is_correct = company_match_2034 == 0
    
    print(f"\n{'✅ PASS' if is_correct else '❌ FAIL'}: IPO window check")
    
    return is_correct


def test_case_4_complex_interaction():
    """
    Test Case 4: Complex interaction - vesting, sales, and match eligibility
    
    Scenario: Progressive vesting, multiple sales, donations at different times
    Tests the correct calculation of match eligibility based on vested shares
    minus already donated, NOT pledge obligations.
    """
    print("\n" + "=" * 80)
    print("TEST CASE 4: Complex Vesting and Match Eligibility")
    print("=" * 80)
    
    profile = create_test_profile(pledge_percentage=0.25, match_ratio=1.0)
    calculator = ProjectionCalculator(profile)
    
    # Update grant to have 20k shares for this test
    profile.grants[0]['total_options'] = 20000
    
    # Create initial lots representing vesting schedule
    # Year 1: 5k vested, Year 2: +5k, Year 3: +5k, Year 4: +5k
    initial_lots = [
        ShareLot(
            lot_id='VEST_20240115_ISO_GRANT_001',
            share_type=ShareType.ISO,
            quantity=5000,
            strike_price=5.0,
            grant_date=date(2020, 1, 15),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2030, 1, 15),
            grant_id='GRANT_001'
        )
    ]
    
    plan = ProjectionPlan(
        name="Test Case 4",
        description="Complex vesting and match eligibility",
        start_date=date(2024, 1, 1),
        end_date=date(2027, 12, 31),
        initial_lots=initial_lots,
        initial_cash=500000,
        price_projections={
            2024: 50.0,
            2025: 55.0,
            2026: 60.0,
            2027: 65.0
        }
    )
    
    # Year 1: Exercise initial 5k
    plan.add_action(PlannedAction(
        action_date=date(2024, 2, 1),
        action_type=ActionType.EXERCISE,
        lot_id='VEST_20240115_ISO_GRANT_001',
        quantity=5000
    ))
    
    # Year 1: Sell 2k shares
    plan.add_action(PlannedAction(
        action_date=date(2024, 6, 1),
        action_type=ActionType.SELL,
        lot_id='VEST_20240115_ISO_GRANT_001_EX_20240201',
        quantity=2000,
        price=50.0
    ))
    
    # Year 1: Donate 1k shares
    plan.add_action(PlannedAction(
        action_date=date(2024, 9, 1),
        action_type=ActionType.DONATE,
        lot_id='VEST_20240115_ISO_GRANT_001_EX_20240201',
        quantity=1000,
        price=50.0
    ))
    
    # Add more vested shares for year 2
    plan.initial_lots.append(ShareLot(
        lot_id='VEST_20250115_ISO_GRANT_001',
        share_type=ShareType.ISO,
        quantity=5000,
        strike_price=5.0,
        grant_date=date(2020, 1, 15),
        lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
        tax_treatment=TaxTreatment.NA,
        expiration_date=date(2030, 1, 15),
        grant_id='GRANT_001'
    ))
    
    # Year 2: Exercise newly vested shares
    plan.add_action(PlannedAction(
        action_date=date(2025, 2, 1),
        action_type=ActionType.EXERCISE,
        lot_id='VEST_20250115_ISO_GRANT_001',
        quantity=5000
    ))
    
    # Year 2: Donate 3k shares
    # With 10k vested, 25% pledge = 2.5k eligible
    # Already donated 1k, so only 1.5k should get match
    plan.add_action(PlannedAction(
        action_date=date(2025, 9, 1),
        action_type=ActionType.DONATE,
        lot_id='VEST_20250115_ISO_GRANT_001_EX_20250201',
        quantity=3000,
        price=55.0
    ))
    
    # Add liquidity events
    profile.liquidity_events = [
        LiquidityEvent(
            event_id="sale_2024-06-01",
            event_date=date(2024, 6, 1),
            event_type="tender_offer",
            price_per_share=50.0,
            shares_vested_at_event=5000
        )
    ]
    
    # Run projection
    result = calculator.evaluate_projection_plan(plan)
    
    # Analyze Year 2 results
    year_2025 = result.get_state_for_year(2025)
    
    print(f"\nYear 2025 Analysis:")
    print(f"  Total vested shares: 10,000")
    print(f"  Pledge percentage: 25%")
    print(f"  Match cap: 2,500 shares (25% of 10k)")
    print(f"  Previously donated: 1,000 shares")
    print(f"  Remaining match eligibility: 1,500 shares")
    print(f"  Shares donated this year: 3,000")
    print(f"  Company match received: ${year_2025.company_match_received:,.2f}")
    
    # Calculate expected match
    expected_match = 1500 * 55.0 * 1.0  # Only 1.5k eligible
    
    print(f"\nExpected match calculation:")
    print(f"  Eligible shares: min(3000 donated, 1500 remaining cap) = 1,500")
    print(f"  Expected match: 1,500 × $55 × 1.0 = ${expected_match:,.2f}")
    
    # The current implementation might give different results based on pledge logic
    is_correct = abs(year_2025.company_match_received - expected_match) < 0.01
    
    print(f"\n{'✅ PASS' if is_correct else '❌ FAIL'}: Complex eligibility calculation")
    if not is_correct:
        print(f"  ERROR: Match calculation not following (pledge% × vested) - already_donated formula")
    
    return is_correct


def run_all_tests():
    """Run all test cases and summarize results."""
    print("COMPANY MATCH CALCULATION RULES TEST SUITE")
    print("Testing current implementation against FAQ requirements")
    print("")
    
    results = []
    
    # Run each test case
    results.append(("Case 1: Donations exceed pledge", test_case_1_donations_exceed_pledge_obligation()))
    results.append(("Case 2: Window expiration", test_case_2_donation_after_window_expires()))
    results.append(("Case 3: IPO window", test_case_3_ipo_window_interaction()))
    results.append(("Case 4: Complex eligibility", test_case_4_complex_interaction()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed < total:
        print("\n⚠️  CURRENT IMPLEMENTATION ISSUES:")
        print("1. Company match is incorrectly based on pledge obligation fulfillment")
        print("2. Should be based on: (pledge% × vested shares) - already donated")
        print("3. Window expiration rules may not be properly enforced")
        print("\nSee CLAUDE.md for migration plan to fix these issues.")
    
    return passed == total


if __name__ == "__main__":
    all_passed = run_all_tests()
    sys.exit(0 if all_passed else 1)