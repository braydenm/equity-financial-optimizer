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
    print(f"  📈 Investment Balance: ${final_state.investment_balance:,.0f}")
    print(f"  📊 Equity Value: ${metrics['total_equity_value_final']:,.0f}")
    print(f"  💎 Total Net Worth: ${final_state.total_net_worth:,.0f}")

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

        # Display opportunity cost warnings if any exist
        total_opportunity_cost = metrics.get('total_opportunity_cost', 0)
        total_expired_shares = metrics.get('total_expired_shares', 0)
        expiration_details = metrics.get('expiration_details', [])

        if total_opportunity_cost > 0:
            print(f"\n⚠️  OPTION EXPIRATION WARNINGS:")
            print(f"  💸 Total Opportunity Cost: ${total_opportunity_cost:,.2f}")
            print(f"  📉 Total Expired Shares: {total_expired_shares:,} shares")
            print(f"  📊 Average Loss per Share: ${total_opportunity_cost/total_expired_shares:.2f}")

            for detail in expiration_details:
                print(f"  🔥 {detail['year']}: {detail['quantity']:,} shares expired - LOST ${detail['opportunity_cost']:,.0f} (${detail['per_share_loss']:.2f}/share)")

            print(f"  ⚡ Consider exercising valuable vested options before expiration!")

        # Comprehensive financial summary
        print(f"\nFINANCIAL SUMMARY:")
        print(f"  {'Year':<6} {'Income':>10} {'Expenses':>10} {'Exercise':>10} {'Sales':>10} {'Tax':>10} {'Donations':>10} {'Net Flow':>10} {'Eff Tax%':>9}")
        print(f"  {'-'*95}")
        for state in result.yearly_states:
            # Calculate total income from all sources
            investment_income = state.investment_income if hasattr(state, 'investment_income') else 0
            total_income = (state.income + state.spouse_income + state.other_income + investment_income)

            # Get expenses and other cash flows
            expenses = state.living_expenses if hasattr(state, 'living_expenses') else 0
            exercise_costs = state.exercise_costs

            # Calculate sale proceeds from components
            sale_proceeds = 0
            if state.annual_tax_components and hasattr(state.annual_tax_components, 'sale_components'):
                sale_proceeds = sum(comp.gross_proceeds for comp in state.annual_tax_components.sale_components)

            # Tax info
            gross_tax = state.gross_tax if hasattr(state, 'gross_tax') else state.tax_state.total_tax
            withholdings = state.tax_withholdings if hasattr(state, 'tax_withholdings') else 0
            net_tax = state.tax_paid  # This is net of withholdings

            # Donations
            donations = state.donation_value

            # Net cash flow
            net_flow = total_income + sale_proceeds - expenses - exercise_costs - net_tax

            # Effective tax rate
            eff_tax_rate = (gross_tax / total_income * 100) if total_income > 0 else 0

            print(f"  {state.year:<6} ${total_income:>9,.0f} ${expenses:>9,.0f} ${exercise_costs:>9,.0f} "
                  f"${sale_proceeds:>9,.0f} ${net_tax:>9,.0f} ${donations:>9,.0f} ${net_flow:>9,.0f} {eff_tax_rate:>8.1f}%")

        # Cash flow waterfall
        print(f"\nCASH FLOW WATERFALL:")
        print(f"  {'Year':<6} {'Start Cash':>12} {'+ Income':>12} {'+ Sales':>12} {'- Expenses':>12} {'- Exercise':>12} {'- Tax':>12} {'= End Cash':>12}")
        print(f"  {'-'*102}")
        for state in result.yearly_states:
            total_income = (state.income + state.spouse_income + state.other_income +
                          (state.investment_income if hasattr(state, 'investment_income') else 0))
            expenses = state.living_expenses if hasattr(state, 'living_expenses') else 0

            # Calculate sale proceeds from components
            sale_proceeds = 0
            if state.annual_tax_components and hasattr(state.annual_tax_components, 'sale_components'):
                sale_proceeds = sum(comp.gross_proceeds for comp in state.annual_tax_components.sale_components)

            print(f"  {state.year:<6} ${state.starting_cash:>11,.0f} ${total_income:>11,.0f} "
                  f"${sale_proceeds:>11,.0f} ${expenses:>11,.0f} ${state.exercise_costs:>11,.0f} "
                  f"${state.tax_paid:>11,.0f} ${state.ending_cash:>11,.0f}")

        # Investment tracking
        if any(hasattr(state, 'investment_balance') and state.investment_balance > 0 for state in result.yearly_states):
            print(f"\nINVESTMENT TRACKING:")
            print(f"  {'Year':<6} {'Balance':>12} {'Growth':>12} {'Total Return':>12}")
            print(f"  {'-'*48}")
            initial_investments = result.user_profile.taxable_investments
            for i, state in enumerate(result.yearly_states):
                balance = state.investment_balance if hasattr(state, 'investment_balance') else 0
                if i == 0:
                    growth = balance - initial_investments
                else:
                    prev_balance = result.yearly_states[i-1].investment_balance if hasattr(result.yearly_states[i-1], 'investment_balance') else 0
                    growth = balance - prev_balance
                total_return = ((balance / initial_investments - 1) * 100) if initial_investments > 0 else 0
                print(f"  {state.year:<6} ${balance:>11,.0f} ${growth:>11,.0f} {total_return:>11.1f}%")

        # Assets breakdown table
        print(f"\nASSETS BREAKDOWN:")
        print(f"  {'Year':<6} {'Cash':>12} {'Investments':>12} {'Equity':>12} {'Total NW':>12} {'YoY Growth':>12}")
        print(f"  {'-'*78}")
        prev_net_worth = 0
        for i, state in enumerate(result.yearly_states):
            cash = state.ending_cash
            investments = state.investment_balance if hasattr(state, 'investment_balance') else 0
            equity = state.total_equity_value
            net_worth = state.total_net_worth

            if i == 0:
                # Calculate starting net worth
                start_cash = state.starting_cash
                start_investments = result.user_profile.taxable_investments
                start_equity = sum(lot.quantity for lot in result.plan.initial_lots
                                 if lot.lifecycle_state.value in ['exercised_not_disposed', 'vested_not_exercised']) * \
                               result.plan.price_projections[state.year]
                prev_net_worth = start_cash + start_investments + start_equity

            yoy_growth = ((net_worth / prev_net_worth - 1) * 100) if prev_net_worth > 0 else 0
            print(f"  {state.year:<6} ${cash:>11,.0f} ${investments:>11,.0f} "
                  f"${equity:>11,.0f} ${net_worth:>11,.0f} {yoy_growth:>11.1f}%")
            prev_net_worth = net_worth

        # Charitable donations table (only if donations exist)
        total_donations = sum(state.donation_value for state in result.yearly_states)
        if total_donations > 0 or (final_state and final_state.pledge_state.total_outstanding_obligation > 0):
            print(f"\nCHARITABLE ACTIVITY:")
            print(f"  {'Year':<6} {'Donated':>12} {'Match Earned':>12} {'Deduction':>12} {'Carried Fwd':>12} {'Pledge Oblig':>12}")
            print(f"  {'-'*78}")

            for state in result.yearly_states:
                donation_value = state.donation_value

                # Calculate company match from donation components
                company_match = 0
                if state.annual_tax_components and state.annual_tax_components.donation_components:
                    for comp in state.annual_tax_components.donation_components:
                        company_match += comp.company_match if hasattr(comp, 'company_match') else 0

                # Get charitable deduction info from tax state
                deduction_used = 0
                carryforward = 0
                if hasattr(state, 'charitable_state'):
                    deduction_used = state.charitable_state.current_year_deduction
                    carryforward = sum(state.charitable_state.carryforward_remaining.values())

                # Get pledge obligation
                pledge_obligation = state.pledge_state.total_outstanding_obligation if state.pledge_state else 0

                print(f"  {state.year:<6} ${donation_value:>11,.0f} ${company_match:>11,.0f} "
                      f"${deduction_used:>11,.0f} ${carryforward:>11,.0f} ${pledge_obligation:>11,.0f}")

            # Add pledge fulfillment summary if pledges exist
            if final_state and final_state.pledge_state and final_state.pledge_state.obligations:
                print(f"\n  Pledge Summary:")
                total_pledged = sum(o.total_pledge_obligation for o in final_state.pledge_state.obligations)
                total_fulfilled = sum(o.donations_made for o in final_state.pledge_state.obligations)
                fulfillment_pct = (total_fulfilled / total_pledged * 100) if total_pledged > 0 else 0
                print(f"    Total Pledged: ${total_pledged:,.0f}")
                print(f"    Total Fulfilled: ${total_fulfilled:,.0f} ({fulfillment_pct:.1f}%)")
                print(f"    Outstanding: ${final_state.pledge_state.total_outstanding_obligation:,.0f}")

def print_raw_data_tables(result):
    """Print raw data tables that map 1:1 to CSV outputs."""
    print(f"\n{'='*80}")
    print("RAW DATA TABLES")
    print(f"{'='*80}")
    print("The following tables contain raw data that maps directly to CSV outputs.")
    print("Data is formatted for easy copy/paste into spreadsheets (no $ or % symbols).")

    # 1. ANNUAL CASH FLOW TABLE
    print(f"\n{'-'*80}")
    print("ANNUAL CASH FLOW (→ yearly_cashflow.csv)")
    print(f"{'-'*80}")
    print(f"{'Year':<6} {'Income':<12} {'Expenses':<12} {'Exercise':<12} {'Tax':<12} {'Donations':<12} {'End_Cash':<12}")
    print(f"{'-'*80}")

    for state in result.yearly_states:
        year_income = state.income
        year_expenses = state.living_expenses
        year_exercise = state.exercise_costs
        year_tax = state.tax_paid
        year_donations = state.donation_value
        end_cash = state.ending_cash

        print(f"{state.year:<6} {year_income:<12.0f} {year_expenses:<12.0f} {year_exercise:<12.0f} {year_tax:<12.0f} {year_donations:<12.0f} {end_cash:<12.0f}")

    # 2. TAX BREAKDOWN TABLE
    print(f"\n{'-'*80}")
    print("TAX BREAKDOWN (→ tax_timeline.csv)")
    print(f"{'-'*80}")
    print(f"{'Year':<6} {'Regular_Tax':<12} {'AMT_Tax':<12} {'Total_Tax':<12} {'AMT_Credits':<12}")
    print(f"{'-'*80}")

    for state in result.yearly_states:
        tax_state = state.tax_state if hasattr(state, 'tax_state') else None
        regular_tax = tax_state.regular_tax if tax_state else 0
        amt_tax = tax_state.amt_tax if tax_state else 0
        total_tax = tax_state.total_tax if tax_state else state.tax_paid
        amt_credits = tax_state.amt_credits_remaining if tax_state else 0

        print(f"{state.year:<6} {regular_tax:<12.0f} {amt_tax:<12.0f} {total_tax:<12.0f} {amt_credits:<12.0f}")

    # 3. ASSETS BREAKDOWN TABLE
    print(f"\n{'-'*80}")
    print("ASSETS BREAKDOWN (→ annual_summary.csv)")
    print(f"{'-'*80}")
    print(f"{'Year':<6} {'Cash':<12} {'Investments':<12} {'Equity':<12} {'Total_NW':<12} {'YoY_Growth':<12}")
    print(f"{'-'*80}")

    prev_net_worth = 0
    for state in result.yearly_states:
        cash = state.ending_cash
        investments = state.investment_balance
        equity = state.total_equity_value
        total_nw = state.total_net_worth
        yoy_growth = ((total_nw - prev_net_worth) / prev_net_worth * 100) if prev_net_worth > 0 else 0

        print(f"{state.year:<6} {cash:<12.0f} {investments:<12.0f} {equity:<12.0f} {total_nw:<12.0f} {yoy_growth:<12.1f}")
        prev_net_worth = total_nw

    # 4. ACTION SUMMARY TABLE
    print(f"\n{'-'*80}")
    print("ACTION SUMMARY (→ action_summary.csv)")
    print(f"{'-'*80}")
    print(f"{'Date':<12} {'Action_Type':<12} {'Lot_ID':<20} {'Quantity':<12}")
    print(f"{'-'*80}")

    for action in result.plan.planned_actions:
        action_date = action.action_date.strftime('%Y-%m-%d')
        action_type = str(action.action_type).replace('ActionType.', '')
        lot_id = action.lot_id
        quantity = action.quantity

        print(f"{action_date:<12} {action_type:<12} {lot_id:<20} {quantity:<12.0f}")

def resolve_scenario_path(scenario_input, use_demo=False):
    """Resolve scenario path from either full name or 3-digit identifier.

    Args:
        scenario_input: Either full scenario name (e.g., '001_exercise_all_vested')
                       or just 3-digit identifier (e.g., '001')
        use_demo: Whether to force demo scenarios

    Returns:
        Full scenario path or raises ValueError if not found
    """
    # Determine which directory to search
    if use_demo:
        scenarios_dir = Path("scenarios/demo")
    else:
        # Check if user scenarios exist, otherwise fall back to demo
        user_dir = Path("scenarios/user")
        demo_dir = Path("scenarios/demo")
        scenarios_dir = user_dir if user_dir.exists() else demo_dir

    # If input is just 3 digits, find matching scenario
    if len(scenario_input) == 3 and scenario_input.isdigit():
        pattern = f"{scenario_input}_*.json"
        matching_files = list(scenarios_dir.glob(pattern))

        if not matching_files:
            raise ValueError(f"No scenario found with identifier '{scenario_input}' in {scenarios_dir}")
        elif len(matching_files) > 1:
            raise ValueError(f"Multiple scenarios found with identifier '{scenario_input}': {[f.stem for f in matching_files]}")

        return matching_files[0].stem  # Return filename without .json extension

    # Otherwise, treat as full scenario name
    scenario_file = scenarios_dir / f"{scenario_input}.json"
    if not scenario_file.exists():
        raise ValueError(f"Scenario file not found: {scenario_file}")

    return scenario_input


def execute_scenario(scenario_input, price_scenario="moderate", projection_years=5, use_demo=False):
    """Execute and display a single scenario.

    Args:
        scenario_input: Either full scenario name or 3-digit identifier
        price_scenario: Price growth assumption
        projection_years: Years to project
        use_demo: Force use of demo data
    """
    # Resolve the scenario path
    try:
        scenario_path = resolve_scenario_path(scenario_input, use_demo)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return None

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
    print_raw_data_tables(result)
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
        for scenario_file in sorted(demo_scenarios_dir.glob("*.json")):
            scenario_name = scenario_file.name.replace(".json", "")
            print(f"    • {scenario_name}")
    else:
        print("  Demo scenarios: Not found")

    # Show user scenarios
    user_scenarios_dir = Path("scenarios/user")
    if user_scenarios_dir.exists():
        print("  User scenarios (your personal data):")
        for scenario_file in sorted(user_scenarios_dir.glob("*.json")):
            scenario_name = scenario_file.name.replace(".json", "")
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
    print("  python run_scenario_analysis.py 000 --demo")
    print("  python run_scenario_analysis.py 002 --price aggressive --years 7")
    print("\nNote: You can use just the 3-digit identifier (e.g., '001') instead of the full name")


def main():
    """Main entry point for scenario analysis."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Execute single equity optimization scenario analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 001_exercise_all_vested
  %(prog)s 000 --demo
  %(prog)s 002 --price aggressive --years 7

Note: You can use just the 3-digit identifier (e.g., '001') instead of the full scenario name
        """
    )

    parser.add_argument('scenario', nargs='?', help='Scenario name or 3-digit ID (e.g., 001_exercise_all_vested or just 001)')
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
