#!/usr/bin/env python3
"""
Comprehensive test suite for ShareSaleComponents validation fixes.

This test verifies that the critical bug fix for ISO disqualifying dispositions
is working correctly. The original bug prevented any ISO disqualifying disposition
that had both ordinary income and capital gains, which is the most common scenario.

Run with: python3 audit_tests/test_validation_fixes.py
"""

import sys
import os
from datetime import date, timedelta

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.components import ShareSaleComponents, DispositionType
from calculators.share_sale_calculator import ShareSaleCalculator


def test_iso_disqualifying_with_ordinary_and_stcg():
    """Test ISO disqualifying disposition with both ordinary income and STCG."""
    print("\n" + "="*70)
    print("TEST: ISO Disqualifying - Ordinary Income + STCG")
    print("="*70)

    # Setup: Exercise ISO, sell within 1 year at profit above FMV at exercise
    grant_date = date(2023, 1, 1)
    exercise_date = date(2024, 1, 1)
    sale_date = date(2024, 6, 1)  # 5 months after exercise

    strike_price = 10.0
    fmv_at_exercise = 25.0
    sale_price = 40.0
    shares = 1000

    # Calculate via ShareSaleCalculator
    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="ISO-001",
        sale_date=sale_date,
        shares_to_sell=shares,
        sale_price=sale_price,
        cost_basis=strike_price,
        acquisition_date=exercise_date,
        acquisition_type='exercise',
        is_iso=True,
        grant_date=grant_date,
        exercise_date=exercise_date,
        fmv_at_exercise=fmv_at_exercise
    )

    print(f"Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"Short-term gain: ${result.short_term_gain:,.2f}")
    print(f"Long-term gain: ${result.long_term_gain:,.2f}")

    # Verify the calculation
    expected_ordinary = 15000.0  # min(total_gain=30k, bargain_element=15k)
    expected_stcg = 15000.0      # remaining gain

    assert result.ordinary_income == expected_ordinary, f"Expected ordinary income {expected_ordinary}, got {result.ordinary_income}"
    assert result.short_term_gain == expected_stcg, f"Expected STCG {expected_stcg}, got {result.short_term_gain}"
    assert result.long_term_gain == 0, f"Expected no LTCG, got {result.long_term_gain}"
    assert result.disposition_type == DispositionType.DISQUALIFYING_ISO

    print("✅ Test passed - Multiple gain types allowed for disqualifying disposition")


def test_iso_disqualifying_with_ordinary_and_ltcg():
    """Test ISO disqualifying disposition with both ordinary income and LTCG."""
    print("\n" + "="*70)
    print("TEST: ISO Disqualifying - Ordinary Income + LTCG")
    print("="*70)

    # Setup: Exercise ISO, sell after 1 year but before 2 years from grant
    grant_date = date(2022, 6, 1)
    exercise_date = date(2023, 1, 1)
    sale_date = date(2024, 3, 1)  # 14 months after exercise, 21 months from grant

    strike_price = 5.0
    fmv_at_exercise = 20.0
    sale_price = 35.0
    shares = 2000

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="ISO-002",
        sale_date=sale_date,
        shares_to_sell=shares,
        sale_price=sale_price,
        cost_basis=strike_price,
        acquisition_date=exercise_date,
        acquisition_type='exercise',
        is_iso=True,
        grant_date=grant_date,
        exercise_date=exercise_date,
        fmv_at_exercise=fmv_at_exercise
    )

    print(f"Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"Short-term gain: ${result.short_term_gain:,.2f}")
    print(f"Long-term gain: ${result.long_term_gain:,.2f}")

    # Verify: total gain = 60k, bargain element = 30k
    assert result.ordinary_income == 30000.0
    assert result.short_term_gain == 0
    assert result.long_term_gain == 30000.0  # Remaining gain is LTCG (>1 year)
    assert result.disposition_type == DispositionType.DISQUALIFYING_ISO

    print("✅ Test passed - Ordinary income + LTCG allowed")


def test_iso_disqualifying_only_ordinary():
    """Test ISO disqualifying disposition with only ordinary income."""
    print("\n" + "="*70)
    print("TEST: ISO Disqualifying - Only Ordinary Income")
    print("="*70)

    # Setup: Sell between strike and FMV at exercise
    grant_date = date(2023, 1, 1)
    exercise_date = date(2024, 1, 1)
    sale_date = date(2024, 4, 1)

    strike_price = 10.0
    fmv_at_exercise = 30.0
    sale_price = 20.0  # Between strike and FMV at exercise
    shares = 500

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="ISO-003",
        sale_date=sale_date,
        shares_to_sell=shares,
        sale_price=sale_price,
        cost_basis=strike_price,
        acquisition_date=exercise_date,
        acquisition_type='exercise',
        is_iso=True,
        grant_date=grant_date,
        exercise_date=exercise_date,
        fmv_at_exercise=fmv_at_exercise
    )

    print(f"Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"Capital gains: STCG=${result.short_term_gain}, LTCG=${result.long_term_gain}")

    # Total gain = 5k, bargain element = 10k, so all gain is ordinary
    assert result.ordinary_income == 5000.0
    assert result.short_term_gain == 0
    assert result.long_term_gain == 0

    print("✅ Test passed - Only ordinary income allowed")


def test_iso_disqualifying_at_loss():
    """Test ISO disqualifying disposition at a loss."""
    print("\n" + "="*70)
    print("TEST: ISO Disqualifying - Capital Loss")
    print("="*70)

    grant_date = date(2023, 1, 1)
    exercise_date = date(2024, 1, 1)
    sale_date = date(2024, 5, 1)

    strike_price = 15.0
    fmv_at_exercise = 25.0
    sale_price = 12.0  # Below strike price - capital loss
    shares = 1000

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="ISO-004",
        sale_date=sale_date,
        shares_to_sell=shares,
        sale_price=sale_price,
        cost_basis=strike_price,
        acquisition_date=exercise_date,
        acquisition_type='exercise',
        is_iso=True,
        grant_date=grant_date,
        exercise_date=exercise_date,
        fmv_at_exercise=fmv_at_exercise
    )

    print(f"Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"Short-term loss: ${result.short_term_gain:,.2f}")

    assert result.ordinary_income == 0
    assert result.short_term_gain == -3000.0  # Loss of $3/share
    assert result.long_term_gain == 0

    print("✅ Test passed - Capital loss with no ordinary income")


def test_regular_sale_validation():
    """Test that regular sales still require exactly one gain type."""
    print("\n" + "="*70)
    print("TEST: Regular Sale Validation")
    print("="*70)

    # Test 1: Valid LTCG sale
    try:
        components = ShareSaleComponents(
            lot_id="REG-001",
            sale_date=date.today(),
            shares_sold=100,
            sale_price=50.0,
            cost_basis=30.0,
            gross_proceeds=5000.0,
            acquisition_date=date.today() - timedelta(days=400),
            acquisition_type='purchase',
            holding_period_days=400,
            disposition_type=DispositionType.REGULAR_SALE,
            long_term_gain=2000.0
        )
        print("✅ Valid LTCG sale accepted")
    except ValueError as e:
        print(f"❌ Unexpected error: {e}")
        raise

    # Test 2: Invalid - multiple gain types for regular sale
    try:
        components = ShareSaleComponents(
            lot_id="REG-002",
            sale_date=date.today(),
            shares_sold=100,
            sale_price=50.0,
            cost_basis=30.0,
            gross_proceeds=5000.0,
            acquisition_date=date.today() - timedelta(days=400),
            acquisition_type='purchase',
            holding_period_days=400,
            disposition_type=DispositionType.REGULAR_SALE,
            short_term_gain=1000.0,
            long_term_gain=1000.0  # Both gains set - should fail
        )
        print("❌ Should have rejected multiple gain types for regular sale")
        assert False, "Validation should have failed"
    except ValueError as e:
        print(f"✅ Correctly rejected: {e}")


def test_edge_cases():
    """Test edge cases in validation logic."""
    print("\n" + "="*70)
    print("TEST: Edge Cases")
    print("="*70)

    # Test: Disqualifying disposition cannot mix ordinary income with capital loss
    try:
        components = ShareSaleComponents(
            lot_id="EDGE-001",
            sale_date=date.today(),
            shares_sold=100,
            sale_price=20.0,
            cost_basis=25.0,
            gross_proceeds=2000.0,
            acquisition_date=date.today() - timedelta(days=180),
            acquisition_type='exercise',
            holding_period_days=180,
            disposition_type=DispositionType.DISQUALIFYING_ISO,
            ordinary_income=500.0,
            short_term_gain=-500.0  # Mixing ordinary income with loss - invalid
        )
        print("❌ Should have rejected mixing ordinary income with capital loss")
        assert False
    except ValueError as e:
        print(f"✅ Correctly rejected: {e}")

    # Test: Zero amounts should be allowed
    try:
        components = ShareSaleComponents(
            lot_id="EDGE-002",
            sale_date=date.today(),
            shares_sold=100,
            sale_price=10.0,
            cost_basis=10.0,
            gross_proceeds=1000.0,
            acquisition_date=date.today() - timedelta(days=400),
            acquisition_type='purchase',
            holding_period_days=400,
            disposition_type=DispositionType.REGULAR_SALE,
            long_term_gain=0.0  # Zero gain is valid
        )
        print("✅ Zero gain accepted")
    except ValueError as e:
        print(f"❌ Unexpected error: {e}")
        raise


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "="*70)
    print("SHARESALECOMPONENTS VALIDATION FIX TESTS")
    print("="*70)
    print("Testing fixes for critical ISO disqualifying disposition bug")

    tests = [
        test_iso_disqualifying_with_ordinary_and_stcg,
        test_iso_disqualifying_with_ordinary_and_ltcg,
        test_iso_disqualifying_only_ordinary,
        test_iso_disqualifying_at_loss,
        test_regular_sale_validation,
        test_edge_cases
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"\n❌ Test {test.__name__} failed: {e}")
            failed += 1

    print("\n" + "="*70)
    if failed == 0:
        print("✅ ALL VALIDATION TESTS PASSED!")
        print("ISO disqualifying dispositions now correctly support multiple gain types")
    else:
        print(f"❌ {failed} tests failed")
        sys.exit(1)
    print("="*70)


if __name__ == "__main__":
    run_all_tests()
