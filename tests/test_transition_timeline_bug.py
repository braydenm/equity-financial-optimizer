"""Test for transition timeline bug where exercised ISOs are marked as expiring."""

import unittest
import tempfile
import os
import csv
import sys
from datetime import date

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ShareLot, ShareType, LifecycleState, TaxTreatment, YearlyState,
    ProjectionResult, ProjectionPlan, UserProfile, TaxState, CharitableDeductionState
)
from projections.projection_output import save_transition_timeline_csv


class TestTransitionTimelineBug(unittest.TestCase):
    """Test case for reproducing the bug where exercised ISOs are marked as expiring."""

    def test_exercised_iso_not_marked_as_expiring(self):
        """Test that exercised ISOs are not incorrectly marked as expiring."""

        # Create initial ISO lot (year 1)
        iso_lot_year1 = ShareLot(
            lot_id="ISO_001",
            share_type=ShareType.ISO,
            quantity=1000,
            strike_price=10.0,
            grant_date=date(2024, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2034, 1, 1),
            grant_id="GRANT_001"
        )

        # Year 1: ISO exists, some shares will be exercised (represented by different lots in year 2)
        year1_state = YearlyState(
            year=2025,
            starting_cash=100000,
            income=200000,
            exercise_costs=5000,
            tax_paid=50000,
            donation_value=0,
            company_match_received=0,
            ending_cash=95000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[iso_lot_year1],
            shares_sold={},
            shares_donated={}
        )

        # Create remaining ISO lot and exercised lot for year 2
        iso_lot_year2 = ShareLot(
            lot_id="ISO_001",
            share_type=ShareType.ISO,
            quantity=500,  # Reduced from 1000 (500 were exercised)
            strike_price=10.0,
            grant_date=date(2024, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2034, 1, 1),
            grant_id="GRANT_001"
        )

        # New exercised lot created from the 500 exercised shares
        exercised_lot = ShareLot(
            lot_id="ISO_001_EX_20250101",
            share_type=ShareType.ISO,
            quantity=500,
            strike_price=10.0,
            grant_date=date(2024, 1, 1),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2025, 1, 1),
            fmv_at_exercise=20.0,
            grant_id="GRANT_001"
        )

        # Year 2: Both lots exist (remaining options + exercised shares)
        year2_state = YearlyState(
            year=2026,
            starting_cash=95000,
            income=200000,
            exercise_costs=0,
            tax_paid=50000,
            donation_value=0,
            company_match_received=0,
            ending_cash=100000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[iso_lot_year2, exercised_lot],
            shares_sold={},
            shares_donated={}
        )

        # Create minimal profile and plan
        profile = UserProfile(
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.133,
            state_ltcg_rate=0.133,
            fica_tax_rate=0.062,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=200000,
            current_cash=100000,
            exercise_reserves=0,
            pledge_percentage=0.0,
            company_match_ratio=0.0,
            assumed_ipo=date(2033, 3, 24),
            grants=[]
        )

        plan = ProjectionPlan(
            name="Test Plan",
            description="Test for transition timeline bug",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            initial_lots=[iso_lot_year1],
            initial_cash=100000
        )

        result = ProjectionResult(
            yearly_states=[year1_state, year2_state],
            plan=plan,
            user_profile=profile,
            summary_metrics={}
        )

        # Save transition timeline CSV
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "transition_timeline.csv")
            save_transition_timeline_csv(result, csv_path)

            # Read and analyze the CSV
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Find ISO_001 rows
            iso_rows = [row for row in rows if row['Lot_ID'] == 'ISO_001']
            transitions = {row['Transition']: row for row in iso_rows}

            # Check that exercising is recorded correctly in 2026
            # Note: This logic detects exercising by the quantity decrease in the original lot
            exercising_2026 = int(transitions['Exercising'].get('2026', 0))
            self.assertEqual(exercising_2026, 500,
                           f"Expected 500 shares exercising in 2026, got {exercising_2026}")

            # BUG CHECK: Original ISO lot should NOT be marked as expiring
            # The 500 exercised shares should not appear as "expiring"
            expiring_2025 = int(transitions['Expiring'].get('2025', 0))
            self.assertEqual(expiring_2025, 0,
                           f"BUG: ISO_001 shows {expiring_2025} expiring shares in 2025, "
                           "but those shares were exercised, not expired")

            expiring_2026 = int(transitions['Expiring'].get('2026', 0))
            self.assertEqual(expiring_2026, 0,
                           f"BUG: ISO_001 shows {expiring_2026} expiring shares in 2026, "
                           "but no expiration should occur")

    def test_actual_expiration_still_works(self):
        """Test that actual option expiration is still detected correctly."""

        # Create ISO lot that will actually expire
        iso_lot_year1 = ShareLot(
            lot_id="ISO_002",
            share_type=ShareType.ISO,
            quantity=1000,
            strike_price=10.0,
            grant_date=date(2024, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2025, 12, 31),  # Expires end of 2025
            grant_id="GRANT_002"
        )

        # Year 1: ISO exists
        year1_state = YearlyState(
            year=2025,
            starting_cash=100000,
            income=200000,
            exercise_costs=0,
            tax_paid=50000,
            donation_value=0,
            company_match_received=0,
            ending_cash=100000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[iso_lot_year1],
            shares_sold={},
            shares_donated={}
        )

        # Year 2: ISO expired (lot disappeared)
        year2_state = YearlyState(
            year=2026,
            starting_cash=100000,
            income=200000,
            exercise_costs=0,
            tax_paid=50000,
            donation_value=0,
            company_match_received=0,
            ending_cash=100000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[],  # Lot disappeared due to expiration
            shares_sold={},
            shares_donated={}
        )

        # Create minimal profile and plan
        profile = UserProfile(
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.133,
            state_ltcg_rate=0.133,
            fica_tax_rate=0.062,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=200000,
            current_cash=100000,
            exercise_reserves=0,
            pledge_percentage=0.0,
            company_match_ratio=0.0,
            assumed_ipo=date(2033, 3, 24),
            grants=[]
        )

        plan = ProjectionPlan(
            name="Test Plan 2",
            description="Test for actual expiration",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            initial_lots=[iso_lot_year1],
            initial_cash=100000
        )

        result = ProjectionResult(
            yearly_states=[year1_state, year2_state],
            plan=plan,
            user_profile=profile,
            summary_metrics={}
        )

        # Save transition timeline CSV
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "transition_timeline.csv")
            save_transition_timeline_csv(result, csv_path)

            # Read and analyze the CSV
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Find ISO_002 rows
            iso_rows = [row for row in rows if row['Lot_ID'] == 'ISO_002']
            transitions = {row['Transition']: row for row in iso_rows}

            # Check that expiration is correctly recorded
            expiring_2026 = int(transitions['Expiring'].get('2026', 0))
            self.assertEqual(expiring_2026, 1000,
                           f"Expected 1000 shares expiring in 2026, got {expiring_2026}")

            # Check that no exercising occurred
            exercising_2025 = int(transitions['Exercising'].get('2025', 0))
            exercising_2026 = int(transitions['Exercising'].get('2026', 0))
            self.assertEqual(exercising_2025, 0, "No exercising should occur in 2025")
            self.assertEqual(exercising_2026, 0, "No exercising should occur in 2026")


if __name__ == '__main__':
    unittest.main()
