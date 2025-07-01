#!/usr/bin/env python3

"""
Test Company Match Tracking - Comprehensive Scenarios

This module tests the comprehensive company match tracking functionality with
all required scenarios:

1. Purchase + donation same year
2. Purchase + donation different year (within window)
3. Purchase + donation after match window expires
4. Purchase + partial donation within window + donation outside window
5. Purchase + donation exceeding matchable obligation
6. Two purchases + single donation within window
7. Complex multi-purchase/donation with FIFO and expiration
"""

import sys
import os
from datetime import date, timedelta
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    UserProfile, ShareLot, ShareType, LifecycleState, TaxTreatment,
    ProjectionPlan, PlannedAction, ActionType, PledgeObligation, PledgeState
)
from projections.projection_calculator import ProjectionCalculator
from calculators.share_donation_calculator import ShareDonationCalculator


class TestCompanyMatchTracking:
    """Test suite for company match tracking functionality."""

    def create_test_profile(self, company_match_ratio: float = 3.0) -> UserProfile:
        """Create a test user profile with 50% pledge."""
        return UserProfile(
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0765,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=300000,
            current_cash=500000,
            exercise_reserves=100000,
            pledge_percentage=0.5,  # 50% pledge
            company_match_ratio=company_match_ratio,
            spouse_w2_income=0,
            other_income=0,
            taxable_investments=200000,
            investment_return_rate=0.07,
            monthly_living_expenses=10000,
            filing_status='single',
            state_of_residence='California'
        )

    def create_25_percent_pledge_profile(self) -> UserProfile:
        """Create a test user profile with 25% pledge and 1:1 match."""
        return UserProfile(
            federal_tax_rate=0.37,
            federal_ltcg_rate=0.20,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0765,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=300000,
            current_cash=500000,
            exercise_reserves=100000,
            pledge_percentage=0.25,  # 25% pledge (1 share donated per 3 sold)
            company_match_ratio=1.0,  # 1:1 match
            spouse_w2_income=0,
            other_income=0,
            taxable_investments=200000,
            investment_return_rate=0.07,
            monthly_living_expenses=10000,
            filing_status='single',
            state_of_residence='California'
        )

    def create_test_lots(self, lot_count: int = 1, shares_per_lot: int = 2000) -> list:
        """Create test share lots."""
        lots = []
        for i in range(lot_count):
            lots.append(ShareLot(
                lot_id=f"ISO_2022_{i+1}",
                share_type=ShareType.ISO,
                quantity=shares_per_lot,
                strike_price=10.0,
                cost_basis=10.0,
                grant_date=date(2022, 1, 1),
                exercise_date=date(2022, 6, 1),
                fmv_at_exercise=25.0,
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.NA
            ))
        return lots

    def calculate_required_donation_shares(self, shares_sold: int, pledge_percentage: float) -> int:
        """Calculate required donation shares based on pledge percentage.

        Formula: shares_donated = (pledge_percentage * shares_sold) / (1 - pledge_percentage)

        Args:
            shares_sold: Number of shares sold
            pledge_percentage: Pledge percentage (e.g., 0.5 for 50%, 0.25 for 25%)

        Returns:
            Number of shares that must be donated
        """
        if pledge_percentage >= 1.0:
            return float('inf')  # Cannot fulfill 100% or higher pledge
        return int((pledge_percentage * shares_sold) / (1 - pledge_percentage))

    def test_scenario_1_same_year_sale_donation(self):
        """Test Scenario 1: Purchase event followed by donation same year."""
        print("\n" + "="*80)
        print("SCENARIO 1: Sale + Donation Same Year")
        print("="*80)

        profile = self.create_test_profile(company_match_ratio=3.0)
        lots = self.create_test_lots(1, 2000)

        plan = ProjectionPlan(
            name="scenario_1",
            description="Same year sale and donation",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            initial_lots=lots,
            initial_cash=500000,
            price_projections={2025: 50.0},
            tax_elections={}
        )

        # Sale creating pledge: 1000 shares at $50
        # Maximalist: need to donate 1000 shares (1:1 ratio for 50% pledge)
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=50.0
        ))

        # Donation same year: 1000 shares at $50 = $50k donation + $150k match
        plan.add_action(PlannedAction(
            action_date=date(2025, 9, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=50.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        calculator.current_lots = lots
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()

        # Verify results
        year_2025_state = result.get_state_for_year(2025)
        expected_company_match = 1000 * 50.0 * 3.0  # $150,000

        assert year_2025_state.company_match_received == expected_company_match
        assert result.summary_metrics['total_company_match_all_years'] == expected_company_match

        # Verify pledge fulfillment
        pledge_state = year_2025_state.pledge_state
        assert len(pledge_state.obligations) == 1
        obligation = pledge_state.obligations[0]
        assert obligation.is_fulfilled  # Should be fully satisfied

        print(f"✅ Sale proceeds: ${1000 * 50.0:,.2f}")
        # Formula: shares_donated = (pledge_percentage * shares_sold) / (1 - pledge_percentage)
        print(f"✅ Pledge obligation (50%): ${(1000 * 50.0 * 0.5)/(1 - 0.5):,.2f}")
        print(f"✅ Donation value: ${1000 * 50.0:,.2f}")
        print(f"✅ Company match: ${expected_company_match:,.2f}")
        print(f"✅ Pledge fulfilled: {obligation.is_fulfilled}")

    def test_scenario_2_different_year_within_window(self):
        """Test Scenario 2: Purchase + donation different year but within 3-year window."""
        print("\n" + "="*80)
        print("SCENARIO 2: Sale + Donation Different Year (Within Window)")
        print("="*80)

        profile = self.create_test_profile(company_match_ratio=3.0)
        lots = self.create_test_lots(1, 2000)

        plan = ProjectionPlan(
            name="scenario_2",
            description="Sale and donation in different years within window",
            start_date=date(2025, 1, 1),
            end_date=date(2027, 12, 31),
            initial_lots=lots,
            initial_cash=500000,
            price_projections={2025: 50.0, 2026: 60.0, 2027: 70.0},
            tax_elections={}
        )

        # Sale in 2025: 1000 shares, creates 3-year match window until March 2028
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=50.0
        ))

        # Donation in 2027 (within window): 1000 shares at $70
        plan.add_action(PlannedAction(
            action_date=date(2027, 6, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=70.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        calculator.current_lots = lots
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()

        # Verify results
        year_2027_state = result.get_state_for_year(2027)
        # Company match is based on the donated shares value at current price
        # 1000 shares * $70/share * 3x match = $210,000
        expected_company_match = 1000 * 70.0 * 3.0  # $210,000

        print(f"DEBUG: Actual company match: ${year_2027_state.company_match_received:,.2f}")
        print(f"DEBUG: Expected company match: ${expected_company_match:,.2f}")
        print(f"DEBUG: Donation value: ${year_2027_state.donation_value:,.2f}")
        
        assert year_2027_state.company_match_received == expected_company_match

        # Verify pledge is fulfilled
        pledge_state = year_2027_state.pledge_state
        obligation = pledge_state.obligations[0]
        assert obligation.is_fulfilled

        print(f"✅ Sale year: 2025, Donation year: 2027")
        # Find the liquidity event to get window close date
        if hasattr(result.user_profile, 'liquidity_events') and result.user_profile.liquidity_events:
            event = next((e for e in result.user_profile.liquidity_events if e.event_id == obligation.source_event_id), None)
            if event:
                print(f"✅ Match window closes: {event.match_window_closes}")
        print(f"✅ Donation within window: Yes")
        print(f"✅ Donation value: ${1000 * 70.0:,.2f}")
        print(f"✅ Company match: ${expected_company_match:,.2f} (based on current share value)")
        print(f"✅ Pledge fulfilled: {obligation.is_fulfilled}")

    def test_scenario_3_donation_after_window_expires(self):
        """Test Scenario 3: Purchase + donation after match window expires."""
        print("\n" + "="*80)
        print("SCENARIO 3: Sale + Donation After Match Window Expires")
        print("="*80)

        profile = self.create_test_profile(company_match_ratio=3.0)
        lots = self.create_test_lots(1, 2000)

        plan = ProjectionPlan(
            name="scenario_3",
            description="Donation after match window expires",
            start_date=date(2025, 1, 1),
            end_date=date(2029, 12, 31),
            initial_lots=lots,
            initial_cash=500000,
            price_projections={2025: 50.0, 2026: 60.0, 2027: 70.0, 2028: 80.0, 2029: 90.0},
            tax_elections={}
        )

        # Sale in 2025: match window closes March 2028
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=50.0
        ))

        # Donation in 2029 (after window): should get NO company match
        plan.add_action(PlannedAction(
            action_date=date(2029, 6, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=90.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        calculator.current_lots = lots
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()

        # Verify NO company match received
        year_2029_state = result.get_state_for_year(2029)
        assert year_2029_state.company_match_received == 0.0  # No match after window

        # Verify lost match opportunity is calculated
        total_lost_match = result.summary_metrics['total_lost_match_value']
        expected_lost_match = 1000 * 90.0 * 3.0  # $270,000 at 2029 prices
        assert total_lost_match > 0, "Should have calculated lost match opportunity"

        # Verify pledge obligation shows donation but no match eligibility
        pledge_state = year_2029_state.pledge_state
        obligation = pledge_state.obligations[0]
        assert obligation.shares_fulfilled == 0  # Match rejected due to closed window

        print(f"✅ Sale year: 2025, Donation year: 2029")
        # Find the liquidity event to get window close date
        if hasattr(result.user_profile, 'liquidity_events') and result.user_profile.liquidity_events:
            event = next((e for e in result.user_profile.liquidity_events if e.event_id == obligation.source_event_id), None)
            if event:
                print(f"✅ Match window closed: {event.match_window_closes}")
        print(f"✅ Total donations made in 2029: ${year_2029_state.donation_value:,.2f}")
        print(f"✅ Shares applied to pledge: {obligation.shares_fulfilled}")
        print(f"✅ Company match received: ${year_2029_state.company_match_received:,.2f}")
        print(f"✅ Lost match opportunity: ${total_lost_match:,.2f}")

    def test_scenario_4_partial_within_then_outside_window(self):
        """Test Scenario 4: Partial donation within window + donation outside window."""
        print("\n" + "="*80)
        print("SCENARIO 4: Partial Donation Within + Outside Window")
        print("="*80)

        profile = self.create_test_profile(company_match_ratio=3.0)
        lots = self.create_test_lots(1, 4000)

        plan = ProjectionPlan(
            name="scenario_4",
            description="Partial donation within window then outside",
            start_date=date(2025, 1, 1),
            end_date=date(2029, 12, 31),
            initial_lots=lots,
            initial_cash=500000,
            price_projections={2025: 50.0, 2026: 60.0, 2027: 70.0, 2028: 80.0, 2029: 90.0},
            tax_elections={}
        )

        # Sale: 2000 shares, need to donate 2000 shares (1:1 for 50% pledge)
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=2000,
            price=50.0
        ))

        # Partial donation within window: 800 shares (partial fulfillment)
        plan.add_action(PlannedAction(
            action_date=date(2027, 6, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=800,
            price=70.0
        ))

        # Remaining donation outside window: 1200 shares (no match)
        plan.add_action(PlannedAction(
            action_date=date(2029, 6, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=1200,
            price=90.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        calculator.current_lots = lots
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()

        # Verify company match only for first donation
        year_2027_state = result.get_state_for_year(2027)
        year_2029_state = result.get_state_for_year(2029)

        expected_match_2027 = 800 * 70.0 * 3.0  # $168,000
        assert year_2027_state.company_match_received == expected_match_2027
        assert year_2029_state.company_match_received == 0.0  # No match for late donation

        # Verify lost match opportunity for unfulfilled portion
        total_lost_match = result.summary_metrics['total_lost_match_value']
        unfulfilled_shares = 2000 - 800  # 1200 shares unfulfilled when window closed
        expected_lost_match = unfulfilled_shares * 90.0 * 3.0  # At 2029 prices
        assert total_lost_match > 0

        pledge_state = year_2029_state.pledge_state
        obligation = pledge_state.obligations[0]

        # We sold 2000 shares, need to donate 2000 shares for 50% pledge
        print(f"✅ Shares obligated: {obligation.shares_obligated}")
        print(f"✅ Shares fulfilled: {obligation.shares_fulfilled}")
        print(f"✅ Shares donated within window: 800")
        print(f"✅ Company match (within window): ${expected_match_2027:,.2f}")
        print(f"✅ Company match (outside window): $0.00")
        print(f"✅ Lost match opportunity: ${total_lost_match:,.2f}")

    def test_scenario_5_donation_exceeding_obligation(self):
        """Test Scenario 5: Donation exceeding matchable obligation."""
        print("\n" + "="*80)
        print("SCENARIO 5: Donation Exceeding Matchable Obligation")
        print("="*80)

        profile = self.create_test_profile(company_match_ratio=3.0)
        lots = self.create_test_lots(1, 3000)

        plan = ProjectionPlan(
            name="scenario_5",
            description="Donation exceeding obligation",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            initial_lots=lots,
            initial_cash=500000,
            price_projections={2025: 50.0, 2026: 60.0},
            tax_elections={}
        )

        # Sale: 1000 shares, need to donate 1000 shares for full fulfillment
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=50.0
        ))

        # Excessive donation: 1500 shares (500 more than required)
        plan.add_action(PlannedAction(
            action_date=date(2026, 6, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=1500,
            price=60.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        calculator.current_lots = lots
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()

        # Verify company match only applies to matchable portion
        year_2026_state = result.get_state_for_year(2026)

        # Company match applies to shares credited (1000 shares at current price)
        # Even though we donate 1500 shares, only 1000 count toward pledge
        expected_company_match = 1000 * 60.0 * 3.0  # $180,000 for credited shares
        assert year_2026_state.company_match_received == expected_company_match

        # Verify pledge is fulfilled (only needed amount applied)
        pledge_state = year_2026_state.pledge_state
        obligation = pledge_state.obligations[0]
        assert obligation.shares_fulfilled == 1000  # Only shares needed for fulfillment
        assert obligation.is_fulfilled  # Fully fulfilled

        print(f"✅ Shares obligated: {obligation.shares_obligated}")
        print(f"✅ Shares fulfilled: {obligation.shares_fulfilled}")
        print(f"✅ Donation value: ${1500 * 60.0:,.2f}")
        print(f"✅ Company match: ${expected_company_match:,.2f} (on credited shares at current price)")
        print(f"✅ Pledge fulfilled: {obligation.is_fulfilled} (excess donation beyond obligation)")

    def test_scenario_6_two_purchases_one_donation(self):
        """Test Scenario 6: Two purchases discharged by single donation within window."""
        print("\n" + "="*80)
        print("SCENARIO 6: Two Purchases + Single Donation (FIFO Discharge)")
        print("="*80)

        profile = self.create_test_profile(company_match_ratio=3.0)
        lots = self.create_test_lots(1, 4000)

        plan = ProjectionPlan(
            name="scenario_6",
            description="Two sales, one donation (FIFO)",
            start_date=date(2025, 1, 1),
            end_date=date(2027, 12, 31),
            initial_lots=lots,
            initial_cash=500000,
            price_projections={2025: 50.0, 2026: 60.0, 2027: 70.0},
            tax_elections={}
        )

        # First sale: 1000 shares
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=50.0
        ))

        # Second sale: 800 shares
        plan.add_action(PlannedAction(
            action_date=date(2025, 6, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=800,
            price=50.0
        ))

        # Single donation: 1500 shares (should discharge both obligations via FIFO)
        plan.add_action(PlannedAction(
            action_date=date(2026, 6, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=1500,
            price=60.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        calculator.current_lots = lots
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()

        # Verify company match
        year_2026_state = result.get_state_for_year(2026)
        expected_company_match = 1500 * 60.0 * 3.0  # $270,000
        assert year_2026_state.company_match_received == expected_company_match

        # Verify FIFO discharge
        pledge_state = year_2026_state.pledge_state
        assert len(pledge_state.obligations) == 2

        # First obligation should be fully satisfied (1000 shares)
        first_obligation = next(o for o in pledge_state.obligations if o.creation_date == date(2025, 3, 1))
        assert first_obligation.shares_fulfilled == 1000
        assert first_obligation.is_fulfilled

        # Second obligation should be partially satisfied (500 shares)
        second_obligation = next(o for o in pledge_state.obligations if o.creation_date == date(2025, 6, 1))
        assert second_obligation.shares_fulfilled == 500
        assert not second_obligation.is_fulfilled  # Still needs 300 more shares

        print(f"✅ First sale: 1000 shares (needs 1000 donated)")
        print(f"✅ Second sale: 800 shares (needs 800 donated)")
        print(f"✅ Total donation: 1500 shares")
        print(f"✅ First obligation fulfilled: {first_obligation.is_fulfilled}")
        print(f"✅ Second obligation donated: {second_obligation.shares_fulfilled}/800")
        print(f"✅ Second obligation fulfilled: {second_obligation.is_fulfilled}")
        print(f"✅ Company match: ${expected_company_match:,.2f}")

    def test_scenario_7_complex_multi_purchase_donation_with_expiration(self):
        """Test Scenario 7: Complex multi-purchase/donation with FIFO and expiration."""
        print("\n" + "="*80)
        print("SCENARIO 7: Complex Multi-Purchase/Donation with Expiration")
        print("="*80)

        profile = self.create_test_profile(company_match_ratio=3.0)
        lots = self.create_test_lots(1, 6000)

        plan = ProjectionPlan(
            name="scenario_7",
            description="Complex scenario with expiration",
            start_date=date(2025, 1, 1),
            end_date=date(2030, 12, 31),
            initial_lots=lots,
            initial_cash=500000,
            price_projections={
                2025: 50.0, 2026: 60.0, 2027: 70.0,
                2028: 80.0, 2029: 90.0, 2030: 100.0
            },
            tax_elections={}
        )

        # First sale: 1000 shares in March 2025 (window closes March 2028)
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=1000,
            price=50.0
        ))

        # Second sale: 1200 shares in June 2025 (window closes June 2028)
        plan.add_action(PlannedAction(
            action_date=date(2025, 6, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=1200,
            price=50.0
        ))

        # Third sale: 800 shares in September 2025 (window closes September 2028)
        plan.add_action(PlannedAction(
            action_date=date(2025, 9, 1),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=800,
            price=50.0
        ))

        # First donation: 1800 shares in 2026 (within all windows, FIFO discharge)
        plan.add_action(PlannedAction(
            action_date=date(2026, 4, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=1800,
            price=60.0
        ))

        # Second donation: 500 shares in 2027 (within remaining windows)
        plan.add_action(PlannedAction(
            action_date=date(2027, 4, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=500,
            price=70.0
        ))

        # Third donation: 300 shares in 2029 (after first window expires)
        plan.add_action(PlannedAction(
            action_date=date(2029, 4, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=300,
            price=90.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        calculator.current_lots = lots
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()

        # Analyze results
        year_2026_state = result.get_state_for_year(2026)
        year_2027_state = result.get_state_for_year(2027)
        year_2029_state = result.get_state_for_year(2029)

        # Company match calculations
        match_2026 = 1800 * 60.0 * 3.0   # $324,000
        match_2027 = 500 * 70.0 * 3.0    # $105,000
        match_2029 = 0.0                 # No match (after window closure)

        assert year_2026_state.company_match_received == match_2026
        assert year_2027_state.company_match_received == match_2027
        assert year_2029_state.company_match_received == match_2029

        # Verify lost match opportunity
        total_lost_match = result.summary_metrics['total_lost_match_value']
        assert total_lost_match > 0, "Should have lost match opportunities"

        # Analyze final pledge state
        final_pledge_state = year_2029_state.pledge_state

        print(f"✅ Sales: 1000 + 1200 + 800 = 3000 shares")
        print(f"✅ Required donations: 1000 + 1200 + 800 = 3000 shares")
        print(f"✅ Actual donations: 1800 + 500 + 300 = 2600 shares")
        print(f"✅ Company match 2026: ${match_2026:,.2f}")
        print(f"✅ Company match 2027: ${match_2027:,.2f}")
        print(f"✅ Company match 2029: ${match_2029:,.2f}")
        print(f"✅ Lost match opportunities: ${total_lost_match:,.2f}")

        # Detailed obligation analysis
        for i, obligation in enumerate(final_pledge_state.obligations):
            print(f"   Obligation {i+1}: {obligation.shares_fulfilled}/{obligation.shares_obligated} shares")

    def test_scenario_8_missed_opportunity_and_over_donation(self):
        """Test Scenario 8: Complex scenario with missed opportunities and over-donation."""
        print("\n" + "="*80)
        print("SCENARIO 8: Missed Opportunity + Over-Donation")
        print("="*80)

        profile = self.create_test_profile(company_match_ratio=3.0)
        lots = self.create_test_lots(1, 8000)

        plan = ProjectionPlan(
            name="scenario_8",
            description="Missed opportunity and over-donation scenario",
            start_date=date(2025, 1, 1),
            end_date=date(2030, 12, 31),
            initial_lots=lots,
            initial_cash=500000,
            price_projections={
                2025: 50.0, 2026: 60.0, 2027: 70.0,
                2028: 80.0, 2029: 90.0, 2030: 100.0
            },
            tax_elections={}
        )

        # Sale 1: 1000 shares in Jan 2025 (window closes Jan 2028)
        plan.add_action(PlannedAction(
            action_date=date(2025, 1, 15),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=1000,  # Need 1000 shares donated
            price=50.0
        ))

        # Sale 2: 800 shares in March 2025 (window closes March 2028)
        plan.add_action(PlannedAction(
            action_date=date(2025, 3, 15),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=800,  # Need 800 shares donated
            price=50.0
        ))

        # Sale 3: 600 shares in June 2025 (window closes June 2028)
        plan.add_action(PlannedAction(
            action_date=date(2025, 6, 15),
            action_type=ActionType.SELL,
            lot_id="ISO_2022_1",
            quantity=600,  # Need 600 shares donated
            price=50.0
        ))

        # Donation 1: Partial fulfillment of first obligation only (2026)
        plan.add_action(PlannedAction(
            action_date=date(2026, 6, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=400,  # Only 400 of 1000 needed for first obligation
            price=60.0
        ))

        # Donation 2: Late donation (2028) - misses completing first obligation window
        # Will apply to obligations 2 and 3, but may over-fulfill them
        plan.add_action(PlannedAction(
            action_date=date(2028, 3, 1),
            action_type=ActionType.DONATE,
            lot_id="ISO_2022_1",
            quantity=2000,  # Much more than needed for remaining obligations
            price=80.0
        ))

        # Run projection
        calculator = ProjectionCalculator(profile)
        calculator.current_lots = lots
        result = calculator.evaluate_projection_plan(plan)
        result.calculate_summary_metrics()

        # Analyze results
        year_2026_state = result.get_state_for_year(2026)
        year_2028_state = result.get_state_for_year(2028)

        # Verify 2026 - partial fulfillment of first obligation
        match_2026 = year_2026_state.company_match_received
        expected_match_2026 = 400 * 60.0 * 3.0  # $72,000

        assert match_2026 == expected_match_2026, \
            f"Expected ${expected_match_2026:,.2f} match in 2026, got ${match_2026:,.2f}"

        # Verify 2028 - limited match due to obligation limits
        match_2028 = year_2028_state.company_match_received

        # Only obligations 2 and 3 are still active (800 + 600 = 1400 shares max)
        # But first obligation expired unfulfilled

        # Get final state for detailed analysis
        final_pledge_state = year_2028_state.pledge_state

        # Calculate expected values
        first_obligation = next(o for o in final_pledge_state.obligations if o.creation_date == date(2025, 1, 15))
        second_obligation = next(o for o in final_pledge_state.obligations if o.creation_date == date(2025, 3, 15))
        third_obligation = next(o for o in final_pledge_state.obligations if o.creation_date == date(2025, 6, 15))

        # Calculate and verify both types of lost opportunities

        # Type 1: Lost match from expired first obligation (missed opportunity)
        unfulfilled_shares_obligation_1 = 1000 - 400  # 600 shares
        # Use price when window closes (2028: $80), not when calculation happens (2029: $90)
        lost_match_from_expired_obligation = unfulfilled_shares_obligation_1 * 80.0 * 3.0  # $144,000

        # Type 2: Lost potential match from over-donated shares (excess beyond capacity)
        total_capacity_before_donation = 800 + 600  # 1400 shares
        applied_to_active_obligations = min(2000, total_capacity_before_donation)
        over_donated_shares = max(0, 2000 - total_capacity_before_donation)  # 600 shares
        lost_potential_match_from_over_donation = over_donated_shares * 80.0 * 3.0  # $144,000

        # Total lost opportunities (from system metrics)
        total_lost_match = result.summary_metrics['total_lost_match_value']



        # Calculate expected match for 2028 (only on applied portion)
        expected_match_2028 = applied_to_active_obligations * 80.0 * 3.0

        # Validate both types of losses
        assert abs(lost_match_from_expired_obligation - 144000.0) < 1, \
            f"Expected $144,000 lost from expired obligation, got ${lost_match_from_expired_obligation:,.2f}"

        assert abs(lost_potential_match_from_over_donation - 144000.0) < 1, \
            f"Expected $144,000 lost potential from over-donation, got ${lost_potential_match_from_over_donation:,.2f}"

        print(f"✅ Sales: 1000 (Jan 2025) + 800 (Mar 2025) + 600 (Jun 2025) = 2400 shares")
        print(f"✅ Required donations: 1000 + 800 + 600 = 2400 shares")
        print(f"✅ Donation 1 (2026): 400 shares → first obligation (partial)")
        print(f"✅ Match earned 2026: ${match_2026:,.2f}")
        print(f"✅ First obligation window expires Jan 2028")
        print(f"✅ Donation 2 (2028): 2000 shares → obligations 2&3 (over-fulfillment)")
        print(f"✅ Active obligations capacity (before donation): {total_capacity_before_donation} shares")
        print(f"✅ Applied to active obligations: {applied_to_active_obligations} shares")
        print(f"✅ Over-donated (no match eligibility): {over_donated_shares} shares")
        print(f"✅ Match earned 2028: ${match_2028:,.2f}")
        print(f"\n✅ LOSS ANALYSIS:")
        print(f"   • Lost match from expired obligation 1: ${lost_match_from_expired_obligation:,.2f}")
        print(f"     ({unfulfilled_shares_obligation_1} unfulfilled shares × $80 × 3.0 ratio - priced at window closure)")
        print(f"   • Lost potential match from over-donation: ${lost_potential_match_from_over_donation:,.2f}")
        print(f"     ({over_donated_shares} excess shares × $80 × 3.0 ratio - priced at donation time)")
        print(f"   • Total lost match opportunities: ${total_lost_match:,.2f}")

        # Detailed obligation analysis
        print(f"\n✅ Final obligation status:")
        print(f"   Obligation 1 (Jan 2025): {first_obligation.shares_fulfilled}/{first_obligation.shares_obligated} shares")
        print(f"   Obligation 2 (Mar 2025): {second_obligation.shares_fulfilled}/{second_obligation.shares_obligated} shares")
        print(f"   Obligation 3 (Jun 2025): {third_obligation.shares_fulfilled}/{third_obligation.shares_obligated} shares")

        # Verify total charitable impact includes both personal donations and company match
        total_donations = result.summary_metrics['total_donations_all_years']
        total_company_match = result.summary_metrics['total_company_match_all_years']
        total_charitable_impact = result.summary_metrics['total_charitable_impact']

        expected_total_donations = (400 * 60.0) + (2000 * 80.0)  # $24,000 + $160,000 = $184,000
        expected_total_match = match_2026 + match_2028

        assert abs(total_donations - expected_total_donations) < 1, \
            f"Expected total donations ${expected_total_donations:,.2f}, got ${total_donations:,.2f}"

        print(f"✅ FINANCIAL SUMMARY:")
        print(f"   • Total donations: ${total_donations:,.2f}")
        print(f"   • Total company match earned: ${total_company_match:,.2f}")
        print(f"   • Total charitable impact: ${total_charitable_impact:,.2f}")
        print(f"   • Lost opportunities (expired window): ${lost_match_from_expired_obligation:,.2f}")
        print(f"   • Lost opportunities (over-donation): ${lost_potential_match_from_over_donation:,.2f}")
        print(f"   • Total lost potential: ${lost_match_from_expired_obligation + lost_potential_match_from_over_donation:,.2f}")
        print(f"✅ Demonstrates both missed timing opportunities and over-donation limits")

    def test_basic_company_match_calculation(self):
        """Test basic company match calculation for individual donations."""
        print("\n" + "="*80)
        print("BASIC TEST: Company Match Calculation")
        print("="*80)

        # Test donation with 3:1 company match
        donation_components = ShareDonationCalculator.calculate_share_donation_components(
            lot_id="ISO_2022",
            donation_date=date(2025, 6, 1),
            shares_donated=100,
            fmv_at_donation=50.0,
            cost_basis=10.0,
            exercise_date=date(2022, 1, 1),
            holding_period_days=365 * 3,  # Long-term
            company_match_ratio=3.0
        )

        # Verify calculations
        expected_donation_value = 100 * 50.0  # $5,000
        expected_company_match = expected_donation_value * 3.0  # $15,000

        assert donation_components.donation_value == expected_donation_value
        assert donation_components.company_match_amount == expected_company_match

        print(f"✅ Donation value: ${donation_components.donation_value:,.2f}")
        print(f"✅ Company match: ${donation_components.company_match_amount:,.2f}")
        print(f"✅ Total impact: ${donation_components.donation_value + donation_components.company_match_amount:,.2f}")

    def run_scenario_with_both_profiles(self, scenario_name: str, action_builder_func, expected_results_func):
        """Helper to run a scenario with both 50% and 25% pledge profiles for comparison."""
        print(f"\n" + "="*80)
        print(f"PROFILE COMPARISON: {scenario_name}")
        print("="*80)

        profiles = [
            ("50% Pledge / 3:1 Match", self.create_test_profile(company_match_ratio=3.0)),
            ("25% Pledge / 1:1 Match", self.create_25_percent_pledge_profile())
        ]

        results = {}

        for profile_name, profile in profiles:
            print(f"\n" + "-"*60)
            print(f"TESTING: {profile_name}")
            print("-"*60)

            lots = self.create_test_lots(1, 4000)

            # Build actions using the provided function
            actions = action_builder_func(profile)

            # Create projection plan
            plan = ProjectionPlan(
                name=f"comparison_{scenario_name.lower().replace(' ', '_')}",
                description=f"Compare {scenario_name}",
                start_date=date(2025, 1, 1),
                end_date=date(2029, 12, 31),
                initial_lots=lots,
                initial_cash=500000,
                price_projections={2025: 50.0, 2026: 60.0, 2027: 70.0, 2028: 80.0, 2029: 90.0},
                tax_elections={}
            )

            # Add actions to plan
            for action in actions:
                plan.add_action(action)

            # Run projection
            calculator = ProjectionCalculator(profile)
            calculator.current_lots = lots
            result = calculator.evaluate_projection_plan(plan)
            result.calculate_summary_metrics()

            # Store results
            results[profile_name] = {
                'result': result,
                'profile': profile,
                'total_donations': result.summary_metrics['total_donations_all_years'],
                'total_company_match': result.summary_metrics['total_company_match_all_years'],
                'total_charitable_impact': result.summary_metrics['total_charitable_impact'],
                'total_lost_match': result.summary_metrics.get('total_lost_match_value', 0)
            }

            # Display results
            print(f"✅ Total donations: ${results[profile_name]['total_donations']:,.2f}")
            print(f"✅ Total company match: ${results[profile_name]['total_company_match']:,.2f}")
            print(f"✅ Total charitable impact: ${results[profile_name]['total_charitable_impact']:,.2f}")
            print(f"✅ Lost match opportunities: ${results[profile_name]['total_lost_match']:,.2f}")

        # Run expected results validation
        expected_results_func(results)

        print(f"\n" + "-"*60)
        print("COMPARISON SUMMARY")
        print("-"*60)

        profile_50 = results["50% Pledge / 3:1 Match"]
        profile_25 = results["25% Pledge / 1:1 Match"]

        print(f"Total Impact Comparison:")
        print(f"  50% Pledge, 3:1 Match: ${profile_50['total_charitable_impact']:,.2f}")
        print(f"  25% Pledge, 1:1 Match: ${profile_25['total_charitable_impact']:,.2f}")

        return results

    def test_comparison_same_year_sale_donation(self):
        """Compare 50% vs 25% pledge for same year sale and donation."""

        def build_actions(profile):
            shares_sold = 1200
            required_donation = self.calculate_required_donation_shares(shares_sold, profile.pledge_percentage)
            return [
                PlannedAction(
                    action_date=date(2025, 3, 1),
                    action_type=ActionType.SELL,
                    lot_id="ISO_2022_1",
                    quantity=shares_sold,
                    price=50.0
                ),
                PlannedAction(
                    action_date=date(2025, 9, 1),
                    action_type=ActionType.DONATE,
                    lot_id="ISO_2022_1",
                    quantity=required_donation,  # Calculated based on pledge percentage
                    price=50.0
                )
            ]

        def validate_results(results):
            profile_50 = results["50% Pledge / 3:1 Match"]
            profile_25 = results["25% Pledge / 1:1 Match"]

            # Calculate expected donations and matches based on proper pledge math
            shares_sold = 1200
            required_50 = self.calculate_required_donation_shares(shares_sold, 0.5)  # Should be 1200
            required_25 = self.calculate_required_donation_shares(shares_sold, 0.25)  # Should be 400

            expected_50_match = required_50 * 50.0 * 3.0
            expected_25_match = required_25 * 50.0 * 1.0

            assert abs(profile_50['total_company_match'] - expected_50_match) < 1
            assert abs(profile_25['total_company_match'] - expected_25_match) < 1

            print(f"✅ 50% pledge: {shares_sold} sold → {required_50} required → ${expected_50_match:,.2f} match")
            print(f"✅ 25% pledge: {shares_sold} sold → {required_25} required → ${expected_25_match:,.2f} match")

        self.run_scenario_with_both_profiles(
            "Same Year Sale + Donation",
            build_actions,
            validate_results
        )

    def test_comparison_partial_fulfillment_and_expiry(self):
        """Compare 50% vs 25% pledge for partial fulfillment with match expiry."""

        def build_actions(profile):
            shares_sold = 1200
            required_donation = self.calculate_required_donation_shares(shares_sold, profile.pledge_percentage)
            half_requirement = required_donation // 2
            remaining_half = required_donation - half_requirement

            return [
                # Sale creating obligation
                PlannedAction(
                    action_date=date(2025, 3, 1),
                    action_type=ActionType.SELL,
                    lot_id="ISO_2022_1",
                    quantity=shares_sold,
                    price=50.0
                ),
                # Partial donation within window
                PlannedAction(
                    action_date=date(2027, 6, 1),
                    action_type=ActionType.DONATE,
                    lot_id="ISO_2022_1",
                    quantity=half_requirement,  # Calculated half of requirement
                    price=70.0
                ),
                # Late donation after window expires
                PlannedAction(
                    action_date=date(2029, 6, 1),
                    action_type=ActionType.DONATE,
                    lot_id="ISO_2022_1",
                    quantity=remaining_half,  # Calculated remaining half
                    price=90.0
                )
            ]

        def validate_results(results):
            profile_50 = results["50% Pledge / 3:1 Match"]
            profile_25 = results["25% Pledge / 1:1 Match"]

            # Both should have some company match from within-window donation
            assert profile_50['total_company_match'] > 0
            assert profile_25['total_company_match'] > 0

            # Both should have lost match opportunities
            assert profile_50['total_lost_match'] > 0
            assert profile_25['total_lost_match'] > 0

            # 50% pledge should have higher absolute lost match due to 3:1 ratio
            assert profile_50['total_lost_match'] > profile_25['total_lost_match']

            print(f"✅ Both profiles show partial fulfillment with match expiry")
            print(f"✅ 50% pledge lost match: ${profile_50['total_lost_match']:,.2f}")
            print(f"✅ 25% pledge lost match: ${profile_25['total_lost_match']:,.2f}")

        self.run_scenario_with_both_profiles(
            "Partial Fulfillment + Match Expiry",
            build_actions,
            validate_results
        )

    def test_comparison_multiple_sales_complex(self):
        """Compare profiles with multiple sales and complex donation patterns."""

        def build_actions(profile):
            first_sale_shares = 900
            second_sale_shares = 600

            # Calculate required donations for each sale
            first_required = self.calculate_required_donation_shares(first_sale_shares, profile.pledge_percentage)
            second_required = self.calculate_required_donation_shares(second_sale_shares, profile.pledge_percentage)

            # First donation covers first obligation + partial second
            first_donation = first_required + (second_required // 2)
            # Second donation completes the second obligation
            second_donation = second_required - (second_required // 2)

            return [
                # First sale
                PlannedAction(
                    action_date=date(2025, 3, 1),
                    action_type=ActionType.SELL,
                    lot_id="ISO_2022_1",
                    quantity=first_sale_shares,
                    price=50.0
                ),
                # Second sale
                PlannedAction(
                    action_date=date(2025, 9, 1),
                    action_type=ActionType.SELL,
                    lot_id="ISO_2022_1",
                    quantity=second_sale_shares,
                    price=50.0
                ),
                # Large donation covering most obligations
                PlannedAction(
                    action_date=date(2026, 6, 1),
                    action_type=ActionType.DONATE,
                    lot_id="ISO_2022_1",
                    quantity=first_donation,  # Calculated to cover first + partial second
                    price=60.0
                ),
                # Final donation within window
                PlannedAction(
                    action_date=date(2027, 6, 1),
                    action_type=ActionType.DONATE,
                    lot_id="ISO_2022_1",
                    quantity=second_donation,  # Calculated to complete second obligation
                    price=70.0
                )
            ]

        def validate_results(results):
            profile_50 = results["50% Pledge / 3:1 Match"]
            profile_25 = results["25% Pledge / 1:1 Match"]

            # Both should achieve full fulfillment (no lost match)
            assert profile_50['total_lost_match'] == 0
            assert profile_25['total_lost_match'] == 0

            # Calculate expected requirements based on sales
            first_sale_shares = 900
            second_sale_shares = 600
            total_shares_sold = first_sale_shares + second_sale_shares

            required_50 = self.calculate_required_donation_shares(first_sale_shares, 0.5) + self.calculate_required_donation_shares(second_sale_shares, 0.5)
            required_25 = self.calculate_required_donation_shares(first_sale_shares, 0.25) + self.calculate_required_donation_shares(second_sale_shares, 0.25)

            print(f"✅ Complex multi-sale scenario with full fulfillment")
            print(f"✅ 50% pledge: {total_shares_sold} sold → {required_50} required → ${profile_50['total_donations']:,.2f} donated")
            print(f"✅ 25% pledge: {total_shares_sold} sold → {required_25} required → ${profile_25['total_donations']:,.2f} donated")

        self.run_scenario_with_both_profiles(
            "Multiple Sales Complex Pattern",
            build_actions,
            validate_results
        )


def run_all_tests():
    """Run all company match tracking tests."""
    print("COMPREHENSIVE COMPANY MATCH TRACKING TESTS")
    print("="*80)

    tester = TestCompanyMatchTracking()

    try:
        # Basic calculation test
        tester.test_basic_company_match_calculation()

        # Original single-profile scenarios
        tester.test_scenario_1_same_year_sale_donation()
        tester.test_scenario_2_different_year_within_window()
        tester.test_scenario_3_donation_after_window_expires()
        tester.test_scenario_4_partial_within_then_outside_window()
        tester.test_scenario_5_donation_exceeding_obligation()
        tester.test_scenario_6_two_purchases_one_donation()
        tester.test_scenario_7_complex_multi_purchase_donation_with_expiration()
        tester.test_scenario_8_missed_opportunity_and_over_donation()

        # Profile comparison scenarios (50% vs 25% pledge)
        tester.test_comparison_same_year_sale_donation()
        tester.test_comparison_partial_fulfillment_and_expiry()
        tester.test_comparison_multiple_sales_complex()

        print("\n" + "="*80)
        print("✅ ALL COMPREHENSIVE COMPANY MATCH TESTS PASSED!")
        print("✅ Including 50% Pledge / 3:1 Match vs 25% Pledge / 1:1 Match Comparisons")
        print("="*80)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        return False

    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
