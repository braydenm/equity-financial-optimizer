#!/usr/bin/env python3
"""
2025 Exercise Decision Analysis
===============================

Analyzes whether to exercise ISOs in 2025 given:
- $200k cash available for exercise + taxes
- Current tender offer at $56.0865
- 15,534 vested ISOs + 6,214 vested NSOs
- Additional ISOs vesting throughout 2025

Compares 4 scenarios:
1. Original comprehensive plan (206)
2. Exercise all ISOs in 2025 (209)
3. Delay ISO exercise to 2026 (210)
4. Tender only, no ISO exercise (211)
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple
from decimal import Decimal
from datetime import datetime

class ExerciseDecisionAnalyzer:
    def __init__(self):
        self.profile_path = "input_data/user_profile.json"
        self.cash_available = 200000
        self.tender_price = 56.0865
        self.strike_price = 4.48

        # Load user profile
        with open(self.profile_path, 'r') as f:
            self.profile = json.load(f)

        # Define scenarios to analyze
        self.scenarios = [
            {
                "id": "206",
                "name": "Original Comprehensive Plan",
                "path": "scenarios/user/206_brayden_comprehensive_plan_v7.json",
                "description": "Original plan: Exercises all ISOs in June 2025"
            },
            {
                "id": "209",
                "name": "2025 ISO Exercise",
                "path": "scenarios/user/209_2025_iso_exercise_analysis.json",
                "description": "Simplified: Exercise all ISOs in 2025 with tender"
            },
            {
                "id": "210",
                "name": "Delay to 2026",
                "path": "scenarios/user/210_2026_iso_exercise_delay.json",
                "description": "Delay ISO exercises to 2026, tender NSOs only"
            },
            {
                "id": "211",
                "name": "Tender Only",
                "path": "scenarios/user/211_tender_only_no_iso.json",
                "description": "Minimal: Tender NSOs only, no ISO exercises"
            }
        ]

    def analyze_2025_cash_requirements(self) -> Dict[str, Dict]:
        """Analyze cash requirements for each scenario in 2025."""
        results = {}

        for scenario in self.scenarios:
            scenario_id = scenario["id"]
            scenario_name = scenario["name"]

            # Load scenario actions
            with open(scenario["path"], 'r') as f:
                scenario_data = json.load(f)

            # Calculate 2025 cash needs
            iso_exercises = 0
            nso_exercises = 0
            shares_sold = 0

            for action in scenario_data['actions']:
                if not action['action_date'].startswith('2025'):
                    continue

                if action['action_type'] == 'exercise':
                    if 'ISO' in action['lot_id']:
                        iso_exercises += action['quantity']
                    elif 'NSO' in action['lot_id']:
                        nso_exercises += action['quantity']

                elif action['action_type'] == 'sell':
                    shares_sold += action['quantity']

            # Calculate cash flows
            iso_exercise_cost = iso_exercises * self.strike_price
            nso_exercise_cost = nso_exercises * self.strike_price
            total_exercise_cost = iso_exercise_cost + nso_exercise_cost

            # Calculate proceeds from tender sales
            sale_proceeds = shares_sold * self.tender_price

            # Calculate tax implications
            nso_ordinary_income = nso_exercises * (self.tender_price - self.strike_price)
            nso_withholding = nso_ordinary_income * 0.364  # From profile

            # ISO AMT calculation (simplified)
            iso_bargain_element = iso_exercises * (self.tender_price - self.strike_price)

            # Net cash needed in 2025
            cash_needed = total_exercise_cost + nso_withholding - sale_proceeds

            # Load actual results if available
            summary_path = f"output/user/moderate/scenario_{scenario_id}_{scenario['name'].lower().replace(' ', '_')}/"\
                          f"{scenario_id}_{scenario['name'].lower().replace(' ', '_')}_annual_summary.csv"

            actual_amt = 0
            actual_tax = 0
            ending_cash = 0

            try:
                with open(summary_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['year'] == '2025':
                            actual_amt = float(row.get('amt_tax', 0))
                            actual_tax = float(row.get('total_tax', 0))
                            ending_cash = float(row.get('ending_cash', 0))
                            break
            except:
                pass

            results[scenario_name] = {
                "iso_shares": iso_exercises,
                "nso_shares": nso_exercises,
                "shares_sold": shares_sold,
                "exercise_cost": total_exercise_cost,
                "sale_proceeds": sale_proceeds,
                "nso_withholding": nso_withholding,
                "iso_bargain_element": iso_bargain_element,
                "cash_needed": cash_needed,
                "actual_amt": actual_amt,
                "actual_total_tax": actual_tax,
                "ending_cash_2025": ending_cash,
                "cash_sufficient": cash_needed <= self.cash_available
            }

        return results

    def analyze_long_term_impact(self) -> Dict[str, Dict]:
        """Analyze long-term financial impact of each scenario."""
        results = {}

        comparison_path = "output/user/portfolio_comparisons/moderate_2025_exercise_decision_analysis_comparison.csv"

        try:
            with open(comparison_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    scenario_name = row['scenario']

                    # Extract key metrics
                    results[scenario_name] = {
                        "final_net_worth": float(row['total_cash_final']) + float(row['total_equity_value_final']),
                        "final_cash": float(row['total_cash_final']),
                        "final_equity": float(row['total_equity_value_final']),
                        "total_taxes": float(row['total_taxes_all_years']),
                        "total_donations": float(row['total_donations_all_years']),
                        "charitable_impact": float(row['charitable_total_impact']),
                        "amt_credits_remaining": float(row['outstanding_amt_credits']),
                        "expired_options": int(row['expired_option_count']),
                        "expired_option_loss": float(row['expired_option_loss'])
                    }
        except:
            print("Warning: Could not load portfolio comparison results")

        return results

    def print_analysis(self):
        """Print comprehensive analysis of all scenarios."""
        print("=" * 80)
        print("2025 EXERCISE DECISION ANALYSIS")
        print("=" * 80)
        print(f"\nASSUMPTIONS:")
        print(f"- Available Cash: ${self.cash_available:,.0f}")
        print(f"- Tender Price: ${self.tender_price:.2f}")
        print(f"- Strike Price: ${self.strike_price:.2f}")
        print(f"- Vested ISOs: 15,534 shares")
        print(f"- Vested NSOs: 6,214 shares")

        # Analyze 2025 cash requirements
        cash_analysis = self.analyze_2025_cash_requirements()

        print("\n" + "=" * 80)
        print("2025 CASH FLOW ANALYSIS")
        print("=" * 80)

        for scenario_name, metrics in cash_analysis.items():
            print(f"\n{scenario_name.upper()}:")
            print(f"  Exercise Activity:")
            print(f"    - ISOs to exercise: {metrics['iso_shares']:,} shares")
            print(f"    - NSOs to exercise: {metrics['nso_shares']:,} shares")
            print(f"    - Shares to sell: {metrics['shares_sold']:,} shares")

            print(f"\n  Cash Flows:")
            print(f"    - Exercise cost: ${metrics['exercise_cost']:,.2f}")
            print(f"    - Sale proceeds: ${metrics['sale_proceeds']:,.2f}")
            print(f"    - NSO withholding: ${metrics['nso_withholding']:,.2f}")
            print(f"    - Net cash needed: ${metrics['cash_needed']:,.2f}")

            if metrics['iso_shares'] > 0:
                print(f"\n  AMT Impact:")
                print(f"    - ISO bargain element: ${metrics['iso_bargain_element']:,.2f}")
                print(f"    - Actual AMT (from results): ${metrics['actual_amt']:,.2f}")

            print(f"\n  2025 Year-End Position:")
            print(f"    - Total tax paid: ${metrics['actual_total_tax']:,.2f}")
            print(f"    - Ending cash: ${metrics['ending_cash_2025']:,.2f}")
            print(f"    - Cash sufficient? {'✅ YES' if metrics['cash_sufficient'] else '❌ NO'}")

        # Analyze long-term impact
        long_term = self.analyze_long_term_impact()

        if long_term:
            print("\n" + "=" * 80)
            print("LONG-TERM IMPACT ANALYSIS (10 YEARS)")
            print("=" * 80)

            # Sort by final net worth
            sorted_scenarios = sorted(long_term.items(),
                                    key=lambda x: x[1]['final_net_worth'],
                                    reverse=True)

            best_scenario = sorted_scenarios[0][0]
            best_nw = sorted_scenarios[0][1]['final_net_worth']

            for scenario_name, metrics in sorted_scenarios:
                print(f"\n{scenario_name.upper()}:")
                print(f"  Final Net Worth: ${metrics['final_net_worth']:,.0f}")

                # Compare to best
                if scenario_name != best_scenario:
                    diff = metrics['final_net_worth'] - best_nw
                    pct = (diff / best_nw) * 100
                    print(f"    Difference from best: ${diff:,.0f} ({pct:+.1f}%)")

                print(f"  - Final cash: ${metrics['final_cash']:,.0f}")
                print(f"  - Final equity: ${metrics['final_equity']:,.0f}")
                print(f"  - Total taxes paid: ${metrics['total_taxes']:,.0f}")
                print(f"  - Charitable impact: ${metrics['charitable_impact']:,.0f}")

                if metrics['expired_options'] > 0:
                    print(f"  ⚠️  EXPIRED OPTIONS: {metrics['expired_options']:,} shares")
                    print(f"     Lost value: ${metrics['expired_option_loss']:,.0f}")

        # Key insights
        print("\n" + "=" * 80)
        print("KEY INSIGHTS & RECOMMENDATIONS")
        print("=" * 80)

        # Check if $200k is sufficient
        print("\n1. IS $200K SUFFICIENT FOR 2025 ISO EXERCISE?")
        for scenario_name, metrics in cash_analysis.items():
            if metrics['iso_shares'] > 0:
                if metrics['cash_sufficient']:
                    print(f"   ✅ {scenario_name}: YES - Need ${metrics['cash_needed']:,.0f}")
                else:
                    shortfall = metrics['cash_needed'] - self.cash_available
                    print(f"   ❌ {scenario_name}: NO - Short ${shortfall:,.0f}")

        # AMT impact analysis
        print("\n2. AMT IMPACT COMPARISON:")
        amt_scenarios = [(name, m) for name, m in cash_analysis.items() if m['iso_shares'] > 0]
        amt_scenarios.sort(key=lambda x: x[1]['actual_amt'])

        for scenario_name, metrics in amt_scenarios:
            print(f"   - {scenario_name}: ${metrics['actual_amt']:,.0f} AMT")

        # Opportunity cost analysis
        print("\n3. OPPORTUNITY COST OF WAITING:")
        if "2025 ISO Exercise" in long_term and "Delay to 2026" in long_term:
            exercise_2025 = long_term["2025 ISO Exercise"]['final_net_worth']
            delay_2026 = long_term["Delay to 2026"]['final_net_worth']
            cost_of_waiting = delay_2026 - exercise_2025

            if cost_of_waiting > 0:
                print(f"   ✅ Delaying to 2026 is BETTER by ${cost_of_waiting:,.0f}")
            else:
                print(f"   ❌ Delaying to 2026 COSTS ${-cost_of_waiting:,.0f}")

        # Tender participation
        print("\n4. TENDER OFFER PARTICIPATION:")
        print(f"   - NSO tender (all scenarios): 6,214 shares = ${348,522} proceeds")
        print(f"   - This covers NSO withholding and provides liquidity")
        print(f"   - ✅ RECOMMENDATION: Participate with all NSOs")

        # Final recommendation
        print("\n" + "=" * 80)
        print("FINAL RECOMMENDATION")
        print("=" * 80)

        if long_term:
            print(f"\nBased on the analysis, the optimal strategy is:")
            print(f"➡️  {best_scenario}")
            print(f"    Final net worth: ${best_nw:,.0f}")

            # Explain why
            if "Delay to 2026" in best_scenario:
                print("\nRationale:")
                print("- Spreads AMT impact across tax years")
                print("- Allows AMT credit usage from 2024")
                print("- Maintains liquidity flexibility")
                print("- No significant opportunity cost")

def main():
    analyzer = ExerciseDecisionAnalyzer()
    analyzer.print_analysis()

if __name__ == "__main__":
    main()
