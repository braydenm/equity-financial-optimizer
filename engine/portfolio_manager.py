"""
Portfolio Manager for multi-scenario execution.

This module manages portfolios of scenarios, where a portfolio is a collection
of scenarios that can be executed together for comparative analysis.
"""

import json
import os
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ProjectionPlan, PlannedAction, ShareLot, UserProfile,
    ShareType, LifecycleState, TaxTreatment, ActionType
)
from projections.projection_calculator import ProjectionCalculator
from projections.projection_output import save_all_projection_csvs, create_comparison_csv
from loaders.scenario_loader import ScenarioLoader
from loaders.csv_loader import CSVLoader


class PriceProjector:
    """Handles price projections using simple growth rates."""

    def __init__(self, price_scenarios_path: str = "data/market_assumptions/price_scenarios.json"):
        """Load price growth scenarios."""
        with open(price_scenarios_path, 'r') as f:
            self.scenarios_data = json.load(f)
        self.scenarios = self.scenarios_data['scenarios']
        self.default_scenario = self.scenarios_data.get('default_scenario', 'moderate')

    def project_prices(self, base_price: float, start_year: int, end_year: int,
                      scenario: str = None) -> Dict[int, float]:
        """
        Project prices using linear growth rate.

        Args:
            base_price: Starting price (from user profile)
            start_year: First year of projection
            end_year: Last year of projection
            scenario: Growth scenario name (default: from config)

        Returns:
            Dictionary of year -> projected price
        """
        if scenario is None:
            scenario = self.default_scenario

        if scenario not in self.scenarios:
            raise ValueError(f"Unknown price scenario: {scenario}")

        growth_rate = self.scenarios[scenario]['annual_growth_rate']
        prices = {}

        for year in range(start_year, end_year + 1):
            years_from_start = year - start_year
            prices[year] = base_price * ((1 + growth_rate) ** years_from_start)

        return prices


class Portfolio:
    """A collection of scenarios to execute together."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.scenario_paths: List[str] = []
        self.price_scenario = "moderate"  # Default price growth scenario
        self.projection_years = 8  # Minimum 5 years

    def add_scenario(self, scenario_path: str) -> None:
        """Add a scenario to the portfolio."""
        if not os.path.exists(scenario_path):
            raise FileNotFoundError(f"Scenario path not found: {scenario_path}")
        self.scenario_paths.append(scenario_path)

    def set_price_scenario(self, scenario: str) -> None:
        """Set the price growth scenario for all scenarios in portfolio."""
        self.price_scenario = scenario

    def set_projection_years(self, years: int) -> None:
        """Set projection period (minimum 5 years)."""
        self.projection_years = max(5, years)


class PortfolioManager:
    """
    Manages execution of scenario portfolios.

    A portfolio is a collection of scenar\
    """

    def __init__(self):
        self.csv_loader = CSVLoader()
        self.price_projector = PriceProjector()
        self._user_profile = None
        self._initial_lots = None

    def load_user_data(self, profile_path: str = "data/user_profile.json",
                      equity_timeline_path: str = "output/working/equity_position_timeline/equity_position_timeline.csv"):
        """Load user profile and initial equity position."""
        # Load user profile
        with open(profile_path, 'r') as f:
            profile_data = json.load(f)

        # Create UserProfile
        personal = profile_data['personal_information']
        income = profile_data['income']
        financial = profile_data['financial_position']
        goals = profile_data['goals_and_constraints']
        charitable = profile_data['charitable_giving']

        self._user_profile = UserProfile(
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

        # Store additional data we might need
        self._profile_data = profile_data

        # Load initial equity position
        self._initial_lots = self.csv_loader.load_initial_equity_position(equity_timeline_path)

        # Apply exercise dates from user profile to exercised lots
        self._apply_exercise_dates_from_profile()

        # Validate that all exercised lots now have exercise dates
        self.csv_loader.validate_exercise_dates(self._initial_lots)

        return self._user_profile, self._initial_lots

    def _apply_exercise_dates_from_profile(self):
        """Apply exercise dates from user profile to initial lots."""
        if not self._profile_data or not self._initial_lots:
            return

        exercised_lots_data = self._profile_data.get('equity_position', {}).get('exercised_lots', [])

        # Create mapping of lot_id to exercise_date
        exercise_dates = {}
        for lot_data in exercised_lots_data:
            lot_id = lot_data.get('lot_id')
            exercise_date_str = lot_data.get('exercise_date')
            if lot_id and exercise_date_str:
                from datetime import datetime
                exercise_dates[lot_id] = datetime.fromisoformat(exercise_date_str).date()

        # Apply exercise dates to matching lots
        for lot in self._initial_lots:
            if lot.lot_id in exercise_dates:
                lot.exercise_date = exercise_dates[lot.lot_id]

    def execute_single_scenario(self, scenario_path: str,
                              price_scenario: str = "moderate",
                              projection_years: int = 5,
                              output_dir: str = "output") -> Any:
        """
        Execute a single scenario.

        Args:
            scenario_path: Path to scenario directory containing actions.csv
            price_scenario: Name of price growth scenario to use
            projection_years: Years to project (minimum 5)
            output_dir: Directory for output files

        Returns:
            ProjectionResult
        """
        if not self._user_profile:
            self.load_user_data()

        # Create portfolio with single scenario
        portfolio = Portfolio("single_scenario")
        portfolio.add_scenario(scenario_path)
        portfolio.set_price_scenario(price_scenario)
        portfolio.set_projection_years(projection_years)

        results = self.execute_portfolio(portfolio, output_dir)
        return results[0] if results else None

    def execute_portfolio(self, portfolio: Portfolio,
                         output_dir: str = "output") -> List[Any]:
        """
        Execute all scenarios in a portfolio.

        Args:
            portfolio: Portfolio object with scenarios to execute
            output_dir: Base directory for output files

        Returns:
            List of ProjectionResult objects
        """
        if not self._user_profile:
            self.load_user_data()

        # Determine projection period (start of current year + projection_years)
        # Use start of year to include actions that may have already occurred
        today = date.today()
        start_date = date(today.year, 1, 1)
        end_date = date(start_date.year + portfolio.projection_years, 12, 31)

        # Get base price from user profile
        base_price = self._profile_data['equity_position']['current_prices']['last_409a_price']

        # Generate price projections
        price_projections = self.price_projector.project_prices(
            base_price=base_price,
            start_year=start_date.year,
            end_year=end_date.year,
            scenario=portfolio.price_scenario
        )

        # Initialize calculator
        calculator = ProjectionCalculator(self._user_profile)

        # Execute each scenario
        results = []
        for scenario_path in portfolio.scenario_paths:
            try:
                # Load scenario actions
                plan = self._load_scenario_plan(
                    scenario_path=scenario_path,
                    start_date=start_date,
                    end_date=end_date,
                    price_projections=price_projections
                )

                # Execute projection
                result = calculator.evaluate_projection_plan(plan)
                results.append(result)

                # Save outputs
                scenario_name = os.path.basename(scenario_path)
                scenario_output_dir = os.path.join(output_dir, scenario_name)
                save_all_projection_csvs(result, scenario_name, scenario_output_dir)

                print(f"✅ Executed scenario: {plan.name}")

            except Exception as e:
                print(f"❌ Error executing scenario {scenario_path}: {e}")
                import traceback
                traceback.print_exc()

        # Create comparison if multiple scenarios
        if len(results) > 1:
            comparison_path = os.path.join(output_dir, f"{portfolio.name}_comparison.csv")
            create_comparison_csv(results, comparison_path)
            print(f"✅ Created comparison: {comparison_path}")

        return results

    def _load_scenario_plan(self, scenario_path: str, start_date: date,
                          end_date: date, price_projections: Dict[int, float]) -> ProjectionPlan:
        """Load scenario and create projection plan."""
        # Load actions from CSV
        actions_path = os.path.join(scenario_path, "actions.csv")
        if not os.path.exists(actions_path):
            raise FileNotFoundError(f"Actions file not found: {actions_path}")

        # Get scenario name from directory
        scenario_name = os.path.basename(scenario_path).replace('_', ' ').title()

        # Create plan
        plan = ProjectionPlan(
            name=scenario_name,
            description=f"Scenario loaded from {scenario_path}",
            start_date=start_date,
            end_date=end_date,
            initial_lots=self._initial_lots.copy(),
            initial_cash=self._user_profile.current_cash,
            price_projections=price_projections
        )

        # Load actions
        import csv
        with open(actions_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows or comments
                if not row.get('action_date') or row['action_date'].strip().startswith('#'):
                    continue

                # Parse action date
                action_date = date.fromisoformat(row['action_date'])

                # Skip actions outside projection period
                if action_date < start_date or action_date > end_date:
                    continue

                # Create action with dynamic price determination
                action_type = ActionType(row['action_type'])
                lot_id = row['lot_id']
                quantity = int(row['quantity'])

                # Determine price based on action type and date
                price = None
                if row.get('price'):  # Allow manual override
                    price = float(row['price'])
                else:
                    price = self._determine_action_price(
                        action_type=action_type,
                        action_date=action_date,
                        lot_id=lot_id,
                        price_projections=price_projections
                    )

                action = PlannedAction(
                    action_date=action_date,
                    action_type=action_type,
                    lot_id=lot_id,
                    quantity=quantity,
                    price=price,
                    notes=row.get('notes', '')
                )
                plan.add_action(action)

        return plan

    def _determine_action_price(self, action_type: ActionType, action_date: date,
                               lot_id: str, price_projections: Dict[int, float]) -> float:
        """
        Determine the appropriate price for an action based on type and date.

        Price determination logic:
        - Exercise: Use strike price from the lot
        - Sell/Donate: Use price projection for the year
        - Tender: Check if date matches known tender offer
        """
        # For exercises, use the strike price from the lot
        if action_type == ActionType.EXERCISE:
            lot = next((lot for lot in self._initial_lots if lot.lot_id == lot_id), None)
            if lot:
                return lot.strike_price
            else:
                raise ValueError(f"Lot {lot_id} not found for exercise action")

        # For sales, check if this matches a known tender offer date
        if action_type == ActionType.SELL:
            # Check tender offers in user profile
            tender_date = self._profile_data['equity_position']['current_prices'].get('last_tender_offer_date')
            tender_price = self._profile_data['equity_position']['current_prices'].get('tender_offer_price')

            if tender_date and tender_price:
                # Parse tender date
                tender_date_obj = date.fromisoformat(tender_date)
                # Allow some flexibility (within 30 days)
                if abs((action_date - tender_date_obj).days) <= 30:
                    return tender_price

        # For sales and donations, use projected price for the year
        if action_type in [ActionType.SELL, ActionType.DONATE]:
            year = action_date.year
            if year in price_projections:
                return price_projections[year]
            else:
                # Extrapolate if beyond projection range
                last_year = max(price_projections.keys())
                if year > last_year:
                    # Continue growth rate
                    years_beyond = year - last_year
                    last_price = price_projections[last_year]
                    growth_rate = self.price_projector.scenarios[
                        self.price_projector.default_scenario
                    ]['annual_growth_rate']
                    return last_price * ((1 + growth_rate) ** years_beyond)
                else:
                    raise ValueError(f"No price projection available for year {year}")

        # Default: use current year projection
        return price_projections.get(action_date.year,
                                   self._profile_data['equity_position']['current_prices']['last_409a_price'])

    def create_portfolio_from_json(self, json_path: str) -> Portfolio:
        """Create a portfolio from a JSON definition file."""
        with open(json_path, 'r') as f:
            data = json.load(f)

        portfolio = Portfolio(
            name=data.get('name', 'unnamed_portfolio'),
            description=data.get('description', '')
        )

        # Add scenarios
        for scenario_path in data.get('scenarios', []):
            portfolio.add_scenario(scenario_path)

        # Set configuration
        if 'price_scenario' in data:
            portfolio.set_price_scenario(data['price_scenario'])

        if 'projection_years' in data:
            portfolio.set_projection_years(data['projection_years'])

        return portfolio


def execute_portfolio_from_json(json_path: str, output_dir: str = "output") -> List[Any]:
    """
    Convenience function to execute a portfolio defined in JSON.

    Args:
        json_path: Path to portfolio JSON file
        output_dir: Output directory for results

    Returns:
        List of ProjectionResult objects
    """
    manager = PortfolioManager()
    portfolio = manager.create_portfolio_from_json(json_path)
    return manager.execute_portfolio(portfolio, output_dir)


def execute_single_scenario(scenario_path: str,
                          price_scenario: str = "moderate",
                          projection_years: int = 5,
                          output_dir: str = "output") -> Any:
    """
    Convenience function to execute a single scenario.

    Args:
        scenario_path: Path to scenario directory
        price_scenario: Price growth assumption
        projection_years: Years to project
        output_dir: Output directory

    Returns:
        ProjectionResult
    """
    manager = PortfolioManager()
    return manager.execute_single_scenario(
        scenario_path=scenario_path,
        price_scenario=price_scenario,
        projection_years=projection_years,
        output_dir=output_dir
    )
