"""
REGRESSION TEST: AMT Credit Carryforward Bug Fix

This test validates that AMT credits properly carry forward across multiple years.
It serves as a regression test for a critical bug that was fixed in Group A1
financial calculation validation.

BUG DESCRIPTION:
In projection_calculator.py around line 218, the code incorrectly overwrote
the correct AMT credit carryforward value:

OLD (BUGGY) CODE:
    amt_credits_remaining = tax_result.federal_amt_credit_carryforward  # Correct
    # ... other code ...
    amt_credits_remaining = year_tax_state.amt_credits_remaining        # BUG: Overwrites!

RESULT: AMT credits stayed constant across all years instead of accumulating
and being consumed properly.

FIXED CODE:
    amt_credits_remaining = tax_result.federal_amt_credit_carryforward
    year_tax_state.amt_credits_remaining = amt_credits_remaining
    # ... (removed the overwrite line)

This test would FAIL under the old implementation because:
1. Credits would stay constant (e.g., 30,209 every year)
2. assertNotEqual() would fail when comparing year-over-year values
3. Credits wouldn't decrease when used in non-AMT years

Under the current (fixed) implementation, credits properly:
- Generate in AMT years (ISO exercises)
- Accumulate if still in AMT
- Get consumed in non-AMT years
- Eventually reach zero when fully used
"""

import unittest
import sys
import os
from datetime import date
from decimal import Decimal

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_calculator import ProjectionCalculator
from projections.projection_state import (
    ProjectionPlan, PlannedAction, ActionType, ShareLot, ShareType,
    LifecycleState, TaxTreatment, UserProfile
)


class TestAMTCreditCarryforward(unittest.TestCase):
    """Test that AMT credits properly carry forward across multiple years."""

    def setUp(self):
        """Set up test profile and lots for AMT credit testing."""
        self.profile = UserProfile(
            # Tax rates (required)
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.133,
            state_ltcg_rate=0.133,

            # FICA/Medicare rates (required)
            fica_tax_rate=0.0765,
            additional_medicare_rate=0.009,
            niit_rate=0.038,

            # Income (required)
            annual_w2_income=200000,

            # Financial position (required)
            current_cash=100000,
            exercise_reserves=50000,

            # Goals and constraints (required)
            pledge_percentage=0.5,
            company_match_ratio=1.0,

            # Optional fields with explicit values
            spouse_w2_income=0,
            other_income=0,
            interest_income=0,
            dividend_income=0,
            bonus_expected=0,
            monthly_living_expenses=15000,
            amt_credit_carryforward=0  # Start with no credits
        )

        # Create ISO lot that will generate AMT when exercised
        self.iso_lot = ShareLot(
            lot_id="TEST_ISO",
            share_type=ShareType.ISO,
            quantity=10000,
            strike_price=5.0,
            grant_date=date(2020, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2030, 1, 1)
        )

    def test_amt_credit_carryforward_across_years(self):
        """
        Test that AMT credits properly accumulate and get used across years.

        This test would FAIL under the old implementation where credits
        stayed constant instead of carrying forward properly.
        """
        # Create plan with ISO exercise in year 1, normal years after
        plan = ProjectionPlan(
            name="AMT Credit Test",
            description="Test AMT credit carryforward",
            start_date=date(2025, 1, 1),
            end_date=date(2028, 12, 31),
            initial_lots=[self.iso_lot],
            initial_cash=100000,
            planned_actions=[
                # Large ISO exercise in 2025 - will generate AMT and credits
                PlannedAction(
                    action_date=date(2025, 6, 1),
                    action_type=ActionType.EXERCISE,
                    lot_id="TEST_ISO",
                    quantity=10000,
                    price=50.0,  # High FMV = large bargain element
                    notes="Exercise ISOs to generate AMT credits"
                )
            ],
            price_projections={
                2025: 50.0,
                2026: 55.0,
                2027: 60.0,
                2028: 65.0
            }
        )

        # Calculate projection
        calculator = ProjectionCalculator(self.profile)
        result = calculator.evaluate_projection_plan(plan)

        # Extract AMT credit amounts by year
        amt_credits_by_year = {}
        for state in result.yearly_states:
            if hasattr(state, 'tax_state') and state.tax_state:
                amt_credits_by_year[state.year] = state.tax_state.amt_credits_remaining
            else:
                amt_credits_by_year[state.year] = 0

        print(f"AMT Credits by year: {amt_credits_by_year}")

        # CRITICAL TEST: AMT credits should change year-over-year
        # Under the OLD (buggy) implementation, credits would stay constant
        # Under the NEW (fixed) implementation, credits should vary

        # Year 2025: Should generate significant AMT credits due to ISO exercise
        self.assertGreater(amt_credits_by_year[2025], 50000,
                          "2025 should generate substantial AMT credits from ISO exercise")

        # Year 2026: Should have accumulated more credits (still in AMT due to income)
        # OR should have used some credits (if not in AMT)
        self.assertNotEqual(amt_credits_by_year[2025], amt_credits_by_year[2026],
                           "AMT credits should change from 2025 to 2026 (not stay constant)")

        # Year 2027: Should continue to change
        self.assertNotEqual(amt_credits_by_year[2026], amt_credits_by_year[2027],
                           "AMT credits should change from 2026 to 2027 (not stay constant)")

        # SPECIFIC BUG TEST: Under old implementation, all years would be equal
        all_years_equal = (amt_credits_by_year[2025] == amt_credits_by_year[2026] ==
                          amt_credits_by_year[2027] == amt_credits_by_year[2028])

        self.assertFalse(all_years_equal,
                        "AMT credits must not stay constant across all years - "
                        "this indicates the old carryforward bug")

        # Verify credits eventually get used (should trend downward in later years)
        # Once AMT stops applying, credits should be consumed
        later_years = [amt_credits_by_year[2026], amt_credits_by_year[2027], amt_credits_by_year[2028]]

        # At least one later year should have fewer credits than 2025 peak
        self.assertTrue(any(credits < amt_credits_by_year[2025] for credits in later_years),
                       "AMT credits should eventually be used in non-AMT years")

    def test_amt_credit_generation_and_usage_pattern(self):
        """
        Test specific pattern: generate in AMT year, use in regular year.

        This validates the exact scenario that was broken by the old bug.
        """
        # Smaller scenario: 2 years only
        plan = ProjectionPlan(
            name="AMT Generation and Usage",
            description="Generate AMT credits then use them",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            initial_lots=[self.iso_lot],
            initial_cash=100000,
            planned_actions=[
                # Exercise in 2025 to generate AMT
                PlannedAction(
                    action_date=date(2025, 3, 1),
                    action_type=ActionType.EXERCISE,
                    lot_id="TEST_ISO",
                    quantity=8000,  # Large enough to trigger AMT
                    price=45.0,
                    notes="Generate AMT credits"
                )
                # 2026: No actions, just regular income (should use credits)
            ],
            price_projections={2025: 45.0, 2026: 45.0}
        )

        calculator = ProjectionCalculator(self.profile)
        result = calculator.evaluate_projection_plan(plan)

        # Get the tax states
        state_2025 = next(s for s in result.yearly_states if s.year == 2025)
        state_2026 = next(s for s in result.yearly_states if s.year == 2026)

        credits_2025 = state_2025.tax_state.amt_credits_remaining
        credits_2026 = state_2026.tax_state.amt_credits_remaining

        print(f"2025 AMT Credits: {credits_2025}")
        print(f"2026 AMT Credits: {credits_2026}")

        # Validate the pattern
        self.assertGreater(credits_2025, 0, "2025 should generate AMT credits")

        # Credits should either:
        # 1. Decrease (if used in 2026), OR
        # 2. Increase (if more AMT in 2026), BUT
        # 3. NOT stay exactly the same (the old bug)
        self.assertNotEqual(credits_2025, credits_2026,
                           f"Credits should change from 2025 ({credits_2025}) to 2026 ({credits_2026}). "
                           f"Equal values indicate the old carryforward bug.")

        # Additional validation: check that tax calculations are using credits appropriately
        if hasattr(state_2026.tax_state, 'amt_credits_used'):
            if state_2026.tax_state.amt_credits_used > 0:
                # If credits were used, remaining should be less than generated
                self.assertLess(credits_2026, credits_2025,
                               "If credits were used, remaining should be less than previous year")


if __name__ == '__main__':
    unittest.main()
