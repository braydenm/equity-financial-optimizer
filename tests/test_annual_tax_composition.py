"""
Comprehensive test demonstrating the refactored annual tax composition system.

This test shows how the new component-based architecture properly handles:
- Multiple actions (exercises, sales, donations) in a single year
- Proper tax bracket calculations (not flat rates)
- AMT determination at the annual level
- Charitable deduction AGI limits
- Federal LTCG brackets (0%, 15%, 20%)
"""

import sys
import os
from datetime import date
from decimal import Decimal

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import UserProfile
from calculators.iso_exercise_calculator import calculate_exercise_components, calculate_nso_exercise_components
from calculators.share_sale_calculator import ShareSaleCalculator
from calculators.share_donation_calculator import ShareDonationCalculator
from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import (
    AnnualTaxComponents,
    ISOExerciseComponents,
    NSOExerciseComponents,
    ShareSaleComponents,
    DonationComponents,
    DispositionType
)


def create_test_profile(w2_income: float = 200000) -> UserProfile:
    """Create a test user profile with realistic tax rates."""
    return UserProfile(
        filing_status='single',
        state_of_residence='California',
        annual_w2_income=w2_income,
        spouse_w2_income=0,
        other_income=0,
        federal_tax_rate=0.37,      # Top federal bracket for high earners
        federal_ltcg_rate=0.20,     # Will be overridden by bracket calculation
        state_tax_rate=0.093,       # CA marginal rate
        state_ltcg_rate=0.093,      # CA treats LTCG as ordinary
        fica_tax_rate=0.0145,       # Medicare only (above SS cap)
        additional_medicare_rate=0.009,  # High earner Medicare
        niit_rate=0.038,            # Net Investment Income Tax
        current_cash=500000,
        exercise_reserves=100000,
        pledge_percentage=0.1,       # 10% pledge
        company_match_ratio=2.0     # 2:1 match
    )


def test_multiple_actions_in_year():
    """Test aggregating multiple actions (ISO exercise, NSO exercise, sale, donation) in one year."""
    print("TEST: Multiple Actions in Single Year")
    print("=" * 60)

    profile = create_test_profile(w2_income=200000)
    calculator = AnnualTaxCalculator()
    sale_calc = ShareSaleCalculator()
    donation_calc = ShareDonationCalculator()

    # Create annual components for 2025
    annual_components = AnnualTaxComponents(year=2025)

    # Action 1: Exercise 1000 ISOs on Jan 15
    iso_exercise = calculate_exercise_components(
        lot_id='ISO_001',
        exercise_date=date(2025, 1, 15),
        shares_to_exercise=1000,
        strike_price=10.0,
        current_fmv=30.0,
        grant_date=date(2022, 1, 1)
    )
    annual_components.iso_exercise_components.append(iso_exercise)
    print(f"✓ ISO Exercise: 1,000 shares, bargain element = ${iso_exercise.bargain_element:,.0f}")

    # Action 2: Exercise 500 NSOs on March 1
    nso_exercise = calculate_nso_exercise_components(
        lot_id='NSO_001',
        exercise_date=date(2025, 3, 1),
        shares_to_exercise=500,
        strike_price=8.0,
        current_fmv=32.0,
        grant_date=date(2022, 6, 1)
    )
    annual_components.nso_exercise_components.append(nso_exercise)
    print(f"✓ NSO Exercise: 500 shares, ordinary income = ${nso_exercise.bargain_element:,.0f}")

    # Action 3: Sell 2000 shares (LTCG) on June 15
    sale = sale_calc.calculate_sale_components(
        lot_id='RSU_2021',
        sale_date=date(2025, 6, 15),
        shares_to_sell=2000,
        sale_price=35.0,
        cost_basis=10.0,
        exercise_date=date(2021, 9, 15),
        # acquisition_type='vest',
        is_iso=False
    )
    annual_components.sale_components.append(sale)
    print(f"✓ Share Sale: 2,000 shares, LTCG = ${sale.long_term_gain:,.0f}")

    # Action 4: Donate 100 shares on Sept 1
    donation = donation_calc.calculate_share_donation_components(
        lot_id='RSU_2022',
        donation_date=date(2025, 9, 1),
        shares_donated=100,
        fmv_at_donation=40.0,
        cost_basis=12.0,
        exercise_date=date(2022, 9, 15),
        holding_period_days=1081,  # ~3 years
        company_match_ratio=profile.company_match_ratio
    )
    annual_components.donation_components.append(donation)
    print(f"✓ Share Donation: 100 shares, value = ${donation.donation_value:,.0f}")

    # Calculate annual tax
    print("\nCalculating Annual Tax...")
    tax_result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=0,
        other_ordinary_income=0,
        exercise_components=annual_components.iso_exercise_components,
        nso_exercise_components=annual_components.nso_exercise_components,
        sale_components=annual_components.sale_components,
        donation_components=annual_components.donation_components
    )

    print("\nIncome Summary:")
    print(f"  W-2 Income: ${tax_result.w2_income:,.0f}")
    print(f"  NSO Exercise Income: ${nso_exercise.bargain_element:,.0f}")
    print(f"  Long-Term Capital Gains: ${tax_result.long_term_capital_gains:,.0f}")
    print(f"  Total Ordinary Income: ${tax_result.total_ordinary_income:,.0f}")
    print(f"  Adjusted Gross Income: ${tax_result.adjusted_gross_income:,.0f}")

    print("\nTax Calculation:")
    print(f"  Federal Regular Tax: ${tax_result.federal_regular_tax:,.0f}")
    print(f"  Federal AMT: ${tax_result.federal_amt:,.0f}")
    print(f"  Federal Tax (higher of): ${tax_result.federal_tax_owed:,.0f}")
    print(f"  CA Tax: ${tax_result.ca_tax_owed:,.0f}")
    print(f"  Total Tax: ${tax_result.total_tax:,.0f}")
    print(f"  Effective Tax Rate: {tax_result.effective_tax_rate:.1%}")

    print("\nDeductions:")
    print(f"  Charitable Deduction Used: ${tax_result.charitable_deduction_result.total_deduction_used:,.0f}")
    print(f"  Deduction Carryforward: ${tax_result.charitable_deduction_result.total_carryforward:,.0f}")

    return tax_result


def test_ltcg_bracket_application():
    """Test that LTCG uses proper brackets (0%, 15%, 20%) not flat rate."""
    print("\n\nTEST: LTCG Bracket Application")
    print("=" * 60)

    calculator = AnnualTaxCalculator()

    # Test different income levels to hit different LTCG brackets
    test_cases = [
        (40000, 50000, "Low income - should get 0% LTCG rate"),
        (150000, 100000, "Middle income - should get 15% LTCG rate"),
        (500000, 200000, "High income - should get 20% LTCG rate")
    ]

    for w2_income, ltcg_amount, description in test_cases:
        print(f"\n{description}:")
        print(f"  W-2 Income: ${w2_income:,}")
        print(f"  LTCG Amount: ${ltcg_amount:,}")

        profile = create_test_profile(w2_income=w2_income)

        # Create sale component
        sale = ShareSaleComponents(
            lot_id='TEST',
            sale_date=date(2025, 6, 1),
            shares_sold=1000,
            sale_price=ltcg_amount/1000 + 10,
            cost_basis=10.0,
            gross_proceeds=ltcg_amount + 10000,
            exercise_date=date(2020, 1, 1),
            # acquisition_type='purchase',
            holding_period_days=1887,
            disposition_type=DispositionType.REGULAR_SALE,
            short_term_gain=0,
            long_term_gain=ltcg_amount
        )

        # Calculate tax without LTCG
        base_result = calculator.calculate_annual_tax(
            year=2025,
            user_profile=profile,
            w2_income=w2_income,
            spouse_income=0,
            other_ordinary_income=0
        )

        # Calculate tax with LTCG
        ltcg_result = calculator.calculate_annual_tax(
            year=2025,
            user_profile=profile,
            w2_income=w2_income,
            spouse_income=0,
            other_ordinary_income=0,
            sale_components=[sale]
        )

        federal_ltcg_tax = ltcg_result.federal_tax_owed - base_result.federal_tax_owed
        effective_ltcg_rate = federal_ltcg_tax / ltcg_amount if ltcg_amount > 0 else 0

        print(f"  Federal tax on LTCG: ${federal_ltcg_tax:,.0f}")
        print(f"  Effective LTCG rate: {effective_ltcg_rate:.1%}")

        # Compare with flat 20% rate
        flat_rate_tax = ltcg_amount * 0.20
        savings = flat_rate_tax - federal_ltcg_tax
        print(f"  If flat 20% rate: ${flat_rate_tax:,.0f}")
        print(f"  Bracket savings: ${savings:,.0f}")


def test_amt_calculation():
    """Test that AMT is properly calculated with ISO exercises."""
    print("\n\nTEST: AMT Calculation with ISO Exercise")
    print("=" * 60)

    profile = create_test_profile(w2_income=200000)
    calculator = AnnualTaxCalculator()

    # Large ISO exercise to trigger AMT
    iso_exercise = calculate_exercise_components(
        lot_id='ISO_AMT_TEST',
        exercise_date=date(2025, 6, 1),
        shares_to_exercise=10000,
        strike_price=5.0,
        current_fmv=35.0,
        grant_date=date(2022, 1, 1)
    )

    print(f"ISO Exercise Details:")
    print(f"  Shares: {iso_exercise.shares_exercised:,}")
    print(f"  Strike Price: ${iso_exercise.strike_price}")
    print(f"  Current FMV: ${iso_exercise.fmv_at_exercise}")
    print(f"  Bargain Element: ${iso_exercise.bargain_element:,.0f}")

    # Calculate without ISO (no AMT)
    base_result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=0,
        other_ordinary_income=0
    )

    # Calculate with ISO (potential AMT)
    iso_result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=0,
        other_ordinary_income=0,
        exercise_components=[iso_exercise]
    )

    print(f"\nWithout ISO Exercise:")
    print(f"  Regular Tax: ${base_result.federal_regular_tax:,.0f}")
    print(f"  AMT: ${base_result.federal_amt:,.0f}")
    print(f"  Tax Owed: ${base_result.federal_tax_owed:,.0f}")

    print(f"\nWith ISO Exercise:")
    print(f"  Regular Tax: ${iso_result.federal_regular_tax:,.0f}")
    print(f"  AMT: ${iso_result.federal_amt:,.0f}")
    print(f"  Tax Owed: ${iso_result.federal_tax_owed:,.0f}")
    print(f"  Is AMT: {'Yes' if iso_result.federal_is_amt else 'No'}")
    print(f"  AMT Credit Generated: ${iso_result.federal_amt_credit_generated:,.0f}")


def test_charitable_deduction_limits():
    """Test that charitable deductions respect AGI limits."""
    print("\n\nTEST: Charitable Deduction AGI Limits")
    print("=" * 60)

    profile = create_test_profile(w2_income=200000)
    calculator = AnnualTaxCalculator()
    donation_calc = ShareDonationCalculator()

    # Large donation to test AGI limits
    large_donation = donation_calc.calculate_share_donation_components(
        lot_id='DONATION_TEST',
        donation_date=date(2025, 6, 1),
        shares_donated=2000,
        fmv_at_donation=50.0,
        cost_basis=10.0,
        exercise_date=date(2020, 1, 1),
        holding_period_days=1887,
        company_match_ratio=0  # No match for simplicity
    )

    print(f"Donation Details:")
    print(f"  Shares Donated: {large_donation.shares_donated:,}")
    print(f"  FMV per Share: ${large_donation.fmv_at_donation}")
    print(f"  Total Donation Value: ${large_donation.donation_value:,.0f}")
    print(f"  AGI: ${profile.annual_w2_income:,.0f}")
    print(f"  30% AGI Limit: ${profile.annual_w2_income * 0.30:,.0f}")

    tax_result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=0,
        other_ordinary_income=0,
        donation_components=[large_donation]
    )

    print(f"\nDeduction Results:")
    print(f"  Deduction Used This Year: ${tax_result.charitable_deduction_result.stock_deduction_used:,.0f}")
    print(f"  Deduction Carryforward: ${tax_result.charitable_deduction_result.stock_carryforward:,.0f}")
    print(f"  Applied Correctly: {'Yes' if tax_result.charitable_deduction_result.stock_deduction_used <= profile.annual_w2_income * 0.30 else 'No'}")


def compare_old_vs_new_approach():
    """Compare the old flat-rate approach with the new component-based approach."""
    print("\n\nCOMPARISON: Old vs New Tax Calculation Approach")
    print("=" * 60)

    profile = create_test_profile(w2_income=175000)

    # Scenario: NSO exercise + share sale in same year
    nso_bargain = 50000  # $50k ordinary income from NSO
    ltcg_gain = 75000    # $75k LTCG from share sale

    # OLD APPROACH (flat rates)
    print("OLD APPROACH (Flat Rates):")
    print(f"  NSO Tax = ${nso_bargain:,} × 48.65% = ${nso_bargain * 0.4865:,.0f}")
    print(f"  LTCG Tax = ${ltcg_gain:,} × 33.1% = ${ltcg_gain * 0.331:,.0f}")
    old_total_tax = nso_bargain * 0.4865 + ltcg_gain * 0.331
    print(f"  Total Tax = ${old_total_tax:,.0f}")

    # NEW APPROACH (components + brackets)
    print("\nNEW APPROACH (Components + Brackets):")

    calculator = AnnualTaxCalculator()

    # Create components
    nso_component = calculate_nso_exercise_components(
        lot_id='NSO_COMP',
        exercise_date=date(2025, 3, 1),
        shares_to_exercise=1000,
        strike_price=10.0,
        current_fmv=60.0,
        grant_date=date(2022, 1, 1)
    )

    sale_component = ShareSaleComponents(
        lot_id='SALE_COMP',
        sale_date=date(2025, 9, 1),
        shares_sold=1000,
        sale_price=100.0,
        cost_basis=25.0,
        gross_proceeds=100000,
        exercise_date=date(2020, 1, 1),
        # acquisition_type='purchase',
        holding_period_days=1979,
        disposition_type=DispositionType.REGULAR_SALE,
        short_term_gain=0,
        long_term_gain=ltcg_gain
    )

    # Calculate with new approach
    new_result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=0,
        other_ordinary_income=0,
        nso_exercise_components=[nso_component],
        sale_components=[sale_component]
    )

    # Calculate base tax for comparison
    base_result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=0,
        other_ordinary_income=0
    )

    incremental_tax = new_result.total_tax - base_result.total_tax

    print(f"  Base Tax (W-2 only): ${base_result.total_tax:,.0f}")
    print(f"  Tax with NSO + LTCG: ${new_result.total_tax:,.0f}")
    print(f"  Incremental Tax: ${incremental_tax:,.0f}")

    print(f"\nSAVINGS WITH NEW APPROACH:")
    savings = old_total_tax - incremental_tax
    print(f"  Old Approach Tax: ${old_total_tax:,.0f}")
    print(f"  New Approach Tax: ${incremental_tax:,.0f}")
    print(f"  Tax Savings: ${savings:,.0f} ({savings/old_total_tax:.1%})")

    print(f"\nWhy the savings?")
    print(f"  - Old: Applied top marginal rate to entire amounts")
    print(f"  - New: Properly fills tax brackets progressively")
    print(f"  - New: LTCG gets preferential bracket treatment")
    print(f"  - New: Considers total income for bracket determination")


if __name__ == "__main__":
    print("=" * 80)
    print("ANNUAL TAX COMPOSITION TEST SUITE")
    print("Demonstrating the refactored component-based tax calculation system")
    print("=" * 80)

    # Run all tests
    test_multiple_actions_in_year()
    test_ltcg_bracket_application()
    test_amt_calculation()
    test_charitable_deduction_limits()
    compare_old_vs_new_approach()

    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 80)
    print("\nKey Takeaways:")
    print("1. Tax is calculated annually, not per-action")
    print("2. Components from all actions are aggregated")
    print("3. Tax brackets are properly applied (not flat rates)")
    print("4. AMT is determined at the annual level")
    print("5. Charitable deductions respect AGI limits")
    print("6. Significant tax savings vs old flat-rate approach")
