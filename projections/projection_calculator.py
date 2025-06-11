"""
Projection calculator for multi-year equity scenario evaluation.

This calculator orchestrates existing calculators (ISO exercise, share sale,
share donation) to evaluate complete projection plans across multiple years.
"""

import sys
import os
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal
from copy import deepcopy

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ProjectionPlan, ProjectionResult, YearlyState, ShareLot, PlannedAction,
    UserProfile, TaxState, CharitableDeductionState, PledgeState, PledgeObligation,
    ShareType, LifecycleState, TaxTreatment, ActionType
)

from calculators.iso_exercise_calculator import estimate_iso_exercise_tax
from calculators.share_sale_calculator import ShareSaleCalculator
from calculators.share_donation_calculator import ShareDonationCalculator


class ProjectionCalculator:
    """
    Evaluates complete projection plans using existing calculators.

    This calculator takes a ProjectionPlan and evaluates it year by year,
    applying planned actions and calculating financial outcomes.
    """

    def __init__(self, user_profile: UserProfile):
        """Initialize with user profile data."""
        self.profile = user_profile
        self.sale_calculator = ShareSaleCalculator()
        self.donation_calculator = ShareDonationCalculator()

    def evaluate_projection_plan(self, plan: ProjectionPlan) -> ProjectionResult:
        """
        Evaluate a complete projection plan over multiple years.

        Args:
            plan: ProjectionPlan with initial state and planned actions

        Returns:
            ProjectionResult with yearly states and summary metrics
        """
        yearly_states = []
        current_lots = deepcopy(plan.initial_lots)
        current_cash = plan.initial_cash

        # Initialize carryforward states
        amt_credits_remaining = 0.0
        charitable_carryforward = {}  # year -> amount
        pledge_state = PledgeState()
        cumulative_shares_sold = {}  # Track cumulative sales across years
        cumulative_shares_donated = {}  # Track cumulative donations across years

        # Process each year in the projection
        for year in range(plan.start_date.year, plan.end_date.year + 1):
            year_start_cash = current_cash
            year_income = self.profile.annual_w2_income + self.profile.spouse_w2_income + self.profile.other_income
            year_exercise_costs = 0.0
            year_tax_paid = 0.0
            year_donation_value = 0.0

            # Get actions for this year
            year_actions = plan.get_actions_for_year(year)

            # Initialize year tax state
            year_tax_state = TaxState(amt_credits_remaining=amt_credits_remaining)

            # Create yearly state early to track disposals
            yearly_state = YearlyState(
                year=year,
                starting_cash=year_start_cash,
                income=year_income,
                exercise_costs=0.0,
                tax_paid=0.0,
                donation_value=0.0,
                ending_cash=0.0,
                tax_state=year_tax_state,
                charitable_state=CharitableDeductionState(),
                equity_holdings=[],
                total_equity_value=0.0,
                shares_sold=deepcopy(cumulative_shares_sold),
                shares_donated=deepcopy(cumulative_shares_donated),
                pledge_state=pledge_state,
                total_net_worth=0.0
            )

            # Process each action chronologically
            for action in sorted(year_actions, key=lambda a: a.action_date):
                if action.action_type == ActionType.VEST:
                    current_lots = self._process_vesting(action, current_lots, plan)

                elif action.action_type == ActionType.EXERCISE:
                    exercise_result = self._process_exercise(action, current_lots, year_tax_state)
                    year_exercise_costs += exercise_result['exercise_cost']
                    year_tax_paid += exercise_result['tax_impact']
                    current_cash -= exercise_result['total_cash_needed']

                elif action.action_type == ActionType.SELL:
                    sale_result = self._process_sale(action, current_lots, year, yearly_state)
                    current_cash += sale_result['net_proceeds']
                    year_tax_paid += sale_result['total_tax']

                    # Create pledge obligation from this sale
                    obligation = PledgeObligation(
                        parent_transaction_id=f"{action.lot_id}_{action.action_date}",
                        commencement_date=action.action_date,
                        deadline_date=date(action.action_date.year + 3, action.action_date.month, action.action_date.day),
                        total_pledge_obligation=sale_result['gross_proceeds'] * self.profile.pledge_percentage,
                        shares_sold=action.quantity,
                        pledge_percentage=self.profile.pledge_percentage,
                        outstanding_obligation=sale_result['gross_proceeds'] * self.profile.pledge_percentage
                    )
                    pledge_state.add_obligation(obligation)

                elif action.action_type == ActionType.DONATE:
                    donation_result = self._process_donation(action, current_lots, year, yearly_state)
                    year_donation_value += donation_result['donation_value']
                    # Apply donation to pledge obligations using FIFO discharge
                    pledge_state.discharge_donation(
                        donation_amount=donation_result['donation_value'],
                        shares_donated=action.quantity
                    )
                    # Tax savings reduce tax paid
                    year_tax_paid -= donation_result['tax_savings']

            # Calculate end of year cash
            year_end_cash = year_start_cash + year_income - year_exercise_costs - year_tax_paid
            current_cash = year_end_cash

            # Update AMT credits for next year
            amt_credits_remaining = year_tax_state.amt_credits_remaining

            # Calculate charitable deduction state
            charitable_state = self._calculate_charitable_state(year_donation_value, charitable_carryforward, year)

            # Pledge state is already maintained and updated throughout the year
            # No additional calculation needed

            # Calculate total equity value
            if year not in plan.price_projections:
                raise ValueError(f"Price projection for year {year} not found in plan")
            current_price = plan.price_projections[year]
            total_equity_value = sum(lot.quantity * current_price for lot in current_lots
                                   if lot.lifecycle_state in [LifecycleState.VESTED_NOT_EXERCISED,
                                                             LifecycleState.EXERCISED_NOT_DISPOSED])

            # Update yearly state with final values
            yearly_state.exercise_costs = year_exercise_costs
            yearly_state.tax_paid = year_tax_paid
            yearly_state.donation_value = year_donation_value
            yearly_state.ending_cash = year_end_cash
            yearly_state.charitable_state = charitable_state
            yearly_state.equity_holdings = deepcopy(current_lots)
            yearly_state.total_equity_value = total_equity_value
            yearly_state.pledge_state = pledge_state
            yearly_state.total_net_worth = year_end_cash + total_equity_value

            # Update cumulative tracking for next year
            cumulative_shares_sold = deepcopy(yearly_state.shares_sold)
            cumulative_shares_donated = deepcopy(yearly_state.shares_donated)

            yearly_states.append(yearly_state)

        # Create projection result
        result = ProjectionResult(
            plan=plan,
            yearly_states=yearly_states
        )

        # Calculate summary metrics
        result.calculate_summary_metrics()

        return result

    def _process_vesting(self, action: PlannedAction, current_lots: List[ShareLot],
                        plan: ProjectionPlan) -> List[ShareLot]:
        """Process a vesting action by adding new lot."""
        # Create new vested lot
        # Strike price must be explicitly provided for vesting events
        if not action.price:
            raise ValueError(f"Strike price must be specified for vesting action on {action.lot_id}")

        new_lot = ShareLot(
            lot_id=action.lot_id,
            share_type=ShareType.ISO if 'ISO' in action.lot_id else ShareType.NSO,
            quantity=action.quantity,
            strike_price=action.price,
            grant_date=action.action_date,
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA
        )

        current_lots.append(new_lot)
        return current_lots

    def _process_exercise(self, action: PlannedAction, current_lots: List[ShareLot],
                         tax_state: TaxState) -> Dict[str, float]:
        """Process an exercise action using ISO exercise calculator."""
        # Find the lot being exercised
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for exercise")

        # Calculate exercise cost
        exercise_cost = action.quantity * lot.strike_price

        # Calculate tax impact
        if lot.share_type == ShareType.ISO:
            # Use ISO exercise calculator
            if not action.price:
                raise ValueError(f"Price must be specified for exercise action on {action.lot_id}")
            current_price = action.price
            tax_result = estimate_iso_exercise_tax(
                wages=self.profile.annual_w2_income,
                other_income=self.profile.spouse_w2_income + self.profile.other_income,
                shares_to_exercise=action.quantity,
                strike_price=lot.strike_price,
                current_fmv=current_price,
                filing_status=self.profile.filing_status,
                include_california=True
            )

            tax_impact = tax_result.total_tax
            tax_state.amt_tax += tax_result.federal_amt + tax_result.ca_amt
            tax_state.amt_credits_generated += tax_result.federal_amt_credit

        else:  # NSO
            # NSO exercise creates ordinary income on bargain element
            if not action.price:
                raise ValueError(f"Price must be specified for exercise action on {action.lot_id}")
            current_price = action.price
            bargain_element = (current_price - lot.strike_price) * action.quantity
            tax_impact = bargain_element * self.profile.ordinary_income_rate

        # Create new exercised lot with proper naming
        new_lot_id = f"{action.lot_id}_EX_{action.action_date.strftime('%Y%m%d')}"
        exercised_lot = ShareLot(
            lot_id=new_lot_id,
            share_type=lot.share_type,
            quantity=action.quantity,
            strike_price=lot.strike_price,
            grant_date=lot.grant_date,
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.STCG,  # Initially STCG, will become LTCG after 1 year
            exercise_date=action.action_date,
            cost_basis=lot.strike_price,
            taxes_paid=tax_impact
        )

        # Add the new exercised lot to current lots
        current_lots.append(exercised_lot)

        # Update original lot - reduce quantity or remove if fully exercised
        if action.quantity >= lot.quantity:
            # Remove the vested lot entirely
            current_lots.remove(lot)
        else:
            # Reduce the quantity of vested shares
            lot.quantity -= action.quantity

        # Update tax state
        tax_state.regular_tax += tax_impact
        tax_state.total_tax += tax_impact

        # TODO: Tax impact from exercise might be due in the following year, not immediately
        # Consider implementing proper tax timing based on withholding vs estimated tax payments
        return {
            'exercise_cost': exercise_cost,
            'tax_impact': tax_impact,
            'total_cash_needed': exercise_cost + tax_impact
        }

    def _process_sale(self, action: PlannedAction, current_lots: List[ShareLot],
                     year: int, yearly_state: YearlyState) -> Dict[str, float]:
        """Process a sale action using share sale calculator."""
        # Find the lot being sold
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for sale")

        # Prepare lot data for calculator
        # Determine LTCG eligibility based on holding period
        current_status = 'STCG'
        if lot.exercise_date:
            months_held = (action.action_date.year - lot.exercise_date.year) * 12 + \
                         (action.action_date.month - lot.exercise_date.month)
            if months_held >= 12:
                current_status = 'LTCG_eligible'

        lots_data = [{
            'lot_id': lot.lot_id,
            'shares': lot.quantity,
            'strike_price': lot.strike_price,
            'current_status': current_status
        }]

        lot_selections = {lot.lot_id: action.quantity}
        if not action.price:
            raise ValueError(f"Price must be specified for sale action on {action.lot_id}")
        sale_price = action.price

        tax_rates = {
            'ltcg_rate': self.profile.ltcg_rate,
            'ordinary_income_rate': self.profile.stcg_rate
        }

        # Calculate sale tax
        sale_result = self.sale_calculator.calculate_tender_tax(
            lots=lots_data,
            lot_selections=lot_selections,
            tender_price=sale_price,
            tax_rates=tax_rates
        )

        # Track cumulative sales
        if lot.lot_id not in yearly_state.shares_sold:
            yearly_state.shares_sold[lot.lot_id] = 0
        yearly_state.shares_sold[lot.lot_id] += action.quantity

        # Update lot state
        if action.quantity >= lot.quantity:
            lot.lifecycle_state = LifecycleState.DISPOSED
        else:
            lot.quantity -= action.quantity

        return sale_result

    def _process_donation(self, action: PlannedAction, current_lots: List[ShareLot],
                         year: int, yearly_state: YearlyState) -> Dict[str, float]:
        """Process a donation action using share donation calculator."""
        # Find the lot being donated
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for donation")

        # Calculate donation impact
        if not action.price:
            raise ValueError(f"Price must be specified for donation action on {action.lot_id}")
        donation_price = action.price
        agi = self.profile.get_total_agi()

        # Determine holding period
        if lot.exercise_date:
            months_held = (action.action_date.year - lot.exercise_date.year) * 12 + \
                         (action.action_date.month - lot.exercise_date.month)
        else:
            months_held = 1  # Conservative assumption

        # Calculate eligible vested shares and shares already donated for match calculation
        eligible_vested_shares = sum(lot.quantity for lot in current_lots
                                   if lot.lifecycle_state in [LifecycleState.VESTED_NOT_EXERCISED,
                                                             LifecycleState.EXERCISED_NOT_DISPOSED])
        # Track shares already donated across all years
        shares_already_donated = sum(yearly_state.shares_donated.values())

        donation_result = self.donation_calculator.calculate_donation(
            agi=agi,
            tax_rate=self.profile.stcg_rate,
            company_match_ratio=self.profile.company_match_ratio,
            pledge_percentage=self.profile.pledge_percentage,
            eligible_vested_shares=eligible_vested_shares,
            shares_already_donated=shares_already_donated,
            shares=action.quantity,
            share_price=donation_price,
            cost_basis=lot.cost_basis,
            holding_period_months=months_held,
            asset_type=lot.share_type.value
        )

        # Track cumulative donations
        if lot.lot_id not in yearly_state.shares_donated:
            yearly_state.shares_donated[lot.lot_id] = 0
        yearly_state.shares_donated[lot.lot_id] += action.quantity

        # Update lot state
        if action.quantity >= lot.quantity:
            lot.lifecycle_state = LifecycleState.DISPOSED
            lot.tax_treatment = TaxTreatment.DONATED
        else:
            lot.quantity -= action.quantity

        return {
            'donation_value': donation_result.donation_value,
            'total_impact': donation_result.total_impact,
            'tax_savings': donation_result.tax_savings
        }

    def _calculate_charitable_state(self, year_donation: float,
                                  carryforward: Dict[int, float],
                                  year: int) -> CharitableDeductionState:
        """Calculate charitable deduction state with carryforward."""
        # Simple implementation - can be enhanced. Must consider expiration.
        return CharitableDeductionState(
            current_year_deduction=year_donation,
            carryforward_remaining=carryforward.copy(),
            total_available=year_donation + sum(carryforward.values())
        )

    def _calculate_pledge_state(self, pledge_state: PledgeState, year: int) -> PledgeState:
        """Return the current pledge state (no calculation needed as it's maintained throughout)."""
        # The pledge state is maintained throughout the year via add_obligation and discharge_donation
        # This method exists for compatibility but doesn't need to do additional calculations
        return pledge_state
