#!/usr/bin/env python3
"""
Portfolio Analysis - Main CLI for equity optimization portfolio execution.

Execute and compare multiple equity optimization scenarios defined in portfolios.
"""

import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
    if 'outstanding_obligation' in metrics:
        print(f"  📋 Outstanding Pledge: ${metrics['outstanding_obligation']:,.0f}")
    if 'pledge_fulfillment_maximalist' in metrics:
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


def execute_portfolio(portfolio_path, output_dir=None, use_demo=False):
    """Execute all scenarios in a portfolio."""
    manager = PortfolioManager()
    manager.load_user_data(force_demo=use_demo)

    # Load portfolio definition
    portfolio = manager.create_portfolio_from_json(portfolio_path)

    print(f"\nEXECUTING PORTFOLIO: {portfolio.name}")
    print("="*80)
    print(f"{portfolio.description}")
    print(f"\nScenarios: {len(portfolio.scenario_paths)}")
    print(f"Price Scenario: {portfolio.price_scenario}")
    print(f"Projection Years: {portfolio.projection_years}")

    # Use default output directory if not specified
    if output_dir is None:
        output_dir = "output/portfolios"

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


def list_available_portfolios():
    """List available portfolio files."""
    print("EQUITY FINANCIAL OPTIMIZER - PORTFOLIO ANALYSIS")
    print("="*80)

    print("\nAvailable portfolios:")
    portfolios_dir = Path("portfolios")
    if portfolios_dir.exists():
        for portfolio in sorted(portfolios_dir.glob("*.json")):
            print(f"  • {portfolio.name}")
    else:
        print("  No portfolios found in portfolios/ directory")

    print("\nData sources:")
    user_profile_exists = Path("data/user_profile.json").exists()
    demo_profile_exists = Path("data/demo_profile.json").exists()

    if user_profile_exists:
        print("  🔒 User profile configured (will use your personal data)")
    else:
        print("  ⚠️  User profile not found")

    if demo_profile_exists:
        print("  🧪 Demo profile available (safe example data)")
    else:
        print("  ❌ Demo profile missing")

    print("\nUsage examples:")
    print("  python run_portfolio_analysis.py portfolios/tax_strategies.json")
    print("  python run_portfolio_analysis.py portfolios/tax_strategies.json --demo")
    print("  python run_portfolio_analysis.py portfolios/tax_strategies.json --output custom_output/")


def main():
    """Main entry point for portfolio analysis."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Execute equity optimization portfolio analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s portfolios/tax_strategies.json
  %(prog)s portfolios/tax_strategies.json --demo
  %(prog)s portfolios/tax_strategies.json --output custom_results/
        """
    )

    parser.add_argument('portfolio', nargs='?', help='Path to portfolio JSON file')
    parser.add_argument('--demo', action='store_true',
                       help='Force use of demo data (safe example data)')
    parser.add_argument('--output', help='Output directory for results')

    args = parser.parse_args()

    if args.portfolio:
        execute_portfolio(args.portfolio, args.output, args.demo)
    else:
        list_available_portfolios()


if __name__ == "__main__":
    main()
