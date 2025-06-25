#!/usr/bin/env python3
"""
Comprehensive test suite for CSV generation.

This test validates that all CSV outputs contain the correct data and format,
addressing all the issues identified in the CSV generation review.

Run with: python3 tests/test_csv_generation_comprehensive.py
"""

import sys
import os
import csv
import shutil
from datetime import date, timedelta
from typing import Dict, List, Any, Optional
import unittest

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ProjectionPlan, ProjectionResult, YearlyState, ShareLot, PlannedAction,
    UserProfile, TaxState, CharitableDeductionState, PledgeState, PledgeObligation,
    ShareType, LifecycleState, TaxTreatment, ActionType
)
from projections.projection_calculator import ProjectionCalculator
from projections.projection_output import save_all_projection_csvs
from calculators.components import AnnualTaxComponents, ShareSaleComponents, DonationComponents
from projections.pledge_calculator import PledgeCalculator


class TestCSVGeneration(unittest.TestCase):
    """Comprehensive tests for CSV generation."""

    def setUp(self):
        """Set up test environment."""
        self.test_output_dir = "output/test_csv_generation"
        if os.path.exists(self.test_output_dir):
            shutil.rmtree(self.test_output_dir)
        os.makedirs(self.test_output_dir, exist_ok=True)

    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.test_output_dir):
            shutil.rmtree(self.test_output_dir)

    def create_comprehensive_test_data(self) -> tuple[UserProfile, ProjectionPlan]:
        """Create test data that exercises all CSV features."""
        # Create user profile with spouse income
        profile = UserProfile(
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0765,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=300000,
            spouse_w2_income=150000,  # Should show in CSV
            other_income=10000,
            current_cash=100000,
            exercise_reserves=50000,
            pledge_percentage=0.5,
            company_match_ratio=3.0,
            filing_status="married_filing_jointly",
            state_of_residence="California"
        )

        # Create projection plan with various lot types
        plan = ProjectionPlan(
            name="Comprehensive CSV Test",
            description="Test scenario exercising all CSV features",
            start_date=date(2025, 1, 1),
            end_date=date(2027, 12, 31),
            initial_lots=[
                # Granted but not vested shares (should show in Granted state)
                ShareLot(
                    lot_id="ISO_GRANT_2024",
                    share_type=ShareType.ISO,
                    quantity=5000,
                    strike_price=10.0,
                    grant_date=date(2024, 1, 1),
                    lifecycle_state=LifecycleState.GRANTED_NOT_VESTED,
                    tax_treatment=TaxTreatment.NA,
                    expiration_date=date(2034, 1, 1)
                ),
                # Lot that will vest automatically
                ShareLot(
                    lot_id="VEST_20250615_ISO",
                    share_type=ShareType.ISO,
                    quantity=3000,
                    strike_price=8.0,
                    grant_date=date(2024, 6, 15),
                    lifecycle_state=LifecycleState.GRANTED_NOT_VESTED,
                    tax_treatment=TaxTreatment.NA,
                    expiration_date=date(2034, 6, 15)
                ),
                # Vested NSOs ready to exercise
                ShareLot(
                    lot_id="NSO",
                    share_type=ShareType.NSO,
                    quantity=4000,
                    strike_price=5.0,
                    grant_date=date(2022, 1, 1),
                    lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                    tax_treatment=TaxTreatment.NA,
                    expiration_date=date(2032, 1, 1)
                ),
                # Vested ISOs ready to exercise
                ShareLot(
                    lot_id="ISO",
                    share_type=ShareType.ISO,
                    quantity=10000,
                    strike_price=5.0,
                    grant_date=date(2022, 1, 1),
                    lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                    tax_treatment=TaxTreatment.NA,
                    expiration_date=date(2032, 1, 1)
                ),
                # Exercised shares ready to sell
                ShareLot(
                    lot_id="RSU_2021",
                    share_type=ShareType.RSU,
                    quantity=2000,
                    strike_price=0.0,
                    grant_date=date(2021, 1, 1),
                    lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                    tax_treatment=TaxTreatment.LTCG,
                    exercise_date=date(2021, 1, 1),
                    cost_basis=0.0,
                    fmv_at_exercise=20.0
                ),
                # NSO lot that will expire in 2026
                ShareLot(
                    lot_id="NSO_OLD",
                    share_type=ShareType.NSO,
                    quantity=1000,
                    strike_price=15.0,
                    grant_date=date(2016, 6, 1),  # 10 years = expires 2026
                    lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                    tax_treatment=TaxTreatment.NA,
                    expiration_date=date(2026, 6, 1)
                )
            ],
            initial_cash=100000
        )

        # Add planned actions
        actions = [
            # Exercise with cost (should show exercise_cost in annual_summary)
            PlannedAction(
                action_date=date(2025, 7, 1),
                action_type=ActionType.EXERCISE,
                lot_id="ISO",
                quantity=5000,
                price=50.0,
                notes="Exercise half of vested ISOs"
            ),
            # Sale creating pledge
            PlannedAction(
                action_date=date(2025, 8, 1),
                action_type=ActionType.SELL,
                lot_id="RSU_2021",
                quantity=1000,
                price=60.0,
                notes="Sell RSUs creating pledge obligation"
            ),
            # Donation (should show in charitable_carryforward.csv)
            PlannedAction(
                action_date=date(2025, 9, 1),
                action_type=ActionType.DONATE,
                lot_id="RSU_2021",
                quantity=500,
                price=60.0,
                notes="Donate to partially fulfill pledge"
            ),
            # Another donation to complete pledge
            PlannedAction(
                action_date=date(2026, 3, 1),
                action_type=ActionType.DONATE,
                lot_id="RSU_2021",
                quantity=500,
                price=65.0,
                notes="Complete pledge fulfillment"
            )
        ]

        for action in actions:
            plan.add_action(action)

        # Set price projections
        plan.price_projections = {
            2025: 50.0,
            2026: 60.0,
            2027: 70.0
        }

        return profile, plan

    def test_annual_tax_detail_shows_spouse_income(self):
        """Test that annual_tax_detail.csv includes spouse income."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read annual_tax_detail.csv
        csv_path = os.path.join(self.test_output_dir, "test_annual_tax_detail.csv")
        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check 2025 row
        year_2025 = next((r for r in rows if r['year'] == '2025'), None)
        self.assertIsNotNone(year_2025)
        self.assertEqual(float(year_2025['spouse_income']), 150000.0)
        self.assertEqual(float(year_2025['w2_income']), 300000.0)

    def test_annual_summary_shows_exercise_costs(self):
        """Test that annual_summary.csv shows exercise costs."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read annual_summary.csv
        csv_path = os.path.join(self.test_output_dir, "test_annual_summary.csv")
        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check 2025 row (year with exercise)
        year_2025 = next((r for r in rows if r['year'] == '2025'), None)
        self.assertIsNotNone(year_2025)
        # 5000 shares * $5 strike = $25,000
        self.assertEqual(float(year_2025['exercise_costs']), 25000.0)

    def test_charitable_carryforward_tracks_donations(self):
        """Test that charitable_carryforward.csv tracks donations."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read charitable_carryforward.csv
        csv_path = os.path.join(self.test_output_dir, "test_charitable_carryforward.csv")
        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check 2025 row (year with donation)
        year_2025 = next((r for r in rows if r['year'] == '2025'), None)
        self.assertIsNotNone(year_2025)
        # 500 shares * $60 = $30,000
        self.assertEqual(float(year_2025['stock_donations']), 30000.0)

        # Check AGI includes spouse income
        agi = float(year_2025['agi'])
        # At minimum: 300k (W2) + 150k (spouse) + 10k (other) + 60k (LTCG from sale)
        self.assertGreaterEqual(agi, 520000.0)

    def test_state_timeline_shows_granted_shares(self):
        """Test that state_timeline.csv shows granted shares."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read state_timeline.csv
        csv_path = os.path.join(self.test_output_dir, "test_state_timeline.csv")
        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find ISO_GRANT_2024 in Granted state
        granted_row = next((r for r in rows if r['Lot_ID'] == 'ISO_GRANT_2024' and r['State'] == 'Granted'), None)
        self.assertIsNotNone(granted_row)
        # Should show 5000 shares in 2025
        self.assertEqual(int(granted_row.get('2025', 0)), 5000)

    def test_transition_timeline_shows_vesting(self):
        """Test that transition_timeline.csv shows vesting transitions."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read transition_timeline.csv
        csv_path = os.path.join(self.test_output_dir, "test_transition_timeline.csv")
        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find VEST_20250615_ISO vesting transition
        vesting_row = next((r for r in rows if 'VEST_20250615_ISO' in r['Lot_ID'] and r['Transition'] == 'Vesting'), None)
        self.assertIsNotNone(vesting_row)
        # Should show 3000 shares vesting in 2025
        self.assertEqual(int(vesting_row.get('2025', 0)), 3000)

    @unittest.skip("Skipping expiration test - lifecycle event detection removed in favor of natural state transitions")
    def test_transition_timeline_shows_expiration(self):
        """Test that transition_timeline.csv shows expiration events."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read transition_timeline.csv
        csv_path = os.path.join(self.test_output_dir, "test_transition_timeline.csv")
        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Find NSO_OLD expiration
        expiring_row = next((r for r in rows if r['Lot_ID'] == 'NSO_OLD' and r['Transition'] == 'Expiring'), None)
        self.assertIsNotNone(expiring_row)
        # Should show 1000 shares expiring in 2026
        self.assertEqual(int(expiring_row.get('2026', 0)), 1000)



    def test_holding_period_tracking(self):
        """Test that holding_period_tracking.csv shows correct periods."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read holding_period_tracking.csv
        csv_path = os.path.join(self.test_output_dir, "test_holding_period_tracking.csv")
        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check for milestone tracking entries
        # Look for any lot with milestones
        milestone_entries = [r for r in rows if r.get('milestone_type')]
        self.assertGreater(len(milestone_entries), 0, f"No milestone entries found in holding_period_tracking. Rows: {rows}")

        # Check that we have proper milestone structure
        first_milestone = milestone_entries[0]
        required_fields = ['milestone_type', 'milestone_date', 'days_until_milestone', 'milestone_description']
        for field in required_fields:
            self.assertIn(field, first_milestone, f"Missing required field {field} in milestone entry")

        # Check for LTCG or IPO deadline milestones for exercised lots
        exercised_milestones = [r for r in milestone_entries if 'exercised_not_disposed' in r.get('lifecycle_state', '')]
        if exercised_milestones:
            milestone_types = [r['milestone_type'] for r in exercised_milestones]
            self.assertTrue(any('ltcg' in mt.lower() or 'ipo' in mt.lower() for mt in milestone_types),
                          f"Expected LTCG or IPO milestones for exercised lots, got: {milestone_types}")

    def test_vested_iso_renamed_in_csvs(self):
        """Test that VESTED_ISO is renamed to ISO in CSVs."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Check state_timeline.csv
        csv_path = os.path.join(self.test_output_dir, "test_state_timeline.csv")
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should find 'ISO' not 'VESTED_ISO'
        iso_rows = [r for r in rows if r['Lot_ID'] == 'ISO']
        vested_iso_rows = [r for r in rows if r['Lot_ID'] == 'VESTED_ISO']

        self.assertGreater(len(iso_rows), 0, "Should have ISO rows")
        self.assertEqual(len(vested_iso_rows), 0, "Should not have VESTED_ISO rows")

    def test_group_totals_in_state_timeline(self):
        """Test that state_timeline.csv shows group TOTAL rows."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read state_timeline.csv
        csv_path = os.path.join(self.test_output_dir, "test_state_timeline.csv")
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have TOTAL rows for groups
        total_rows = [r for r in rows if r['State'] == 'TOTAL']
        self.assertGreater(len(total_rows), 0, "Should have group TOTAL rows")

        # Should have SUBTOTAL rows for exercised lots
        subtotal_rows = [r for r in rows if r['State'] == 'SUBTOTAL']
        # We create an exercised lot, so should have at least one
        self.assertGreater(len(subtotal_rows), 0, "Should have SUBTOTAL rows for exercised lots")

    def test_all_transitions_positive(self):
        """Test that transition_timeline.csv only shows positive values."""
        profile, plan = self.create_comprehensive_test_data()

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSVs
        save_all_projection_csvs(result, "test", self.test_output_dir)

        # Read transition_timeline.csv
        csv_path = os.path.join(self.test_output_dir, "test_transition_timeline.csv")
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check all numeric values are non-negative
        for row in rows:
            for year in ['2025', '2026', '2027']:
                if year in row:
                    value = float(row.get(year, 0))
                    self.assertGreaterEqual(value, 0,
                        f"Negative value {value} found in {row['Lot_ID']} {row['Transition']} for {year}")


if __name__ == "__main__":
    unittest.main()
