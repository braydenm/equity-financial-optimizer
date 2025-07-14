#!/usr/bin/env python3
"""
Test to demonstrate and fix the IPO obligation timing bug.

The bug: IPO obligations are created AFTER processing actions for the year,
preventing same-year donations from being applied to the IPO obligation.
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


def create_test_profile() -> UserProfile:
    """Create a test user profile with IPO date."""
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
        pledge_percentage=0.5,
        company_match_ratio=3.0,
        filing_status='single',
        state_of_residence='California',
        spouse_w2_income=0,
        monthly_living_expenses=5000,
        regular_income_withholding_rate=0.22,
        supplemental_income_withholding_rate=0.22,
        quarterly_payments=0,
        assumed_ipo=date(2033, 3, 24),  # IPO in March
        investment_return_rate=0.07
    )
    
    # Add grant information
    profile.grants = [{
        'grant_id': 'GRANT_001',
        'grant_date': '2020-01-15',
        'total_options': 20000,
        'option_type': 'NSO',
        'strike_price': 1.0,
        'vesting_schedule': '4_year_monthly_with_cliff',
        'cliff_months': 12,
        'vesting_start_date': '2020-01-15',
        'charitable_program': {
            'pledge_percentage': 0.5,
            'company_match_ratio': 3.0
        }
    }]
    
    # Add pre-existing IPO event to avoid the bug in IPO event creation
    from calculators.liquidity_event import LiquidityEvent
    profile.liquidity_events = [
        LiquidityEvent(
            event_id="ipo_2033",
            event_date=date(2033, 3, 24),
            event_type="ipo",
            price_per_share=50.0,
            shares_vested_at_event=20000
        )
    ]
    
    return profile


def test_ipo_obligation_timing():
    """Test that donations after IPO in the same year reduce the IPO obligation."""
    print("\nIPO OBLIGATION TIMING BUG TEST")
    print("=" * 80)
    
    profile = create_test_profile()
    
    # Create initial lots - 20,000 shares vested before IPO
    initial_lots = [
        ShareLot(
            lot_id="VCS-100",
            share_type=ShareType.NSO,
            quantity=20000,
            strike_price=1.0,
            grant_date=date(2020, 1, 1),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2022, 1, 1),
            cost_basis=1.0,
            fmv_at_exercise=10.0,
            grant_id='GRANT_001'
        )
    ]
    
    # Create plan with donation AFTER IPO in the same year
    plan = ProjectionPlan(
        name="IPO Timing Test",
        description="Test IPO obligation with same-year donation",
        start_date=date(2033, 1, 1),
        end_date=date(2034, 12, 31),
        initial_lots=initial_lots,
        initial_cash=500000,
        price_projections={
            2033: 50.0,
            2034: 55.0
        }
    )
    
    # Add donation in September 2033 (AFTER March IPO)
    plan.add_action(PlannedAction(
        action_date=date(2033, 9, 1),
        action_type=ActionType.DONATE,
        lot_id="VCS-100",
        quantity=5000,
        price=50.0,  # Use the year's price
        notes="Donation after IPO should reduce IPO obligation"
    ))
    
    # Run projection
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)
    
    # Check 2033 results
    state_2033 = result.get_state_for_year(2033)
    
    print(f"\n2033 Results (IPO year):")
    print(f"  IPO Date: {profile.assumed_ipo}")
    print(f"  Donation Date: 2033-09-01")
    print(f"  Vested shares at IPO: 20,000")
    print(f"  Expected IPO obligation: 10,000 (50% of 20,000)")
    print(f"  Shares donated: {state_2033.pledge_shares_donated_this_year}")
    print(f"  Expected outstanding: 5,000 (10,000 - 5,000)")
    print(f"  Actual outstanding: {state_2033.pledge_state.total_shares_remaining}")
    
    # The bug: outstanding should be 5,000 but will be 10,000
    # because IPO obligation is created after donations are processed
    expected_outstanding = 5000
    actual_outstanding = state_2033.pledge_state.total_shares_remaining
    
    if actual_outstanding == expected_outstanding:
        print(f"\n✅ PASS: Outstanding shares correctly shows {expected_outstanding}")
        return True
    else:
        print(f"\n❌ FAIL: Outstanding shares shows {actual_outstanding}, expected {expected_outstanding}")
        print("  This confirms the IPO obligation timing bug!")
        
        # Check 2034 to see if donation applies next year
        state_2034 = result.get_state_for_year(2034)
        if state_2034:
            print(f"\n2034 Results (following year):")
            print(f"  Outstanding: {state_2034.pledge_state.total_shares_remaining}")
            print("  The donation appears to apply in the following year (one-year lag)")
        
        return False


def main():
    """Run the test."""
    success = test_ipo_obligation_timing()
    
    if not success:
        print("\n⚠️  Test confirmed the bug exists. IPO obligations need to be created")
        print("   BEFORE processing actions so same-year donations can apply.")
        sys.exit(1)
    else:
        print("\n✅ Bug has been fixed!")
        sys.exit(0)


if __name__ == "__main__":
    main()