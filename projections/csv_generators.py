"""
CSV generators for projection outputs.

This module provides CSV generation functions that automatically export data
from components and state objects without recalculation or reconstruction.
The approach uses dataclass introspection for automatic field inclusion,
ensuring new fields appear in CSVs without code changes.
"""

import os
import csv
from dataclasses import asdict, fields
from typing import List, Any, Dict
from datetime import date
from projections.projection_state import ProjectionResult, YearlyState, PledgeState
from calculators.liquidity_event import LiquidityEvent


def save_components_csv(result: ProjectionResult, output_path: str) -> None:
    """
    Generate comprehensive component CSV with automatic field inclusion.

    This replaces action_summary.csv with a more maintainable approach
    that automatically includes all component fields.

    Args:
        result: ProjectionResult containing yearly states with components
        output_path: Path to save the CSV file
    """
    rows = []

    for yearly_state in result.yearly_states:
        if not yearly_state.annual_tax_components:
            continue

        components = yearly_state.annual_tax_components
        year_context = {
            'year': yearly_state.year,
            'current_share_price': result.plan.price_projections.get(yearly_state.year, 0.0)
        }

        # ISO Exercises
        for comp in components.iso_exercise_components:
            row = {
                'component_type': 'ISO Exercise',
                **year_context,
                **asdict(comp)
            }
            rows.append(row)

        # NSO Exercises
        for comp in components.nso_exercise_components:
            row = {
                'component_type': 'NSO Exercise',
                **year_context,
                **asdict(comp)
            }
            rows.append(row)

        # Sales
        for comp in components.sale_components:
            row_dict = asdict(comp)
            # Convert enum to string
            if 'disposition_type' in row_dict and hasattr(row_dict['disposition_type'], 'value'):
                row_dict['disposition_type'] = row_dict['disposition_type'].value

            row = {
                'component_type': 'Sale',
                **year_context,
                **row_dict,
                # Add computed display fields
                'total_proceeds': comp.shares_sold * comp.sale_price,
                'total_gain': comp.short_term_gain + comp.long_term_gain + comp.ordinary_income
            }
            rows.append(row)

        # Stock Donations
        for comp in components.donation_components:
            row = {
                'component_type': 'Stock Donation',
                **year_context,
                **asdict(comp),
                'total_impact': comp.donation_value + comp.company_match_amount
            }
            rows.append(row)

        # Cash Donations
        for comp in components.cash_donation_components:
            row = {
                'component_type': 'Cash Donation',
                **year_context,
                **asdict(comp),
                'total_impact': comp.amount + comp.company_match_amount
            }
            rows.append(row)

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if rows:
        # Convert date objects to strings in all rows
        for row in rows:
            for key, value in list(row.items()):
                if isinstance(value, date):
                    row[key] = value.isoformat()

        # Get all unique column names
        all_columns = set()
        for row in rows:
            all_columns.update(row.keys())

        # Order columns
        priority_cols = ['year', 'component_type', 'lot_id', 'shares_exercised',
                        'shares_sold', 'shares_donated', 'amount', 'action_date',
                        'action_type', 'calculator_name']
        other_cols = sorted([col for col in all_columns if col not in priority_cols])
        ordered_cols = [col for col in priority_cols if col in all_columns] + other_cols

        # Write CSV
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=ordered_cols)
            writer.writeheader()
            writer.writerows(rows)
    else:
        # Empty file with minimal headers
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['year', 'component_type'])
            writer.writeheader()




def save_annual_summary_csv(result: ProjectionResult, output_path: str) -> None:
    """
    Generate annual summary using YearlyState data directly.
    No reconstruction or recalculation.

    Args:
        result: ProjectionResult containing yearly states
        output_path: Path to save the CSV file
    """
    rows = []

    for yearly_state in result.yearly_states:
        # Calculate counts from components if available
        if yearly_state.annual_tax_components:
            components = yearly_state.annual_tax_components

            options_exercised = (
                sum(c.shares_exercised for c in components.iso_exercise_components) +
                sum(c.shares_exercised for c in components.nso_exercise_components)
            )

            shares_sold = sum(c.shares_sold for c in components.sale_components)
            shares_donated = sum(c.shares_donated for c in components.donation_components)

            # Calculate proceeds and gains from components
            sale_proceeds = sum(c.gross_proceeds for c in components.sale_components)
            capital_gains = components.short_term_capital_gains + components.long_term_capital_gains
        else:
            options_exercised = 0
            shares_sold = 0
            shares_donated = 0
            sale_proceeds = 0.0
            capital_gains = 0.0

        # Calculate cumulative outstanding from pledge state
        if yearly_state.pledge_state and yearly_state.pledge_state.obligations:
            cumulative_outstanding = yearly_state.pledge_state.total_shares_remaining
        else:
            cumulative_outstanding = 0

        # Get expiration metrics
        expired_options = sum(e.quantity for e in yearly_state.expiration_events)
        expired_opportunity_cost = sum(e.opportunity_cost for e in yearly_state.expiration_events)

        row = {
            # Income
            'year': yearly_state.year,
            'w2_income': yearly_state.income,
            'spouse_income': yearly_state.spouse_income,
            'other_income': getattr(yearly_state, 'other_income', 0.0),
            'total_income': (
                yearly_state.income +
                yearly_state.spouse_income +
                getattr(yearly_state, 'other_income', 0.0)
            ),

            # Actions
            'exercise_costs': yearly_state.exercise_costs,
            'sale_proceeds': sale_proceeds,
            'capital_gains': capital_gains,

            # Charitable
            'donations': yearly_state.donation_value,
            'company_match': yearly_state.company_match_received,
            'total_charitable_impact': yearly_state.donation_value + yearly_state.company_match_received,

            # Pledge tracking (year-specific values from YearlyState)
            'pledge_shares_obligated': yearly_state.pledge_shares_obligated_this_year,
            'pledge_shares_donated': yearly_state.pledge_shares_donated_this_year,
            'pledge_shares_outstanding': cumulative_outstanding,
            'pledge_shares_expired': yearly_state.pledge_shares_expired_this_year,

            # Share counts
            'options_exercised_count': options_exercised,
            'shares_sold_count': shares_sold,
            'shares_donated_count': shares_donated,
            'expired_option_count': expired_options,

            # Tax details (from actual progressive calculations)
            'regular_tax': yearly_state.tax_state.regular_tax,
            'amt_tax': yearly_state.tax_state.amt_tax,
            'total_tax': yearly_state.tax_state.total_tax,
            'amt_credits_generated': yearly_state.tax_state.amt_credits_generated,
            'amt_credits_consumed': yearly_state.tax_state.amt_credits_used,
            'amt_credits_balance': yearly_state.tax_state.amt_credits_remaining,

            # Wealth tracking
            'ending_cash': yearly_state.ending_cash,
            'equity_value': yearly_state.total_equity_value,
            'net_worth': yearly_state.ending_cash + yearly_state.total_equity_value,
            'expired_option_loss': expired_opportunity_cost
        }
        rows.append(row)

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if rows:
        # Round financial values to 2 decimal places
        non_financial_cols = {'year', 'options_exercised_count', 'shares_sold_count',
                             'shares_donated_count', 'expired_option_count',
                             'pledge_shares_obligated', 'pledge_shares_donated',
                             'pledge_shares_outstanding', 'pledge_shares_expired'}

        for row in rows:
            for key, value in row.items():
                if key not in non_financial_cols and isinstance(value, (int, float)):
                    row[key] = round(value, 2)

        # Get column names from first row
        fieldnames = list(rows[0].keys())

        # Write CSV
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        # Empty file with minimal headers
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['year'])
            writer.writeheader()


def generate_liquidity_events_csv(result: ProjectionResult, output_path: str) -> None:
    """
    Generate CSV tracking all liquidity events and their utilization.
    
    Includes tender offers, IPO, and secondary offerings with:
    - Event details (date, type, price)
    - Share activity (sales, proceeds)
    - Donation window tracking
    - Pledge obligations created
    
    Args:
        result: ProjectionResult containing user profile with liquidity events
        output_path: Path to save the CSV file
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    rows = []
    
    # Get liquidity events from user profile
    liquidity_events = result.user_profile.liquidity_events
    
    for event in liquidity_events:
        # Get pledge obligations for this event from final state
        final_state = result.get_final_state()
        event_obligations = []
        if final_state and final_state.pledge_state:
            event_obligations = final_state.pledge_state.get_obligations_for_event(event.event_id)
        
        # Calculate obligation totals
        total_shares_obligated = sum(o.shares_obligated for o in event_obligations)
        total_shares_fulfilled = sum(o.shares_fulfilled for o in event_obligations)
        total_shares_remaining = sum(o.shares_remaining for o in event_obligations)
        
        row = {
            'event_id': event.event_id,
            'event_date': event.event_date.isoformat(),
            'event_type': event.event_type,
            'price_per_share': round(event.price_per_share, 2),
            'shares_vested_at_event': event.shares_vested_at_event,
            'shares_sold': event.shares_sold,
            'net_proceeds': round(event.net_proceeds, 2),
            'cash_donated_from_event': round(event.cash_donated_from_event, 2),
            'match_window_opens': event.event_date.isoformat(),
            'match_window_closes': event.match_window_closes.isoformat(),
            'window_is_open': event.is_window_open(result.plan.end_date),
            'obligations_created': len(event_obligations),
            'shares_obligated': total_shares_obligated,
            'shares_fulfilled': total_shares_fulfilled,
            'shares_remaining': total_shares_remaining,
            'fulfillment_rate': round(total_shares_fulfilled / total_shares_obligated, 4) if total_shares_obligated > 0 else 0.0
        }
        rows.append(row)
    
    # Write CSV
    if rows:
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    else:
        # Empty file with headers
        with open(output_path, 'w', newline='') as f:
            fieldnames = ['event_id', 'event_date', 'event_type', 'price_per_share',
                         'shares_vested_at_event', 'shares_sold', 'net_proceeds',
                         'cash_donated_from_event', 'match_window_opens', 'match_window_closes',
                         'window_is_open', 'obligations_created', 'shares_obligated',
                         'shares_fulfilled', 'shares_remaining', 'fulfillment_rate']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()


def save_charitable_carryforward_csv(result: ProjectionResult, output_path: str) -> None:
    """
    Save charitable deduction carryforward tracking from CharitableDeductionResult.
    
    This version uses only the data from the annual tax calculator's CharitableDeductionResult.
    
    Args:
        result: ProjectionResult containing yearly states with charitable deduction results
        output_path: Path to save the CSV file
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    rows = []
    
    for state in result.yearly_states:
        # Get AGI and donation amounts from components
        if state.annual_tax_components:
            components = state.annual_tax_components
            agi = components.adjusted_gross_income
            
            # Calculate donation amounts
            cash_donations = sum(d.amount for d in components.cash_donation_components)
            stock_donations = sum(d.donation_value for d in components.donation_components)
        else:
            agi = state.income + state.spouse_income + getattr(state, 'other_income', 0.0)
            cash_donations = 0.0
            stock_donations = 0.0
            
        # Get charitable deduction results - these contain ALL the data we need
        federal_result = state.federal_charitable_deduction_result
        ca_result = state.ca_charitable_deduction_result
        
        if not federal_result or not ca_result:
            raise ValueError(
                f"Year {state.year}: CharitableDeductionResult not found in YearlyState."
            )
            
        # Build row using ONLY data from CharitableDeductionResult
        row = {
            'year': state.year,
            'agi': round(agi, 2),
            'cash_donations': round(cash_donations, 2),
            'stock_donations': round(stock_donations, 2),
            
            # Federal data - all from CharitableDeductionResult
            'federal_cash_used': round(federal_result.cash_deduction_used, 2),
            'federal_stock_used': round(federal_result.stock_deduction_used, 2),
            'federal_total_used': round(federal_result.total_deduction_used, 2),
            'federal_cash_carryforward': round(federal_result.cash_carryforward, 2),
            'federal_stock_carryforward': round(federal_result.stock_carryforward, 2),
            'federal_total_carryforward': round(federal_result.total_carryforward, 2),
            'federal_expired_cash': round(federal_result.expired_cash_carryforward, 2),
            'federal_expired_stock': round(federal_result.expired_carryforward, 2),
            
            # Federal breakdown
            'federal_cash_current_used': round(federal_result.cash_current_used, 2),
            'federal_cash_carryforward_used': round(federal_result.cash_carryforward_used, 2),
            'federal_stock_current_used': round(federal_result.stock_current_used, 2),
            'federal_stock_carryforward_used': round(federal_result.stock_carryforward_used, 2),
            
            # Federal carryforward by year - direct from result
            'federal_cash_cf_by_year': str(federal_result.cash_carryforward_remaining_by_creation_year),
            'federal_stock_cf_by_year': str(federal_result.carryforward_remaining_by_creation_year),
            'federal_stock_cf_consumed': str(federal_result.carryforward_consumed_by_creation_year),
            
            # CA data - all from CharitableDeductionResult
            'ca_cash_used': round(ca_result.cash_deduction_used, 2),
            'ca_stock_used': round(ca_result.stock_deduction_used, 2),
            'ca_total_used': round(ca_result.total_deduction_used, 2),
            'ca_cash_carryforward': round(ca_result.cash_carryforward, 2),
            'ca_stock_carryforward': round(ca_result.stock_carryforward, 2),
            'ca_total_carryforward': round(ca_result.total_carryforward, 2),
            'ca_expired_cash': round(ca_result.expired_cash_carryforward, 2),
            'ca_expired_stock': round(ca_result.expired_carryforward, 2),
            
            # CA breakdown
            'ca_cash_current_used': round(ca_result.cash_current_used, 2),
            'ca_cash_carryforward_used': round(ca_result.cash_carryforward_used, 2),
            'ca_stock_current_used': round(ca_result.stock_current_used, 2),
            'ca_stock_carryforward_used': round(ca_result.stock_carryforward_used, 2),
            
            # CA carryforward by year - direct from result
            'ca_cash_cf_by_year': str(ca_result.cash_carryforward_remaining_by_creation_year),
            'ca_stock_cf_by_year': str(ca_result.carryforward_remaining_by_creation_year),
            'ca_stock_cf_consumed': str(ca_result.carryforward_consumed_by_creation_year),
        }
        
        rows.append(row)
    
    # Write to CSV
    if rows:
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def generate_pledge_obligations_csv(result: ProjectionResult, output_path: str) -> None:
    """
    Generate detailed CSV of all pledge obligations and their fulfillment status.
    
    Shows each individual obligation with:
    - Source event and type
    - Creation date
    - Shares obligated/fulfilled/remaining
    - Grant association
    - Fulfillment status
    
    Args:
        result: ProjectionResult containing yearly states with pledge obligations
        output_path: Path to save the CSV file
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    rows = []
    
    # Get final state for cumulative obligations
    final_state = result.get_final_state()
    if not final_state or not final_state.pledge_state:
        # Write empty file with headers
        with open(output_path, 'w', newline='') as f:
            fieldnames = ['source_event_id', 'obligation_type', 'creation_date',
                         'grant_id', 'pledge_percentage', 'match_ratio',
                         'shares_obligated', 'shares_fulfilled', 'shares_remaining',
                         'fulfillment_percentage', 'is_fulfilled']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return
    
    # Process each obligation
    for obligation in final_state.pledge_state.obligations:
        row = {
            'source_event_id': obligation.source_event_id,
            'obligation_type': obligation.obligation_type,
            'creation_date': obligation.creation_date.isoformat(),
            'grant_id': obligation.grant_id or '',
            'pledge_percentage': round(obligation.pledge_percentage, 4),
            'match_ratio': obligation.match_ratio,
            'shares_obligated': obligation.shares_obligated,
            'shares_fulfilled': obligation.shares_fulfilled,
            'shares_remaining': obligation.shares_remaining,
            'fulfillment_percentage': round(obligation.fulfillment_percentage, 4),
            'is_fulfilled': obligation.is_fulfilled
        }
        rows.append(row)
    
    # Write CSV
    if rows:
        # Sort by creation date
        rows.sort(key=lambda r: r['creation_date'])
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def save_comprehensive_cashflow_csv(result: ProjectionResult, output_path: str) -> None:
    """Save comprehensive cash flow tracking with all income sources, expenses, and balances."""
    rows = []

    for i, state in enumerate(result.yearly_states):
        # Get starting values
        starting_cash = state.starting_cash
        starting_investments = state.investment_balance if i == 0 else result.yearly_states[i-1].investment_balance

        # Income breakdown
        w2_income = state.income
        spouse_income = state.spouse_income
        other_income = state.other_income
        interest_income = result.user_profile.interest_income
        dividend_income = result.user_profile.dividend_income
        bonus_income = result.user_profile.bonus_expected
        investment_growth = starting_investments * result.user_profile.investment_return_rate
        total_income = (w2_income + spouse_income + other_income + interest_income +
                       dividend_income + bonus_income + investment_growth)

        # Cash inflows
        sale_proceeds = sum(
            comp.gross_proceeds
            for comp in state.annual_tax_components.sale_components
        ) if state.annual_tax_components else 0
        company_match_received = state.company_match_received

        # Cash outflows
        exercise_costs = state.exercise_costs
        living_expenses = state.living_expenses
        gross_tax = state.gross_tax
        tax_withholdings = state.tax_withholdings
        net_tax_payment = max(0, gross_tax - tax_withholdings)
        donation_value = state.donation_value

        # Net cash flow (company match goes directly to DAF, not user cash)
        net_cash_flow = (total_income + sale_proceeds - exercise_costs -
                        living_expenses - net_tax_payment)

        # Ending balances
        ending_cash = state.ending_cash
        static_investments = result.user_profile.crypto  # Static crypto balance from profile
        ending_investments = state.investment_balance
        ending_equity_value = state.total_equity_value

        # Other investments (crypto + real estate + other non-equity assets)
        crypto_balance = getattr(result.user_profile, 'crypto', 0)
        real_estate_equity = getattr(result.user_profile, 'real_estate_equity', 0)
        other_investments = crypto_balance + real_estate_equity

        total_net_worth = ending_cash + static_investments + ending_investments + ending_equity_value

        row = {
            'year': state.year,
            # Starting balances
            'starting_cash': round(starting_cash, 2),
            'starting_investments': round(starting_investments, 2),
            # Income sources
            'w2_income': round(w2_income, 2),
            'spouse_income': round(spouse_income, 2),
            'bonus_income': round(bonus_income, 2),
            'interest_income': round(interest_income, 2),
            'dividend_income': round(dividend_income, 2),
            'other_income': round(other_income, 2),
            'investment_growth': round(investment_growth, 2),
            'total_income': round(total_income, 2),
            # Cash inflows
            'sale_proceeds': round(sale_proceeds, 2),
            'company_match_received': round(company_match_received, 2),
            # Cash outflows
            'exercise_costs': round(exercise_costs, 2),
            'living_expenses': round(living_expenses, 2),
            'gross_tax': round(gross_tax, 2),
            'tax_withholdings': round(tax_withholdings, 2),
            'net_tax_payment': round(net_tax_payment, 2),
            'donation_value': round(donation_value, 2),
            # Net flows
            'net_cash_flow': round(net_cash_flow, 2),
            # Ending balances
            'ending_cash': round(ending_cash, 2),
            'ending_investments': round(ending_investments, 2),
            'static_investments': round(static_investments, 2),
            'other_investments': round(other_investments, 2),
            'ending_equity_value': round(ending_equity_value, 2),
            'total_net_worth': round(total_net_worth, 2),
            # Tax details
            'amt_credits_used': round(state.tax_state.amt_credits_used, 2),
            'amt_credits_remaining': round(state.tax_state.amt_credits_remaining, 2),
        }
        rows.append(row)

    # Write CSV
    if rows:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fieldnames = list(rows[0].keys())
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


