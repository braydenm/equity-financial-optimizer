#!/usr/bin/env python3
"""
Test Timeline Generation from Actions CSV

This script demonstrates the simple workflow:
1. User creates actions.csv manually
2. System generates state and transition timelines automatically
3. No procedural generation or JSON configs needed
"""

import sys
import os
import csv
from datetime import date

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.portfolio_manager import execute_single_scenario


def demonstrate_timeline_generation():
    """Show how timelines are generated from manual actions.csv files."""
    print("=" * 80)
    print("TIMELINE GENERATION FROM ACTIONS.CSV")
    print("=" * 80)

    # Use existing scenarios with manually created actions.csv files
    scenarios = [
        ("Natural Evolution", "scenarios/natural_evolution"),
        ("Exercise All Vested", "scenarios/exercise_all_vested"),
        ("Tender and Donate", "scenarios/tender_and_donate")
    ]

    for scenario_name, scenario_path in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario_name}")
        print(f"{'='*60}")

        # Show the actions.csv content
        actions_path = os.path.join(scenario_path, "actions.csv")
        print(f"\nActions defined in {actions_path}:")
        with open(actions_path, 'r') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i < 5 and not row[0].startswith('#'):  # Show first few non-comment rows
                    print(f"  {', '.join(row)}")

        # Execute scenario to generate timelines
        print(f"\nGenerating timelines...")
        output_dir = f"output/timeline_demo/{scenario_name.lower().replace(' ', '_')}"

        result = execute_single_scenario(
            scenario_path=scenario_path,
            price_scenario='moderate',
            projection_years=5,
            output_dir=output_dir
        )

        print(f"✅ Timelines generated in {output_dir}")

        # Show what timeline files were created
        timeline_files = [
            f for f in os.listdir(output_dir)
            if 'timeline' in f and f.endswith('.csv')
        ]

        print(f"\nGenerated timeline files:")
        for file in sorted(timeline_files):
            print(f"  • {file}")

        # Display sample of state timeline
        state_timeline_file = next((f for f in timeline_files if 'state_timeline' in f), None)
        if state_timeline_file:
            print(f"\nSample from {state_timeline_file}:")
            file_path = os.path.join(output_dir, state_timeline_file)
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                # Show LOT-01 states as example
                print(f"  {'State':<20} 2025   2026   2027   2028   2029   2030")
                print("  " + "-" * 60)
                for row in reader:
                    if row['Lot_ID'] == 'LOT-01' and row['State'] in ['Vested', 'Exercised', 'Disposed_Sold', 'Disposed_Donated', 'TOTAL']:
                        years = [row.get(str(year), '0') for year in range(2025, 2031)]
                        print(f"  {row['State']:<20} {years[0]:>6} {years[1]:>6} {years[2]:>6} {years[3]:>6} {years[4]:>6} {years[5]:>6}")


def show_lot_naming_behavior():
    """Demonstrate automatic lot naming on exercise."""
    print("\n" + "=" * 80)
    print("LOT NAMING ON EXERCISE")
    print("=" * 80)

    print("\nWhen VESTED_ISO is exercised on 2025-07-01:")
    print("  • Original lot: VESTED_ISO (vested, unexercised)")
    print("  • After exercise: VESTED_ISO_EX_20250701 (exercised, held)")
    print("\nThis preserves:")
    print("  • Exercise date for tax calculations")
    print("  • Parent lot reference")
    print("  • Enables tracking of holding period for LTCG")


def main():
    """Run timeline generation demonstration."""
    print("ACTIONS.CSV → TIMELINE GENERATION")
    print("Simple workflow: manually create actions, automatically generate timelines")
    print("=" * 80)

    try:
        # Demonstrate timeline generation
        demonstrate_timeline_generation()

        # Show lot naming behavior
        show_lot_naming_behavior()

        print("\n" + "=" * 80)
        print("✅ TIMELINE GENERATION COMPLETE")
        print("=" * 80)
        print("\nKey Points:")
        print("• Actions are defined manually in CSV (no procedural generation)")
        print("• State timelines show share quantities over time")
        print("• Transition timelines show movements between states")
        print("• Lot naming happens automatically on exercise")
        print("• Simple, transparent, and auditable")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
