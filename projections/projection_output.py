"""
CSV output functionality for projection calculator results.

This module provides functions to save projection results to CSV files
for analysis and comparison.
"""

import csv
import os
from datetime import date
from typing import List, Dict, Any
from projections.projection_state import ProjectionResult, YearlyState, LifecycleState
from projections.detailed_materialization import materialize_detailed_projection

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
            'federal_amt_credits_generated', 'federal_amt_credits_used', 'amt_credits_remaining',
            'charitable_deduction_cash', 'charitable_deduction_stock'
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
                'federal_amt_credits_generated': round(state.tax_state.amt_credits_generated, 2),
                'federal_amt_credits_used': round(state.tax_state.amt_credits_used, 2),
                'amt_credits_remaining': round(state.tax_state.amt_credits_remaining, 2),
                'charitable_deduction_cash': round(charitable_cash, 2),
                'charitable_deduction_stock': round(charitable_stock, 2)
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


def save_holding_period_tracking_csv(result: ProjectionResult, output_path: str) -> None:
    """Save holding period tracking for tax treatment determination."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    final_state = result.get_final_state()
    if not final_state:
        return

    with open(output_path, 'w', newline='') as f:
        fieldnames = [
            'lot_id', 'acquisition_date', 'acquisition_type', 'current_quantity',
            'days_held', 'holding_status', 'iso_qualifying_date', 'notes'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Calculate from final state
        calculation_date = final_state.year * 10000 + 1231  # Year-end date
        calc_date = date(final_state.year, 12, 31)

        for lot in final_state.equity_holdings:
            # Skip expired lots - they're no longer held
            if lot.lifecycle_state == LifecycleState.EXPIRED:
                continue

            # Determine acquisition date and type
            acquisition_date = None
            acquisition_type = ''
            iso_qualifying_date = None

            if hasattr(lot, 'acquisition_date'):
                acquisition_date = lot.acquisition_date
            elif hasattr(lot, 'exercise_date'):
                acquisition_date = lot.exercise_date
                acquisition_type = 'exercise'
            elif hasattr(lot, 'vest_date'):
                acquisition_date = lot.vest_date
                acquisition_type = 'vest'
            elif hasattr(lot, 'grant_date'):
                acquisition_date = lot.grant_date
                acquisition_type = 'grant'

            # Calculate days held
            days_held = 0
            if acquisition_date:
                days_held = (calc_date - acquisition_date).days

            # Determine holding status
            holding_status = 'short-term' if days_held <= 365 else 'long-term'

            # For ISOs, calculate qualifying disposition date
            if lot.share_type.value == 'ISO' and acquisition_date:
                # ISO qualifying requires 2 years from grant AND 1 year from exercise
                if hasattr(lot, 'grant_date') and hasattr(lot, 'exercise_date'):
                    if lot.grant_date and lot.exercise_date:
                        two_years_from_grant = lot.grant_date.replace(year=lot.grant_date.year + 2)
                        one_year_from_exercise = lot.exercise_date.replace(year=lot.exercise_date.year + 1)
                        iso_qualifying_date = max(two_years_from_grant, one_year_from_exercise)

            # Build notes about tax treatment
            notes = []
            if lot.share_type.value == 'ISO' and iso_qualifying_date:
                if calc_date >= iso_qualifying_date:
                    notes.append('Qualifying disposition eligible')
                else:
                    days_until_qualify = (iso_qualifying_date - calc_date).days
                    notes.append(f'Disqualifying - {days_until_qualify} days until qualifying')

            writer.writerow({
                'lot_id': lot.lot_id,
                'acquisition_date': acquisition_date.isoformat() if acquisition_date else '',
                'acquisition_type': acquisition_type,
                'current_quantity': lot.quantity,
                'days_held': days_held,
                'holding_status': holding_status,
                'iso_qualifying_date': iso_qualifying_date.isoformat() if iso_qualifying_date else '',
                'notes': '; '.join(notes)
            })


def save_pledge_obligations_csv(result: ProjectionResult, output_path: str) -> None:
    """Save pledge obligations tracking from share sales."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    final_state = result.get_final_state()
    if not final_state or not hasattr(final_state, 'pledge_state'):
        return

    with open(output_path, 'w', newline='') as f:
        fieldnames = [
            'obligation_id', 'creation_date', 'source_sale_lot', 'sale_proceeds',
            'pledge_percentage', 'pledge_amount', 'match_window_closes',
            'fulfilled_amount', 'remaining_amount', 'days_until_deadline'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Get current date for deadline calculation
        calc_date = date(final_state.year, 12, 31)

        # Write all obligations
        for obligation in final_state.pledge_state.obligations:
            days_until_deadline = (obligation.match_window_closes - calc_date).days

            writer.writerow({
                'obligation_id': obligation.parent_transaction_id,
                'creation_date': obligation.commencement_date.isoformat(),
                'source_sale_lot': obligation.parent_transaction_id.rsplit('_', 1)[0] if '_' in obligation.parent_transaction_id else obligation.parent_transaction_id, ##CLaude TODO: Confirm this isn't assuming always the second underscore since there might be other naming conventions used.
                'sale_proceeds': round(obligation.total_pledge_obligation / obligation.pledge_percentage if obligation.pledge_percentage > 0 else 0, 2),
                'pledge_percentage': round(obligation.pledge_percentage, 4),
                'pledge_amount': round(obligation.total_pledge_obligation, 2),
                'match_window_closes': obligation.match_window_closes.isoformat(),
                'fulfilled_amount': round(obligation.donations_made, 2),
                'remaining_amount': round(obligation.outstanding_obligation, 2),
                'days_until_deadline': days_until_deadline
            })


def save_charitable_carryforward_csv(result: ProjectionResult, output_path: str) -> None:
    """Save charitable deduction carryforward tracking."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', newline='') as f:
        fieldnames = [
            'year', 'cash_donations', 'stock_donations', 'agi',
            'federal_cash_limit', 'federal_stock_limit', 'federal_cash_used', 'federal_stock_used',
            'federal_cash_carryforward', 'federal_stock_carryforward', 'federal_expired_this_year',
            'ca_cash_limit', 'ca_stock_limit', 'ca_cash_used', 'ca_stock_used',
            'ca_cash_carryforward', 'ca_stock_carryforward', 'ca_expired_this_year',
            'carryforward_expiration_year', 'basis_election', 'stock_deduction_type',
            'total_federal_deduction', 'federal_stock_carryforward_remaining_by_year',
            'pledge_obligations_unmet', 'cumulative_match_expiries', 'match_earned',
            'unmatched_donations'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Track carryforward across years for both federal and CA
        cumulative_federal_cash_carryforward = {}  # year -> amount
        cumulative_federal_stock_carryforward = {}  # year -> amount
        cumulative_ca_cash_carryforward = {}  # year -> amount
        cumulative_ca_stock_carryforward = {}  # year -> amount

        # Track cumulative match expiries
        cumulative_match_expiries = 0.0

        for state in result.yearly_states:
            # Get AGI for this year
            agi = 0
            cash_donations = 0
            stock_donations = 0

            # Check if basis election applies this year
            basis_election = False
            if hasattr(result, 'plan') and result.plan and 'charitable_basis_election_years' in result.plan.tax_elections:
                basis_election = state.year in result.plan.tax_elections['charitable_basis_election_years']

            # Extract donation data from state
            if state.donation_value > 0:
                # State tracks total donation value
                stock_donations = state.donation_value

            # Extract detailed data from annual tax components if available
            if state.annual_tax_components:
                # Calculate AGI from all income sources
                w2_income = state.income
                spouse_income = state.spouse_income
                other_income = state.other_income

                # Extract capital gains
                stcg = 0
                ltcg = 0
                for sale in getattr(state.annual_tax_components, 'sale_components', []):
                    stcg += getattr(sale, 'short_term_gain', 0)
                    ltcg += getattr(sale, 'long_term_gain', 0)

                # NSO exercise creates ordinary income
                nso_ordinary = 0
                for nso in getattr(state.annual_tax_components, 'nso_exercise_components', []):
                    nso_ordinary += getattr(nso, 'bargain_element', 0)

                agi = w2_income + spouse_income + other_income + stcg + ltcg + nso_ordinary

                # Get detailed donation breakdown if available
                donation_components = getattr(state.annual_tax_components, 'donation_components', [])
                if donation_components:
                    # Reset if we have detailed data
                    stock_donations = 0
                    cash_donations = 0

                    for donation in donation_components:
                        donation_value = getattr(donation, 'donation_value', 0)
                        deduction_type = getattr(donation, 'deduction_type', 'stock')
                        if deduction_type == 'stock':
                            stock_donations += donation_value
                        else:
                            cash_donations += donation_value

                # Add cash donations
                for cash_donation in getattr(state.annual_tax_components, 'cash_donation_components', []):
                    cash_donations += getattr(cash_donation, 'amount', 0)
            else:
                # Fallback AGI calculation #Claude TODO: Just throw an error here.
                agi = state.income + state.spouse_income + state.other_income

            # AGI limits for charitable deductions - differentiate federal vs state
            # Use federal limits as primary (most scenarios), but could be enhanced for state-specific analysis
            federal_cash_limit = agi * FEDERAL_CHARITABLE_AGI_LIMITS['cash']
            federal_stock_limit = agi * (FEDERAL_CHARITABLE_BASIS_ELECTION_AGI_LIMITS['stock'] if basis_election else FEDERAL_CHARITABLE_AGI_LIMITS['stock'])

            ca_cash_limit = agi * CALIFORNIA_CHARITABLE_AGI_LIMITS['cash']
            ca_stock_limit = agi * (CALIFORNIA_CHARITABLE_BASIS_ELECTION_AGI_LIMITS['stock'] if basis_election else CALIFORNIA_CHARITABLE_AGI_LIMITS['stock'])

            # Get deductions actually used from charitable state (both federal and state)
            has_federal_deductions = state.charitable_state and state.charitable_state.federal_current_year_deduction > 0
            has_ca_deductions = state.charitable_state and state.charitable_state.ca_current_year_deduction > 0

            if has_federal_deductions or has_ca_deductions:
                federal_total_deduction = state.charitable_state.federal_current_year_deduction if has_federal_deductions else 0
                ca_total_deduction = state.charitable_state.ca_current_year_deduction if has_ca_deductions else 0

                # Split between cash and stock based on donation ratio for both federal and state
                if (cash_donations + stock_donations) > 0:
                    stock_ratio = stock_donations / (cash_donations + stock_donations)

                    # Federal splits
                    federal_stock_used = min(stock_donations, federal_total_deduction * stock_ratio, federal_stock_limit)
                    federal_cash_used = min(cash_donations, federal_total_deduction * (1 - stock_ratio), federal_cash_limit)

                    # California splits
                    ca_stock_used = min(stock_donations, ca_total_deduction * stock_ratio, ca_stock_limit)
                    ca_cash_used = min(cash_donations, ca_total_deduction * (1 - stock_ratio), ca_cash_limit)
                else:
                    federal_cash_used = federal_stock_used = 0
                    ca_cash_used = ca_stock_used = 0
            else:
                federal_cash_used = federal_stock_used = 0
                ca_cash_used = ca_stock_used = 0

            # Calculate carryforwards for both federal and state
            federal_cash_carryforward = max(0, cash_donations - federal_cash_used)
            federal_stock_carryforward = max(0, stock_donations - federal_stock_used)
            ca_cash_carryforward = max(0, cash_donations - ca_cash_used)
            ca_stock_carryforward = max(0, stock_donations - ca_stock_used)

            # Track cumulative carryforward separately for federal and state
            if federal_cash_carryforward > 0:
                cumulative_federal_cash_carryforward[state.year] = federal_cash_carryforward
            if federal_stock_carryforward > 0:
                cumulative_federal_stock_carryforward[state.year] = federal_stock_carryforward
            if ca_cash_carryforward > 0:
                cumulative_ca_cash_carryforward[state.year] = ca_cash_carryforward
            if ca_stock_carryforward > 0:
                cumulative_ca_stock_carryforward[state.year] = ca_stock_carryforward

            # Carryforward expires after 5 years (same for both federal and CA)
            has_any_carryforward = (federal_cash_carryforward > 0 or federal_stock_carryforward > 0 or
                                  ca_cash_carryforward > 0 or ca_stock_carryforward > 0)
            carryforward_expiration = state.year + 5 if has_any_carryforward else ''

            # Calculate total federal deduction for the year
            total_federal_deduction = federal_cash_used + federal_stock_used

            # Create remaining carryforward dictionary for federal stock carryforward
            federal_stock_remaining_dict = {}
            if hasattr(state, 'charitable_state') and state.charitable_state:
                federal_stock_remaining_dict = dict(state.charitable_state.federal_carryforward_remaining)

            # Calculate pledge obligation tracking
            pledge_obligations_unmet = 0.0
            match_earned = 0.0

            if hasattr(state, 'pledge_state') and state.pledge_state:
                # Calculate unmet obligations that haven't expired (as of end of this year)
                from datetime import date as date_class
                year_end = date_class(state.year, 12, 31)

                for obligation in state.pledge_state.obligations:
                    # Only count obligations where match window is still open
                    if (obligation.match_window_closes is None or
                        year_end <= obligation.match_window_closes):
                        pledge_obligations_unmet += obligation.outstanding_obligation

                # Track lost match opportunities (cumulative)
                cumulative_match_expiries += state.lost_match_opportunities

            # Company match earned this year
            if hasattr(state, 'company_match_received'):
                match_earned = state.company_match_received

            # Calculate unmatched donations (donations that didn't receive company match)
            total_donations_this_year = cash_donations + stock_donations
            if match_earned > 0 and hasattr(result, 'user_profile') and result.user_profile.company_match_ratio > 0:
                # Calculate how much donation value was actually matched
                # For pledge-based matching, only the amount applied to active obligations gets matched
                matched_donation_value = match_earned / result.user_profile.company_match_ratio
                unmatched_donations = max(0, total_donations_this_year - matched_donation_value)
            else:
                # No match earned, so all donations were unmatched
                unmatched_donations = total_donations_this_year

            writer.writerow({
                'year': state.year,
                'cash_donations': round(cash_donations, 2),
                'stock_donations': round(stock_donations, 2),
                'agi': round(agi, 2),
                'federal_cash_limit': round(federal_cash_limit, 2),
                'federal_stock_limit': round(federal_stock_limit, 2),
                'federal_cash_used': round(federal_cash_used, 2),
                'federal_stock_used': round(federal_stock_used, 2),
                'federal_cash_carryforward': round(federal_cash_carryforward, 2),
                'federal_stock_carryforward': round(federal_stock_carryforward, 2),
                'federal_expired_this_year': round(state.charitable_state.federal_expired_this_year, 2),
                'ca_cash_limit': round(ca_cash_limit, 2),
                'ca_stock_limit': round(ca_stock_limit, 2),
                'ca_cash_used': round(ca_cash_used, 2),
                'ca_stock_used': round(ca_stock_used, 2),
                'ca_cash_carryforward': round(ca_cash_carryforward, 2),
                'ca_stock_carryforward': round(ca_stock_carryforward, 2),
                'ca_expired_this_year': round(state.charitable_state.ca_expired_this_year, 2),
                'carryforward_expiration_year': carryforward_expiration,
                'basis_election': basis_election,
                'stock_deduction_type': 'basis' if basis_election else 'fmv',
                'total_federal_deduction': round(total_federal_deduction, 2),
                'federal_stock_carryforward_remaining_by_year': str(federal_stock_remaining_dict),
                'pledge_obligations_unmet': round(pledge_obligations_unmet, 2),
                'cumulative_match_expiries': round(cumulative_match_expiries, 2),
                'match_earned': round(match_earned, 2),
                'unmatched_donations': round(unmatched_donations, 2)
            })




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
                                    # Make sure it wasn't sold or donated
                                    total_sold = yearly_state.shares_sold.get(lot_id, 0)
                                    total_donated = yearly_state.shares_donated.get(lot_id, 0)
                                    if prev_lot.quantity > total_sold + total_donated:
                                        quantity = prev_lot.quantity - total_sold - total_donated

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
        ending_investments = state.investment_balance
        ending_equity_value = state.total_equity_value
        total_net_worth = ending_cash + ending_investments + ending_equity_value

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


def save_all_projection_csvs(result: ProjectionResult, scenario_name: str, output_dir: str = "output") -> None:
    """Save all projection CSVs for a scenario."""
    base_name = scenario_name.lower().replace(' ', '_').replace('-', '_')

    # Core timeline and state tracking CSVs
    save_annual_tax_detail_csv(result, f"{output_dir}/{base_name}_annual_tax_detail.csv")
    save_state_timeline_csv(result, f"{output_dir}/{base_name}_state_timeline.csv")
    save_transition_timeline_csv(result, f"{output_dir}/{base_name}_transition_timeline.csv")

    # New tracking CSVs
    save_holding_period_tracking_csv(result, f"{output_dir}/{base_name}_holding_period_tracking.csv")
    save_pledge_obligations_csv(result, f"{output_dir}/{base_name}_pledge_obligations.csv")
    save_charitable_carryforward_csv(result, f"{output_dir}/{base_name}_charitable_carryforward.csv")

    # Comprehensive cash flow tracking
    save_comprehensive_cashflow_csv(result, f"{output_dir}/{base_name}_comprehensive_cashflow.csv")

    # Generate detailed financial materialization for transparency
    # This creates action_summary.csv and annual_summary.csv (keeping these)
    materialize_detailed_projection(result, output_dir, scenario_name)


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
