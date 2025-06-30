#!/usr/bin/env python3
"""
Test ISO qualifying disposition date calculations.
"""

import unittest
from datetime import date
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.tax_utils import (
    calculate_iso_qualifying_disposition_date,
    is_iso_qualifying_disposition,
    calculate_holding_period_days,
    is_long_term_capital_gain
)
from projections.projection_state import ShareLot, ShareType, LifecycleState, TaxTreatment


class TestISOQualifyingDate(unittest.TestCase):
    """Test ISO qualifying disposition date calculations."""

    def test_basic_iso_qualifying_date(self):
        """Test basic ISO qualifying date calculation."""
        # Grant date: Jan 1, 2023
        # Exercise date: Jun 1, 2024 (1.5 years after grant)
        # 2 years from grant: Jan 1, 2025
        # 1 year from exercise: Jun 1, 2025
        # Qualifying date should be Jun 1, 2025 (the later date)

        grant_date = date(2023, 1, 1)
        exercise_date = date(2024, 6, 1)

        qualifying_date = calculate_iso_qualifying_disposition_date(grant_date, exercise_date)
        expected = date(2025, 6, 1)

        self.assertEqual(qualifying_date, expected)

    def test_grant_date_controls(self):
        """Test case where 2 years from grant is later than 1 year from exercise."""
        # Grant date: Jan 1, 2023
        # Exercise date: Dec 1, 2024 (almost 2 years after grant)
        # 2 years from grant: Jan 1, 2025
        # 1 year from exercise: Dec 1, 2025
        # Qualifying date should be Dec 1, 2025

        grant_date = date(2023, 1, 1)
        exercise_date = date(2024, 12, 1)

        qualifying_date = calculate_iso_qualifying_disposition_date(grant_date, exercise_date)
        expected = date(2025, 12, 1)

        self.assertEqual(qualifying_date, expected)

    def test_leap_year_grant(self):
        """Test handling of leap year grant date."""
        # Grant date: Feb 29, 2020 (leap year)
        # Exercise date: Mar 1, 2021
        # 2 years from grant: Feb 28, 2022 (non-leap year)
        # 1 year from exercise: Mar 1, 2022
        # Qualifying date should be Mar 1, 2022

        grant_date = date(2020, 2, 29)
        exercise_date = date(2021, 3, 1)

        qualifying_date = calculate_iso_qualifying_disposition_date(grant_date, exercise_date)
        expected = date(2022, 3, 1)

        self.assertEqual(qualifying_date, expected)

    def test_leap_year_exercise(self):
        """Test handling of leap year exercise date."""
        # Grant date: Jan 1, 2019
        # Exercise date: Feb 29, 2020 (leap year)
        # 2 years from grant: Jan 1, 2021
        # 1 year from exercise: Feb 28, 2021 (non-leap year)
        # Qualifying date should be Feb 28, 2021

        grant_date = date(2019, 1, 1)
        exercise_date = date(2020, 2, 29)

        qualifying_date = calculate_iso_qualifying_disposition_date(grant_date, exercise_date)
        expected = date(2021, 2, 28)

        self.assertEqual(qualifying_date, expected)

    def test_is_qualifying_disposition(self):
        """Test the is_iso_qualifying_disposition helper."""
        grant_date = date(2023, 1, 1)
        exercise_date = date(2024, 1, 1)
        # Qualifying date would be Jan 1, 2025 (2 years from grant)

        # Before qualifying date - not qualifying
        self.assertFalse(is_iso_qualifying_disposition(
            grant_date, exercise_date, date(2024, 12, 31)
        ))

        # On qualifying date - qualifying
        self.assertTrue(is_iso_qualifying_disposition(
            grant_date, exercise_date, date(2025, 1, 1)
        ))

        # After qualifying date - qualifying
        self.assertTrue(is_iso_qualifying_disposition(
            grant_date, exercise_date, date(2025, 6, 1)
        ))

    def test_holding_period_calculation(self):
        """Test holding period calculation."""
        acquisition = date(2023, 1, 1)

        # Same day - 0 days
        self.assertEqual(calculate_holding_period_days(acquisition, acquisition), 0)

        # Next day - 1 day
        self.assertEqual(calculate_holding_period_days(acquisition, date(2023, 1, 2)), 1)

        # One year later - 365 days
        self.assertEqual(calculate_holding_period_days(acquisition, date(2024, 1, 1)), 365)

        # Leap year - 366 days
        leap_start = date(2024, 1, 1)
        self.assertEqual(calculate_holding_period_days(leap_start, date(2025, 1, 1)), 366)

    def test_long_term_capital_gain(self):
        """Test long-term capital gain determination."""
        acquisition = date(2023, 1, 1)

        # 365 days - not long term (need > 365)
        self.assertFalse(is_long_term_capital_gain(acquisition, date(2024, 1, 1)))

        # 366 days - long term
        self.assertTrue(is_long_term_capital_gain(acquisition, date(2024, 1, 2)))

    def test_share_lot_iso_qualifying_date_property(self):
        """Test the iso_qualifying_date property on ShareLot."""
        # ISO lot
        iso_lot = ShareLot(
            lot_id="ISO_001",
            share_type=ShareType.ISO,
            quantity=1000,
            strike_price=10.0,
            grant_date=date(2023, 1, 1),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.NA,
            exercise_date=date(2024, 6, 1),
            fmv_at_exercise=50.0
        )

        # Should return qualifying date
        expected = date(2025, 6, 1)  # 1 year from exercise
        self.assertEqual(iso_lot.iso_qualifying_date, expected)

        # NSO lot - should return None
        nso_lot = ShareLot(
            lot_id="NSO_001",
            share_type=ShareType.NSO,
            quantity=1000,
            strike_price=10.0,
            grant_date=date(2023, 1, 1),
            lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
            tax_treatment=TaxTreatment.NA,
            exercise_date=date(2024, 6, 1),
            fmv_at_exercise=50.0
        )

        self.assertIsNone(nso_lot.iso_qualifying_date)

        # Unexercised ISO - should return None
        unexercised_iso = ShareLot(
            lot_id="ISO_002",
            share_type=ShareType.ISO,
            quantity=1000,
            strike_price=10.0,
            grant_date=date(2023, 1, 1),
            lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
            tax_treatment=TaxTreatment.NA,
            expiration_date=date(2033, 1, 1)
        )

        self.assertIsNone(unexercised_iso.iso_qualifying_date)

    def test_edge_cases(self):
        """Test various edge cases."""
        # Same grant and exercise date
        same_date = date(2023, 1, 1)
        qualifying = calculate_iso_qualifying_disposition_date(same_date, same_date)
        # Should be 2 years from grant
        self.assertEqual(qualifying, date(2025, 1, 1))

        # Exercise before grant (shouldn't happen but handle gracefully)
        grant = date(2023, 6, 1)
        exercise = date(2023, 1, 1)
        qualifying = calculate_iso_qualifying_disposition_date(grant, exercise)
        # Should still be 2 years from grant
        self.assertEqual(qualifying, date(2025, 6, 1))


def run_test():
    """Run the ISO qualifying date tests."""
    print("\n" + "="*70)
    print("ISO QUALIFYING DATE TEST SUITE")
    print("="*70)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestISOQualifyingDate)

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    if result.wasSuccessful():
        print("\n✅ All ISO qualifying date tests passed!")
    else:
        print(f"\n❌ {len(result.failures)} tests failed")
        for test, trace in result.failures:
            print(f"\nFAILED: {test}")
            print(trace)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_test()
    sys.exit(0 if success else 1)
