#!/usr/bin/env python3
"""
Main Projection Analysis - Equity Financial Optimizer

This is the main execution program for equity projection analysis using
real user profile data. It generates Natural Evolution scenarios and
evaluates multi-year financial projections.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import date
from projections.projection_state import UserProfile
from engine.natural_evolution_generator import generate_natural_evolution_from_profile_data
from projections.projection_calculator import ProjectionCalculator
from projections.projection_output import save_all_projection_csvs
from loaders.profile_loader import ProfileLoader


def load_user_profile():
    """Load user profile with secure fallback to demo data."""
    loader = ProfileLoader()
    return loader.load_profile(verbose=True)


def create_user_profile_object(profile_data):
    """Create UserProfile object from profile data."""
    personal_info = profile_data.get('personal_information', {})
    income = profile_data.get('income', {})
    financial_pos = profile_data.get('financial_position', {})
    charitable = profile_data.get('charitable_giving', {})

    return UserProfile(
        federal_tax_rate=personal_info['federal_tax_rate'],
        federal_ltcg_rate=personal_info['federal_ltcg_rate'],
        state_tax_rate=personal_info['state_tax_rate'],
        state_ltcg_rate=personal_info['state_ltcg_rate'],
        fica_tax_rate=personal_info['fica_tax_rate'],
        additional_medicare_rate=personal_info['additional_medicare_rate'],
        niit_rate=personal_info['niit_rate'],
        annual_w2_income=income.get('annual_w2_income', 0),
        spouse_w2_income=income.get('spouse_w2_income', 0),
        current_cash=financial_pos.get('liquid_assets', {}).get('cash', 0),
        exercise_reserves=profile_data.get('goals_and_constraints', {}).get('liquidity_needs', {}).get('exercise_reserves', 0),
        pledge_percentage=charitable.get('pledge_percentage', 0.5),
        company_match_ratio=charitable.get('company_match_ratio', 3.0),
        filing_status=personal_info.get('tax_filing_status', 'single')
    )


def display_equity_position_summary(plan):
    """Display summary of current equity position."""
    print("\nCURRENT EQUITY POSITION:")
    print("-" * 50)

    total_exercised_shares = 0
    total_vested_shares = 0
    ltcg_shares = 0
    stcg_shares = 0

    for lot in plan.initial_lots:
        if lot.lifecycle_state.value == "exercised_not_disposed":
            total_exercised_shares += lot.quantity
            if lot.tax_treatment.value == "LTCG":
                ltcg_shares += lot.quantity
            elif lot.tax_treatment.value == "STCG":
                stcg_shares += lot.quantity
        elif lot.lifecycle_state.value == "vested_not_exercised":
            total_vested_shares += lot.quantity

        print(f"  {lot.lot_id}: {lot.quantity:,} {lot.share_type.value} shares ({lot.lifecycle_state.value})")

    print(f"\nSUMMARY:")
    print(f"  Total Exercised: {total_exercised_shares:,} shares")
    print(f"    - LTCG Eligible: {ltcg_shares:,} shares")
    print(f"    - STCG: {stcg_shares:,} shares")
    print(f"  Total Vested (Unexercised): {total_vested_shares:,} shares")


def display_projection_results(result):
    """Display projection results in a clear format."""
    print("\MULTI-YEAR PROJECTION RESULTS:")
    print("=" * 80)

    print(f"\nYear-by-Year Summary:")
    print(f"{'Year':<6} {'Cash':<12} {'Income':<12} {'Exercise':<10} {'Tax':<10} {'Equity Value':<15} {'Net Worth':<12}")
    print("-" * 85)

    for state in result.yearly_states:
        print(f"{state.year:<6} ${state.ending_cash:<11,.0f} ${state.income:<11,.0f} "
              f"${state.exercise_costs:<9,.0f} ${state.tax_paid:<9,.0f} "
              f"${state.total_equity_value:<14,.0f} ${state.total_net_worth:<11,.0f}")

    # Summary metrics
    metrics = result.summary_metrics
    final_state = result.get_final_state()

    print(f"\nFINAL OUTCOMES (2029):")
    print(f"  Cash Position: ${metrics.get('total_cash_final', 0):,.0f}")
    print(f"  Equity Value: ${metrics.get('total_equity_value_final', 0):,.0f}")
    print(f"  Total Net Worth: ${final_state.total_net_worth if final_state else 0:,.0f}")
    print(f"  Total Taxes Paid: ${metrics.get('total_taxes_all_years', 0):,.0f}")
    print(f"  Total Donations Made: ${metrics.get('total_donations_all_years', 0):,.0f}")

    print(f"\nPLEDGE OBLIGATIONS:")
    print(f"  Outstanding Obligation: ${metrics.get('outstanding_obligation', 0):,.0f}")
    print(f"  Shares Obligated: {metrics.get('pledge_shares_obligated', 0):,}")
    print(f"  Shares Donated: {metrics.get('pledge_shares_donated', 0):,}")
    print(f"  Shares Outstanding: {metrics.get('pledge_shares_outstanding', 0):,}")
    if metrics.get('pledge_shares_expired_window', 0) > 0:
        print(f"  Shares with Expired Windows: {metrics.get('pledge_shares_expired_window', 0):,}")


def main():
    """Main projection analysis execution."""
    print("EQUITY PROJECTION ANALYSIS")
    print("=" * 80)
    print("Multi-Year Natural Evolution Scenario")
    print("=" * 80)

    # Load real user profile data
    print("Loading user profile data...")
    profile_data, is_real_data = load_user_profile()
    user_profile = create_user_profile_object(profile_data)

    print(f"✅ Profile loaded: {user_profile.filing_status}")
    print(f"✅ Annual income: ${user_profile.annual_w2_income + user_profile.spouse_w2_income:,.0f}")
    print(f"✅ Current cash: ${user_profile.current_cash:,.0f}")
    print(f"✅ Pledge percentage: {user_profile.pledge_percentage:.0%}")

    # Generate Natural Evolution scenario
    print("\nGenerating Natural Evolution scenario...")
    plan = generate_natural_evolution_from_profile_data(profile_data, projection_years=5)

    print(f"✅ Scenario: {plan.name}")
    print(f"✅ Period: {plan.start_date} to {plan.end_date}")
    print(f"✅ Initial lots: {len(plan.initial_lots)}")
    print(f"✅ Planned actions: {len(plan.planned_actions)}")

    # Display equity position
    display_equity_position_summary(plan)

    # Run projection calculation
    print(f"\nRunning multi-year projection...")
    calculator = ProjectionCalculator(user_profile)
    result = calculator.evaluate_projection_plan(plan)

    print(f"✅ Projection complete: {len(result.yearly_states)} years evaluated")

    # Display results
    display_projection_results(result)

    # Save CSV outputs
    print(f"\nSaving results to CSV files...")
    output_dir = "output/natural_evolution"
    save_all_projection_csvs(result, "Natural Evolution", output_dir)

    print(f"✅ CSV files saved to: {output_dir}/")
    print(f"  - natural_evolution_annual_tax_detail.csv")
    print(f"  - natural_evolution_state_timeline.csv")
    print(f"  - natural_evolution_transition_timeline.csv")
    print(f"  - natural_evolution_action_summary.csv")
    print(f"  - natural_evolution_annual_summary.csv")
    print(f"  - natural_evolution_holding_period_tracking.csv")
    print(f"  - natural_evolution_pledge_obligations.csv")
    print(f"  - natural_evolution_charitable_carryforward.csv")

    print(f"\nKEY INSIGHTS:")
    final_state = result.get_final_state()
    if final_state:
        cash_growth = final_state.ending_cash - plan.initial_cash
        print(f"  💰 Cash Growth: ${cash_growth:,.0f} over 5 years")
        print(f"  📈 Total Return: {(final_state.total_net_worth / (plan.initial_cash + final_state.total_equity_value - cash_growth) - 1):.1%} (est.)")
        print(f"  🎯 No pledge obligations created (no sales/tenders)")
        print(f"  ⚠️  Vested options remain unexercised")

    print(f"\nNEXT STEPS:")
    print(f"  1. Compare with 'Exercise All Vested' scenario")
    print(f"  2. Evaluate tender offer participation")
    print(f"  3. Model charitable donation strategies")
    print(f"  4. Optimize for pledge fulfillment")


if __name__ == "__main__":
    main()
