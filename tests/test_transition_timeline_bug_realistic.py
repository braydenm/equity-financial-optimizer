"""Test for transition timeline bug with realistic scenario data that reproduces the actual bug."""

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


class TestTransitionTimelineBugRealistic(unittest.TestCase):
    """Test case for reproducing the actual bug from scenario 036 where exercised ISOs are marked as expiring."""

    def test_bug_exercised_iso_marked_as_expiring_same_year_as_expiration(self):
        """
        Test the actual bug: ISOs exercised in the same year they would expire
        are incorrectly marked as both exercising AND expiring.

        This reproduces the scenario 036 bug where:
        - ISO lot shows 1034 shares expiring in 2029
        - ISO_EX_20290624 lot shows 1034 shares exercising in 2029
        """

        # Create ISO lot that expires in 2029, based on scenario 036 data
        iso_lot_2028 = ShareLot(
            lot_id="ISO_EX_20290624",  # Using the actual lot ID from scenario 036
            share_type=ShareType.ISO,
            quantity=1034,  # Actual quantity from scenario 036
            strike_price=4.48,  # Realistic strike price
            grant_date=date(2019, 6, 24),  # 10 years before expiration
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2029, 6, 24),  # Expires in 2029
            grant_id="GRANT_2019_ISO"
        )

        # Year 2028: ISO exists and is about to expire
        year2028_state = YearlyState(
            year=2028,
            starting_cash=500000,
            income=350000,
            exercise_costs=0,
            tax_paid=75000,
            donation_value=0,
            company_match_received=0,
            ending_cash=525000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[iso_lot_2028],
            shares_sold={},
            shares_donated={}
        )

        # Year 2029: ISO gets exercised (lot disappears, new exercised lot appears)
        # This is the critical case - exercise happens in the same year as expiration
        exercised_lot_2029 = ShareLot(
            lot_id="ISO_EX_20290624_EXERCISED",  # New exercised lot
            share_type=ShareType.ISO,
            quantity=1034,
            strike_price=4.48,
            grant_date=date(2019, 6, 24),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2029, 6, 24),  # Exercised on expiration date
            fmv_at_exercise=137.08,  # Based on scenario 036 opportunity cost calculations
            grant_id="GRANT_2019_ISO"
        )

        # Year 2029: Original ISO lot disappears, exercised lot appears
        year2029_state = YearlyState(
            year=2029,
            starting_cash=525000,
            income=350000,
            exercise_costs=4635,  # 1034 * $4.48
            tax_paid=85000,
            donation_value=0,
            company_match_received=0,
            ending_cash=435365,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[exercised_lot_2029],  # Only exercised lot remains
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
            annual_w2_income=350000,
            current_cash=500000,
            exercise_reserves=100000,
            pledge_percentage=0.0,
            company_match_ratio=0.0,
            assumed_ipo=date(2033, 3, 24),
            grants=[]
        )

        plan = ProjectionPlan(
            name="Scenario 036 Bug Reproduction",
            description="Test for ISO exercise/expiration bug",
            start_date=date(2028, 1, 1),
            end_date=date(2029, 12, 31),
            initial_lots=[iso_lot_2028],
            initial_cash=500000
        )

        result = ProjectionResult(
            yearly_states=[year2028_state, year2029_state],
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

            # Debug: Print the CSV to see what we got
            print("\n=== TRANSITION TIMELINE CSV ===")
            for row in rows:
                if int(row.get('2029', 0)) > 0:  # Show only rows with activity in 2029
                    print(f"{row['Lot_ID']:<30} {row['Transition']:<12} 2029: {row['2029']}")

            # Find the rows for the original ISO lot
            original_iso_rows = [row for row in rows if row['Lot_ID'] == 'ISO_EX_20290624']
            self.assertTrue(len(original_iso_rows) > 0, "Original ISO lot should appear in timeline")

            original_transitions = {row['Transition']: row for row in original_iso_rows}

            # Find the rows for the exercised lot
            exercised_iso_rows = [row for row in rows if row['Lot_ID'] == 'ISO_EX_20290624_EXERCISED']
            self.assertTrue(len(exercised_iso_rows) > 0, "Exercised ISO lot should appear in timeline")

            exercised_transitions = {row['Transition']: row for row in exercised_iso_rows}

            # THE BUG CHECK: Original ISO lot should NOT show expiring shares
            # When options are exercised, they should not also be marked as expired
            original_expiring_2029 = int(original_transitions['Expiring'].get('2029', 0))
            self.assertEqual(original_expiring_2029, 0,
                           f"BUG DETECTED: ISO_EX_20290624 shows {original_expiring_2029} expiring shares in 2029, "
                           f"but these shares were exercised, not expired. "
                           f"This is the actual bug from scenario 036.")

            # Verify that the exercised lot correctly shows as exercising
            exercised_exercising_2029 = int(exercised_transitions['Exercising'].get('2029', 0))
            self.assertEqual(exercised_exercising_2029, 1034,
                           f"Expected 1034 shares exercising in exercised lot, got {exercised_exercising_2029}")

            # Additional check: make sure we're not double-counting
            # Total shares in transitions should not exceed the original lot size
            total_expiring = sum(int(row.get('2029', 0)) for row in rows if row['Transition'] == 'Expiring')
            total_exercising = sum(int(row.get('2029', 0)) for row in rows if row['Transition'] == 'Exercising')

            print(f"\n=== SUMMARY ===")
            print(f"Total shares marked as expiring in 2029: {total_expiring}")
            print(f"Total shares marked as exercising in 2029: {total_exercising}")
            print(f"Original lot size: 1034")

            # The bug would manifest as total_expiring > 0 when it should be 0
            self.assertEqual(total_expiring, 0,
                           f"BUG: {total_expiring} shares marked as expiring when they should be 0 "
                           f"(all shares were exercised, not expired)")

    def test_realistic_actual_expiration_with_partial_exercise(self):
        """
        Test a more complex realistic scenario:
        - ISO lot with 2000 shares expiring in 2030
        - 1500 shares get exercised in early 2029
        - 500 shares actually expire at end of 2030

        Expected result:
        - 1500 shares marked as exercising
        - 500 shares marked as expiring
        - No double counting
        """

        # Create ISO lot that expires in 2030
        iso_lot_2028 = ShareLot(
            lot_id="ISO_PARTIAL_TEST",
            share_type=ShareType.ISO,
            quantity=2000,
            strike_price=5.00,
            grant_date=date(2019, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2030, 12, 31),
            grant_id="GRANT_2019_PARTIAL"
        )

        # Year 2028: Full ISO lot exists
        year2028_state = YearlyState(
            year=2028,
            starting_cash=400000,
            income=300000,
            exercise_costs=0,
            tax_paid=60000,
            donation_value=0,
            company_match_received=0,
            ending_cash=440000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[iso_lot_2028],
            shares_sold={},
            shares_donated={}
        )

        # Year 2029: Partial exercise + partial expiration
        # Remaining 500 shares in original lot (will expire)
        remaining_iso_lot = ShareLot(
            lot_id="ISO_PARTIAL_TEST",
            share_type=ShareType.ISO,
            quantity=500,  # Reduced from 2000
            strike_price=5.00,
            grant_date=date(2019, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2030, 12, 31),
            grant_id="GRANT_2019_PARTIAL"
        )

        # Exercised 1500 shares
        exercised_lot = ShareLot(
            lot_id="ISO_PARTIAL_TEST_EX_20290615",
            share_type=ShareType.ISO,
            quantity=1500,
            strike_price=5.00,
            grant_date=date(2019, 1, 1),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2029, 6, 15),
            fmv_at_exercise=100.00,
            grant_id="GRANT_2019_PARTIAL"
        )

        year2029_state = YearlyState(
            year=2029,
            starting_cash=440000,
            income=300000,
            exercise_costs=7500,  # 1500 * $5.00
            tax_paid=70000,
            donation_value=0,
            company_match_received=0,
            ending_cash=362500,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[remaining_iso_lot, exercised_lot],
            shares_sold={},
            shares_donated={}
        )

        # Year 2030: Remaining 500 shares expired (lot disappeared)
        year2030_state = YearlyState(
            year=2030,
            starting_cash=362500,
            income=300000,
            exercise_costs=0,
            tax_paid=65000,
            donation_value=0,
            company_match_received=0,
            ending_cash=597500,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[exercised_lot],  # Only exercised lot remains
            shares_sold={},
            shares_donated={}
        )

        profile = UserProfile(
            federal_tax_rate=0.35,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.10,
            state_ltcg_rate=0.10,
            fica_tax_rate=0.062,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=300000,
            current_cash=400000,
            exercise_reserves=50000,
            pledge_percentage=0.0,
            company_match_ratio=0.0,
            assumed_ipo=date(2033, 3, 24),
            grants=[]
        )

        plan = ProjectionPlan(
            name="Partial Exercise Test",
            description="Test partial exercise with partial expiration",
            start_date=date(2028, 1, 1),
            end_date=date(2030, 12, 31),
            initial_lots=[iso_lot_2028],
            initial_cash=400000
        )

        result = ProjectionResult(
            yearly_states=[year2028_state, year2029_state, year2030_state],
            plan=plan,
            user_profile=profile,
            summary_metrics={}
        )

        # Save and analyze CSV
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "transition_timeline_partial.csv")
            save_transition_timeline_csv(result, csv_path)

            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Find original lot transitions
            original_rows = [row for row in rows if row['Lot_ID'] == 'ISO_PARTIAL_TEST']
            original_transitions = {row['Transition']: row for row in original_rows}

            # Check exercising in 2029 (partial exercise)
            exercising_2029 = int(original_transitions['Exercising'].get('2029', 0))
            self.assertEqual(exercising_2029, 1500,
                           f"Expected 1500 shares exercising in 2029, got {exercising_2029}")

            # Check expiring in 2030 (remaining shares expire)
            expiring_2030 = int(original_transitions['Expiring'].get('2030', 0))
            self.assertEqual(expiring_2030, 500,
                           f"Expected 500 shares expiring in 2030, got {expiring_2030}")

            # Make sure no expiring in 2029 (before actual expiration date)
            expiring_2029 = int(original_transitions['Expiring'].get('2029', 0))
            self.assertEqual(expiring_2029, 0,
                           f"No shares should expire in 2029 (expiration date is 2030-12-31), got {expiring_2029}")

            print(f"\n=== PARTIAL EXERCISE TEST RESULTS ===")
            print(f"2029 Exercising: {exercising_2029} (expected: 1500)")
            print(f"2029 Expiring: {expiring_2029} (expected: 0)")
            print(f"2030 Expiring: {expiring_2030} (expected: 500)")


if __name__ == '__main__':
    unittest.main()
