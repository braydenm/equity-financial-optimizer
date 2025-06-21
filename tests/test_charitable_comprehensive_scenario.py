"""
Comprehensive test for charitable deduction calculations with varying AGI.

This test implements a detailed 7-year IRS scenario that verifies:
- FIFO ordering (oldest carryforwards used first)
- 5-year expiration rules
- Federal vs California separate tracking
- Cash vs stock deduction ordering
- 50% limit organizations
- Current year donations used before carryforwards
"""

import sys
import os
import unittest
from datetime import date, datetime
from decimal import Decimal

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from projections.projection_state import UserProfile
from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import DonationComponents, CashDonationComponents


class TestCharitableComprehensiveScenario(unittest.TestCase):
    """Test comprehensive 7-year charitable deduction scenario with IRS rules."""

    def create_profile_for_year(self, year: int) -> UserProfile:
        """Create profile with AGI matching the test scenario."""
        # AGI by year from the test scenario
        agi_by_year = {
            2023: 200000,
            2024: 150000,
            2025: 80000,
            2026: 70000,
            2027: 60000,
            2028: 180000,
            2029: 300000
        }

        agi = agi_by_year.get(year, 100000)

        return UserProfile(
            annual_w2_income=agi,
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
            current_cash=1000000,  # Enough for all donations
            exercise_reserves=0,
            taxable_investments=100000,
            monthly_living_expenses=5000,
            pledge_percentage=0.0,  # No pledge for this test
            company_match_ratio=0.0,  # No match for this test
            amt_credit_carryforward=0,
            investment_return_rate=0.07
        )

    def test_comprehensive_seven_year_scenario(self):
        """
        Test the comprehensive 7-year charitable deduction scenario.

        This scenario tests:
        - Varying AGI from $60K to $300K
        - Mixed cash and stock donations
        - 50% limit organizations (overall charitable limit is 50% of AGI)
        - FIFO carryforward consumption
        - 5-year expiration rules
        - Federal vs California separate calculations
        """
        # Expected values from the corrected scenario
        expected_results = {
            2023: {
                'agi': 200000,
                'cash_donated': 140000,
                'stock_donated': 70000,
                'federal_cash_deducted': 120000,
                'federal_stock_deducted': 0,
                'federal_cash_carryover': 20000,
                'federal_stock_carryover': 70000,
                'ca_cash_deducted': 100000,
                'ca_stock_deducted': 0,
                'ca_cash_carryover': 40000,
                'ca_stock_carryover': 70000
            },
            2024: {
                'agi': 150000,
                'cash_donated': 100000,
                'stock_donated': 50000,
                'federal_cash_deducted': 90000,
                'federal_stock_deducted': 0,
                'federal_cash_carryover': 30000,
                'federal_stock_carryover': 120000,
                'ca_cash_deducted': 75000,
                'ca_stock_deducted': 0,
                'ca_cash_carryover': 65000,
                'ca_stock_carryover': 120000
            },
            2025: {
                'agi': 80000,
                'cash_donated': 10000,
                'stock_donated': 5000,
                'federal_cash_deducted': 40000,
                'federal_stock_deducted': 0,
                'federal_cash_carryover': 0,
                'federal_stock_carryover': 125000,
                'ca_cash_deducted': 40000,
                'ca_stock_deducted': 0,
                'ca_cash_carryover': 35000,
                'ca_stock_carryover': 125000
            },
            2026: {
                'agi': 70000,
                'cash_donated': 8000,
                'stock_donated': 0,
                'federal_cash_deducted': 8000,
                'federal_stock_deducted': 21000,
                'federal_cash_carryover': 0,
                'federal_stock_carryover': 104000,
                'ca_cash_deducted': 35000,
                'ca_stock_deducted': 0,
                'ca_cash_carryover': 8000,
                'ca_stock_carryover': 125000
            },
            2027: {
                'agi': 60000,
                'cash_donated': 5000,
                'stock_donated': 0,
                'federal_cash_deducted': 5000,
                'federal_stock_deducted': 18000,
                'federal_cash_carryover': 0,
                'federal_stock_carryover': 86000,
                'ca_cash_deducted': 13000,
                'ca_stock_deducted': 17000,
                'ca_cash_carryover': 0,
                'ca_stock_carryover': 108000
            },
            2028: {
                'agi': 180000,
                'cash_donated': 20000,
                'stock_donated': 40000,
                'federal_cash_deducted': 20000,
                'federal_stock_deducted': 54000,
                'federal_expired': 17000,  # 2023 carryforward expires
                'federal_cash_carryover': 0,
                'federal_stock_carryover': 55000,  # 2024: 50K, 2025: 5K only
                'ca_cash_deducted': 20000,
                'ca_stock_deducted': 54000,
                'ca_expired': 39000,  # 2023 carryforward expires
                'ca_cash_carryover': 0,
                'ca_stock_carryover': 55000  # 2024: 50K, 2025: 5K only
            },
            2029: {
                'agi': 300000,
                'cash_donated': 15000,
                'stock_donated': 5000,
                'federal_cash_deducted': 15000,
                'federal_stock_deducted': 60000,  # Corrected from 75000
                'federal_cash_carryover': 0,
                'federal_stock_carryover': 0,
                'ca_cash_deducted': 15000,
                'ca_stock_deducted': 60000,  # Corrected from 75000
                'ca_cash_carryover': 0,
                'ca_stock_carryover': 0  # Corrected from 19000
            }
        }

        # Track carryforwards manually between years
        federal_cash_carryforward_by_creation_year = {}
        federal_stock_carryforward_by_creation_year = {}
        ca_cash_carryforward_by_creation_year = {}
        ca_stock_carryforward_by_creation_year = {}

        all_passed = True
        failure_messages = []

        for year in range(2023, 2030):
            expected = expected_results[year]
            profile = self.create_profile_for_year(year)

            # Create donation components
            donation_components = []
            cash_donation_components = []

            if expected['stock_donated'] > 0:
                donation_component = DonationComponents(
                    lot_id=f"STOCK_{year}",
                    donation_date=date(year, 6, 1),
                    shares_donated=int(expected['stock_donated'] / 100),
                    fmv_at_donation=100.0,
                    cost_basis=0.0,
                    acquisition_date=date(year - 2, 1, 1),
                    holding_period_days=365 * 2,
                    donation_value=float(expected['stock_donated']),
                    deduction_type="stock"
                )
                donation_components.append(donation_component)

            if expected['cash_donated'] > 0:
                cash_component = CashDonationComponents(
                    donation_date=date(year, 6, 1),
                    amount=float(expected['cash_donated'])
                )
                cash_donation_components.append(cash_component)

            # Calculate taxes with our calculator
            calculator = AnnualTaxCalculator()

            # Calculate with carryforwards
            federal_cash_carryforward = sum(federal_cash_carryforward_by_creation_year.values())
            ca_cash_carryforward = sum(ca_cash_carryforward_by_creation_year.values())

            result = calculator.calculate_annual_tax(
                year=year,
                user_profile=profile,
                w2_income=profile.annual_w2_income,
                donation_components=donation_components,
                cash_donation_components=cash_donation_components,
                carryforward_cash_deduction=federal_cash_carryforward,
                carryforward_stock_by_creation_year=federal_stock_carryforward_by_creation_year.copy(),
                ca_carryforward_cash_deduction=ca_cash_carryforward,
                ca_carryforward_stock_by_creation_year=ca_stock_carryforward_by_creation_year.copy()
            )

            # Get expiration amounts from calculator results
            federal_expired = result.charitable_deduction_result.expired_carryforward
            ca_expired = result.ca_charitable_deduction_result.expired_carryforward

            # Verify results
            federal_cash_match = abs(result.charitable_deduction_result.cash_deduction_used - expected['federal_cash_deducted']) < 1
            federal_stock_match = abs(result.charitable_deduction_result.stock_deduction_used - expected['federal_stock_deducted']) < 1
            federal_cash_carryover_match = abs(result.charitable_deduction_result.cash_carryforward - expected['federal_cash_carryover']) < 1
            federal_stock_carryover_match = abs(result.charitable_deduction_result.stock_carryforward - expected['federal_stock_carryover']) < 1

            ca_cash_match = abs(result.ca_charitable_deduction_result.cash_deduction_used - expected['ca_cash_deducted']) < 1
            ca_stock_match = abs(result.ca_charitable_deduction_result.stock_deduction_used - expected['ca_stock_deducted']) < 1
            ca_cash_carryover_match = abs(result.ca_charitable_deduction_result.cash_carryforward - expected['ca_cash_carryover']) < 1
            ca_stock_carryover_match = abs(result.ca_charitable_deduction_result.stock_carryforward - expected['ca_stock_carryover']) < 1

            if not all([federal_cash_match, federal_stock_match, federal_cash_carryover_match, federal_stock_carryover_match,
                       ca_cash_match, ca_stock_match, ca_cash_carryover_match, ca_stock_carryover_match]):
                all_passed = False
                failure_messages.append(f"Year {year} calculations did not match expected values")

                # Add debug output for 2028
                if year == 2028:
                    failure_messages.append(f"  Federal stock carryover: expected ${expected['federal_stock_carryover']:,}, got ${result.charitable_deduction_result.stock_carryforward:,.0f}")
                    failure_messages.append(f"  CA stock carryover: expected ${expected['ca_stock_carryover']:,}, got ${result.ca_charitable_deduction_result.stock_carryforward:,.0f}")

            # Check expiration amounts if expected
            if 'federal_expired' in expected:
                if abs(federal_expired - expected['federal_expired']) >= 1:
                    all_passed = False
                    failure_messages.append(f"Year {year} federal expiration: expected ${expected['federal_expired']:,}, got ${federal_expired:,.0f}")

            if 'ca_expired' in expected:
                if abs(ca_expired - expected['ca_expired']) >= 1:
                    all_passed = False
                    failure_messages.append(f"Year {year} CA expiration: expected ${expected['ca_expired']:,}, got ${ca_expired:,.0f}")

            # Update carryforwards for next year
            # Stock carryforwards are tracked by creation year
            federal_stock_carryforward_by_creation_year = result.charitable_deduction_result.carryforward_remaining_by_creation_year.copy()
            ca_stock_carryforward_by_creation_year = result.ca_charitable_deduction_result.carryforward_remaining_by_creation_year.copy()

            # Update cash carryforwards using FIFO
            total_cash_carryforward = result.charitable_deduction_result.cash_carryforward
            if total_cash_carryforward > 0:
                current_year_cash_donated = sum(d.amount for d in cash_donation_components)
                current_year_cash_used = min(current_year_cash_donated, result.charitable_deduction_result.cash_deduction_used)
                new_cash_carryforward = current_year_cash_donated - current_year_cash_used

                # Reduce existing carryforwards by amount used (FIFO)
                cash_used_from_carryforward = max(0, result.charitable_deduction_result.cash_deduction_used - current_year_cash_used)
                remaining_to_reduce = cash_used_from_carryforward

                for creation_year in sorted(federal_cash_carryforward_by_creation_year.keys()):
                    if remaining_to_reduce <= 0:
                        break
                    available = federal_cash_carryforward_by_creation_year[creation_year]
                    used = min(available, remaining_to_reduce)
                    federal_cash_carryforward_by_creation_year[creation_year] -= used
                    if federal_cash_carryforward_by_creation_year[creation_year] <= 0:
                        del federal_cash_carryforward_by_creation_year[creation_year]
                    remaining_to_reduce -= used

                if new_cash_carryforward > 0:
                    federal_cash_carryforward_by_creation_year[year] = new_cash_carryforward
            else:
                federal_cash_carryforward_by_creation_year.clear()

            # Same for CA cash
            total_ca_cash_carryforward = result.ca_charitable_deduction_result.cash_carryforward
            if total_ca_cash_carryforward > 0:
                current_year_cash_donated = sum(d.amount for d in cash_donation_components)
                current_year_cash_used = min(current_year_cash_donated, result.ca_charitable_deduction_result.cash_deduction_used)
                new_cash_carryforward = current_year_cash_donated - current_year_cash_used

                cash_used_from_carryforward = max(0, result.ca_charitable_deduction_result.cash_deduction_used - current_year_cash_used)
                remaining_to_reduce = cash_used_from_carryforward

                for creation_year in sorted(ca_cash_carryforward_by_creation_year.keys()):
                    if remaining_to_reduce <= 0:
                        break
                    available = ca_cash_carryforward_by_creation_year[creation_year]
                    used = min(available, remaining_to_reduce)
                    ca_cash_carryforward_by_creation_year[creation_year] -= used
                    if ca_cash_carryforward_by_creation_year[creation_year] <= 0:
                        del ca_cash_carryforward_by_creation_year[creation_year]
                    remaining_to_reduce -= used

                if new_cash_carryforward > 0:
                    ca_cash_carryforward_by_creation_year[year] = new_cash_carryforward
            else:
                ca_cash_carryforward_by_creation_year.clear()

            # Add new stock carryforwards from current year
            if result.charitable_deduction_result.stock_carryforward > sum(federal_stock_carryforward_by_creation_year.values()):
                current_year_stock_donated = sum(d.donation_value for d in donation_components)
                current_year_stock_used = min(current_year_stock_donated, result.charitable_deduction_result.stock_deduction_used)
                new_stock = current_year_stock_donated - current_year_stock_used
                if new_stock > 0:
                    federal_stock_carryforward_by_creation_year[year] = new_stock

            if result.ca_charitable_deduction_result.stock_carryforward > sum(ca_stock_carryforward_by_creation_year.values()):
                current_year_stock_donated = sum(d.donation_value for d in donation_components)
                current_year_stock_used = min(current_year_stock_donated, result.ca_charitable_deduction_result.stock_deduction_used)
                new_stock = current_year_stock_donated - current_year_stock_used
                if new_stock > 0:
                    ca_stock_carryforward_by_creation_year[year] = new_stock

            # Remove expired carryforwards after they could be used in their 5th year
            for creation_year in list(federal_cash_carryforward_by_creation_year.keys()):
                if year - creation_year >= 5:
                    del federal_cash_carryforward_by_creation_year[creation_year]

            for creation_year in list(federal_stock_carryforward_by_creation_year.keys()):
                if year - creation_year >= 5:
                    del federal_stock_carryforward_by_creation_year[creation_year]

            for creation_year in list(ca_cash_carryforward_by_creation_year.keys()):
                if year - creation_year >= 5:
                    del ca_cash_carryforward_by_creation_year[creation_year]

            for creation_year in list(ca_stock_carryforward_by_creation_year.keys()):
                if year - creation_year >= 5:
                    del ca_stock_carryforward_by_creation_year[creation_year]

        # Assert all tests passed
        if not all_passed:
            self.fail("Comprehensive charitable deduction test failed:\n" + "\n".join(failure_messages))


def run_test():
    """Run the comprehensive charitable deduction test."""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_test()
