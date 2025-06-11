"""
CSV loader for equity financial optimizer.

This module provides functionality to load equity positions and other
data from CSV files into the projection system's data structures.
"""

import csv
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from pathlib import Path

import sys
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ShareLot, ShareType, LifecycleState, TaxTreatment
)


class CSVLoader:
    """Load and parse CSV data for equity projections."""

    def load_initial_equity_position(self, csv_path: str) -> List[ShareLot]:
        """
        Load initial equity position from CSV timeline file.

        This method reads the equity_position_timeline.csv and extracts
        the current state of all equity lots. It filters to only include
        lots that are currently vested or exercised.

        Args:
            csv_path: Path to equity_position_timeline.csv

        Returns:
            List of ShareLot objects representing current equity position
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        lots = []
        seen_lots = {}  # Track lots to handle duplicates and get latest state

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                lot_id = row['lot_id']
                lifecycle_state = LifecycleState(row['lifecycle_state'])

                # Parse the row into a lot
                lot = self._parse_csv_row_to_lot(row)

                # Update our tracking - keep the latest state for each lot
                if lot_id not in seen_lots or self._is_later_state(lot, seen_lots[lot_id]):
                    seen_lots[lot_id] = lot

        # Filter to only include currently relevant lots
        for lot_id, lot in seen_lots.items():
            if lot.lifecycle_state in [
                LifecycleState.VESTED_NOT_EXERCISED,
                LifecycleState.EXERCISED_NOT_DISPOSED
            ]:
                lots.append(lot)

        return lots

    def load_full_timeline(self, csv_path: str) -> List[Dict[str, Any]]:
        """
        Load the complete timeline including all events.

        Args:
            csv_path: Path to equity_position_timeline.csv

        Returns:
            List of dictionaries with all timeline entries
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        timeline = []

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert date string to date object
                row['date'] = datetime.strptime(row['date'], '%Y-%m-%d').date()
                # Convert numeric fields
                row['quantity'] = int(row['quantity'])
                row['strike_price'] = float(row['strike_price'])
                timeline.append(row)

        return timeline

    def _parse_csv_row_to_lot(self, row: Dict[str, str]) -> ShareLot:
        """
        Parse a CSV row into a ShareLot object.

        Args:
            row: Dictionary from CSV reader

        Returns:
            ShareLot object
        """
        # Parse date
        event_date = datetime.strptime(row['date'], '%Y-%m-%d').date()

        # Create ShareLot
        lot = ShareLot(
            lot_id=row['lot_id'],
            share_type=ShareType(row['share_type']),
            quantity=int(row['quantity']),
            strike_price=float(row['strike_price']),
            grant_date=event_date,  # Using event date as grant date (approximate)
            lifecycle_state=LifecycleState(row['lifecycle_state']),
            tax_treatment=TaxTreatment(row['tax_treatment']) if row['tax_treatment'] != 'N/A' else TaxTreatment.NA
        )

        # For exercised lots, set cost basis (exercise date will be applied later)
        if lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED:
            lot.cost_basis = lot.strike_price
            # Exercise date will be set by calling code from user profile data
            lot.exercise_date = None

        return lot

    def _is_later_state(self, new_lot: ShareLot, existing_lot: ShareLot) -> bool:
        """
        Determine if new_lot represents a later state than existing_lot.

        This is used when processing timeline to keep only the latest
        state of each lot.

        Args:
            new_lot: Potentially newer lot state
            existing_lot: Current lot state

        Returns:
            True if new_lot is a later state
        """
        # Define lifecycle progression order
        state_order = {
            LifecycleState.GRANTED_NOT_VESTED: 0,
            LifecycleState.VESTED_NOT_EXERCISED: 1,
            LifecycleState.EXERCISED_NOT_DISPOSED: 2,
            LifecycleState.DISPOSED: 3
        }

        return state_order.get(new_lot.lifecycle_state, -1) > state_order.get(existing_lot.lifecycle_state, -1)

    def load_vesting_schedule(self, csv_path: str,
                            start_date: Optional[date] = None,
                            end_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """
        Load future vesting events from timeline.

        Args:
            csv_path: Path to equity_position_timeline.csv
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of vesting events within date range
        """
        timeline = self.load_full_timeline(csv_path)

        vesting_events = []
        for entry in timeline:
            # Filter for vesting events
            if entry['lifecycle_state'] == 'granted_not_vested':
                # Apply date filters if provided
                if start_date and entry['date'] < start_date:
                    continue
                if end_date and entry['date'] > end_date:
                    continue

                vesting_events.append({
                    'date': entry['date'],
                    'lot_id': entry['lot_id'],
                    'share_type': entry['share_type'],
                    'quantity': entry['quantity'],
                    'strike_price': entry['strike_price']
                })

        return sorted(vesting_events, key=lambda x: x['date'])

    def validate_exercise_dates(self, lots: List[ShareLot]) -> None:
        """
        Validate that all exercised lots have exercise dates.
        Call this after loading exercise dates from external source.
        """
        missing_dates = []
        for lot in lots:
            if (lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED
                and lot.exercise_date is None):
                missing_dates.append(lot.lot_id)

        if missing_dates:
            raise ValueError(
                f"Exercise dates missing for exercised lots: {', '.join(missing_dates)}. "
                f"Exercised lots must have exercise_date specified. "
                f"Add exercise dates from user_profile.json or CSV data. "
                f"This ensures accurate tax treatment and holding period calculations."
            )

    def save_equity_position(self, lots: List[ShareLot], output_path: str) -> None:
        """
        Save equity position to CSV file.

        Args:
            lots: List of ShareLot objects
            output_path: Path for output CSV file
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', newline='') as f:
            fieldnames = ['lot_id', 'share_type', 'quantity', 'strike_price',
                         'lifecycle_state', 'tax_treatment', 'exercise_date', 'cost_basis']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for lot in lots:
                writer.writerow({
                    'lot_id': lot.lot_id,
                    'share_type': lot.share_type.value,
                    'quantity': lot.quantity,
                    'strike_price': lot.strike_price,
                    'lifecycle_state': lot.lifecycle_state.value,
                    'tax_treatment': lot.tax_treatment.value,
                    'exercise_date': lot.exercise_date.isoformat() if lot.exercise_date else '',
                    'cost_basis': lot.cost_basis
                })
