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
from calculators.tax_constants import (
    FEDERAL_SUPPLEMENTAL_WITHHOLDING_RATE,
    CALIFORNIA_SUPPLEMENTAL_WITHHOLDING_RATE,
    MEDICARE_RATE,
    CALIFORNIA_SDI_RATE,
    CHARITABLE_CARRYFORWARD_YEARS
)
from calculators.components import (
    ISOExerciseComponents,
    NSOExerciseComponents,
    ShareSaleComponents,
    DonationComponents,
    AnnualTaxComponents
)
from projections.vesting_events import process_natural_vesting, VestingEvent, process_natural_expiration, ExpirationEvent
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

    def _validate_exercise_plan(self, plan: ProjectionPlan) -> None:
        """
        Validate that total planned exercises don't exceed lot sizes.

        Args:
            plan: ProjectionPlan to validate

        Raises:
            ValueError: If any lot would be over-exercised
        """
        # Group exercise actions by lot_id and sum quantities
        exercise_totals = {}
        for action in plan.planned_actions:
            if action.action_type == ActionType.EXERCISE:
                lot_id = action.lot_id
                exercise_totals[lot_id] = exercise_totals.get(lot_id, 0) + action.quantity

        # Check against initial lot sizes
        for lot_id, total_exercise_quantity in exercise_totals.items():
            # Find the lot in initial_lots
            lot = next((l for l in plan.initial_lots if l.lot_id == lot_id), None)
            if not lot:
                raise ValueError(f"Exercise planned for lot {lot_id} but lot not found in initial position")

            if total_exercise_quantity > lot.quantity:
                raise ValueError(f"Total planned exercises for lot {lot_id} ({total_exercise_quantity} shares) "
                               f"exceed lot size ({lot.quantity} shares). Check for duplicate exercise actions.")

    def evaluate_projection_plan(self, plan: ProjectionPlan) -> ProjectionResult:
        """
        Evaluate a complete projection plan over multiple years.

        Args:
            plan: ProjectionPlan with initial state and planned actions

        Returns:
            ProjectionResult with yearly states and summary metrics
        """
        # Validate the exercise plan before processing
        self._validate_exercise_plan(plan)

        yearly_states = []
        current_lots = deepcopy(plan.initial_lots)
        current_cash = plan.initial_cash
        current_investments = self.profile.taxable_investments

        # Initialize carryforward states
        # AMT credits from profile apply to the first projection year
        amt_credits_remaining = self.profile.amt_credit_carryforward
        federal_charitable_carryforward = {}  # year -> {creation_year: amount} (federal)
        ca_charitable_carryforward = {}  # year -> {creation_year: amount} (California)
        pledge_state = PledgeState()
        cumulative_shares_sold = {}  # Track cumulative sales across years
        cumulative_shares_donated = {}  # Track cumulative donations across years

        # Resolve pledge settings (scenario overrides profile)
        pledge_elections = plan.tax_elections.get('pledge_elections', {})
        self.pledge_percentage = pledge_elections.get('pledge_percentage', self.profile.pledge_percentage)
        self.company_match_ratio = pledge_elections.get('company_match_ratio', self.profile.company_match_ratio)

        # Process each year in the projection
        for year in range(plan.start_date.year, plan.end_date.year + 1):
            year_start_cash = current_cash
            year_start_investments = current_investments

            # Calculate all income sources
            year_w2_income = self.profile.annual_w2_income
            year_total_income = self.profile.get_total_income()
            year_investment_income = self.profile.interest_income + self.profile.dividend_income

            # Model investment growth
            investment_growth = current_investments * self.profile.investment_return_rate
            current_investments = current_investments * (1 + self.profile.investment_return_rate)

            year_exercise_costs = 0.0
            year_sale_proceeds = 0.0  # Track total sale proceeds for the year
            year_tax_paid = 0.0
            year_donation_value = 0.0
            year_company_match = 0.0

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
                company_match_received=0.0,
                ending_cash=0.0,
                tax_state=year_tax_state,
                charitable_state=CharitableDeductionState(),
                equity_holdings=[],
                total_equity_value=0.0,
                shares_sold=deepcopy(cumulative_shares_sold),
                shares_donated=deepcopy(cumulative_shares_donated),
                pledge_state=pledge_state,  # Shared reference, will snapshot at year end
                total_net_worth=0.0,
                annual_tax_components=annual_components,
                spouse_income=self.profile.spouse_w2_income,
                other_income=self.profile.other_income
            )

            vesting_events = process_natural_vesting(current_lots, year)

            # Track vesting events for CSV output
            yearly_state.vesting_events = vesting_events
            market_price = plan.price_projections.get(year, 0.0)
            expiration_events = process_natural_expiration(current_lots, year, market_price)
            yearly_state.expiration_events = expiration_events

            # Process each action chronologically
            for action in sorted(year_actions, key=lambda a: a.action_date):
                if action.action_type == ActionType.EXERCISE:
                    # Get the FMV - use action price if specified (e.g., tender offer), otherwise use projection
                    if action.price is not None:
                        year_fmv = action.price
                    else:
                        if year not in plan.price_projections:
                            raise ValueError(f"Price projection for year {year} not found in plan")
                        year_fmv = plan.price_projections[year]
                    exercise_result = self._process_exercise(action, current_lots, annual_components, year_fmv)
                    year_exercise_costs += exercise_result['exercise_cost']

                elif action.action_type == ActionType.SELL:
                    sale_result = self._process_sale(action, current_lots, annual_components, yearly_state)
                    year_sale_proceeds += sale_result['gross_proceeds']  # Track total sale proceeds

                    # Get grant-specific charitable program for pledge obligation
                    sold_lot = sale_result['lot']
                    grant_charitable_program = self._get_charitable_program_for_grant(sold_lot.grant_id)

                    # Create pledge obligation using grant-specific settings
                    obligation = PledgeCalculator.calculate_obligation(
                        shares_sold=action.quantity,
                        sale_price=action.price if action.price else 0,
                        pledge_percentage=grant_charitable_program['pledge_percentage'],
                        sale_date=action.action_date,
                        lot_id=action.lot_id,
                        assumed_ipo=self.profile.assumed_ipo
                    )
                    pledge_state.add_obligation(obligation)
                    
                    # Track year-specific obligated shares
                    yearly_state.pledge_shares_obligated_this_year += obligation.maximalist_shares_required

                elif action.action_type == ActionType.DONATE:
                    donation_result = self._process_donation(action, current_lots, annual_components, yearly_state)
                    year_donation_value += donation_result['donation_value']
                    
                    # Track year-specific donated shares
                    yearly_state.pledge_shares_donated_this_year += action.quantity
                    
                    # Apply donation to pledge obligations using FIFO discharge
                    discharge_result = pledge_state.discharge_donation(
                        donation_amount=donation_result['donation_value'],
                        shares_donated=action.quantity,
                        donation_date=action.action_date
                    )

                    # Calculate company match based on eligible amount using grant-specific ratio
                    eligible_amount = discharge_result.get('eligible_amount', 0.0)
                    # Get the company match ratio from the donation component that was just created
                    latest_donation_component = annual_components.donation_components[-1]
                    grant_company_match_ratio = latest_donation_component.company_match_ratio
                    actual_company_match = eligible_amount * grant_company_match_ratio
                    year_company_match += actual_company_match

                    # Update the donation result with actual company match
                    donation_result['company_match'] = actual_company_match

            # Calculate annual tax using aggregated components
            annual_components.aggregate_components()

            # Check if basis election applies for this year #Claude TODO: Improve docs here.
            elect_basis = False
            if 'charitable_basis_election_years' in plan.tax_elections:
                elect_basis = year in plan.tax_elections['charitable_basis_election_years']

            # Extract current year carryforward by creation year for FIFO (no expiration - let annual tax calculator handle that)

            federal_carryforward_by_creation_year_current = self._extract_current_year_carryforward(
                federal_charitable_carryforward, year
            )
            ca_carryforward_by_creation_year_current = self._extract_current_year_carryforward(
                ca_charitable_carryforward, year
            )



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
                existing_amt_credit=amt_credits_remaining,
                carryforward_stock_by_creation_year=federal_carryforward_by_creation_year_current,
                ca_carryforward_stock_by_creation_year=ca_carryforward_by_creation_year_current,
                elect_basis_deduction=elect_basis
            )



            # Calculate net tax payment (gross tax minus withholdings)
            year_gross_tax = tax_result.total_tax
            year_withholdings = self.calculate_year_withholding(year, annual_components)
            year_tax_paid = max(0, year_gross_tax - year_withholdings)  # Net payment due

            year_tax_state.amt_tax = tax_result.federal_amt + tax_result.ca_amt
            year_tax_state.regular_tax = tax_result.federal_regular_tax + tax_result.ca_tax_owed
            year_tax_state.total_tax = tax_result.total_tax
            year_tax_state.amt_credits_generated = tax_result.federal_amt_credit_generated
            year_tax_state.amt_credits_used = tax_result.federal_amt_credit_used

            # Store separate federal/state components for detailed reporting
            year_tax_state.federal_regular_tax = tax_result.federal_regular_tax
            year_tax_state.federal_amt_tax = tax_result.federal_amt
            year_tax_state.ca_regular_tax = tax_result.ca_tax_owed
            year_tax_state.ca_amt_tax = tax_result.ca_amt

            # Update AMT credits for next year
            amt_credits_remaining = tax_result.federal_amt_credit_carryforward
            year_tax_state.amt_credits_remaining = amt_credits_remaining

            # Calculate end of year cash including all income/expenses and sale proceeds
            # Note: Investment growth stays in investments, not added to liquid cash
            year_expenses = self.profile.get_annual_expenses()
            year_end_cash = (year_start_cash + year_total_income + year_sale_proceeds
                           - year_exercise_costs - year_tax_paid - year_expenses)
            current_cash = year_end_cash

            # Use FIFO-compliant carryforward propagation from annual tax calculator results
            # The annual tax calculator now returns detailed consumption by creation year

            # Propagate federal carryforward using FIFO consumption results
            federal_remaining_by_creation_year = tax_result.charitable_deduction_result.carryforward_remaining_by_creation_year

            if federal_remaining_by_creation_year:
                next_year = year + 1
                if next_year not in federal_charitable_carryforward:
                    federal_charitable_carryforward[next_year] = {}
                # Propagate remaining amounts by creation year
                for creation_year, remaining_amount in federal_remaining_by_creation_year.items():
                    if remaining_amount > 0:
                        federal_charitable_carryforward[next_year][creation_year] = remaining_amount

            # Add new carryforward from current year donations (if any)
            federal_new_carryforward = tax_result.charitable_deduction_result.total_carryforward - sum(federal_remaining_by_creation_year.values())

            if federal_new_carryforward > 0 and year_donation_value > 0:
                next_year = year + 1
                if next_year not in federal_charitable_carryforward:
                    federal_charitable_carryforward[next_year] = {}
                federal_charitable_carryforward[next_year][year] = federal_new_carryforward

            # Propagate California carryforward using FIFO consumption results
            ca_remaining_by_creation_year = tax_result.ca_charitable_deduction_result.carryforward_remaining_by_creation_year

            if ca_remaining_by_creation_year:
                next_year = year + 1
                if next_year not in ca_charitable_carryforward:
                    ca_charitable_carryforward[next_year] = {}
                # Propagate remaining amounts by creation year
                for creation_year, remaining_amount in ca_remaining_by_creation_year.items():
                    if remaining_amount > 0:
                        ca_charitable_carryforward[next_year][creation_year] = remaining_amount

            # Add new carryforward from current year donations (if any)
            ca_new_carryforward = tax_result.ca_charitable_deduction_result.total_carryforward - sum(ca_remaining_by_creation_year.values())

            if ca_new_carryforward > 0 and year_donation_value > 0:
                next_year = year + 1
                if next_year not in ca_charitable_carryforward:
                    ca_charitable_carryforward[next_year] = {}
                ca_charitable_carryforward[next_year][year] = ca_new_carryforward

            # Remove current year carryforwards since they've been processed
            if year in federal_charitable_carryforward:
                del federal_charitable_carryforward[year]
            if year in ca_charitable_carryforward:
                del ca_charitable_carryforward[year]

            # Use expiration amounts from tax calculator (single source of truth)
            federal_expired = tax_result.charitable_deduction_result.expired_carryforward
            ca_expired = tax_result.ca_charitable_deduction_result.expired_carryforward


            # Calculate charitable deduction state using AGI-limited amounts from tax calculation (federal and state)
            charitable_state = self._calculate_charitable_state(
                year_donation_value, federal_charitable_carryforward, ca_charitable_carryforward,
                year, tax_result, federal_expired, ca_expired
            )

            # Pledge state is already maintained and updated throughout the year
            # No additional calculation needed

            # Calculate total equity value
            if year not in plan.price_projections:
                raise ValueError(f"Price projection for year {year} not found in plan")
            current_price = plan.price_projections[year]
            total_equity_value = sum(lot.quantity * current_price for lot in current_lots
                                   if lot.lifecycle_state in [LifecycleState.VESTED_NOT_EXERCISED,
                                                             LifecycleState.EXERCISED_NOT_DISPOSED])

            # Calculate year-specific expired shares before processing window closures
            for obligation in pledge_state.obligations:
                if obligation.match_window_closes and obligation.match_window_closes.year == year:
                    unfulfilled = obligation.maximalist_shares_required - obligation.maximalist_shares_donated
                    if unfulfilled > 0:
                        yearly_state.pledge_shares_expired_this_year += unfulfilled
            
            # Process match window closures and calculate lost opportunities
            lost_match_value = pledge_state.process_window_closures(
                current_year=year,
                current_price=current_price,
                company_match_ratio=self.company_match_ratio
            )

            # Update yearly state with final values
            yearly_state.exercise_costs = year_exercise_costs
            yearly_state.annual_tax_components = annual_components
            yearly_state.tax_paid = year_tax_paid
            yearly_state.gross_tax = year_gross_tax
            yearly_state.tax_withholdings = year_withholdings
            yearly_state.living_expenses = year_expenses
            yearly_state.investment_income = year_investment_income
            yearly_state.investment_balance = current_investments
            yearly_state.donation_value = year_donation_value
            yearly_state.company_match_received = year_company_match
            yearly_state.lost_match_opportunities = lost_match_value
            yearly_state.ending_cash = year_end_cash
            yearly_state.charitable_state = charitable_state
            yearly_state.federal_charitable_deduction_result = tax_result.charitable_deduction_result
            yearly_state.ca_charitable_deduction_result = tax_result.ca_charitable_deduction_result
            yearly_state.equity_holdings = deepcopy(current_lots)
            yearly_state.total_equity_value = total_equity_value
            yearly_state.pledge_state = deepcopy(pledge_state)
            yearly_state.total_net_worth = year_end_cash + total_equity_value + current_investments

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

    def _get_charitable_program_for_grant(self, grant_id: Optional[str]) -> Dict[str, float]:
        """
        Get charitable program settings for a specific grant.

        Args:
            grant_id: Grant identifier, may be None for legacy lots

        Returns:
            Dictionary with pledge_percentage and company_match_ratio
        """
        # If no grant_id provided, use profile-level defaults
        if not grant_id:
            return {
                'pledge_percentage': self.profile.pledge_percentage,
                'company_match_ratio': self.profile.company_match_ratio
            }

        # Look up grant-specific charitable program
        for grant in self.profile.grants:
            if grant.get('grant_id') == grant_id:
                charitable_program = grant.get('charitable_program', {})
                return {
                    'pledge_percentage': charitable_program.get('pledge_percentage', self.profile.pledge_percentage),
                    'company_match_ratio': charitable_program.get('company_match_ratio', self.profile.company_match_ratio)
                }

        # Fallback to profile-level settings if grant not found
        return {
            'pledge_percentage': self.profile.pledge_percentage,
            'company_match_ratio': self.profile.company_match_ratio
        }



    def _process_exercise(self, action: PlannedAction, current_lots: List[ShareLot],
                         annual_components: AnnualTaxComponents, current_year_fmv: float) -> Dict[str, float]:
        """Process an exercise action and extract tax components.

        Args:
            action: The exercise action to process
            current_lots: Current share lots
            annual_components: Annual tax components to update
            current_year_fmv: Fair market value for the current year from price projections
        """
        # Find the lot being exercised
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for exercise")

        # Validate share quantity
        if action.quantity > lot.quantity:
            raise ValueError(f"Cannot exercise {action.quantity} shares from lot {action.lot_id} - only {lot.quantity} shares available")

        # Calculate exercise cost
        exercise_cost = action.quantity * lot.strike_price

        # Get current FMV
        # Use the year's projected FMV for exercises (not action.price which may be strike price)
        # This fixes NSO bargain element calculations
        current_price = current_year_fmv

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
            cost_basis=current_price if lot.share_type == ShareType.NSO else lot.strike_price,
            fmv_at_exercise=current_price,  # Critical for disqualifying disposition calculations
            taxes_paid=0.0,  # Tax will be calculated at year-end
            expiration_date=lot.expiration_date,  # Preserve expiration date from parent lot
            grant_id=lot.grant_id  # Preserve grant_id from parent lot
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
                     annual_components: AnnualTaxComponents, yearly_state: YearlyState) -> Dict[str, Any]:
        """Process a sale action and extract tax components."""
        # Find the lot being sold
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for sale")

        # Validate share quantity
        if action.quantity > lot.quantity:
            raise ValueError(f"Cannot sell {action.quantity} shares from lot {action.lot_id} - only {lot.quantity} shares available")

        # Get sale price
        if not action.price:
            raise ValueError(f"Price must be specified for sale action on {action.lot_id}")
        sale_price = action.price

        # Determine acquisition date and type based on lifecycle state
        exercise_date = lot.exercise_date
        if not exercise_date:
            # Fallback: use action date if lot doesn't have exercise date
            exercise_date = action.action_date

        # Calculate sale components
        sale_components = self.sale_calculator.calculate_sale_components(
            lot_id=lot.lot_id,
            sale_date=action.action_date,
            shares_to_sell=action.quantity,
            sale_price=sale_price,
            cost_basis=lot.cost_basis,
            exercise_date=exercise_date,
            is_iso=(lot.share_type == ShareType.ISO),
            grant_date=lot.grant_date,
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
            'shares_sold': action.quantity,
            'lot': lot
        }

    def _process_donation(self, action: PlannedAction, current_lots: List[ShareLot],
                         annual_components: AnnualTaxComponents, yearly_state: YearlyState) -> Dict[str, float]:
        """Process a donation action and extract tax components."""
        # Find the lot being donated
        lot = next((l for l in current_lots if l.lot_id == action.lot_id), None)
        if not lot:
            raise ValueError(f"Lot {action.lot_id} not found for donation")

        # Validate share quantity
        if action.quantity > lot.quantity:
            raise ValueError(f"Cannot donate {action.quantity} shares from lot {action.lot_id} - only {lot.quantity} shares available")

        # Get donation price
        if not action.price:
            raise ValueError(f"Price must be specified for donation action on {action.lot_id}")
        donation_price = action.price

        # Determine acquisition date and holding period
        if lot.exercise_date:
            exercise_date = lot.exercise_date
            holding_period_days = (action.action_date - exercise_date).days
        else:
            holding_period_days = 0

        # Calculate donation value (FMV for display purposes)
        donation_value = action.quantity * donation_price

        # Company match will be calculated after pledge discharge based on eligible amount
        company_match_amount = 0.0

        # Get grant-specific charitable program for company match ratio
        grant_charitable_program = self._get_charitable_program_for_grant(lot.grant_id)
        grant_company_match_ratio = grant_charitable_program['company_match_ratio']

        # Create donation components
        donation_components = DonationComponents(
            lot_id=lot.lot_id,
            donation_date=action.action_date,
            shares_donated=action.quantity,
            fmv_at_donation=donation_price,
            cost_basis=lot.cost_basis,
            exercise_date=exercise_date,
            holding_period_days=holding_period_days,
            donation_value=donation_value,
            deduction_type='stock',
            company_match_ratio=grant_company_match_ratio,
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
                                  federal_carryforward: Dict[int, Dict[int, float]],
                                  ca_carryforward: Dict[int, Dict[int, float]],
                                  year: int,
                                  tax_result,
                                  federal_expired: float = 0.0,
                                  ca_expired: float = 0.0) -> CharitableDeductionState:
        """Calculate charitable deduction state with carryforward using AGI-limited amounts for both federal and state."""
        # Use the AGI-limited deduction amounts from the tax calculation results
        # for both federal and California to properly respect their different AGI limits
        federal_agi_limited_deduction = tax_result.charitable_deduction_result.total_deduction_used
        ca_agi_limited_deduction = tax_result.ca_charitable_deduction_result.total_deduction_used

        # Convert carryforward structure for display (flatten creation year tracking)
        federal_remaining_flat = {}
        for future_year, creation_dict in federal_carryforward.items():
            federal_remaining_flat[future_year] = sum(creation_dict.values())

        ca_remaining_flat = {}
        for future_year, creation_dict in ca_carryforward.items():
            ca_remaining_flat[future_year] = sum(creation_dict.values())

        return CharitableDeductionState(
            federal_current_year_deduction=federal_agi_limited_deduction,
            federal_carryforward_remaining=federal_remaining_flat,
            federal_total_available=federal_agi_limited_deduction + sum(federal_remaining_flat.values()),
            federal_expired_this_year=federal_expired,
            ca_current_year_deduction=ca_agi_limited_deduction,
            ca_carryforward_remaining=ca_remaining_flat,
            ca_total_available=ca_agi_limited_deduction + sum(ca_remaining_flat.values()),
            ca_expired_this_year=ca_expired
        )

    def _extract_current_year_carryforward(self, carryforward_dict: Dict[int, Dict[int, float]],
                                         current_year: int) -> Dict[int, float]:
        """
        Extract current year carryforward by creation year for FIFO processing.

        No expiration logic - the Annual Tax Calculator handles all expiration as the single source of truth.

        Args:
            carryforward_dict: Dictionary mapping year -> {creation_year: amount}
            current_year: Current tax year

        Returns:
            Dict[int, float]: current_year_carryforward_by_creation_year
        """
        current_year_carryforward_by_creation_year = {}

        if current_year in carryforward_dict:
            creation_year_dict = carryforward_dict[current_year]
            # Return all carryforwards by creation year - let annual tax calculator handle expiration
            current_year_carryforward_by_creation_year = creation_year_dict.copy()

        return current_year_carryforward_by_creation_year

    def _calculate_pledge_state(self, pledge_state: PledgeState, year: int) -> PledgeState:
        """Return the current pledge state (no calculation needed as it's maintained throughout)."""
        # The pledge state is maintained throughout the year via add_obligation and discharge_donation
        # This method exists for compatibility but doesn't need to do additional calculations
        return pledge_state

    def calculate_year_withholding(self, year: int, annual_components: AnnualTaxComponents) -> float:
        """
        Calculate tax withholding for a given year based on income types.

        For years after 2024, uses base withholding amounts if available to avoid
        inflated withholding from stock exercise years.

        Args:
            year: Tax year
            annual_components: Annual tax components with income breakdown

        Returns:
            Total withholding amount for the year
        """
        # Calculate regular income withholding (W2, interest, dividends, bonuses)
        regular_income = (
            self.profile.annual_w2_income +
            self.profile.spouse_w2_income +
            self.profile.interest_income +
            self.profile.dividend_income +
            self.profile.bonus_expected
        )
        regular_withholding = regular_income * self.profile.regular_income_withholding_rate

        # Calculate supplemental withholding for stock compensation
        # NSO exercises
        nso_income = sum(comp.bargain_element for comp in annual_components.nso_exercise_components)

        # RSU vesting (if any RSU components exist)
        rsu_income = 0.0  # RSUs would be added here if implemented

        total_stock_income = nso_income + rsu_income
        supplemental_withholding = total_stock_income * self.profile.supplemental_income_withholding_rate

        return regular_withholding + supplemental_withholding
