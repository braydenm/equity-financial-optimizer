"""
Simple charitable deduction expiration test.

This test creates the most basic scenario possible to verify expiration logic:
- Single donation in 2025
- Controlled AGI to allow specific deduction amounts
- Verify exact expiration in 2031 (6 years after donation)
"""

import sys
import os
import unittest
from datetime import date, datetime

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from projections.projection_state import UserProfile
from projections.projection_calculator import ProjectionCalculator, ProjectionPlan
from projections.projection_state import (
    ShareLot, LifecycleState, PlannedAction, ActionType, ShareType, TaxTreatment
)


class TestSimpleExpiration(unittest.TestCase):
    """Test the most basic charitable deduction expiration scenario."""

    def setUp(self):
        """Set up test profile with controlled parameters."""
        self.profile = UserProfile(
            filing_status="single",
            annual_w2_income=100000,  # Low income for controlled deduction limits
            spouse_w2_income=0,
            other_income=0,
            federal_tax_rate=0.24,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0145,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            current_cash=1000000,
            exercise_reserves=100000,
            pledge_percentage=0.0,  # No pledges to keep it simple
            company_match_ratio=0.0  # No company match to keep it simple
        )

    def test_simple_expiration_scenario(self):
        """
        Test the simplest possible expiration scenario:

        2025: Donate $200K, use $30K → $170K carryforward (donation year)
        2026: Use $30K → $140K remaining (carryforward year 1 of 5)
        2027: Use $30K → $110K remaining (carryforward year 2 of 5)
        2028: Use $30K → $80K remaining (carryforward year 3 of 5)
        2029: Use $30K → $50K remaining (carryforward year 4 of 5)
        2030: Use $30K → $20K remaining (carryforward year 5 of 5), $20K expires at end of year
        2031: No carryforward available (already expired)
        """
        # Create a simple RSU lot for donation
        donation_lot = ShareLot(
            lot_id='SIMPLE_TEST',
            share_type=ShareType.RSU,
            quantity=2000,  # $200K at $100/share
            strike_price=0.0,
            grant_date=date(2020, 1, 1),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.LTCG,
            exercise_date=date(2023, 1, 1),
            fmv_at_exercise=25.0,
            cost_basis=0.0
        )

        # Single donation in 2025
        donation_action = PlannedAction(
            action_type=ActionType.DONATE,
            action_date=date(2025, 6, 1),
            lot_id='SIMPLE_TEST',
            quantity=2000,
            price=100.0,
            notes='Simple expiration test donation'
        )

        # 7-year projection: 2025-2031
        plan = ProjectionPlan(
            name="Simple Expiration Test",
            description="Test basic expiration after 5 years",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2031, 12, 31),
            planned_actions=[donation_action],
            initial_lots=[donation_lot],
            initial_cash=self.profile.current_cash,
            tax_elections={},
            price_projections={year: 100.0 for year in range(2025, 2032)}
        )

        # Execute projection
        calculator = ProjectionCalculator(self.profile)
        result = calculator.evaluate_projection_plan(plan)

        # Get yearly states
        states = {state.year: state for state in result.yearly_states}

        # Expected calculations:
        # AGI = $100K, Stock limit = 30% = $30K per year
        agi = 100000
        annual_stock_limit = agi * 0.30  # $30K
        donation_amount = 200000  # $200K

        print(f"\n=== Simple Expiration Test Results ===")
        print(f"AGI: ${agi:,}")
        print(f"Annual stock limit (30%): ${annual_stock_limit:,}")
        print(f"Total donation: ${donation_amount:,}")
        print(f"Expected pattern:")
        print(f"  2025: Use ${annual_stock_limit:,}, carryforward ${donation_amount - annual_stock_limit:,} (donation year)")
        print(f"  2026: Use ${annual_stock_limit:,} → $140K remaining (carryforward year 1 of 5)")
        print(f"  2027: Use ${annual_stock_limit:,} → $110K remaining (carryforward year 2 of 5)")
        print(f"  2028: Use ${annual_stock_limit:,} → $80K remaining (carryforward year 3 of 5)")
        print(f"  2029: Use ${annual_stock_limit:,} → $50K remaining (carryforward year 4 of 5)")
        print(f"  2030: Use ${annual_stock_limit:,} → $20K remaining, then $20K expires (carryforward year 5 of 5)")
        print(f"  2031: No carryforward available")
        print()

        # Track running carryforward balance for verification
        expected_carryforward = donation_amount - annual_stock_limit  # $170K after 2025

        # 2025: Donation year
        state_2025 = states[2025]
        self.assertEqual(state_2025.charitable_state.federal_current_year_deduction, annual_stock_limit)
        self.assertEqual(state_2025.charitable_state.federal_expired_this_year, 0)
        print(f"2025: ✓ Used ${state_2025.charitable_state.federal_current_year_deduction:,}, "
              f"Expired ${state_2025.charitable_state.federal_expired_this_year:,}")

        # 2026-2029: Use carryforward each year (years 1-4 of carryforward)
        for year in range(2026, 2030):
            state = states[year]
            self.assertEqual(state.charitable_state.federal_current_year_deduction, annual_stock_limit)
            self.assertEqual(state.charitable_state.federal_expired_this_year, 0)
            expected_carryforward -= annual_stock_limit
            print(f"{year}: ✓ Used ${state.charitable_state.federal_current_year_deduction:,}, "
                  f"Expired ${state.charitable_state.federal_expired_this_year:,}, "
                  f"Expected remaining after usage: ${expected_carryforward:,}")

        # 2030: Year 5 of carryforward - use $30K, then remaining $20K expires at end of year
        state_2030 = states[2030]
        expected_carryforward -= annual_stock_limit  # $50K - $30K = $20K
        expected_expired_2030 = expected_carryforward  # $20K remaining should expire

        print(f"2030: Used ${state_2030.charitable_state.federal_current_year_deduction:,}, "
              f"Expired ${state_2030.charitable_state.federal_expired_this_year:,}, "
              f"Expected used: ${annual_stock_limit:,}, Expected expired: ${expected_expired_2030:,}")

        # In 2030, should use $30K and expire remaining $20K
        self.assertEqual(state_2030.charitable_state.federal_current_year_deduction, annual_stock_limit)
        self.assertEqual(state_2030.charitable_state.federal_expired_this_year, expected_expired_2030)

        # 2031: No carryforward available (already expired)
        state_2031 = states[2031]
        print(f"2031: Used ${state_2031.charitable_state.federal_current_year_deduction:,}, "
              f"Expired ${state_2031.charitable_state.federal_expired_this_year:,}")

        # In 2031, no carryforward usage or expiration
        self.assertEqual(state_2031.charitable_state.federal_current_year_deduction, 0)
        self.assertEqual(state_2031.charitable_state.federal_expired_this_year, 0)

        # No carryforward should remain
        self.assertEqual(sum(state_2031.charitable_state.federal_carryforward_remaining.values()), 0)

        print(f"\n✅ All assertions passed! Expiration logic working correctly.")


if __name__ == '__main__':
    unittest.main()
