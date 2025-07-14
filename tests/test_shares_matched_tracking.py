#!/usr/bin/env python3
"""
Test that shares_matched_this_year is correctly tracked in annual summary CSV.
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


class TestSharesMatchedTracking(unittest.TestCase):
    """Test that shares_matched is tracked correctly in YearlyState."""

    def test_shares_matched_tracking(self):
        """
        Test that shares_matched_this_year correctly tracks the number of 
        donated shares that received company match.
        """
        # Create user profile with 50% pledge and 3:1 match
        profile = UserProfile(
            federal_tax_rate=0.24,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0145,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=200000,
            current_cash=500000,
            exercise_reserves=100000,
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
            'grant_id': 'GRANT_001',
            'grant_date': '2020-01-15',
            'total_options': 10000,
            'option_type': 'ISO',
            'strike_price': 5.0,
            'vesting_schedule': '4_year_monthly_with_cliff',
            'cliff_months': 12,
            'vesting_start_date': '2020-01-15',
            'charitable_program': {
                'pledge_percentage': 0.5,
                'company_match_ratio': 3.0
            }
        }]
        
        calculator = ProjectionCalculator(profile)
        
        # Initial lots: 10k exercised shares
        initial_lots = [
            ShareLot(
                lot_id='EXERCISED_ISO_GRANT_001',
                share_type=ShareType.ISO,
                quantity=10000,
                strike_price=5.0,
                grant_date=date(2020, 1, 15),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                expiration_date=date(2030, 1, 15),
                grant_id='GRANT_001',
                exercise_date=date(2024, 1, 1),
                fmv_at_exercise=50.0
            )
        ]
        
        # Projection plan
        plan = ProjectionPlan(
            name="Test Shares Matched Tracking",
            description="Test shares_matched_this_year field",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            initial_lots=initial_lots,
            initial_cash=500000,
            price_projections={
                2025: 50.0,
                2026: 55.0
            }
        )
        
        # Year 1: Sell 2k shares (creates 2k pledge obligation at 50%)
        plan.add_action(PlannedAction(
            action_date=date(2025, 6, 1),
            action_type=ActionType.SELL,
            lot_id='EXERCISED_ISO_GRANT_001',
            quantity=2000,
            price=50.0
        ))
        
        # Year 1: Donate 1.5k shares (only 1k will be matched due to pledge)
        plan.add_action(PlannedAction(
            action_date=date(2025, 9, 1),
            action_type=ActionType.DONATE,
            lot_id='EXERCISED_ISO_GRANT_001',
            quantity=1500,
            price=50.0
        ))
        
        # Year 2: Donate another 1k shares (500 for pledge, 500 excess)
        plan.add_action(PlannedAction(
            action_date=date(2026, 6, 1),
            action_type=ActionType.DONATE,
            lot_id='EXERCISED_ISO_GRANT_001',
            quantity=1000,
            price=55.0
        ))
        
        # Add liquidity event
        sale_event = LiquidityEvent(
            event_id="sale_2025-06-01",
            event_date=date(2025, 6, 1),
            event_type="tender_offer",
            price_per_share=50.0,
            shares_vested_at_event=10000
        )
        profile.liquidity_events = [sale_event]
        
        # Run projection
        result = calculator.evaluate_projection_plan(plan)
        
        # Check Year 1
        year_2025 = result.get_state_for_year(2025)
        print(f"\nYear 2025 Results:")
        print(f"  Shares donated: 1,500")
        print(f"  Shares matched: {year_2025.shares_matched_this_year}")
        print(f"  Company match: ${year_2025.company_match_received:,.2f}")
        
        # New FAQ-based implementation: All 1500 shares get matched
        # (50% of 10k vested = 5k max matchable, 1.5k donated < 5k cap)
        self.assertEqual(year_2025.shares_matched_this_year, 1500,
                        "All 1500 shares should be matched (under 5k cap)")
        self.assertEqual(year_2025.company_match_received, 1500 * 50.0 * 3.0,
                        "Company match should be 1500 shares × $50 × 3.0")
        
        # Check Year 2
        year_2026 = result.get_state_for_year(2026)
        print(f"\nYear 2026 Results:")
        print(f"  Shares donated: 1,000")
        print(f"  Shares matched: {year_2026.shares_matched_this_year}")
        print(f"  Company match: ${year_2026.company_match_received:,.2f}")
        
        # New implementation: All 1000 shares get matched
        # (Already donated 1.5k, so 5k - 1.5k = 3.5k remaining cap, 1k < 3.5k)
        self.assertEqual(year_2026.shares_matched_this_year, 1000,
                        "All 1000 shares should be matched (under remaining cap)")
        self.assertEqual(year_2026.company_match_received, 1000 * 55.0 * 3.0,
                        "Company match should be 1000 shares × $55 × 3.0")
        
        print(f"\n✅ Shares matched tracking is working correctly!")
        print(f"   - Shows which donations received match vs which didn't")
        print(f"   - Helps identify when donations exceed match eligibility")


if __name__ == "__main__":
    unittest.main()