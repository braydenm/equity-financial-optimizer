#!/usr/bin/env python3
"""
Tests for the share sale calculator component-based API.

These tests validate the calculate_sale_components() method which extracts
tax components from share sales for annual tax aggregation.
"""

import sys
import os
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.share_sale_calculator import ShareSaleCalculator
from calculators.components import ShareSaleComponents, DispositionType


def test_basic_stock_sale_ltcg():
    """Test basic stock sale with long-term capital gains."""
    print("\nTest: Basic Stock Sale (LTCG)")
    print("-" * 50)

    # Sale after 1+ year = LTCG
    exercise_date = date(2022, 1, 1)
    sale_date = date(2023, 6, 1)

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="STOCK-001",
        sale_date=sale_date,
        shares_to_sell=1000,
        sale_price=50.0,
        cost_basis=20.0,
        exercise_date=exercise_date,
        # acquisition_type='purchase',
        is_iso=False
    )

    # Verify components
    assert isinstance(result, ShareSaleComponents)
    assert result.lot_id == "STOCK-001"
    assert result.shares_sold == 1000
    assert result.sale_price == 50.0
    assert result.cost_basis == 20.0
    assert result.gross_proceeds == 50000.0  # 1000 * 50
    total_gain = result.short_term_gain + result.long_term_gain
    assert total_gain == 30000.0  # 1000 * (50 - 20)
    assert result.long_term_gain == 30000.0
    assert result.short_term_gain == 0.0
    assert result.ordinary_income == 0.0

    print(f"✓ Gross proceeds: ${result.gross_proceeds:,.2f}")
    print(f"✓ Total gain: ${total_gain:,.2f}")
    print(f"✓ Long-term gain: ${result.long_term_gain:,.2f}")


def test_basic_stock_sale_stcg():
    """Test basic stock sale with short-term capital gains."""
    print("\nTest: Basic Stock Sale (STCG)")
    print("-" * 50)

    # Sale within 1 year = STCG
    exercise_date = date(2023, 1, 1)
    sale_date = date(2023, 6, 1)

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="STOCK-002",
        sale_date=sale_date,
        shares_to_sell=500,
        sale_price=30.0,
        cost_basis=25.0,
        exercise_date=exercise_date,
        # acquisition_type='purchase',
        is_iso=False
    )

    # Verify components
    assert result.shares_sold == 500
    assert result.gross_proceeds == 15000.0  # 500 * 30
    total_gain = result.short_term_gain + result.long_term_gain
    assert total_gain == 2500.0  # 500 * (30 - 25)
    assert result.short_term_gain == 2500.0
    assert result.long_term_gain == 0.0
    assert result.ordinary_income == 0.0

    print(f"✓ Gross proceeds: ${result.gross_proceeds:,.2f}")
    print(f"✓ Total gain: ${total_gain:,.2f}")
    print(f"✓ Short-term gain: ${result.short_term_gain:,.2f}")


def test_stock_sale_at_loss():
    """Test stock sale at a loss."""
    print("\nTest: Stock Sale at Loss")
    print("-" * 50)

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="STOCK-003",
        sale_date=date(2023, 6, 1),
        shares_to_sell=1000,
        sale_price=15.0,
        cost_basis=25.0,
        exercise_date=date(2022, 1, 1)
    )

    # Verify loss calculation
    assert result.gross_proceeds == 15000.0  # 1000 * 15
    total_gain = result.short_term_gain + result.long_term_gain
    assert total_gain == -10000.0  # 1000 * (15 - 25)
    assert result.long_term_gain == -10000.0  # Long-term loss
    assert result.short_term_gain == 0.0

    print(f"✓ Gross proceeds: ${result.gross_proceeds:,.2f}")
    print(f"✓ Total loss: ${total_gain:,.2f}")
    print(f"✓ Long-term loss: ${result.long_term_gain:,.2f}")


def test_iso_qualifying_disposition():
    """Test ISO qualifying disposition (held 2+ years from grant, 1+ year from exercise)."""
    print("\nTest: ISO Qualifying Disposition")
    print("-" * 50)

    grant_date = date(2020, 1, 1)
    exercise_date = date(2022, 1, 1)
    sale_date = date(2023, 6, 1)  # > 2 years from grant, > 1 year from exercise

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="ISO-001",
        sale_date=sale_date,
        shares_to_sell=1000,
        sale_price=50.0,
        cost_basis=10.0,  # Strike price
        exercise_date=exercise_date,
        # acquisition_type='exercise',
        is_iso=True,
        grant_date=grant_date,
        fmv_at_exercise=30.0
    )

    # Verify qualifying disposition
    assert result.is_qualifying_disposition == True
    assert result.disposition_type.name == "QUALIFYING_ISO"
    assert result.gross_proceeds == 50000.0
    total_gain = result.short_term_gain + result.long_term_gain
    assert total_gain == 40000.0  # 1000 * (50 - 10)
    assert result.long_term_gain == 40000.0  # All gain is LTCG
    assert result.short_term_gain == 0.0
    assert result.ordinary_income == 0.0  # No ordinary income for qualifying

    print(f"✓ Disposition type: {result.disposition_type.name}")
    print(f"✓ Total gain: ${total_gain:,.2f}")
    print(f"✓ Long-term gain: ${result.long_term_gain:,.2f}")


def test_iso_disqualifying_disposition():
    """Test ISO disqualifying disposition (sold too early)."""
    print("\nTest: ISO Disqualifying Disposition")
    print("-" * 50)

    grant_date = date(2022, 1, 1)
    exercise_date = date(2022, 6, 1)
    sale_date = date(2023, 1, 1)  # < 1 year from exercise = disqualifying

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="ISO-002",
        sale_date=sale_date,
        shares_to_sell=1000,
        sale_price=50.0,
        cost_basis=10.0,  # Strike price
        exercise_date=exercise_date,
        # acquisition_type='exercise',
        is_iso=True,
        grant_date=grant_date,
        fmv_at_exercise=30.0
    )

    # Verify disqualifying disposition
    assert result.is_qualifying_disposition == False
    assert result.disposition_type.name == "DISQUALIFYING_ISO"
    assert result.gross_proceeds == 50000.0

    # Ordinary income = min(sale price - strike, FMV at exercise - strike) * shares
    # = min(50 - 10, 30 - 10) * 1000 = min(40, 20) * 1000 = 20000
    assert result.ordinary_income == 20000.0

    # Remaining gain is STCG: (50 - 30) * 1000 = 20000
    assert result.short_term_gain == 20000.0
    assert result.long_term_gain == 0.0

    print(f"✓ Disposition type: {result.disposition_type.name}")
    print(f"✓ Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"✓ Short-term gain: ${result.short_term_gain:,.2f}")


def test_iso_disqualifying_sale_below_fmv():
    """Test ISO disqualifying disposition where sale price < FMV at exercise."""
    print("\nTest: ISO Disqualifying Sale Below FMV")
    print("-" * 50)

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="ISO-003",
        sale_date=date(2023, 1, 1),
        shares_to_sell=500,
        sale_price=25.0,  # Below FMV at exercise
        cost_basis=10.0,
        exercise_date=date(2022, 6, 1),
        # acquisition_type='exercise',
        is_iso=True,
        grant_date=date(2022, 1, 1),
        fmv_at_exercise=30.0
    )

    # When sale price < FMV at exercise, ordinary income is limited to actual gain
    # Ordinary income = (25 - 10) * 500 = 7500
    assert result.ordinary_income == 7500.0
    assert result.short_term_gain == 0.0  # No capital gain since sale < FMV
    assert result.long_term_gain == 0.0

    print(f"✓ Ordinary income: ${result.ordinary_income:,.2f}")
    print(f"✓ No capital gain (sale below FMV at exercise)")


def test_rsu_sale():
    """Test RSU sale (always has zero cost basis for employee)."""
    print("\nTest: RSU Sale")
    print("-" * 50)

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="RSU-001",
        sale_date=date(2023, 6, 1),
        shares_to_sell=1000,
        sale_price=40.0,
        cost_basis=0.0,  # RSUs typically have zero cost basis
        exercise_date=date(2022, 1, 1),
        # acquisition_type='release',
        is_iso=False
    )

    assert result.gross_proceeds == 40000.0
    total_gain = result.short_term_gain + result.long_term_gain
    assert total_gain == 40000.0  # All proceeds are gain for RSUs
    assert result.long_term_gain == 40000.0
    assert result.short_term_gain == 0.0

    print(f"✓ Gross proceeds: ${result.gross_proceeds:,.2f}")
    print(f"✓ Total gain: ${total_gain:,.2f} (100% of proceeds for RSU)")


def test_zero_shares():
    """Test edge case of selling zero shares."""
    print("\nTest: Zero Shares")
    print("-" * 50)

    result = ShareSaleCalculator.calculate_sale_components(
        lot_id="EDGE-001",
        sale_date=date(2023, 6, 1),
        shares_to_sell=0,
        sale_price=50.0,
        cost_basis=20.0,
        exercise_date=date(2022, 1, 1),
        # acquisition_type='purchase',
        is_iso=False
    )

    assert result.shares_sold == 0
    assert result.gross_proceeds == 0.0
    total_gain = result.short_term_gain + result.long_term_gain
    assert total_gain == 0.0
    assert result.long_term_gain == 0.0
    assert result.short_term_gain == 0.0

    print("✓ All values correctly zero for zero shares")


def test_holding_period_edge_cases():
    """Test edge cases around the 1-year holding period boundary."""
    print("\nTest: Holding Period Edge Cases")
    print("-" * 50)

    exercise_date = date(2022, 1, 1)

    # Exactly 365 days = still STCG
    sale_date_365 = exercise_date + timedelta(days=365)
    result_365 = ShareSaleCalculator.calculate_sale_components(
        lot_id="EDGE-002",
        sale_date=sale_date_365,
        shares_to_sell=100,
        sale_price=30.0,
        cost_basis=20.0,
        exercise_date=exercise_date,
        # acquisition_type='purchase',
        is_iso=False
    )

    assert result_365.holding_period_days == 365
    assert result_365.short_term_gain == 1000.0  # Still short-term
    assert result_365.long_term_gain == 0.0

    print(f"✓ 365 days: Still STCG (gain: ${result_365.short_term_gain:,.2f})")

    # 366 days = LTCG
    sale_date_366 = exercise_date + timedelta(days=366)
    result_366 = ShareSaleCalculator.calculate_sale_components(
        lot_id="EDGE-003",
        sale_date=sale_date_366,
        shares_to_sell=100,
        sale_price=30.0,
        cost_basis=20.0,
        exercise_date=exercise_date,
        # acquisition_type='purchase',
        is_iso=False
    )

    assert result_366.holding_period_days == 366
    assert result_366.long_term_gain == 1000.0  # Now long-term
    assert result_366.short_term_gain == 0.0

    print(f"✓ 366 days: Now LTCG (gain: ${result_366.long_term_gain:,.2f})")


def run_all_tests():
    """Run all share sale calculator tests."""
    print("=" * 70)
    print("SHARE SALE CALCULATOR TESTS")
    print("=" * 70)

    tests = [
        test_basic_stock_sale_ltcg,
        test_basic_stock_sale_stcg,
        test_stock_sale_at_loss,
        test_iso_qualifying_disposition,
        test_iso_disqualifying_disposition,
        test_iso_disqualifying_sale_below_fmv,
        test_rsu_sale,
        test_zero_shares,
        test_holding_period_edge_cases,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAILED: {test_func.__name__}")
            print(f"   {str(e)}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR in {test_func.__name__}: {type(e).__name__}: {str(e)}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")

    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"❌ {failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
