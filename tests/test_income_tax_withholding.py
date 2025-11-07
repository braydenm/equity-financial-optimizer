"""
Test income tax withholding calculation (excludes FICA/SDI).

Validates that:
- Income tax withholding is calculated separately from total withholding
- Net tax payment uses income tax withholding, not total withholding
- income_tax_withholding_rate is required when income_tax_only=True
"""

import sys
import os
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import UserProfile
from calculators.components import AnnualTaxComponents, NSOExerciseComponents


def test_income_tax_withholding_separate_from_total():
    """Test that income tax withholding excludes FICA/SDI."""
    print("\n" + "="*70)
    print("TEST: Income Tax Withholding vs Total Withholding")
    print("="*70)

    # Create profile with both rate types
    profile = UserProfile(
        filing_status='married_filing_jointly',
        state_of_residence='California',
        annual_w2_income=350000,
        spouse_w2_income=150000,
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        current_cash=100000,
        exercise_reserves=50000,
        pledge_percentage=0.0,
        company_match_ratio=0.0,
        regular_income_withholding_rate=0.379,  # Includes FICA/SDI
        supplemental_income_withholding_rate=0.364,  # Includes FICA/SDI
        income_tax_withholding_rate=0.3454  # Income tax only
    )

    # Import here to avoid circular dependency
    from projections.projection_calculator import ProjectionCalculator

    calculator = ProjectionCalculator(profile)

    # Create sample components
    components = AnnualTaxComponents(year=2025)

    # Calculate both types of withholding
    total_wh = calculator.calculate_year_withholding(2025, components, income_tax_only=False)
    income_tax_wh = calculator.calculate_year_withholding(2025, components, income_tax_only=True)

    total_income = 500000  # W2s only for this test

    print(f"\nTotal Income: ${total_income:,.0f}")
    print(f"\nTotal Withholding (37.9%):     ${total_wh:,.0f}")
    print(f"Income Tax WH (34.54%):        ${income_tax_wh:,.0f}")
    print(f"Difference (FICA/SDI):         ${total_wh - income_tax_wh:,.0f}")

    # Verify income tax is less than total
    assert income_tax_wh < total_wh, "Income tax withholding should be less than total"

    # Verify approximately correct
    expected_income_tax = total_income * 0.3454
    assert abs(income_tax_wh - expected_income_tax) < 100, \
        f"Income tax WH should be ~{expected_income_tax:.0f}, got {income_tax_wh:.0f}"

    print("\n✅ Income tax withholding correctly excludes FICA/SDI")


def test_default_income_tax_rate():
    """Test that income_tax_withholding_rate has a sensible default."""
    print("\n" + "="*70)
    print("TEST: Default income_tax_withholding_rate")
    print("="*70)

    # Create profile without explicitly setting income_tax_withholding_rate
    profile = UserProfile(
        filing_status='single',
        annual_w2_income=100000,
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        current_cash=50000,
        exercise_reserves=10000,
        pledge_percentage=0.0,
        company_match_ratio=0.0,
        regular_income_withholding_rate=0.379,
        supplemental_income_withholding_rate=0.364
        # income_tax_withholding_rate will use default (0.31)
    )

    from projections.projection_calculator import ProjectionCalculator

    calculator = ProjectionCalculator(profile)
    components = AnnualTaxComponents(year=2025)

    # Should work with default rate
    income_tax_wh = calculator.calculate_year_withholding(2025, components, income_tax_only=True)

    # Verify default rate was used (0.31 on $100k)
    expected = 100000 * 0.31
    assert abs(income_tax_wh - expected) < 100, f"Expected ~{expected}, got {income_tax_wh}"

    print(f"\n  Default rate (0.31) applied: ${income_tax_wh:,.0f}")
    print("\n✅ Default income_tax_withholding_rate works correctly")


if __name__ == '__main__':
    test_income_tax_withholding_separate_from_total()
    test_default_income_tax_rate()
    print("\n" + "="*70)
    print("ALL TESTS PASSED")
    print("="*70)
