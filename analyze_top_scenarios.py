#!/usr/bin/env python3
"""
Analyze portfolio results to identify top scenarios balancing net worth and pledge fulfillment.
"""

import csv
from pathlib import Path

def load_portfolio_results():
    """Load the portfolio comparison results."""
    results_path = Path("output/user/portfolio_comparisons/moderate_all_comparison.csv")
    if not results_path.exists():
        raise FileNotFoundError(f"Portfolio results not found at {results_path}")

    scenarios = []
    with open(results_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            for field in ['total_cash_final', 'total_taxes_all_years', 'total_donations_all_years',
                         'total_equity_value_final', 'pledge_shares_obligated', 'pledge_shares_donated',
                         'pledge_shares_outstanding', 'pledge_shares_expired_window', 'outstanding_obligation']:
                row[field] = float(row[field]) if row[field] else 0.0
            scenarios.append(row)

    return scenarios

def calculate_scenario_scores(scenarios):
    """Calculate composite scores for each scenario."""
    # Calculate derived metrics
    for scenario in scenarios:
        # Total net worth
        scenario['total_net_worth'] = scenario['total_cash_final'] + scenario['total_equity_value_final']

        # Pledge fulfillment rate
        if scenario['pledge_shares_obligated'] > 0:
            scenario['pledge_fulfillment_rate'] = scenario['pledge_shares_donated'] / scenario['pledge_shares_obligated']
        else:
            scenario['pledge_fulfillment_rate'] = 1.0  # Perfect if no pledges

        # Tax efficiency
        scenario['tax_efficiency'] = scenario['total_net_worth'] / (scenario['total_net_worth'] + scenario['total_taxes_all_years'])

        # Outstanding obligation penalty
        scenario['outstanding_obligation_penalty'] = scenario['outstanding_obligation'] / scenario['total_net_worth'] if scenario['total_net_worth'] > 0 else 0

    # Find max values for normalization
    max_net_worth = max(s['total_net_worth'] for s in scenarios)

    # Calculate composite scores
    for scenario in scenarios:
        # Normalize to 0-100 scale
        net_worth_score = (scenario['total_net_worth'] / max_net_worth) * 100
        pledge_score = scenario['pledge_fulfillment_rate'] * 100
        tax_score = scenario['tax_efficiency'] * 100
        obligation_penalty = scenario['outstanding_obligation_penalty'] * 100

        # Composite score: Heavy weight on pledge fulfillment, then net worth, then tax efficiency
        # Subtract penalty for outstanding obligations
        scenario['composite_score'] = (
            pledge_score * 0.4 +           # 40% weight on pledge fulfillment
            net_worth_score * 0.35 +       # 35% weight on net worth
            tax_score * 0.25 -             # 25% weight on tax efficiency
            obligation_penalty * 2.0       # 2x penalty for outstanding obligations
        )

    return scenarios

def identify_top_scenarios(scenarios, top_n=5):
    """Identify top scenarios based on composite score."""
    return sorted(scenarios, key=lambda x: x['composite_score'], reverse=True)[:top_n]

def print_scenario_analysis(scenarios):
    """Print detailed analysis of scenarios."""
    print("PORTFOLIO SCENARIO ANALYSIS")
    print("=" * 80)
    print()

    # Summary statistics
    pledge_scenarios = sum(1 for s in scenarios if s['pledge_shares_obligated'] > 0)
    perfect_pledges = sum(1 for s in scenarios if s['pledge_fulfillment_rate'] >= 0.99)
    min_nw = min(s['total_net_worth'] for s in scenarios)
    max_nw = max(s['total_net_worth'] for s in scenarios)

    print("PORTFOLIO SUMMARY:")
    print(f"  Total Scenarios: {len(scenarios)}")
    print(f"  Scenarios with Pledges: {pledge_scenarios}")
    print(f"  Perfect Pledge Fulfillment: {perfect_pledges}")
    print(f"  Net Worth Range: ${min_nw:,.0f} - ${max_nw:,.0f}")
    print()

    # Top 10 scenarios
    top_10 = sorted(scenarios, key=lambda x: x['composite_score'], reverse=True)[:10]

    print("TOP 10 SCENARIOS (by composite score):")
    print("-" * 120)
    print(f"{'Rank':<4} {'Scenario':<35} {'Net Worth':<12} {'Pledge %':<9} {'Tax Eff %':<9} {'Outstand $':<12} {'Score':<6}")
    print("-" * 120)

    for i, scenario in enumerate(top_10, 1):
        print(f"{i:<4} {scenario['scenario']:<35} ${scenario['total_net_worth']:<11,.0f} "
              f"{scenario['pledge_fulfillment_rate']*100:<8.1f}% {scenario['tax_efficiency']*100:<8.1f}% "
              f"${scenario['outstanding_obligation']:<11,.0f} {scenario['composite_score']:<5.1f}")

    print()

def print_top_5_detailed(top_5):
    """Print detailed analysis of top 5 scenarios."""
    print("TOP 5 SCENARIOS - DETAILED ANALYSIS:")
    print("=" * 80)

    for i, scenario in enumerate(top_5, 1):
        print(f"\n{i}. {scenario['scenario']}")
        print(f"   Net Worth: ${scenario['total_net_worth']:,.0f} (Cash: ${scenario['total_cash_final']:,.0f}, Equity: ${scenario['total_equity_value_final']:,.0f})")
        print(f"   Taxes Paid: ${scenario['total_taxes_all_years']:,.0f}")
        print(f"   Tax Efficiency: {scenario['tax_efficiency']*100:.1f}%")

        if scenario['pledge_shares_obligated'] > 0:
            print(f"   Pledge Status: {scenario['pledge_shares_donated']:,.0f}/{scenario['pledge_shares_obligated']:,.0f} shares ({scenario['pledge_fulfillment_rate']*100:.1f}%)")
            print(f"   Outstanding Obligation: ${scenario['outstanding_obligation']:,.0f}")
            if scenario['outstanding_obligation'] > 0:
                print(f"   ⚠️  INCOMPLETE PLEDGE FULFILLMENT")
        else:
            print(f"   Pledge Status: No charitable obligations")

        print(f"   Composite Score: {scenario['composite_score']:.1f}")

def identify_problematic_scenarios(scenarios):
    """Identify scenarios with significant issues."""
    print("\nPROBLEMATIC SCENARIOS:")
    print("-" * 50)

    # High outstanding obligations
    high_obligations = [s for s in scenarios if s['outstanding_obligation'] > 500000]
    high_obligations.sort(key=lambda x: x['outstanding_obligation'], reverse=True)

    if high_obligations:
        print("\nHigh Outstanding Obligations (>$500K):")
        for scenario in high_obligations[:5]:
            print(f"  {scenario['scenario']}: ${scenario['outstanding_obligation']:,.0f} outstanding")

    # Low pledge fulfillment
    low_fulfillment = [s for s in scenarios if s['pledge_shares_obligated'] > 0 and s['pledge_fulfillment_rate'] < 0.8]
    low_fulfillment.sort(key=lambda x: x['pledge_fulfillment_rate'])

    if low_fulfillment:
        print("\nLow Pledge Fulfillment (<80%):")
        for scenario in low_fulfillment[:5]:
            print(f"  {scenario['scenario']}: {scenario['pledge_fulfillment_rate']*100:.1f}% fulfilled")

def recommend_scenario_improvements(top_5):
    """Recommend improvements for top scenarios."""
    print("\nRECOMMENDATIONS FOR TOP 5 SCENARIOS:")
    print("=" * 60)

    max_net_worth = max(s['total_net_worth'] for s in top_5)

    for i, scenario in enumerate(top_5, 1):
        print(f"\n{i}. {scenario['scenario']}:")

        # Check for outstanding obligations
        if scenario['outstanding_obligation'] > 50000:
            print(f"   🔧 CRITICAL: Complete ${scenario['outstanding_obligation']:,.0f} in outstanding pledges")
            outstanding_shares = scenario['pledge_shares_obligated'] - scenario['pledge_shares_donated']
            print(f"      - Add donation actions to fulfill remaining {outstanding_shares:,.0f} shares")

        # Check tax efficiency
        if scenario['tax_efficiency'] < 0.6:
            print(f"   🔧 Tax efficiency is low ({scenario['tax_efficiency']*100:.1f}%)")
            print(f"      - Consider more tax-efficient timing of exercises/sales")

        # Check for cash vs equity balance
        cash_ratio = scenario['total_cash_final'] / scenario['total_net_worth']
        if cash_ratio < 0.05:
            print(f"   🔧 Very low cash position ({cash_ratio*100:.1f}% of net worth)")
            print(f"      - Consider adding liquidity events for cash flow")
        elif cash_ratio > 0.25:
            print(f"   🔧 High cash position ({cash_ratio*100:.1f}% of net worth)")
            print(f"      - Consider more equity retention for growth")

        # Net worth potential
        if scenario['total_net_worth'] < max_net_worth * 0.9:
            gap = max_net_worth - scenario['total_net_worth']
            print(f"   🔧 Net worth gap: ${gap:,.0f} below top performer")
            print(f"      - Analyze timing of exercises for better equity growth")

def main():
    """Main analysis function."""
    try:
        # Load portfolio results
        scenarios = load_portfolio_results()

        # Calculate scores
        scenarios = calculate_scenario_scores(scenarios)

        # Print analysis
        print_scenario_analysis(scenarios)

        # Identify top scenarios
        top_5 = identify_top_scenarios(scenarios, 5)

        # Print detailed analysis
        print_top_5_detailed(top_5)

        # Identify problems
        identify_problematic_scenarios(scenarios)

        # Recommendations
        recommend_scenario_improvements(top_5)

        # Return top scenario names
        print(f"\nTOP 5 CANDIDATE SCENARIOS:")
        top_names = []
        for i, scenario in enumerate(top_5, 1):
            print(f"{i}. {scenario['scenario']}")
            top_names.append(scenario['scenario'])

        return top_names

    except Exception as e:
        print(f"Error in analysis: {e}")
        raise

if __name__ == "__main__":
    main()
