"""
Equity Position Timeline Generator

Generates equity_position_timeline.csv describing all share lots and vesting events.
Orders by time, then lot_id. Shows current positions and future vesting calendar.
This serves as the base inventory for scenario planning and strategy generation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import csv
import argparse
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Tuple

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loaders.profile_loader import ProfileLoader

def load_user_profile() -> Tuple[Dict[str, Any], bool]:
    """Load user profile with secure fallback to demo data."""
    loader = ProfileLoader()
    return loader.load_profile(verbose=True)

def generate_vesting_calendar(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Read vesting events from hardcoded calendar."""
    equity_pos = profile['equity_position']

    # Read from hardcoded vesting calendar
    vesting_calendar = equity_pos['unvested'].get('vesting_calendar', [])

    vesting_events = []
    for event in vesting_calendar:
        vesting_events.append({
            'vest_date': datetime.fromisoformat(event['date']).date(),
            'shares_vesting': event['shares'],
            'share_type': event['share_type']
        })

    return vesting_events

def create_realistic_lifecycle_csv(profile: Dict[str, Any], current_date: date = None) -> List[Dict[str, Any]]:
    """Create lifecycle CSV from actual user data."""
    equity_pos = profile['equity_position']

    # Extract key parameters from profile
    strike_price = equity_pos['original_grants'][0]['strike_price']

    # Use provided current_date or extract from profile metadata
    if current_date is None:
        metadata_date = profile.get('metadata', {}).get('last_updated')
        if metadata_date:
            current_date = datetime.fromisoformat(metadata_date.split('T')[0] if 'T' in metadata_date else metadata_date).date()
        else:
            current_date = date.today()

    start_date = current_date  # Start from the reference date

    rows = []

    # Current exercised lots - these exist as of today
    exercised_lots = equity_pos['exercised_lots']

    # Current vested unexercised options
    vested_iso = equity_pos['vested_unexercised']['iso_shares']
    vested_nso = equity_pos['vested_unexercised']['nso_shares']

    # Generate vesting calendar
    vesting_calendar = generate_vesting_calendar(profile)

    def get_price_for_date(target_date):
        """Price calculation left undefined - to be determined later."""
        return None  # Prices left undefined for future planning

    # Add all vesting events from the hardcoded calendar with unique lot IDs
    for vest_event in vesting_calendar:
        vest_date = vest_event['vest_date']

        # Generate unique lot ID for each vesting event using share type
        lot_id = f"VEST_{vest_date.strftime('%Y%m%d')}_{vest_event['share_type']}"

        # Determine lifecycle state based on whether vesting has occurred
        if vest_date <= current_date:
            lifecycle_state = 'vested_not_exercised'
        else:
            lifecycle_state = 'granted_not_vested'

        rows.append({
            'date': vest_date.isoformat(),
            'lot_id': lot_id,
            'share_type': vest_event['share_type'],
            'quantity': vest_event['shares_vesting'],
            'strike_price': strike_price,
            'lifecycle_state': lifecycle_state,
            'tax_treatment': 'N/A'
        })

    # Add existing exercised lots (shown once at start)
    for lot in exercised_lots:
        # Determine lifecycle state and tax treatment
        exercise_date = datetime.fromisoformat(lot['exercise_date']).date()
        holding_period_days = (start_date - exercise_date).days

        lifecycle_state = 'exercised_not_disposed'
        tax_treatment = 'LTCG' if holding_period_days > 365 else 'STCG'

        rows.append({
            'date': start_date.isoformat(),
            'lot_id': lot['lot_id'],
            'share_type': lot['type'],
            'quantity': lot['shares'],
            'strike_price': lot['strike_price'],
            'lifecycle_state': lifecycle_state,
            'tax_treatment': tax_treatment
        })

    # Add current vested unexercised options
    if vested_iso > 0:
        rows.append({
            'date': start_date.isoformat(),
            'lot_id': 'VESTED_ISO',
            'share_type': 'ISO',
            'quantity': vested_iso,
            'strike_price': strike_price,
            'lifecycle_state': 'vested_not_exercised',
            'tax_treatment': 'N/A'
        })

    if vested_nso > 0:
        rows.append({
            'date': start_date.isoformat(),
            'lot_id': 'VESTED_NSO',
            'share_type': 'NSO',
            'quantity': vested_nso,
            'strike_price': strike_price,
            'lifecycle_state': 'vested_not_exercised',
            'tax_treatment': 'N/A'
        })

    # Sort by date, then lot_id as requested
    rows.sort(key=lambda x: (x['date'], x['lot_id']))

    return rows

def main():
    """Generate equity position timeline CSV from actual user data."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate equity position timeline CSV')
    parser.add_argument('--current-date', type=str, help='Current date for reference (YYYY-MM-DD)', default=None)
    parser.add_argument('--profile-path', type=str, help='Path to user profile JSON', default=None)
    args = parser.parse_args()

    print("EQUITY POSITION TIMELINE GENERATOR")
    print("=" * 50)
    print("Using actual user_profile.json data...")

    # Parse current date if provided
    current_date = None
    if args.current_date:
        try:
            current_date = datetime.fromisoformat(args.current_date).date()
            print(f"📅 Using reference date: {current_date}")
        except ValueError:
            print(f"❌ Invalid date format: {args.current_date}. Use YYYY-MM-DD")
            return

    # Load profile
    try:
        profile, is_real_data = load_user_profile()
        print(f"✅ Loaded profile version {profile['metadata']['profile_version']}")

        # Show the reference date being used
        if current_date is None:
            metadata_date = profile.get('metadata', {}).get('last_updated', 'today')
            print(f"📅 Using reference date from profile: {metadata_date}")

    except FileNotFoundError:
        print("❌ Could not find user_profile.json in data/")
        return

    # Generate lifecycle data
    lifecycle_rows = create_realistic_lifecycle_csv(profile, current_date)

    # Create output directory
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'equity_position_timeline')
    os.makedirs(output_dir, exist_ok=True)

    # Save to CSV
    filename = os.path.join(output_dir, 'equity_position_timeline.csv')
    with open(filename, 'w', newline='') as f:
        if lifecycle_rows:
            writer = csv.DictWriter(f, fieldnames=lifecycle_rows[0].keys())
            writer.writeheader()
            writer.writerows(lifecycle_rows)

    print(f"\n📁 Equity position timeline saved to: {filename}")

    # Show summary
    vest_events = [r for r in lifecycle_rows if r['lot_id'].startswith('VEST_')]
    existing_lots = [r for r in lifecycle_rows if not r['lot_id'].startswith('VEST_')]

    print(f"\nSummary:")
    print(f"  - {len(vest_events)} future vesting events")
    print(f"  - {len(existing_lots)} existing positions")
    print(f"  - Ordered by: time, then lot_id")
    print(f"  - Using vesting calendar from profile")

    # Show first few vesting events
    if vest_events:
        print(f"\nNext vesting events:")
        for event in vest_events[:8]:
            print(f"  {event['date']}: {event['quantity']} {event['share_type']} shares vest (lot: {event['lot_id']})")

    print(f"\n✨ Equity position timeline includes:")
    print(f"  - Real grant: {profile['equity_position']['original_grants'][0]['total_options']} options")
    print(f"  - Strike price: ${profile['equity_position']['original_grants'][0]['strike_price']}")
    print(f"  - Total unvested: {profile['equity_position']['unvested']['total_shares']} shares")
    print(f"  - Real holdings: {len(profile['equity_position']['exercised_lots'])} exercised lots")
    print(f"  - Vesting calendar: {len(profile['equity_position']['unvested'].get('vesting_calendar', []))} events")
    print(f"  - Clear structure: date, lot_id, share_type, quantity, strike_price, lifecycle_state, tax_treatment")
    print(f"\n💡 Usage: python3 {os.path.basename(__file__)} --current-date YYYY-MM-DD")

if __name__ == "__main__":
    main()
