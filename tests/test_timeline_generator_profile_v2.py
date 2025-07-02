#!/usr/bin/env python3
"""
Test suite for TimelineGenerator with Profile v2.0 structure.

These tests demonstrate the current bugs in TimelineGenerator:
1. It expects a flat structure but profiles use grant-based structure
2. It fails to generate future vesting events
3. EquityLoader creates duplicate lot IDs with multiple grants
"""

import sys
import os
from datetime import date

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.timeline_generator import TimelineGenerator


def test_timeline_generator_single_grant_profile():
    """Test timeline generation with v2.0 single grant profile."""
    profile = {
        'equity_position': {
            'grants': [{
                'grant_id': 'TEST-001',
                'strike_price': 5.00,
                'vesting_status': {
                    'vested_unexercised': {
                        'iso': 1000,
                        'nso': 2000
                    },
                    'unvested': {
                        'vesting_calendar': [
                            {'date': '2025-07-24', 'shares': 3107, 'share_type': 'ISO'}
                        ]
                    }
                }
            }]
        }
    }
    
    generator = TimelineGenerator()
    timeline_rows = generator._create_timeline_rows(profile, date(2025, 6, 1))
    
    # Should have vested shares + future vesting event
    assert len(timeline_rows) >= 3, f"Expected at least 3 rows, got {len(timeline_rows)}"
    
    # Check for vested ISO shares
    iso_vested = None
    for row in timeline_rows:
        if 'ISO' in row['lot_id'] and row['lifecycle_state'] == 'vested_not_exercised':
            iso_vested = row
            break
    
    assert iso_vested is not None, "Should have vested ISO shares"
    assert iso_vested['quantity'] == 1000, f"Expected 1000 ISO shares, got {iso_vested['quantity']}"
    
    # Check for vested NSO shares
    nso_vested = None
    for row in timeline_rows:
        if 'NSO' in row['lot_id'] and row['lifecycle_state'] == 'vested_not_exercised':
            nso_vested = row
            break
    
    assert nso_vested is not None, "Should have vested NSO shares"
    assert nso_vested['quantity'] == 2000, f"Expected 2000 NSO shares, got {nso_vested['quantity']}"
    
    # Check for future vesting event
    future_vest = None
    for row in timeline_rows:
        if 'VEST_20250724' in row['lot_id']:
            future_vest = row
            break
    
    assert future_vest is not None, "Should have future vesting event VEST_20250724_ISO"
    assert future_vest['quantity'] == 3107, f"Expected 3107 shares in future vest, got {future_vest['quantity']}"
    assert future_vest['share_type'] == 'ISO', f"Expected ISO type, got {future_vest['share_type']}"


def test_timeline_generator_multi_grant_profile():
    """Test timeline generation with multiple grants."""
    profile = {
        'equity_position': {
            'grants': [
                {
                    'grant_id': 'ES-83',
                    'strike_price': 5.00,
                    'vesting_status': {
                        'vested_unexercised': {'iso': 1000, 'nso': 0},
                        'unvested': {
                            'vesting_calendar': [
                                {'date': '2025-07-24', 'shares': 1000, 'share_type': 'ISO'}
                            ]
                        }
                    }
                },
                {
                    'grant_id': 'ES-84',
                    'strike_price': 10.00,
                    'vesting_status': {
                        'vested_unexercised': {'iso': 500, 'nso': 1500},
                        'unvested': {
                            'vesting_calendar': [
                                {'date': '2025-08-24', 'shares': 2000, 'share_type': 'NSO'}
                            ]
                        }
                    }
                }
            ]
        }
    }
    
    generator = TimelineGenerator()
    timeline_rows = generator._create_timeline_rows(profile, date(2025, 6, 1))
    
    # Should have shares from both grants
    assert len(timeline_rows) >= 5, f"Expected at least 5 rows (2 grants with vested + future), got {len(timeline_rows)}"
    
    # Check grant 1 ISO vested
    grant1_iso = None
    for row in timeline_rows:
        if row.get('grant_id') == 'ES-83' and 'ISO' in row['lot_id']:
            grant1_iso = row
            break
    
    assert grant1_iso is not None, "Should have ISO shares from grant ES-83"
    assert grant1_iso['quantity'] == 1000, f"Expected 1000 shares, got {grant1_iso['quantity']}"
    assert grant1_iso['strike_price'] == 5.00, f"Expected strike price 5.00, got {grant1_iso['strike_price']}"
    
    # Check grant 2 NSO vested
    grant2_nso = None
    for row in timeline_rows:
        if row.get('grant_id') == 'ES-84' and 'NSO' in row['lot_id']:
            grant2_nso = row
            break
    
    assert grant2_nso is not None, "Should have NSO shares from grant ES-84"
    assert grant2_nso['quantity'] == 1500, f"Expected 1500 shares, got {grant2_nso['quantity']}"
    assert grant2_nso['strike_price'] == 10.00, f"Expected strike price 10.00, got {grant2_nso['strike_price']}"
    
    # Check future vesting events from both grants
    future_vests = [row for row in timeline_rows if 'VEST_' in row['lot_id']]
    assert len(future_vests) >= 2, f"Expected at least 2 future vesting events, got {len(future_vests)}"


def test_timeline_generator_backward_compatibility():
    """Test timeline generation with old profile structure."""
    profile = {
        'equity_position': {
            'vested_unexercised': {
                'iso_shares': 1000,
                'nso_shares': 2000
            },
            'unvested': {
                'vesting_calendar': [
                    {'date': '2025-07-24', 'shares': 3107, 'share_type': 'ISO'}
                ]
            }
        }
    }
    
    generator = TimelineGenerator()
    timeline_rows = generator._create_timeline_rows(profile, date(2025, 6, 1))
    
    # Should still work with old structure
    assert len(timeline_rows) > 0, "Should generate rows with old profile structure"
    
    # Check that we have the expected vested shares
    has_iso = any(row['share_type'] == 'ISO' and row['quantity'] == 1000 for row in timeline_rows)
    has_nso = any(row['share_type'] == 'NSO' and row['quantity'] == 2000 for row in timeline_rows)
    
    assert has_iso, "Should have ISO vested shares"
    assert has_nso, "Should have NSO vested shares"


def test_equity_loader_lot_id_collision():
    """Test that EquityLoader creates unique lot IDs for multiple grants."""
    from loaders.equity_loader import EquityLoader
    
    profile = {
        'equity_position': {
            'grants': [
                {
                    'grant_id': 'GRANT-001',
                    'grant_date': '2020-01-15',
                    'expiration_date': '2030-01-15',
                    'strike_price': 5.00,
                    'vesting_status': {
                        'vested_unexercised': {'iso': 1000, 'nso': 0}
                    }
                },
                {
                    'grant_id': 'GRANT-002',
                    'grant_date': '2021-01-15',
                    'expiration_date': '2031-01-15',
                    'strike_price': 10.00,
                    'vesting_status': {
                        'vested_unexercised': {'iso': 2000, 'nso': 0}
                    }
                }
            ]
        }
    }
    
    loader = EquityLoader()
    lots = loader.load_lots_from_profile(profile)
    
    # Check lot IDs
    lot_ids = [lot.lot_id for lot in lots]
    
    # This will FAIL - currently creates duplicate 'ISO' lot IDs
    assert len(lot_ids) == len(set(lot_ids)), f"Lot IDs should be unique, but got: {lot_ids}"
    
    # Each grant should have unique lot IDs
    grant1_lots = [lot for lot in lots if lot.grant_id == 'GRANT-001']
    grant2_lots = [lot for lot in lots if lot.grant_id == 'GRANT-002']
    
    assert len(grant1_lots) == 1, f"Expected 1 lot for GRANT-001, got {len(grant1_lots)}"
    assert len(grant2_lots) == 1, f"Expected 1 lot for GRANT-002, got {len(grant2_lots)}"
    
    # Lot IDs should include grant ID to be unique
    assert grant1_lots[0].lot_id != grant2_lots[0].lot_id, \
        f"Lot IDs should be different: {grant1_lots[0].lot_id} vs {grant2_lots[0].lot_id}"


if __name__ == "__main__":
    print("Running TimelineGenerator Profile v2.0 tests...")
    print("These tests are expected to FAIL with the current implementation.")
    print("They demonstrate bugs that need to be fixed.\n")
    
    tests = [
        ("Single grant profile", test_timeline_generator_single_grant_profile),
        ("Multi-grant profile", test_timeline_generator_multi_grant_profile),
        ("Backward compatibility", test_timeline_generator_backward_compatibility),
        ("EquityLoader lot ID collision", test_equity_loader_lot_id_collision)
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        try:
            test_func()
            print(f"✓ PASSED (unexpected - this test should fail!)")
        except AssertionError as e:
            print(f"✗ FAILED (expected): {e}")
            failed_tests.append((test_name, str(e)))
        except Exception as e:
            print(f"✗ ERROR: {type(e).__name__}: {e}")
            failed_tests.append((test_name, f"ERROR: {e}"))
    
    print(f"\n\nSummary: {len(failed_tests)}/{len(tests)} tests failed (as expected)")
    print("\nThese failures confirm the bugs exist and need to be fixed:")
    for test_name, error in failed_tests:
        print(f"- {test_name}: {error}")