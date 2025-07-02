#!/usr/bin/env python3
"""
Exercise Before Expiry Scenario - Custom Projection Analysis

This scenario exercises all vested options and options that vest during the
projection period at the latest possible time before expiry (but within
the 5-year projection window). No sales or donations are made.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import date, datetime
from projections.projection_state import (
    ProjectionPlan, ShareLot, PlannedAction, UserProfile,
    ShareType, LifecycleState, TaxTreatment, ActionType
)
from projections.projection_calculator import ProjectionCalculator
from projections.projection_output import save_all_projection_csvs
from loaders.profile_loader import ProfileLoader


def load_user_profile():
    """Load user profile with secure fallback to demo data."""
    loader = ProfileLoader()
    return loader.load_profile(verbose=True)


def create_user_profile_object(profile_data):
    """Create UserProfile object from profile data."""
    personal_info = profile_data.get('personal_information', {})
    income = profile_data.get('income', {})
    financial_pos = profile_data.get('financial_position', {})
    charitable = profile_data.get('charitable_giving', {})

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
        current_cash=financial_pos.get('liquid_assets', {}).get('cash', 0),
        exercise_reserves=profile_data.get('goals_and_constraints', {}).get('liquidity_needs', {}).get('exercise_reserves', 0),
        pledge_percentage=charitable.get('pledge_percentage', 0.5),
        company_match_ratio=charitable.get('company_match_ratio', 3.0),
        filing_status=personal_info.get('tax_filing_status', 'single'),
        state_of_residence=personal_info.get('state_of_residence', 'California')
    )


def create_exercise_before_expiry_scenario(profile_data):
    """
    Create scenario that exercises all options before expiry.

    Strategy:
    - Exercise all currently vested options in early 2025
    - Exercise options as they vest throughout the projection period
    - No sales or donations (hold everything after exercise)
    - Exercise timing optimized for latest possible before expiry
    """
    print("Creating Exercise Before Expiry scenario...")

    # Extract current position
    exercised_lots = profile_data.get('equity_position', {}).get('exercised_lots', [])
    vested_unexercised = profile_data.get('equity_position', {}).get('vested_unexercised', {})
    vesting_calendar = profile_data.get('equity_position', {}).get('unvested', {}).get('vesting_calendar', [])
    current_prices = profile_data.get('equity_position', {}).get('current_prices', {})

    # Set up projection period
    start_date = date(2025, 1, 1)
    end_date = date(2029, 12, 31)

    # Create initial lots (already exercised positions)
    initial_lots = []
    for lot_data in exercised_lots:
        exercise_date = datetime.fromisoformat(lot_data.get('exercise_date', '2024-01-01')).date()

        # Determine tax treatment based on exercise date
        months_held = (start_date.year - exercise_date.year) * 12 + (start_date.month - exercise_date.month)
        tax_treatment = TaxTreatment.LTCG if months_held >= 12 else TaxTreatment.STCG

        lot = ShareLot(
            lot_id=lot_data['lot_id'],
            share_type=ShareType.ISO if lot_data['type'] == 'ISO' else ShareType.NSO,
            quantity=lot_data['shares'],
            strike_price=lot_data['strike_price'],
            grant_date=exercise_date,
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=tax_treatment,
            exercise_date=exercise_date,
            cost_basis=lot_data.get('cost_basis', lot_data['strike_price']),
            amt_adjustment=lot_data.get('amt_adjustment', 0)
        )
        initial_lots.append(lot)

    # Add currently vested unexercised positions
    if vested_unexercised.get('iso_shares', 0) > 0:
        iso_lot = ShareLot(
            lot_id="VESTED_ISO",
            share_type=ShareType.ISO,
            quantity=vested_unexercised['iso_shares'],
            strike_price=5.00,
            grant_date=date(2020, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA
        )
        initial_lots.append(iso_lot)

    if vested_unexercised.get('nso_shares', 0) > 0:
        nso_lot = ShareLot(
            lot_id="VESTED_NSO",
            share_type=ShareType.NS
