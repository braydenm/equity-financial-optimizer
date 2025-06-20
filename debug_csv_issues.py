#!/usr/bin/env python3
"""
Debug script to diagnose CSV generation issues.

This script creates a simple scenario and traces through the CSV generation
to identify where data is being lost or incorrectly calculated.
"""

import sys
import os
from datetime import date
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from projections.projection_state import (
    ProjectionPlan, ShareLot, PlannedAction,
    UserProfile, ShareType, LifecycleState, TaxTreatment, ActionType
)
from projections.projection_calculator import ProjectionCalculator
from projections.projection_output import save_all_projection_csvs


def create_debug_scenario():
    """Create a simple scenario for debugging."""
    # Simple profile
    profile = UserProfile(
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0765,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        annual_w2_income=300000,
        spouse_w2_income=150000,
        other_income=10000,
        current_cash=100000,
        exercise_reserves=50000,
        pledge_percentage=0.5,
        company_match_ratio=3.0,
        filing_status="married_filing_jointly",
        state_of_residence="California"
    )

    # Simple plan with RSU sale
    plan = ProjectionPlan(
        name="Debug Test",
        description="Simple test for debugging",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        initial_lots=[
            # RSU lot that we'll sell
            ShareLot(
                lot_id="RSU_2021",
                share_type=ShareType.RSU,
                quantity=2000,
                strike_price=0.0,
                grant_date=date(2021, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.LTCG,
                exercise_date=date(2021, 1, 1),
                cost_basis=20.0,
                fmv_at_exercise=20.0
            )
        ],
        initial_cash=100000
    )

    # Add a simple sale
    plan.add_action(PlannedAction(
        action_date=date(2025, 6, 1),
        action_type=ActionType.SELL,
        lot_id="RSU_2021",
        quantity=1000,
        price=60.0,
        notes="Test sale"
    ))

    # Set price projections
    plan.price_projections = {
        2025: 60.0
    }

    return profile, plan


def main():
    """Run debug scenario and inspect results."""
    print("CSV Generation Debug Script")
    print("=" * 60)

    # Create scenario
    profile, plan = create_debug_scenario()
    print(f"\nProfile W2 income: ${profile.annual_w2_income:,}")
    print(f"Profile spouse income: ${profile.spouse_w2_income:,}")
    print(f"Profile other income: ${profile.other_income:,}")
    print(f"Total income: ${profile.annual_w2_income + profile.spouse_w2_income + profile.other_income:,}")

    # Run projection
    print("\nRunning projection...")
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)

    # Inspect yearly state
    print("\nYearly State for 2025:")
    state_2025 = result.get_state_for_year(2025)
    if state_2025:
        print(f"  state.income: ${state_2025.income:,}")
        print(f"  state.spouse_income: ${state_2025.spouse_income:,}")
        print(f"  state.other_income: ${state_2025.other_income:,}")
        print(f"  state.exercise_costs: ${state_2025.exercise_costs:,}")
        print(f"  state.donation_value: ${state_2025.donation_value:,}")

        # Check annual tax components
        if state_2025.annual_tax_components:
            print("\n  Annual Tax Components:")
            print(f"    w2_income: ${state_2025.annual_tax_components.w2_income:,}")
            print(f"    spouse_income: ${state_2025.annual_tax_components.spouse_income:,}")
            print(f"    other_ordinary_income: ${state_2025.annual_tax_components.other_ordinary_income:,}")

            # Check sale components
            if state_2025.annual_tax_components.sale_components:
                print(f"\n    Sale Components ({len(state_2025.annual_tax_components.sale_components)}):")
                for i, sale in enumerate(state_2025.annual_tax_components.sale_components):
                    print(f"      Sale {i+1}:")
                    print(f"        lot_id: {sale.lot_id}")
                    print(f"        shares_sold: {sale.shares_sold}")
                    print(f"        sale_price: ${sale.sale_price}")
                    print(f"        long_term_gain: ${sale.long_term_gain:,}")

        # Check equity holdings at end of year
        print(f"\n  Equity Holdings ({len(state_2025.equity_holdings)}):")
        for lot in state_2025.equity_holdings:
            print(f"    {lot.lot_id}: {lot.quantity} shares ({lot.lifecycle_state.value})")

        # Check pledge state
        if state_2025.pledge_state and state_2025.pledge_state.obligations:
            print(f"\n  Pledge Obligations ({len(state_2025.pledge_state.obligations)}):")
            for i, obligation in enumerate(state_2025.pledge_state.obligations):
                print(f"    Obligation {i+1}:")
                print(f"      parent_transaction_id: {obligation.parent_transaction_id}")
                print(f"      shares_sold: {obligation.shares_sold}")
                print(f"      pledge_percentage: {obligation.pledge_percentage}")
                print(f"      total_pledge_obligation: ${obligation.total_pledge_obligation:,}")

    # Generate CSVs
    output_dir = "output/debug_csv"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nGenerating CSVs to {output_dir}/...")
    save_all_projection_csvs(result, "debug", output_dir)

    # Check specific CSV contents
    print("\nChecking generated CSVs:")

    # Check holding_period_tracking.csv
    holding_csv = os.path.join(output_dir, "debug_holding_period_tracking.csv")
    if os.path.exists(holding_csv):
        print(f"\n  {holding_csv}:")
        with open(holding_csv, 'r') as f:
            content = f.read()
            print("    " + "\n    ".join(content.strip().split('\n')[:5]))  # First 5 lines
    else:
        print(f"\n  ERROR: {holding_csv} not found!")

    # Check pledge_obligations.csv
    pledge_csv = os.path.join(output_dir, "debug_pledge_obligations.csv")
    if os.path.exists(pledge_csv):
        print(f"\n  {pledge_csv}:")
        with open(pledge_csv, 'r') as f:
            content = f.read()
            print("    " + "\n    ".join(content.strip().split('\n')[:5]))  # First 5 lines
    else:
        print(f"\n  ERROR: {pledge_csv} not found!")

    print("\n" + "=" * 60)
    print("Debug complete. Check output/debug_csv/ for full CSV files.")


if __name__ == "__main__":
    main()
