"""
Test that 401k contributions properly reduce AGI and affect charitable deduction limits.

This test verifies that:
- 401k contributions reduce AGI
- Reduced AGI affects charitable deduction limits (30% of AGI for stock)
- Tax calculations use the reduced AGI correctly
"""

import sys
import os
from datetime import date

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import UserProfile
from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import DonationComponents


def create_test_profile(retirement_401k: float = 0) -> UserProfile:
    """Create a test user profile (uses values from user_profile_template.json)."""
    return UserProfile(
        filing_status='married_filing_jointly',
        state_of_residence='California',
        annual_w2_income=350000,
        spouse_w2_income=150000,
        other_income=0,
        retirement_contributions_401k=retirement_401k,
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        current_cash=60000,
        exercise_reserves=100000,
        pledge_percentage=0.0,
        company_match_ratio=0.0
    )


def test_401k_reduces_agi():
    """Test that 401k contributions reduce AGI."""
    print("\n" + "="*70)
    print("TEST: 401k Contributions Reduce AGI")
    print("="*70)

    calculator = AnnualTaxCalculator()

    # Test without 401k
    profile_no_401k = create_test_profile(retirement_401k=0)
    result_no_401k = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile_no_401k,
        w2_income=350000,
        spouse_income=150000
    )

    # Test with 401k (using template value)
    profile_with_401k = create_test_profile(retirement_401k=10000)
    result_with_401k = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile_with_401k,
        w2_income=350000,
        spouse_income=150000,
        retirement_contributions_401k=10000
    )

    print(f"\nWithout 401k:")
    print(f"  AGI: ${result_no_401k.adjusted_gross_income:,.0f}")

    print(f"\nWith $10k 401k:")
    print(f"  AGI: ${result_with_401k.adjusted_gross_income:,.0f}")

    print(f"\nDifference: ${result_no_401k.adjusted_gross_income - result_with_401k.adjusted_gross_income:,.0f}")

    # Verify AGI reduction
    assert result_with_401k.adjusted_gross_income == result_no_401k.adjusted_gross_income - 10000, \
        "AGI should be reduced by 401k contribution amount"

    print("✅ AGI correctly reduced by 401k contributions")


def test_401k_affects_charitable_limits():
    """Test that 401k contributions affect charitable deduction limits."""
    print("\n" + "="*70)
    print("TEST: 401k Contributions Affect Charitable Deduction Limits")
    print("="*70)

    calculator = AnnualTaxCalculator()

    # Create donation worth $200k
    donation_value = 200000
    donation_components = [
        DonationComponents(
            lot_id="TEST_LOT",
            donation_date=date(2025, 12, 1),
            shares_donated=3000,
            fmv_at_donation=66.67,
            cost_basis=10.0,
            exercise_date=date(2024, 1, 1),
            holding_period_days=700,
            donation_value=donation_value,
            deduction_type='stock',
            company_match_ratio=3.0,
            company_match_amount=600000,
            action_date=date(2025, 12, 1)
        )
    ]

    # Test without 401k
    profile_no_401k = create_test_profile(retirement_401k=0)
    result_no_401k = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile_no_401k,
        w2_income=350000,
        spouse_income=150000,
        donation_components=donation_components
    )

    # Test with 401k (using template value)
    profile_with_401k = create_test_profile(retirement_401k=10000)
    result_with_401k = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile_with_401k,
        w2_income=350000,
        spouse_income=150000,
        retirement_contributions_401k=10000,
        donation_components=donation_components
    )

    print(f"\nWithout 401k:")
    print(f"  AGI: ${result_no_401k.adjusted_gross_income:,.0f}")
    print(f"  30% limit: ${result_no_401k.adjusted_gross_income * 0.30:,.0f}")
    print(f"  Stock deduction used: ${result_no_401k.charitable_deduction_result.stock_deduction_used:,.0f}")
    print(f"  Stock carryforward: ${result_no_401k.charitable_deduction_result.stock_carryforward:,.0f}")

    print(f"\nWith $10k 401k:")
    print(f"  AGI: ${result_with_401k.adjusted_gross_income:,.0f}")
    print(f"  30% limit: ${result_with_401k.adjusted_gross_income * 0.30:,.0f}")
    print(f"  Stock deduction used: ${result_with_401k.charitable_deduction_result.stock_deduction_used:,.0f}")
    print(f"  Stock carryforward: ${result_with_401k.charitable_deduction_result.stock_carryforward:,.0f}")

    # Verify limits are correctly applied
    expected_limit_no_401k = 500000 * 0.30  # $150k
    expected_limit_with_401k = 490000 * 0.30  # $147k

    assert abs(result_no_401k.charitable_deduction_result.stock_deduction_used - expected_limit_no_401k) < 100, \
        "Stock deduction should be limited to 30% of AGI (no 401k)"

    assert abs(result_with_401k.charitable_deduction_result.stock_deduction_used - expected_limit_with_401k) < 100, \
        "Stock deduction should be limited to 30% of AGI (with 401k)"

    # Verify the deduction is lower with 401k due to lower AGI
    assert result_with_401k.charitable_deduction_result.stock_deduction_used < result_no_401k.charitable_deduction_result.stock_deduction_used, \
        "Deduction limit should be lower with 401k (lower AGI)"

    print("\n✅ Charitable deduction limits correctly affected by 401k contributions")


if __name__ == '__main__':
    test_401k_reduces_agi()
    test_401k_affects_charitable_limits()
    print("\n" + "="*70)
    print("ALL TESTS PASSED")
    print("="*70)
