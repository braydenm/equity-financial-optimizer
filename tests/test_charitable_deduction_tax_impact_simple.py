"""
Simplified E2E tests verifying that charitable deductions affect tax bills.

These tests demonstrate tax impacts by comparing scenarios with and without
charitable donations, rather than trying to modify tax constants at runtime.
"""

import sys
import os
from datetime import date, datetime
from decimal import Decimal

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import DonationComponents, CashDonationComponents
from projections.projection_state import UserProfile
from projections.projection_calculator import ProjectionCalculator, ProjectionPlan
from projections.projection_state import ShareLot, LifecycleState, PlannedAction, ActionType, ShareType, TaxTreatment


def create_test_profile(annual_income: float = 500000):
    """Create a test profile with specified income."""
    return UserProfile(
        annual_w2_income=annual_income,
        spouse_w2_income=0,
        other_income=0,
        interest_income=0,
        dividend_income=0,
        filing_status='single',
        state_of_residence='California',
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.133,
        state_ltcg_rate=0.133,
        fica_tax_rate=0.0765,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        current_cash=1000000,  # Enough for donations
        exercise_reserves=0,
        taxable_investments=200000,
        monthly_living_expenses=12500,
        pledge_percentage=0.5,
        company_match_ratio=3.0,
        amt_credit_carryforward=0,
        investment_return_rate=0.07
    )


def test_donation_reduces_tax_bill():
    """
    E2E test showing charitable donations reduce total tax bill.

    Compares identical income scenarios with and without donations.
    """
    print("\n" + "="*80)
    print("E2E TEST: Charitable Donations Reduce Tax Bills")
    print("="*80)

    profile = create_test_profile(annual_income=400000)  # $400K AGI
    calculator = AnnualTaxCalculator()

    # Scenario 1: No donation
    result_no_donation = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        include_california=True
    )

    # Scenario 2: With $100K cash donation
    cash_donation = CashDonationComponents(
        donation_date=date(2025, 6, 1),
        amount=100000,  # $100K donation
        company_match_ratio=0,
        company_match_amount=0
    )

    result_with_donation = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        cash_donation_components=[cash_donation],
        include_california=True
    )

    print(f"\nScenario: $400K income")
    print(f"\nWithout Donation:")
    print(f"  Federal deduction: $0")
    print(f"  CA deduction: $0")
    print(f"  Total tax bill: ${result_no_donation.total_tax:,.0f}")

    print(f"\nWith $100K Donation:")
    print(f"  Federal deduction: ${result_with_donation.charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  CA deduction: ${result_with_donation.ca_charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  Total tax bill: ${result_with_donation.total_tax:,.0f}")

    tax_savings = result_no_donation.total_tax - result_with_donation.total_tax
    print(f"\n💰 TAX SAVINGS: ${tax_savings:,.0f} lower tax bill due to charitable deduction")

    # Verify donation reduces taxes
    assert result_with_donation.total_tax < result_no_donation.total_tax, \
        "Tax bill should be lower with charitable donation"

    # Verify deductions were applied
    assert result_with_donation.charitable_deduction_result.cash_deduction_used == 100000, \
        "Full donation should be deductible (within limits)"

    print("\n✅ Test passed: Charitable donations reduce tax bills")


def test_federal_vs_ca_deduction_differences():
    """
    E2E test showing federal vs CA deduction limit differences affect taxes.

    Uses a large donation that hits different federal (60%) vs CA (50%) limits.
    """
    print("\n" + "="*80)
    print("E2E TEST: Federal vs CA Deduction Limit Differences")
    print("="*80)

    profile = create_test_profile(annual_income=400000)  # $400K AGI
    calculator = AnnualTaxCalculator()

    # Large donation that will hit AGI limits differently
    # Federal: 60% × $400K = $240K limit
    # CA: 50% × $400K = $200K limit
    cash_donation = CashDonationComponents(
        donation_date=date(2025, 6, 1),
        amount=250000,  # $250K donation exceeds both limits
        company_match_ratio=0,
        company_match_amount=0
    )

    result = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        cash_donation_components=[cash_donation],
        include_california=True
    )

    print(f"\nScenario: $400K income, $250K donation")
    print(f"Federal limit: 60% × $400K = $240K")
    print(f"CA limit: 50% × $400K = $200K")

    print(f"\nResults:")
    print(f"  Federal deduction used: ${result.charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  Federal carryforward: ${result.charitable_deduction_result.cash_carryforward:,.0f}")
    print(f"  CA deduction used: ${result.ca_charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  CA carryforward: ${result.ca_charitable_deduction_result.cash_carryforward:,.0f}")

    # Verify different limits applied
    assert result.charitable_deduction_result.cash_deduction_used == 240000, \
        f"Federal deduction should be limited to 60% of AGI = $240K"

    assert result.ca_charitable_deduction_result.cash_deduction_used == 200000, \
        f"CA deduction should be limited to 50% of AGI = $200K"

    # Verify different carryforwards
    federal_carryforward = result.charitable_deduction_result.cash_carryforward
    ca_carryforward = result.ca_charitable_deduction_result.cash_carryforward

    print(f"\n💡 INSIGHT: CA has ${ca_carryforward - federal_carryforward:,.0f} more carryforward")
    print(f"   due to lower annual deduction limit (50% vs 60%)")

    assert ca_carryforward > federal_carryforward, \
        "CA should have larger carryforward due to lower annual limit"

    print("\n✅ Test passed: Federal vs CA limits create different deduction amounts")


def test_carryforward_reduces_future_taxes():
    """
    E2E test showing carryforwards reduce taxes in future years.

    Year 1: Large donation creates carryforward
    Year 2: No donation, but carryforward reduces taxes
    """
    print("\n" + "="*80)
    print("E2E TEST: Carryforwards Reduce Future Year Taxes")
    print("="*80)

    profile = create_test_profile(annual_income=300000)  # $300K AGI
    calculator = AnnualTaxCalculator()

    # Year 1: Large donation creating carryforward
    large_donation = CashDonationComponents(
        donation_date=date(2025, 6, 1),
        amount=250000,  # $250K donation
        company_match_ratio=0,
        company_match_amount=0
    )

    result_year1 = calculator.calculate_annual_tax(
        year=2025,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        cash_donation_components=[large_donation],
        include_california=True
    )

    # Year 2: No new donation, but use carryforward
    result_year2_with_carryforward = calculator.calculate_annual_tax(
        year=2026,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        carryforward_cash_deduction=result_year1.charitable_deduction_result.cash_carryforward,
        ca_carryforward_cash_deduction=result_year1.ca_charitable_deduction_result.cash_carryforward,
        include_california=True
    )

    # Year 2 comparison: No donation and no carryforward
    result_year2_no_carryforward = calculator.calculate_annual_tax(
        year=2026,
        user_profile=profile,
        w2_income=profile.annual_w2_income,
        include_california=True
    )

    print(f"\nYear 1 ($300K income, $250K donation):")
    print(f"  Federal deduction: ${result_year1.charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  Federal carryforward: ${result_year1.charitable_deduction_result.cash_carryforward:,.0f}")
    print(f"  CA deduction: ${result_year1.ca_charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  CA carryforward: ${result_year1.ca_charitable_deduction_result.cash_carryforward:,.0f}")

    print(f"\nYear 2 (Using carryforward):")
    print(f"  Federal deduction from carryforward: ${result_year2_with_carryforward.charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  CA deduction from carryforward: ${result_year2_with_carryforward.ca_charitable_deduction_result.cash_deduction_used:,.0f}")
    print(f"  Tax with carryforward: ${result_year2_with_carryforward.total_tax:,.0f}")
    print(f"  Tax without carryforward: ${result_year2_no_carryforward.total_tax:,.0f}")

    tax_savings_year2 = result_year2_no_carryforward.total_tax - result_year2_with_carryforward.total_tax
    print(f"\n💰 YEAR 2 TAX SAVINGS: ${tax_savings_year2:,.0f} from using carryforward")

    # Verify carryforward reduces future taxes
    assert result_year2_with_carryforward.total_tax < result_year2_no_carryforward.total_tax, \
        "Tax bill should be lower when using carryforward"

    # Verify carryforward was used
    assert result_year2_with_carryforward.charitable_deduction_result.cash_deduction_used > 0, \
        "Should have deduction from carryforward in year 2"

    print("\n✅ Test passed: Carryforwards reduce taxes in future years")


def test_projection_multi_year_tax_impact():
    """
    E2E test using projection system to show multi-year tax impacts.

    Demonstrates total tax differences over multiple years with donations.
    """
    print("\n" + "="*80)
    print("E2E TEST: Multi-Year Projection Tax Impact")
    print("="*80)

    profile = create_test_profile(annual_income=400000)

    # Create a stock lot for donation
    stock_lot = ShareLot(
        lot_id='STOCK_001',
        share_type=ShareType.RSU,
        quantity=3000,
        strike_price=0.0,
        grant_date=date(2020, 1, 1),
        lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
        tax_treatment=TaxTreatment.LTCG,
        exercise_date=date(2022, 1, 1),
        fmv_at_exercise=20.0,
        cost_basis=0.0
    )

    # Scenario 1: Natural evolution (no donations)
    plan_no_donation = ProjectionPlan(
        name="No Donations",
        description="Baseline with no charitable activity",
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2027, 12, 31),  # 3 years
        planned_actions=[],  # No actions
        initial_lots=[stock_lot],
        initial_cash=profile.current_cash,
        tax_elections={},
        price_projections={2025: 100.0, 2026: 100.0, 2027: 100.0}
    )

    # Scenario 2: With donation
    donation_action = PlannedAction(
        action_type=ActionType.DONATE,
        action_date=date(2025, 6, 1),
        lot_id='STOCK_001',
        quantity=2000,  # $200K donation
        price=100.0,
        notes='Charitable donation for tax planning'
    )

    plan_with_donation = ProjectionPlan(
        name="With Donation",
        description="Charitable giving strategy",
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2027, 12, 31),
        planned_actions=[donation_action],
        initial_lots=[stock_lot],
        initial_cash=profile.current_cash,
        tax_elections={},
        price_projections={2025: 100.0, 2026: 100.0, 2027: 100.0}
    )

    calculator = ProjectionCalculator(profile)

    result_no_donation = calculator.evaluate_projection_plan(plan_no_donation)
    result_with_donation = calculator.evaluate_projection_plan(plan_with_donation)

    print(f"\n3-Year Tax Comparison:")

    total_tax_no_donation = 0
    total_tax_with_donation = 0

    for year in [2025, 2026, 2027]:
        state_no_donation = next(s for s in result_no_donation.yearly_states if s.year == year)
        state_with_donation = next(s for s in result_with_donation.yearly_states if s.year == year)

        total_tax_no_donation += state_no_donation.tax_state.total_tax
        total_tax_with_donation += state_with_donation.tax_state.total_tax

        print(f"\nYear {year}:")
        print(f"  Tax without donation: ${state_no_donation.tax_state.total_tax:,.0f}")
        print(f"  Tax with donation: ${state_with_donation.tax_state.total_tax:,.0f}")
        print(f"  Savings: ${state_no_donation.tax_state.total_tax - state_with_donation.tax_state.total_tax:,.0f}")

    total_savings = total_tax_no_donation - total_tax_with_donation
    print(f"\n💰 3-YEAR TOTAL TAX SAVINGS: ${total_savings:,.0f}")

    # Verify donations reduce total taxes over multiple years
    assert total_tax_with_donation < total_tax_no_donation, \
        "Total taxes over 3 years should be lower with charitable donations"

    print("\n✅ Test passed: Multi-year projections show charitable tax benefits")


def run_all_tests():
    """Run all simplified E2E charitable deduction tax impact tests."""
    print("="*80)
    print("SIMPLIFIED CHARITABLE DEDUCTION TAX IMPACT E2E TESTS")
    print("="*80)
    print("These tests verify charitable deductions affect tax bills using direct comparisons")

    tests = [
        ("Donations Reduce Tax Bills", test_donation_reduces_tax_bill),
        ("Federal vs CA Deduction Differences", test_federal_vs_ca_deduction_differences),
        ("Carryforwards Reduce Future Taxes", test_carryforward_reduces_future_taxes),
        ("Multi-Year Projection Tax Impact", test_projection_multi_year_tax_impact),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            test_func()
            results.append((test_name, True))
        except Exception as e:
            print(f"\n💥 Test '{test_name}' failed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    print(f"\n{'='*80}")
    print("E2E TEST RESULTS SUMMARY")
    print(f"{'='*80}")

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status}: {test_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print(f"\n🎉 ALL E2E TESTS PASSED!")
        print(f"   ✅ Charitable donations reduce tax bills")
        print(f"   ✅ Federal vs CA limits create different outcomes")
        print(f"   ✅ Carryforwards provide future tax benefits")
        print(f"   ✅ Multi-year projections show cumulative impact")
    else:
        print(f"\n⚠️  Some E2E tests failed")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
