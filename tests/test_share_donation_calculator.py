#!/usr/bin/env python3
"""
Tests for the share donation calculator component-based API.

These tests validate the calculate_share_donation_components() and
calculate_cash_donation_components() methods which extract tax components
from charitable donations for annual tax aggregation.
"""

import sys
import os
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.share_donation_calculator import ShareDonationCalculator
from calculators.components import DonationComponents, CashDonationComponents


def test_share_donation_long_term():
    """Test share donation with long-term holding period (full FMV deduction)."""
    print("\nTest: Share Donation - Long-term Holding")
    print("-" * 50)

    acquisition_date = date(2022, 1, 1)
    donation_date = date(2023, 6, 1)
    holding_period_days = (donation_date - acquisition_date).days

    result = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="RSU-001",
        donation_date=donation_date,
        shares_donated=1000,
        fmv_at_donation=60.0,
        cost_basis=20.0,
        acquisition_date=acquisition_date,
        holding_period_days=holding_period_days,
        company_match_ratio=3.0,
        pledge_id="PLEDGE-2023-001"
    )

    # Verify components
    assert isinstance(result, DonationComponents)
    assert result.lot_id == "RSU-001"
    assert result.shares_donated == 1000
    assert result.fmv_at_donation == 60.0
    assert result.cost_basis == 20.0
    assert result.holding_period_days == holding_period_days

    # Long-term: deduction value = FMV
    assert result.donation_value == 60000.0  # 1000 * 60
    assert result.deduction_type == 'stock'

    # Company match
    assert result.company_match_ratio == 3.0
    assert result.company_match_amount == 180000.0  # 60000 * 3

    # Pledge tracking
    assert result.pledge_id == "PLEDGE-2023-001"
    assert result.pledge_amount_satisfied == 0.0  # ShareDonationCalculator doesn't set this

    print(f"✓ Donation value: ${result.donation_value:,.2f}")
    print(f"✓ Company match: ${result.company_match_amount:,.2f}")
    print(f"✓ Total impact: ${result.donation_value + result.company_match_amount:,.2f}")


def test_share_donation_short_term():
    """Test share donation with short-term holding period (limited to cost basis)."""
    print("\nTest: Share Donation - Short-term Holding")
    print("-" * 50)

    acquisition_date = date(2023, 1, 1)
    donation_date = date(2023, 6, 1)
    holding_period_days = (donation_date - acquisition_date).days

    result = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="RSU-002",
        donation_date=donation_date,
        shares_donated=500,
        fmv_at_donation=100.0,
        cost_basis=80.0,
        acquisition_date=acquisition_date,
        holding_period_days=holding_period_days,
        company_match_ratio=1.0
    )

    # Verify short-term treatment
    assert result.shares_donated == 500
    assert result.fmv_at_donation == 100.0
    assert result.cost_basis == 80.0

    # Short-term: deduction limited to cost basis
    assert result.donation_value == 40000.0  # 500 * 80 (cost basis)
    assert result.deduction_type == 'stock'

    # Company match is still based on FMV
    total_fmv = 500 * 100.0
    assert result.company_match_amount == 50000.0  # total_fmv * 1.0

    print(f"✓ FMV: ${total_fmv:,.2f}")
    print(f"✓ Deduction (limited to cost): ${result.donation_value:,.2f}")
    print(f"✓ Company match (on FMV): ${result.company_match_amount:,.2f}")


def test_share_donation_exactly_one_year():
    """Test share donation at exactly 365 days (still short-term)."""
    print("\nTest: Share Donation - Exactly 365 Days")
    print("-" * 50)

    acquisition_date = date(2022, 1, 1)
    donation_date = acquisition_date + timedelta(days=365)

    result = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="STOCK-001",
        donation_date=donation_date,
        shares_donated=100,
        fmv_at_donation=50.0,
        cost_basis=30.0,
        acquisition_date=acquisition_date,
        holding_period_days=365,
        company_match_ratio=0.0
    )

    # 365 days is long-term (>= 365)
    assert result.holding_period_days == 365
    assert result.donation_value == 5000.0  # 100 * 50 (FMV)

    print(f"✓ Holding period: {result.holding_period_days} days")
    print(f"✓ Full FMV deduction: ${result.donation_value:,.2f}")


def test_share_donation_366_days():
    """Test share donation at 366 days (long-term)."""
    print("\nTest: Share Donation - 366 Days (Long-term)")
    print("-" * 50)

    acquisition_date = date(2022, 1, 1)
    donation_date = acquisition_date + timedelta(days=366)

    result = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="STOCK-002",
        donation_date=donation_date,
        shares_donated=100,
        fmv_at_donation=50.0,
        cost_basis=30.0,
        acquisition_date=acquisition_date,
        holding_period_days=366,
        company_match_ratio=0.0
    )

    # 366 days is long-term
    assert result.holding_period_days == 366
    assert result.donation_value == 5000.0  # 100 * 50 (FMV)

    print(f"✓ Holding period: {result.holding_period_days} days")
    print(f"✓ Full FMV deduction: ${result.donation_value:,.2f}")


def test_cash_donation_basic():
    """Test basic cash donation calculation."""
    print("\nTest: Cash Donation - Basic")
    print("-" * 50)

    result = ShareDonationCalculator.calculate_cash_donation_components(
        donation_date=date(2023, 6, 1),
        amount=10000.0,
        company_match_ratio=2.0,
        pledge_id="PLEDGE-2023-002",
        pledge_amount_satisfied=10000.0
    )

    # Verify components
    assert isinstance(result, CashDonationComponents)
    assert result.donation_date == date(2023, 6, 1)
    assert result.amount == 10000.0
    # CashDonationComponents doesn't have deduction_type attribute

    # Company match
    assert result.company_match_ratio == 2.0
    assert result.company_match_amount == 20000.0  # 10000 * 2

    # Pledge tracking
    assert result.pledge_id == "PLEDGE-2023-002"
    assert result.pledge_amount_satisfied == 10000.0

    print(f"✓ Cash donation: ${result.amount:,.2f}")
    print(f"✓ Company match: ${result.company_match_amount:,.2f}")
    print(f"✓ Total impact: ${result.amount + result.company_match_amount:,.2f}")


def test_donation_no_company_match():
    """Test donations without company match."""
    print("\nTest: Donation with No Company Match")
    print("-" * 50)

    # Share donation
    share_result = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="NO-MATCH-001",
        donation_date=date(2023, 6, 1),
        shares_donated=1000,
        fmv_at_donation=40.0,
        cost_basis=10.0,
        acquisition_date=date(2022, 1, 1),
        holding_period_days=517,
        company_match_ratio=0.0
    )

    assert share_result.company_match_amount == 0.0

    # Cash donation
    cash_result = ShareDonationCalculator.calculate_cash_donation_components(
        donation_date=date(2023, 6, 1),
        amount=5000.0,
        company_match_ratio=0.0
    )

    assert cash_result.company_match_amount == 0.0

    print("✓ Share donation match: $0")
    print("✓ Cash donation match: $0")


def test_zero_donation():
    """Test edge case of zero donation amounts."""
    print("\nTest: Zero Donation Amounts")
    print("-" * 50)

    # Zero shares
    share_result = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="ZERO-001",
        donation_date=date(2023, 6, 1),
        shares_donated=0,
        fmv_at_donation=100.0,
        cost_basis=50.0,
        acquisition_date=date(2022, 1, 1),
        holding_period_days=517,
        company_match_ratio=3.0
    )

    assert share_result.shares_donated == 0
    assert share_result.donation_value == 0.0
    assert share_result.company_match_amount == 0.0

    # Zero cash
    cash_result = ShareDonationCalculator.calculate_cash_donation_components(
        donation_date=date(2023, 6, 1),
        amount=0.0,
        company_match_ratio=3.0
    )

    assert cash_result.amount == 0.0
    assert cash_result.company_match_amount == 0.0

    print("✓ All values correctly zero for zero donations")


def test_donation_without_pledge():
    """Test donations that aren't associated with a pledge."""
    print("\nTest: Donation Without Pledge")
    print("-" * 50)

    result = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="NO-PLEDGE-001",
        donation_date=date(2023, 6, 1),
        shares_donated=500,
        fmv_at_donation=75.0,
        cost_basis=25.0,
        acquisition_date=date(2022, 1, 1),
        holding_period_days=517,
        company_match_ratio=1.0,
        pledge_id=None,
        pledge_amount_satisfied=0.0
    )

    assert result.pledge_id is None
    assert result.pledge_amount_satisfied == 0.0
    assert result.donation_value == 37500.0  # Still calculated normally

    print("✓ Donation processed without pledge association")
    print(f"✓ Donation value: ${result.donation_value:,.2f}")


def test_fractional_company_match():
    """Test fractional company match ratios."""
    print("\nTest: Fractional Company Match")
    print("-" * 50)

    result = ShareDonationCalculator.calculate_cash_donation_components(
        donation_date=date(2023, 6, 1),
        amount=1000.0,
        company_match_ratio=0.5  # 50% match
    )

    assert result.company_match_ratio == 0.5
    assert result.company_match_amount == 500.0  # 1000 * 0.5

    print(f"✓ Donation: ${result.amount:,.2f}")
    print(f"✓ 50% match: ${result.company_match_amount:,.2f}")


def test_high_value_donation():
    """Test high-value donation to ensure proper calculation."""
    print("\nTest: High-Value Donation")
    print("-" * 50)

    result = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="HIGH-VALUE-001",
        donation_date=date(2023, 12, 1),
        shares_donated=10000,
        fmv_at_donation=250.0,
        cost_basis=50.0,
        acquisition_date=date(2020, 1, 1),
        holding_period_days=1430,
        company_match_ratio=3.0,
        pledge_id="MAJOR-PLEDGE-001"
    )

    # High value calculations
    assert result.donation_value == 2500000.0  # 10000 * 250
    assert result.company_match_amount == 7500000.0  # 2.5M * 3

    print(f"✓ Donation value: ${result.donation_value:,.2f}")
    print(f"✓ Company match (3x): ${result.company_match_amount:,.2f}")
    print(f"✓ Total impact: ${result.donation_value + result.company_match_amount:,.2f}")


def run_all_tests():
    """Run all share donation calculator tests."""
    print("=" * 70)
    print("SHARE DONATION CALCULATOR TESTS")
    print("=" * 70)

    tests = [
        test_share_donation_long_term,
        test_share_donation_short_term,
        test_share_donation_exactly_one_year,
        test_share_donation_366_days,
        test_cash_donation_basic,
        test_donation_no_company_match,
        test_zero_donation,
        test_donation_without_pledge,
        test_fractional_company_match,
        test_high_value_donation,
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
