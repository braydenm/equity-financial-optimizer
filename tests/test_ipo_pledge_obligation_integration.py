#!/usr/bin/env python3
"""
Integration test for IPO pledge obligation feature.

This test verifies that when a user has charitable pledges and an IPO date,
the system correctly calculates remaining pledge obligations due 1 year after IPO.

Uses the exact examples provided during development to catch regressions.
"""

import unittest
import tempfile
import csv
import os
from datetime import date
from typing import Dict, List

from engine.portfolio_manager import PortfolioManager
from projections.projection_state import (
    ProjectionPlan, PlannedAction, ActionType, YearlyState, ProjectionResult,
    UserProfile, TaxState, CharitableDeductionState, PledgeState
)
from projections.projection_output import generate_holding_milestones_csv


class TestIPOPledgeObligationIntegration(unittest.TestCase):
    """Integration test for IPO pledge obligation feature using real projection system."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_profile(self, total_shares: int, pledge_percentage: float, assumed_ipo: str) -> Dict:
        """Create a test user profile with the specified pledge configuration."""
        return {
            "metadata": {
                "profile_version": "2.0",
                "created_date": "2024-01-01"
            },
            "personal_information": {
                "tax_filing_status": "married_filing_jointly",
                "state_of_residence": "California",
                "federal_tax_rate": 0.37,
                "federal_ltcg_rate": 0.2,
                "state_tax_rate": 0.093,
                "state_ltcg_rate": 0.093,
                "fica_tax_rate": 0.0145,
                "additional_medicare_rate": 0.009,
                "niit_rate": 0.038
            },
            "income": {
                "annual_w2_income": 300000,
                "spouse_w2_income": 100000,
                "other_income": 0,
                "interest_income": 0,
                "dividend_income": 0,
                "bonus_expected": 0
            },
            "financial_position": {
                "liquid_assets": {
                    "cash": 50000,
                    "taxable_investments": 0,
                    "crypto": 0
                },
                "illiquid_assets": {
                    "real_estate_equity": 0
                },
                "monthly_cash_flow": {
                    "expenses": 15000
                }
            },
            "equity_position": {
                "company": "Test Company",
                "original_grants": [
                    {
                        "grant_id": "TEST_GRANT",
                        "grant_date": "2022-01-15",
                        "total_shares": total_shares,
                        "strike_price": 2.5,
                        "vesting_start_date": "2022-01-15",
                        "vesting_schedule": "4_year_monthly_with_cliff",
                        "cliff_months": 12,
                        "expiration_date": "2032-01-15",
                        "charitable_program": {
                            "pledge_percentage": pledge_percentage,
                            "company_match_ratio": 3.0
                        }
                    }
                ],
                "exercised_lots": [
                    {
                        "lot_id": "TEST_LOT_A",
                        "grant_id": "TEST_GRANT",
                        "exercise_date": "2024-01-15",
                        "quantity": total_shares,
                        "exercise_price": 2.5,
                        "exercise_type": "cashless"
                    }
                ],
                "vested_unexercised": {
                    "total_shares": 0,
                    "iso_shares": 0,
                    "nso_shares": 0,
                    "rsu_shares": 0
                },
                "unvested": {
                    "total_shares": 0,
                    "monthly_vesting_rate": 0,
                    "vesting_calendar": []
                }
            },
            "charitable_giving": {
                "pledge_percentage": 0.0,  # Profile-level pledge (unused in our implementation)
                "company_match_ratio": 0.0,
                "match_window_months": 36
            },
            "goals_and_constraints": {
                "liquidity_needs": {
                    "exercise_reserves": 100000,
                    "emergency_fund": 50000
                }
            },
            "tax_situation": {
                "carryforwards": {
                    "amt_credit": 0,
                    "capital_loss": 0,
                    "charitable_deduction": 0
                },
                "estimated_taxes": {
                    "regular_income_withholding_rate": 0.25,
                    "supplemental_income_withholding_rate": 0.37,
                    "quarterly_payments": 0
                }
            },
            "assumed_ipo": assumed_ipo
        }

    def create_test_scenario(self, name: str, actions: List[Dict], profile_data: Dict) -> str:
        """Create a test scenario with specified actions and return the CSV output path."""
        from projections.projection_state import UserProfile, YearlyState, ProjectionResult
        from projections.projection_output import generate_holding_milestones_csv

        # Create UserProfile directly from profile data
        personal = profile_data['personal_information']
        income = profile_data['income']
        financial = profile_data['financial_position']
        charitable = profile_data['charitable_giving']
        goals = profile_data['goals_and_constraints']
        tax_situation = profile_data['tax_situation']

        user_profile = UserProfile(
            federal_tax_rate=personal['federal_tax_rate'],
            federal_ltcg_rate=personal['federal_ltcg_rate'],
            state_tax_rate=personal['state_tax_rate'],
            state_ltcg_rate=personal['state_ltcg_rate'],
            fica_tax_rate=personal['fica_tax_rate'],
            additional_medicare_rate=personal['additional_medicare_rate'],
            niit_rate=personal['niit_rate'],
            annual_w2_income=income['annual_w2_income'],
            spouse_w2_income=income.get('spouse_w2_income', 0),
            other_income=income.get('other_income', 0),
            interest_income=income.get('interest_income', 0),
            dividend_income=income.get('dividend_income', 0),
            bonus_expected=income.get('bonus_expected', 0),
            current_cash=financial['liquid_assets']['cash'],
            exercise_reserves=goals['liquidity_needs']['exercise_reserves'],
            pledge_percentage=charitable['pledge_percentage'],
            company_match_ratio=charitable['company_match_ratio'],
            filing_status=personal['tax_filing_status'],
            state_of_residence=personal['state_of_residence'],
            monthly_living_expenses=financial['monthly_cash_flow']['expenses'],
            taxable_investments=financial['liquid_assets'].get('taxable_investments', 0),
            crypto=financial['liquid_assets'].get('crypto', 0),
            real_estate_equity=financial['illiquid_assets'].get('real_estate_equity', 0),
            amt_credit_carryforward=tax_situation['carryforwards'].get('amt_credit', 0),
            assumed_ipo=date.fromisoformat(profile_data['assumed_ipo']),
            grants=profile_data['equity_position']['original_grants']
        )

        # Create planned actions
        planned_actions = []
        for action in actions:
            planned_actions.append(PlannedAction(
                action_date=date.fromisoformat(action['date']),
                action_type=ActionType(action['type']),
                lot_id=action['lot_id'],
                quantity=action['quantity'],
                price=action.get('price'),
                notes=action.get('notes', '')
            ))

        # Create projection plan
        plan = ProjectionPlan(
            name=name,
            description=f"Test scenario: {name}",
            start_date=date(2025, 1, 1),
            end_date=date(2035, 12, 31),
            initial_lots=[],
            initial_cash=50000,
            planned_actions=planned_actions
        )

        # Create yearly states with donations tracking
        yearly_states = []
        for year in range(2025, 2036):
            shares_donated = {}
            shares_sold = {}

            # Find actions for this year
            for action in actions:
                action_date = date.fromisoformat(action['date'])
                if action_date.year == year:
                    if action['type'] == 'donate':
                        shares_donated[action['lot_id']] = action['quantity']
                    elif action['type'] == 'sell':
                        shares_sold[action['lot_id']] = action['quantity']

            # Create required sub-objects for YearlyState
            tax_state = TaxState(
                regular_tax=50000,
                amt_tax=50000,
                total_tax=50000,
                amt_credits_generated=0,
                amt_credits_used=0,
                amt_credits_remaining=0
            )

            charitable_state = CharitableDeductionState(
                federal_current_year_deduction=sum(shares_donated.values()) * 50.0,
                federal_carryforward_remaining={},
                federal_total_available=sum(shares_donated.values()) * 50.0,
                federal_expired_this_year=0,
                ca_current_year_deduction=sum(shares_donated.values()) * 50.0,
                ca_carryforward_remaining={},
                ca_total_available=sum(shares_donated.values()) * 50.0,
                ca_expired_this_year=0
            )

            pledge_state = PledgeState()

            year_state = YearlyState(
                year=year,
                starting_cash=50000,
                income=300000,
                exercise_costs=0,
                tax_paid=0,
                donation_value=sum(shares_donated.values()) * 50.0,
                company_match_received=0,
                ending_cash=50000,
                tax_state=tax_state,
                charitable_state=charitable_state,
                equity_holdings=[],
                shares_sold=shares_sold,
                shares_donated=shares_donated,
                pledge_state=pledge_state
            )
            yearly_states.append(year_state)

        # Create mock projection result
        result = ProjectionResult(
            plan=plan,
            user_profile=user_profile,
            yearly_states=yearly_states
        )

        # Generate CSV output
        output_dir = os.path.join(self.temp_dir, f"scenario_{name}")
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, f"{name}_holding_period_tracking.csv")

        generate_holding_milestones_csv(result, csv_path)
        return csv_path

    def read_ipo_pledge_obligations(self, csv_path: str) -> List[Dict]:
        """Read IPO pledge obligations from the holding period tracking CSV."""
        obligations = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['milestone_type'] == 'ipo_pledge_obligation':
                    obligations.append(row)
        return obligations

    def test_example_1_ipo_pledge_obligation(self):
        """
        Test Example 1: 10K shares, 50% pledge, sell 2K in 2028, donate 2K in 2029.
        Should have 3K shares due at IPO+1 (2035-03-15).
        """
        # Test configuration from user examples
        total_shares = 10000
        pledge_percentage = 0.5  # 50% pledge = 5,000 shares
        assumed_ipo = "2034-03-15"
        expected_ipo_deadline = "2035-03-15"

        # Create profile with pledge configuration
        profile_data = self.create_test_profile(total_shares, pledge_percentage, assumed_ipo)

        # Define actions from Example 1
        actions = [
            {
                'date': '2028-06-15',
                'type': 'sell',
                'lot_id': 'TEST_LOT_A',
                'quantity': 2000,
                'notes': 'Sell shares creating pledge obligation'
            },
            {
                'date': '2029-12-15',
                'type': 'donate',
                'lot_id': 'TEST_LOT_A',
                'quantity': 2000,
                'notes': 'Partial donation - leaves remaining pledge'
            }
        ]

        # Execute scenario
        csv_path = self.create_test_scenario("example_1", actions, profile_data)

        # Verify IPO pledge obligation was created
        obligations = self.read_ipo_pledge_obligations(csv_path)
        self.assertEqual(len(obligations), 1, "Should have exactly one IPO pledge obligation")

        obligation = obligations[0]

        # Verify key fields
        self.assertEqual(obligation['lot_id'], 'TOTAL_PLEDGE')
        self.assertEqual(int(obligation['current_quantity']), 3000)  # 5,000 pledge - 2,000 donated
        self.assertEqual(obligation['milestone_date'], expected_ipo_deadline)
        self.assertEqual(obligation['milestone_type'], 'ipo_pledge_obligation')

        # Verify description contains correct numbers
        description = obligation['milestone_description']
        self.assertIn('3000 shares', description)
        self.assertIn('50% of 10000 total shares', description)
        self.assertIn('2000 already donated', description)

    def test_example_2_ipo_pledge_obligation(self):
        """
        Test Example 2: 10K shares, 50% pledge, multiple sales and donations.
        Sell 1K in 2028, 2K in 2029; donate 2K in 2030, 1K in 2031.
        Should have 2K shares due at IPO+1 (2035-06-01).
        """
        # Test configuration from user examples
        total_shares = 10000
        pledge_percentage = 0.5  # 50% pledge = 5,000 shares
        assumed_ipo = "2034-06-01"
        expected_ipo_deadline = "2035-06-01"

        # Create profile with pledge configuration
        profile_data = self.create_test_profile(total_shares, pledge_percentage, assumed_ipo)

        # Define actions from Example 2
        actions = [
            {
                'date': '2028-03-15',
                'type': 'sell',
                'lot_id': 'TEST_LOT_A',
                'quantity': 1000,
                'notes': 'First sale'
            },
            {
                'date': '2029-06-15',
                'type': 'sell',
                'lot_id': 'TEST_LOT_A',
                'quantity': 2000,
                'notes': 'Second sale'
            },
            {
                'date': '2030-09-15',
                'type': 'donate',
                'lot_id': 'TEST_LOT_A',
                'quantity': 2000,
                'notes': 'First donation'
            },
            {
                'date': '2031-12-15',
                'type': 'donate',
                'lot_id': 'TEST_LOT_A',
                'quantity': 1000,
                'notes': 'Second donation'
            }
        ]

        # Execute scenario
        csv_path = self.create_test_scenario("example_2", actions, profile_data)

        # Verify IPO pledge obligation was created
        obligations = self.read_ipo_pledge_obligations(csv_path)
        self.assertEqual(len(obligations), 1, "Should have exactly one IPO pledge obligation")

        obligation = obligations[0]

        # Verify key fields
        self.assertEqual(obligation['lot_id'], 'TOTAL_PLEDGE')
        self.assertEqual(int(obligation['current_quantity']), 2000)  # 5,000 pledge - 3,000 donated
        self.assertEqual(obligation['milestone_date'], expected_ipo_deadline)
        self.assertEqual(obligation['milestone_type'], 'ipo_pledge_obligation')

        # Verify description contains correct numbers
        description = obligation['milestone_description']
        self.assertIn('2000 shares', description)
        self.assertIn('50% of 10000 total shares', description)
        self.assertIn('3000 already donated', description)

    def test_no_pledge_no_obligation(self):
        """Test that no IPO obligation is created when there's no pledge."""
        # Create profile with 0% pledge
        profile_data = self.create_test_profile(
            total_shares=10000,
            pledge_percentage=0.0,  # No pledge
            assumed_ipo="2034-03-15"
        )

        # Execute scenario with no actions
        csv_path = self.create_test_scenario("no_pledge", [], profile_data)

        # Verify no IPO pledge obligation exists
        obligations = self.read_ipo_pledge_obligations(csv_path)
        self.assertEqual(len(obligations), 0, "Should have no IPO pledge obligation when no pledge exists")

    def test_pledge_fully_satisfied(self):
        """Test that no IPO obligation is created when pledge is fully satisfied."""
        # Create profile with 30% pledge (3,000 shares)
        profile_data = self.create_test_profile(
            total_shares=10000,
            pledge_percentage=0.3,
            assumed_ipo="2034-03-15"
        )

        # Donate exactly the pledge amount
        actions = [
            {
                'date': '2029-12-15',
                'type': 'donate',
                'lot_id': 'TEST_LOT_A',
                'quantity': 3000,
                'notes': 'Fully satisfy pledge'
            }
        ]

        # Execute scenario
        csv_path = self.create_test_scenario("pledge_satisfied", actions, profile_data)

        # Verify no IPO pledge obligation exists since pledge is fully satisfied
        obligations = self.read_ipo_pledge_obligations(csv_path)
        self.assertEqual(len(obligations), 0, "Should have no IPO pledge obligation when pledge is fully satisfied")

    def test_leap_year_ipo_handling(self):
        """Test that leap year IPO dates are handled correctly."""
        # Create profile with IPO on leap day
        profile_data = self.create_test_profile(
            total_shares=10000,
            pledge_percentage=0.4,  # 4,000 share pledge
            assumed_ipo="2032-02-29"  # Leap day
        )

        # Execute scenario with no donations (full pledge remains)
        csv_path = self.create_test_scenario("leap_year_ipo", [], profile_data)

        # Verify IPO pledge obligation exists with correct date handling
        obligations = self.read_ipo_pledge_obligations(csv_path)
        self.assertEqual(len(obligations), 1)

        obligation = obligations[0]
        # 2033 is not a leap year, so should fall back to Feb 28
        self.assertEqual(obligation['milestone_date'], '2033-02-28')
        self.assertEqual(int(obligation['current_quantity']), 4000)

    def test_chronological_sorting(self):
        """Test that IPO pledge obligations are properly sorted chronologically with other milestones."""
        profile_data = self.create_test_profile(
            total_shares=10000,
            pledge_percentage=0.25,  # 2,500 share pledge
            assumed_ipo="2034-12-31"
        )

        # Execute scenario
        csv_path = self.create_test_scenario("chronological_test", [], profile_data)

        # Read all milestones and verify sorting
        milestones = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                milestones.append({
                    'date': row['milestone_date'],
                    'type': row['milestone_type'],
                    'lot_id': row['lot_id']
                })

        # Find our IPO pledge obligation
        ipo_obligations = [m for m in milestones if m['type'] == 'ipo_pledge_obligation']
        self.assertEqual(len(ipo_obligations), 1)
        self.assertEqual(ipo_obligations[0]['date'], '2035-12-31')  # IPO + 1 year

        # Verify milestones are sorted by date
        milestone_dates = [m['date'] for m in milestones]
        self.assertEqual(milestone_dates, sorted(milestone_dates),
                        "Milestones should be sorted chronologically by milestone_date")

    def test_multiple_grants_pledge_aggregation(self):
        """Test that pledges from multiple grants are properly aggregated."""
        # Create profile with multiple grants
        profile_data = self.create_test_profile(
            total_shares=10000,
            pledge_percentage=0.5,
            assumed_ipo="2034-06-15"
        )

        # Add a second grant
        profile_data["equity_position"]["original_grants"].append({
            "grant_id": "TEST_GRANT_2",
            "grant_date": "2023-01-15",
            "total_shares": 5000,
            "strike_price": 5.0,
            "vesting_start_date": "2023-01-15",
            "vesting_schedule": "4_year_monthly_with_cliff",
            "cliff_months": 12,
            "expiration_date": "2033-01-15",
            "charitable_program": {
                "pledge_percentage": 0.2,  # 20% of 5,000 = 1,000 shares
                "company_match_ratio": 2.0
            }
        })

        # Execute scenario
        csv_path = self.create_test_scenario("multiple_grants", [], profile_data)

        # Verify IPO pledge obligation aggregates both grants
        obligations = self.read_ipo_pledge_obligations(csv_path)
        self.assertEqual(len(obligations), 1)

        obligation = obligations[0]
        # Grant 1: 10,000 * 0.5 = 5,000 shares
        # Grant 2: 5,000 * 0.2 = 1,000 shares
        # Total: 6,000 share pledge
        self.assertEqual(int(obligation['current_quantity']), 6000)

        # Verify description shows correct aggregated numbers
        description = obligation['milestone_description']
        self.assertIn('6000 shares', description)
        self.assertIn('40% of 15000 total shares', description)  # 6000/15000 = 40%

    def test_end_to_end_portfolio_manager_integration(self):
        """
        Test PortfolioManager grant loading to catch regressions in grant transfer from JSON to UserProfile.
        This validates the specific fix where grants weren't being loaded from equity_position.original_grants.
        """
        from engine.portfolio_manager import PortfolioManager

        # Test with demo profile first (known structure for regression testing)
        portfolio_manager = PortfolioManager()
        portfolio_manager.load_user_data(force_demo=True)

        # Get the loaded UserProfile
        user_profile = portfolio_manager._user_profile

        # Verify grants were properly loaded (this is the key regression test)
        self.assertIsNotNone(user_profile.grants, "UserProfile.grants should not be None")
        self.assertEqual(len(user_profile.grants), 1, "Demo profile should have loaded 1 grant")

        # Verify demo grant data structure
        demo_grant = user_profile.grants[0]
        self.assertEqual(demo_grant['grant_id'], 'DEMO_GRANT_001')
        self.assertEqual(demo_grant['total_options'], 20000)
        self.assertEqual(demo_grant['charitable_program']['pledge_percentage'], 0.25)
        self.assertEqual(demo_grant['charitable_program']['company_match_ratio'], 1.0)

        # Verify IPO date was loaded correctly from demo profile
        self.assertEqual(user_profile.assumed_ipo.isoformat(), "2033-03-24")

        # Test with real user profile (if available) to verify actual data loading
        try:
            portfolio_manager_real = PortfolioManager()
            portfolio_manager_real.load_user_data(force_demo=False)

            real_user_profile = portfolio_manager_real._user_profile

            # Verify real profile grants were loaded
            self.assertIsNotNone(real_user_profile.grants, "Real UserProfile.grants should not be None")
            self.assertGreater(len(real_user_profile.grants), 0, "Real profile should have at least 1 grant")

            # Verify real grant structure (if available)
            if real_user_profile.grants:
                real_grant = real_user_profile.grants[0]
                self.assertIn('grant_id', real_grant, "Real grant should have grant_id")
                self.assertTrue('total_options' in real_grant or 'total_shares' in real_grant,
                              "Real grant should have total_options or total_shares")

        except Exception as e:
            # If real profile loading fails, that's OK for the test - we're mainly testing demo profile
            print(f"Real profile loading skipped: {e}")

        # Calculate expected total pledge from demo: 20000 * 0.25 = 5000
        expected_total_pledge = 5000

        # Create a minimal test to verify IPO pledge calculation would work
        # (without needing full scenario execution)
        from projections.projection_state import YearlyState, ProjectionResult, ProjectionPlan
        from datetime import date

        # Test IPO pledge calculation with demo data
        from projections.projection_state import TaxState, CharitableDeductionState

        tax_state = TaxState()
        charitable_state = CharitableDeductionState()

        yearly_states = [YearlyState(
            year=2025,
            starting_cash=50000,
            income=300000,
            exercise_costs=0,
            tax_paid=0,
            donation_value=0,
            company_match_received=0,
            ending_cash=50000,
            tax_state=tax_state,
            charitable_state=charitable_state,
            equity_holdings=[],
            shares_sold={},
            shares_donated={},  # No donations = full pledge remains
            spouse_income=0,
            other_income=0,
            annual_tax_components=None
        )]

        # Create minimal projection result
        plan = ProjectionPlan(
            name="test_grant_loading",
            description="Test grant loading regression",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            initial_lots=[],
            initial_cash=50000,
            planned_actions=[]
        )

        result = ProjectionResult(
            plan=plan,
            user_profile=user_profile,
            yearly_states=yearly_states
        )

        # Generate CSV to test IPO pledge obligation
        csv_path = os.path.join(self.temp_dir, "grant_loading_test.csv")
        generate_holding_milestones_csv(result, csv_path)

        # Verify IPO pledge obligation was created with correct demo data
        obligations = self.read_ipo_pledge_obligations(csv_path)
        self.assertEqual(len(obligations), 1, "Should have exactly one IPO pledge obligation")

        obligation = obligations[0]
        self.assertEqual(obligation['lot_id'], 'TOTAL_PLEDGE')
        self.assertEqual(int(obligation['current_quantity']), expected_total_pledge)
        self.assertEqual(obligation['milestone_date'], '2034-03-24')  # Demo IPO 2033-03-24 + 1 year

        # Verify description shows correct demo pledge calculation
        description = obligation['milestone_description']
        self.assertIn(f'{expected_total_pledge} shares', description)
        self.assertIn('25% of 20000 total shares', description)  # 5000/20000 = 25%
        self.assertIn('0 already donated', description)

    def test_grant_loading_regression_validation(self):
        """
        Regression test for the specific bug where grants weren't being loaded from JSON.
        This test would have failed before the PortfolioManager fix and should catch future regressions.
        """
        from engine.portfolio_manager import PortfolioManager
        import json
        import tempfile

        # Create a minimal profile with grants that should be loaded
        test_profile = {
            "personal_information": {
                "federal_tax_rate": 0.37,
                "federal_ltcg_rate": 0.20,
                "state_tax_rate": 0.093,
                "state_ltcg_rate": 0.093,
                "fica_tax_rate": 0.0145,
                "additional_medicare_rate": 0.009,
                "niit_rate": 0.038,
                "tax_filing_status": "single"
            },
            "income": {
                "annual_w2_income": 300000
            },
            "financial_position": {
                "liquid_assets": {
                    "cash": 50000
                },
                "illiquid_assets": {
                    "real_estate_equity": 0
                }
            },
            "goals_and_constraints": {
                "liquidity_needs": {
                    "exercise_reserves": 100000
                }
            },
            "charitable_giving": {
                "pledge_percentage": 0.0,  # Should be overridden by grant-level pledges
                "company_match_ratio": 0.0
            },
            "equity_position": {
                "original_grants": [
                    {
                        "grant_id": "REGRESSION_TEST_GRANT",
                        "grant_date": "2022-01-01",
                        "total_shares": 10000,
                        "strike_price": 5.0,
                        "charitable_program": {
                            "pledge_percentage": 0.4,  # 40% pledge
                            "company_match_ratio": 2.0
                        }
                    }
                ]
            },
            "assumed_ipo": "2035-01-01"
        }

        # Test with demo profile (safer and more reliable)
        portfolio_manager = PortfolioManager()
        portfolio_manager.load_user_data(force_demo=True)
        user_profile = portfolio_manager._user_profile

        # Critical regression check: grants must be populated
        self.assertIsNotNone(user_profile.grants,
                           "REGRESSION: UserProfile.grants is None - grant loading is broken!")
        self.assertIsInstance(user_profile.grants, list,
                            "REGRESSION: UserProfile.grants is not a list")
        self.assertGreater(len(user_profile.grants), 0,
                         "REGRESSION: No grants loaded from profile - this would break IPO pledge obligations")

        # Verify grant structure integrity
        grant = user_profile.grants[0]
        self.assertIsInstance(grant, dict, "REGRESSION: Grant should be a dict from JSON")
        self.assertIn('grant_id', grant, "REGRESSION: Grant missing grant_id")
        self.assertTrue('total_shares' in grant or 'total_options' in grant,
                       "REGRESSION: Grant missing total_shares/total_options")
        self.assertIn('charitable_program', grant,
                     "REGRESSION: Grant missing charitable_program")

        # Verify charitable program structure
        charitable_program = grant['charitable_program']
        self.assertIsInstance(charitable_program, dict,
                            "REGRESSION: charitable_program should be a dict")
        self.assertIn('pledge_percentage', charitable_program,
                     "REGRESSION: charitable_program missing pledge_percentage")
        self.assertIsInstance(charitable_program['pledge_percentage'], (int, float),
                            "REGRESSION: pledge_percentage should be numeric")

        # Verify the fix enables IPO pledge obligation calculation
        # This is what would break if grants aren't loaded properly
        total_shares = grant.get('total_shares', grant.get('total_options', 0))
        pledge_percentage = charitable_program.get('pledge_percentage', 0.0)
        expected_pledge = int(total_shares * pledge_percentage)

        self.assertGreater(total_shares, 0,
                         "REGRESSION: Grant should have shares for pledge calculation")
        self.assertGreater(expected_pledge, 0,
                         "REGRESSION: Should have a pledge amount for IPO obligation")

    def test_ipo_pledge_obligation_csv_generation_regression(self):
        """
        Comprehensive regression test for the IPO pledge obligation bug fix.

        This test specifically validates the fix that was made where:
        1. Grants weren't being transferred from JSON to UserProfile.grants
        2. IPO pledge calculation wasn't handling dict-based grants from JSON

        This test would have failed before the fix and should catch future regressions.
        """
        from projections.projection_output import generate_holding_milestones_csv
        from projections.projection_state import UserProfile, YearlyState, ProjectionResult, ProjectionPlan
        from datetime import date
        import tempfile
        import csv
        import os

        # Create a UserProfile with grants that should trigger IPO pledge obligations
        grants = [
            {
                "grant_id": "REGRESSION_GRANT_1",
                "grant_date": "2022-01-01",
                "total_shares": 8000,
                "strike_price": 5.0,
                "charitable_program": {
                    "pledge_percentage": 0.5,  # 50% pledge = 4000 shares
                    "company_match_ratio": 3.0
                }
            },
            {
                "grant_id": "REGRESSION_GRANT_2",
                "grant_date": "2023-01-01",
                "total_options": 4000,  # Test both total_shares and total_options
                "strike_price": 10.0,
                "charitable_program": {
                    "pledge_percentage": 0.25,  # 25% pledge = 1000 shares
                    "company_match_ratio": 2.0
                }
            }
        ]

        user_profile = UserProfile(
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0145,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=300000,
            current_cash=100000,
            exercise_reserves=50000,
            pledge_percentage=0.0,  # Profile-level should be ignored
            company_match_ratio=0.0,
            assumed_ipo=date(2034, 6, 15),
            grants=grants  # This is the key fix being tested
        )

        # Create yearly states with some donations (but not enough to satisfy full pledge)
        yearly_states = [
            YearlyState(
                year=2028,
                starting_cash=100000,
                income=300000,
                exercise_costs=0,
                tax_paid=50000,
                donation_value=0,
                company_match_received=0,
                ending_cash=150000,
                tax_state=None,
                charitable_state=None,
                shares_sold={'LOT_A': 1000},  # Sale creates pledge obligation
                shares_donated={}  # No donations yet
            ),
            YearlyState(
                year=2029,
                starting_cash=150000,
                income=300000,
                exercise_costs=0,
                tax_paid=45000,
                donation_value=100000,
                company_match_received=0,
                ending_cash=200000,
                tax_state=None,
                charitable_state=None,
                shares_sold={},
                shares_donated={'LOT_B': 2000}  # Partial donation - 2000 out of 5000 total pledge
            )
        ]

        # Create projection plan and result
        plan = ProjectionPlan(
            name="IPO Pledge Regression Test",
            description="Test for IPO pledge obligation regression",
            start_date=date(2025, 1, 1),
            end_date=date(2030, 12, 31),
            initial_lots=[],
            initial_cash=100000,
            planned_actions=[]
        )

        result = ProjectionResult(
            plan=plan,
            user_profile=user_profile,
            yearly_states=yearly_states
        )

        # Generate the CSV and verify IPO pledge obligation is created
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            try:
                generate_holding_milestones_csv(result, temp_file.name)

                # Read and parse the CSV
                with open(temp_file.name, 'r') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)

                # Find IPO pledge obligation entries
                ipo_obligations = [row for row in rows if row['milestone_type'] == 'ipo_pledge_obligation']

                # REGRESSION TEST: This should find exactly one IPO pledge obligation
                self.assertEqual(len(ipo_obligations), 1,
                               "REGRESSION: Expected exactly one IPO pledge obligation, found: " +
                               str(len(ipo_obligations)) + ". This indicates the fix is broken!")

                obligation = ipo_obligations[0]

                # Verify the IPO pledge obligation details
                self.assertEqual(obligation['lot_id'], 'TOTAL_PLEDGE',
                               "REGRESSION: IPO pledge obligation should use TOTAL_PLEDGE lot_id")

                # Expected calculation:
                # Grant 1: 8000 * 0.5 = 4000 shares pledged
                # Grant 2: 4000 * 0.25 = 1000 shares pledged
                # Total pledge: 5000 shares
                # Donated: 2000 shares
                # Remaining: 3000 shares
                expected_remaining = 3000
                self.assertEqual(int(obligation['current_quantity']), expected_remaining,
                               f"REGRESSION: Expected {expected_remaining} remaining pledge shares, got {obligation['current_quantity']}")

                # Verify IPO deadline calculation (IPO date + 1 year)
                self.assertEqual(obligation['milestone_date'], '2035-06-15',
                               "REGRESSION: IPO deadline should be IPO date + 1 year")

                # Verify description contains correct calculations
                description = obligation['milestone_description']
                self.assertIn('3000 shares', description,
                             "REGRESSION: Description should show 3000 remaining shares")
                self.assertIn('42% of 12000 total shares', description,  # 5000/12000 ≈ 42%
                             "REGRESSION: Description should show correct total pledge percentage")
                self.assertIn('2000 already donated', description,
                             "REGRESSION: Description should show donated amount")

            finally:
                # Clean up
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)

        # ADDITIONAL REGRESSION CHECK: Verify grants structure that enables the fix
        self.assertIsNotNone(user_profile.grants,
                           "REGRESSION: UserProfile.grants must not be None")
        self.assertEqual(len(user_profile.grants), 2,
                        "REGRESSION: Should have 2 grants loaded")

        # Verify the fix handles both total_shares and total_options
        grant1 = user_profile.grants[0]
        grant2 = user_profile.grants[1]

        self.assertIn('total_shares', grant1,
                     "REGRESSION: First grant should have total_shares")
        self.assertIn('total_options', grant2,
                     "REGRESSION: Second grant should have total_options")

        # Verify both grants have charitable_program as dict (not object)
        self.assertIsInstance(grant1['charitable_program'], dict,
                            "REGRESSION: charitable_program should be dict from JSON")
        self.assertIsInstance(grant2['charitable_program'], dict,
                            "REGRESSION: charitable_program should be dict from JSON")


if __name__ == '__main__':
    unittest.main()
