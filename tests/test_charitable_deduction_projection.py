"""
Regression tests for charitable deduction AGI limit handling in projection calculator.

This test ensures that ProjectionCalculator properly applies AGI limits from
AnnualTaxCalculator results instead of using raw donation amounts. Previously,
the projection calculator ignored AGI limits, causing overstatement of deductions.
"""

import sys
import os
from datetime import date, datetime
from decimal import Decimal

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from projections.projection_state import UserProfile
from projections.projection_calculator import ProjectionCalculator, ProjectionPlan
from projections.projection_state import ShareLot, LifecycleState, PlannedAction, ActionType, ShareType, TaxTreatment


def create_test_profile_for_bug():
    """Create a test profile with high income to test AGI limits."""
    return UserProfile(
        # High AGI to test limits
        annual_w2_income=500000,  # $500K AGI
        spouse_w2_income=0,
        other_income=0,
        interest_income=0,
        dividend_income=0,

        # Tax info
        filing_status='single',
        state_of_residence='California',
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.133,
        state_ltcg_rate=0.133,
        fica_tax_rate=0.0765,
        additional_medicare_rate=0.009,
        niit_rate=0.038,

        # Financial position
        current_cash=100000,
        exercise_reserves=0,
        taxable_investments=200000,
        monthly_living_expenses=12500,  # $150K annual

        # Company matching
        pledge_percentage=0.5,
        company_match_ratio=3.0,

        # AMT and carryforwards
        amt_credit_carryforward=0,

        # Investment return
        investment_return_rate=0.07
    )


def test_charitable_deduction_agi_limit_bug():
    """
    Regression test for charitable deduction AGI limit application.

    Verifies that $400K donation with $500K AGI is correctly limited to $150K (30%)
    instead of allowing the full $400K deduction amount.
    """
    print("\n" + "="*80)
    print("TEST: Charitable Deduction AGI Limit Regression Test")
    print("="*80)

    profile = create_test_profile_for_bug()

    # Create a share lot that we'll donate
    test_lot = ShareLot(
        lot_id='RSU_001',
        share_type=ShareType.RSU,
        quantity=4000,  # 4000 shares at $100 = $400K donation
        strike_price=0.0,  # RSU
        grant_date=date(2020, 1, 1),
        lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
        tax_treatment=TaxTreatment.LTCG,
        exercise_date=date(2023, 1, 1),
        fmv_at_exercise=25.0,
        cost_basis=0.0
    )

    # Create projection plan with donation action
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)

    # Create timeline action for donation - $400K donation (exceeds 30% AGI limit)
    donation_action = PlannedAction(
        action_type=ActionType.DONATE,
        action_date=date(2025, 6, 1),
        lot_id='RSU_001',
        quantity=4000,  # Full lot
        price=100.0,  # $400K total donation value
        notes='Large donation exceeding AGI limit'
    )

    plan = ProjectionPlan(
        name="Test Charitable Deduction Bug",
        description="Test scenario with large donation exceeding AGI limits",
        start_date=start_date,
        end_date=end_date,
        planned_actions=[donation_action],
        initial_lots=[test_lot],
        initial_cash=profile.current_cash,
        tax_elections={},
        price_projections={2025: 100.0}
    )

    # Execute projection
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)

    # Get the 2025 yearly state
    year_2025_state = None
    for yearly_state in result.yearly_states:
        if yearly_state.year == 2025:
            year_2025_state = yearly_state
            break

    assert year_2025_state is not None, "Should have 2025 yearly state"

    # Print the results
    agi = profile.annual_w2_income  # $500K
    donation_value = 400000  # $400K
    expected_limit = agi * 0.30  # $150K (30% AGI limit for stock donations)

    print(f"\nScenario Details:")
    print(f"  AGI: ${agi:,}")
    print(f"  Stock Donation Value: ${donation_value:,}")
    print(f"  Expected AGI Limit (30%): ${expected_limit:,.0f}")

    print(f"\nProjection Results:")
    print(f"  Donation Value in State: ${year_2025_state.donation_value:,.0f}")
    print(f"  Federal Current Year Deduction: ${year_2025_state.charitable_state.federal_current_year_deduction:,.0f}")
    print(f"  Federal Total Available: ${year_2025_state.charitable_state.federal_total_available:,.0f}")

    print(f"\nAnnual Tax Calculator Results (from tax_result):")
    print(f"  Total Tax: ${year_2025_state.tax_state.total_tax:,.0f}")

    # The BUG: charitable_state shows full donation amount instead of AGI-limited amount
    print(f"📊 VERIFICATION:")
    print(f"  Actual Deduction: ${year_2025_state.charitable_state.federal_current_year_deduction:,.0f}")
    print(f"  Expected Deduction: ${expected_limit:,.0f}")
    print(f"  Difference: ${year_2025_state.charitable_state.federal_current_year_deduction - expected_limit:,.0f}")

    # Verify AGI limits are properly applied
    assert year_2025_state.charitable_state.federal_current_year_deduction == expected_limit, \
        f"Charitable deduction should be limited to {expected_limit:,.0f} (30% of AGI), but got {year_2025_state.charitable_state.federal_current_year_deduction:,.0f}"

    print("\n✅ Test PASSED - AGI limits correctly applied!")
    return True


def test_charitable_deduction_carryforward():
    """
    Test that charitable deduction carryforward works correctly across multiple years.

    This test verifies that when a donation exceeds AGI limits, the excess
    amount is properly carried forward and used in subsequent years.
    """
    print("\n" + "="*80)
    print("TEST: Charitable Deduction Carryforward Functionality")
    print("="*80)

    profile = create_test_profile_for_bug()

    # Create a share lot for a large donation
    test_lot = ShareLot(
        lot_id='RSU_002',
        share_type=ShareType.RSU,
        quantity=6000,  # 6000 shares at $100 = $600K donation
        strike_price=0.0,
        grant_date=date(2020, 1, 1),
        lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
        tax_treatment=TaxTreatment.LTCG,
        exercise_date=date(2023, 1, 1),
        fmv_at_exercise=25.0,
        cost_basis=0.0
    )

    # Create multi-year projection plan with large donation in year 1
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2026, 12, 31)  # Two years

    # Large donation in year 1 - $600K donation (exceeds 30% AGI limit significantly)
    donation_action = PlannedAction(
        action_type=ActionType.DONATE,
        action_date=date(2025, 6, 1),
        lot_id='RSU_002',
        quantity=6000,
        price=100.0,
        notes='Large donation with carryforward'
    )

    plan = ProjectionPlan(
        name="Test Charitable Carryforward",
        description="Multi-year test with large donation requiring carryforward",
        start_date=start_date,
        end_date=end_date,
        planned_actions=[donation_action],
        initial_lots=[test_lot],
        initial_cash=profile.current_cash,
        tax_elections={},
        price_projections={2025: 100.0, 2026: 100.0}
    )

    # Execute projection
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)

    # Get yearly states
    year_2025_state = None
    year_2026_state = None
    for yearly_state in result.yearly_states:
        if yearly_state.year == 2025:
            year_2025_state = yearly_state
        elif yearly_state.year == 2026:
            year_2026_state = yearly_state

    assert year_2025_state is not None, "Should have 2025 yearly state"
    assert year_2026_state is not None, "Should have 2026 yearly state"

    # Calculate expected values
    agi = profile.annual_w2_income  # $500K
    donation_value = 600000  # $600K
    year_1_limit = agi * 0.30  # $150K (30% AGI limit)
    expected_carryforward = donation_value - year_1_limit  # $450K

    print(f"\nMulti-Year Carryforward Test:")
    print(f"  AGI (both years): ${agi:,}")
    print(f"  Total Donation Value: ${donation_value:,}")
    print(f"  Year 1 AGI Limit (30%): ${year_1_limit:,.0f}")
    print(f"  Expected Carryforward: ${expected_carryforward:,.0f}")

    print(f"Year 2025 Results:")
    print(f"  Federal Current Year Deduction: ${year_2025_state.charitable_state.federal_current_year_deduction:,.0f}")
    print(f"  Federal Total Available: ${year_2025_state.charitable_state.federal_total_available:,.0f}")
    print(f"  Federal Carryforward Remaining: {year_2025_state.charitable_state.federal_carryforward_remaining}")

    print(f"\nYear 2026 Results:")
    print(f"  Federal Current Year Deduction: ${year_2026_state.charitable_state.federal_current_year_deduction:,.0f}")
    print(f"  Federal Total Available: ${year_2026_state.charitable_state.federal_total_available:,.0f}")
    print(f"  Federal Carryforward Remaining: {year_2026_state.charitable_state.federal_carryforward_remaining}")

    # Verify year 1 deduction is limited to AGI
    assert year_2025_state.charitable_state.federal_current_year_deduction == year_1_limit, \
        f"Year 1 deduction should be {year_1_limit:,.0f}, but got {year_2025_state.charitable_state.federal_current_year_deduction:,.0f}"

    # Verify year 2 uses carryforward (up to AGI limit)
    year_2_limit = agi * 0.30  # $150K again
    assert year_2026_state.charitable_state.federal_current_year_deduction == year_2_limit, \
        f"Year 2 deduction should be {year_2_limit:,.0f}, but got {year_2026_state.charitable_state.federal_current_year_deduction:,.0f}"

    # Verify remaining carryforward
    total_used = year_1_limit + year_2_limit  # $300K
    expected_remaining = donation_value - total_used  # $300K
    remaining_carryforward = sum(year_2026_state.charitable_state.federal_carryforward_remaining.values())
    assert remaining_carryforward == expected_remaining, \
        f"Remaining carryforward should be {expected_remaining:,.0f}, but got {remaining_carryforward:,.0f}"

    print(f"\n✅ Carryforward test passed!")
    print(f"  Year 1 used: ${year_1_limit:,.0f}")
    print(f"  Year 2 used: ${year_2_limit:,.0f}")
    print(f"  Total used: ${total_used:,.0f}")
    print(f"  Remaining carryforward: ${remaining_carryforward:,.0f}")

    return True




def run_test():
    """Run charitable deduction regression and carryforward tests."""
    print("Testing Charitable Deduction AGI Limit and Carryforward in Projection Calculator")

    try:
        # Test 1: Bug reproduction
        success1 = test_charitable_deduction_agi_limit_bug()

        # Test 2: Carryforward functionality
        success2 = test_charitable_deduction_carryforward()

        if success1 and success2:
            print("\n🎉 All tests passed!")
        else:
            print("\n⚠️  Some tests failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_test()
