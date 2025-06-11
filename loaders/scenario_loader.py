"""
Scenario loader for CSV-based scenario definitions.

This module provides functionality to load projection scenarios from
structured CSV and JSON files, enabling data-driven scenario construction.
"""

import json
import csv
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import sys
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ProjectionPlan, PlannedAction, ShareLot, UserProfile,
    ShareType, LifecycleState, TaxTreatment, ActionType
)
from loaders.csv_loader import CSVLoader


class ScenarioLoader:
    """Load projection scenarios from CSV/JSON configuration files."""

    def __init__(self, scenario_dir: str):
        """
        Initialize scenario loader with a scenario directory.

        Args:
            scenario_dir: Path to directory containing scenario files
        """
        self.scenario_dir = Path(scenario_dir)
        self.csv_loader = CSVLoader()

    def load_scenario(self) -> Tuple[ProjectionPlan, UserProfile]:
        """
        Load a complete scenario from configuration files.

        Returns:
            Tuple of (ProjectionPlan, UserProfile)
        """
        # Load scenario configuration
        config_path = self.scenario_dir / "scenario_config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Scenario config not found: {config_path}")

        with open(config_path, 'r') as f:
            config = json.load(f)

        # Load user profile
        profile_path = self.scenario_dir / config['data_sources']['user_profile']
        profile = self._load_user_profile(profile_path)

        # Load initial equity position
        equity_path = self.scenario_dir / config['data_sources']['equity_timeline']
        initial_lots = self._load_initial_lots(equity_path)

        # Create projection plan
        metadata = config['scenario_metadata']
        settings = config['projection_settings']

        plan = ProjectionPlan(
            name=metadata['name'],
            description=metadata['description'],
            start_date=datetime.strptime(settings['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(settings['end_date'], '%Y-%m-%d').date(),
            initial_lots=initial_lots,
            initial_cash=settings['initial_cash'],
            price_projections={int(year): price for year, price in settings['price_projections'].items()}
        )

        # Load and add planned actions
        actions_path = self.scenario_dir / config['data_sources']['actions']
        if actions_path.exists():
            actions = self._load_actions(actions_path)
            for action in actions:
                plan.add_action(action)

        return plan, profile

    def _load_user_profile(self, profile_path: Path) -> UserProfile:
        """Load user profile from JSON file."""
        profile_path = profile_path.resolve()

        if not profile_path.exists():
            raise FileNotFoundError(f"User profile not found: {profile_path}")

        with open(profile_path, 'r') as f:
            data = json.load(f)

        # Extract relevant fields from v2.0 profile format
        personal = data['personal_information']
        income = data['income']
        financial = data['financial_position']
        goals = data['goals_and_constraints']
        charitable = data['charitable_giving']

        return UserProfile(
            ordinary_income_rate=personal['ordinary_income_rate'],
            ltcg_rate=personal['ltcg_rate'],
            stcg_rate=personal['stcg_rate'],
            annual_w2_income=income['annual_w2_income'],
            spouse_w2_income=income['spouse_w2_income'],
            other_income=income['interest_income'] + income['other_income'] + income['dividend_income'],
            current_cash=financial['liquid_assets']['cash'],
            exercise_reserves=goals['liquidity_needs']['exercise_reserves'],
            pledge_percentage=charitable['pledge_percentage'],
            company_match_ratio=charitable['company_match_ratio'],
            filing_status=personal['tax_filing_status'],
            state_of_residence=personal['state_of_residence']
        )

    def _load_initial_lots(self, equity_path: Path) -> List[ShareLot]:
        """Load initial equity position from CSV timeline."""
        equity_path = equity_path.resolve()

        if not equity_path.exists():
            raise FileNotFoundError(f"Equity timeline not found: {equity_path}")

        lots = []
        seen_lots = set()

        with open(equity_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lot_id = row['lot_id']

                # Only include each lot once (use first occurrence)
                if lot_id in seen_lots:
                    continue
                seen_lots.add(lot_id)

                # Only include lots that are vested or exercised at start
                lifecycle_state = LifecycleState(row['lifecycle_state'])
                if lifecycle_state not in [LifecycleState.VESTED_NOT_EXERCISED,
                                          LifecycleState.EXERCISED_NOT_DISPOSED]:
                    continue

                # Create ShareLot
                lot = ShareLot(
                    lot_id=lot_id,
                    share_type=ShareType(row['share_type']),
                    quantity=int(row['quantity']),
                    strike_price=float(row['strike_price']),
                    grant_date=datetime.strptime(row['date'], '%Y-%m-%d').date(),
                    lifecycle_state=lifecycle_state,
                    tax_treatment=TaxTreatment(row['tax_treatment'])
                )

                # For exercised lots, exercise date must be provided in the data
                if lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED:
                    # Exercise date MUST be provided - no fallbacks allowed
                    raise ValueError(
                        f"Exercise date missing for exercised lot '{lot_id}'. "
                        f"Exercised lots must have exercise_date specified in the equity timeline data. "
                        f"Add an 'exercise_date' column to the CSV or load exercise dates from user_profile.json. "
                        f"This ensures accurate tax treatment and holding period calculations."
                    )

                lots.append(lot)

        return lots

    def _load_actions(self, actions_path: Path) -> List[PlannedAction]:
        """Load planned actions from CSV file."""
        actions = []

        with open(actions_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                action = PlannedAction(
                    action_date=datetime.strptime(row['action_date'], '%Y-%m-%d').date(),
                    action_type=ActionType(row['action_type']),
                    lot_id=row['lot_id'],
                    quantity=int(row['quantity']),
                    price=float(row['price']) if row['price'] else None,
                    notes=row.get('notes', '')
                )
                actions.append(action)

        return actions


def load_scenario_from_directory(scenario_dir: str) -> Tuple[ProjectionPlan, UserProfile]:
    """
    Convenience function to load a scenario from a directory.

    Args:
        scenario_dir: Path to scenario directory

    Returns:
        Tuple of (ProjectionPlan, UserProfile)
    """
    loader = ScenarioLoader(scenario_dir)
    return loader.load_scenario()
