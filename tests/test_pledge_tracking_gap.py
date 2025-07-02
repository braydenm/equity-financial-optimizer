"""
Test the pledge tracking gap where donations don't count toward pledge fulfillment.

This test demonstrates the bug where donations made before obligations exist
(either through sales or IPO trigger) don't count toward pledge fulfillment,
creating confusing output where you can donate your entire position but still
show 0% pledge fulfillment.
"""

import os
import sys
from datetime import date
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_calculator import ProjectionCalculator
from projections.projection_state import (
    UserProfile, PlannedAction, ActionType, ProjectionPlan,
    ShareLot, ShareType, LifecycleState, TaxTreatment
)


def test_donations_without_obligations_dont_count():
    """Test that donations made before obligations exist don't count toward pledge."""

    # Create test profile with 50% pledge
    profile = UserProfile(
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.0930,
        state_ltcg_rate=0.0930,
        fica_tax_rate=0.0765,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        annual_w2_income=200000,
        spouse_w2_income=0,
        other_income=0,
        interest_income=0,
        dividend_income=0,
        bonus_expected=50000,
        current_cash=500000,  # Enough cash for exercises
        exercise_reserves=50000,
        pledge_percentage=0.5,  # 50% pledge percentage
        company_match_ratio=3.0,
        filing_status="single",
        state_of_residence="CA",
        monthly_living_expenses=10000,
        taxable_investments=0,
        crypto=0,
        real_estate_equity=0,
        amt_credit_carryforward=0,
        assumed_ipo=date(2026, 3, 15),  # IPO date in future
        grants=[{
            "grant_id": "RSU_001",
            "grant_date": "2021-01-15",
            "expiration_date": "2031-01-15",
            "type": "RSU",
            "total_options": 100000,
            "strike_price": 0,
            "vesting_start_date": "2021-01-15",
            "vesting_schedule": "4_year_monthly_with_cliff",
            "cliff_months": 12,
            "charitable_program": {
                "pledge_percentage": 0.5,
                "company_match_ratio": 3.0
            }
        }]
    )

    # Create initial lots - RSUs that are vested
    initial_lots = [
        ShareLot(
            lot_id="RSU_001",
            share_type=ShareType.RSU,
            quantity=50000,  # 50k shares vested
            strike_price=0,
            grant_date=date(2021, 1, 15),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,  # RSUs auto-exercise
            tax_treatment=TaxTreatment.LTCG,  # Been held > 1 year
            exercise_date=date(2022, 1, 15),  # Vested and delivered
            cost_basis=10.0,  # FMV at vesting
            amt_adjustment=0.0,
            fmv_at_exercise=10.0,
            expiration_date=None,  # RSUs don't expire
            grant_id="RSU_001"
        )
    ]

    # Scenario: Donate 20,000 shares WITHOUT any prior sales
    planned_actions = [
        PlannedAction(
            action_date=date(2025, 6, 1),
            action_type=ActionType.DONATE,
            lot_id="RSU_001",
            quantity=20000,  # Donate 20k shares
            price=60.0,
            notes="Donate shares without any sales to trigger obligations"
        )
    ]

    # Create projection plan
    plan = ProjectionPlan(
        name="test_donation_gap",
        description="Test donations without obligations",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        initial_lots=initial_lots,
        initial_cash=profile.current_cash,
        price_projections={
            2025: 60.0,
            2026: 75.0
        }
    )

    # Add actions to the plan
    for action in planned_actions:
        plan.add_action(action)

    # Initialize calculator and run projection
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)

    # Get 2025 state
    year_2025 = next(ys for ys in result.yearly_states if ys.year == 2025)

    # Check donation tracking
    print("\n=== BUG DEMONSTRATION: Donations Without Obligations ===")
    print(f"\nTotal shares donated: {year_2025.pledge_shares_donated_this_year}")
    print(f"Donation value: ${year_2025.donation_value:,.2f}")

    # Check pledge obligations
    pledge_state = year_2025.pledge_state
    total_pledge_shares_credited = sum(o.shares_fulfilled for o in pledge_state.obligations)

    print(f"\nPledge obligations created: {len(pledge_state.obligations)}")
    print(f"Shares credited toward pledge: {total_pledge_shares_credited}")

    # This is the bug: We donated 20,000 shares but 0 count toward pledge
    assert year_2025.pledge_shares_donated_this_year == 20000, "Should have donated 20,000 shares"
    assert total_pledge_shares_credited == 0, "Bug: No shares credited toward pledge without obligations"

    print("\n❌ BUG CONFIRMED: Donated 20,000 shares but 0 count toward pledge fulfillment!")
    print("   This creates confusing output where donations don't fulfill pledge obligations.")

    return result


def test_ipo_trigger_ignores_prior_donations():
    """Test that IPO trigger doesn't credit donations made before the obligation existed."""

    # Create test profile with IPO date
    profile = UserProfile(
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.0930,
        state_ltcg_rate=0.0930,
        fica_tax_rate=0.0765,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        annual_w2_income=200000,
        spouse_w2_income=0,
        other_income=0,
        interest_income=0,
        dividend_income=0,
        bonus_expected=50000,
        current_cash=500000,
        exercise_reserves=50000,
        pledge_percentage=0.5,  # 50% pledge
        company_match_ratio=3.0,
        filing_status="single",
        state_of_residence="CA",
        monthly_living_expenses=10000,
        taxable_investments=0,
        crypto=0,
        real_estate_equity=0,
        amt_credit_carryforward=0,
        assumed_ipo=date(2026, 3, 15),  # IPO in 2026
        grants=[{
            "grant_id": "RSU_001",
            "grant_date": "2021-01-15",
            "expiration_date": "2031-01-15",
            "type": "RSU",
            "total_options": 100000,
            "strike_price": 0,
            "vesting_start_date": "2021-01-15",
            "vesting_schedule": "4_year_monthly_with_cliff",
            "cliff_months": 12,
            "charitable_program": {
                "pledge_percentage": 0.5,
                "company_match_ratio": 3.0
            }
        }]
    )

    # Create initial lots
    initial_lots = [
        ShareLot(
            lot_id="RSU_001",
            share_type=ShareType.RSU,
            quantity=100000,  # All shares vested
            strike_price=0,
            grant_date=date(2021, 1, 15),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2022, 1, 15),
            cost_basis=10.0,
            amt_adjustment=0.0,
            fmv_at_exercise=10.0,
            expiration_date=None,
            grant_id="RSU_001"
        )
    ]

    # Scenario: Donate before IPO trigger
    planned_actions = [
        PlannedAction(
            action_date=date(2025, 6, 1),  # Before IPO
            action_type=ActionType.DONATE,
            lot_id="RSU_001",
            quantity=25000,  # Donate 25k shares
            price=60.0,
            notes="Donate shares before IPO trigger"
        )
    ]

    # Create projection plan through IPO year
    plan = ProjectionPlan(
        name="test_ipo_gap",
        description="Test IPO trigger with prior donations",
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),  # Include IPO year
        initial_lots=initial_lots,
        initial_cash=profile.current_cash,
        price_projections={
            2025: 60.0,
            2026: 75.0
        }
    )

    # Add actions to the plan
    for action in planned_actions:
        plan.add_action(action)

    # Initialize calculator and run projection
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)

    # Get 2026 state (IPO year)
    year_2026 = next(ys for ys in result.yearly_states if ys.year == 2026)

    print("\n=== BUG DEMONSTRATION: IPO Trigger Ignores Prior Donations ===")

    # Check total donations across both years
    total_donated = sum(ys.pledge_shares_donated_this_year for ys in result.yearly_states)
    print(f"\nTotal shares donated (2025-2026): {total_donated}")

    # Check IPO-triggered obligations
    pledge_state = year_2026.pledge_state
    ipo_obligations = [o for o in pledge_state.obligations if o.obligation_type == "ipo_remainder"]

    if ipo_obligations:
        ipo_obligation = ipo_obligations[0]
        print(f"\nIPO triggered obligation for: {ipo_obligation.shares_obligated} shares")
        print(f"Shares credited toward IPO obligation: {ipo_obligation.shares_fulfilled}")

        # This is the bug: IPO creates 50k obligation but doesn't credit the 25k already donated
        assert ipo_obligation.shares_obligated == 50000, "IPO should create 50k obligation (50% of 100k)"
        assert ipo_obligation.shares_fulfilled == 0, "Bug: Prior donations not credited"

        print("\n❌ BUG CONFIRMED: IPO created 50,000 share obligation")
        print("   but the 25,000 shares donated in 2025 don't count!")
        print("   This makes it appear you haven't fulfilled any of your pledge.")

    return result


if __name__ == "__main__":
    print("Running pledge tracking gap tests...")
    print("These tests demonstrate bugs in how donations are credited toward pledge obligations.\n")

    try:
        # Test 1: Donations without obligations
        print("TEST 1: Donations without sales don't create obligations")
        test_donations_without_obligations_dont_count()

        # Test 2: IPO trigger ignores prior donations
        print("\n\nTEST 2: IPO trigger doesn't credit prior donations")
        test_ipo_trigger_ignores_prior_donations()

        print("\n\n✅ Both tests passed - bugs confirmed!")
        print("\nSUMMARY OF BUGS:")
        print("1. Donations made without sales/obligations don't count toward pledge")
        print("2. IPO-triggered obligations ignore donations made before the IPO")
        print("\nThese bugs create confusing output where users can donate large amounts")
        print("but still show 0% pledge fulfillment.")

    except AssertionError as e:
        print(f"\n❌ Test failed unexpectedly: {e}")
        print("The system behavior may have changed.")
