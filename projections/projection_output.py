"""
CSV output functionality for projection calculator results.

This module provides functions to save projection results to CSV files
for analysis and comparison.
"""

import csv
import os
from datetime import date
from typing import List, Dict, Any
from projections.projection_state import ProjectionResult, YearlyState, LifecycleState, ShareType
from projections.csv_generators import (
    save_components_csv, 
    save_annual_summary_csv, 
    save_charitable_carryforward_csv,
    save_comprehensive_cashflow_csv
)

# Import tax constants for charitable deduction limits
from calculators.tax_constants import (
    FEDERAL_CHARITABLE_AGI_LIMITS,
    CALIFORNIA_CHARITABLE_AGI_LIMITS,
    FEDERAL_CHARITABLE_BASIS_ELECTION_AGI_LIMITS,
    CALIFORNIA_CHARITABLE_BASIS_ELECTION_AGI_LIMITS
)




def save_annual_tax_detail_csv(result: ProjectionResult, output_path: str) -> None:
    """Save detailed annual tax breakdown to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        fieldnames = [
            'year', 'w2_income', 'spouse_income', 'nso_ordinary_income',
            'short_term_gains', 'long_term_gains', 'iso_bargain_element',
            'federal_regular_tax', 'federal_amt_tax', 'ca_regular_tax', 'ca_amt_tax', 'total_tax_combined',
            'federal_tax_regime', 'federal_amt_credits_generated', 'federal_amt_credits_used', 'amt_credits_remaining',
            'charitable_deduction_cash', 'charitable_deduction_stock', 'charitable_deduction_total'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for state in result.yearly_states:
            # Extract component details from annual tax components
            nso_ordinary = 0
            stcg = 0
            ltcg = 0
            iso_bargain = 0
            charitable_cash = 0
            charitable_stock = 0

            if state.annual_tax_components:
                # Extract from NSO exercises
                nso_ordinary = sum(getattr(e, 'bargain_element', 0) for e in state.annual_tax_components.nso_exercise_components)

                # Extract from sales
                for sale in state.annual_tax_components.sale_components:
                    stcg += getattr(sale, 'short_term_gain', 0)
                    ltcg += getattr(sale, 'long_term_gain', 0)
                    nso_ordinary += getattr(sale, 'ordinary_income', 0)  # From disqualifying dispositions

                # Extract from ISO exercises
                iso_bargain = sum(getattr(e, 'bargain_element', 0) for e in state.annual_tax_components.iso_exercise_components)

                # Extract charitable deductions
                charitable_cash = getattr(state.annual_tax_components, 'charitable_deductions_cash', 0)
                charitable_stock = getattr(state.annual_tax_components, 'charitable_deductions_stock', 0)

            # Determine which tax regime applies
            federal_tax_regime = 'AMT' if state.tax_state.federal_amt_tax > state.tax_state.federal_regular_tax else 'Regular'

            writer.writerow({
                'year': state.year,
                'w2_income': round(result.user_profile.annual_w2_income if result.user_profile else state.income, 2),
                'spouse_income': round(result.user_profile.spouse_w2_income if result.user_profile else state.spouse_income, 2),
                'nso_ordinary_income': round(nso_ordinary, 2),
                'short_term_gains': round(stcg, 2),
                'long_term_gains': round(ltcg, 2),
                'iso_bargain_element': round(iso_bargain, 2),
                'federal_regular_tax': round(state.tax_state.federal_regular_tax, 2),
                'federal_amt_tax': round(state.tax_state.federal_amt_tax, 2),
                'ca_regular_tax': round(state.tax_state.ca_regular_tax, 2),
                'ca_amt_tax': round(state.tax_state.ca_amt_tax, 2),
                'total_tax_combined': round(state.tax_state.total_tax, 2),
                'federal_tax_regime': federal_tax_regime,
                'federal_amt_credits_generated': round(state.tax_state.amt_credits_generated, 2),
                'federal_amt_credits_used': round(state.tax_state.amt_credits_used, 2),
                'amt_credits_remaining': round(state.tax_state.amt_credits_remaining, 2),
                'charitable_deduction_cash': round(charitable_cash, 2),
                'charitable_deduction_stock': round(charitable_stock, 2),
                'charitable_deduction_total': round(
                    state.federal_charitable_deduction_result.total_deduction_used 
                    if state.federal_charitable_deduction_result else 0, 2
                )
            })






def save_state_timeline_csv(result: ProjectionResult, output_path: str) -> None:
    """Save state timeline showing share quantities in each state over time."""
    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    # Helper function to create group total rows
    def _create_group_total_row(group_lots: List[str], yearly_states: List[YearlyState], years: List[str]) -> Dict[str, Any]:
        """Create a TOTAL row for a group of related lots."""
        base_id = group_lots[0].replace('VESTED_', '').split('_EX_')[0]
        display_base_id = base_id

        row = {'Lot_ID': f'{display_base_id}_GROUP', 'State': 'TOTAL'}

        for year in years:
            yearly_state = next((s for s in yearly_states if str(s.year) == year), None)
            if yearly_state:
                total = 0
                for lot_id in group_lots:
                    # Find lot quantity
                    lot = next((l for l in yearly_state.equity_holdings if l.lot_id == lot_id), None)
                    if lot:
                        total += lot.quantity
                    # Add disposed quantities
                    total += yearly_state.shares_sold.get(lot_id, 0)
                    total += yearly_state.shares_donated.get(lot_id, 0)
                row[year] = total
            else:
                row[year] = 0

        return row

    # Collect all unique lot IDs across all years, including from disposal tracking
    all_lot_ids = set()
    for state in result.yearly_states:
        for lot in state.equity_holdings:
            all_lot_ids.add(lot.lot_id)
        # Also include lots that may have been fully disposed
        all_lot_ids.update(state.shares_sold.keys())
        all_lot_ids.update(state.shares_donated.keys())

    # Also include initial lots to catch granted shares
    if result.plan and hasattr(result.plan, 'initial_lots'):
        for lot in result.plan.initial_lots:
            all_lot_ids.add(lot.lot_id)

    # Sort lot IDs for consistent output, grouping related lots
    def lot_sort_key(lot_id):
        # Group ISO/NSO lots with their exercised versions
        base_id = lot_id.replace('VESTED_', '').split('_EX_')[0]
        is_exercised = '_EX_' in lot_id
        return (base_id, is_exercised, lot_id)

    sorted_lot_ids = sorted(all_lot_ids, key=lot_sort_key)

    # Define states to track
    states = ['Granted', 'Vested', 'Exercised', 'Disposed_Sold', 'Disposed_Donated', 'Expired']

    # Prepare fieldnames: Lot_ID, State, then one column per year
    years = [str(state.year) for state in result.yearly_states]
    fieldnames = ['Lot_ID', 'State'] + years

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Track when we need to add group totals
        last_base_id = None
        group_lots = []

        # For each lot and state, track quantities across years
        for lot_id in sorted_lot_ids:
            # Use lot_id directly since upstream naming is now consistent
            display_lot_id = lot_id

            # Check if we're starting a new group
            base_id = lot_id.replace('VESTED_', '').split('_EX_')[0]
            if base_id != last_base_id and last_base_id is not None and group_lots:
                # Write group total for previous group
                if len(group_lots) > 1 or '_EX_' in group_lots[0]:
                    writer.writerow(_create_group_total_row(group_lots, result.yearly_states, years))
                group_lots = []

            last_base_id = base_id
            group_lots.append(lot_id)

            # Skip TOTAL rows for parent lots (ISO, NSO) that have no quantity
            has_quantity = False
            for yearly_state in result.yearly_states:
                lot = next((l for l in yearly_state.equity_holdings if l.lot_id == lot_id), None)
                if lot and lot.quantity > 0:
                    has_quantity = True
                    break

            if not '_EX_' in lot_id and not has_quantity:
                # For parent lots with no shares, only show states, no TOTAL
                state_list = states
            else:
                # For lots with shares or exercised lots, show states plus SUBTOTAL
                state_list = states + ['SUBTOTAL']

            for state_name in state_list:
                row = {'Lot_ID': display_lot_id, 'State': state_name}

                for yearly_state in result.yearly_states:
                    year = str(yearly_state.year)
                    quantity = 0

                    # Find this lot in the yearly state
                    lot = next((l for l in yearly_state.equity_holdings if l.lot_id == lot_id), None)

                    if state_name == 'Granted':
                        # Granted shares are those not yet vested
                        if lot and lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                            quantity = lot.quantity
                        # Also check for lots that will vest in the future based on ID
                        elif lot_id.startswith('VEST_') and lot and lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
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
                        # Track shares that have expired
                        if lot and lot.lifecycle_state == LifecycleState.EXPIRED:
                            quantity = lot.quantity
                    elif state_name == 'SUBTOTAL':
                        # Subtotal is the sum of all states for this lot
                        # Current holdings + disposed shares
                        current_quantity = lot.quantity if lot else 0
                        sold_quantity = yearly_state.shares_sold.get(lot_id, 0)
                        donated_quantity = yearly_state.shares_donated.get(lot_id, 0)
                        quantity = current_quantity + sold_quantity + donated_quantity

                    row[year] = quantity

                writer.writerow(row)

        # Write final group total if needed
        if group_lots and (len(group_lots) > 1 or '_EX_' in group_lots[0]):
            writer.writerow(_create_group_total_row(group_lots, result.yearly_states, years))


def generate_holding_milestones_csv(result: ProjectionResult, output_path: str) -> None:
    """Generate comprehensive milestone tracking for all equity lots based on current state."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    final_state = result.get_final_state()
    if not final_state:
        return

    # Get assumed IPO date from user profile
    assumed_ipo = None
    if result.user_profile and hasattr(result.user_profile, 'assumed_ipo'):
        assumed_ipo = result.user_profile.assumed_ipo #No silent fallback
    if not assumed_ipo:
        assumed_ipo = date(2040, 1, 1)  # Default fallback



    with open(output_path, 'w', newline='') as f:
        fieldnames = [
            'lot_id', 'current_quantity', 'lifecycle_state', 'share_type',
            'grant_date', 'exercise_date', 'exercise_date',
            'milestone_type', 'milestone_date', 'milestone_description'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Collect all milestone entries for sorting
        all_milestones = []

        # Process all current holdings
        for lot in final_state.equity_holdings:
            if lot.lifecycle_state == LifecycleState.EXPIRED:
                continue

            milestones = []

            # Calculate milestones based on lifecycle state
            if lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                # Option expiration date
                if hasattr(lot, 'expiration_date') and lot.expiration_date:
                    milestones.append({
                        'type': 'option_expiration',
                        'date': lot.expiration_date,
                        'description': 'Option expires - exercise before this date'
                    })

            elif lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED:
                # Option expiration date
                if hasattr(lot, 'expiration_date') and lot.expiration_date:
                    milestones.append({
                        'type': 'option_expiration',
                        'date': lot.expiration_date,
                        'description': 'Option expires - exercise before this date'
                    })

                # IPO pledge deadline (assumed_ipo + 12 months)
                try:
                    ipo_pledge_deadline = date(assumed_ipo.year + 1, assumed_ipo.month, assumed_ipo.day)
                except ValueError:
                    ipo_pledge_deadline = date(assumed_ipo.year + 1, assumed_ipo.month, 28)
                milestones.append({
                    'type': 'ipo_pledge_deadline',
                    'date': ipo_pledge_deadline,
                    'description': 'IPO pledge window closes - donate before this date for company match'
                })

            elif lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED:
                # LTCG date (exercise_date + 1 year)
                if hasattr(lot, 'exercise_date') and lot.exercise_date:
                    try:
                        ltcg_date = date(lot.exercise_date.year + 1, lot.exercise_date.month, lot.exercise_date.day)
                    except ValueError:
                        ltcg_date = date(lot.exercise_date.year + 1, lot.exercise_date.month, 28)

                    milestones.append({
                        'type': 'ltcg_eligible',
                        'date': ltcg_date,
                        'description': 'Long-term capital gains treatment begins'
                    })

                # IPO pledge deadline
                try:
                    ipo_pledge_deadline = date(assumed_ipo.year + 1, assumed_ipo.month, assumed_ipo.day)
                except ValueError:
                    ipo_pledge_deadline = date(assumed_ipo.year + 1, assumed_ipo.month, 28)
                milestones.append({
                    'type': 'ipo_pledge_deadline',
                    'date': ipo_pledge_deadline,
                    'description': 'IPO pledge window closes - donate before this date for company match'
                })

            # ISO-specific qualifying disposition date
            if lot.share_type.value == 'ISO' and hasattr(lot, 'grant_date') and hasattr(lot, 'exercise_date'):
                if lot.grant_date and lot.exercise_date:
                    # max(grant_date + 2 years, exercise_date + 1 year)
                    try:
                        two_years_from_grant = date(lot.grant_date.year + 2, lot.grant_date.month, lot.grant_date.day)
                    except ValueError:
                        two_years_from_grant = date(lot.grant_date.year + 2, lot.grant_date.month, 28)

                    try:
                        one_year_from_exercise = date(lot.exercise_date.year + 1, lot.exercise_date.month, lot.exercise_date.day)
                    except ValueError:
                        one_year_from_exercise = date(lot.exercise_date.year + 1, lot.exercise_date.month, 28)

                    qualifying_date = max(two_years_from_grant, one_year_from_exercise)
                    milestones.append({
                        'type': 'iso_qualifying_disposition',
                        'date': qualifying_date,
                        'description': 'ISO qualifying disposition eligibility begins'
                    })

            # Determine acquisition date
            exercise_date = None
            if hasattr(lot, 'exercise_date') and lot.exercise_date:
                exercise_date = lot.exercise_date

            # Collect milestones for this lot
            for milestone in milestones:
                all_milestones.append({
                    'lot_id': lot.lot_id,
                    'current_quantity': lot.quantity,
                    'lifecycle_state': lot.lifecycle_state.value,
                    'share_type': lot.share_type.value,
                    'grant_date': lot.grant_date.isoformat() if hasattr(lot, 'grant_date') and lot.grant_date else '',
                    'exercise_date': exercise_date.isoformat() if exercise_date else '',
                    'milestone_type': milestone['type'],
                    'milestone_date': milestone['date'].isoformat(),
                    'milestone_description': milestone['description']
                })

        # Process disposed lots for additional milestones
        # Build a map of actual sale dates from planned actions
        sale_dates = {}
        if result.plan and hasattr(result.plan, 'planned_actions'):
            for action in result.plan.planned_actions:
                if action.action_type.value == 'SELL':
                    sale_dates[action.lot_id] = action.action_date

        # Track pledge obligations with FIFO donation application
        # Build chronological list of sales and donations
        pledge_events = []

        for year_state in result.yearly_states:
            # Add sales (create pledge obligations)
            for lot_id, shares_sold in year_state.shares_sold.items():
                if shares_sold > 0:
                    sale_date = sale_dates.get(lot_id, date(year_state.year, 3, 1))
                    pledge_events.append({
                        'type': 'sale',
                        'date': sale_date,
                        'lot_id': lot_id,
                        'shares': shares_sold,
                        'year': year_state.year
                    })

            # Add donations (reduce pledge obligations)
            for lot_id, shares_donated in year_state.shares_donated.items():
                if shares_donated > 0:
                    # Use actual donation date from planned actions, fallback to mid-year
                    donation_date = date(year_state.year, 6, 15)  # Mid-year fallback
                    if result.plan and hasattr(result.plan, 'planned_actions'):
                        for action in result.plan.planned_actions:
                            if (action.action_type.value == 'DONATE' and
                                action.lot_id == lot_id and
                                action.action_date.year == year_state.year):
                                donation_date = action.action_date
                                break

                    pledge_events.append({
                        'type': 'donation',
                        'date': donation_date,
                        'lot_id': lot_id,
                        'shares': shares_donated,
                        'year': year_state.year
                    })

        # Sort events chronologically
        pledge_events.sort(key=lambda x: x['date'])

        # Apply FIFO logic: donations discharge earliest sales first
        outstanding_sales = []  # List of {'lot_id': str, 'shares': int, 'date': date, 'year': int}

        for event in pledge_events:
            if event['type'] == 'sale':
                outstanding_sales.append({
                    'lot_id': event['lot_id'],
                    'shares': event['shares'],
                    'date': event['date'],
                    'year': event['year']
                })
            elif event['type'] == 'donation':
                # Apply donation to outstanding sales FIFO
                shares_to_apply = event['shares']
                remaining_sales = []

                for sale in outstanding_sales:
                    if shares_to_apply <= 0:
                        remaining_sales.append(sale)
                    elif sale['shares'] <= shares_to_apply:
                        # This sale is fully discharged
                        shares_to_apply -= sale['shares']
                    else:
                        # This sale is partially discharged
                        remaining_sales.append({
                            'lot_id': sale['lot_id'],
                            'shares': sale['shares'] - shares_to_apply,
                            'date': sale['date'],
                            'year': sale['year']
                        })
                        shares_to_apply = 0

                outstanding_sales = remaining_sales

        # Generate pledge window expiry entries only for outstanding sales
        for sale in outstanding_sales:
            # Calculate pledge window expiry (sale_date + 36 months, but max IPO + 12 months)
            try:
                sale_plus_36_months = date(sale['date'].year + 3, sale['date'].month, sale['date'].day)
            except ValueError:
                sale_plus_36_months = date(sale['date'].year + 3, sale['date'].month, 28)

            try:
                ipo_plus_12_months = date(assumed_ipo.year + 1, assumed_ipo.month, assumed_ipo.day)
            except ValueError:
                ipo_plus_12_months = date(assumed_ipo.year + 1, assumed_ipo.month, 28)
            pledge_window_expiry = min(sale_plus_36_months, ipo_plus_12_months)

            all_milestones.append({
                'lot_id': sale['lot_id'],
                'current_quantity': 0,
                'lifecycle_state': 'DISPOSED_SOLD',
                'share_type': '',
                'grant_date': '',
                'exercise_date': '',
                'exercise_date': '',
                'milestone_type': 'pledge_window_expiry',
                'milestone_date': pledge_window_expiry.isoformat(),
                'milestone_description': f'Pledge window expires for {sale["shares"]} outstanding shares from sale on {sale["date"].isoformat()}'
            })

        # Generate IPO pledge obligation for remaining total pledge amount
        if assumed_ipo and result.user_profile:

            # Calculate total pledge amount from grants' charitable programs
            total_shares = 0
            total_pledge_shares = 0

            # Get pledge amounts from all grants with charitable programs

            if hasattr(result.user_profile, 'grants') and result.user_profile.grants:
                for grant in result.user_profile.grants:
                    # Handle both total_shares and total_options attributes (from dict)
                    grant_shares = 0
                    if 'total_options' in grant:
                        grant_shares = grant['total_options']

                    if grant_shares > 0 and 'charitable_program' in grant:
                        pledge_percentage = grant['charitable_program'].get('pledge_percentage', 0.0)

                        total_shares += grant_shares
                        total_pledge_shares += int(grant_shares * pledge_percentage)

            if total_pledge_shares > 0:

                # Calculate total donations made across all years
                total_donated_shares = 0
                for year_state in result.yearly_states:
                    for lot_id, shares_donated in year_state.shares_donated.items():
                        total_donated_shares += shares_donated

                # Calculate remaining pledge obligation
                remaining_pledge_shares = total_pledge_shares - total_donated_shares

                if remaining_pledge_shares > 0:
                    # IPO pledge deadline is 1 year after assumed IPO date
                    try:
                        ipo_pledge_deadline = date(assumed_ipo.year + 1, assumed_ipo.month, assumed_ipo.day)
                    except ValueError:
                        ipo_pledge_deadline = date(assumed_ipo.year + 1, assumed_ipo.month, 28)

                    # Calculate overall pledge percentage for display
                    overall_pledge_percentage = (total_pledge_shares / total_shares) * 100 if total_shares > 0 else 0

                    all_milestones.append({
                        'lot_id': 'TOTAL_PLEDGE',
                        'current_quantity': remaining_pledge_shares,
                        'lifecycle_state': 'PLEDGE_OBLIGATION',
                        'share_type': '',
                        'grant_date': '',
                        'exercise_date': '',
                        'exercise_date': '',
                        'milestone_type': 'ipo_pledge_obligation',
                        'milestone_date': ipo_pledge_deadline.isoformat(),
                        'milestone_description': f'Total pledge obligation due: {remaining_pledge_shares} shares ({overall_pledge_percentage:.0f}% of {total_shares} total shares, {total_donated_shares} already donated)'
                    })

        # Track donated lots for deduction expiry
        for year_state in result.yearly_states:
            for lot_id, shares_donated in year_state.shares_donated.items():
                if shares_donated > 0:
                    # Deduction expires 5 years after donation year
                    deduction_expiry = date(year_state.year + 5, 12, 31)

                    all_milestones.append({
                        'lot_id': lot_id,
                        'current_quantity': 0,
                        'lifecycle_state': 'DISPOSED_DONATED',
                        'share_type': '',
                        'grant_date': '',
                        'exercise_date': '',
                        'exercise_date': '',
                        'milestone_type': 'deduction_expiry',
                        'milestone_date': deduction_expiry.isoformat(),
                        'milestone_description': f'Charitable deduction expires for {shares_donated} shares donated in {year_state.year}'
                    })

        # Sort all milestones by milestone_date and write to CSV
        all_milestones.sort(key=lambda x: x['milestone_date'])
        for milestone_entry in all_milestones:
            writer.writerow(milestone_entry)


def save_holding_period_tracking_csv(result: ProjectionResult, output_path: str) -> None:
    """Legacy wrapper - use generate_holding_milestones_csv for new comprehensive tracking."""
    generate_holding_milestones_csv(result, output_path)








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
        # Include lots from vesting/expiration events
        for event in getattr(state, 'vesting_events', []):
            all_lot_ids.add(event.lot_id)
        for event in getattr(state, 'expiration_events', []):
            all_lot_ids.add(event.lot_id)

    # Also need to check initial lots from the plan to catch grants
    if result.plan and hasattr(result.plan, 'initial_lots'):
        for lot in result.plan.initial_lots:
            all_lot_ids.add(lot.lot_id)

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
            # Use lot_id directly since upstream naming is now consistent
            display_lot_id = lot_id

            for transition in transitions:
                row = {'Lot_ID': display_lot_id, 'Transition': transition}

                # For each year, calculate transitions
                for i, yearly_state in enumerate(result.yearly_states):
                    year = str(yearly_state.year)
                    quantity = 0

                    if i == 0:
                        # First year - need to detect initial grants and vests
                        curr_lot = next((l for l in yearly_state.equity_holdings if l.lot_id == lot_id), None)

                        # Check initial lots from plan
                        initial_lot = None
                        if result.plan and hasattr(result.plan, 'initial_lots'):
                            initial_lot = next((l for l in result.plan.initial_lots if l.lot_id == lot_id), None)

                        # Check for sales/donations in first year
                        if transition == 'Selling':
                            quantity = yearly_state.shares_sold.get(lot_id, 0)
                        elif transition == 'Donating':
                            quantity = yearly_state.shares_donated.get(lot_id, 0)
                        # Check for vesting events
                        elif transition == 'Vesting':
                            # Check tracked vesting events
                            for event in getattr(yearly_state, 'vesting_events', []):
                                if event.lot_id == lot_id:
                                    quantity = event.quantity
                                    break
                            # Also check state changes
                            if quantity == 0 and curr_lot and curr_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED:
                                if initial_lot and initial_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                                    quantity = curr_lot.quantity
                        # Check for expiring
                        elif transition == 'Expiring':
                            for event in getattr(yearly_state, 'expiration_events', []):


                                if event.lot_id == lot_id:
                                    quantity = event.quantity
                                    break
                        elif curr_lot:
                            # Check for granting in year 1
                            if transition == 'Granting' and curr_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                                # If lot wasn't in initial state or had fewer shares, it was granted
                                if not initial_lot or initial_lot.quantity < curr_lot.quantity:
                                    quantity = curr_lot.quantity - (initial_lot.quantity if initial_lot else 0)

                            # Check for exercising
                            elif transition == 'Exercising':
                                if '_EX_' in lot_id and curr_lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED:
                                    quantity = curr_lot.quantity
                    else:
                        # Compare with previous year to detect transitions
                        prev_state = result.yearly_states[i-1]
                        curr_lot = next((l for l in yearly_state.equity_holdings if l.lot_id == lot_id), None)
                        prev_lot = next((l for l in prev_state.equity_holdings if l.lot_id == lot_id), None)

                        # Check tracked vesting events first
                        if transition == 'Vesting':
                            for event in getattr(yearly_state, 'vesting_events', []):
                                if event.lot_id == lot_id:
                                    quantity = event.quantity
                                    break
                        elif transition == 'Expiring':
                            for event in getattr(yearly_state, 'expiration_events', []):


                                if event.lot_id == lot_id:
                                    quantity = event.quantity
                                    break

                        # If no tracked events, detect state changes
                        if quantity == 0 and curr_lot and prev_lot:
                            # Granting - increase in granted shares
                            if (transition == 'Granting' and
                                curr_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED and
                                prev_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED and
                                curr_lot.quantity > prev_lot.quantity):
                                quantity = curr_lot.quantity - prev_lot.quantity

                            # Vesting - transition from granted to vested (fallback if not in events)
                            elif transition == 'Vesting' and quantity == 0:
                                if (prev_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED and
                                    curr_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED):
                                    quantity = curr_lot.quantity
                                elif (prev_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED and
                                      curr_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED and
                                      prev_lot.quantity > curr_lot.quantity):
                                    # Partial vesting - granted quantity decreased
                                    quantity = prev_lot.quantity - curr_lot.quantity

                            # Exercising - vested shares decreased or exercise lot created
                            elif transition == 'Exercising':
                                if (prev_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED and
                                    curr_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED and
                                    prev_lot.quantity > curr_lot.quantity):
                                    # Partial exercise
                                    quantity = prev_lot.quantity - curr_lot.quantity

                        elif curr_lot and not prev_lot:
                            # New lot appeared
                            if transition == 'Granting' and curr_lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                                quantity = curr_lot.quantity
                            elif transition == 'Vesting' and curr_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED:
                                # Lot appeared as vested (e.g., from a vest event)
                                quantity = curr_lot.quantity
                            elif transition == 'Exercising' and '_EX_' in lot_id:
                                # New exercise lot created
                                quantity = curr_lot.quantity

                        elif prev_lot and not curr_lot:
                            # Lot disappeared - check if expired
                            if transition == 'Expiring':
                                # First check tracked expiration events
                                for event in getattr(yearly_state, 'expiration_events', []):
                                    if event.lot_id == lot_id:
                                        quantity = event.quantity
                                        break
                                # If not in events, calculate from state
                                if quantity == 0:
                                    # Only mark as expiring if it was an unexercised option that actually expired this year
                                    # Exercised options disappear but don't expire - they become exercise lots
                                    if (prev_lot.share_type in [ShareType.ISO, ShareType.NSO] and
                                        prev_lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED and
                                        prev_lot.expiration_date and
                                        (prev_lot.expiration_date.year == yearly_state.year or
                                         prev_lot.expiration_date.year == yearly_state.year - 1)):

                                        # Calculate shares that were sold or donated
                                        total_sold = yearly_state.shares_sold.get(lot_id, 0)
                                        total_donated = yearly_state.shares_donated.get(lot_id, 0)

                                        # Check for shares that were exercised THIS YEAR by looking for exercise lots created this year
                                        # Only count exercises that happened in the current year to avoid double-counting
                                        total_exercised_from_this_lot = 0
                                        for curr_exercise_lot in yearly_state.equity_holdings:
                                            if (curr_exercise_lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED and
                                                curr_exercise_lot.grant_id == prev_lot.grant_id and
                                                curr_exercise_lot.grant_date == prev_lot.grant_date and
                                                curr_exercise_lot.strike_price == prev_lot.strike_price and
                                                curr_exercise_lot.exercise_date and
                                                curr_exercise_lot.exercise_date.year == yearly_state.year):
                                                # Check if this exercise lot didn't exist in previous year
                                                prev_exercise_lot = next((l for l in prev_state.equity_holdings
                                                                        if l.lot_id == curr_exercise_lot.lot_id), None)
                                                if not prev_exercise_lot:
                                                    # This exercise lot was created this year from our disappeared lot
                                                    total_exercised_from_this_lot += curr_exercise_lot.quantity

                                        # Only mark as expired the shares that can't be accounted for by sales, donations, or exercises
                                        unaccounted_shares = prev_lot.quantity - total_sold - total_donated - total_exercised_from_this_lot
                                        if unaccounted_shares > 0:
                                            quantity = unaccounted_shares

                        # Track disposals using year-over-year changes
                        if transition == 'Selling':
                            prev_sold = prev_state.shares_sold.get(lot_id, 0)
                            curr_sold = yearly_state.shares_sold.get(lot_id, 0)
                            quantity = curr_sold - prev_sold
                        elif transition == 'Donating':
                            prev_donated = prev_state.shares_donated.get(lot_id, 0)
                            curr_donated = yearly_state.shares_donated.get(lot_id, 0)
                            quantity = curr_donated - prev_donated

                    row[year] = quantity if quantity > 0 else 0  # Only show positive transitions

                writer.writerow(row)



def save_all_projection_csvs(result: ProjectionResult, scenario_name: str, output_dir: str = "output") -> None:
    """Save all projection CSVs for a scenario."""
    base_name = scenario_name.lower().replace(' ', '_').replace('-', '_')

    # Core timeline and state tracking CSVs
    save_annual_tax_detail_csv(result, f"{output_dir}/{base_name}_annual_tax_detail.csv")
    save_state_timeline_csv(result, f"{output_dir}/{base_name}_state_timeline.csv")
    save_transition_timeline_csv(result, f"{output_dir}/{base_name}_transition_timeline.csv")

    # New tracking CSVs
    generate_holding_milestones_csv(result, f"{output_dir}/{base_name}_holding_period_tracking.csv")
    save_charitable_carryforward_csv(result, f"{output_dir}/{base_name}_charitable_carryforward.csv")


    # Comprehensive cash flow tracking
    save_comprehensive_cashflow_csv(result, f"{output_dir}/{base_name}_comprehensive_cashflow.csv")

    # NEW: Component-based CSVs replacing detailed_materialization
    save_components_csv(result, f"{output_dir}/{base_name}_components.csv")
    save_annual_summary_csv(result, f"{output_dir}/{base_name}_annual_summary.csv")


def create_comparison_csv(results: List[ProjectionResult], output_path: str) -> None:
    """Create comparison CSV across multiple scenarios."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        fieldnames = ['scenario', 'net_worth', 'total_cash_final', 'total_equity_value_final', 
                     'net_worth_plus_charity', 'total_taxes_all_years', 'total_donations_all_years',
                     'pledge_shares_obligated', 'pledge_shares_donated',
                     'pledge_shares_outstanding', 'pledge_shares_expired', 'outstanding_obligation',
                     'charitable_personal_value', 'charitable_match_value', 'charitable_total_impact',
                     'pledge_fulfillment_rate', 'outstanding_amt_credits', 'expired_charitable_deduction',
                     'expired_option_count', 'expired_option_loss', 'min_cash_balance', 'min_cash_year',
                     'years_to_burn_amt_credits', 'initial_amt_credits', 'years_with_insufficient_cash',
                     'zero_plg_exp', 'zero_equity', 'meets_all_constraints']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            metrics = result.summary_metrics
            net_worth = metrics.get('total_cash_final', 0) + metrics.get('total_equity_value_final', 0)
            charity_total = metrics.get('total_charitable_impact_all_years', metrics.get('total_donations_all_years', 0))
            net_worth_plus_charity = net_worth + charity_total
            
            # Check constraints
            zero_plg_exp = metrics.get('pledge_shares_expired_window', 0) == 0
            zero_equity = metrics.get('total_equity_value_final', 0) == 0
            meets_all_constraints = zero_plg_exp and zero_equity
            
            writer.writerow({
                'scenario': result.plan.name,
                'net_worth': net_worth,
                'total_cash_final': metrics.get('total_cash_final', 0),
                'total_equity_value_final': metrics.get('total_equity_value_final', 0),
                'net_worth_plus_charity': net_worth_plus_charity,
                'total_taxes_all_years': metrics.get('total_taxes_all_years', 0),
                'total_donations_all_years': metrics.get('total_donations_all_years', 0),
                'pledge_shares_obligated': metrics.get('pledge_shares_obligated', 0),
                'pledge_shares_donated': metrics.get('pledge_shares_donated', 0),
                'pledge_shares_outstanding': metrics.get('pledge_shares_outstanding', 0),
                'pledge_shares_expired': metrics.get('pledge_shares_expired_window', 0),
                'outstanding_obligation': metrics.get('outstanding_obligation', 0),
                'charitable_personal_value': metrics.get('total_donations_all_years', 0),
                'charitable_match_value': metrics.get('total_company_match_all_years', 0),
                'charitable_total_impact': metrics.get('total_charitable_impact_all_years', 0),
                'pledge_fulfillment_rate': metrics.get('pledge_fulfillment_rate', 0),
                'outstanding_amt_credits': metrics.get('amt_credits_final', 0),
                'expired_charitable_deduction': metrics.get('expired_charitable_deduction', 0),
                'expired_option_count': metrics.get('expired_option_count', 0),
                'expired_option_loss': metrics.get('expired_option_loss', 0),
                'min_cash_balance': metrics.get('min_cash_balance', 0),
                'min_cash_year': metrics.get('min_cash_year', 0),
                'years_to_burn_amt_credits': metrics.get('years_to_burn_amt_credits', 0),
                'initial_amt_credits': metrics.get('initial_amt_credits', 0),
                'years_with_insufficient_cash': metrics.get('years_with_insufficient_cash', 0),
                'zero_plg_exp': zero_plg_exp,
                'zero_equity': zero_equity,
                'meets_all_constraints': meets_all_constraints
            })
