#!/usr/bin/env python3
"""
Simple Timeline Demo - Actions to Timelines

This example shows the core workflow:
1. User manually creates actions.csv
2. System automatically generates state and transition timelines
3. No procedural generation, just CSV in → CSV out
"""

import sys
import os
import csv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.portfolio_manager import execute_single_scenario


def show_actions_to_timelines():
    """Demonstrate how actions.csv generates timeline CSVs."""
    print("ACTIONS → TIMELINES WORKFLOW")
    print("=" * 80)
    print("User creates actions.csv → System generates timeline CSVs")
    print()

    # Focus on the working scenarios
    scenarios = [
        {
            "name": "Natural Evolution",
            "path": "scenarios/natural_evolution",
            "description": "No actions - baseline scenario"
        },
        {
            "name": "Exercise All Vested",
            "path": "scenarios/exercise_all_vested",
            "description": "Exercise vested options on July 1, 2025"
        }
    ]

    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario['name']}")
        print(f"Description: {scenario['description']}")
        print(f"{'='*60}")

        # Show input: actions.csv
        actions_path = os.path.join(scenario['path'], "actions.csv")
        print(f"\nINPUT: {actions_path}")
        print("-" * 40)

        with open(actions_path, 'r') as f:
            content = f.read().strip()
            if content:
                print(content)
            else:
                print("(No actions - baseline scenario)")

        # Execute to generate timelines
        print(f"\nPROCESSING...")
        output_dir = f"output/simple_demo/{scenario['name'].lower().replace(' ', '_')}"

        try:
            result = execute_single_scenario(
                scenario_path=scenario['path'],
                price_scenario='moderate',
                projection_years=5,
                output_dir=output_dir
            )
            print(f"✅ Success!")

            # Show output files
            print(f"\nOUTPUT FILES in {output_dir}:")
            print("-" * 40)

            # List timeline files
            if os.path.exists(output_dir):
                files = sorted([f for f in os.listdir(output_dir) if f.endswith('.csv')])
                for file in files:
                    if 'timeline' in file:
                        print(f"  • {file} {'← NEW!' if 'state_timeline' in file or 'transition_timeline' in file else ''}")
                    else:
                        print(f"  • {file}")

                # Show sample of state timeline
                state_file = next((f for f in files if 'state_timeline' in f), None)
                if state_file:
                    print(f"\nSAMPLE: State Timeline for LOT-01")
                    print("-" * 40)
                    path = os.path.join(output_dir, state_file)
                    with open(path, 'r') as f:
                        reader = csv.DictReader(f)
                        print(f"{'State':<20} 2025   2026   2027   2028   2029")
                        for row in reader:
                            if row['Lot_ID'] == 'LOT-01':
                                state = row['State']
                                if state in ['Vested', 'Exercised', 'TOTAL']:
                                    values = [row.get(str(y), '0') for y in range(2025, 2030)]
                                    print(f"{state:<20} {values[0]:>6} {values[1]:>6} {values[2]:>6} {values[3]:>6} {values[4]:>6}")

        except Exception as e:
            print(f"❌ Error: {e}")


def explain_lot_naming():
    """Explain the automatic lot naming on exercise."""
    print("\n" + "=" * 80)
    print("AUTOMATIC LOT NAMING")
    print("=" * 80)

    print("\nWhen options are exercised, new lot IDs are created automatically:")
    print("\nExample: VESTED_ISO exercised on 2025-07-01")
    print("  Before: VESTED_ISO (12,427 shares, vested)")
    print("  After:  VESTED_ISO_EX_20250701 (12,427 shares, exercised)")
    print("\nThis enables:")
    print("  • Tracking exercise date for tax calculations")
    print("  • Calculating holding period for LTCG qualification")
    print("  • Maintaining complete audit trail")


def main():
    """Run the simple timeline demonstration."""
    print("=" * 80)
    print("SIMPLE TIMELINE GENERATION")
    print("CSV Actions → State & Transition Timelines")
    print("=" * 80)
    print()

    # Show the workflow
    show_actions_to_timelines()

    # Explain lot naming
    explain_lot_naming()

    print("\n" + "=" * 80)
    print("KEY TAKEAWAYS")
    print("=" * 80)
    print("• Actions are manually specified in CSV format")
    print("• State timelines show share quantities in each state over time")
    print("• Transition timelines show movements between states")
    print("• Lot naming preserves exercise dates automatically")
    print("• Simple, auditable, and transparent")
    print()

    # Cleanup
    import shutil
    if os.path.exists("output/simple_demo"):
        shutil.rmtree("output/simple_demo")
        print("✓ Cleaned up demo output files")


if __name__ == "__main__":
    main()
