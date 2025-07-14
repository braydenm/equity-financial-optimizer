#!/usr/bin/env python3
"""
Test demonstrating the company match bug where donations within the 3-year window
receive 0 match when they exceed pledge obligations.

This test shows the current incorrect behavior and what the correct behavior should be.
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


class TestCompanyMatchWindowBug(unittest.TestCase):
    """Test that demonstrates the company match calculation bug."""

    def test_donation_within_window_gets_zero_match(self):
        """
        Test showing that donations within the 3-year window incorrectly 
        receive 0 match when they exceed pledge obligations.
        
        This mirrors the bug seen in scenario 101 where 2025 donations get 0 match.
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
        
        # Add grant with 50% pledge
        profile.grants = [{
            'grant_id': 'TEST_GRANT_001',
            'grant_date': '2020-01-15',
            'total_options': 20000,
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
        
        # Initial lots: 20k exercised shares
        initial_lots = [
            ShareLot(
                lot_id='EXERCISED_ISO_TEST_GRANT_001',
                share_type=ShareType.ISO,
                quantity=20000,
                strike_price=5.0,
                grant_date=date(2020, 1, 15),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                expiration_date=date(2030, 1, 15),
                grant_id='TEST_GRANT_001',
                exercise_date=date(2024, 1, 1),
                fmv_at_exercise=50.0
            )
        ]
        
        # Create projection plan
        plan = ProjectionPlan(
            name="Test Company Match Window Bug",
            description="Demonstrates donations getting 0 match within window",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            initial_lots=initial_lots,
            initial_cash=100000,
            price_projections={
                2025: 50.0,
                2026: 55.0
            }
        )
        
        # No sales = no pledge obligations created
        # Just a pure donation to test match eligibility
        
        # Year 1: Donate 2.5k shares (should be eligible for match)
        plan.add_action(PlannedAction(
            action_date=date(2025, 9, 1),
            action_type=ActionType.DONATE,
            lot_id='EXERCISED_ISO_TEST_GRANT_001',
            quantity=2500,
            price=50.0
        ))
        
        # Add a historical liquidity event to establish the match window
        # This represents a past tender offer that makes donations eligible
        historical_event = LiquidityEvent(
            event_id="past_tender_2024",
            event_date=date(2024, 6, 1),
            event_type="tender_offer",
            price_per_share=45.0,
            shares_vested_at_event=20000
        )
        profile.liquidity_events = [historical_event]
        
        # Run projection
        result = calculator.evaluate_projection_plan(plan)
        
        # Check Year 1 results
        year_2025 = result.get_state_for_year(2025)
        
        print(f"\n=== Test Results ===")
        print(f"Donation details:")
        print(f"  - Date: 2025-09-01")
        print(f"  - Shares donated: 2,500")
        print(f"  - Share price: $50")
        print(f"  - Donation value: ${year_2025.donation_value:,.2f}")
        
        print(f"\nLiquidity event window:")
        print(f"  - Past tender offer: 2024-06-01")
        print(f"  - Window closes: 2027-06-01")
        print(f"  - Donation within window: YES")
        
        print(f"\nMatch eligibility:")
        print(f"  - Total vested shares: 20,000")
        print(f"  - Pledge percentage: 50%")
        print(f"  - Max matchable shares: 10,000")
        print(f"  - Previously donated: 0")
        print(f"  - Shares eligible for match: 2,500")
        
        print(f"\nActual results:")
        print(f"  - Company match received: ${year_2025.company_match_received:,.2f}")
        print(f"  - Shares matched: {year_2025.shares_matched_this_year}")
        
        # Expected vs actual
        expected_match = 2500 * 50.0 * 3.0  # All shares should get 3:1 match
        
        print(f"\nExpected behavior (per FAQ):")
        print(f"  - All 2,500 shares should receive 3:1 match")
        print(f"  - Expected match: ${expected_match:,.2f}")
        
        print(f"\nCurrent behavior (bug):")
        print(f"  - Match based on pledge fulfillment")
        print(f"  - No pledge obligations = $0 match")
        print(f"  - This is INCORRECT per the FAQ")
        
        # After fix: Verify correct behavior
        self.assertEqual(year_2025.company_match_received, expected_match,
                        "Company match should be based on vesting eligibility, not pledge")
        self.assertEqual(year_2025.shares_matched_this_year, 2500,
                        "All 2,500 shares should be matched")
        
        print(f"\n✅ FIXED: Donations within window now receive correct match")
        print(f"   2,500 shares matched × $50 × 3.0 = ${expected_match:,.2f}")


if __name__ == "__main__":
    unittest.main()