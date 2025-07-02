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
from projections.projection_state import UserProfile, PlannedAction, ActionType


def test_ipo_creates_remainder_obligation():
    """Test that IPO creates obligation for all vested shares, not just sold shares"""

    # Create test profile directly
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
        current_cash=100000,
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
        assumed_ipo=date(2026, 3, 15),  # IPO date
        grants=[{
            "grant_id": "GRANT_001",
            "grant_date": "2021-01-15",
            "expiration_date": "2031-01-15",
            "type": "ISO",
            "total_options": 10000,
            "strike_price": 2.5,
            "vesting_start_date": "2021-01-15",
            "vesting_schedule": "4_year_monthly_with_cliff",
            "cliff_months": 12,
            "charitable_program": {
                "pledge_percentage": 0.5,
                "company_match_ratio": 3.0
            }
        }]
    )

    # We need to exercise the shares first to make them sellable
    planned_actions = [
        PlannedAction(
            action_date=date(2025, 1, 15),
            action_type=ActionType.EXERCISE,
            lot_id="ISO_001",
            quantity=10000,  # Exercise all vested shares
            price=60.0,  # Share price at sale
            notes="Exercise all vested ISOs"
        ),
        PlannedAction(
            action_date=date(2025, 6, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_001_EX_20250115",  # The exercised lot ID
            quantity=2000,
            price=60.0,  # Share price at sale
            notes="Sell 2000 shares before IPO"
        )
    ]

    # Initialize calculator
    calculator = ProjectionCalculator(profile)

    # Create initial lots - the unexercised options
    from projections.projection_state import ShareLot, ShareType, LifecycleState, TaxTreatment
    initial_lots = [
        ShareLot(
            lot_id="ISO_001",
            share_type=ShareType.ISO,
            quantity=10000,
            strike_price=2.5,
            grant_date=date(2021, 1, 15),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,  # Unexercised options
            exercise_date=None,
            cost_basis=0.0,
            amt_adjustment=0.0,
            fmv_at_exercise=None,
            expiration_date=date(2031, 1, 15),
            grant_id="GRANT_001"
        )
    ]

    # Create a projection plan
    from projections.projection_state import ProjectionPlan
    plan = ProjectionPlan(
        name="test_ipo_obligation",
        description="Test IPO remainder obligation creation",
        start_date=date(2025, 1, 1),
        end_date=date(2027, 12, 31),
        initial_lots=initial_lots,
        initial_cash=profile.current_cash,
        price_projections={
            2025: 60.0,
            2026: 75.0,  # IPO year
            2027: 90.0
        }
    )

    # Add actions to the plan
    for action in planned_actions:
        plan.add_action(action)

    # Run projection
    result = calculator.evaluate_projection_plan(plan)

    # Get 2026 state (IPO year)
    ipo_year_state = None
    for yearly_state in result.yearly_states:
        if yearly_state.year == 2026:
            ipo_year_state = yearly_state
            break

    assert ipo_year_state is not None, "Should have 2026 year state"

    # Calculate expected values
    # By 2026-03-15 (IPO), the grant will have vested for ~5.2 years
    # 4-year vesting with 1-year cliff means:
    # - After 1 year: 25% vested (2500 shares)
    # - Then 75% over 36 months = 2.083% per month
    # - From 2021-01-15 to 2026-03-15 is ~62 months
    # - Vested shares = 2500 + (48 months * 208.33) = 10000 (fully vested after 4 years)
    vested_shares_at_ipo = 10000  # Fully vested by IPO

    # Expected pledge obligation calculation:
    # - 50% pledge on 10,000 vested shares = 5,000 total share obligation
    # - Sale of 2,000 shares with 50% maximalist pledge:
    #   shares_donated / (shares_sold + shares_donated) = 0.5
    #   shares_donated / (2000 + shares_donated) = 0.5
    #   shares_donated = 2000
    # - IPO should create remainder obligation for 3,000 shares
    expected_total_obligation = 5000
    expected_sale_obligation = 2000  # Maximalist interpretation
    expected_ipo_remainder = 3000

    # Check total obligations
    total_obligations = sum(
        o.shares_obligated for o in ipo_year_state.pledge_state.obligations
    )

    print(f"\nDEBUG: Total obligations found: {total_obligations}")
    print(f"DEBUG: Expected total obligations: {expected_total_obligation}")
    print(f"DEBUG: Number of obligations: {len(ipo_year_state.pledge_state.obligations)}")

    for i, obligation in enumerate(ipo_year_state.pledge_state.obligations):
        print(f"DEBUG: Obligation {i+1}: {obligation.shares_obligated} shares")
        print(f"       Source event: {obligation.source_event_id}")
        print(f"       Obligation type: {obligation.obligation_type}")
        print(f"       Pledge %: {obligation.pledge_percentage}")
        print(f"       Shares fulfilled: {obligation.shares_fulfilled}")

    # Check for the bug: The system is incorrectly calculating IPO obligations
    # It shows 3000 shares "sold" at IPO which is wrong
    # The real issue is that it's not tracking obligations correctly

    # Let's check if an IPO trigger exists first
    ipo_trigger_found = any(o.obligation_type == "ipo_remainder" for o in ipo_year_state.pledge_state.obligations)
    print(f"\nDEBUG: IPO trigger found: {ipo_trigger_found}")

    if ipo_trigger_found:
        ipo_obligation = next(o for o in ipo_year_state.pledge_state.obligations if o.obligation_type == "ipo_remainder")
        print(f"DEBUG: IPO obligation created for {ipo_obligation.shares_obligated} shares")
        print(f"DEBUG: This is the remainder obligation to complete the pledge")

    # The test should check that obligations are created correctly
    # Current behavior: System creates strange IPO obligations with phantom "sales"
    # Expected behavior: IPO should create remainder obligations without sales

    # Check that IPO remainder obligation exists
    ipo_obligations = [
        o for o in ipo_year_state.pledge_state.obligations
        if o.obligation_type == "ipo_remainder"
    ]

    sale_obligations = [
        o for o in ipo_year_state.pledge_state.obligations
        if o.obligation_type == "sale"
    ]

    assert len(ipo_obligations) == 1, (
        f"Should have one IPO remainder obligation, but found {len(ipo_obligations)}. "
        f"The system needs to create obligations at IPO for all vested shares."
    )

    assert len(sale_obligations) == 1, (
        f"Should have one sale obligation, but found {len(sale_obligations)}."
    )

    if ipo_obligations:
        assert ipo_obligations[0].shares_obligated == expected_ipo_remainder, (
            f"IPO remainder obligation should be {expected_ipo_remainder} shares, "
            f"but got {ipo_obligations[0].shares_obligated}"
        )

    if sale_obligations:
        assert sale_obligations[0].shares_obligated == expected_sale_obligation, (
            f"Sale obligation should be {expected_sale_obligation} shares, "
            f"but got {sale_obligations[0].shares_obligated}"
        )


if __name__ == "__main__":
    print("Running test_ipo_creates_remainder_obligation...")
    print("This test is expected to FAIL with the current implementation.")
    print("It demonstrates that IPO events should create pledge obligations")
    print("for all vested shares, not just those that were sold.\n")

    try:
        test_ipo_creates_remainder_obligation()
        print("\nTest PASSED - IPO remainder obligations are correctly created!")
    except AssertionError as e:
        print(f"\nTest FAILED (as expected): {e}")
        print("\nThis confirms the bug exists and needs to be fixed.")
