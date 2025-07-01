"""
Test that IPO-triggered pledge obligations are properly tracked and expired.

This test verifies that when a user has a 50% pledge obligation and makes zero
donations, the entire pledge amount shows as expired after IPO + 3 years.
"""

import unittest
import sys
import os
from datetime import date
from decimal import Decimal

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_calculator import ProjectionCalculator
from projections.projection_state import (
    UserProfile, ShareLot, LifecycleState, ActionType, PlannedAction, ProjectionPlan,
    ShareType, TaxTreatment
)


class TestIPOPledgeZeroDonations(unittest.TestCase):
    """Test IPO-triggered pledge obligations with zero donations."""

    def setUp(self):
        """Create test profile with 50% pledge and IPO date."""
        self.profile = UserProfile(
            # Tax rates
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0765,
            additional_medicare_rate=0.009,
            niit_rate=0.038,

            # Income
            annual_w2_income=400000,
            spouse_w2_income=0,
            other_income=0,
            interest_income=5000,
            dividend_income=5000,

            # Financial position
            current_cash=100000,
            exercise_reserves=50000,
            taxable_investments=0,
            real_estate_equity=0,

            # Goals and constraints
            pledge_percentage=0.5,  # 50% pledge
            company_match_ratio=3.0,

            # Other parameters
            filing_status='married_filing_jointly',
            state_of_residence='California',
            investment_return_rate=0.07,
            monthly_living_expenses=10000,

            # IPO and grants
            assumed_ipo=date(2028, 3, 1),  # IPO in 2028
            grants=[
                {
                    'grant_id': 'GRANT_001',
                    'grant_date': '2023-01-01',
                    'total_shares': 80000,
                    'vesting_start_date': '2023-01-01',
                    'vesting_schedule': '4_year_monthly_with_cliff',
                    'cliff_months': 12,
                    'charitable_program': {
                        'pledge_percentage': 0.5,
                        'company_match_ratio': 3.0
                    }
                },
                {
                    'grant_id': 'GRANT_002',
                    'grant_date': '2024-01-01',
                    'total_options': 40000,
                    'vesting_start_date': '2024-01-01',
                    'vesting_schedule': '4_year_monthly_with_cliff',
                    'cliff_months': 12,
                    'charitable_program': {
                        'pledge_percentage': 0.5,
                        'company_match_ratio': 3.0
                    }
                }
            ]
        )

        # Create initial lots (already exercised shares)
        self.initial_lots = [
            ShareLot(
                lot_id='LOT_001',
                share_type=ShareType.ISO,
                quantity=50000,
                strike_price=2.00,
                grant_date=date(2023, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.LTCG,
                exercise_date=date(2024, 1, 15),
                cost_basis=2.00,
                fmv_at_exercise=10.00,
                grant_id='GRANT_001'
            ),
            ShareLot(
                lot_id='LOT_002',
                share_type=ShareType.NSO,
                quantity=30000,
                strike_price=3.00,
                grant_date=date(2024, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.STCG,
                exercise_date=date(2024, 6, 15),
                cost_basis=3.00,
                fmv_at_exercise=12.00,
                grant_id='GRANT_002'
            )
        ]

    def test_ipo_pledge_obligation_with_zero_donations(self):
        """Test that zero donations result in expired pledge obligations after IPO."""
        # Create a projection plan with NO actions (no sales, no donations)
        plan = ProjectionPlan(
            name='Natural Evolution - Zero Donations',
            description='No actions taken, testing IPO pledge trigger',
            start_date=date(2025, 1, 1),
            end_date=date(2032, 12, 31),  # Run past IPO + 3 years (window closure)
            initial_cash=self.profile.current_cash,
            initial_lots=self.initial_lots,
            tax_elections={}
        )

        # Set up price projections
        for year in range(2025, 2033):
            plan.price_projections[year] = 25.00

        # Create calculator and run projection
        calculator = ProjectionCalculator(self.profile)
        result = calculator.evaluate_projection_plan(plan)

        # Calculate summary metrics
        result.calculate_summary_metrics()
        metrics = result.summary_metrics

        # Expected values
        # Total shares from grants: 80,000 + 40,000 = 120,000
        # At IPO (March 2028), calculate vested shares:
        # GRANT_001: Started Jan 2023, by Mar 2028 = 62 months = fully vested (80,000)
        # GRANT_002: Started Jan 2024, by Mar 2028 = 50 months = fully vested (40,000)
        # Total vested: 80,000 + 40,000 = 120,000
        # At 50% pledge: 120,000 * 50% = 60,000 obligated
        expected_obligated = 60000
        expected_expired = 60000  # All should expire after IPO + 3 years

        # Verify pledge obligations
        print(f"\nPledge Metrics:")
        print(f"  Shares Obligated: {metrics.get('pledge_shares_obligated', 0):,}")
        print(f"  Shares Donated: {metrics.get('pledge_shares_donated', 0):,}")
        print(f"  Shares Expired: {metrics.get('pledge_shares_expired_window', 0):,}")
        
        # Debug: Check yearly states for expiration tracking
        print(f"\nYearly expiration tracking:")
        for state in result.yearly_states:
            if hasattr(state, 'pledge_shares_expired_this_year'):
                print(f"  Year {state.year}: {state.pledge_shares_expired_this_year} shares expired")
        
        # Debug: Check liquidity events
        print(f"\nLiquidity events in profile:")
        if hasattr(self.profile, 'liquidity_events'):
            for event in self.profile.liquidity_events:
                print(f"  Event {event.event_id}: {event.event_date} (window closes {event.match_window_closes})")

        # Check that IPO created the obligation
        self.assertEqual(
            metrics.get('pledge_shares_obligated', 0),
            expected_obligated,
            f"Expected {expected_obligated:,} shares obligated, got {metrics.get('pledge_shares_obligated', 0):,}"
        )

        # Check that zero donations were made
        self.assertEqual(
            metrics.get('pledge_shares_donated', 0),
            0,
            "Expected 0 shares donated"
        )

        # Check that all shares expired (this will fail without the fix)
        self.assertEqual(
            metrics.get('pledge_shares_expired_window', 0),
            expected_expired,
            f"Expected {expected_expired:,} shares expired after IPO+3 years, got {metrics.get('pledge_shares_expired_window', 0):,}"
        )

        # Verify the IPO obligation was created in 2028
        ipo_year_state = None
        for state in result.yearly_states:
            if state.year == 2028:
                ipo_year_state = state
                break

        self.assertIsNotNone(ipo_year_state, "Should have 2028 year state")

        # Check for IPO-triggered obligation
        ipo_obligations = [
            o for o in ipo_year_state.pledge_state.obligations
            if 'ipo' in o.source_event_id.lower()
        ]
        # We should have one or more IPO-triggered obligations (one per grant)
        self.assertGreaterEqual(len(ipo_obligations), 1, "Should have at least one IPO-triggered obligation")

        # Total obligated shares from all IPO obligations
        total_ipo_obligated = sum(o.shares_obligated for o in ipo_obligations)
        self.assertEqual(total_ipo_obligated, expected_obligated)
        # The match window should be from the liquidity event, not the obligation itself

    def test_ipo_pledge_with_partial_pre_ipo_sales(self):
        """Test that pre-IPO sales reduce the IPO obligation amount."""
        # Create a plan with a sale before IPO
        plan = ProjectionPlan(
            name='Pre-IPO Sale',
            description='Sale before IPO reduces IPO obligation',
            start_date=date(2025, 1, 1),
            end_date=date(2032, 12, 31),
            initial_cash=self.profile.current_cash,
            initial_lots=self.initial_lots,
            tax_elections={}
        )

        # Add a sale in 2026 (before IPO)
        plan.add_action(PlannedAction(
            action_date=date(2026, 6, 1),
            action_type=ActionType.SELL,
            lot_id='LOT_001',
            quantity=10000,
            price=30.00
        ))

        # Set up price projections
        for year in range(2025, 2033):
            plan.price_projections[year] = 25.00

        # Run projection
        calculator = ProjectionCalculator(self.profile)
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()
        metrics = result.summary_metrics

        # With 10,000 shares sold at 50% pledge:
        # Sale creates obligation for 10,000 shares (maximalist interpretation)
        # At IPO, total vested shares are 120,000 (80k + 40k, both grants fully vested)
        # Total pledge commitment: 120,000 * 50% = 60,000 shares
        # Already obligated from sale: 10,000 shares
        # IPO remainder obligation: 60,000 - 10,000 = 50,000 shares
        # Total obligated: 10,000 (sale) + 50,000 (IPO) = 60,000

        # Total obligated should be 60,000 based on vested shares
        self.assertEqual(
            metrics.get('pledge_shares_obligated', 0),
            60000,
            f"Expected 60,000 total shares obligated"
        )

        # All should expire since no donations made
        self.assertEqual(
            metrics.get('pledge_shares_expired_window', 0),
            60000,
            f"Expected all 60,000 shares to expire"
        )

    def test_ipo_pledge_with_donations_after_deadline(self):
        """Test that donations after IPO+1 year don't reduce expired count."""
        plan = ProjectionPlan(
            name='Late Donations',
            description='Donations after IPO deadline',
            start_date=date(2025, 1, 1),
            end_date=date(2032, 12, 31),
            initial_cash=self.profile.current_cash,
            initial_lots=self.initial_lots,
            tax_elections={}
        )

        # Add donation in 2032 (after IPO + 3 year deadline of March 2031)
        plan.add_action(PlannedAction(
            action_date=date(2032, 6, 1),
            action_type=ActionType.DONATE,
            lot_id='LOT_001',
            quantity=20000,
            price=35.00
        ))

        # Set up price projections
        for year in range(2025, 2033):
            plan.price_projections[year] = 25.00

        # Run projection
        calculator = ProjectionCalculator(self.profile)
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()
        metrics = result.summary_metrics

        # Should still show 60,000 expired because donation was too late
        self.assertEqual(
            metrics.get('pledge_shares_expired_window', 0),
            60000,
            f"Expected 60,000 shares expired (donations after deadline don't count)"
        )


if __name__ == '__main__':
    unittest.main()
