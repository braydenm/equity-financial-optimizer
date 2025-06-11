"""
CSV output functionality for projection calculator results.

This module provides functions to save projection results to CSV files
for analysis and comparison.
"""

import csv
import os
from typing import List, Dict, Any
from projections.projection_state import ProjectionResult, YearlyState, LifecycleState


def save_yearly_cashflow_csv(result: ProjectionResult, output_path: str) -> None:
    """Save yearly cash flow data to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        fieldnames = ['year', 'starting_cash', 'income', 'exercise_costs', 'tax_paid', 'donation_value', 'ending_cash']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for state in result.yearly_states:
            writer.writerow({
                'year': state.year,
                'starting_cash': round(state.starting_cash, 2),
                'income': round(state.income, 2),
                'exercise_costs': round(state.exercise_costs, 2),
                'tax_paid': round(state.tax_paid, 2),
                'donation_value': round(state.donation_value, 2),
                'ending_cash': round(state.ending_cash, 2)
            })


def save_tax_timeline_csv(result: ProjectionResult, output_path: str) -> None:
    """Save tax timeline data to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        fieldnames = ['year', 'regular_tax', 'amt_tax', 'total_tax', 'amt_credits_generated', 'amt_credits_used', 'charitable_deduction']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for state in result.yearly_states:
            writer.writerow({
                'year': state.year,
                'regular_tax': round(state.tax_state.regular_tax, 2),
                'amt_tax': round(state.tax_state.amt_tax, 2),
                'total_tax': round(state.tax_state.total_tax, 2),
                'amt_credits_generated': round(state.tax_state.amt_credits_generated, 2),
                'amt_credits_used': round(state.tax_state.amt_credits_used, 2),
                'charitable_deduction': round(state.charitable_state.current_year_deduction, 2)
            })


def save_summary_csv(result: ProjectionResult, output_path: str) -> None:
    """Save summary metrics to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        fieldnames = ['total_cash_final', 'total_taxes_all_years', 'total_donations_all_years',
                     'total_equity_value_final', 'pledge_fulfillment_maximalist', 'pledge_fulfillment_minimalist',
                     'outstanding_obligation']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        metrics = result.summary_metrics
        writer.writerow({
            'total_cash_final': round(metrics.get('total_cash_final', 0), 2),
            'total_taxes_all_years': round(metrics.get('total_taxes_all_years', 0), 2),
            'total_donations_all_years': round(metrics.get('total_donations_all_years', 0), 2),
            'total_equity_value_final': round(metrics.get('total_equity_value_final', 0), 2),
            'pledge_fulfillment_maximalist': round(metrics.get('pledge_fulfillment_maximalist', 0), 4),
            'pledge_fulfillment_minimalist': round(metrics.get('pledge_fulfillment_minimalist', 0), 4),
            'outstanding_obligation': round(metrics.get('outstanding_obligation', 0), 2)
        })


def save_equity_holdings_csv(result: ProjectionResult, output_path: str) -> None:
    """Save final equity holdings to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    final_state = result.get_final_state()
    if not final_state:
        return

    with open(output_path, 'w', newline='') as f:
        fieldnames = ['lot_id', 'share_type', 'quantity', 'strike_price', 'lifecycle_state', 'tax_treatment']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for lot in final_state.equity_holdings:
            writer.writerow({
                'lot_id': lot.lot_id,
                'share_type': lot.share_type.value,
                'quantity': lot.quantity,
                'strike_price': round(lot.strike_price, 2),
                'lifecycle_state': lot.lifecycle_state.value,
                'tax_treatment': lot.tax_treatment.value
            })


def save_state_timeline_csv(result: ProjectionResult, output_path: str) -> None:
    """Save state timeline showing share quantities in each state over time."""
    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    # Collect all unique lot IDs across all years, including from disposal tracking
    all_lot_ids = set()
    for state in result.yearly_states:
        for lot in state.equity_holdings:
            all_lot_ids.add(lot.lot_id)
        # Also include lots that may have been fully disposed
        all_lot_ids.update(state.shares_sold.keys())
        all_lot_ids.update(state.shares_donated.keys())

    # Sort lot IDs for consistent output
    sorted_lot_ids = sorted(all_lot_ids)

    # Define states to track
    states = ['Granted', 'Vested', 'Exercised', 'Disposed_Sold', 'Disposed_Donated', 'Expired', 'TOTAL']

    # Prepare fieldnames: Lot_ID, State, then one column per year
    years = [str(state.year) for state in result.yearly_states]
    fieldnames = ['Lot_ID', 'State'] + years

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # For each lot and state, track quantities across years
        for lot_id in sorted_lot_ids:
            for state_name in states:
                row = {'Lot_ID': lot_id, 'State': state_name}

                for yearly_state in result.yearly_states:
                    year = str(yearly_state.year)
                    quantity = 0

                    # Find this lot in the yearly state
                    lot = next((l for l in yearly_state.equity_holdings if l.lot_id == lot_id), None)

                    if state_name == 'Granted':
                        # Granted shares are those not yet vested
                        if lot and lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                            quantity = lot.quantity
                    elif state_name == 'Vested':
                        # Vested but unexercised
                        if lot and lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED:
                            quantity = lot.quantity
                    elif state_name == 'Exercised':
                        # Exercised and held
                        if lot and lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED:
                            quantity = lot.quantity
                    elif state_name == 'Disposed_Sold':
                        # Track cumulative sales from disposal tracking
                        quantity = yearly_state.shares_sold.get(lot_id, 0)
                    elif state_name == 'Disposed_Donated':
                        # Track cumulative donations from disposal tracking
                        quantity = yearly_state.shares_donated.get(lot_id, 0)
                    elif state_name == 'Expired':
                        # Check if past expiration date
                        # For now, mark as 0 - this would need expiration date tracking
                        quantity = 0
                    elif state_name == 'TOTAL':
                        # Total is the sum of all states for this lot
                        # Current holdings + disposed shares
                        current_quantity = lot.quantity if lot else 0
                        sold_quantity = yearly_state.shares_sold.get(lot_id, 0)
                        donated_quantity = yearly_state.shares_donated.get(lot_id, 0)
                        quantity = current_quantity + sold_quantity + donated_quantity

                    row[year] = quantity

                writer.writerow(row)


def save_transition_timeline_csv(result: ProjectionResult, output_path: str) -> None:
    """Save state transition timeline showing share movements between states."""
    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    # Collect all unique lot IDs including from disposal tracking
    all_lot_ids = set()
    for state in result.yearly_states:
        for lot in state.equity_holdings:
            all_lot_ids.add(lot.lot_id)
        # Also include lots that may have been fully disposed
        all_lot_ids.update(state.shares_sold.keys())
        all_lot_ids.update(state.shares_donated.keys())

    sorted_lot_ids = sorted(all_lot_ids)

    # Define transitions to track
    transitions = ['Granting', 'Vesting', 'Exercising', 'Selling', 'Donating', 'Expiring']

    # Prepare fieldnames
    years = [str(state.year) for state in result.yearly_states]
    fieldnames = ['Lot_ID', 'Transition'] + years

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # For each lot and transition type
        for lot_id in sorted_lot_ids:
            for transition in transitions:
                row = {'Lot_ID': lot_id, 'Transition': transition}

                # For each year, calculate transitions
                for i, yearly_state in enumerate(result.yearly_states):
                    year = str(yearly_state.year)
                    quantity = 0

                    if i == 0:
                        # First year - compare with initial state
                        # For the first year, we need to check against the original plan's initial lots
                        # and also check for any sales/donations that happened in year 1
                        curr_lot = next((l for l in yearly_state.equity_holdings if l.lot_id == lot_id), None)

                        # Check for sales/donations in first year
                        if transition == 'Selling':
                            quantity = yearly_state.shares_sold.get(lot_id, 0)
                        elif transition == 'Donating':
                            quantity = yearly_state.shares_donated.get(lot_id, 0)
                        elif curr_lot:
                            if transition == 'Granting' and curr_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                                quantity = curr_lot.quantity
                            elif transition == 'Vesting' and curr_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED:
                                quantity = curr_lot.quantity
                            elif transition == 'Exercising' and curr_lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED:
                                # Check if this is a new exercise lot (contains _EX_)
                                if '_EX_' in lot_id:
                                    quantity = curr_lot.quantity
                    else:
                        # Compare with previous year to detect transitions
                        prev_state = result.yearly_states[i-1]
                        curr_lot = next((l for l in yearly_state.equity_holdings if l.lot_id == lot_id), None)
                        prev_lot = next((l for l in prev_state.equity_holdings if l.lot_id == lot_id), None)

                        # Detect transitions based on lifecycle state changes
                        if curr_lot and prev_lot:
                            if (transition == 'Vesting' and
                                prev_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED and
                                curr_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED):
                                quantity = curr_lot.quantity
                            elif (transition == 'Exercising' and
                                  prev_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED):
                                # When exercising, the vested lot quantity decreases
                                quantity = -(prev_lot.quantity - (curr_lot.quantity if curr_lot else 0))
                        elif curr_lot and not prev_lot:
                            # New lot appeared
                            if transition == 'Granting' and curr_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                                quantity = curr_lot.quantity
                            elif transition == 'Vesting' and curr_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED:
                                quantity = curr_lot.quantity
                            elif transition == 'Exercising' and '_EX_' in lot_id:
                                # New exercise lot created
                                quantity = curr_lot.quantity

                        # Track disposals using year-over-year changes
                        if transition == 'Selling':
                            prev_sold = prev_state.shares_sold.get(lot_id, 0)
                            curr_sold = yearly_state.shares_sold.get(lot_id, 0)
                            quantity = curr_sold - prev_sold
                        elif transition == 'Donating':
                            prev_donated = prev_state.shares_donated.get(lot_id, 0)
                            curr_donated = yearly_state.shares_donated.get(lot_id, 0)
                            quantity = curr_donated - prev_donated

                    row[year] = quantity

                writer.writerow(row)


def save_all_projection_csvs(result: ProjectionResult, scenario_name: str, output_dir: str = "output") -> None:
    """Save all projection CSVs for a scenario."""
    base_name = scenario_name.lower().replace(' ', '_').replace('-', '_')

    save_yearly_cashflow_csv(result, f"{output_dir}/{base_name}_yearly_cashflow.csv")
    save_tax_timeline_csv(result, f"{output_dir}/{base_name}_tax_timeline.csv")
    save_summary_csv(result, f"{output_dir}/{base_name}_summary.csv")
    save_equity_holdings_csv(result, f"{output_dir}/{base_name}_equity_holdings.csv")
    save_state_timeline_csv(result, f"{output_dir}/{base_name}_state_timeline.csv")
    save_transition_timeline_csv(result, f"{output_dir}/{base_name}_transition_timeline.csv")


def create_comparison_csv(results: List[ProjectionResult], output_path: str) -> None:
    """Create comparison CSV across multiple scenarios."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        fieldnames = ['scenario', 'total_cash_final', 'total_taxes_all_years', 'total_donations_all_years',
                     'total_equity_value_final', 'pledge_fulfillment_maximalist', 'outstanding_obligation']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            metrics = result.summary_metrics
            writer.writerow({
                'scenario': result.plan.name,
                'total_cash_final': round(metrics.get('total_cash_final', 0), 2),
                'total_taxes_all_years': round(metrics.get('total_taxes_all_years', 0), 2),
                'total_donations_all_years': round(metrics.get('total_donations_all_years', 0), 2),
                'total_equity_value_final': round(metrics.get('total_equity_value_final', 0), 2),
                'pledge_fulfillment_maximalist': round(metrics.get('pledge_fulfillment_maximalist', 0), 4),
                'outstanding_obligation': round(metrics.get('outstanding_obligation', 0), 2)
            })
