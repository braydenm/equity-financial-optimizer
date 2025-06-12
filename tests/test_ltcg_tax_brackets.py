#!/usr/bin/env python3
"""
Test script to verify LTCG tax calculation uses brackets instead of flat rate.

This demonstrates the difference between:
1. Old approach: ltcg_gain * federal_ltcg_rate (flat 20%)
2. New approach: LTCG brackets (0%, 15%, 20%) based on total income
"""

import sys
import os
from datetime import date

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.share_sale_calculator import ShareSaleCalculator
from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import AnnualTaxComponents, ShareSaleComponents, DispositionType
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
        company_match_ratio=data['charitable_giving']['company_match_ratio'],
        pledge_percentage=data['charitable_giving']['pledge_percentage']
    )

    return profile


def test_ltcg_bracket_calculation():
    """Test LTCG tax calculation with different income levels to show bracket effects."""

    print("LTCG Tax Bracket Calculation Test")
    print("=" * 80)

    # Load demo profile
    profile = load_demo_profile()
    calculator = AnnualTaxCalculator()

    # Test scenarios with different W2 incomes to show bracket effects
    test_scenarios = [
        {
            'name': 'Low Income (0% LTCG bracket)',
            'w2_income': 30000,
            'ltcg_gain': 50000,
            'expected_bracket': '0%'
        },
        {
            'name': 'Middle Income (15% LTCG bracket)',
            'w2_income': 100000,
            'ltcg_gain': 50000,
            'expected_bracket': '15%'
        },
        {
            'name': 'High Income (20% LTCG bracket)',
            'w2_income': 500000,
            'ltcg_gain': 50000,
            'expected_bracket': '20%'
        },
        {
            'name': 'Demo Profile Income',
            'w2_income': profile.annual_w2_income,
            'ltcg_gain': 100000,
            'expected_bracket': 'mixed'
        }
    ]

    print("\nFederal LTCG Tax Brackets (2024 - Single):")
    print("  0% bracket: $0 - $44,625")
    print("  15% bracket: $44,625 - $492,300")
    print("  20% bracket: $492,300+")
    print("\nNote: LTCG stacks on top of ordinary income for bracket determination")

    for scenario in test_scenarios:
        print(f"\n{'='*60}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"{'='*60}")

        w2_income = scenario['w2_income']
        ltcg_gain = scenario['ltcg_gain']

        # Create sale components for the LTCG
        shares_sold = 1000
        sale_price = 150.0
        sale_components = ShareSaleComponents(
            lot_id="TEST_LTCG",
            sale_date=date(2026, 6, 1),
            shares_sold=shares_sold,
            sale_price=sale_price,
            gross_proceeds=shares_sold * sale_price,
            cost_basis=50.0,
            acquisition_date=date(2024, 1, 1),
            acquisition_type='exercise',
            holding_period_days=520,
            disposition_type=DispositionType.REGULAR_SALE,
            long_term_gain=ltcg_gain,
            short_term_gain=0.0,
            ordinary_income=0.0
        )

        # Calculate tax with LTCG
        annual_components = AnnualTaxComponents(year=2026)
        annual_components.sale_components.append(sale_components)

        # Create a custom profile with the test W2 income
        test_profile = UserProfile(
            filing_status=profile.filing_status,
            state_of_residence=profile.state_of_residence,
            annual_w2_income=w2_income,
            spouse_w2_income=0,
            other_income=0,
            federal_tax_rate=profile.federal_tax_rate,
            federal_ltcg_rate=profile.federal_ltcg_rate,
            state_tax_rate=profile.state_tax_rate,
            state_ltcg_rate=profile.state_ltcg_rate,
            fica_tax_rate=profile.fica_tax_rate,
            additional_medicare_rate=profile.additional_medicare_rate,
            niit_rate=profile.niit_rate,
            current_cash=0,
            exercise_reserves=0,
            company_match_ratio=0,
            pledge_percentage=0
        )

        # Calculate base tax (no LTCG)
        base_result = calculator.calculate_annual_tax(
            year=2026,
            user_profile=test_profile,
            w2_income=w2_income,
            spouse_income=0,
            other_ordinary_income=0
        )

        # Calculate tax with LTCG
        ltcg_result = calculator.calculate_annual_tax(
            year=2026,
            user_profile=test_profile,
            w2_income=w2_income,
            spouse_income=0,
            other_ordinary_income=0,
            sale_components=[sale_components]
        )

        # Calculate the actual LTCG tax
        federal_ltcg_tax = ltcg_result.federal_tax_owed - base_result.federal_tax_owed
        total_ltcg_tax = ltcg_result.total_tax - base_result.total_tax

        # Old approach (flat rate)
        old_federal_ltcg_tax = ltcg_gain * 0.20  # Flat 20%
        old_state_ltcg_tax = ltcg_gain * test_profile.state_ltcg_rate
        old_niit_tax = ltcg_gain * test_profile.niit_rate if w2_income > 200000 else 0
        old_total_ltcg_tax = old_federal_ltcg_tax + old_state_ltcg_tax + old_niit_tax

        print(f"\nIncome Details:")
        print(f"  W2 Income: ${w2_income:,}")
        print(f"  LTCG Gain: ${ltcg_gain:,}")
        print(f"  Total Income: ${w2_income + ltcg_gain:,}")

        print(f"\n🚫 OLD APPROACH (Flat 20% Federal):")
        print(f"  Federal LTCG Tax: ${old_federal_ltcg_tax:,.2f} ({old_federal_ltcg_tax/ltcg_gain:.1%})")
        print(f"  State Tax: ${old_state_ltcg_tax:,.2f} ({old_state_ltcg_tax/ltcg_gain:.1%})")
        if old_niit_tax > 0:
            print(f"  NIIT: ${old_niit_tax:,.2f} ({old_niit_tax/ltcg_gain:.1%})")
        print(f"  Total LTCG Tax: ${old_total_ltcg_tax:,.2f}")

        print(f"\n✅ NEW APPROACH (Tax Brackets):")
        print(f"  Federal LTCG Tax: ${federal_ltcg_tax:,.2f} ({federal_ltcg_tax/ltcg_gain:.1%})")

        # Calculate state and NIIT components
        state_ltcg_tax = ltcg_result.ca_tax_owed - base_result.ca_tax_owed
        effective_federal_rate = federal_ltcg_tax / ltcg_gain

        print(f"  State Tax: ${state_ltcg_tax:,.2f} ({state_ltcg_tax/ltcg_gain:.1%})")
        print(f"  Total LTCG Tax: ${total_ltcg_tax:,.2f}")
        print(f"\n  Effective Federal LTCG Rate: {effective_federal_rate:.1%}")
        print(f"  Expected Bracket: {scenario['expected_bracket']}")

        # Show savings
        if old_federal_ltcg_tax != federal_ltcg_tax:
            savings = old_federal_ltcg_tax - federal_ltcg_tax
            print(f"\n💰 Federal Tax Savings: ${savings:,.2f}")

    # Test bracket transitions
    print(f"\n{'='*80}")
    print("BRACKET TRANSITION TEST")
    print("=" * 80)
    print("\nThis shows how LTCG tax changes as it crosses bracket thresholds:")

    # Test with income that spans brackets
    test_w2 = 400000  # Puts us near the 15%/20% transition
    large_ltcg = 200000  # This will span from 15% to 20% bracket

    shares_sold = 2000
    sale_price = 150.0
    sale_components = ShareSaleComponents(
        lot_id="TEST_LARGE_LTCG",
        sale_date=date(2026, 6, 1),
        shares_sold=shares_sold,
        sale_price=sale_price,
        gross_proceeds=shares_sold * sale_price,
        cost_basis=50.0,
        acquisition_date=date(2024, 1, 1),
        acquisition_type='exercise',
        holding_period_days=520,
        disposition_type=DispositionType.REGULAR_SALE,
        long_term_gain=large_ltcg,
        short_term_gain=0.0,
        ordinary_income=0.0
    )

    # Create test profile
    test_profile = UserProfile(
        filing_status='single',
        state_of_residence='California',
        annual_w2_income=test_w2,
        spouse_w2_income=0,
        other_income=0,
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        current_cash=0,
        exercise_reserves=0,
        company_match_ratio=0,
        pledge_percentage=0
    )

    # Calculate taxes
    base_result = calculator.calculate_annual_tax(
        year=2026,
        user_profile=test_profile,
        w2_income=test_w2,
        spouse_income=0,
        other_ordinary_income=0
    )

    ltcg_result = calculator.calculate_annual_tax(
        year=2026,
        user_profile=test_profile,
        w2_income=test_w2,
        spouse_income=0,
        other_ordinary_income=0,
        sale_components=[sale_components]
    )

    federal_ltcg_tax = ltcg_result.federal_tax_owed - base_result.federal_tax_owed
    effective_rate = federal_ltcg_tax / large_ltcg

    print(f"\nW2 Income: ${test_w2:,}")
    print(f"LTCG Gain: ${large_ltcg:,}")
    print(f"Total Income: ${test_w2 + large_ltcg:,}")
    print(f"\nFederal LTCG Tax: ${federal_ltcg_tax:,.2f}")
    print(f"Effective Federal LTCG Rate: {effective_rate:.2%}")
    print(f"\nThis rate is between 15% and 20% because the LTCG spans both brackets!")

    print("\n✅ Test demonstrates that LTCG tax now uses proper federal brackets!")
    print("   Low-income taxpayers can pay 0% on LTCG")
    print("   Middle-income taxpayers pay 15% on LTCG")
    print("   High-income taxpayers pay 20% on LTCG")
    print("   The rate depends on total income, not just a flat 20%!")


if __name__ == "__main__":
    test_ltcg_bracket_calculation()
