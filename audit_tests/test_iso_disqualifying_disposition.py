"""
Comprehensive tests for ISO disqualifying disposition tax calculations.

This test suite validates critical tax calculations for ISO disqualifying dispositions,
which occur when ISOs are sold before meeting both:
1. 1 year from exercise date
2. 2 years from grant date

The tax treatment is complex and involves:
- Ordinary income up to the original bargain element
- Capital gains/losses on any remaining amount
- AMT adjustment reversals
"""

import sys
import os
from datetime import date, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.share_sale_calculator import ShareSaleCalculator
from calculators.components import DispositionType


def test_basic_disqualifying_disposition():
    """Test basic disqualifying disposition with gain above bargain element."""
    print("\n" + "="*70)
    print("TEST: Basic Disqualifying Disposition")
    print("="*70)

    # ISO exercised 6 months ago
    grant_date = date(2023, 1, 1)
    exercise_date = date(2024, 1, 1)
    sale_date = date(2024, 7, 1)  # 6 months after exercise

    strike_price = 10.0
    fmv_at_exercise = 25.0
    sale_price = 40.0
    shares = 1000

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

    print(f"Grant date: {grant_date}")
    print(f"Exercise date: {exercise_date}")
    print(f"Sale date: {sale_date}")
    print(f"Days from exercise: {(sale_date - exercise_date).days}")
    print(f"Days from grant: {(sale_date - grant_date).days}")
    print(f"\nPrices:")
    print(f"  Strike price: ${strike_price}")
    print(f"  FMV at exercise: ${fmv_at_exercise}")
    print(f"  Sale price: ${sale_price}")
    print(f"\nCalculations:")
    print(f"  Original bargain element: ${(fmv_at_exercise - strike_price) * shares:,.2f}")
    print(f"  Total gain on sale: ${(sale_price - strike_price) * shares:,.2f}")
    print(f"\nTax treatment:")
    print(f"  Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"  Short-term capital gain: ${result.short_term_gain:,.2f}")
    print(f"  Long-term capital gain: ${result.long_term_gain:,.2f}")
    print(f"  AMT adjustment reversal: ${result.amt_adjustment_reversal:,.2f}")
    print(f"  Disposition type: {result.disposition_type}")

    # Verify calculations
    original_bargain_element = (fmv_at_exercise - strike_price) * shares
    total_gain = (sale_price - strike_price) * shares

    assert result.disposition_type == DispositionType.DISQUALIFYING_ISO
    assert result.is_qualifying_disposition == False
    assert result.ordinary_income == original_bargain_element  # $15,000
    assert result.short_term_gain == total_gain - original_bargain_element  # $15,000
    assert result.long_term_gain == 0  # Not held long enough
    assert result.amt_adjustment_reversal == original_bargain_element

    print("\n✅ Test passed!")


def test_disqualifying_sale_below_fmv():
    """Test disqualifying disposition when sale price is below FMV at exercise."""
    print("\n" + "="*70)
    print("TEST: Disqualifying Disposition - Sale Below FMV at Exercise")
    print("="*70)

    grant_date = date(2023, 1, 1)
    exercise_date = date(2024, 1, 1)
    sale_date = date(2024, 3, 1)  # 2 months after exercise

    strike_price = 10.0
    fmv_at_exercise = 25.0
    sale_price = 20.0  # Below FMV at exercise!
    shares = 1000

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

    print(f"Strike price: ${strike_price}")
    print(f"FMV at exercise: ${fmv_at_exercise}")
    print(f"Sale price: ${sale_price} (below FMV at exercise)")
    print(f"\nCalculations:")
    print(f"  Original bargain element: ${(fmv_at_exercise - strike_price) * shares:,.2f}")
    print(f"  Total gain on sale: ${(sale_price - strike_price) * shares:,.2f}")
    print(f"\nTax treatment:")
    print(f"  Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"  Short-term capital gain: ${result.short_term_gain:,.2f}")
    print(f"  AMT adjustment reversal: ${result.amt_adjustment_reversal:,.2f}")

    # When sale price < FMV at exercise, ordinary income is limited to actual gain
    total_gain = (sale_price - strike_price) * shares

    assert result.ordinary_income == total_gain  # Limited to $10,000
    assert result.short_term_gain == 0  # No additional gain
    assert result.amt_adjustment_reversal == total_gain

    print("\n✅ Test passed!")


def test_disqualifying_sale_at_loss():
    """Test disqualifying disposition when selling at a loss."""
    print("\n" + "="*70)
    print("TEST: Disqualifying Disposition - Sale at Loss")
    print("="*70)

    grant_date = date(2023, 1, 1)
    exercise_date = date(2024, 1, 1)
    sale_date = date(2024, 4, 1)

    strike_price = 10.0
    fmv_at_exercise = 25.0
    sale_price = 8.0  # Below strike price!
    shares = 1000

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

    print(f"Strike price: ${strike_price}")
    print(f"FMV at exercise: ${fmv_at_exercise}")
    print(f"Sale price: ${sale_price} (below strike price)")
    print(f"\nCalculations:")
    print(f"  Total loss on sale: ${(sale_price - strike_price) * shares:,.2f}")
    print(f"\nTax treatment:")
    print(f"  Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"  Short-term capital loss: ${result.short_term_gain:,.2f}")
    print(f"  AMT adjustment reversal: ${result.amt_adjustment_reversal:,.2f}")

    total_loss = (sale_price - strike_price) * shares

    # Even with a loss, there's no ordinary income
    assert result.ordinary_income == 0
    assert result.short_term_gain == total_loss  # Should be negative
    assert result.amt_adjustment_reversal == 0  # No ordinary income to reverse

    print("\n✅ Test passed!")


def test_edge_case_exactly_one_year():
    """Test disposition exactly at 1-year mark (still disqualifying due to 2-year rule)."""
    print("\n" + "="*70)
    print("TEST: Edge Case - Exactly 1 Year from Exercise")
    print("="*70)

    grant_date = date(2023, 1, 1)
    exercise_date = date(2023, 7, 1)
    sale_date = date(2024, 7, 1)  # Exactly 1 year

    strike_price = 10.0
    fmv_at_exercise = 25.0
    sale_price = 40.0
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

    days_from_exercise = (sale_date - exercise_date).days
    days_from_grant = (sale_date - grant_date).days

    print(f"Days from exercise: {days_from_exercise} (need >365)")
    print(f"Days from grant: {days_from_grant} (need >730)")
    print(f"\nTax treatment:")
    print(f"  Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"  Short-term gain: ${result.short_term_gain:,.2f}")
    print(f"  Long-term gain: ${result.long_term_gain:,.2f}")
    print(f"  Is qualifying: {result.is_qualifying_disposition}")

    # Still disqualifying because not 2 years from grant
    assert result.disposition_type == DispositionType.DISQUALIFYING_ISO
    assert result.is_qualifying_disposition == False

    # But the capital gain portion should be long-term now
    original_bargain_element = (fmv_at_exercise - strike_price) * shares
    remaining_gain = (sale_price - strike_price) * shares - original_bargain_element

    assert result.ordinary_income == original_bargain_element
    assert result.long_term_gain == remaining_gain  # Now LTCG since held >1 year
    assert result.short_term_gain == 0

    print("\n✅ Test passed!")


def test_qualifying_disposition():
    """Test qualifying disposition (meets both 1 and 2 year rules)."""
    print("\n" + "="*70)
    print("TEST: Qualifying Disposition")
    print("="*70)

    grant_date = date(2022, 1, 1)
    exercise_date = date(2022, 6, 1)
    sale_date = date(2024, 2, 1)  # >2 years from grant, >1 year from exercise

    strike_price = 10.0
    fmv_at_exercise = 25.0
    sale_price = 50.0
    shares = 1000

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="ISO-005",
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

    days_from_exercise = (sale_date - exercise_date).days
    days_from_grant = (sale_date - grant_date).days

    print(f"Days from exercise: {days_from_exercise} (>365 ✓)")
    print(f"Days from grant: {days_from_grant} (>730 ✓)")
    print(f"\nTax treatment:")
    print(f"  Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"  Long-term capital gain: ${result.long_term_gain:,.2f}")
    print(f"  Is qualifying: {result.is_qualifying_disposition}")

    # Qualifying disposition - all gain is LTCG
    total_gain = (sale_price - strike_price) * shares

    assert result.disposition_type == DispositionType.QUALIFYING_ISO
    assert result.is_qualifying_disposition == True
    assert result.ordinary_income == 0
    assert result.long_term_gain == total_gain
    assert result.amt_adjustment_reversal == 0  # No reversal for qualifying

    print("\n✅ Test passed!")


def test_missing_fmv_at_exercise():
    """Test error handling when FMV at exercise is missing for disqualifying disposition."""
    print("\n" + "="*70)
    print("TEST: Missing FMV at Exercise Error")
    print("="*70)

    grant_date = date(2023, 1, 1)
    exercise_date = date(2024, 1, 1)
    sale_date = date(2024, 3, 1)  # Disqualifying

    try:
        result = ShareSaleCalculator.calculate_sale_components(
            lot_id="ISO-006",
            sale_date=sale_date,
            shares_to_sell=1000,
            sale_price=40.0,
            cost_basis=10.0,
            exercise_date=exercise_date,
            acquisition_type='exercise',
            is_iso=True,
            grant_date=grant_date,
            exercise_date=exercise_date,
            fmv_at_exercise=None  # Missing!
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"Expected error caught: {e}")
        assert "FMV at exercise is required" in str(e)
        assert "disqualifying ISO disposition" in str(e)

    print("\n✅ Test passed!")


def test_regular_stock_sale():
    """Test that regular stock sales don't use ISO logic."""
    print("\n" + "="*70)
    print("TEST: Regular Stock Sale (Non-ISO)")
    print("="*70)

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="STOCK-001",
        sale_date=date(2024, 7, 1),
        shares_to_sell=1000,
        sale_price=40.0,
        cost_basis=10.0,
        acquisition_date=date(2023, 1, 1),
        acquisition_type='purchase',
        is_iso=False
    )

    print(f"Regular stock sale:")
    print(f"  Long-term gain: ${result.long_term_gain:,.2f}")
    print(f"  Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"  Disposition type: {result.disposition_type}")

    assert result.disposition_type == DispositionType.REGULAR_SALE
    assert result.ordinary_income == 0
    assert result.long_term_gain == 30000
    assert result.is_qualifying_disposition is None

    print("\n✅ Test passed!")


def run_all_tests():
    """Run all ISO disqualifying disposition tests."""
    print("\n" + "="*70)
    print("ISO DISQUALIFYING DISPOSITION TAX TESTS")
    print("="*70)

    test_basic_disqualifying_disposition()
    test_disqualifying_sale_below_fmv()
    test_disqualifying_sale_at_loss()
    test_edge_case_exactly_one_year()
    test_qualifying_disposition()
    test_missing_fmv_at_exercise()
    test_regular_stock_sale()

    print("\n" + "="*70)
    print("✅ All ISO disqualifying disposition tests passed!")
    print("="*70)


if __name__ == "__main__":
    run_all_tests()
