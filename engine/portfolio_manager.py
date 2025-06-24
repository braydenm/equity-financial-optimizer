"""
Portfolio Manager for multi-scenario execution.

This module manages portfolios of scenarios, where a portfolio is a collection
of scenarios that can be executed together for comparative analysis.
"""

import json
import os
from datetime import date, datetime, timedelta
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
from loaders.profile_loader import ProfileLoader
from loaders.equity_loader import EquityLoader
from engine.timeline_generator import TimelineGenerator


class PriceProjector:
    """Handles price projections using simple growth rates."""

    def __init__(self, price_scenarios_path: str = "input_data/market_assumptions/price_scenarios.json"):
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
        # New format: just scenario name like "001_exercise_all_vested"
        # Store the scenario name, resolution will happen at execution time
        # when we know the data source (demo vs user)
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
        self.price_projector = PriceProjector()
        self.profile_loader = ProfileLoader()
        self.timeline_generator = TimelineGenerator()
        self.equity_loader = EquityLoader()
        self._user_profile = None
        self._initial_lots = None
        self._data_source = None  # Track whether using 'demo' or 'user' data
        self._current_price_scenario = None  # Track current price scenario

    def load_user_data(self, profile_path: str = "input_data/user_profile.json",
                      equity_timeline_path: str = None,
                      force_demo: bool = False):
        """Load user profile and initial equity position with secure fallback to demo data."""
        # Load user profile with secure fallback
        profile_data, is_real_data = self.profile_loader.load_profile(verbose=True, force_demo=force_demo)

        # Track data source for output path generation
        self._data_source = "user" if is_real_data else "demo"
        is_demo = not is_real_data

        # Generate timeline for CSV output visualization (not for loading)
        generated_timeline_path = self.timeline_generator.generate_timeline(profile_data, is_demo=is_demo)

        # Store profile data for later use
        self._profile_data = profile_data
        # Create UserProfile
        personal = profile_data['personal_information']
        income = profile_data['income']
        financial = profile_data['financial_position']
        goals = profile_data['goals_and_constraints']
        charitable = profile_data['charitable_giving']
        tax_situation = profile_data.get('tax_situation', {})
        estimated_taxes = tax_situation.get('estimated_taxes', {})
        carryforwards = tax_situation.get('carryforwards', {})
        monthly_cash_flow = financial.get('monthly_cash_flow', {})

        # Parse assumed_ipo date if present
        assumed_ipo = None
        if 'assumed_ipo' in profile_data:
            assumed_ipo = date.fromisoformat(profile_data['assumed_ipo'])

        self._user_profile = UserProfile(
            federal_tax_rate=personal['federal_tax_rate'],
            federal_ltcg_rate=personal['federal_ltcg_rate'],
            state_tax_rate=personal['state_tax_rate'],
            state_ltcg_rate=personal['state_ltcg_rate'],
            fica_tax_rate=personal['fica_tax_rate'],
            additional_medicare_rate=personal['additional_medicare_rate'],
            niit_rate=personal['niit_rate'],
            annual_w2_income=income['annual_w2_income'],
            spouse_w2_income=income.get('spouse_w2_income', 0),
            other_income=income.get('other_income', 0),
            interest_income=income.get('interest_income', 0),
            dividend_income=income.get('dividend_income', 0),
            bonus_expected=income.get('bonus_expected', 0),
            current_cash=financial['liquid_assets']['cash'],
            exercise_reserves=goals['liquidity_needs']['exercise_reserves'],
            pledge_percentage=charitable['pledge_percentage'],
            company_match_ratio=charitable['company_match_ratio'],
            filing_status=personal['tax_filing_status'],
            state_of_residence=personal['state_of_residence'],
            monthly_living_expenses=monthly_cash_flow.get('expenses', 0),
            regular_income_withholding_rate=estimated_taxes.get('regular_income_withholding_rate', 0.0),
            supplemental_income_withholding_rate=estimated_taxes.get('supplemental_income_withholding_rate', 0.0),
            quarterly_payments=estimated_taxes.get('quarterly_payments', 0),
            taxable_investments=financial['liquid_assets'].get('taxable_investments', 0),
            crypto=financial['liquid_assets'].get('crypto', 0),
            real_estate_equity=financial['illiquid_assets'].get('real_estate_equity', 0),
            amt_credit_carryforward=carryforwards.get('amt_credit', 0),
            assumed_ipo=assumed_ipo
        )

        # Store additional data we might need
        self._profile_data = profile_data

        # Load initial lots directly from profile data
        self._initial_lots = self.equity_loader.load_lots_from_profile(profile_data)

        # Log loading summary
        summary = self.equity_loader.summarize_lots(self._initial_lots)
        print(f"📊 Loaded {summary['total_lots']} lots with {summary['total_shares']} total shares from profile")
        print(f"   - By state: {summary['by_lifecycle_state']}")
        print(f"   - By type: {summary['by_share_type']}")

        return self._user_profile, self._initial_lots





    def execute_single_scenario(self, scenario_path: str,
                              price_scenario: str = "moderate",
                              projection_years: int = 5,
                              output_dir: str = None) -> Any:
        """
        Execute a single scenario.

        Args:
            scenario_path: Path to scenario directory containing actions.csv
            price_scenario: Name of price growth scenario to use
            projection_years: Years to project (minimum 5)
            output_dir: Directory for output files (optional, auto-generated if not provided)

        Returns:
            ProjectionResult
        """
        if not self._user_profile:
            self.load_user_data()

        # Store current price scenario for output path generation
        self._current_price_scenario = price_scenario

        # Resolve scenario path
        resolved_path = self._resolve_scenario_path(scenario_path)

        # Generate scenario name for output
        scenario_name = os.path.basename(resolved_path)
        if scenario_name.endswith('_actions.csv'):
            scenario_name = scenario_name[:-12]  # Remove "_actions.csv"

        # Generate proper output directory if not provided
        if output_dir is None:
            output_dir = self._generate_output_path(scenario_name, price_scenario)

        # Create portfolio with single scenario
        portfolio = Portfolio("single_scenario")
        portfolio.add_scenario(scenario_path)
        portfolio.set_price_scenario(price_scenario)
        portfolio.set_projection_years(projection_years)

        # Execute as single-scenario portfolio
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

        # Execute each scenario
        results = []
        for scenario_path in portfolio.scenario_paths:
            try:
                # Resolve scenario path based on data source
                resolved_path = self._resolve_scenario_path(scenario_path)

                # Load scenario actions
                plan = self._load_scenario_plan(
                    scenario_path=resolved_path,
                    start_date=start_date,
                    end_date=end_date,
                    price_projections=price_projections
                )

                # Initialize calculator
                calculator = ProjectionCalculator(self._user_profile)

                # Execute projection
                result = calculator.evaluate_projection_plan(plan)
                results.append(result)

                # Generate proper output path with data source and price scenario
                scenario_name = os.path.basename(resolved_path)
                if scenario_name.endswith('.json'):
                    scenario_name = scenario_name[:-5]  # Remove ".json"

                scenario_output_dir = self._generate_output_path(scenario_name, portfolio.price_scenario)

                # Create output directory
                os.makedirs(scenario_output_dir, exist_ok=True)

                # Generate and save metadata
                metadata = self._generate_scenario_metadata(scenario_name, portfolio.price_scenario)
                metadata_path = os.path.join(scenario_output_dir, "metadata.json")
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

                # Save projection outputs
                save_all_projection_csvs(result, scenario_name, scenario_output_dir)

                print(f"✅ Executed scenario: {plan.name}")

            except Exception as e:
                print(f"❌ Error executing scenario {scenario_path}: {e}")
                import traceback
                traceback.print_exc()

        # Create comparison if multiple scenarios
        if len(results) > 1:
            # Create portfolio comparison directory
            portfolio_comparison_dir = f"output/{self._data_source}/portfolio_comparisons"
            os.makedirs(portfolio_comparison_dir, exist_ok=True)

            comparison_filename = f"{portfolio.price_scenario}_{portfolio.name.lower().replace(' ', '_')}_comparison.csv"
            comparison_path = os.path.join(portfolio_comparison_dir, comparison_filename)
            create_comparison_csv(results, comparison_path)
            print(f"✅ Created comparison: {comparison_path}")

        return results

    def _load_scenario_plan(self, scenario_path: str, start_date: date,
                          end_date: date, price_projections: Dict[int, float]) -> ProjectionPlan:
        """Load scenario and create projection plan."""
        # New format: scenarios/{data_source}/001_exercise_all_vested.json
        scenario_base = os.path.basename(scenario_path)
        if not scenario_base.endswith('.json'):
            scenario_base = f"{scenario_base}.json"

        actions_path = os.path.join(self._get_scenario_directory(), scenario_base)
        # Extract clean scenario name (remove number prefix and .json suffix)
        scenario_name = scenario_base.replace('.json', '')
        if scenario_name[:4].isdigit() and scenario_name[3] == '_':
            scenario_name = scenario_name[4:]  # Remove "001_" prefix
        scenario_name = scenario_name.replace('_', ' ').title()

        if not os.path.exists(actions_path):
            raise FileNotFoundError(f"Actions file not found: {actions_path}")

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

        # Load actions from JSON
        with open(actions_path, 'r') as f:
            scenario_data = json.load(f)

        # Update plan name and description from JSON if available
        if 'scenario_name' in scenario_data:
            scenario_name = scenario_data['scenario_name'].replace('_', ' ').title()
        if 'description' in scenario_data:
            plan.description = scenario_data['description']

        # Load tax elections if present
        if 'tax_elections' in scenario_data:
            plan.tax_elections = scenario_data['tax_elections']

        # Process actions
        for action_data in scenario_data.get('actions', []):
            # Parse action date
            action_date = date.fromisoformat(action_data['action_date'])

            # Skip actions outside projection period
            if action_date < start_date or action_date > end_date:
                print(f"⚠️  Warning: Skipping action on {action_date} in scenario '{scenario_name}' (outside projection period {start_date} to {end_date})")
                continue

            # Create action with dynamic price determination
            action_type = ActionType(action_data['action_type'])
            lot_id = action_data['lot_id']
            quantity = int(action_data['quantity'])

            # Determine price based on action type and date
            price = action_data.get('price')
            if price is None:  # Use dynamic pricing if not specified
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
                notes=action_data.get('notes', '')
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

    def _generate_output_path(self, scenario_name: str, price_scenario: str = "moderate") -> str:
        """Generate output path with data source and price scenario."""
        # Extract scenario number and name from filename (e.g., "001_exercise_all_vested" -> "scenario_001_exercise_all_vested")
        if scenario_name.endswith('.json'):
            scenario_name = scenario_name[:-5]  # Remove ".json"

        scenario_dir = f"scenario_{scenario_name}"
        return f"output/{self._data_source}/{price_scenario}/{scenario_dir}"

    def _generate_scenario_metadata(self, scenario_name: str, price_scenario: str = "moderate") -> Dict[str, Any]:
        """Generate metadata for scenario execution."""
        base_price = self._profile_data['equity_position']['current_prices']['last_409a_price']

        return {
            "data_source": f"{self._data_source}_profile",
            "price_scenario": price_scenario,
            "scenario_name": scenario_name,
            "generated_timestamp": datetime.now().isoformat(),
            "profile_version": self._profile_data.get('metadata', {}).get('profile_version', 'unknown'),
            "base_409a_price": base_price,
            "projection_years": 5,  # Default, should be parameterized
            "data_source_type": "real_user_data" if self._data_source == "user" else "demo_data"
        }

    def _get_scenario_directory(self) -> str:
        """Get the appropriate scenario directory based on data source."""
        return f"scenarios/{self._data_source}"

    def _resolve_scenario_path(self, scenario_path: str) -> str:
        """Resolve scenario path based on data source and naming convention."""
        # Resolve scenario name to appropriate data source directory
        scenario_name = scenario_path
        if not scenario_name.endswith(".json"):
            scenario_name = f"{scenario_name}.json"

        return os.path.join(self._get_scenario_directory(), scenario_name)

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
