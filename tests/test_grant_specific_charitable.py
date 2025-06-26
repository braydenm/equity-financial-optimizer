"""
Test grant-specific charitable program functionality.

This test verifies that the system correctly uses different charitable programs
for different grants when creating pledge obligations.
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
from projections.projection_calculator import ProjectionCalculator
from projections.projection_state import (
    ProjectionPlan, PlannedAction, ShareLot, UserProfile,
    ShareType, LifecycleState, TaxTreatment, ActionType
)


class TestGrantSpecificCharitable(unittest.TestCase):
    """Test grant-specific charitable program functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir)

    def create_multi_grant_profile(self):
        """Create a profile with multiple grants having different charitable programs."""
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
                    "cash": 100000,
                    "taxable_investments": 0
                },
                "monthly_cash_flow": {
                    "expenses": 8000
                }
            },
            "goals_and_constraints": {
                "liquidity_needs": {
                    "exercise_reserves": 50000
                }
            },
            "equity_position": {
                "company": "TestCorp",
                "original_grants": [
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
                    },
                    {
                        "grant_id": "GRANT_003",
                        "grant_date": "2024-01-01",
                        "total_options": 3000,
                        "isos": 1500,
                        "nsos": 1500,
                        "strike_price": 10.0,
                        "vesting_start_date": "2024-01-01",
                        "vesting_schedule": "4_year_monthly_with_cliff",
                        "cliff_months": 12,
                        "expiration_date": "2034-01-01"
                        # No charitable_program - should use fallback
                    }
                ],
                "exercised_lots": [],
                "vested_unexercised": {},
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

    def create_lots_with_different_grants(self):
        """Create lots with different grant IDs."""
        lots = [
            ShareLot(
                lot_id="LOT_GRANT_001",
                share_type=ShareType.NSO,
                quantity=1000,
                strike_price=2.5,
                grant_date=date(2022, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                exercise_date=date(2024, 1, 1),
                cost_basis=2.5,
                fmv_at_exercise=15.0,
                grant_id="GRANT_001"
            ),
            ShareLot(
                lot_id="LOT_GRANT_002",
                share_type=ShareType.NSO,
                quantity=500,
                strike_price=5.0,
                grant_date=date(2023, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                exercise_date=date(2024, 6, 1),
                cost_basis=5.0,
                fmv_at_exercise=15.0,
                grant_id="GRANT_002"
            ),
            ShareLot(
                lot_id="LOT_GRANT_003",
                share_type=ShareType.NSO,
                quantity=300,
                strike_price=10.0,
                grant_date=date(2024, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                exercise_date=date(2024, 12, 1),
                cost_basis=10.0,
                fmv_at_exercise=15.0,
                grant_id="GRANT_003"
            ),
            ShareLot(
                lot_id="LOT_NO_GRANT",
                share_type=ShareType.NSO,
                quantity=200,
                strike_price=1.0,
                grant_date=date(2021, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                exercise_date=date(2023, 1, 1),
                cost_basis=1.0,
                fmv_at_exercise=15.0,
                grant_id=None  # No grant ID
            )
        ]
        return lots

    def test_charitable_program_lookup_method(self):
        """Test the _get_charitable_program_for_grant method directly."""
        # Create profile with grants
        profile_data = self.create_multi_grant_profile()

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Load profile
        loader = ScenarioLoader(self.test_dir)
        profile = loader._load_user_profile(Path(profile_path))

        # Create calculator
        calculator = ProjectionCalculator(profile)

        # Test grant-specific lookups
        grant_001_program = calculator._get_charitable_program_for_grant("GRANT_001")
        self.assertEqual(grant_001_program['pledge_percentage'], 0.5)
        self.assertEqual(grant_001_program['company_match_ratio'], 3.0)

        grant_002_program = calculator._get_charitable_program_for_grant("GRANT_002")
        self.assertEqual(grant_002_program['pledge_percentage'], 0.25)
        self.assertEqual(grant_002_program['company_match_ratio'], 1.0)

        # Test grant without charitable program (should use profile defaults)
        grant_003_program = calculator._get_charitable_program_for_grant("GRANT_003")
        self.assertEqual(grant_003_program['pledge_percentage'], 0.5)  # From GRANT_001 (first grant)
        self.assertEqual(grant_003_program['company_match_ratio'], 3.0)  # From GRANT_001

        # Test non-existent grant (should use profile defaults)
        nonexistent_program = calculator._get_charitable_program_for_grant("NONEXISTENT")
        self.assertEqual(nonexistent_program['pledge_percentage'], 0.5)
        self.assertEqual(nonexistent_program['company_match_ratio'], 3.0)

        # Test None grant_id (should use profile defaults)
        none_program = calculator._get_charitable_program_for_grant(None)
        self.assertEqual(none_program['pledge_percentage'], 0.5)
        self.assertEqual(none_program['company_match_ratio'], 3.0)

    def test_pledge_obligations_use_grant_specific_programs(self):
        """Test that pledge obligations use the correct charitable program based on grant."""
        # Create profile with grants
        profile_data = self.create_multi_grant_profile()

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Load profile
        loader = ScenarioLoader(self.test_dir)
        profile = loader._load_user_profile(Path(profile_path))

        # Create lots with different grants
        lots = self.create_lots_with_different_grants()

        # Create projection plan with sales from different grants
        plan = ProjectionPlan(
            name="Test Grant-Specific Charitable",
            description="Test different charitable programs per grant",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            initial_lots=lots,
            initial_cash=100000,
            price_projections={2025: 20.0}
        )

        # Add sales from different grants
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 1),
            action_type=ActionType.SELL,
            lot_id="LOT_GRANT_001",  # 50% pledge, 3.0x match
            quantity=100,
            price=20.0
        ))

        plan.add_action(PlannedAction(
            action_date=date(2025, 6, 1),
            action_type=ActionType.SELL,
            lot_id="LOT_GRANT_002",  # 25% pledge, 1.0x match
            quantity=100,
            price=20.0
        ))

        plan.add_action(PlannedAction(
            action_date=date(2025, 9, 1),
            action_type=ActionType.SELL,
            lot_id="LOT_GRANT_003",  # No charitable program (should use defaults)
            quantity=100,
            price=20.0
        ))

        plan.add_action(PlannedAction(
            action_date=date(2025, 12, 1),
            action_type=ActionType.SELL,
            lot_id="LOT_NO_GRANT",  # No grant_id (should use defaults)
            quantity=100,
            price=20.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Verify pledge obligations were created with correct percentages
        self.assertIsNotNone(result)
        # Get final year's pledge state
        final_year_state = result.yearly_states[-1]
        pledge_state = final_year_state.pledge_state

        # Should have 4 obligations
        self.assertEqual(len(pledge_state.obligations), 4)

        # Check GRANT_001 obligation (50% pledge)
        grant_001_obligation = next(
            (o for o in pledge_state.obligations if "LOT_GRANT_001" in o.parent_transaction_id),
            None
        )
        self.assertIsNotNone(grant_001_obligation)
        self.assertEqual(grant_001_obligation.pledge_percentage, 0.5)
        # With 50% pledge: shares_donated = (0.5 * 100) / (1 - 0.5) = 100
        expected_shares = int((0.5 * 100) / (1 - 0.5))
        self.assertEqual(grant_001_obligation.maximalist_shares_required, expected_shares)

        # Check GRANT_002 obligation (25% pledge)
        grant_002_obligation = next(
            (o for o in pledge_state.obligations if "LOT_GRANT_002" in o.parent_transaction_id),
            None
        )
        self.assertIsNotNone(grant_002_obligation)
        self.assertEqual(grant_002_obligation.pledge_percentage, 0.25)
        # With 25% pledge: shares_donated = (0.25 * 100) / (1 - 0.25) = 33.33 -> 33
        expected_shares = int((0.25 * 100) / (1 - 0.25))
        self.assertEqual(grant_002_obligation.maximalist_shares_required, expected_shares)

        # Check GRANT_003 obligation (should use default 50% pledge)
        grant_003_obligation = next(
            (o for o in pledge_state.obligations if "LOT_GRANT_003" in o.parent_transaction_id),
            None
        )
        self.assertIsNotNone(grant_003_obligation)
        self.assertEqual(grant_003_obligation.pledge_percentage, 0.5)  # Default from first grant

        # Check no-grant obligation (should use default 50% pledge)
        no_grant_obligation = next(
            (o for o in pledge_state.obligations if "LOT_NO_GRANT" in o.parent_transaction_id),
            None
        )
        self.assertIsNotNone(no_grant_obligation)
        self.assertEqual(no_grant_obligation.pledge_percentage, 0.5)  # Default from first grant

    def test_profile_grants_data_preserved(self):
        """Test that grants data is properly preserved in UserProfile."""
        profile_data = self.create_multi_grant_profile()

        # Save to file
        profile_path = os.path.join(self.test_dir, "test_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)

        # Load profile
        loader = ScenarioLoader(self.test_dir)
        profile = loader._load_user_profile(Path(profile_path))

        # Verify grants data is preserved
        self.assertEqual(len(profile.grants), 3)

        # Check GRANT_001
        grant_001 = profile.grants[0]
        self.assertEqual(grant_001['grant_id'], 'GRANT_001')
        self.assertEqual(grant_001['charitable_program']['pledge_percentage'], 0.5)
        self.assertEqual(grant_001['charitable_program']['company_match_ratio'], 3.0)

        # Check GRANT_002
        grant_002 = profile.grants[1]
        self.assertEqual(grant_002['grant_id'], 'GRANT_002')
        self.assertEqual(grant_002['charitable_program']['pledge_percentage'], 0.25)
        self.assertEqual(grant_002['charitable_program']['company_match_ratio'], 1.0)

        # Check GRANT_003 (no charitable program)
        grant_003 = profile.grants[2]
        self.assertEqual(grant_003['grant_id'], 'GRANT_003')
        self.assertNotIn('charitable_program', grant_003)


if __name__ == '__main__':
    unittest.main()
