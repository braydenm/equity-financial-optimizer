#!/usr/bin/env python3
"""
Multi-scenario analysis runner for equity optimization.

This script runs multiple scenarios defined in CSV/JSON files and provides
comparative analysis across different strategies.
"""

import sys
import os
from datetime import date
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_calculator import ProjectionCalculator
from projections.projection_state import (
    ProjectionPlan, PlannedAction, ShareLot, UserProfile,
    ShareType, LifecycleState, TaxTreatment, ActionType
)
from projections.projection_output import (
    save_all_projection_csvs, create_comparison_csv
)
from loaders.scenario_loader import load_scenario_from_directory
from loaders.csv_loader import CSVLoader
from loaders.profile_loader import ProfileLoader


def create_natural_evolution_scenario(profile: UserProfile, initial_lots: List[ShareLot]) -> ProjectionPlan:
    """Create the baseline Natural Evolution scenario (no actions)."""
    plan = ProjectionPlan(
        name="Natural Evolution",
        description="Baseline scenario with no equity actions - just accumulate income",
        start_date=date(2025, 1, 1),
        end_date=date(2029, 12, 31),
        initial_lots=initial_lots,
        initial_cash=profile.current_cash,
        price_projections={
            2025: 23.75,
            2026: 23.75,
            2027: 23.75,
            2028: 23.75,
            2029: 23.75
        }
    )
    # No actions in Natural Evolution
    return plan


def print_scenario_summary(name: str, result: Any) -> None:
    """Print a summary of scenario results."""
    final_state = result.get_final_state()
    metrics = result.summary_metrics

    print(f"\n{'=' * 80}")
    print(f"SCENARIO: {name}")
    print(f"{'=' * 80}")

    print(f"\nFINAL STATE (2029):")
    print(f"  💰 Cash Position: ${metrics['total_cash_final']:,.0f}")
    print(f"  📊 Equity Value: ${metrics['total_equity_value_final']:,.0f}")
    print(f"  💎 Total Net Worth: ${metrics['total_cash_final'] + metrics['total_equity_value_final']:,.0f}")

    print(f"\nCUMULATIVE METRICS:")
    print(f"  💸 Total Taxes Paid: ${metrics['total_taxes_all_years']:,.0f}")
    print(f"  🎁 Total Donations: ${metrics['total_donations_all_years']:,.0f}")
    print(f"  📋 Outstanding Pledge: ${metrics['outstanding_obligation']:,.0f}")
    print(f"  ✅ Pledge Fulfillment: {metrics['pledge_fulfillment_maximalist']:.1%}")

    if final_state:
        vested_unexercised = sum(lot.quantity for lot in final_state.equity_holdings
                                if lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED)
        exercised_shares = sum(lot.quantity for lot in final_state.equity_holdings
                              if lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED)

        print(f"\nEQUITY POSITION:")
        print(f"  🎯 Vested Unexercised: {vested_unexercised:,} shares")
        print(f"  ✅ Exercised Shares: {exercised_shares:,} shares")


def main():
    """Run multi-scenario analysis."""
    print("MULTI-SCENARIO EQUITY ANALYSIS")
    print("=" * 80)

    # Load baseline data
    csv_loader = CSVLoader()

    # Load user profile with secure fallback
    print("\nLoading user profile...")
    try:
        profile_loader = ProfileLoader()
        profile_data, is_real_data = profile_loader.load_profile(verbose=True)

        # Create UserProfile from data
        personal = profile_data['personal_information']
        income = profile_data['income']
        financial = profile_data['financial_position']
        goals = profile_data['goals_and_constraints']
        charitable = profile_data['charitable_giving']

        profile = UserProfile(
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

        print(f"✅ Profile loaded: {personal['tax_filing_status']}")
        print(f"✅ Annual income: ${income['annual_w2_income'] + income['spouse_w2_income']:,}")
        print(f"✅ Current cash: ${financial['liquid_assets']['cash']:,}")

    except Exception as e:
        print(f"❌ Error loading profile: {e}")
        return

    # Load initial equity position
    print("\nLoading equity position...")
    try:
        timeline_path = 'output/working/equity_position_timeline/equity_position_timeline.csv'
        initial_lots = csv_loader.load_initial_equity_position(timeline_path)
        print(f"✅ Loaded {len(initial_lots)} equity lots")
    except Exception as e:
        print(f"❌ Error loading equity position: {e}")
        return

    # Initialize calculator
    calculator = ProjectionCalculator(profile)

    # Store results for comparison
    all_results = []

    # Scenario 1: Natural Evolution (baseline)
    print("\n" + "=" * 80)
    print("Running Natural Evolution scenario...")
    natural_plan = create_natural_evolution_scenario(profile, initial_lots)
    natural_result = calculator.evaluate_projection_plan(natural_plan)
    all_results.append(natural_result)
    print_scenario_summary("Natural Evolution", natural_result)
    save_all_projection_csvs(natural_result, "natural_evolution", "output/natural_evolution")

    # Scenario 2: Exercise All Vested (from CSV)
    print("\n" + "=" * 80)
    print("Running Exercise All Vested scenario...")
    try:
        exercise_plan, _ = load_scenario_from_directory("scenarios/exercise_all_vested")
        # Override initial lots to match our baseline
        exercise_plan.initial_lots = initial_lots
        exercise_result = calculator.evaluate_projection_plan(exercise_plan)
        all_results.append(exercise_result)
        print_scenario_summary("Exercise All Vested", exercise_result)
        save_all_projection_csvs(exercise_result, "exercise_all_vested", "output/exercise_all_vested")
    except Exception as e:
        print(f"❌ Error running Exercise All Vested scenario: {e}")
        import traceback
        traceback.print_exc()

    # Scenario 3: Tender and Donate (from CSV)
    print("\n" + "=" * 80)
    print("Running Tender and Donate scenario...")
    try:
        tender_plan, _ = load_scenario_from_directory("scenarios/tender_and_donate")
        # Override initial lots to match our baseline
        tender_plan.initial_lots = initial_lots
        tender_result = calculator.evaluate_projection_plan(tender_plan)
        all_results.append(tender_result)
        print_scenario_summary("Tender and Donate", tender_result)
        save_all_projection_csvs(tender_result, "tender_and_donate", "output/tender_and_donate")
    except Exception as e:
        print(f"❌ Error running Tender and Donate scenario: {e}")
        import traceback
        traceback.print_exc()

    # Create comparison
    print("\n" + "=" * 80)
    print("SCENARIO COMPARISON")
    print("=" * 80)

    if len(all_results) >= 2:
        natural_metrics = all_results[0].summary_metrics
        exercise_metrics = all_results[1].summary_metrics

        print("\nKey Differences (Exercise All Vested vs Natural Evolution):")

        cash_diff = exercise_metrics['total_cash_final'] - natural_metrics['total_cash_final']
        print(f"  💰 Cash Impact: ${cash_diff:,.0f}")

        tax_diff = exercise_metrics['total_taxes_all_years'] - natural_metrics['total_taxes_all_years']
        print(f"  💸 Additional Taxes: ${tax_diff:,.0f}")

        equity_diff = exercise_metrics['total_equity_value_final'] - natural_metrics['total_equity_value_final']
        print(f"  📊 Equity Value Change: ${equity_diff:,.0f}")

        net_worth_natural = natural_metrics['total_cash_final'] + natural_metrics['total_equity_value_final']
        net_worth_exercise = exercise_metrics['total_cash_final'] + exercise_metrics['total_equity_value_final']
        net_worth_diff = net_worth_exercise - net_worth_natural
        print(f"  💎 Net Worth Impact: ${net_worth_diff:,.0f}")

        print("\nKey Insights:")
        if cash_diff < 0:
            print(f"  ⚠️  Exercising options reduces cash by ${abs(cash_diff):,.0f}")
        if tax_diff > 0:
            print(f"  ⚠️  Exercise triggers ${tax_diff:,.0f} in taxes")
        print(f"  📈 Options are converted from unvested to exercised status")
        print(f"  🎯 Sets up potential for future LTCG treatment after 1-year holding")

        # Compare Tender and Donate scenario if available
        if len(all_results) >= 3:
            tender_metrics = all_results[2].summary_metrics

            print("\n" + "-" * 80)
            print("\nKey Differences (Tender and Donate vs Natural Evolution):")

            cash_diff_tender = tender_metrics['total_cash_final'] - natural_metrics['total_cash_final']
            print(f"  💰 Cash Impact: ${cash_diff_tender:,.0f}")

            tax_diff_tender = tender_metrics['total_taxes_all_years'] - natural_metrics['total_taxes_all_years']
            print(f"  💸 Total Taxes: ${tax_diff_tender:,.0f}")

            donation_diff = tender_metrics['total_donations_all_years'] - natural_metrics['total_donations_all_years']
            print(f"  🎁 Total Donations: ${donation_diff:,.0f}")

            pledge_fulfillment = tender_metrics['pledge_fulfillment_maximalist']
            print(f"  ✅ Pledge Fulfillment: {pledge_fulfillment:.1%}")

            net_worth_tender = tender_metrics['total_cash_final'] + tender_metrics['total_equity_value_final']
            net_worth_diff_tender = net_worth_tender - net_worth_natural
            print(f"  💎 Net Worth Impact: ${net_worth_diff_tender:,.0f}")

            print("\nTender & Donate Strategy Insights:")
            print(f"  📈 Generates liquidity through tender participation")
            print(f"  🎁 Maximizes charitable impact with company matching")
            print(f"  ✅ Fulfills pledge obligations from share sales")
            print(f"  💡 Balances liquidity, taxes, and charitable goals")

        # Save comparison CSV
        create_comparison_csv(all_results, "output/scenario_comparison.csv")
        print(f"\n✅ Comparison saved to: output/scenario_comparison.csv")

    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("  1. Create more scenario CSVs in scenarios/ directory")
    print("  2. Test tender offer participation scenarios")
    print("  3. Model donation strategies with company matching")
    print("  4. Optimize for AMT breakeven points")
    print("=" * 80)


if __name__ == "__main__":
    main()
