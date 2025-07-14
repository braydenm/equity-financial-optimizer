#!/usr/bin/env python3
"""
Test that pledge_shares_outstanding properly decreases when obligations expire.

This test demonstrates that outstanding shares should go to 0 after windows expire,
not remain at their previous value.
"""

import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from projections.projection_calculator import ProjectionCalculator
from projections.projection_state import (
    ProjectionPlan, PlannedAction, ActionType, ShareLot, 
    UserProfile, ShareType, LifecycleState, TaxTreatment
)
from calculators.liquidity_event import LiquidityEvent
from projections.csv_generators import save_annual_summary_csv
import tempfile


class TestPledgeOutstandingExpiration(unittest.TestCase):
    """Test that outstanding pledge shares properly decrease when windows expire."""

    def test_outstanding_decreases_after_expiration(self):
        """
        Test that pledge_shares_outstanding goes to 0 after obligations expire.
        
        Scenario:
        - Year 1: Sale of 1000 shares creates 1000 share obligation (window open until year 4)
        - Year 2-3: Outstanding shows 1000
        - Year 4: Window expires, 1000 shares move to expired
        - Year 5+: Outstanding should be 0, not 1000
        """
        # Create user profile with 50% pledge
        profile = UserProfile(
            federal_tax_rate=0.24,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0145,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=200000,
            current_cash=100000,
            exercise_reserves=50000,
            pledge_percentage=0.5,
            company_match_ratio=3.0,
            filing_status='single',
            state_of_residence='California',
            spouse_w2_income=0,
            monthly_living_expenses=5000,
            taxable_investments=0
        )
        
        # Add grant
        profile.grants = [{
            'grant_id': 'TEST_GRANT',
            'grant_date': '2020-01-01',
            'total_options': 10000,
            'option_type': 'ISO',
            'strike_price': 5.0,
            'vesting_schedule': '4_year_monthly_with_cliff',
            'cliff_months': 12,
            'vesting_start_date': '2020-01-01',
            'charitable_program': {
                'pledge_percentage': 0.5,
                'company_match_ratio': 3.0
            }
        }]
        
        calculator = ProjectionCalculator(profile)
        
        # Initial lots: 10k exercised shares
        initial_lots = [
            ShareLot(
                lot_id='EXERCISED_TEST',
                share_type=ShareType.ISO,
                quantity=10000,
                strike_price=5.0,
                grant_date=date(2020, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.LTCG,
                expiration_date=date(2030, 1, 1),
                grant_id='TEST_GRANT',
                exercise_date=date(2023, 1, 1),
                fmv_at_exercise=20.0
            )
        ]
        
        # Create projection plan
        plan = ProjectionPlan(
            name="Test Outstanding Expiration",
            description="Test that outstanding goes to 0 after expiration",
            start_date=date(2024, 1, 1),
            end_date=date(2029, 12, 31),
            initial_lots=initial_lots,
            initial_cash=100000,
            price_projections={
                2024: 50.0,
                2025: 50.0,
                2026: 50.0,
                2027: 50.0,
                2028: 50.0,
                2029: 50.0
            }
        )
        
        # Year 1: Sell 1000 shares (creates 1000 share obligation with 100% pledge)
        plan.add_action(PlannedAction(
            action_date=date(2024, 6, 1),
            action_type=ActionType.SELL,
            lot_id='EXERCISED_TEST',
            quantity=1000,
            price=50.0
        ))
        
        # Run projection
        result = calculator.evaluate_projection_plan(plan)
        
        # Save to CSV to test the output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name
            
        save_annual_summary_csv(result, csv_path)
        
        # Read the CSV and check values
        import csv
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        os.unlink(csv_path)  # Clean up temp file
        
        # Check each year
        print("\nYear-by-year pledge tracking:")
        for row in rows:
            year = row['year']
            obligated = row['pledge_shares_obligated']
            outstanding = row['pledge_shares_outstanding']
            expired = row['pledge_shares_expired']
            print(f"  {year}: obligated={obligated}, outstanding={outstanding}, expired={expired}")
        
        # Year 2024: Sale creates obligation
        self.assertEqual(rows[0]['year'], '2024')
        self.assertEqual(int(rows[0]['pledge_shares_obligated']), 1000)
        self.assertEqual(int(rows[0]['pledge_shares_outstanding']), 1000)
        self.assertEqual(int(rows[0]['pledge_shares_expired']), 0)
        
        # Year 2025-2026: Outstanding remains
        self.assertEqual(int(rows[1]['pledge_shares_outstanding']), 1000)
        self.assertEqual(int(rows[2]['pledge_shares_outstanding']), 1000)
        
        # Year 2027: Window expires (3 years after 2024 sale)
        self.assertEqual(rows[3]['year'], '2027')
        self.assertEqual(int(rows[3]['pledge_shares_expired']), 1000)
        
        # Year 2028-2029: Outstanding should be 0 after expiration
        self.assertEqual(rows[4]['year'], '2028')
        self.assertEqual(int(rows[4]['pledge_shares_outstanding']), 0,
                        "Outstanding should be 0 after obligations expire")
        
        self.assertEqual(rows[5]['year'], '2029')
        self.assertEqual(int(rows[5]['pledge_shares_outstanding']), 0,
                        "Outstanding should remain 0 in subsequent years")
        
        print("\n✅ Test correctly demonstrates the desired behavior")
        print("   - Outstanding should decrease to 0 after obligations expire")
        print("   - Currently this test will FAIL, showing the bug")


if __name__ == "__main__":
    unittest.main()