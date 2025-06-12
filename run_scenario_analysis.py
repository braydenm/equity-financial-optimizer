#!/usr/bin/env python3
"""
Scenario Analysis - Main CLI for single equity optimization scenario execution.

Execute and analyze individual equity optimization scenarios.
"""

import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from engine.portfolio_manager import PortfolioManager


def print_scenario_results(result, detailed=True):
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


def execute_scenario(scenario_path, price_scenario="moderate", projection_years=5, use_demo=False):
    """Execute and display a single scenario."""
    manager = PortfolioManager()
    manager.load_user_data(force_demo=use_demo)

    print(f"\nExecuting scenario: {scenario_path}")
    print(f"Price assumption: {price_scenario} ({projection_years} years)")

    result = manager.execute_single_scenario(
        scenario_path=scenario_path,
        price_scenario=price_scenario,
        projection_years=projection_years
    )

    print_scenario_results(result, detailed=True)
    return result


def list_available_scenarios():
    """List available scenario files."""
    print("EQUITY FINANCIAL OPTIMIZER - SCENARIO ANALYSIS")
    print("="*80)

    print("Available scenarios:")

    # Show demo scenarios
    demo_scenarios_dir = Path("scenarios/demo")
    if demo_scenarios_dir.exists():
        print("  Demo scenarios (safe example data):")
        for scenario_file in sorted(demo_scenarios_dir.glob("*_actions.csv")):
            scenario_name = scenario_file.name.replace("_actions.csv", "")
            print(f"    • {scenario_name}")
    else:
        print("  Demo scenarios: Not found")

    # Show user scenarios
    user_scenarios_dir = Path("scenarios/user")
    if user_scenarios_dir.exists():
        print("  User scenarios (your personal data):")
        for scenario_file in sorted(user_scenarios_dir.glob("*_actions.csv")):
            scenario_name = scenario_file.name.replace("_actions.csv", "")
            print(f"    • {scenario_name}")
    else:
        print("  User scenarios: Not configured")

    print("\nData sources:")
    user_profile_exists = Path("data/user_profile.json").exists()
    demo_profile_exists = Path("data/demo_profile.json").exists()

    if user_profile_exists:
        print("  🔒 User profile configured (will use your personal data)")
    else:
        print("  ⚠️  User profile not found (will use demo data)")

    if demo_profile_exists:
        print("  🧪 Demo profile available (safe example data)")
    else:
        print("  ❌ Demo profile missing")

    print("\nUsage examples:")
    print("  python run_scenario_analysis.py 001_exercise_all_vested")
    print("  python run_scenario_analysis.py 000_natural_evolution --demo")
    print("  python run_scenario_analysis.py 002_tender_and_donate --price aggressive --years 7")


def main():
    """Main entry point for scenario analysis."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Execute single equity optimization scenario analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 001_exercise_all_vested
  %(prog)s 000_natural_evolution --demo
  %(prog)s 002_tender_and_donate --price aggressive --years 7
        """
    )

    parser.add_argument('scenario', nargs='?', help='Scenario name (e.g., 001_exercise_all_vested)')
    parser.add_argument('--price', default='moderate',
                       choices=['conservative', 'moderate', 'aggressive', 'flat', 'historical_tech'],
                       help='Price growth scenario (default: moderate)')
    parser.add_argument('--years', type=int, default=5, help='Projection years (default: 5)')
    parser.add_argument('--demo', action='store_true',
                       help='Force use of demo data (safe example data)')

    args = parser.parse_args()

    if args.scenario:
        execute_scenario(args.scenario, args.price, args.years, args.demo)
    else:
        list_available_scenarios()


if __name__ == "__main__":
    main()
