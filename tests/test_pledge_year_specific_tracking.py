"""Test year-specific pledge tracking in annual summary."""

import sys
import os
import unittest
from datetime import date, datetime

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from projections.projection_calculator import ProjectionCalculator, ProjectionPlan
from projections.projection_state import (
    PlannedAction, ActionType, UserProfile, ShareLot, ShareType, LifecycleState, TaxTreatment
)


class TestPledgeYearSpecificTracking(unittest.TestCase):
    """Test that pledge metrics are tracked year-specifically in annual summary."""

    def test_year_specific_pledge_tracking_scenario_206_pattern(self):
        """Test pledge tracking with scenario 206 pattern - same shares sold each year."""
        # Create a minimal user profile
        profile = UserProfile(
            filing_status="single",
            annual_w2_income=200000,
            federal_tax_rate=0.35,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.093,  # CA
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0145,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            current_cash=50000,
            exercise_reserves=10000,
            pledge_percentage=0.5,  # 50% pledge
            company_match_ratio=3.0,
            assumed_ipo=date(2026, 1, 1)
        )

        # Create enough shares to sell 6214 each year
        lots = [
            ShareLot(
                lot_id=f'LOT{i}',
                grant_id='GRANT1',
                grant_date=date(2020, 1, 1),
                quantity=6214,
                strike_price=1.0,
                share_type=ShareType.NSO,
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                exercise_date=date(2023, 1, 1),
                fmv_at_exercise=10.0,
                cost_basis=1.0
            )
            for i in range(6)  # 6 lots of 6214 shares each
        ]

        # Create actions that sell 6214 shares each year (like scenario 206)
        actions = []
        for year in range(2025, 2031):  # 2025-2030
            actions.append(
                PlannedAction(
                    action_date=date(year, 6, 1),
                    action_type=ActionType.SELL,
                    lot_id=f'LOT{year - 2025}',
                    quantity=6214,
                    price=50.0 + (year - 2025) * 10  # Increasing price
                )
            )

        plan = ProjectionPlan(
            name='Test Plan - Scenario 206 Pattern',
            description='Test with same shares sold each year',
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2030, 12, 31),
            planned_actions=actions,
            initial_lots=lots,
            initial_cash=profile.current_cash,
            tax_elections={},
            price_projections={year: 50.0 + (year - 2025) * 10 for year in range(2025, 2031)}
        )

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Get yearly states
        yearly_states = {year.year: year for year in result.yearly_states}

        # With 50% pledge on 6214 shares sold each year -> 6214 shares obligated each year
        for year in range(2025, 2031):
            year_state = yearly_states[year]
            self.assertEqual(year_state.pledge_shares_obligated_this_year, 6214,
                             f"{year} should show 6214 shares obligated (50% pledge on 6214 shares sold)")

        # Check cumulative totals
        final_state = yearly_states[2030]
        total_obligated = sum(o.shares_obligated for o in final_state.pledge_state.obligations)
        self.assertEqual(total_obligated, 6214 * 6,  # 37,284 total
                         "Total cumulative obligated should be 37,284 (6214 × 6 years)")

    def test_year_specific_pledge_tracking_variable_sales(self):
        """Test pledge tracking with different sale amounts each year."""
        # Create a minimal user profile
        profile = UserProfile(
            filing_status="single",
            annual_w2_income=200000,
            federal_tax_rate=0.35,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.093,  # CA
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0145,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            current_cash=50000,
            exercise_reserves=10000,
            pledge_percentage=0.5,  # 50% pledge
            company_match_ratio=3.0,
            assumed_ipo=date(2026, 1, 1)
        )

        # Create lots with different quantities
        lots = [
            ShareLot(
                lot_id='LOT1',
                grant_id='GRANT1',
                grant_date=date(2020, 1, 1),
                quantity=10000,
                strike_price=1.0,
                share_type=ShareType.NSO,
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                exercise_date=date(2023, 1, 1),
                fmv_at_exercise=10.0,
                cost_basis=1.0
            ),
            ShareLot(
                lot_id='LOT2',
                grant_id='GRANT2',
                grant_date=date(2021, 1, 1),
                quantity=10000,
                strike_price=2.0,
                share_type=ShareType.NSO,
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                exercise_date=date(2023, 1, 1),
                fmv_at_exercise=10.0,
                cost_basis=2.0
            )
        ]

        # Create actions with different quantities each year
        actions = [
            PlannedAction(
                action_date=date(2025, 6, 1),
                action_type=ActionType.SELL,
                lot_id='LOT1',
                quantity=1000,  # Year 1: 1000 shares
                price=50.0
            ),
            PlannedAction(
                action_date=date(2026, 6, 1),
                action_type=ActionType.SELL,
                lot_id='LOT1',
                quantity=2000,  # Year 2: 2000 shares
                price=60.0
            ),
            PlannedAction(
                action_date=date(2027, 6, 1),
                action_type=ActionType.SELL,
                lot_id='LOT2',
                quantity=3000,  # Year 3: 3000 shares
                price=70.0
            ),
        ]

        plan = ProjectionPlan(
            name='Test Plan - Variable Sales',
            description='Test with different sale amounts each year',
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2027, 12, 31),
            planned_actions=actions,
            initial_lots=lots,
            initial_cash=profile.current_cash,
            tax_elections={},
            price_projections={2025: 50.0, 2026: 60.0, 2027: 70.0}
        )

        # Run projection
        calculator = ProjectionCalculator(profile)
        result = calculator.evaluate_projection_plan(plan)

        # Get yearly states
        yearly_states = {year.year: year for year in result.yearly_states}

        # Check year-specific obligations
        self.assertEqual(yearly_states[2025].pledge_shares_obligated_this_year, 1000,
                         "2025 should show 1000 shares obligated")
        self.assertEqual(yearly_states[2026].pledge_shares_obligated_this_year, 2000,
                         "2026 should show 2000 shares obligated")
        self.assertEqual(yearly_states[2027].pledge_shares_obligated_this_year, 3000,
                         "2027 should show 3000 shares obligated")

        # Check cumulative total
        final_state = yearly_states[2027]
        total_obligated = sum(o.shares_obligated for o in final_state.pledge_state.obligations)
        self.assertEqual(total_obligated, 6000,  # 1000 + 2000 + 3000
                         "Total cumulative obligated should be 6000")


if __name__ == '__main__':
    unittest.main()