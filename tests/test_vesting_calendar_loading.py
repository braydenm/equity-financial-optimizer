#!/usr/bin/env python3
"""
Test that equity loader properly creates lots for future vesting events.

This test would have caught the issue where vesting calendar lots weren't
being created from the new grant structure with vesting_status.
"""

import unittest
import sys
import os
from datetime import date, datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loaders.equity_loader import EquityLoader
from projections.projection_state import ShareLot, LifecycleState


class TestVestingCalendarLoading(unittest.TestCase):
    """Test loading of future vesting events from grant structure."""

    def setUp(self):
        """Set up test data with the new grant structure."""
        self.profile_data = {
            "equity_position": {
                "grants": [
                    {
                        "grant_id": "GRANT_001",
                        "grant_date": "2023-01-15",
                        "type": "ISO/NSO",
                        "total_options": 50000,
                        "strike_price": 10.0,
                        "vesting_start_date": "2023-01-15",
                        "expiration_date": "2033-01-15",
                        "vesting_status": {
                            "vested_unexercised": {
                                "iso": 10000,
                                "nso": 5000
                            },
                            "unvested": {
                                "remaining_unvested": 35000,
                                "vesting_calendar": [
                                    {"date": "2025-06-24", "shares": 3106, "share_type": "ISO"},
                                    {"date": "2025-09-24", "shares": 3107, "share_type": "ISO"},
                                    {"date": "2025-12-24", "shares": 3107, "share_type": "NSO"},
                                    {"date": "2026-01-24", "shares": 3107, "share_type": "ISO"},
                                    {"date": "2026-03-24", "shares": 3107, "share_type": "NSO"}
                                ]
                            }
                        }
                    }
                ],
                "exercised_lots": []
            }
        }

        self.loader = EquityLoader(reference_date=date(2025, 1, 1))

    def test_vesting_calendar_lots_created(self):
        """Test that future vesting events create appropriate lots."""
        lots = self.loader.load_lots_from_profile(self.profile_data)

        # Find all VEST_ lots
        vest_lots = [lot for lot in lots if lot.lot_id.startswith('VEST_')]

        # Should have 5 vesting calendar entries
        self.assertEqual(len(vest_lots), 5,
                        f"Expected 5 VEST_ lots, got {len(vest_lots)}: {[lot.lot_id for lot in vest_lots]}")

        # Check specific lot IDs were created
        expected_lot_ids = [
            "VEST_20250624_ISO",
            "VEST_20250924_ISO",
            "VEST_20251224_NSO",
            "VEST_20260124_ISO",
            "VEST_20260324_NSO"
        ]

        actual_lot_ids = [lot.lot_id for lot in vest_lots]
        for expected_id in expected_lot_ids:
            self.assertIn(expected_id, actual_lot_ids,
                         f"Expected lot {expected_id} not found in {actual_lot_ids}")

    def test_vesting_lot_details(self):
        """Test that vesting lots have correct details."""
        lots = self.loader.load_lots_from_profile(self.profile_data)

        # Check the first vesting lot
        vest_lot = next((lot for lot in lots if lot.lot_id == "VEST_20250624_ISO"), None)
        self.assertIsNotNone(vest_lot, "VEST_20250624_ISO lot not found")

        # Verify lot details
        self.assertEqual(vest_lot.quantity, 3106)
        self.assertEqual(vest_lot.strike_price, 10.0)
        self.assertEqual(vest_lot.share_type.value, "ISO")
        self.assertEqual(vest_lot.grant_id, "GRANT_001")
        self.assertEqual(vest_lot.lifecycle_state, LifecycleState.GRANTED_NOT_VESTED)

        # Verify expiration date
        self.assertEqual(vest_lot.expiration_date, date(2033, 1, 15))

    def test_mixed_vested_and_unvested(self):
        """Test that both vested and unvested shares are loaded correctly."""
        lots = self.loader.load_lots_from_profile(self.profile_data)

        # Should have vested lots
        iso_lot = next((lot for lot in lots if lot.lot_id == "ISO"), None)
        nso_lot = next((lot for lot in lots if lot.lot_id == "NSO"), None)

        self.assertIsNotNone(iso_lot, "ISO vested lot not found")
        self.assertIsNotNone(nso_lot, "NSO vested lot not found")

        self.assertEqual(iso_lot.quantity, 10000)
        self.assertEqual(nso_lot.quantity, 5000)

        # Plus the 5 unvested lots
        vest_lots = [lot for lot in lots if lot.lot_id.startswith('VEST_')]
        self.assertEqual(len(vest_lots), 5)

        # Total should be 7 lots (2 vested + 5 unvested)
        self.assertEqual(len(lots), 7)

    def test_lifecycle_state_based_on_date(self):
        """Test that lifecycle state changes based on reference date."""
        # Create loader with future reference date
        future_loader = EquityLoader(reference_date=date(2025, 10, 1))
        lots = future_loader.load_lots_from_profile(self.profile_data)

        # Lots that should have vested by October 2025
        june_lot = next((lot for lot in lots if lot.lot_id == "VEST_20250624_ISO"), None)
        sept_lot = next((lot for lot in lots if lot.lot_id == "VEST_20250924_ISO"), None)
        dec_lot = next((lot for lot in lots if lot.lot_id == "VEST_20251224_NSO"), None)

        # June and September should be vested
        self.assertEqual(june_lot.lifecycle_state, LifecycleState.VESTED_NOT_EXERCISED)
        self.assertEqual(sept_lot.lifecycle_state, LifecycleState.VESTED_NOT_EXERCISED)

        # December should still be unvested
        self.assertEqual(dec_lot.lifecycle_state, LifecycleState.GRANTED_NOT_VESTED)

    def test_no_vesting_calendar_fallback(self):
        """Test that loader doesn't crash when no vesting calendar exists."""
        # Profile with no vesting calendar
        minimal_profile = {
            "equity_position": {
                "grants": [
                    {
                        "grant_id": "GRANT_002",
                        "grant_date": "2023-01-15",
                        "type": "ISO",
                        "total_options": 10000,
                        "strike_price": 5.0,
                        "expiration_date": "2033-01-15",
                        "vesting_status": {
                            "vested_unexercised": {
                                "iso": 10000
                            }
                        }
                    }
                ]
            }
        }

        lots = self.loader.load_lots_from_profile(minimal_profile)

        # Should only have the vested ISO lot
        self.assertEqual(len(lots), 1)
        self.assertEqual(lots[0].lot_id, "ISO")
        self.assertEqual(lots[0].quantity, 10000)


if __name__ == '__main__':
    unittest.main()
