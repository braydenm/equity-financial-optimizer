"""
Timeline Generator - Data-source aware equity position timeline generation.

This module generates equity position timelines that match the active data source
(demo vs user), ensuring lot IDs in scenarios match those in the timeline.
"""

import os
import csv
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


class TimelineGenerator:
    """Generates equity position timelines for specific data sources."""

    def __init__(self, output_base_dir: str = "output"):
        """Initialize timeline generator.

        Args:
            output_base_dir: Base directory for output files
        """
        self.output_base_dir = Path(output_base_dir)

    def generate_timeline(self, profile: Dict[str, Any], is_demo: bool = False,
                         current_date: Optional[date] = None) -> str:
        """Generate equity position timeline for the given profile.

        Args:
            profile: User or demo profile data
            is_demo: Whether this is demo data
            current_date: Reference date for timeline generation

        Returns:
            Path to the generated timeline CSV file
        """
        # Determine output directory based on data source
        data_source = "demo" if is_demo else "user"
        output_dir = self.output_base_dir / data_source / "timeline"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timeline data
        timeline_rows = self._create_timeline_rows(profile, current_date)

        # Save to CSV
        output_path = output_dir / "equity_position_timeline.csv"
        self._save_timeline_csv(timeline_rows, output_path)

        print(f"📊 Generated {data_source} equity position timeline: {output_path}")
        return str(output_path)

    def _create_timeline_rows(self, profile: Dict[str, Any],
                             current_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Create timeline rows from profile data.

        Args:
            profile: Profile data
            current_date: Reference date for timeline

        Returns:
            List of timeline row dictionaries
        """
        equity_pos = profile['equity_position']

        # Use provided current_date or extract from profile metadata
        if current_date is None:
            metadata_date = profile.get('metadata', {}).get('last_updated')
            if metadata_date:
                current_date = datetime.fromisoformat(
                    metadata_date.split('T')[0] if 'T' in metadata_date else metadata_date
                ).date()
            else:
                current_date = date.today()

        rows = []

        # Add existing exercised lots
        for lot in equity_pos.get('exercised_lots', []):
            exercise_date = datetime.fromisoformat(lot['exercise_date']).date()
            holding_period_days = (current_date - exercise_date).days

            rows.append({
                'date': current_date.isoformat(),
                'lot_id': lot['lot_id'],
                'grant_id': self._get_grant_id(equity_pos, lot),
                'share_type': lot['type'],
                'quantity': lot['shares'],
                'strike_price': lot['strike_price'],
                'lifecycle_state': 'exercised_not_disposed',
                'tax_treatment': 'LTCG' if holding_period_days > 365 else 'STCG'
            })

        # Add current vested unexercised options
        vested = equity_pos.get('vested_unexercised', {})

        if vested.get('iso_shares', 0) > 0:
            # Get strike price from original grants
            strike_price = self._get_strike_price(equity_pos)
            rows.append({
                'date': current_date.isoformat(),
                'lot_id': 'ISO',
                'grant_id': self._get_grant_id(equity_pos),
                'share_type': 'ISO',
                'quantity': vested['iso_shares'],
                'strike_price': strike_price,
                'lifecycle_state': 'vested_not_exercised',
                'tax_treatment': 'N/A'
            })

        if vested.get('nso_shares', 0) > 0:
            strike_price = self._get_strike_price(equity_pos)
            rows.append({
                'date': current_date.isoformat(),
                'lot_id': 'NSO',
                'grant_id': self._get_grant_id(equity_pos),
                'share_type': 'NSO',
                'quantity': vested['nso_shares'],
                'strike_price': strike_price,
                'lifecycle_state': 'vested_not_exercised',
                'tax_treatment': 'N/A'
            })

        # Add vesting calendar events
        vesting_events = self._generate_vesting_events(equity_pos, current_date)
        rows.extend(vesting_events)

        # Sort by date, then lot_id
        rows.sort(key=lambda x: (x['date'], x['lot_id']))

        return rows

    def _get_strike_price(self, equity_pos: Dict[str, Any]) -> float:
        """Extract strike price from original grants."""
        grants = equity_pos.get('grants', [])
        if grants:
            return grants[0].get('strike_price', 0.0)
        return 0.0

    def _get_grant_id(self, equity_pos: Dict[str, Any], lot_data: Dict[str, Any] = None) -> str:
        """Extract grant_id from lot data or original grants."""
        # First try to get grant_id from the lot data itself
        if lot_data and 'grant_id' in lot_data:
            return lot_data['grant_id']

        # Fallback to first grant ID if available
        grants = equity_pos.get('grants', [])
        if grants and 'grant_id' in grants[0]:
            return grants[0]['grant_id']

        return 'UNKNOWN'

    def _generate_vesting_events(self, equity_pos: Dict[str, Any],
                                current_date: date) -> List[Dict[str, Any]]:
        """Generate vesting calendar events."""
        unvested = equity_pos.get('unvested', {})
        vesting_calendar = unvested.get('vesting_calendar', [])

        strike_price = self._get_strike_price(equity_pos)
        vesting_events = []

        for event in vesting_calendar:
            vest_date = datetime.fromisoformat(event['date']).date()

            # Generate unique lot ID for each vesting event
            lot_id = f"VEST_{vest_date.strftime('%Y%m%d')}_{event['share_type']}"

            # Determine lifecycle state based on whether vesting has occurred
            if vest_date <= current_date:
                lifecycle_state = 'vested_not_exercised'
            else:
                lifecycle_state = 'granted_not_vested'

            vesting_events.append({
                'date': vest_date.isoformat(),
                'lot_id': lot_id,
                'grant_id': self._get_grant_id(equity_pos),
                'share_type': event['share_type'],
                'quantity': event['shares'],
                'strike_price': strike_price,
                'lifecycle_state': lifecycle_state,
                'tax_treatment': 'N/A'
            })

        return vesting_events

    def _save_timeline_csv(self, rows: List[Dict[str, Any]], output_path: Path) -> None:
        """Save timeline rows to CSV file."""
        if not rows:
            print("⚠️  No timeline data to save")
            return

        fieldnames = ['date', 'lot_id', 'grant_id', 'share_type', 'quantity',
                     'strike_price', 'lifecycle_state', 'tax_treatment']

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def get_timeline_path(self, is_demo: bool = False) -> Path:
        """Get the path where timeline would be saved for given data source.

        Args:
            is_demo: Whether to get demo timeline path

        Returns:
            Path to timeline CSV file
        """
        data_source = "demo" if is_demo else "user"
        return self.output_base_dir / data_source / "timeline" / "equity_position_timeline.csv"

    def timeline_exists(self, is_demo: bool = False) -> bool:
        """Check if timeline exists for given data source.

        Args:
            is_demo: Whether to check demo timeline

        Returns:
            True if timeline exists
        """
        return self.get_timeline_path(is_demo).exists()


def generate_timeline_for_profile(profile: Dict[str, Any], is_demo: bool = False,
                                 output_base_dir: str = "output") -> str:
    """Convenience function to generate timeline for a profile.

    Args:
        profile: Profile data
        is_demo: Whether this is demo data
        output_base_dir: Base directory for output

    Returns:
        Path to generated timeline CSV
    """
    generator = TimelineGenerator(output_base_dir)
    return generator.generate_timeline(profile, is_demo)
