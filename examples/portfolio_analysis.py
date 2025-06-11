#!/usr/bin/env python3
"""
Portfolio Analysis - Execute and compare equity optimization scenarios.

This script demonstrates the portfolio-based approach to scenario analysis,
where scenarios are defined in CSV files and executed with shared assumptions.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.portfolio_manager import PortfolioManager, Portfolio
from projections.projection_output import create_comparison_csv


def print_scenario_results(result, detailed=False):
    """Print formatted results for a scenario."""
    metrics = result.summary_metrics
    final_state = result.get_final_state()

    print(f"\n{'='*80}")
    print(f"SCENARIO: {result.plan.name}")
    print(f"{'='*80}")

    # Financial outcomes
    print(f"\nFINAL STATE ({final_state.year}):")
    print(f"  💰 Cash Position: ${metrics['total_cash_final']:,.0f}")
    print(f"  📊 Equity Value: ${metrics['total_equity_value_final']:,.0f}")
    print(f"  💎 Total Net Worth: ${metrics['total_cash_final'] + metrics['total_equity_value_final']:,.0f}")

    # Cumulative metrics
    print(f"\nCUMULATIVE METRICS:")
    print(f"  💸 Total Taxes Paid: ${metrics['total_taxes_all_years']:,.0f}")
    print(f"  🎁 Total Donations: ${metrics['total_donations_all_years']:,.0f}")
    print(f"  📋 Outstanding Pledge: ${metrics['outstanding_obligation']:,.0f}")
    print(f"  ✅ Pledge Fulfillment: {metrics['pledge_fulfillment_maximalist']:.1%}")

    if detailed and final_state:
        # Equity position details
        vested_unexercised = sum(lot.quantity for lot in final_state.equity_holdings
                                if lot.lifecycle_state.value == 'vested_not_exercised')
        exercised_shares = sum(lot.quantity for lot in final_state.equity_holdings
                              if lot.lifecycle_state.value == 'exercised_not_disposed')

        print(f"\nEQUITY POSITION:")
        print(f"  🎯 Vested Unexercised: {vested_unexercised:,} shares")
        print(f"  ✅ Exercised Shares: {exercised_shares:,} shares")

        # Year-by-year cash flow
        print(f"\nCASH FLOW SUMMARY:")
        print(f"  {'Year':<6} {'Income':>12} {'Exercise':>12} {'Taxes':>12} {'Ending Cash':>12}")
        print(f"  {'-'*60}")
        for state in result.yearly_states[-3:]:  # Last 3 years
            print(f"  {state.year:<6} ${state.income:>11,.0f} ${state.exercise_costs:>11,.0f} "
                  f"${state.tax_paid:>11,.0f} ${state.ending_cash:>11,.0f}")


def compare_scenarios(results):
    """Print comparison table of scenario results."""
    if len(results) < 2:
        return

    print(f"\n{'='*80}")
    print("SCENARIO COMPARISON")
    print(f"{'='*80}")

    # Header
    print(f"\n{'Scenario':<30} {'Net Worth':>12} {'Cash':>12} {'Taxes':>12} {'Donations':>12}")
    print(f"{'-'*80}")

    # Results
    for result in results:
        metrics = result.summary_metrics
        net_worth = metrics['total_cash_final'] + metrics['total_equity_value_final']
        print(f"{result.plan.name:<30} ${net_worth:>11,.0f} ${metrics['total_cash_final']:>11,.0f} "
              f"${metrics['total_taxes_all_years']:>11,.0f} ${metrics['total_donations_all_years']:>11,.0f}")

    # Key insights vs baseline
    if len(results) >= 2:
        baseline = results[0].summary_metrics
        baseline_nw = baseline['total_cash_final'] + baseline['total_equity_value_final']

        print(f"\nKEY INSIGHTS vs {results[0].plan.name}:")
        for result in results[1:]:
            metrics = result.summary_metrics
            net_worth = metrics['total_cash_final'] + metrics['total_equity_value_final']
            nw_diff = net_worth - baseline_nw
            tax_diff = metrics['total_taxes_all_years'] - baseline['total_taxes_all_years']

            print(f"\n{result.plan.name}:")
            print(f"  • Net Worth Impact: ${nw_diff:+,.0f} ({nw_diff/baseline_nw:+.1%})")
            print(f"  • Additional Taxes: ${tax_diff:+,.0f}")
            if metrics['total_donations_all_years'] > 0:
                print(f"  • Charitable Impact: ${metrics['total_donations_all_years']:,.0f}")


def execute_single_scenario(scenario_path, price_scenario="moderate", projection_years=5):
    """Execute and display a single scenario."""
    manager = PortfolioManager()
    manager.load_user_data()

    print(f"\nExecuting scenario: {scenario_path}")
    print(f"Price assumption: {price_scenario} ({projection_years} years)")

    result = manager.execute_single_scenario(
        scenario_path=scenario_path,
        price_scenario=price_scenario,
        projection_years=projection_years
    )

    print_scenario_results(result, detailed=True)
    return result


def execute_portfolio(portfolio_path, output_dir="output/portfolios"):
    """Execute all scenarios in a portfolio."""
    manager = PortfolioManager()
    manager.load_user_data()

    # Load portfolio definition
    portfolio = manager.create_portfolio_from_json(portfolio_path)

    print(f"\nEXECUTING PORTFOLIO: {portfolio.name}")
    print("="*80)
    print(f"{portfolio.description}")
    print(f"\nScenarios: {len(portfolio.scenario_paths)}")
    print(f"Price Scenario: {portfolio.price_scenario}")
    print(f"Projection Years: {portfolio.projection_years}")

    # Execute all scenarios
    results = manager.execute_portfolio(portfolio, output_dir)

    # Print individual results
    for result in results:
        print_scenario_results(result)

    # Print comparison
    compare_scenarios(results)

    print(f"\n✅ Portfolio analysis complete")
    print(f"📁 Results saved to: {output_dir}")

    return results




def main():
    """Main entry point for portfolio analysis."""
    import argparse

    parser = argparse.ArgumentParser(description='Execute equity optimization scenarios')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Single scenario command
    single_parser = subparsers.add_parser('scenario', help='Execute a single scenario')
    single_parser.add_argument('path', help='Path to scenario directory')
    single_parser.add_argument('--price', default='moderate',
                              choices=['conservative', 'moderate', 'aggressive', 'flat', 'historical_tech'],
                              help='Price growth scenario')
    single_parser.add_argument('--years', type=int, default=5, help='Projection years')

    # Portfolio command
    portfolio_parser = subparsers.add_parser('portfolio', help='Execute a portfolio')
    portfolio_parser.add_argument('path', help='Path to portfolio JSON file')
    portfolio_parser.add_argument('--output', default='output/portfolios', help='Output directory')

    # Quick start command
    demo_parser = subparsers.add_parser('demo', help='Run demonstration analysis')

    args = parser.parse_args()

    if args.command == 'scenario':
        execute_single_scenario(args.path, args.price, args.years)

    elif args.command == 'portfolio':
        execute_portfolio(args.path, args.output)

    elif args.command == 'demo':
        # Run a quick demonstration
        print("EQUITY FINANCIAL OPTIMIZER - DEMONSTRATION")
        print("="*80)

        # Create a simple portfolio using new numbered scenario format
        demo_portfolio = Portfolio("Quick Demo", "Compare baseline with exercise strategies")
        demo_portfolio.add_scenario("000_natural_evolution")
        demo_portfolio.add_scenario("001_exercise_all_vested")

        # Execute
        manager = PortfolioManager()
        manager.load_user_data()
        results = manager.execute_portfolio(demo_portfolio, "output/demo")

        # Show comparison
        compare_scenarios(results)

    else:
        # Default: show available scenarios and portfolios
        print("EQUITY FINANCIAL OPTIMIZER")
        print("="*80)
        print("Available scenarios:")

        # Show demo scenarios
        demo_scenarios_dir = Path("scenarios/demo")
        if demo_scenarios_dir.exists():
            print("  Demo scenarios (safe example data):")
            for scenario_file in sorted(demo_scenarios_dir.glob("*_actions.csv")):
                scenario_name = scenario_file.name.replace("_actions.csv", "")
                print(f"    • {scenario_name}")

        # Show user scenarios
        user_scenarios_dir = Path("scenarios/user")
        if user_scenarios_dir.exists():
            print("  User scenarios (your personal data):")
            for scenario_file in sorted(user_scenarios_dir.glob("*_actions.csv")):
                scenario_name = scenario_file.name.replace("_actions.csv", "")
                print(f"    • {scenario_name}")
        else:
            print("  User scenarios: Not configured (using demo scenarios)")

        print("\nAvailable portfolios:")
        portfolios_dir = Path("portfolios")
        if portfolios_dir.exists():
            for portfolio in sorted(portfolios_dir.glob("*.json")):
                print(f"  • {portfolio.name}")

        print("\nUsage examples:")
        print("  python portfolio_analysis.py scenario 001_exercise_all_vested")
        print("  python portfolio_analysis.py portfolio portfolios/tax_strategies.json")
        print("  python portfolio_analysis.py demo")


if __name__ == "__main__":
    main()
