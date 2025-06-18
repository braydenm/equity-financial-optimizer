#!/usr/bin/env python3
"""
Test NSO exercise calculations including bargain element and withholding.

This test verifies:
1. NSO exercises correctly calculate bargain element (FMV - strike price)
2. Supplemental withholding is applied to NSO bargain element
3. The correct calculator is used (NSO not ISO)
4. Integration with projection system works correctly
"""

import sys
import os
from datetime import date
from decimal import Decimal

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.iso_exercise_calculator import calculate_nso_exercise_components
from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import AnnualTaxComponents
from calculators.tax_constants import (
    FEDERAL_SUPPLEMENTAL_WITHHOLDING_RATE,
    CALIFORNIA_SUPPLEMENTAL_WITHHOLDING_RATE,
    MEDICARE_RATE,
    CALIFORNIA_SDI_RATE
)
from projections.projection_state import (
    UserProfile, ProjectionPlan, PlannedAction, ShareLot,
    ShareType, LifecycleState, TaxTreatment, ActionType
)
from projections.projection_calculator import ProjectionCalculator


def create_test_profile():
    """Create a test user profile with base withholding."""
    return UserProfile(
        filing_status='single',
        state_of_residence='California',
        annual_w2_income=175000,
        spouse_w2_income=0,
        other_income=0,
        interest_income=2000,
        dividend_income=500,
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        current_cash=10000,
        exercise_reserves=50000,
        company_match_ratio=3.0,
        pledge_percentage=0.0,
        # Base withholding for normal years
        federal_withholding=15000,
        state_withholding=8000,
        base_federal_withholding=15000,
        base_state_withholding=8000
    )


def test_nso_bargain_element_calculation():
    """Test that NSO exercises correctly calculate bargain element."""
    print("\nTest 1: NSO Bargain Element Calculation")
    print("=" * 60)

    # Test parameters
    shares = 1000
    strike_price = 5.0
    fmv_at_exercise = 30.0
    exercise_date = date(2026, 6, 15)
    grant_date = date(2022, 1, 1)

    # Calculate NSO components
    nso_components = calculate_nso_exercise_components(
        lot_id="TEST_NSO",
        exercise_date=exercise_date,
        shares_to_exercise=shares,
        strike_price=strike_price,
        current_fmv=fmv_at_exercise,
        grant_date=grant_date
    )

    expected_bargain_element = shares * (fmv_at_exercise - strike_price)

    print(f"Shares: {shares}")
    print(f"Strike Price: ${strike_price}")
    print(f"FMV at Exercise: ${fmv_at_exercise}")
    print(f"Expected Bargain Element: ${expected_bargain_element:,.2f}")
    print(f"Calculated Bargain Element: ${nso_components.bargain_element:,.2f}")

    assert nso_components.bargain_element == expected_bargain_element, \
        f"Expected {expected_bargain_element}, got {nso_components.bargain_element}"

    print("✅ NSO bargain element calculated correctly")


def test_nso_withholding_calculation():
    """Test that NSO exercises trigger supplemental withholding."""
    print("\n\nTest 2: NSO Supplemental Withholding")
    print("=" * 60)

    profile = create_test_profile()
    calculator = ProjectionCalculator(profile)

    # Calculate expected supplemental withholding rate
    supplemental_rate = (
        FEDERAL_SUPPLEMENTAL_WITHHOLDING_RATE +      # 22%
        CALIFORNIA_SUPPLEMENTAL_WITHHOLDING_RATE +   # 10.23%
        MEDICARE_RATE +                               # 1.45%
        CALIFORNIA_SDI_RATE                           # 1.2%
    )

    print(f"Federal Supplemental Rate: {FEDERAL_SUPPLEMENTAL_WITHHOLDING_RATE:.2%}")
    print(f"CA Supplemental Rate: {CALIFORNIA_SUPPLEMENTAL_WITHHOLDING_RATE:.2%}")
    print(f"Medicare Rate: {MEDICARE_RATE:.2%}")
    print(f"CA SDI Rate: {CALIFORNIA_SDI_RATE:.2%}")
    print(f"Total Supplemental Rate: {supplemental_rate:.2%}")

    # Test NSO exercise
    shares = 2000
    strike_price = 5.0
    fmv = 31.25  # Projected 2026 price with 25% growth
    bargain_element = shares * (fmv - strike_price)

    print(f"\nNSO Exercise:")
    print(f"Shares: {shares}")
    print(f"Strike: ${strike_price}")
    print(f"FMV: ${fmv}")
    print(f"Bargain Element: ${bargain_element:,.2f}")

    # Create annual components with NSO exercise
    annual_components = AnnualTaxComponents(year=2026)
    annual_components.w2_income = profile.annual_w2_income

    nso_components = calculate_nso_exercise_components(
        lot_id="TEST_NSO",
        exercise_date=date(2026, 1, 15),
        shares_to_exercise=shares,
        strike_price=strike_price,
        current_fmv=fmv,
        grant_date=date(2022, 1, 1)
    )
    annual_components.nso_exercise_components.append(nso_components)

    # Calculate withholding
    withholding = calculator.calculate_year_withholding(2026, annual_components)

    # Expected: base withholding + supplemental on bargain element
    expected_base = profile.base_federal_withholding + profile.base_state_withholding
    expected_supplemental = bargain_element * supplemental_rate
    expected_total = expected_base + expected_supplemental

    print(f"\nWithholding Calculation:")
    print(f"Base Withholding: ${expected_base:,.2f}")
    print(f"Supplemental on Bargain Element: ${expected_supplemental:,.2f}")
    print(f"Expected Total: ${expected_total:,.2f}")
    print(f"Calculated Total: ${withholding:,.2f}")

    # Allow small rounding difference
    assert abs(withholding - expected_total) < 1.0, \
        f"Expected {expected_total:.2f}, got {withholding:.2f}"

    print("✅ NSO supplemental withholding calculated correctly")


def test_iso_vs_nso_distinction():
    """Test that ISOs and NSOs are handled differently."""
    print("\n\nTest 3: ISO vs NSO Distinction")
    print("=" * 60)

    profile = create_test_profile()

    # Create lots
    iso_lot = ShareLot(
        lot_id="TEST_ISO",
        share_type=ShareType.ISO,
        quantity=1000,
        strike_price=5.0,
        grant_date=date(2022, 1, 1),
        lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
        tax_treatment=TaxTreatment.NA
    )

    nso_lot = ShareLot(
        lot_id="TEST_NSO",
        share_type=ShareType.NSO,
        quantity=1000,
        strike_price=5.0,
        grant_date=date(2022, 1, 1),
        lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
        tax_treatment=TaxTreatment.NA
    )

    # Create projection plan
    plan = ProjectionPlan(
        name="ISO vs NSO Test",
        description="Test different handling of ISO vs NSO",
        start_date=date(2025, 1, 1),
        end_date=date(2027, 12, 31),
        initial_lots=[iso_lot, nso_lot],
        initial_cash=profile.current_cash,
        price_projections={
            2025: 25.0,
            2026: 31.25,
            2027: 39.06
        }
    )

    # Add ISO exercise
    iso_action = PlannedAction(
        action_date=date(2026, 1, 15),
        action_type=ActionType.EXERCISE,
        lot_id="TEST_ISO",
        quantity=1000,
        price=5.0,  # Currently this is strike price (the bug)
        notes="ISO exercise"
    )
    plan.add_action(iso_action)

    # Add NSO exercise
    nso_action = PlannedAction(
        action_date=date(2026, 6, 15),
        action_type=ActionType.EXERCISE,
        lot_id="TEST_NSO",
        quantity=1000,
        price=5.0,  # Currently this is strike price (the bug)
        notes="NSO exercise"
    )
    plan.add_action(nso_action)

    # Run projection
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)

    # Check 2026 results
    year_2026 = next(s for s in result.yearly_states if s.year == 2026)

    print(f"2026 Tax Results:")
    print(f"Total Tax: ${year_2026.tax_state.total_tax:,.2f}")
    print(f"AMT Tax: ${year_2026.tax_state.amt_tax:,.2f}")
    print(f"Regular Tax: ${year_2026.tax_state.regular_tax:,.2f}")

    # With the bug, both exercises will show minimal tax impact
    # because action.price = strike price = $5
    # After fix, NSO should show significant ordinary income tax

    if year_2026.tax_state.total_tax < 50000:
        print("❌ Bug confirmed: NSO exercise not generating proper tax")
        print("   This is because action.price is strike price, not FMV")
    else:
        print("✅ NSO exercise generating proper tax")


def test_projection_integration():
    """Test full integration with projection system."""
    print("\n\nTest 4: Projection System Integration")
    print("=" * 60)

    profile = create_test_profile()

    # Create NSO lot that will vest in the future
    nso_lot = ShareLot(
        lot_id="VEST_20260101_NSO",
        share_type=ShareType.NSO,
        quantity=2000,
        strike_price=5.0,
        grant_date=date(2022, 1, 1),
        lifecycle_state=LifecycleState.GRANTED_NOT_VESTED,
        tax_treatment=TaxTreatment.NA
    )

    # Create plan
    plan = ProjectionPlan(
        name="NSO Vesting Test",
        description="Test NSO vesting and exercise",
        start_date=date(2025, 1, 1),
        end_date=date(2027, 12, 31),
        initial_lots=[nso_lot],
        initial_cash=profile.current_cash,
        price_projections={
            2025: 25.0,
            2026: 31.25,  # 25% growth
            2027: 39.06   # 25% growth
        }
    )

    # Add vesting action
    vest_action = PlannedAction(
        action_date=date(2026, 1, 1),
        action_type=ActionType.VEST,
        lot_id="VEST_20260101_NSO",
        quantity=2000,
        notes="NSO vesting"
    )
    plan.add_action(vest_action)

    # Add exercise action
    exercise_action = PlannedAction(
        action_date=date(2026, 1, 15),
        action_type=ActionType.EXERCISE,
        lot_id="VEST_20260101_NSO",
        quantity=2000,
        price=5.0,  # This should be FMV but is currently strike (bug)
        notes="Exercise vested NSOs"
    )
    plan.add_action(exercise_action)

    # Run projection
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)

    # Analyze results
    for yearly_state in result.yearly_states:
        print(f"\nYear {yearly_state.year}:")
        print(f"  Starting Cash: ${yearly_state.starting_cash:,.2f}")
        print(f"  Income: ${yearly_state.income:,.2f}")
        print(f"  Exercise Costs: ${yearly_state.exercise_costs:,.2f}")
        print(f"  Tax Paid: ${yearly_state.tax_paid:,.2f}")
        print(f"  Ending Cash: ${yearly_state.ending_cash:,.2f}")

        if yearly_state.year == 2026 and yearly_state.exercise_costs > 0:
            print(f"  Tax Withholdings: ${yearly_state.tax_withholdings:,.2f}")

            # With proper NSO handling, withholdings should be much higher
            base_withholding = 23000  # base federal + state
            if yearly_state.tax_withholdings <= base_withholding + 1000:
                print("  ❌ Bug: No supplemental withholding on NSO exercise")
            else:
                supplemental = yearly_state.tax_withholdings - base_withholding
                print(f"  ✅ Supplemental withholding: ${supplemental:,.2f}")


if __name__ == "__main__":
    print("NSO Exercise and Withholding Tests")
    print("=" * 80)

    # Run all tests
    test_nso_bargain_element_calculation()
    test_nso_withholding_calculation()
    test_iso_vs_nso_distinction()
    test_projection_integration()

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("\nNOTE: Some tests will show the bug until the fix is implemented.")
    print("After the fix, all tests should pass with proper bargain element calculations.")
