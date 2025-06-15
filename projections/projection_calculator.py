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

from calculators.iso_exercise_calculator import (
    estimate_iso_exercise_tax,
    calculate_exercise_components,
    calculate_nso_exercise_components
)
from calculators.share_sale_calculator import ShareSaleCalculator
from calculators.share_donation_calculator import ShareDonationCalculator
from calculators.annual_tax_calculator import AnnualTaxCalculator
from calculators.components import (
    ISOExerciseComponents,
    NSOExerciseComponents,
    ShareSaleComponents,
    DonationComponents,
    AnnualTaxComponents
)
from projections.vesting_events import process_natural_vesting, VestingEvent
from projections.pledge_calculator import PledgeCalculator


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
        self.annual_tax_calculator = AnnualTaxCalculator()

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
            year_w2_income = self.profile.annual_w2_income
            year_total_income = self.profile.annual_w2_income + self.profile.spouse_w2_income + self.profile.other_income
            year_exercise_costs = 0.0
            year_tax_paid = 0.0
            year_donation_value = 0.0

            # Initialize annual tax components for this year
            annual_components = AnnualTaxComponents(year=year)
            annual_components.w2_income = self.profile.annual_w2_income
            annual_components.spouse_income = self.profile.spouse_w2_income
            annual_components.other_ordinary_income = self.profile.other_income

            # Get actions for this year
            year_actions = plan.get_actions_for_year(year)

            # Initialize year tax state
            year_tax_state = TaxState(amt_credits_remaining=amt_credits_remaining)

            # Create yearly state early to track disposals
            yearly_state = YearlyState(
                year=year,
                starting_cash=year_start_cash,
                income=year_w2_income,  # Store just W2 income
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
                total_net_worth=0.0,
                annual_tax_components=annual_components,
                spouse_income=self.profile.spouse_w2_income,
                other_income=self.profile.other_income
            )

            vesting_events = process_natural_vesting(current_lots, year)

            # Track vesting events for CSV output
            yearly_state.vesting_events = vesting_events
            yearly_state.expiration_events = []  # Claude TODO: Add expiration handling based on specified expiration date on the parent grant object.

            # Process each action chronologically
            for action in sorted(year_actions, key=lambda a: a.action_date):
                if action.action_type == ActionType.EXERCISE:
                    exercise_result = self._process_exercise(action, current_lots, annual_components)
                    year_exercise_costs += exercise_result['exercise_cost']
                    current_cash -= exercise_result['exercise_cost']

                elif action.action_type == ActionType.SELL:
                    sale_result = self._process_sale(action, current_lots, annual_components, yearly_state)
                    current_cash += sale_result['gross_proceeds']  # Tax will be calculated at year-end

                    # Create pledge obligation using centralized calculator
                    obligation = PledgeCalculator.calculate_obligation(
                        shares_sold=action.quantity,
                        sale_price=action.price if action.price else 0,
                        pledge_percentage=self.profile.pledge_percentage,
                        sale_date=action.action_date,
                        lot_id=action.lot_id
                    )
                    pledge_state.add_obligation(obligation)

                elif action.action_type == ActionType.DONATE:
                    donation_result = self._process_donation(action, current_lots, annual_components, yearly_state)
                    year_donation_value += donation_result['donation_value']
                    # Apply donation to pledge obligations using FIFO discharge
                    pledge_state.discharge_donation(
                        donation_amount=donation_result['donation_value'],
                        shares_donated=action.quantity
                    )

            # Calculate annual tax using aggregated components
            annual_components.aggregate_components()
            tax_result = self.annual_tax_calculator.calculate_annual_tax(
                year=year,
                user_profile=self.profile,
                w2_income=self.profile.annual_w2_income,
                spouse_income=self.profile.spouse_w2_income,
                other_ordinary_income=self.profile.other_income,
                exercise_components=annual_components.iso_exercise_components,
                nso_exercise_components=annual_components.nso_exercise_components,
                sale_components=annual_components.sale_components,
                donation_components=annual_components.donation_components,
                existing_amt_credit=amt_credits_remaining
            )

            year_tax_paid = tax_result.total_tax
            year_tax_state.amt_tax = tax_result.federal_amt + tax_result.ca_amt
            year_tax_state.regular_tax = tax_result.federal_regular_tax + tax_result.ca_tax_owed
            year_tax_state.total_tax = tax_result.total_tax
            year_tax_state.amt_credits_generated = tax_result.federal_amt_credit_generated
            year_tax_state.amt_credits_used = tax_result.federal_amt_credit_used

            # Update AMT credits for next year
            amt_credits_remaining = tax_result.federal_amt_credit_carryforward

            # Calculate end of year cash
            year_end_cash = year_start_cash + year_total_income - year_exercise_costs - year_tax_paid
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
            yearly_state.annual_tax_components = annual_components
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
            user_profile=self.profile,
            yearly_states=yearly_states
        )

        # Calculate summary metrics
        result.calculate_summary_metrics()

        return result



    def _process_exercise(self, action: PlannedAction, current_lots: List[ShareLot],
                         annual_components: AnnualTaxComponents) -> Dict[str, float]:
        """Process an exercise action and extract tax components."""
        # Find the lot being exercised
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for exercise")

        # Calculate exercise cost
        exercise_cost = action.quantity * lot.strike_price

        # Get current FMV
        if not action.price:
            raise ValueError(f"Price must be specified for exercise action on {action.lot_id}")
        current_price = action.price

        # Extract exercise components based on share type
        if lot.share_type == ShareType.ISO:
            # Create ISO exercise components
            iso_components = calculate_exercise_components(
                lot_id=action.lot_id,
                exercise_date=action.action_date,
                shares_to_exercise=action.quantity,
                strike_price=lot.strike_price,
                current_fmv=current_price,
                grant_date=lot.grant_date
            )
            annual_components.iso_exercise_components.append(iso_components)

        else:  # NSO
            # Create NSO exercise components
            nso_components = calculate_nso_exercise_components(
                lot_id=action.lot_id,
                exercise_date=action.action_date,
                shares_to_exercise=action.quantity,
                strike_price=lot.strike_price,
                current_fmv=current_price,
                grant_date=lot.grant_date
            )
            annual_components.nso_exercise_components.append(nso_components)

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
            fmv_at_exercise=current_price,  # Critical for disqualifying disposition calculations
            taxes_paid=0.0  # Tax will be calculated at year-end
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

        return {
            'exercise_cost': exercise_cost
        }

    def _process_sale(self, action: PlannedAction, current_lots: List[ShareLot],
                     annual_components: AnnualTaxComponents, yearly_state: YearlyState) -> Dict[str, float]:
        """Process a sale action and extract tax components."""
        # Find the lot being sold
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for sale")

        # Get sale price
        if not action.price:
            raise ValueError(f"Price must be specified for sale action on {action.lot_id}")
        sale_price = action.price

        # Determine acquisition date and type based on lifecycle state
        if lot.exercise_date:
            acquisition_date = lot.exercise_date
            acquisition_type = 'exercise'
        else:
            # For vested but not exercised shares, use grant date
            acquisition_date = lot.grant_date
            acquisition_type = 'vest'

        # Calculate sale components
        sale_components = self.sale_calculator.calculate_sale_components(
            lot_id=lot.lot_id,
            sale_date=action.action_date,
            shares_to_sell=action.quantity,
            sale_price=sale_price,
            cost_basis=lot.cost_basis,
            acquisition_date=acquisition_date,
            acquisition_type=acquisition_type,
            is_iso=(lot.share_type == ShareType.ISO),
            grant_date=lot.grant_date,
            exercise_date=lot.exercise_date,
            fmv_at_exercise=getattr(lot, 'fmv_at_exercise', None)
        )

        # Add components to annual aggregation
        annual_components.sale_components.append(sale_components)

        # Calculate gross proceeds for cash flow
        gross_proceeds = action.quantity * sale_price

        # Track cumulative sales
        if lot.lot_id not in yearly_state.shares_sold:
            yearly_state.shares_sold[lot.lot_id] = 0
        yearly_state.shares_sold[lot.lot_id] += action.quantity

        # Update lot state
        if action.quantity >= lot.quantity:
            lot.lifecycle_state = LifecycleState.DISPOSED
            current_lots.remove(lot)
        else:
            lot.quantity -= action.quantity

        return {
            'gross_proceeds': gross_proceeds,
            'shares_sold': action.quantity
        }

    def _process_donation(self, action: PlannedAction, current_lots: List[ShareLot],
                         annual_components: AnnualTaxComponents, yearly_state: YearlyState) -> Dict[str, float]:
        """Process a donation action and extract tax components."""
        # Find the lot being donated
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for donation")

        # Get donation price
        if not action.price:
            raise ValueError(f"Price must be specified for donation action on {action.lot_id}")
        donation_price = action.price

        # Determine acquisition date and holding period
        if lot.exercise_date:
            acquisition_date = lot.exercise_date
            holding_period_days = (action.action_date - acquisition_date).days
        else:
            # For vested but not exercised shares, use grant date
            acquisition_date = lot.grant_date
            holding_period_days = (action.action_date - acquisition_date).days

        # Calculate donation value (FMV for display purposes)
        donation_value = action.quantity * donation_price

        # Calculate company match (if applicable)
        # Note: This is a simplified calculation - actual match may have limits
        company_match_amount = donation_value * self.profile.company_match_ratio

        # Create donation components
        donation_components = DonationComponents(
            lot_id=lot.lot_id,
            donation_date=action.action_date,
            shares_donated=action.quantity,
            fmv_at_donation=donation_price,
            cost_basis=lot.cost_basis,
            acquisition_date=acquisition_date,
            holding_period_days=holding_period_days,
            donation_value=donation_value,
            deduction_type='stock',
            company_match_ratio=self.profile.company_match_ratio,
            company_match_amount=company_match_amount
        )

        # Add components to annual aggregation
        annual_components.donation_components.append(donation_components)

        # Track cumulative donations
        if lot.lot_id not in yearly_state.shares_donated:
            yearly_state.shares_donated[lot.lot_id] = 0
        yearly_state.shares_donated[lot.lot_id] += action.quantity

        # Update lot state
        if action.quantity >= lot.quantity:
            lot.lifecycle_state = LifecycleState.DISPOSED
            lot.tax_treatment = TaxTreatment.DONATED
            current_lots.remove(lot)
        else:
            lot.quantity -= action.quantity

        return {
            'donation_value': donation_value,
            'company_match': company_match_amount
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
