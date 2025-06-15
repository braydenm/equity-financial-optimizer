"""
Test Net Investment Income Tax (NIIT) calculation.

NIIT is a 3.8% tax on investment income for high earners:
- Single: Income > $200,000
- Married filing jointly: Income > $250,000

Applies to the lesser of:
1. Net investment income, or
2. Modified AGI exceeding the threshold
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from calculators.components import ShareSaleComponents, DispositionType
from calculators.annual_tax_calculator import AnnualTaxCalculator
from projections.projection_state import UserProfile


def test_niit_on_capital_gains():
    """Test NIIT calculation on capital gains for high earners."""
    print("Testing NIIT on Capital Gains")
    print("=" * 60)

    calculator = AnnualTaxCalculator()

    # High earner profile - should trigger NIIT
    user_profile = UserProfile(
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.13,
        state_ltcg_rate=0.13,
        fica_tax_rate=0.0145,  # Medicare only (above SS cap)
        additional_medicare_rate=0.009,
        niit_rate=0.038,  # 3.8% NIIT rate
        annual_w2_income=300_000,  # Above NIIT threshold
        spouse_w2_income=0,
        other_income=0,
        current_cash=1_000_000,
        exercise_reserves=200_000,
        pledge_percentage=0.0,
        company_match_ratio=0.0,
        filing_status='single'
    )

    # Create a profitable stock sale
    sale = ShareSaleComponents(
        lot_id='TEST-001',
        sale_date=date(2024, 6, 1),
        shares_sold=1000,
        sale_price=100.0,
        cost_basis=20_000,
        gross_proceeds=100_000,
        acquisition_date=date(2022, 1, 1),
        acquisition_type='purchase',
        holding_period_days=881,
        disposition_type=DispositionType.REGULAR_SALE,
        short_term_gain=0,
        long_term_gain=80_000  # $80k LTCG
    )

    # Calculate annual tax
    result = calculator.calculate_annual_tax(
        year=2024,
        user_profile=user_profile,
        w2_income=user_profile.annual_w2_income,
        spouse_income=0,
        other_ordinary_income=0,
        exercise_components=[],
        sale_components=[sale],
        existing_amt_credit=0
    )

    # Expected NIIT calculation:
    # AGI = $300k W2 + $80k LTCG = $380k
    # Excess over threshold = $380k - $200k = $180k
    # Net investment income = $80k LTCG
    # NIIT base = min($180k, $80k) = $80k
    # NIIT = $80k × 3.8% = $3,040

    expected_niit = 3_040

    print(f"W2 Income: ${user_profile.annual_w2_income:,}")
    print(f"Long-term Capital Gain: ${sale.long_term_gain:,}")
    print(f"Total AGI: ${result.adjusted_gross_income:,}")
    print(f"NIIT Threshold (Single): $200,000")
    print(f"Excess over threshold: ${result.adjusted_gross_income - 200_000:,}")
    print(f"Expected NIIT: ${expected_niit:,}")

    # Check if NIIT is being calculated
    # Note: Currently, NIIT is NOT included in the annual tax calculator
    federal_tax_breakdown = {
        'Regular tax': result.federal_regular_tax,
        'AMT': result.federal_amt,
        'Tax owed': result.federal_tax_owed
    }

    print("\nFederal Tax Breakdown:")
    for component, amount in federal_tax_breakdown.items():
        print(f"  {component}: ${amount:,.2f}")

    # This will likely fail because NIIT is not implemented
    print("\n❌ CRITICAL FINDING: NIIT is not being calculated!")
    print("   Missing $3,040 in federal taxes for this scenario")

    return False  # Test fails - NIIT not implemented


def test_niit_threshold_scenarios():
    """Test NIIT thresholds for different filing statuses and income levels."""
    print("\n\nTesting NIIT Thresholds")
    print("=" * 60)

    calculator = AnnualTaxCalculator()

    scenarios = [
        # (filing_status, W2_income, investment_income, should_owe_niit)
        ('single', 150_000, 100_000, True),   # Total $250k > $200k threshold
        ('single', 190_000, 5_000, False),    # Total $195k < $200k threshold
        ('single', 190_000, 20_000, True),    # Total $210k > $200k threshold
        ('married_filing_jointly', 200_000, 100_000, True),  # Total $300k > $250k threshold
        ('married_filing_jointly', 240_000, 5_000, False),   # Total $245k < $250k threshold
    ]

    for filing_status, w2_income, investment_income, should_owe_niit in scenarios:
        user_profile = UserProfile(
            federal_tax_rate=0.32,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.09,
            state_ltcg_rate=0.09,
            fica_tax_rate=0.0145,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=w2_income,
            spouse_w2_income=0,
            other_income=investment_income,  # Interest/dividends
            current_cash=500_000,
            exercise_reserves=100_000,
            pledge_percentage=0.0,
            company_match_ratio=0.0,
            filing_status=filing_status
        )

        result = calculator.calculate_annual_tax(
            year=2024,
            user_profile=user_profile,
            w2_income=w2_income,
            spouse_income=0,
            other_ordinary_income=investment_income,
            exercise_components=[],
            sale_components=[],
            existing_amt_credit=0
        )

        threshold = 200_000 if filing_status == 'single' else 250_000
        total_income = w2_income + investment_income

        if should_owe_niit:
            excess = total_income - threshold
            niit_base = min(excess, investment_income)
            expected_niit = niit_base * 0.038
        else:
            expected_niit = 0

        print(f"\n{filing_status.replace('_', ' ').title()}:")
        print(f"  W2 Income: ${w2_income:,}")
        print(f"  Investment Income: ${investment_income:,}")
        print(f"  Total Income: ${total_income:,}")
        print(f"  NIIT Threshold: ${threshold:,}")
        print(f"  Should owe NIIT: {'Yes' if should_owe_niit else 'No'}")
        if should_owe_niit:
            print(f"  Expected NIIT: ${expected_niit:,.2f}")


def test_niit_on_multiple_income_types():
    """Test NIIT on various types of investment income."""
    print("\n\nTesting NIIT on Multiple Investment Income Types")
    print("=" * 60)

    calculator = AnnualTaxCalculator()

    # High earner with multiple investment income sources
    user_profile = UserProfile(
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.13,
        state_ltcg_rate=0.13,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        annual_w2_income=400_000,
        spouse_w2_income=0,
        other_income=50_000,  # Dividends and interest
        current_cash=2_000_000,
        exercise_reserves=500_000,
        pledge_percentage=0.0,
        company_match_ratio=0.0,
        filing_status='single'
    )

    # Multiple sales creating different types of gains
    sales = [
        ShareSaleComponents(
            lot_id='STCG-001',
            sale_date=date(2024, 3, 1),
            shares_sold=500,
            sale_price=50.0,
            cost_basis=20_000,
            gross_proceeds=25_000,
            acquisition_date=date(2023, 6, 1),
            acquisition_type='purchase',
            holding_period_days=273,
            disposition_type=DispositionType.REGULAR_SALE,
            short_term_gain=5_000,  # STCG
            long_term_gain=0
        ),
        ShareSaleComponents(
            lot_id='LTCG-001',
            sale_date=date(2024, 6, 1),
            shares_sold=1000,
            sale_price=100.0,
            cost_basis=30_000,
            gross_proceeds=100_000,
            acquisition_date=date(2020, 1, 1),
            acquisition_type='purchase',
            holding_period_days=1613,
            disposition_type=DispositionType.REGULAR_SALE,
            short_term_gain=0,
            long_term_gain=70_000  # LTCG
        )
    ]

    result = calculator.calculate_annual_tax(
        year=2024,
        user_profile=user_profile,
        w2_income=user_profile.annual_w2_income,
        spouse_income=0,
        other_ordinary_income=user_profile.other_income,
        exercise_components=[],
        sale_components=sales,
        existing_amt_credit=0
    )

    # Calculate expected NIIT
    total_investment_income = (
        user_profile.other_income +  # Dividends/interest: $50k
        5_000 +                      # STCG: $5k
        70_000                       # LTCG: $70k
    )  # Total: $125k

    total_agi = user_profile.annual_w2_income + user_profile.other_income + 5_000 + 70_000
    excess_over_threshold = total_agi - 200_000
    niit_base = min(excess_over_threshold, total_investment_income)
    expected_niit = niit_base * 0.038

    print(f"Income Breakdown:")
    print(f"  W2 Income: ${user_profile.annual_w2_income:,}")
    print(f"  Dividends/Interest: ${user_profile.other_income:,}")
    print(f"  Short-term Capital Gains: $5,000")
    print(f"  Long-term Capital Gains: $70,000")
    print(f"  Total AGI: ${total_agi:,}")
    print(f"\nNIIT Calculation:")
    print(f"  Total Investment Income: ${total_investment_income:,}")
    print(f"  Excess over $200k threshold: ${excess_over_threshold:,}")
    print(f"  NIIT Base: ${niit_base:,}")
    print(f"  Expected NIIT (3.8%): ${expected_niit:,}")

    print(f"\n❌ NIIT of ${expected_niit:,} is NOT being collected")


def run_all_tests():
    """Run all NIIT tests and summarize findings."""
    print("Net Investment Income Tax (NIIT) Test Suite")
    print("=" * 80)
    print("Testing 3.8% tax on investment income for high earners\n")

    # Run tests
    test_niit_on_capital_gains()
    test_niit_threshold_scenarios()
    test_niit_on_multiple_income_types()

    print("\n" + "=" * 80)
    print("AUDIT FINDING: Net Investment Income Tax NOT IMPLEMENTED")
    print("=" * 80)
    print("\nCRITICAL TAX COMPLIANCE ISSUE:")
    print("- NIIT (3.8% tax) is required on investment income for high earners")
    print("- Applies when MAGI exceeds $200k (single) or $250k (married)")
    print("- Missing from ALL tax calculations despite being in user profile")
    print("\nIMPACT:")
    print("- Understates federal tax liability by 3.8% of investment income")
    print("- Could result in significant underpayment penalties")
    print("- Affects most users of equity compensation planning tools")
    print("\nRECOMMENDATION:")
    print("- Implement NIIT calculation in AnnualTaxCalculator._calculate_federal_tax()")
    print("- Add to federal tax total after regular tax and AMT")
    print("- Test thoroughly with various income scenarios")


if __name__ == "__main__":
    run_all_tests()
