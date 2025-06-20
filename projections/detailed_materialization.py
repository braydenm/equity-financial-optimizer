"""
Detailed Financial Materialization - Comprehensive calculation transparency.

This module provides detailed CSV output showing every calculation step,
enabling users to trace financial outcome differences to specific actions
and years. Captures all intermediate calculations, tax breakdowns, and
which calculators were used.
"""

import csv
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import date, datetime

from projections.projection_state import (
    ProjectionResult, YearlyState, PlannedAction, ActionType,
    ShareLot, LifecycleState, ShareType, TaxTreatment
)


@dataclass
class DetailedAction:
    """Captures all details of a single financial action."""
    # Action identification
    year: int
    action_date: date
    action_type: str
    lot_id: str
    quantity: int
    price: float
    notes: str

    # Pre-action state
    pre_cash: float = 0.0
    pre_shares_in_lot: int = 0
    pre_lot_lifecycle: str = ""
    pre_tax_treatment: str = ""

    # Simplified tracking
    tax_impact: float = 0.0

    # Action details
    calculator_used: str = ""
    strike_price: float = 0.0
    cost_basis: float = 0.0
    holding_period_days: int = 0
    acquisition_date: Optional[date] = None
    tax_treatment: str = ""
    vest_expiration_date: Optional[date] = None

    # Financial calculations
    gross_proceeds: float = 0.0
    exercise_cost: float = 0.0
    capital_gain: float = 0.0
    ordinary_income: float = 0.0

    # Tax calculations
    regular_tax_on_action: float = 0.0
    amt_on_action: float = 0.0
    amt_adjustment: float = 0.0
    capital_gains_tax: float = 0.0
    tax_rate_applied: float = 0.0
    total_tax_on_action: float = 0.0

    # Donation calculations
    donation_value: float = 0.0
    company_match: float = 0.0
    total_charitable_impact: float = 0.0
    deduction_taken: float = 0.0
    deduction_carryforward: float = 0.0

    # Pledge tracking
    pledge_created: float = 0.0
    pledge_fulfilled: float = 0.0
    pledge_balance_after: float = 0.0

    # Post-action state
    post_cash: float = 0.0
    post_shares_in_lot: int = 0
    post_lot_lifecycle: str = ""
    post_tax_treatment: str = ""
    net_cash_change: float = 0.0


@dataclass
class DetailedYear:
    """Captures all details for a single year."""
    year: int

    # Income
    w2_income: float = 0.0
    spouse_income: float = 0.0
    other_income: float = 0.0
    total_ordinary_income: float = 0.0

    # Actions in this year
    actions: List[DetailedAction] = field(default_factory=list)

    # Aggregate calculations
    total_exercise_cost: float = 0.0
    total_gross_proceeds: float = 0.0
    total_capital_gains: float = 0.0
    total_ordinary_income_from_equity: float = 0.0

    # Tax calculations
    agi: float = 0.0
    regular_taxable_income: float = 0.0
    regular_tax_before_credits: float = 0.0
    amt_taxable_income: float = 0.0
    amt_tax: float = 0.0
    total_tax_liability: float = 0.0

    # Credits and deductions
    amt_credits_generated: float = 0.0
    amt_credits_used: float = 0.0
    amt_credits_available: float = 0.0
    federal_charitable_deductions_used: float = 0.0
    federal_charitable_deductions_carried: float = 0.0
    ca_charitable_deductions_used: float = 0.0
    ca_charitable_deductions_carried: float = 0.0

    # Cash flow
    starting_cash: float = 0.0
    ending_cash: float = 0.0
    net_cash_flow: float = 0.0

    # Equity position summary
    vested_unexercised_shares: int = 0
    exercised_shares: int = 0
    total_equity_value: float = 0.0

    # Option expiration tracking
    opportunity_cost: float = 0.0


class DetailedMaterializer:
    """Materializes detailed financial calculations for full transparency."""

    def __init__(self):
        """Initialize the materializer."""
        self.detailed_years: List[DetailedYear] = []

    def materialize_projection(self, result: ProjectionResult) -> List[DetailedYear]:
        """Convert projection result into detailed materialization.

        Args:
            result: ProjectionResult containing all yearly states and actions

        Returns:
            List of DetailedYear objects with all calculations exposed
        """
        self.detailed_years = []

        # Process each year
        for i, yearly_state in enumerate(result.yearly_states):
            detailed_year = self._materialize_year(
                yearly_state,
                result.plan,
                i > 0 and result.yearly_states[i-1] or None
            )
            self.detailed_years.append(detailed_year)

        return self.detailed_years

    def _materialize_year(self,
                         yearly_state: YearlyState,
                         plan: Any,
                         prev_state: Optional[YearlyState]) -> DetailedYear:
        """Materialize all details for a single year."""
        detailed_year = DetailedYear(year=yearly_state.year)

        # Income details
        detailed_year.w2_income = yearly_state.income
        detailed_year.spouse_income = yearly_state.spouse_income
        detailed_year.other_income = yearly_state.other_income
        detailed_year.total_ordinary_income = yearly_state.income + yearly_state.spouse_income + yearly_state.other_income

        # Process each action in this year
        year_actions = [a for a in plan.planned_actions if a.action_date.year == yearly_state.year]

        for action in year_actions:
            detailed_action = self._materialize_action(
                action,
                yearly_state,
                prev_state
            )
            detailed_year.actions.append(detailed_action)

        # Aggregate calculations
        detailed_year.total_exercise_cost = yearly_state.exercise_costs  # Use from YearlyState
        detailed_year.total_gross_proceeds = sum(a.gross_proceeds for a in detailed_year.actions)
        detailed_year.total_capital_gains = sum(a.capital_gain for a in detailed_year.actions)
        detailed_year.total_ordinary_income_from_equity = sum(a.ordinary_income for a in detailed_year.actions)

        # Tax calculations
        detailed_year.agi = detailed_year.total_ordinary_income + detailed_year.total_capital_gains
        detailed_year.regular_taxable_income = 0.0  # Not available in TaxState
        detailed_year.regular_tax_before_credits = yearly_state.tax_state.regular_tax
        detailed_year.amt_taxable_income = 0.0  # Not available in TaxState
        detailed_year.amt_tax = yearly_state.tax_state.amt_tax
        detailed_year.total_tax_liability = yearly_state.tax_state.total_tax

        # Credits and deductions
        detailed_year.amt_credits_generated = yearly_state.tax_state.amt_credits_generated
        detailed_year.amt_credits_used = yearly_state.tax_state.amt_credits_used
        detailed_year.amt_credits_available = yearly_state.tax_state.amt_credits_remaining
        detailed_year.federal_charitable_deductions_used = yearly_state.charitable_state.federal_current_year_deduction
        detailed_year.federal_charitable_deductions_carried = yearly_state.charitable_state.federal_total_available
        detailed_year.ca_charitable_deductions_used = yearly_state.charitable_state.ca_current_year_deduction
        detailed_year.ca_charitable_deductions_carried = yearly_state.charitable_state.ca_total_available

        # Cash flow
        detailed_year.starting_cash = yearly_state.starting_cash
        detailed_year.ending_cash = yearly_state.ending_cash
        detailed_year.net_cash_flow = yearly_state.ending_cash - yearly_state.starting_cash

        # Equity position
        detailed_year.vested_unexercised_shares = sum(
            lot.quantity for lot in yearly_state.equity_holdings
            if lot.lifecycle_state.value == 'vested_not_exercised'
        )
        detailed_year.exercised_shares = sum(
            lot.quantity for lot in yearly_state.equity_holdings
            if lot.lifecycle_state.value == 'exercised_not_disposed'
        )
        detailed_year.total_equity_value = yearly_state.total_equity_value

        # Calculate opportunity cost from expiration events
        detailed_year.opportunity_cost = 0.0
        if hasattr(yearly_state, 'expiration_events') and yearly_state.expiration_events:
            for event in yearly_state.expiration_events:
                if hasattr(event, 'opportunity_cost'):
                    detailed_year.opportunity_cost += event.opportunity_cost

        return detailed_year

    def _materialize_action(self,
                           action: PlannedAction,
                           yearly_state: YearlyState,
                           prev_state: Optional[YearlyState]) -> DetailedAction:
        """Materialize all details for a single action."""
        detailed = DetailedAction(
            year=action.action_date.year,
            action_date=action.action_date,
            action_type=action.action_type.value,
            lot_id=action.lot_id,
            quantity=action.quantity,
            price=action.price or 0.0,
            notes=action.notes or ""
        )

        # Find the lot in current state
        lot = None
        for l in yearly_state.equity_holdings:
            if l.lot_id == action.lot_id:
                lot = l
                break

        if lot:
            detailed.post_shares_in_lot = lot.quantity
            detailed.pre_shares_in_lot = lot.quantity + action.quantity  # Approximate before action
            detailed.pre_lot_lifecycle = lot.lifecycle_state.value
            detailed.post_lot_lifecycle = lot.lifecycle_state.value
            detailed.pre_tax_treatment = lot.tax_treatment.value
            detailed.post_tax_treatment = lot.tax_treatment.value
            detailed.tax_treatment = lot.tax_treatment.value
            detailed.strike_price = lot.strike_price

            # Extract acquisition date and expiration date from lot
            if hasattr(lot, 'acquisition_date'):
                detailed.acquisition_date = lot.acquisition_date
                # Calculate holding period
                if action.action_type in [ActionType.SELL, ActionType.DONATE]:
                    detailed.holding_period_days = (action.action_date - lot.acquisition_date).days

            if hasattr(lot, 'expiration_date'):
                detailed.vest_expiration_date = lot.expiration_date

        # Starting cash position
        detailed.pre_cash = yearly_state.starting_cash

        # Calculator identification and calculations based on action type
        if action.action_type == ActionType.EXERCISE:
            detailed.calculator_used = "iso_exercise_calculator"
            detailed.exercise_cost = action.quantity * (lot.strike_price if lot else 0)
            detailed.amt_adjustment = action.quantity * ((action.price if action.price else 0) - (lot.strike_price if lot else 0))
            detailed.tax_impact = 0  # AMT impact tracked at year level

        elif action.action_type == ActionType.SELL:
            detailed.calculator_used = "share_sale_calculator"
            detailed.gross_proceeds = action.quantity * (action.price if action.price else 0)
            if lot:
                detailed.cost_basis = lot.strike_price
                detailed.capital_gain = ((action.price if action.price else 0) - detailed.cost_basis) * action.quantity

                # Simplified tax rate
                if lot.tax_treatment == TaxTreatment.LTCG:
                    detailed.tax_rate_applied = 0.243
                else:
                    detailed.tax_rate_applied = 0.333

                detailed.capital_gains_tax = max(0, detailed.capital_gain * detailed.tax_rate_applied)
                detailed.tax_impact = detailed.capital_gains_tax

                # Create pledge from sale
                from projections.projection_state import UserProfile
                if hasattr(yearly_state, 'user_profile') or hasattr(self, 'user_profile'):
                    pledge_pct = getattr(getattr(yearly_state, 'user_profile', getattr(self, 'user_profile', None)), 'pledge_percentage', 0.5)
                    detailed.pledge_created = detailed.gross_proceeds * pledge_pct

        elif action.action_type == ActionType.DONATE:
            detailed.calculator_used = "share_donation_calculator"
            detailed.donation_value = action.quantity * (action.price if action.price else 0)
            detailed.total_charitable_impact = detailed.donation_value
            detailed.tax_impact = 0  # Deduction benefit tracked at year level

        # Simplified cash change
        detailed.net_cash_change = -detailed.exercise_cost + detailed.gross_proceeds - detailed.tax_impact
        detailed.post_cash = detailed.pre_cash + detailed.net_cash_change

        return detailed

    def save_detailed_csv(self, detailed_years: List[DetailedYear], output_path: str):
        """Save detailed materialization to comprehensive CSV."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Define all possible fields for the comprehensive CSV
        all_fieldnames = [
            # Common fields
            'year', 'action_date', 'action_type', 'lot_id', 'quantity', 'price', 'notes', 'calculator_used',
            # Year summary fields
            'w2_income', 'total_ordinary_income', 'total_exercise_cost', 'total_gross_proceeds',
            'total_capital_gains', 'agi', 'regular_tax', 'amt_tax', 'total_tax_liability',
            'ending_cash', 'total_equity_value', 'vested_unexercised_shares', 'exercised_shares',
            # Action detail fields
            'strike_price', 'cost_basis', 'holding_period_days', 'gross_proceeds', 'exercise_cost',
            'capital_gain', 'ordinary_income', 'regular_tax_on_action', 'amt_on_action', 'amt_adjustment',
            'capital_gains_tax', 'tax_rate_applied', 'total_tax_on_action', 'donation_value',
            'company_match', 'total_charitable_impact', 'deduction_taken', 'pledge_created',
            'pledge_fulfilled', 'net_cash_change', 'post_shares_in_lot'
        ]

        # Flatten all actions across all years
        all_actions = []
        for year in detailed_years:
            # Add year-level summary row
            year_summary = {field: '' for field in all_fieldnames}  # Initialize with empty values
            year_summary.update({
                'year': year.year,
                'action_date': f"{year.year}-12-31",
                'action_type': 'YEAR_SUMMARY',
                'lot_id': 'ALL',
                'quantity': 0,
                'price': 0,
                'notes': f'Year {year.year} Summary',
                'calculator_used': 'N/A',
                'w2_income': year.w2_income,
                'total_ordinary_income': year.total_ordinary_income,
                'total_exercise_cost': year.total_exercise_cost,
                'total_gross_proceeds': year.total_gross_proceeds,
                'total_capital_gains': year.total_capital_gains,
                'agi': year.agi,
                'regular_tax': year.regular_tax_before_credits,
                'amt_tax': year.amt_tax,
                'total_tax_liability': year.total_tax_liability,
                'ending_cash': year.ending_cash,
                'total_equity_value': year.total_equity_value,
                'vested_unexercised_shares': year.vested_unexercised_shares,
                'exercised_shares': year.exercised_shares
            })
            all_actions.append(year_summary)

            # Add individual actions
            for action in year.actions:
                action_dict = {field: '' for field in all_fieldnames}  # Initialize with empty values
                action_dict.update({
                    'year': action.year,
                    'action_date': action.action_date.isoformat(),
                    'action_type': action.action_type,
                    'lot_id': action.lot_id,
                    'quantity': action.quantity,
                    'price': action.price,
                    'notes': action.notes,
                    'calculator_used': action.calculator_used,
                    'strike_price': action.strike_price,
                    'cost_basis': action.cost_basis,
                    'holding_period_days': action.holding_period_days,
                    'gross_proceeds': action.gross_proceeds,
                    'exercise_cost': action.exercise_cost,
                    'capital_gain': action.capital_gain,
                    'ordinary_income': action.ordinary_income,
                    'regular_tax_on_action': action.regular_tax_on_action,
                    'amt_on_action': action.amt_on_action,
                    'amt_adjustment': action.amt_adjustment,
                    'capital_gains_tax': action.capital_gains_tax,
                    'tax_rate_applied': action.tax_rate_applied,
                    'total_tax_on_action': action.total_tax_on_action,
                    'donation_value': action.donation_value,
                    'company_match': action.company_match,
                    'total_charitable_impact': action.total_charitable_impact,
                    'deduction_taken': action.deduction_taken,
                    'pledge_created': action.pledge_created,
                    'pledge_fulfilled': action.pledge_fulfilled,
                    'net_cash_change': action.net_cash_change,
                    'post_shares_in_lot': action.post_shares_in_lot
                })
                all_actions.append(action_dict)

        # Write to CSV
        if all_actions:
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=all_fieldnames)
                writer.writeheader()
                writer.writerows(all_actions)

    def save_action_level_csv(self, detailed_years: List[DetailedYear], output_path: str):
        """Save action-level details only (no year summaries)."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Collect all actions
        all_actions = []
        for year in detailed_years:
            for action in year.actions:
                all_actions.append({
                    'year': action.year,
                    'date': action.action_date.isoformat(),
                    'type': action.action_type,
                    'lot_id': action.lot_id,
                    'quantity': action.quantity,
                    'price': round(action.price, 2),
                    'acquisition_date': action.acquisition_date.isoformat() if action.acquisition_date else '',
                    'holding_period_days': action.holding_period_days,
                    'tax_treatment': action.tax_treatment,
                    'calculator': action.calculator_used,
                    'gross_proceeds': round(action.gross_proceeds, 2),
                    'exercise_cost': round(action.exercise_cost, 2),
                    'capital_gain': round(action.capital_gain, 2),
                    'amt_adjustment': round(action.amt_adjustment, 2),
                    'tax': round(action.total_tax_on_action, 2),
                    'donation_value': round(action.donation_value, 2),
                    'company_match': round(action.company_match, 2),
                    'pledge_created': round(action.pledge_created, 2),
                    'net_cash_change': round(action.net_cash_change, 2),
                    'vest_expiration_date': action.vest_expiration_date.isoformat() if action.vest_expiration_date else '',
                    'notes': action.notes
                })

        # Always create the file, even if empty
        fieldnames = [
            'year', 'date', 'type', 'lot_id', 'quantity', 'price',
            'acquisition_date', 'holding_period_days', 'tax_treatment',
            'calculator', 'gross_proceeds', 'exercise_cost', 'capital_gain',
            'amt_adjustment', 'tax', 'donation_value', 'company_match',
            'pledge_created', 'net_cash_change', 'vest_expiration_date', 'notes'
        ]

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            if all_actions:
                writer.writerows(all_actions)

    def save_annual_summary_csv(self, detailed_years: List[DetailedYear], output_path: str):
        """Save annual summaries with key metrics."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        summaries = []
        for year in detailed_years:
            summaries.append({
                'year': year.year,
                'w2_income': round(year.w2_income, 2),
                'total_income': round(year.total_ordinary_income, 2),
                'exercise_costs': round(year.total_exercise_cost, 2),
                'sale_proceeds': round(year.total_gross_proceeds, 2),
                'capital_gains': round(year.total_capital_gains, 2),
                'donations': round(sum(a.donation_value for a in year.actions), 2),
                'company_match': round(sum(a.company_match for a in year.actions), 2),
                'regular_tax': round(year.regular_tax_before_credits, 2),
                'amt_tax': round(year.amt_tax, 2),
                'total_tax': round(year.total_tax_liability, 2),
                'ending_cash': round(year.ending_cash, 2),
                'equity_value': round(year.total_equity_value, 2),
                'net_worth': round(year.ending_cash + year.total_equity_value, 2),
                'opportunity_cost': round(year.opportunity_cost, 2)
            })

        if summaries:
            fieldnames = list(summaries[0].keys())
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(summaries)


def materialize_detailed_projection(result: ProjectionResult,
                                   output_dir: str,
                                   scenario_name: str = "scenario") -> None:
    """Main function to materialize and save detailed projection results.

    Args:
        result: ProjectionResult to materialize
        output_dir: Directory to save CSV files
        scenario_name: Name prefix for output files
    """
    materializer = DetailedMaterializer()
    detailed_years = materializer.materialize_projection(result)

    # Save different views of the data
    base_name = scenario_name.lower().replace(' ', '_').replace('-', '_')

    # Comprehensive detail with all calculations
    # Save all three levels of detail
    # Commented out - detailed_calculations.csv is redundant with action_summary and annual_summary
    # materializer.save_detailed_csv(
    #     detailed_years,
    #     f"{output_dir}/{base_name}_detailed_calculations.csv"
    # )

    # Action-level summary
    materializer.save_action_level_csv(
        detailed_years,
        f"{output_dir}/{base_name}_action_summary.csv"
    )

    # Annual summary
    materializer.save_annual_summary_csv(
        detailed_years,
        f"{output_dir}/{base_name}_annual_summary.csv"
    )
