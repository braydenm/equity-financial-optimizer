"""
Test option expiration functionality.

This module tests the natural expiration of options based on their expiration dates,
ensuring proper state transitions and exclusion from exercisable inventory.
"""

import unittest
from datetime import date, datetime
from decimal import Decimal
from typing import List
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ShareLot, ShareType, LifecycleState, TaxTreatment,
    ProjectionPlan, PlannedAction, ActionType, UserProfile
)
from projections.projection_calculator import ProjectionCalculator
from projections.vesting_events import process_natural_expiration, ExpirationEvent
from projections.projection_output import save_all_projection_csvs
import tempfile
import os
import csv


class TestOptionExpiration(unittest.TestCase):
    """Test option expiration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_output_dir = tempfile.mkdtemp()

        # Create a basic user profile for testing
        self.profile = UserProfile(
            # Basic personal info
            filing_status="single",
            state_of_residence="California",
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0145,
            additional_medicare_rate=0.009,
            niit_rate=0.038,

            # Income
            annual_w2_income=200000,
            spouse_w2_income=0,
            other_income=0,

            # Cash flow
            current_cash=100000,
            exercise_reserves=50000,

            # Goals
            pledge_percentage=0.1,
            company_match_ratio=2.0
        )

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.test_output_dir)

    def test_unvested_options_expire_no_opportunity_cost(self):
        """Test that unvested options expire without opportunity cost."""
        # Create lot that expires while unvested
        lot = ShareLot(
            lot_id="UNVESTED_ISO_EXPIRING",
            share_type=ShareType.ISO,
            quantity=1000,
            strike_price=10.0,
            grant_date=date(2020, 1, 1),
            lifecycle_state=LifecycleState.GRANTED_NOT_VESTED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2024, 1, 1)
        )

        lots = [lot]
        expiration_events = process_natural_expiration(lots, 2024, 25.0)

        # Should have one expiration event
        self.assertEqual(len(expiration_events), 1)

        event = expiration_events[0]
        self.assertEqual(event.lot_id, "UNVESTED_ISO_EXPIRING")
        self.assertEqual(event.quantity, 1000)
        self.assertEqual(event.expiration_date, date(2024, 1, 1))
        self.assertIn("Unvested options expired", event.notes)

        # Lot should be marked as expired
        self.assertEqual(lot.lifecycle_state, LifecycleState.EXPIRED)

    def test_vested_options_expire_with_opportunity_cost_warning(self):
        """Test that vested options expire with opportunity cost warning."""
        # Create lot that expires while vested
        lot = ShareLot(
            lot_id="VESTED_ISO_EXPIRING",
            share_type=ShareType.ISO,
            quantity=500,
            strike_price=5.0,
            grant_date=date(2020, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2024, 6, 15)
        )

        lots = [lot]
        expiration_events = process_natural_expiration(lots, 2024, 25.0)

        # Should have one expiration event
        self.assertEqual(len(expiration_events), 1)

        event = expiration_events[0]
        self.assertEqual(event.lot_id, "VESTED_ISO_EXPIRING")
        self.assertEqual(event.quantity, 500)
        self.assertEqual(event.expiration_date, date(2024, 6, 15))
        self.assertIn("Vested options expired", event.notes)
        self.assertIn("OPPORTUNITY COST:", event.notes)

        # Lot should be marked as expired
        self.assertEqual(lot.lifecycle_state, LifecycleState.EXPIRED)

    def test_mixed_portfolio_staggered_expirations(self):
        """Test portfolio with multiple lots expiring in different years."""
        lots = [
            ShareLot(
                lot_id="ISO_EXPIRES_2024",
                share_type=ShareType.ISO,
                quantity=1000,
                strike_price=10.0,
                grant_date=date(2020, 1, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2024, 1, 1)
            ),
            ShareLot(
                lot_id="NSO_EXPIRES_2025",
                share_type=ShareType.NSO,
                quantity=2000,
                strike_price=8.0,
                grant_date=date(2021, 1, 1),
                lifecycle_state=LifecycleState.GRANTED_NOT_VESTED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2025, 1, 1)
            ),
            ShareLot(
                lot_id="ISO_NO_EXPIRATION",
                share_type=ShareType.ISO,
                quantity=500,
                strike_price=12.0,
                grant_date=date(2022, 1, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=None  # No expiration
            )
        ]

        # Test 2024 expiration
        expiration_events_2024 = process_natural_expiration(lots, 2024, 0.0)
        self.assertEqual(len(expiration_events_2024), 1)
        self.assertEqual(expiration_events_2024[0].lot_id, "ISO_EXPIRES_2024")

        # Test 2025 expiration
        expiration_events_2025 = process_natural_expiration(lots, 2025, 0.0)
        self.assertEqual(len(expiration_events_2025), 1)
        self.assertEqual(expiration_events_2025[0].lot_id, "NSO_EXPIRES_2025")

        # Test 2026 - no expirations
        expiration_events_2026 = process_natural_expiration(lots, 2026, 0.0)
        self.assertEqual(len(expiration_events_2026), 0)

        # Check final states
        self.assertEqual(lots[0].lifecycle_state, LifecycleState.EXPIRED)  # ISO_EXPIRES_2024
        self.assertEqual(lots[1].lifecycle_state, LifecycleState.EXPIRED)  # NSO_EXPIRES_2025
        self.assertEqual(lots[2].lifecycle_state, LifecycleState.VESTED_NOT_EXERCISED)  # ISO_NO_EXPIRATION

    def test_expired_options_excluded_from_exercisable(self):
        """Test that expired options are excluded from exercisable inventory."""
        from projections.projection_state import YearlyState, TaxState, CharitableDeductionState

        lots = [
            ShareLot(
                lot_id="ACTIVE_ISO",
                share_type=ShareType.ISO,
                quantity=1000,
                strike_price=10.0,
                grant_date=date(2020, 1, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2030, 1, 1)  # Future expiration
            ),
            ShareLot(
                lot_id="EXPIRED_ISO",
                share_type=ShareType.ISO,
                quantity=500,
                strike_price=8.0,
                grant_date=date(2019, 1, 1),
                lifecycle_state=LifecycleState.EXPIRED,  # Already expired
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2023, 1, 1)
            )
        ]

        # Create a YearlyState with these lots
        yearly_state = YearlyState(
            year=2024,
            starting_cash=100000,
            income=200000,
            exercise_costs=0,
            tax_paid=0,
            donation_value=0,
            ending_cash=300000,
            tax_state=TaxState(),
            charitable_state=CharitableDeductionState(),
            equity_holdings=lots,
            shares_sold={},
            shares_donated={}
        )

        # Get exercisable options
        exercisable = yearly_state.get_exercisable_options()

        # Should only include the active ISO, not the expired one
        self.assertEqual(len(exercisable), 1)
        self.assertEqual(exercisable[0].lot_id, "ACTIVE_ISO")
        self.assertEqual(exercisable[0].lifecycle_state, LifecycleState.VESTED_NOT_EXERCISED)

    def test_no_expiration_for_rsus(self):
        """Test that RSUs don't expire (expiration_date should be None)."""
        rsu_lot = ShareLot(
            lot_id="RSU_LOT",
            share_type=ShareType.RSU,
            quantity=200,
            strike_price=0.0,
            grant_date=date(2020, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=None  # RSUs don't expire
        )

        lots = [rsu_lot]
        expiration_events = process_natural_expiration(lots, 2024, 0.0)

        # Should have no expiration events
        self.assertEqual(len(expiration_events), 0)

        # RSU should remain in original state
        self.assertEqual(rsu_lot.lifecycle_state, LifecycleState.VESTED_NOT_EXERCISED)

    def test_expiration_integration_with_projection_calculator(self):
        """Test that expiration events are properly tracked in projection results."""
        # Create a projection plan with expiring options
        lots = [
            ShareLot(
                lot_id="EXPIRING_ISO",
                share_type=ShareType.ISO,
                quantity=1000,
                strike_price=10.0,
                grant_date=date(2020, 1, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2024, 12, 31)
            )
        ]

        plan = ProjectionPlan(
            name="expiration_test",
            description="Test expiration events tracking",
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
            initial_lots=lots,
            initial_cash=100000,
            planned_actions=[]  # No actions, let them expire naturally
        )

        # Set price projections
        plan.price_projections = {
            2024: 25.0,
            2025: 30.0
        }

        # Run projection
        calculator = ProjectionCalculator(self.profile)
        result = calculator.evaluate_projection_plan(plan)

        # Check that 2024 state has expiration events
        state_2024 = result.get_state_for_year(2024)
        self.assertIsNotNone(state_2024)
        self.assertTrue(hasattr(state_2024, 'expiration_events'))
        self.assertEqual(len(state_2024.expiration_events), 1)

        # Check expiration event details
        expiration_event = state_2024.expiration_events[0]
        self.assertEqual(expiration_event.lot_id, "EXPIRING_ISO")
        self.assertEqual(expiration_event.quantity, 1000)
        self.assertEqual(expiration_event.expiration_date, date(2024, 12, 31))

    def test_expiration_event_to_dict(self):
        """Test ExpirationEvent.to_dict() method for CSV export."""
        event = ExpirationEvent(
            lot_id="TEST_LOT",
            expiration_date=date(2024, 6, 15),
            quantity=1500,
            share_type=ShareType.ISO,
            strike_price=10.0,
            market_price=25.0,
            notes="Test expiration event"
        )

        event_dict = event.to_dict()

        expected_dict = {
            'lot_id': 'TEST_LOT',
            'expiration_date': '2024-06-15',
            'quantity': 1500,
            'share_type': 'ISO',
            'strike_price': 10.0,
            'market_price': 25.0,
            'opportunity_cost': 22500.0,
            'notes': 'Test expiration event'
        }

        self.assertEqual(event_dict, expected_dict)

    def test_csv_output_includes_expiration_events(self):
        """Test that CSV outputs properly include expiration events."""
        # Create a projection with expiring options
        lots = [
            ShareLot(
                lot_id="CSV_EXPIRING_ISO",
                share_type=ShareType.ISO,
                quantity=750,
                strike_price=15.0,
                grant_date=date(2020, 1, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2024, 8, 31)
            )
        ]

        plan = ProjectionPlan(
            name="csv_expiration_test",
            description="Test CSV output for expiration events",
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
            initial_lots=lots,
            initial_cash=100000,
            planned_actions=[]
        )

        # Set price projections
        plan.price_projections = {
            2024: 25.0,
            2025: 30.0
        }

        # Run projection
        calculator = ProjectionCalculator(self.profile)
        result = calculator.evaluate_projection_plan(plan)

        # Generate CSV outputs
        save_all_projection_csvs(result, "test_expiration", self.test_output_dir)

        # Check that transition_timeline.csv includes expiration events
        transition_file = os.path.join(self.test_output_dir, "test_expiration_transition_timeline.csv")
        self.assertTrue(os.path.exists(transition_file))

        # Read and verify content
        with open(transition_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Should have expiration transition for our lot
            expiring_rows = [row for row in rows if row.get('Transition') == 'Expiring']
            self.assertGreater(len(expiring_rows), 0)

            # Find our specific lot
            our_lot_rows = [row for row in expiring_rows if 'CSV_EXPIRING_ISO' in str(row)]
            self.assertGreater(len(our_lot_rows), 0)


if __name__ == '__main__':
    unittest.main()
