#!/usr/bin/env python3
"""
Test to verify components CSV data quality.

This test verifies that components.csv contains proper data:
1. All component fields are automatically included
2. Date fields are properly formatted
3. Financial calculations are accurate
4. Component types are correctly identified
5. No manual field mapping is required
"""

import sys
import os
import unittest
import tempfile
import csv
from datetime import date

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ProjectionResult, ProjectionPlan, YearlyState, UserProfile, TaxState,
    CharitableDeductionState, PledgeState, ShareLot, LifecycleState, ShareType,
    TaxTreatment, PlannedAction, ActionType
)
from calculators.components import (
    AnnualTaxComponents, ISOExerciseComponents, NSOExerciseComponents,
    ShareSaleComponents, DonationComponents, DispositionType
)
from projections.csv_generators import save_components_csv
from projections.projection_calculator import ProjectionCalculator


class TestComponentsCSVDataQuality(unittest.TestCase):
    """Test the data quality of the new components CSV output."""

    def create_test_scenario(self):
        """Create a test scenario with various component types."""
        # Create user profile
        profile = UserProfile(
            annual_w2_income=200000,
            spouse_w2_income=0,
            other_income=0,
            filing_status='single',
            state_of_residence='California',
            federal_tax_rate=0.32,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0765,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            current_cash=500000,
            exercise_reserves=100000,
            pledge_percentage=0.1,
            company_match_ratio=1.0
        )

        # Create initial lots
        initial_lots = [
            # ISO lot - vested, ready to exercise
            ShareLot(
                lot_id="ISO_2022",
                share_type=ShareType.ISO,
                quantity=1000,
                strike_price=10.0,
                grant_date=date(2022, 1, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2032, 1, 1)
            ),
            # NSO lot - vested, ready to exercise
            ShareLot(
                lot_id="NSO_2022",
                share_type=ShareType.NSO,
                quantity=500,
                strike_price=15.0,
                grant_date=date(2022, 6, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2032, 6, 1)
            ),
            # RSU lot - already exercised, can be sold/donated
            ShareLot(
                lot_id="RSU_2023",
                share_type=ShareType.RSU,
                quantity=2000,
                strike_price=0.0,
                grant_date=date(2023, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.LTCG,
                exercise_date=date(2023, 1, 1),
                fmv_at_exercise=30.0
            )
        ]

        # Create projection plan with actions
        plan = ProjectionPlan(
            name="Components CSV Test",
            description="Test all component types",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            initial_cash=500000,
            initial_lots=initial_lots,
            planned_actions=[
                # ISO exercise
                PlannedAction(
                    action_date=date(2025, 3, 15),
                    action_type=ActionType.EXERCISE,
                    lot_id="ISO_2022",
                    quantity=500,
                    notes="ISO exercise test"
                ),
                # NSO exercise
                PlannedAction(
                    action_date=date(2025, 6, 1),
                    action_type=ActionType.EXERCISE,
                    lot_id="NSO_2022",
                    quantity=300,
                    notes="NSO exercise test"
                ),
                # Share sale (LTCG)
                PlannedAction(
                    action_date=date(2025, 9, 1),
                    action_type=ActionType.SELL,
                    lot_id="RSU_2023",
                    quantity=1000,
                    price=50.0,
                    notes="LTCG sale test"
                ),
                # Share donation
                PlannedAction(
                    action_date=date(2025, 12, 1),
                    action_type=ActionType.DONATE,
                    lot_id="RSU_2023",
                    quantity=500,
                    price=55.0,
                    notes="Stock donation test"
                ),
                # ISO sale (qualifying disposition)
                PlannedAction(
                    action_date=date(2026, 6, 1),
                    action_type=ActionType.SELL,
                    lot_id="ISO_2022_EX_20250315",
                    quantity=200,
                    price=60.0,
                    notes="Qualifying ISO sale"
                )
            ],
            price_projections={
                2025: 45.0,
                2026: 60.0
            }
        )

        return profile, plan

    def test_components_csv_data_quality(self):
        """Test that components CSV contains accurate and complete data."""
        profile, plan = self.create_test_scenario()

        # Execute projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate components CSV
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "test_components.csv")
            save_components_csv(result, csv_path)

            # Read and analyze the CSV
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

        # Should have 5 rows (2 exercises, 2 sales, 1 donation)
        self.assertEqual(len(rows), 5, "Should have 5 component rows")

        # Group rows by component type
        rows_by_type = {}
        for row in rows:
            comp_type = row['component_type']
            if comp_type not in rows_by_type:
                rows_by_type[comp_type] = []
            rows_by_type[comp_type].append(row)

        # Test ISO exercise
        iso_exercises = rows_by_type.get('ISO Exercise', [])
        self.assertEqual(len(iso_exercises), 1, "Should have 1 ISO exercise")
        iso_ex = iso_exercises[0]
        self.assertEqual(iso_ex['shares_exercised'], '500')
        self.assertEqual(iso_ex['strike_price'], '10.0')
        self.assertEqual(iso_ex['fmv_at_exercise'], '45.0')
        self.assertEqual(float(iso_ex['bargain_element']), 17500.0)  # (45-10)*500
        self.assertEqual(iso_ex['calculator_name'], 'iso_exercise_calculator')
        self.assertEqual(iso_ex['action_type'], 'exercise')
        self.assertEqual(iso_ex['action_date'], '2025-03-15')

        # Test NSO exercise
        nso_exercises = rows_by_type.get('NSO Exercise', [])
        self.assertEqual(len(nso_exercises), 1, "Should have 1 NSO exercise")
        nso_ex = nso_exercises[0]
        self.assertEqual(nso_ex['shares_exercised'], '300')
        self.assertEqual(nso_ex['strike_price'], '15.0')
        self.assertEqual(nso_ex['fmv_at_exercise'], '45.0')
        self.assertEqual(float(nso_ex['bargain_element']), 9000.0)  # (45-15)*300
        self.assertEqual(nso_ex['calculator_name'], 'nso_exercise_calculator')

        # Test sales
        sales = rows_by_type.get('Sale', [])
        self.assertEqual(len(sales), 2, "Should have 2 sales")

        # LTCG sale
        ltcg_sale = next(s for s in sales if s['lot_id'] == 'RSU_2023')
        self.assertEqual(ltcg_sale['shares_sold'], '1000')
        self.assertEqual(ltcg_sale['sale_price'], '50.0')
        self.assertEqual(float(ltcg_sale['gross_proceeds']), 50000.0)
        self.assertEqual(ltcg_sale['tax_treatment'], 'LTCG')
        self.assertTrue(float(ltcg_sale['long_term_gain']) > 0)
        self.assertEqual(float(ltcg_sale['short_term_gain']), 0.0)

        # Qualifying ISO sale
        iso_sale = next(s for s in sales if s['lot_id'] == 'ISO_2022_EX_20250315')
        self.assertEqual(iso_sale['shares_sold'], '200')
        self.assertEqual(iso_sale['disposition_type'], 'qualifying_iso')
        self.assertEqual(iso_sale['tax_treatment'], 'Qualifying')

        # Test donation
        donations = rows_by_type.get('Stock Donation', [])
        self.assertEqual(len(donations), 1, "Should have 1 donation")
        donation = donations[0]
        self.assertEqual(donation['shares_donated'], '500')
        self.assertEqual(donation['fmv_at_donation'], '55.0')
        self.assertEqual(float(donation['donation_value']), 27500.0)
        self.assertIn('company_match_amount', donation)  # Field should exist
        self.assertTrue(float(donation['company_match_amount']) >= 0)  # Can be 0 if no match earned

        # Verify all component fields are included automatically
        # Check that ISO exercise has all expected fields
        expected_iso_fields = {
            'lot_id', 'exercise_date', 'shares_exercised', 'strike_price',
            'fmv_at_exercise', 'exercise_cost', 'bargain_element', 'grant_date',
            'action_date', 'action_type', 'calculator_name'
        }
        iso_fields = set(iso_ex.keys())
        for field in expected_iso_fields:
            self.assertIn(field, iso_fields, f"ISO exercise should have {field} field")

        # Verify dates are properly formatted
        for row in rows:
            if 'action_date' in row and row['action_date']:
                # Should be ISO format YYYY-MM-DD
                self.assertRegex(row['action_date'], r'^\d{4}-\d{2}-\d{2}$',
                               "Dates should be in ISO format")

        print("✅ All components CSV data quality tests passed!")


def run_test():
    """Run the components CSV data quality test."""
    print("\n" + "="*70)
    print("COMPONENTS CSV DATA QUALITY TEST")
    print("="*70)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestComponentsCSVDataQuality)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_test()
    sys.exit(0 if success else 1)
