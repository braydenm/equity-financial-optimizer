"""
Natural Evolution (no action) scenario generator.

This module generates the baseline scenario where natural vesting occurs
but no additional actions are taken. Options vest according to schedule
and expire if not exercised.

Note: Price projections should be loaded from external sources such as:
- market_projections.json (market assumptions file)
- financial advisor inputs
- user-specified price scenarios
- Monte Carlo simulation inputs
This module defaults to current price with no change if projections not provided.
"""

import csv
import json
from datetime import date, datetime
from typing import Dict, List, Any
from pathlib import Path

from projections.projection_state import (
    ProjectionPlan, ShareLot, PlannedAction, UserProfile,
    ShareType, LifecycleState, TaxTreatment, ActionType
)


def load_equity_timeline(timeline_path: str) -> List[Dict[str, Any]]:
    """Load equity position timeline from CSV."""
    timeline = []
    with open(timeline_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timeline.append(row)
    return timeline


def load_user_profile_simplified(profile_path: str) -> UserProfile: #Claude TODO: Explain why we are using a simplified load here. Can we just use an existing loader? What's the data flow for this file compared to the whole project flow?
    """Load user profile and extract key parameters for projections."""
    with open(profile_path, 'r') as f:
        profile_data = json.load(f) #Claude TODO: Does this look like we are loading the profile twice in this file in a way that is redundant?

    personal_info = profile_data.get('personal_information', {})
    income = profile_data.get('income', {})
    financial_pos = profile_data.get('financial_position', {})
    charitable = profile_data.get('charitable_giving', {})
    liquid_assets = financial_pos.get('liquid_assets', {})
    liquidity_needs = profile_data.get('goals_and_constraints', {}).get('liquidity_needs', {})
    tax_situation = profile_data.get('tax_situation', {})
    estimated_taxes = tax_situation.get('estimated_taxes', {})
    carryforwards = tax_situation.get('carryforwards', {})
    monthly_cash_flow = financial_pos.get('monthly_cash_flow', {})

    return UserProfile(
        federal_tax_rate=personal_info['federal_tax_rate'],
        federal_ltcg_rate=personal_info['federal_ltcg_rate'],
        state_tax_rate=personal_info['state_tax_rate'],
        state_ltcg_rate=personal_info['state_ltcg_rate'],
        fica_tax_rate=personal_info['fica_tax_rate'],
        additional_medicare_rate=personal_info['additional_medicare_rate'],
        niit_rate=personal_info['niit_rate'],
        annual_w2_income=income.get('annual_w2_income', 0),
        spouse_w2_income=income.get('spouse_w2_income', 0),
        other_income=income.get('other_income', 0),
        interest_income=income.get('interest_income', 0),
        dividend_income=income.get('dividend_income', 0),
        bonus_expected=income.get('bonus_expected', 0),
        current_cash=liquid_assets.get('cash', 0),
        exercise_reserves=liquidity_needs.get('exercise_reserves', 0),
        pledge_percentage=charitable.get('pledge_percentage', 0.5),
        company_match_ratio=charitable.get('company_match_ratio', 3.0),
        filing_status=personal_info.get('tax_filing_status', 'single'),
        state_of_residence=personal_info.get('state_of_residence', 'California'),
        monthly_living_expenses=monthly_cash_flow.get('expenses', 0),
        regular_income_withholding_rate=estimated_taxes.get('regular_income_withholding_rate', 0.0),
        supplemental_income_withholding_rate=estimated_taxes.get('supplemental_income_withholding_rate', 0.0),
        quarterly_payments=estimated_taxes.get('quarterly_payments', 0),
        taxable_investments=liquid_assets.get('taxable_investments', 0),
        amt_credit_carryforward=carryforwards.get('amt_credit', 0)
    )


def parse_timeline_row(row: Dict[str, Any]) -> ShareLot:
    """Convert a timeline CSV row to a ShareLot object."""
    return ShareLot(
        lot_id=row['lot_id'],
        share_type=ShareType(row['share_type']),
        quantity=int(row['quantity']),
        strike_price=float(row['strike_price']),
        grant_date=datetime.fromisoformat(row['date']).date(),
        lifecycle_state=LifecycleState(row['lifecycle_state']),
        tax_treatment=TaxTreatment(row['tax_treatment']) if row['tax_treatment'] != 'N/A' else TaxTreatment.NA
    )


def generate_natural_evolution(timeline_path: str, profile_path: str,
                             projection_years: int = 8) -> ProjectionPlan:
    """
    Generate Natural Evolution scenario.

    This scenario includes:
    - Natural vesting according to schedule
    - No additional exercise actions
    - Options expire if not exercised by end of projection period
    - No sales or donations

    Args:
        timeline_path: Path to equity_position_timeline.csv
        profile_path: Path to user_profile.json
        projection_years: Number of years to project (default 8)

    Returns:
        ProjectionPlan with natural evolution actions only
    """
    # Load data
    timeline_data = load_equity_timeline(timeline_path)
    profile = load_user_profile_simplified(profile_path) ##Claude TODO: Just use regular profile loader and delete simplified.

    # Determine projection period
    start_date = date(2025, 1, 1)  # Start of current projection year
    end_date = date(start_date.year + projection_years - 1, 12, 31)

    # Parse initial lots from timeline
    initial_lots = []
    vesting_actions = []

    for row in timeline_data:
        lot = parse_timeline_row(row)
        row_date = datetime.fromisoformat(row['date']).date()

        # If this is a current position (already vested/exercised), add to initial lots
        if row_date <= start_date:
            if lot.lifecycle_state in [LifecycleState.VESTED_NOT_EXERCISED,
                                     LifecycleState.EXERCISED_NOT_DISPOSED]:
                initial_lots.append(lot)

        # If this is a future vesting event, add as planned action
        elif row_date <= end_date and lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
            vesting_action = PlannedAction(
                action_date=row_date,
                action_type=ActionType.VEST,
                lot_id=lot.lot_id,
                quantity=lot.quantity,
                notes=f"Natural vesting of {lot.quantity} {lot.share_type.value} shares"
            )
            vesting_actions.append(vesting_action)

    # Add option expiration actions for unexercised options at end of period
    # Assume options expire 10 years from grant date if not exercised
    expiration_actions = []
    for lot in initial_lots:
        if lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED:
            # Calculate expiration date (10 years from grant). #Claude TODO: Pull this from user profile, don't hardcode.
            expiration_date = date(lot.grant_date.year + 10, lot.grant_date.month, lot.grant_date.day)
            if expiration_date <= end_date:
                expiration_action = PlannedAction(
                    action_date=expiration_date,
                    action_type=ActionType.HOLD,  # Hold until expiration
                    lot_id=lot.lot_id,
                    quantity=lot.quantity,
                    notes=f"Option expires unexercised"
                )
                expiration_actions.append(expiration_action)

    # Price projections should be provided externally (e.g., market_projections.json)
    # Default to current price with no change if not provided
    # Claude TODO: Load price projections from external source (market_projections.json, financial advisor inputs, etc.)

    # Extract current price from profile data
    with open(profile_path, 'r') as f:
        profile_data = json.load(f)
    current_prices = profile_data.get('equity_position', {}).get('current_prices', {})
    base_price = current_prices.get('last_409a_price')
    if not base_price:
        raise ValueError("Current 409A price must be provided in user profile current_prices")

    price_projections = {} #Claude TODO: Remove this basic assumption and load from external source.
    for year in range(start_date.year, end_date.year + 1):
        price_projections[year] = base_price  # No change assumption

    # Create the projection plan
    plan = ProjectionPlan(
        name="Natural Evolution",
        description="Baseline scenario with natural vesting, no additional actions, options expire if unexercised",
        start_date=start_date,
        end_date=end_date,
        initial_lots=initial_lots,
        initial_cash=profile.current_cash,
        planned_actions=vesting_actions + expiration_actions,
        price_projections=price_projections
    )

    return plan


def generate_natural_evolution_from_profile_data(profile_data: Dict[str, Any],
                                               projection_years: int = 5) -> ProjectionPlan:
    """
    Generate Natural Evolution scenario directly from profile data dictionary.

    Alternative method that works with profile data directly rather than file paths.
    """
    # Extract equity position data
    equity_position = profile_data.get('equity_position', {})
    exercised_lots = equity_position.get('exercised_lots', [])
    vested_unexercised = equity_position.get('vested_unexercised', {})
    vesting_calendar = equity_position.get('vesting_calendar', [])
    current_prices = equity_position.get('current_prices', {})

    # Create user profile
    personal_info = profile_data.get('personal_information', {})
    income = profile_data.get('income', {})
    financial = profile_data.get('financial_position', {})
    charitable = profile_data.get('charitable_giving', {})
    tax_situation = profile_data.get('tax_situation', {})
    estimated_taxes = tax_situation.get('estimated_taxes', {})
    carryforwards = tax_situation.get('carryforwards', {})
    monthly_cash_flow = financial.get('monthly_cash_flow', {})

    profile = UserProfile(
        federal_tax_rate=personal_info['federal_tax_rate'],
        federal_ltcg_rate=personal_info['federal_ltcg_rate'],
        state_tax_rate=personal_info['state_tax_rate'],
        state_ltcg_rate=personal_info['state_ltcg_rate'],
        fica_tax_rate=personal_info['fica_tax_rate'],
        additional_medicare_rate=personal_info['additional_medicare_rate'],
        niit_rate=personal_info['niit_rate'],
        annual_w2_income=income['annual_w2_income'],
        spouse_w2_income=income.get('spouse_w2_income', 0),
        other_income=income.get('other_income', 0),
        interest_income=income.get('interest_income', 0),
        dividend_income=income.get('dividend_income', 0),
        bonus_expected=income.get('bonus_expected', 0),
        current_cash=financial['liquid_assets']['cash'],
        exercise_reserves=profile_data.get('goals_and_constraints', {}).get('liquidity_needs', {}).get('exercise_reserves', 0),
        pledge_percentage=charitable.get('pledge_percentage', 0.5),
        company_match_ratio=charitable.get('company_match_ratio', 3.0),
        filing_status=personal_info.get('tax_filing_status', 'single'),
        state_of_residence=personal_info.get('state_of_residence', 'California'),
        monthly_living_expenses=monthly_cash_flow.get('expenses', 0),
        regular_income_withholding_rate=estimated_taxes.get('regular_income_withholding_rate', 0.0),
        supplemental_income_withholding_rate=estimated_taxes.get('supplemental_income_withholding_rate', 0.0),
        quarterly_payments=estimated_taxes.get('quarterly_payments', 0),
        taxable_investments=financial['liquid_assets'].get('taxable_investments', 0),
        amt_credit_carryforward=carryforwards.get('amt_credit', 0)
    )

    # Set up projection period
    start_date = date(2025, 1, 1)
    end_date = date(start_date.year + projection_years - 1, 12, 31)

    # Process initial lots (already exercised)
    initial_lots = []
    for lot_data in exercised_lots:
        exercise_date = datetime.fromisoformat(lot_data.get('exercise_date', '2024-01-01')).date()

        # Determine tax treatment based on exercise date
        months_held = (start_date.year - exercise_date.year) * 12 + (start_date.month - exercise_date.month)
        tax_treatment = TaxTreatment.LTCG if months_held >= 12 else TaxTreatment.STCG

        lot = ShareLot(
            lot_id=lot_data['lot_id'],
            share_type=ShareType(lot_data['type']),
            quantity=lot_data['shares'],
            strike_price=lot_data['strike_price'],
            grant_date=exercise_date,
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=tax_treatment,
            exercise_date=exercise_date,
            cost_basis=lot_data.get('cost_basis', lot_data['strike_price']),
            taxes_paid=lot_data.get('taxes_paid', 0),
            amt_adjustment=lot_data.get('amt_adjustment', 0)
        )
        initial_lots.append(lot)

    # Extract grant information from profile data - REQUIRED
    original_grants = profile_data['equity_position']['original_grants']
    if not original_grants:
        raise ValueError(
            "Missing required grant information in user_profile.json. "
            "The 'equity_position.original_grants' field must contain grant data with "
            "'strike_price' and 'grant_date' to accurately model vested positions. "
            "Add this data to your user profile or fix the data loading process."
        )

    grant_info = original_grants[0]  # Use first grant for vested positions
    if 'strike_price' not in grant_info:
        raise ValueError(
            "Missing 'strike_price' in grant information. "
            "This is required for accurate financial modeling."
        )
    if 'grant_date' not in grant_info:
        raise ValueError(
            "Missing 'grant_date' in grant information. "
            "This is required for tax treatment calculations."
        )

    strike_price = grant_info['strike_price']
    grant_date = datetime.strptime(grant_info['grant_date'], '%Y-%m-%d').date()

    # Extract expiration date if available (required for options)
    expiration_date = None
    if 'expiration_date' in grant_info:
        expiration_date = datetime.strptime(grant_info['expiration_date'], '%Y-%m-%d').date()

    # Add vested unexercised positions
    if vested_unexercised.get('iso_shares', 0) > 0:
        iso_lot = ShareLot(
            lot_id="ISO",
            share_type=ShareType.ISO,
            quantity=vested_unexercised['iso_shares'],
            strike_price=strike_price,
            grant_date=grant_date,
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=expiration_date
        )
        initial_lots.append(iso_lot)

    if vested_unexercised.get('nso_shares', 0) > 0:
        nso_lot = ShareLot(
            lot_id="NSO",
            share_type=ShareType.NSO,
            quantity=vested_unexercised['nso_shares'],
            strike_price=strike_price,
            grant_date=grant_date,
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=expiration_date
        )
        initial_lots.append(nso_lot)

    # Process future vesting events
    vesting_actions = []
    for vesting_event in vesting_calendar:
        vest_date = datetime.fromisoformat(vesting_event['date']).date()
        if start_date < vest_date <= end_date:
            action = PlannedAction(
                action_date=vest_date,
                action_type=ActionType.VEST,
                lot_id=f"VEST_{vest_date.strftime('%Y%m%d')}_{vesting_event['share_type']}",
                quantity=vesting_event['shares'],
                notes=f"Natural vesting of {vesting_event['shares']} {vesting_event['share_type']} shares"
            )
            vesting_actions.append(action)

    # Price projections should be provided externally (e.g., market_projections.json)
    # Default to current price with no change if not provided
    # TODO: Load price projections from external source (market_projections.json, financial advisor inputs, etc.)
    base_price = current_prices.get('last_409a_price')
    if not base_price:
        raise ValueError("Current 409A price must be provided in user profile current_prices")

    price_projections = {}
    for year in range(start_date.year, end_date.year + 1):
        price_projections[year] = base_price  # No change assumption

    plan = ProjectionPlan(
        name="Natural Evolution",
        description="Baseline scenario with natural vesting, no additional actions",
        start_date=start_date,
        end_date=end_date,
        initial_lots=initial_lots,
        initial_cash=profile.current_cash,
        planned_actions=vesting_actions,
        price_projections=price_projections
    )

    return plan
