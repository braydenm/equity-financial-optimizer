"""
Comprehensive tests for generate_holding_milestones_csv function.

This test suite identifies bugs in the milestone tracking system by testing:
1. Countdown calculation accuracy
2. Milestone date calculations
3. CSV structure and field names
4. State-based milestone logic
5. IPO integration
6. Edge cases and boundary conditions
"""

import unittest
import tempfile
import os
import csv
import sys
from datetime import date, timedelta

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ShareLot, ShareType, LifecycleState, TaxTreatment, YearlyState,
    ProjectionResult, ProjectionPlan, UserProfile, TaxState, CharitableDeductionState
)
from projections.projection_output import generate_holding_milestones_csv


class TestHoldingMilestonesComprehensive(unittest.TestCase):
    """Comprehensive tests for holding milestones CSV generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir)

    def create_basic_test_projection(self, scenario_end_year=2025):
        """Create a basic projection for testing milestone calculations."""

        # Create test lots
        vested_iso = ShareLot(
            lot_id="TEST_VESTED_ISO",
            share_type=ShareType.ISO,
            quantity=1000,
            strike_price=10.0,
            grant_date=date(2023, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2033, 1, 1),
            grant_id="GRANT_2023"
        )

        exercised_iso = ShareLot(
            lot_id="TEST_EXERCISED_ISO",
            share_type=ShareType.ISO,
            quantity=500,
            strike_price=10.0,
            grant_date=date(2023, 1, 1),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2024, 6, 1),
            fmv_at_exercise=50.0,
            grant_id="GRANT_2023"
        )

        exercised_nso = ShareLot(
            lot_id="TEST_EXERCISED_NSO",
            share_type=ShareType.NSO,
            quantity=300,
            strike_price=5.0,
            grant_date=date(2023, 1, 1),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2024, 3, 15),
            fmv_at_exercise=30.0,
            grant_id="GRANT_2023"
        )

        # Create yearly states
        final_state = YearlyState(
            year=scenario_end_year,
            starting_cash=100000,
            income=200000,
            exercise_costs=0,
            tax_paid=50000,
            donation_value=0,
            company_match_received=0,
            ending_cash=150000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[vested_iso, exercised_iso, exercised_nso],
            shares_sold={"TEST_SOLD_LOT": 200},
            shares_donated={"TEST_DONATED_LOT": 100}
        )

        # Create user profile with known IPO date
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
            assumed_ipo=date(2028, 6, 15),  # Known IPO date for testing
            grants=[]
        )

        plan = ProjectionPlan(
            name="Test Plan",
            description="Test milestones",
            start_date=date(2024, 1, 1),
            end_date=date(scenario_end_year, 12, 31),
            initial_lots=[vested_iso],
            initial_cash=100000
        )

        result = ProjectionResult(
            yearly_states=[final_state],
            plan=plan,
            user_profile=profile,
            summary_metrics={}
        )

        return result

    def test_csv_structure_and_field_names(self):
        """Test that CSV has correct structure and field names."""
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_milestones.csv")
        generate_holding_milestones_csv(result, csv_path)

        # Read CSV and check structure
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        # Check expected field names
        expected_fields = [
            'lot_id', 'current_quantity', 'lifecycle_state', 'share_type',
            'grant_date', 'exercise_date', 'exercise_date',
            'milestone_type', 'milestone_date', 'days_until_milestone',
            'years_until_milestone', 'milestone_description'
        ]

        for field in expected_fields:
            self.assertIn(field, fieldnames, f"Missing required field: {field}")

        # Check that we have data
        self.assertGreater(len(rows), 0, "CSV should contain milestone data")

    def test_countdown_calculation_accuracy(self):
        """Test that countdown calculations are accurate."""
        # Use 2025 as scenario end to get predictable countdowns
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_countdown.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find a specific milestone we can verify
        scenario_end = date(2025, 12, 31)

        for row in rows:
            if row['milestone_type'] == 'ltcg_eligible' and row['lot_id'] == 'TEST_EXERCISED_ISO':
                # Exercise date was 2024-06-01, so LTCG eligible on 2025-06-01
                expected_milestone_date = date(2025, 6, 1)
                expected_days = (expected_milestone_date - scenario_end).days
                expected_years = round(expected_days / 365.25, 1)

                actual_milestone_date = date.fromisoformat(row['milestone_date'])
                actual_days = int(row['days_until_milestone'])
                actual_years = float(row['years_until_milestone'])

                self.assertEqual(actual_milestone_date, expected_milestone_date,
                               f"LTCG milestone date incorrect: got {actual_milestone_date}, expected {expected_milestone_date}")
                self.assertEqual(actual_days, expected_days,
                               f"Days countdown incorrect: got {actual_days}, expected {expected_days}")
                self.assertAlmostEqual(actual_years, expected_years, places=1,
                                     msg=f"Years countdown incorrect: got {actual_years}, expected {expected_years}")
                break
        else:
            self.fail("Could not find LTCG milestone for TEST_EXERCISED_ISO")

    def test_vested_iso_milestones(self):
        """Test milestones for vested but not exercised ISOs."""
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_vested_iso.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find milestones for vested ISO
        vested_iso_milestones = [r for r in rows if r['lot_id'] == 'TEST_VESTED_ISO']
        milestone_types = [r['milestone_type'] for r in vested_iso_milestones]

        # Should have option expiration and IPO deadline
        self.assertIn('option_expiration', milestone_types, "Vested ISO should have option expiration milestone")
        self.assertIn('ipo_pledge_deadline', milestone_types, "Vested ISO should have IPO pledge deadline")

        # Check option expiration date is correct
        expiration_milestone = next(r for r in vested_iso_milestones if r['milestone_type'] == 'option_expiration')
        expected_expiration = date(2033, 1, 1)  # From test data
        actual_expiration = date.fromisoformat(expiration_milestone['milestone_date'])
        self.assertEqual(actual_expiration, expected_expiration, "Option expiration date incorrect")

    def test_exercised_iso_milestones(self):
        """Test milestones for exercised ISOs."""
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_exercised_iso.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find milestones for exercised ISO
        exercised_iso_milestones = [r for r in rows if r['lot_id'] == 'TEST_EXERCISED_ISO']
        milestone_types = [r['milestone_type'] for r in exercised_iso_milestones]

        # Should have LTCG, IPO deadline, and ISO qualifying
        self.assertIn('ltcg_eligible', milestone_types, "Exercised ISO should have LTCG milestone")
        self.assertIn('ipo_pledge_deadline', milestone_types, "Exercised ISO should have IPO pledge deadline")
        self.assertIn('iso_qualifying_disposition', milestone_types, "Exercised ISO should have qualifying disposition milestone")

        # Check ISO qualifying disposition logic: max(grant_date + 2 years, exercise_date + 1 year)
        qualifying_milestone = next(r for r in exercised_iso_milestones if r['milestone_type'] == 'iso_qualifying_disposition')

        grant_plus_2y = date(2025, 1, 1)  # 2023-01-01 + 2 years
        exercise_plus_1y = date(2025, 6, 1)  # 2024-06-01 + 1 year
        expected_qualifying = max(grant_plus_2y, exercise_plus_1y)  # Should be 2025-06-01

        actual_qualifying = date.fromisoformat(qualifying_milestone['milestone_date'])
        self.assertEqual(actual_qualifying, expected_qualifying,
                        f"ISO qualifying date incorrect: got {actual_qualifying}, expected {expected_qualifying}")

    def test_exercised_nso_milestones(self):
        """Test milestones for exercised NSOs."""
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_exercised_nso.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find milestones for exercised NSO
        exercised_nso_milestones = [r for r in rows if r['lot_id'] == 'TEST_EXERCISED_NSO']
        milestone_types = [r['milestone_type'] for r in exercised_nso_milestones]

        # Should have LTCG and IPO deadline, but NOT ISO qualifying
        self.assertIn('ltcg_eligible', milestone_types, "Exercised NSO should have LTCG milestone")
        self.assertIn('ipo_pledge_deadline', milestone_types, "Exercised NSO should have IPO pledge deadline")
        self.assertNotIn('iso_qualifying_disposition', milestone_types, "NSO should not have ISO qualifying milestone")

    def test_ipo_deadline_calculation(self):
        """Test IPO deadline calculation accuracy."""
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_ipo_deadline.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find IPO deadline milestones
        ipo_milestones = [r for r in rows if r['milestone_type'] == 'ipo_pledge_deadline']
        self.assertGreater(len(ipo_milestones), 0, "Should have IPO deadline milestones")

        # All IPO deadlines should be IPO date + 1 year
        expected_ipo_deadline = date(2029, 6, 15)  # 2028-06-15 + 1 year

        for milestone in ipo_milestones:
            actual_deadline = date.fromisoformat(milestone['milestone_date'])
            self.assertEqual(actual_deadline, expected_ipo_deadline,
                           f"IPO deadline incorrect for {milestone['lot_id']}: got {actual_deadline}, expected {expected_ipo_deadline}")

    def test_disposed_lots_tracking(self):
        """Test tracking of disposed lots (sold/donated)."""
        # Create projection with some disposals
        result = self.create_basic_test_projection(2025)

        # Add disposal data to multiple years
        year_2024 = YearlyState(
            year=2024,
            starting_cash=50000,
            income=200000,
            exercise_costs=0,
            tax_paid=40000,
            donation_value=10000,
            company_match_received=0,
            ending_cash=60000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[],
            shares_sold={"SOLD_LOT_2024": 1000},
            shares_donated={"DONATED_LOT_2024": 500}
        )

        result.yearly_states.insert(0, year_2024)

        csv_path = os.path.join(self.test_dir, "test_disposed.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check for disposed lot milestones
        disposed_milestones = [r for r in rows if r['current_quantity'] == '0']
        self.assertGreater(len(disposed_milestones), 0, "Should have disposed lot milestones")

        # Check for pledge window expiry
        pledge_milestones = [r for r in disposed_milestones if r['milestone_type'] == 'pledge_window_expiry']
        self.assertGreater(len(pledge_milestones), 0, "Should have pledge window expiry milestones")

        # Check for deduction expiry
        deduction_milestones = [r for r in disposed_milestones if r['milestone_type'] == 'deduction_expiry']
        self.assertGreater(len(deduction_milestones), 0, "Should have deduction expiry milestones")

    def test_leap_year_handling(self):
        """Test leap year date calculations."""
        # Create lots with Feb 29 dates
        leap_year_lot = ShareLot(
            lot_id="LEAP_YEAR_ISO",
            share_type=ShareType.ISO,
            quantity=100,
            strike_price=1.0,
            grant_date=date(2020, 2, 29),  # Leap year
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2024, 2, 29),  # Another leap year
            fmv_at_exercise=10.0,
            grant_id="LEAP_GRANT"
        )

        final_state = YearlyState(
            year=2025,
            starting_cash=100000,
            income=200000,
            exercise_costs=0,
            tax_paid=50000,
            donation_value=0,
            company_match_received=0,
            ending_cash=150000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=[leap_year_lot],
            shares_sold={},
            shares_donated={}
        )

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
            assumed_ipo=date(2028, 6, 15),
            grants=[]
        )

        plan = ProjectionPlan(
            name="Leap Year Test",
            description="Test leap year handling",
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
            initial_lots=[],
            initial_cash=100000
        )

        result = ProjectionResult(
            yearly_states=[final_state],
            plan=plan,
            user_profile=profile,
            summary_metrics={}
        )

        csv_path = os.path.join(self.test_dir, "test_leap_year.csv")
        generate_holding_milestones_csv(result, csv_path)

        # Should not crash and should handle Feb 29 -> Feb 28 conversion
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find ISO qualifying milestone
        qualifying_milestones = [r for r in rows if r['milestone_type'] == 'iso_qualifying_disposition']
        self.assertGreater(len(qualifying_milestones), 0, "Should have ISO qualifying milestone")

        # Check that dates are valid (no crash on leap year calculation)
        for milestone in qualifying_milestones:
            milestone_date = date.fromisoformat(milestone['milestone_date'])
            self.assertIsInstance(milestone_date, date, "Milestone date should be valid")

    def test_negative_countdown_bug(self):
        """Test that countdown values are not negative when they shouldn't be."""
        # Create projection with future milestones
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_negative_countdown.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check for inappropriate negative values
        scenario_end = date(2025, 12, 31)

        for row in rows:
            milestone_date = date.fromisoformat(row['milestone_date'])
            expected_days = (milestone_date - scenario_end).days
            actual_days = int(row['days_until_milestone'])

            self.assertEqual(actual_days, expected_days,
                           f"Countdown calculation error for {row['lot_id']} {row['milestone_type']}: "
                           f"got {actual_days} days, expected {expected_days} days. "
                           f"Milestone: {milestone_date}, Scenario end: {scenario_end}")

    def test_extreme_negative_countdown_detection(self):
        """Test to catch the specific bug where most milestones show extreme negative values."""
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_extreme_negative.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Count negative and extremely negative values
        negative_count = 0
        extreme_negative_count = 0
        total_count = len(rows)

        for row in rows:
            days = int(row['days_until_milestone'])
            if days < 0:
                negative_count += 1
                if days < -1000:
                    extreme_negative_count += 1

        # Should not have majority negative values for future milestones
        negative_percentage = negative_count / total_count if total_count > 0 else 0
        self.assertLess(negative_percentage, 0.5,
                       f"Too many negative countdown values: {negative_count}/{total_count} ({negative_percentage*100:.1f}%)")

        # Should not have any extreme negative values
        self.assertEqual(extreme_negative_count, 0,
                        f"Found {extreme_negative_count} extremely negative countdown values (< -1000 days)")

    def test_future_milestone_dates(self):
        """Test that milestones are properly calculated for future dates."""
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_future_milestones.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        scenario_end = date(2025, 12, 31)
        future_count = 0

        for row in rows:
            milestone_date = date.fromisoformat(row['milestone_date'])
            if milestone_date > scenario_end:
                future_count += 1

        # Should have some future milestones
        self.assertGreater(future_count, 0, "Should have some future milestones")

    def test_milestone_descriptions(self):
        """Test that milestone descriptions are meaningful."""
        result = self.create_basic_test_projection(2025)

        csv_path = os.path.join(self.test_dir, "test_descriptions.csv")
        generate_holding_milestones_csv(result, csv_path)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            description = row['milestone_description']
            milestone_type = row['milestone_type']

            # Descriptions should not be empty
            self.assertIsNotNone(description, f"Description should not be None for {milestone_type}")
            self.assertNotEqual(description.strip(), "", f"Description should not be empty for {milestone_type}")

            # Descriptions should contain relevant keywords
            if milestone_type == 'ltcg_eligible':
                self.assertIn('Long-term', description, "LTCG description should mention long-term")
            elif milestone_type == 'ipo_pledge_deadline':
                self.assertIn('IPO', description, "IPO deadline description should mention IPO")
            elif milestone_type == 'iso_qualifying_disposition':
                self.assertIn('qualifying', description, "ISO qualifying description should mention qualifying")
            elif milestone_type == 'option_expiration':
                self.assertIn('expires', description, "Option expiration description should mention expiration")

    def test_performance_with_large_dataset(self):
        """Test performance with a large number of lots."""
        # Create many lots to test performance
        lots = []
        for i in range(100):
            lot = ShareLot(
                lot_id=f"PERF_TEST_LOT_{i}",
                share_type=ShareType.ISO if i % 2 == 0 else ShareType.NSO,
                quantity=100 + i,
                strike_price=1.0 + i * 0.1,
                grant_date=date(2023, 1, 1) + timedelta(days=i),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED if i % 3 == 0 else LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.LTCG,
                exercise_date=date(2024, 1, 1) + timedelta(days=i) if i % 3 == 0 else None,
                expiration_date=date(2033, 1, 1) + timedelta(days=i) if i % 3 != 0 else None,
                grant_id=f"GRANT_{i // 10}"
            )
            lots.append(lot)

        final_state = YearlyState(
            year=2025,
            starting_cash=100000,
            income=200000,
            exercise_costs=0,
            tax_paid=50000,
            donation_value=0,
            company_match_received=0,
            ending_cash=150000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=lots,
            shares_sold={},
            shares_donated={}
        )

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
            assumed_ipo=date(2028, 6, 15),
            grants=[]
        )

        plan = ProjectionPlan(
            name="Performance Test",
            description="Test performance",
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
            initial_lots=[],
            initial_cash=100000
        )

        result = ProjectionResult(
            yearly_states=[final_state],
            plan=plan,
            user_profile=profile,
            summary_metrics={}
        )

        import time
        start_time = time.time()

        csv_path = os.path.join(self.test_dir, "test_performance.csv")
        generate_holding_milestones_csv(result, csv_path)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete in reasonable time (less than 1 second for 100 lots)
        self.assertLess(duration, 1.0, f"Performance test took too long: {duration} seconds")

        # Check that CSV was generated with expected number of entries
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have multiple milestones per lot
        self.assertGreater(len(rows), 100, "Should have more rows than lots due to multiple milestones per lot")


if __name__ == '__main__':
    unittest.main()
