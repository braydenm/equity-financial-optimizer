#!/usr/bin/env python3
"""
Script to copy formatted CSV files from a scenario to clipboard for spreadsheet viewing.
Usage: python copy_scenario_csvs.py <3-digit-scenario-id>
Example: python copy_scenario_csvs.py 200
"""

import os
import sys
import csv
import glob
from typing import List, Dict

def find_scenario_directory(scenario_id: str) -> str:
    """Find the full scenario directory path from a 3-digit ID."""
    base_path = "output/user/moderate"
    pattern = f"{base_path}/scenario_{scenario_id}_*"
    matches = glob.glob(pattern)

    if not matches:
        raise ValueError(f"No scenario directory found for ID {scenario_id}")
    if len(matches) > 1:
        raise ValueError(f"Multiple scenario directories found for ID {scenario_id}: {matches}")

    return matches[0]

def read_csv_as_text(file_path: str) -> List[str]:
    """Read CSV file and return as list of tab-separated lines for spreadsheet compatibility."""
    lines = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                # Convert to tab-separated for better spreadsheet compatibility
                lines.append('\t'.join(row))
    except Exception as e:
        lines.append(f"Error reading {file_path}: {str(e)}")
    return lines

def get_file_priority() -> Dict[str, int]:
    """Define the order in which CSV files should appear."""
    return {
        'annual_summary.csv': 1,
        'action_summary.csv': 2,
        'annual_tax_detail.csv': 3,
        'comprehensive_cashflow.csv': 4,
        'pledge_obligations.csv': 5,
        'charitable_carryforward.csv': 6,
        'holding_period_tracking.csv': 7,
        'state_timeline.csv': 8,
        'transition_timeline.csv': 9,
    }

def format_filename_for_header(filename: str) -> str:
    """Convert filename to a readable header."""
    # Remove the scenario prefix and .csv extension
    name = filename.split('_', 1)[-1] if '_' in filename else filename
    name = name.replace('.csv', '')

    # Convert underscores to spaces and title case
    return name.replace('_', ' ').title()

def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using available methods."""
    try:
        # Try pyperclip first (cross-platform)
        import pyperclip
        pyperclip.copy(text)
        return True
    except ImportError:
        pass

    try:
        # Try macOS pbcopy
        import subprocess
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-8'))
        return process.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    try:
        # Try Linux xclip
        import subprocess
        process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-8'))
        return process.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python copy_scenario_csvs.py <3-digit-scenario-id>")
        print("Example: python copy_scenario_csvs.py 200")
        sys.exit(1)

    scenario_id = sys.argv[1]

    # Validate scenario ID format
    if not scenario_id.isdigit() or len(scenario_id) != 3:
        print("Error: Scenario ID must be exactly 3 digits")
        sys.exit(1)

    try:
        # Find the scenario directory
        scenario_dir = find_scenario_directory(scenario_id)
        print(f"Found scenario directory: {scenario_dir}")

        # Get all CSV files
        csv_files = glob.glob(f"{scenario_dir}/*.csv")
        if not csv_files:
            print("No CSV files found in scenario directory")
            sys.exit(1)

        # Sort files by priority, then alphabetically
        priority = get_file_priority()
        csv_files.sort(key=lambda f: (
            priority.get(os.path.basename(f), 999),
            os.path.basename(f)
        ))

        # Build the combined output
        output_lines = []

        # Add header with scenario info
        scenario_name = os.path.basename(scenario_dir)
        output_lines.append(f"SCENARIO ANALYSIS: {scenario_name}")
        output_lines.append("=" * 80)
        output_lines.append("")

        # Process each CSV file
        for i, csv_file in enumerate(csv_files):
            filename = os.path.basename(csv_file)
            header = format_filename_for_header(filename)

            # Add section header
            output_lines.append(f"{header.upper()}")
            output_lines.append("-" * len(header))

            # Add CSV content
            csv_content = read_csv_as_text(csv_file)
            output_lines.extend(csv_content)

            # Add spacing between sections (except after last file)
            if i < len(csv_files) - 1:
                output_lines.extend(["", "", ""])

        # Combine all lines
        final_output = '\n'.join(output_lines)

        # Copy to clipboard
        if copy_to_clipboard(final_output):
            print(f"✅ Successfully copied {len(csv_files)} CSV files to clipboard!")
            print(f"📋 Total lines: {len(output_lines)}")
            print("\nFiles included:")
            for csv_file in csv_files:
                filename = os.path.basename(csv_file)
                print(f"  - {format_filename_for_header(filename)}")
            print("\n💡 Paste into your spreadsheet - data is tab-separated for easy column parsing")
        else:
            print("❌ Failed to copy to clipboard. Here's the formatted output:")
            print("\n" + "="*80)
            print(final_output)
            print("="*80)
            print("\n💡 To enable clipboard support, install pyperclip: pip install pyperclip")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
