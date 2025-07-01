"""
Test charitable program per-grant loading functionality.

This test verifies that the charitable giving system correctly reads
charitable programs from individual grants rather than top-level profile settings.
"""

import unittest
import tempfile
import json
import os
import sys
from datetime import date
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.scenario_loader import ScenarioLoader
from engine.natural_evolution_generator import load_user_profile_simplified
from projections.projection_state import UserProfile


class TestCharitablePerGrant(unittest.TestCase):
    """Test charitable program loading from per-grant structure."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir)

    def create_test_profile(self, charitable_program=None, multiple_grants=False):
        """Create a test profile with per-grant charitable programs."""
        grants = []

        if multiple_grants:
            grants = [
                {
                    "grant_id": "GRANT_001",
                    "grant_date": "2022-01-01",
                    "total_options": 10000,
                    "isos": 5000,
                    "nsos": 5000,
                    "strike_price": 2.5,
                    "vesting_start_date": "2022-01-01",
                    "vesting_schedule": "4_year_monthly_with_cliff",
                    "cliff_months": 12,
                    "expiration_date": "2032-01-01",
                    "charitable_program": {
                        "pledge_percentage": 0.5,
                        "company_match_ratio": 3.0
                    }
                },
                {
                    "grant_id": "GRANT_002",
                    "grant_date": "2023-01-01",
                    "total_options": 5000,
                    "isos": 2500,
                    "nsos": 2500,
                    "strike_price": 5.0,
                    "vesting_start_date": "2023-01-01",
                    "vesting_schedule": "4_year_monthly_with_cliff",
                    "cliff_months": 12,
                    "expiration_date": "2033-01-01",
                    "charitable_program": {
                        "pledge_percentage": 0.25,
                        "company_match_ratio": 1.0
                    }
                }
            ]
        else:
            grant = {
                "grant_id": "GRANT_001",
                "grant_date": "2022-01-01",
                "total_options": 10000,
                "isos": 5000,
                "nsos": 5000,
                "strike_price": 2.5,
                "vesting_start_date": "2022-01-01",
                "vesting_schedule": "4_year_monthly_with_cliff",
                "cliff_months": 12,
                "expiration_date": "2032-01-01"
            }

            if charitable_program:
                grant["charitable_program"] = charitable_program

            grants = [grant]

        profile_data = {
            "personal_information": {
                "federal_tax_rate": 0.37,
                "federal_ltcg_rate": 0.20,
                "state_tax_rate": 0.133,
                "state_ltcg_rate": 0.133,
                "fica_tax_rate": 0.062,
                "additional_medicare_rate": 0.009,
                "niit_rate": 0.038,
                "tax_filing_status": "single",
                "state_of_residence": "California"
            },
            "income": {
                "annual_w2_income": 200000,
                "spouse_w2_income": 0,
                "other_income": 0,
                "interest_income": 0,
                "dividend_income": 0,
                "bonus_expected": 0
            },
            "financial_position": {
                "liquid_assets": {
                    "cash": 50000,
                    "taxable_investments": 0
                },
                "monthly_cash_flow": {
                    "expenses": 8000
                }
            },
            "goals_and_constraints": {
                "liquidity_needs": {
                    "exercise_reserves": 25000
                }
            },
            "equity_position": {
                "company": "TestCorp",
                "grants": grants,
                "exercised_lots": [],
                "vested_unexercised": {
                    "iso_shares": 1000,
                    "nso_shares": 500
                },
                "unvested": {
                    "vesting_calendar": []
                }
            },
            "tax_situation": {
                "estimated_taxes": {
                    "regular_income_withholding_rate": 0.25,
                    "supplemental_income_withholding_rate": 0.40,
                    "quarterly_payments": 5000
                },
                "carryforwards": {
                    "amt_credit": 0
                }
            },
            "assumed_ipo": "2030-01-01"
        }

        return profile_data

    def test_charitable_program_loading_scenario_loader(self):
        """Test that scenario loader reads charitable programs from grants."""
        # Create profile with charitable program
        charitable_program = {
            "pledge_percentage": 0.6,
            "company_match_ratio": 4.0
        }
        profile_data = self.create_test_profile(charitable_program=charitable_program)

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Create scenario loader
        loader = ScenarioLoader(self.test_dir)

        # Load profile
        profile = loader._load_user_profile(Path(profile_path))

        # Verify charitable program values
        self.assertEqual(profile.pledge_percentage, 0.6)
        self.assertEqual(profile.company_match_ratio, 4.0)

    def test_charitable_program_loading_natural_evolution(self):
        """Test that natural evolution generator reads charitable programs from grants."""
        # Create profile with charitable program
        charitable_program = {
            "pledge_percentage": 0.3,
            "company_match_ratio": 2.5
        }
        profile_data = self.create_test_profile(charitable_program=charitable_program)

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Load profile
        profile = load_user_profile_simplified(profile_path)

        # Verify charitable program values
        self.assertEqual(profile.pledge_percentage, 0.3)
        self.assertEqual(profile.company_match_ratio, 2.5)

    def test_charitable_program_fallback_scenario_loader(self):
        """Test fallback behavior when no charitable program is defined."""
        # Create profile without charitable program
        profile_data = self.create_test_profile(charitable_program=None)

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Create scenario loader
        loader = ScenarioLoader(self.test_dir)

        # Load profile
        profile = loader._load_user_profile(Path(profile_path))

        # Verify fallback values
        self.assertEqual(profile.pledge_percentage, 0.0)
        self.assertEqual(profile.company_match_ratio, 0.0)

    def test_charitable_program_fallback_natural_evolution(self):
        """Test fallback behavior in natural evolution generator."""
        # Create profile without charitable program
        profile_data = self.create_test_profile(charitable_program=None)

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Load profile
        profile = load_user_profile_simplified(profile_path)

        # Verify fallback values
        self.assertEqual(profile.pledge_percentage, 0.0)
        self.assertEqual(profile.company_match_ratio, 0.0)

    def test_multiple_grants_uses_first_grant(self):
        """Test that with multiple grants, the first grant's charitable program is used."""
        # Create profile with multiple grants having different charitable programs
        profile_data = self.create_test_profile(multiple_grants=True)

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Create scenario loader
        loader = ScenarioLoader(self.test_dir)

        # Load profile
        profile = loader._load_user_profile(Path(profile_path))

        # Verify that first grant's charitable program is used
        self.assertEqual(profile.pledge_percentage, 0.5)  # From GRANT_001
        self.assertEqual(profile.company_match_ratio, 3.0)  # From GRANT_001

    def test_profile_without_grants(self):
        """Test behavior when profile has no grants."""
        profile_data = self.create_test_profile()

        # Remove grants
        profile_data["equity_position"]["grants"] = []

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Create scenario loader
        loader = ScenarioLoader(self.test_dir)

        # Load profile
        profile = loader._load_user_profile(Path(profile_path))

        # Verify fallback values
        self.assertEqual(profile.pledge_percentage, 0.0)
        self.assertEqual(profile.company_match_ratio, 0.0)

    def test_assumed_ipo_loading(self):
        """Test that assumed_ipo is correctly loaded."""
        profile_data = self.create_test_profile()

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Create scenario loader
        loader = ScenarioLoader(self.test_dir)

        # Load profile
        profile = loader._load_user_profile(Path(profile_path))

        # Verify assumed_ipo
        self.assertEqual(profile.assumed_ipo, date(2030, 1, 1))


if __name__ == '__main__':
    unittest.main()
