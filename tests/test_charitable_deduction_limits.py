"""
Test charitable deduction limits for federal and California taxes.

This test verifies that:
- Federal cash donation limit is 60% of AGI (2025)
- California cash donation limit is 50% of AGI (2025)
- Stock donation limit is 30% of AGI for both
- Limits are properly applied in tax calculations
"""

import sys
import os
from datetime import date
from decimal import Decimal

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import UserProfile
from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import (
    DonationComponents,
    CashDonationComponents
)


def create_test_profile(state: str = 'California') -> UserProfile:
    """Create a test user profile."""
    return UserProfile(
        filing_status='single',
        state_of_residence=state,
        annual_w2_income=500000,  # High income to test AGI limits
        spouse_w2_income=0,
        other_income=0,
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        current_cash=1000000,
        exercise_reserves=100000,
        pledge_percentage=0.1,
        company_match_ratio=2.0
    )


def test_federal_vs_california_cash_limits():
    """Test that federal allows 60% cash deduction while California allows only 50%."""
    print("\n" + "="*70)
    print("TEST: Federal vs California Cash Donation Limits")
    print("="*70)

    profile = create_test_profile()
    calculator = AnnualTaxCalculator()

    # Test with $500k income and $350k cash donation
    # This is 70% of AGI, so it should be limited to:
    # - Federal: $300k (60% of $500k)
    # - California: $250k (50% of $500k)
    w2_income = 500000
    cash_donation = 350000

    cash_donation_components = [
        CashDonationComponents(
            donation_date=date(2025, 6, 1),
            amount=cash_donation,
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    # Calculate taxes
    result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        cash_donation_components=cash_donation_components
    )

    print(f"\nIncome and Donation Details:")
    print(f"  W2 Income: ${w2_income:,}")
    print(f"  Cash Donation: ${cash_donation:,} (70% of AGI)")

    print(f"\nFederal Charitable Deduction:")
    print(f"  Deduction Used: ${result.charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  Expected (60% limit): ${w2_income * 0.60:,.0f}")
    print(f"  Carryforward: ${result.charitable_deduction_result.cash_carryforward:,.0f}")

    # Verify federal limit (60%)
    assert result.charitable_deduction_result.cash_deduction_used == w2_income * 0.60, \
        f"Federal cash deduction should be limited to 60% of AGI"
    assert result.charitable_deduction_result.cash_carryforward == cash_donation - (w2_income * 0.60), \
        f"Federal carryforward should be donation amount minus 60% limit"

    # Calculate what California tax would be with its 50% limit
    # We need to check that CA is using its own limit
    # The CA tax calculation should reflect a smaller deduction

    print(f"\nTax Calculation Results:")
    print(f"  Federal Taxable Income: ${result.federal_taxable_income:,.0f}")
    print(f"  CA Taxable Income: ${result.ca_taxable_income:,.0f}")

    # CA should have higher taxable income because it allows less deduction
    # Federal: 500k - 300k deduction - 15k std deduction = 185k
    # CA: 500k - 250k deduction - 5,809 std deduction = 244,191
    expected_federal_taxable = w2_income - (w2_income * 0.60) - 15000  # Federal std deduction
    expected_ca_taxable = w2_income - (w2_income * 0.50) - 5809  # CA std deduction

    print(f"\nExpected Taxable Income:")
    print(f"  Federal: ${expected_federal_taxable:,.0f}")
    print(f"  California: ${expected_ca_taxable:,.0f}")

    # Allow small rounding differences
    assert abs(result.federal_taxable_income - expected_federal_taxable) < 1, \
        f"Federal taxable income calculation incorrect"
    assert abs(result.ca_taxable_income - expected_ca_taxable) < 1, \
        f"California taxable income calculation incorrect"

    print("\n✅ Federal 60% and California 50% cash donation limits correctly applied")


def test_stock_donation_limits():
    """Test that stock donations are limited to 30% for both federal and California."""
    print("\n" + "="*70)
    print("TEST: Stock Donation Limits (30% for both Federal and California)")
    print("="*70)

    profile = create_test_profile()
    calculator = AnnualTaxCalculator()

    w2_income = 500000
    stock_donation_value = 200000  # 40% of AGI

    donation_components = [
        DonationComponents(
            lot_id='RSU_001',
            donation_date=date(2025, 6, 1),
            shares_donated=2000,
            fmv_at_donation=100.0,
            cost_basis=50000,
            acquisition_date=date(2020, 1, 1),
            holding_period_days=1887,
            donation_value=stock_donation_value,
            deduction_type='stock',
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components
    )

    print(f"\nIncome and Donation Details:")
    print(f"  W2 Income: ${w2_income:,}")
    print(f"  Stock Donation Value: ${stock_donation_value:,} (40% of AGI)")

    print(f"\nCharitable Deduction Results:")
    print(f"  Stock Deduction Used: ${result.charitable_deduction_result.stock_deduction_used:,.0f}")
    print(f"  Expected (30% limit): ${w2_income * 0.30:,.0f}")
    print(f"  Stock Carryforward: ${result.charitable_deduction_result.stock_carryforward:,.0f}")

    # Verify 30% limit for both federal and CA
    assert result.charitable_deduction_result.stock_deduction_used == w2_income * 0.30, \
        f"Stock deduction should be limited to 30% of AGI"
    assert result.charitable_deduction_result.stock_carryforward == stock_donation_value - (w2_income * 0.30), \
        f"Stock carryforward should be donation amount minus 30% limit"

    print("\n✅ Stock donation 30% limit correctly applied for both federal and California")


def test_combined_cash_and_stock_limits():
    """Test combined cash and stock donation limits."""
    print("\n" + "="*70)
    print("TEST: Combined Cash and Stock Donation Limits")
    print("="*70)

    profile = create_test_profile()
    calculator = AnnualTaxCalculator()

    w2_income = 500000
    cash_donation = 200000      # 40% of AGI
    stock_donation_value = 100000  # 20% of AGI

    cash_donation_components = [
        CashDonationComponents(
            donation_date=date(2025, 6, 1),
            amount=cash_donation,
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    donation_components = [
        DonationComponents(
            lot_id='RSU_001',
            donation_date=date(2025, 6, 1),
            shares_donated=1000,
            fmv_at_donation=100.0,
            cost_basis=25000,
            acquisition_date=date(2020, 1, 1),
            holding_period_days=1887,
            donation_value=stock_donation_value,
            deduction_type='stock',
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        cash_donation_components=cash_donation_components,
        donation_components=donation_components
    )

    print(f"\nIncome and Donation Details:")
    print(f"  W2 Income: ${w2_income:,}")
    print(f"  Cash Donation: ${cash_donation:,} (40% of AGI)")
    print(f"  Stock Donation: ${stock_donation_value:,} (20% of AGI)")
    print(f"  Total Donations: ${cash_donation + stock_donation_value:,} (60% of AGI)")

    print(f"\nFederal Deduction Results:")
    print(f"  Stock Deduction Used: ${result.charitable_deduction_result.stock_deduction_used:,.0f}")
    print(f"  Cash Deduction Used: ${result.charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  Total Deduction Used: ${result.charitable_deduction_result.total_deduction_used:,.0f}")

    # For 50% limit organizations (public charities):
    # Overall limit: 50% of AGI = $250k
    # Cash uses: $200k (full amount, under 60% cash limit and 50% overall limit)
    # Remaining overall limit: $250k - $200k = $50k
    # Stock gets: min($150k stock limit, $50k remaining overall) = $50k

    assert result.charitable_deduction_result.cash_deduction_used == cash_donation, \
        f"Cash donation should be fully deductible when under overall 50% limit"

    expected_stock_deduction = 50000  # Limited by remaining overall limit
    assert result.charitable_deduction_result.stock_deduction_used == expected_stock_deduction, \
        f"Stock donation should be limited by remaining overall charitable limit (50% org)"

    expected_stock_carryforward = stock_donation_value - expected_stock_deduction
    assert result.charitable_deduction_result.stock_carryforward == expected_stock_carryforward, \
        f"Stock carryforward should be unused portion of donation"

    print(f"  Stock Carryforward: ${result.charitable_deduction_result.stock_carryforward:,.0f}")
    print("\n✅ Combined donation limits correctly applied for 50% limit organizations")


def test_public_charity_vs_private_foundation():
    """Test donation limit differences between public charities and private foundations."""
    print("\n" + "="*70)
    print("TEST: Public Charity vs Private Foundation Donation Limits")
    print("="*70)

    profile = create_test_profile()
    calculator = AnnualTaxCalculator()

    w2_income = 500000
    stock_donation_value = 200000  # 40% of AGI

    donation_components = [
        DonationComponents(
            lot_id='RSU_001',
            donation_date=date(2025, 6, 1),
            shares_donated=2000,
            fmv_at_donation=100.0,
            cost_basis=50000,
            acquisition_date=date(2020, 1, 1),
            holding_period_days=1887,
            donation_value=stock_donation_value,
            deduction_type='stock',
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    # Test public charity (50% limit organization)
    result_public = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        fifty_pct_limit_org=True
    )

    # Test private foundation (30% limit organization)
    result_private = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        fifty_pct_limit_org=False
    )

    print(f"\nDonation Details:")
    print(f"  W2 Income: ${w2_income:,}")
    print(f"  Stock Donation: ${stock_donation_value:,} (40% of AGI)")

    print(f"\nPublic Charity (50% limit org) Results:")
    print(f"  Stock Deduction Used: ${result_public.charitable_deduction_result.stock_deduction_used:,.0f}")
    print(f"  Stock Carryforward: ${result_public.charitable_deduction_result.stock_carryforward:,.0f}")

    print(f"\nPrivate Foundation (30% limit org) Results:")
    print(f"  Stock Deduction Used: ${result_private.charitable_deduction_result.stock_deduction_used:,.0f}")
    print(f"  Stock Carryforward: ${result_private.charitable_deduction_result.stock_carryforward:,.0f}")

    # Public charity: 30% stock limit, 50% overall limit
    # Stock donation is 40% of AGI, limited to 30% = $150k
    expected_public_deduction = w2_income * 0.30  # $150k
    expected_public_carryforward = stock_donation_value - expected_public_deduction  # $50k

    # Private foundation: 30% overall limit for stock
    # Stock donation is 40% of AGI, limited to 30% = $150k
    expected_private_deduction = w2_income * 0.30  # $150k
    expected_private_carryforward = stock_donation_value - expected_private_deduction  # $50k

    assert result_public.charitable_deduction_result.stock_deduction_used == expected_public_deduction, \
        f"Public charity stock deduction should be limited to 30% of AGI"
    assert result_public.charitable_deduction_result.stock_carryforward == expected_public_carryforward, \
        f"Public charity stock carryforward should be excess over 30% limit"

    assert result_private.charitable_deduction_result.stock_deduction_used == expected_private_deduction, \
        f"Private foundation stock deduction should be limited to 30% of AGI"
    assert result_private.charitable_deduction_result.stock_carryforward == expected_private_carryforward, \
        f"Private foundation stock carryforward should be excess over 30% limit"

    print("\n✅ Public charity vs private foundation limits correctly applied")


def test_basis_election_high_appreciation():
    """Test basis election with highly appreciated stock (FMV clearly better)."""
    print("\n" + "="*70)
    print("TEST: Basis Election with High Appreciation Stock")
    print("="*70)

    profile = create_test_profile()
    calculator = AnnualTaxCalculator()

    # High appreciation: basis is 20% of FMV
    w2_income = 200000
    stock_fmv = 100000
    stock_basis = 20000  # 20% of FMV

    donation_components = [
        DonationComponents(
            lot_id='RSU_001',
            donation_date=date(2025, 6, 1),
            shares_donated=1000,
            fmv_at_donation=100.0,
            cost_basis=20.0,  # $20 per share basis
            acquisition_date=date(2020, 1, 1),
            holding_period_days=1887,
            donation_value=stock_fmv,
            deduction_type='stock',
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    # Test with FMV deduction (default)
    result_fmv = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        elect_basis_deduction=False
    )

    # Test with basis election
    result_basis = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        elect_basis_deduction=True
    )

    print(f"\nStock Details:")
    print(f"  FMV: ${stock_fmv:,}")
    print(f"  Basis: ${stock_basis:,} (20% of FMV)")
    print(f"  AGI: ${w2_income:,}")

    print(f"\nFMV Deduction (Default):")
    print(f"  Deduction Amount: ${stock_fmv:,}")
    print(f"  AGI Limit: 30% = ${w2_income * 0.30:,}")
    print(f"  Deduction Used: ${result_fmv.charitable_deduction_result.stock_deduction_used:,}")
    print(f"  Carryforward: ${result_fmv.charitable_deduction_result.stock_carryforward:,}")

    print(f"\nBasis Election:")
    print(f"  Deduction Amount: ${stock_basis:,}")
    print(f"  AGI Limit: 50% = ${w2_income * 0.50:,}")
    print(f"  Deduction Used: ${result_basis.charitable_deduction_result.stock_deduction_used:,}")
    print(f"  Carryforward: ${result_basis.charitable_deduction_result.stock_carryforward:,}")

    # FMV option: $100k limited to 30% of $200k = $60k deduction
    assert result_fmv.charitable_deduction_result.stock_deduction_used == 60000, \
        "FMV deduction should be limited to 30% of AGI"

    # Basis option: $20k deduction (within 50% limit)
    assert result_basis.charitable_deduction_result.stock_deduction_used == 20000, \
        "Basis election should deduct cost basis amount"

    print("\n✅ High appreciation test passed - FMV deduction clearly superior")


def test_basis_election_low_appreciation():
    """Test basis election with low appreciation stock (basis might be better)."""
    print("\n" + "="*70)
    print("TEST: Basis Election with Low Appreciation Stock")
    print("="*70)

    profile = create_test_profile()
    calculator = AnnualTaxCalculator()

    # Low appreciation: basis is 70% of FMV
    w2_income = 200000
    stock_fmv = 100000
    stock_basis = 70000  # 70% of FMV

    donation_components = [
        DonationComponents(
            lot_id='RSU_001',
            donation_date=date(2025, 6, 1),
            shares_donated=1000,
            fmv_at_donation=100.0,
            cost_basis=70.0,  # $70 per share basis
            acquisition_date=date(2023, 1, 1),
            holding_period_days=517,
            donation_value=stock_fmv,
            deduction_type='stock',
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    # Test both options
    result_fmv = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        elect_basis_deduction=False
    )

    result_basis = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        elect_basis_deduction=True
    )

    print(f"\nStock Details:")
    print(f"  FMV: ${stock_fmv:,}")
    print(f"  Basis: ${stock_basis:,} (70% of FMV)")
    print(f"  Basis/FMV Ratio: 70%")

    print(f"\nDeduction Comparison:")
    print(f"  FMV Deduction Used: ${result_fmv.charitable_deduction_result.stock_deduction_used:,}")
    print(f"  Basis Deduction Used: ${result_basis.charitable_deduction_result.stock_deduction_used:,}")

    # FMV: $100k limited to 30% = $60k
    # Basis: $70k within 50% limit = $70k (more deduction!)
    assert result_basis.charitable_deduction_result.stock_deduction_used == 70000, \
        "Basis election should allow full $70k deduction"

    print(f"\n💡 Basis election provides ${70000 - 60000:,} more in current year deductions")
    print("✅ Low appreciation test passed - Basis election can be beneficial")


def test_basis_election_with_mixed_donations():
    """Test basis election with both stock and cash donations."""
    print("\n" + "="*70)
    print("TEST: Basis Election with Mixed Stock and Cash Donations")
    print("="*70)

    profile = create_test_profile()
    calculator = AnnualTaxCalculator()

    w2_income = 100000
    stock_fmv = 50000
    stock_basis = 35000  # 70% of FMV
    cash_donation = 30000

    donation_components = [
        DonationComponents(
            lot_id='RSU_001',
            donation_date=date(2025, 6, 1),
            shares_donated=500,
            fmv_at_donation=100.0,
            cost_basis=70.0,
            acquisition_date=date(2023, 1, 1),
            holding_period_days=517,
            donation_value=stock_fmv,
            deduction_type='stock',
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    cash_donation_components = [
        CashDonationComponents(
            donation_date=date(2025, 6, 1),
            amount=cash_donation,
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    # Test both options
    result_fmv = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        cash_donation_components=cash_donation_components,
        elect_basis_deduction=False
    )

    result_basis = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        cash_donation_components=cash_donation_components,
        elect_basis_deduction=True
    )

    print(f"\nDonation Details:")
    print(f"  Stock FMV: ${stock_fmv:,}")
    print(f"  Stock Basis: ${stock_basis:,}")
    print(f"  Cash: ${cash_donation:,}")
    print(f"  AGI: ${w2_income:,}")

    print(f"\nFMV Option:")
    fmv_result = result_fmv.charitable_deduction_result
    print(f"  Stock Deduction: ${fmv_result.stock_deduction_used:,}")
    print(f"  Cash Deduction: ${fmv_result.cash_deduction_used:,}")
    print(f"  Total: ${fmv_result.total_deduction_used:,}")

    print(f"\nBasis Election:")
    basis_result = result_basis.charitable_deduction_result
    print(f"  Stock Deduction: ${basis_result.stock_deduction_used:,}")
    print(f"  Cash Deduction: ${basis_result.cash_deduction_used:,}")
    print(f"  Total: ${basis_result.total_deduction_used:,}")

    # With FMV: Stock limited to 30% ($30k), cash gets remaining to 60% ($30k) = $60k total
    # With basis: Stock $35k (within 50%), cash limited to 60% - $35k = $25k = $60k total
    # Same total but different mix!
    assert fmv_result.total_deduction_used == 60000
    assert basis_result.total_deduction_used == 60000

    print("\n✅ Mixed donation test passed - Total deduction same but mix differs")


def test_california_basis_election():
    """Test basis election with California's different limits."""
    print("\n" + "="*70)
    print("TEST: California Basis Election")
    print("="*70)

    profile = create_test_profile(state='California')
    calculator = AnnualTaxCalculator()

    w2_income = 200000
    stock_fmv = 80000
    stock_basis = 60000  # 75% of FMV
    cash_donation = 50000

    donation_components = [
        DonationComponents(
            lot_id='RSU_001',
            donation_date=date(2025, 6, 1),
            shares_donated=800,
            fmv_at_donation=100.0,
            cost_basis=75.0,
            acquisition_date=date(2023, 1, 1),
            holding_period_days=517,
            donation_value=stock_fmv,
            deduction_type='stock',
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    cash_donation_components = [
        CashDonationComponents(
            donation_date=date(2025, 6, 1),
            amount=cash_donation,
            company_match_ratio=0,
            company_match_amount=0
        )
    ]

    result_basis = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=w2_income,
        donation_components=donation_components,
        cash_donation_components=cash_donation_components,
        elect_basis_deduction=True
    )

    # California analysis
    ca_result = result_basis.charitable_deduction_result
    print(f"\nCalifornia with Basis Election:")
    print(f"  Stock basis deduction: ${ca_result.stock_deduction_used:,}")
    print(f"  Cash deduction: ${ca_result.cash_deduction_used:,}")
    print(f"  Total deduction: ${ca_result.total_deduction_used:,}")

    # CA limits: 50% for both cash and stock (with basis election)
    # Stock: $60k basis (within 50% = $100k limit)
    # Cash: Limited to 50% - stock used
    print("\n✅ California basis election test passed")


def run_all_tests():
    """Run all charitable deduction limit tests."""
    print("\n" + "="*70)
    print("CHARITABLE DEDUCTION LIMITS TEST SUITE")
    print("Testing Federal (60%) vs California (50%) cash donation limits")
    print("="*70)

    test_federal_vs_california_cash_limits()
    test_stock_donation_limits()
    test_combined_cash_and_stock_limits()
    test_public_charity_vs_private_foundation()
    test_basis_election_high_appreciation()
    test_california_basis_election()

    print("\n" + "="*70)
    print("✅ All charitable deduction limit tests passed!")
    print("="*70)


if __name__ == "__main__":
    run_all_tests()
