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

    # Charitable impact details
    if 'total_charitable_impact_all_years' in metrics:
        print(f"  🤝 Total Charitable Impact: ${metrics['total_charitable_impact_all_years']:,.0f}")
        if 'total_company_match_all_years' in metrics:
            personal_value = metrics.get('total_donations_all_years', 0)
            match_value = metrics.get('total_company_match_all_years', 0)
            print(f"     (Personal: ${personal_value:,.0f} + Company Match: ${match_value:,.0f})")

    # Pledge status
    if 'pledge_shares_obligated' in metrics and metrics['pledge_shares_obligated'] > 0:
        obligated = metrics['pledge_shares_obligated']
        donated = metrics.get('pledge_shares_donated', 0)
        outstanding = metrics.get('pledge_shares_outstanding', 0)
        expired = metrics.get('pledge_shares_expired_window', 0)
        fulfillment_rate = donated / obligated if obligated > 0 else 0

        print(f"  📊 Pledge Status:")
        print(f"     Obligated: {obligated:,.0f} shares")
        print(f"     Donated: {donated:,.0f} shares ({fulfillment_rate:.1%})")
        print(f"     Outstanding: {outstanding:,.0f} shares")
        if expired > 0:
            print(f"     ⚠️  Expired Window: {expired:,.0f} shares (lost match opportunity)")
        if 'outstanding_obligation' in metrics and metrics['outstanding_obligation'] > 0:
            print(f"     💵 Outstanding Shares: {metrics['outstanding_obligation']:,.0f} shares")

    # Option expiration
    if 'expired_option_count' in metrics and metrics['expired_option_count'] > 0:
        print(f"  ⏰ Expired Options: {metrics['expired_option_count']:,.0f} shares")
        if 'expired_option_loss' in metrics:
            print(f"     💸 Lost Value: ${metrics['expired_option_loss']:,.0f}")

    # Tax efficiency
    if 'amt_credits_final' in metrics and metrics['amt_credits_final'] > 0:
        print(f"  💳 AMT Credits Remaining: ${metrics['amt_credits_final']:,.0f}")

    # Expired charitable deductions
    if 'expired_charitable_deduction' in metrics and metrics['expired_charitable_deduction'] > 0:
        print(f"  📝 Expired Charitable Carryforward: ${metrics['expired_charitable_deduction']:,.0f}")
        print(f"     ❗️ These deductions expired after 5-year carryforward period")

    if detailed and final_state:
        # Equity position details
        vested_unexercised = sum(lot.quantity for lot in final_state.equity_holdings
                                if lot.lifecycle_state.value == 'vested_not_exercised')
        exercised_shares = sum(lot.quantity for lot in final_state.equity_holdings
                              if lot.lifecycle_state.value == 'exercised_not_disposed')
        unvested_shares = sum(lot.quantity for lot in final_state.equity_holdings
                             if lot.lifecycle_state.value == 'granted_not_vested')

        total_shares = vested_unexercised + exercised_shares + unvested_shares

        print(f"\nEQUITY POSITION:")
        print(f"  📈 Total Shares: {total_shares:,}")
        print(f"  🎯 Vested Unexercised: {vested_unexercised:,} shares")
        print(f"  ✅ Exercised Shares: {exercised_shares:,} shares")
        print(f"  🔒 Unvested Shares: {unvested_shares:,} shares")

        # Share type breakdown if available
        iso_shares = sum(lot.quantity for lot in final_state.equity_holdings
                        if lot.share_type == 'ISO' and lot.lifecycle_state.value == 'exercised_not_disposed')
        nso_shares = sum(lot.quantity for lot in final_state.equity_holdings
                        if lot.share_type == 'NSO' and lot.lifecycle_state.value == 'exercised_not_disposed')
        if iso_shares > 0 or nso_shares > 0:
            print(f"  📊 Exercised by Type: ISO: {iso_shares:,}, NSO: {nso_shares:,}")

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

    print(f"\n{'='*180}")
    print("SCENARIO COMPARISON")
    print(f"{'='*180}")

    # Header
    print(f"\n{'Scenario':<20} {'Net Worth':>12} {'Equity':>12} {'Cash':>12} {'Taxes':>12} {'Charity':>12} {'Exp Ded':>10} {'Plg Exp':>9} {'NW+Charity':>12} {'✓'}")
    print(f"{'-'*180}")

    # Sort results by constraints (True first) then by NW+Charity descending
    sorted_results = sorted(results, key=lambda r: (
        # First sort key: constraints met (True = 1, False = 0, so True comes first when negated)
        -(r.summary_metrics.get('pledge_shares_expired_window', 0) == 0 and 
          r.summary_metrics.get('total_equity_value_final', 0) == 0),
        # Second sort key: NW+Charity descending (negative for descending sort)
        -(r.summary_metrics.get('total_cash_final', 0) + 
          r.summary_metrics.get('total_equity_value_final', 0) +
          r.summary_metrics.get('total_charitable_impact_all_years', 
                              r.summary_metrics.get('total_donations_all_years', 0)))
    ))

    # Results
    for result in sorted_results:
        metrics = result.summary_metrics
        net_worth = metrics['total_cash_final'] + metrics['total_equity_value_final']
        charity_impact = metrics.get('total_charitable_impact_all_years', metrics.get('total_donations_all_years', 0))
        nw_plus_charity = net_worth + charity_impact
        expired_ded = metrics.get('expired_charitable_deduction', 0)
        pledge_exp = metrics.get('pledge_shares_expired_window', 0)
        
        # Check constraints
        zero_plg_exp = pledge_exp == 0
        zero_equity = metrics['total_equity_value_final'] == 0
        meets_both = zero_plg_exp and zero_equity
        constraint_str = "✓" if meets_both else ""

        # Create short name: if starts with number, use "XXX: " + first few words
        name_parts = result.plan.name.split()
        if name_parts and name_parts[0].replace('_', '').isdigit():
            # Take scenario number and next 2 words
            short_name = f"{name_parts[0]}: {' '.join(name_parts[1:3])}"
        else:
            # Just truncate to 20 chars
            short_name = result.plan.name[:20]

        # Ensure it fits in 20 chars
        if len(short_name) > 20:
            short_name = short_name[:17] + "..."

        print(f"{short_name:<20} ${net_worth:>11,.0f} ${metrics['total_equity_value_final']:>11,.0f} "
              f"${metrics['total_cash_final']:>11,.0f} ${metrics['total_taxes_all_years']:>11,.0f} "
              f"${charity_impact:>11,.0f} ${expired_ded:>9,.0f} "
              f"{pledge_exp:>8,} ${nw_plus_charity:>11,.0f} {constraint_str:>1}")




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
