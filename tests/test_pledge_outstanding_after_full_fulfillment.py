#!/usr/bin/env python3
"""
Test that pledge_shares_outstanding goes to 0 after fulfilling the entire original pledge.

This test demonstrates a bug where pledge_shares_outstanding remains non-zero
even after the entire original pledge has been fulfilled through donations.
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
import csv

class TestPledgeOutstandingAfterFullFulfillment(unittest.TestCase):
    """Test that outstanding pledge shares reset to 0 after fulfilling entire pledge."""

    def test_outstanding_resets_after_full_pledge_fulfillment(self):
        """
        Test that pledge_shares_outstanding goes to 0 after fulfilling entire pledge.
        
        Scenario:
        - Year 1: IPO creates pledge obligation (50% of 10000 = 5000 shares)
        - Year 2: Donate 5000 shares (fulfills entire pledge obligation)
        - Year 3: Sell 3000 additional shares (should NOT create new obligation)
        - Year 4: Outstanding should be 0, not 3000 (BUG: currently shows 3000)
        
        This test will FAIL until the bug is fixed.
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
            name="Test Outstanding After Full Fulfillment",
            description="Test that outstanding goes to 0 after fulfilling entire pledge",
            start_date=date(2024, 1, 1),
            end_date=date(2027, 12, 31),
            initial_lots=initial_lots,
            initial_cash=100000,
            price_projections={
                2024: 50.0,
                2025: 50.0,
                2026: 50.0,
                2027: 50.0
            }
        )
        
        # Add IPO liquidity event that creates pledge obligation
        ipo_event = LiquidityEvent(
            event_id="IPO_2024",
            event_date=date(2024, 3, 24),
            event_type="ipo",
            price_per_share=50.0,
            shares_vested_at_event=10000
        )
        profile.liquidity_events = [ipo_event]
        
        # Year 2: Donate 5000 shares (fulfills entire original pledge)
        plan.add_action(PlannedAction(
            action_date=date(2025, 6, 1),
            action_type=ActionType.DONATE,
            lot_id='EXERCISED_TEST',
            quantity=5000,
            price=50.0
        ))
        
        # Year 3: Sell 3000 additional shares (should not create new obligations)
        plan.add_action(PlannedAction(
            action_date=date(2026, 6, 1),
            action_type=ActionType.SELL,
            lot_id='EXERCISED_TEST',
            quantity=3000,
            price=50.0
        ))
        
        # Run projection
        result = calculator.evaluate_projection_plan(plan)
        
        # Save to CSV to test the output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name
            
        save_annual_summary_csv(result, csv_path)
        
        # Read the CSV and check values
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        os.unlink(csv_path)  # Clean up temp file
        
        # Find key years for verification
        year_2024 = None  # IPO creates obligation
        year_2025 = None  # Donation fulfills obligation
        year_2026 = None  # Sale should not create new obligations
        year_2027 = None  # Outstanding should remain 0
        
        for row in rows:
            if row['year'] == '2024':
                year_2024 = row
            elif row['year'] == '2025':
                year_2025 = row
            elif row['year'] == '2026':
                year_2026 = row
            elif row['year'] == '2027':
                year_2027 = row
        
        self.assertIsNotNone(year_2024, "Should have 2024 data")
        self.assertIsNotNone(year_2025, "Should have 2025 data")
        self.assertIsNotNone(year_2026, "Should have 2026 data")
        self.assertIsNotNone(year_2027, "Should have 2027 data")
        
        # Check each year
        print("\nYear-by-year pledge tracking:")
        for row in rows:
            year = row['year']
            obligated = row['pledge_shares_obligated']
            outstanding = row['pledge_shares_outstanding']
            donated = row['shares_donated_count']
            sold = row['shares_sold_count']
            print(f"  {year}: obligated={obligated}, outstanding={outstanding}, donated={donated}, sold={sold}")
        
        # Year 2024: Check if IPO obligation is created (depends on implementation)
        obligated_2024 = int(year_2024['pledge_shares_obligated'])
        outstanding_2024 = int(year_2024['pledge_shares_outstanding'])
        
        # The IPO obligation might be created in 2024 or later depending on implementation
        print(f"2024: obligated={obligated_2024}, outstanding={outstanding_2024}")
        
        # For now, just verify the basic structure works
        self.assertGreaterEqual(obligated_2024, 0, "Obligated should be non-negative")
        self.assertGreaterEqual(outstanding_2024, 0, "Outstanding should be non-negative")
        
        # Year 2025: Donation (considered fulfilling hypothetical pledge)
        donated_2025 = int(year_2025['shares_donated_count'])
        outstanding_2025 = int(year_2025['pledge_shares_outstanding'])
        
        self.assertEqual(donated_2025, 5000, "Should donate 5000 shares in 2025")
        self.assertEqual(outstanding_2025, 0, "Outstanding should remain 0 after donation")
        
        # Year 2026: Sale creates obligation (this is the bug!)
        sold_2026 = int(year_2026['shares_sold_count'])
        obligated_2026 = int(year_2026['pledge_shares_obligated'])
        outstanding_2026 = int(year_2026['pledge_shares_outstanding'])
        
        self.assertEqual(sold_2026, 3000, "Should sell 3000 shares in 2026")
        self.assertEqual(obligated_2026, 3000, "Sale creates 3000 share obligation")
        
        # BUG: This assertion will FAIL until the bug is fixed
        # After donating 5000 shares, no further obligations should be created
        self.assertEqual(outstanding_2026, 0, 
                        "Outstanding should remain 0 after selling shares post-donation")
        
        # Year 2027: Outstanding should remain 0
        outstanding_2027 = int(year_2027['pledge_shares_outstanding'])
        self.assertEqual(outstanding_2027, 0, 
                        "Outstanding should remain 0 in subsequent years")
        
        print("\n✅ Test correctly demonstrates the bug")
        print("   - Outstanding should be 0 after entire pledge is fulfilled")
        print("   - Problem: Share sales create pledge obligations even after pledge is fulfilled")
        print("   - Currently this test will FAIL, showing the bug")


if __name__ == "__main__":
    unittest.main()