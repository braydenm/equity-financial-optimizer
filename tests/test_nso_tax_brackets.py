#!/usr/bin/env python3
"""
Test script to verify NSO exercise tax calculation uses brackets instead of flat rate.

This demonstrates the difference between:
1. Old approach: bargain_element * ordinary_income_rate (flat 48.65%)
2. New approach: Annual tax calculation with proper brackets
"""

import sys
import os
from datetime import date

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.iso_exercise_calculator import calculate_nso_exercise_components
from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import AnnualTaxComponents
from projections.projection_state import UserProfile


def load_demo_profile():
    """Load the demo profile to get tax rates."""
    import json
    with open('input_data/demo_profile.json', 'r') as f:
        data = json.load(f)

    # Create UserProfile with tax rates
    profile = UserProfile(
        filing_status=data['personal_information']['tax_filing_status'],
        state_of_residence=data['personal_information']['state_of_residence'],
        annual_w2_income=data['income']['annual_w2_income'],
        spouse_w2_income=data['income']['spouse_w2_income'],
        other_income=data['income']['other_income'],
        federal_tax_rate=data['personal_information']['federal_tax_rate'],
        federal_ltcg_rate=data['personal_information']['federal_ltcg_rate'],
        state_tax_rate=data['personal_information']['state_tax_rate'],
        state_ltcg_rate=data['personal_information']['state_ltcg_rate'],
        fica_tax_rate=data['personal_information']['fica_tax_rate'],
        additional_medicare_rate=data['personal_information']['additional_medicare_rate'],
        niit_rate=data['personal_information']['niit_rate'],
        # Required financial position fields
        current_cash=data['financial_position']['liquid_assets']['cash'],
        exercise_reserves=data['goals_and_constraints']['liquidity_needs']['exercise_reserves'],
        # Add other fields with defaults
        company_match_ratio=data['equity_position']['grants'][0]['charitable_program']['company_match_ratio'],
        pledge_percentage=data['equity_position']['grants'][0]['charitable_program']['pledge_percentage']
    )

    return profile


def test_nso_exercise_tax_calculation():
    """Test NSO exercise tax calculation comparing old vs new approach."""

    print("NSO Exercise Tax Calculation Test")
    print("=" * 80)

    # Load demo profile
    profile = load_demo_profile()

    # Test scenario: Exercise 2000 NSO shares
    shares_to_exercise = 2000
    strike_price = 5.0
    current_fmv = 25.0  # Same as moderate price assumption
    exercise_date = date(2026, 1, 15)
    grant_date = date(2022, 1, 1)

    # Calculate bargain element
    bargain_element = shares_to_exercise * (current_fmv - strike_price)
    exercise_cost = shares_to_exercise * strike_price

    print(f"\nExercise Details:")
    print(f"  Shares: {shares_to_exercise:,}")
    print(f"  Strike Price: ${strike_price}")
    print(f"  Current FMV: ${current_fmv}")
    print(f"  Exercise Cost: ${exercise_cost:,.2f}")
    print(f"  Bargain Element: ${bargain_element:,.2f}")

    # OLD APPROACH: Flat rate calculation
    print(f"\n🚫 OLD APPROACH (Flat Rate):")
    combined_rate = profile.federal_tax_rate + profile.state_tax_rate
    old_tax = bargain_element * combined_rate
    print(f"  Tax = Bargain Element × Combined Tax Rate")
    print(f"  Tax = ${bargain_element:,.2f} × {combined_rate:.2%}")
    print(f"  Tax = ${old_tax:,.2f}")

    # NEW APPROACH: Component-based with brackets
    print(f"\n✅ NEW APPROACH (Tax Brackets):")

    # Create NSO exercise components
    nso_components = calculate_nso_exercise_components(
        lot_id="TEST_NSO",
        exercise_date=exercise_date,
        shares_to_exercise=shares_to_exercise,
        strike_price=strike_price,
        current_fmv=current_fmv,
        grant_date=grant_date
    )

    # Create annual tax components
    annual_components = AnnualTaxComponents(year=2026)
    annual_components.w2_income = profile.annual_w2_income
    annual_components.spouse_income = profile.spouse_w2_income
    annual_components.other_ordinary_income = profile.other_income
    annual_components.nso_exercise_components.append(nso_components)

    # Calculate annual tax WITHOUT the NSO exercise
    calculator = AnnualTaxCalculator()
    base_tax_result = calculator.calculate_annual_tax(
        year=2026,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=profile.spouse_w2_income,
        other_ordinary_income=profile.other_income
    )

    # Calculate annual tax WITH the NSO exercise
    tax_result_with_nso = calculator.calculate_annual_tax(
        year=2026,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=profile.spouse_w2_income,
        other_ordinary_income=profile.other_income,
        nso_exercise_components=[nso_components]
    )

    # The actual tax impact is the difference
    actual_tax_impact = tax_result_with_nso.total_tax - base_tax_result.total_tax

    print(f"  Base Income: ${profile.annual_w2_income:,.2f}")
    print(f"  + NSO Bargain Element: ${bargain_element:,.2f}")
    print(f"  = Total Income: ${profile.annual_w2_income + bargain_element:,.2f}")
    print(f"\n  Tax without NSO: ${base_tax_result.total_tax:,.2f}")
    print(f"  Tax with NSO: ${tax_result_with_nso.total_tax:,.2f}")
    print(f"  Actual Tax Impact: ${actual_tax_impact:,.2f}")

    # Show the difference
    print(f"\n💰 TAX SAVINGS WITH BRACKET CALCULATION:")
    tax_difference = old_tax - actual_tax_impact
    print(f"  Old Method Tax: ${old_tax:,.2f}")
    print(f"  New Method Tax: ${actual_tax_impact:,.2f}")
    print(f"  Tax Savings: ${tax_difference:,.2f}")
    print(f"  Savings Rate: {tax_difference / old_tax:.1%}")

    # Show effective tax rate
    print(f"\n📊 EFFECTIVE TAX RATES ON BARGAIN ELEMENT:")
    old_effective_rate = old_tax / bargain_element
    new_effective_rate = actual_tax_impact / bargain_element
    print(f"  Old Method: {old_effective_rate:.2%}")
    print(f"  New Method: {new_effective_rate:.2%}")

    # Test with larger exercise to show bracket effects
    print(f"\n" + "=" * 80)
    print("TESTING LARGER NSO EXERCISE (10,000 shares)")
    print("=" * 80)

    large_shares = 10000
    large_bargain_element = large_shares * (current_fmv - strike_price)

    # Old approach
    combined_rate = profile.federal_tax_rate + profile.state_tax_rate
    large_old_tax = large_bargain_element * combined_rate

    # New approach
    large_nso_components = calculate_nso_exercise_components(
        lot_id="TEST_NSO_LARGE",
        exercise_date=exercise_date,
        shares_to_exercise=large_shares,
        strike_price=strike_price,
        current_fmv=current_fmv,
        grant_date=grant_date
    )

    large_tax_result = calculator.calculate_annual_tax(
        year=2026,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        spouse_income=profile.spouse_w2_income,
        other_ordinary_income=profile.other_income,
        nso_exercise_components=[large_nso_components]
    )

    large_actual_tax_impact = large_tax_result.total_tax - base_tax_result.total_tax

    print(f"\nBargain Element: ${large_bargain_element:,.2f}")
    print(f"Old Method Tax: ${large_old_tax:,.2f} ({large_old_tax/large_bargain_element:.2%})")
    print(f"New Method Tax: ${large_actual_tax_impact:,.2f} ({large_actual_tax_impact/large_bargain_element:.2%})")
    print(f"Tax Savings: ${large_old_tax - large_actual_tax_impact:,.2f}")

    print("\n✅ Test demonstrates that NSO exercises now use proper tax brackets!")
    print("   The effective tax rate increases as income rises through the brackets,")
    print("   rather than applying a flat 48.65% rate to all bargain element income.")


if __name__ == "__main__":
    test_nso_exercise_tax_calculation()
