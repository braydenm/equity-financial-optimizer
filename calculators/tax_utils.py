"""
Tax utility functions for equity compensation calculations.

This module provides utility functions for tax-related calculations that are
used across multiple calculators.
"""

from datetime import date
from typing import Optional


def calculate_iso_qualifying_disposition_date(grant_date: date, exercise_date: date) -> date:
    """
    Calculate when ISO shares become eligible for qualifying disposition.

    For a disposition of ISO shares to be "qualifying" (and thus eligible for
    long-term capital gains treatment on the entire gain), two conditions must
    be met:
    1. The shares must be held for at least 2 years from the grant date
    2. The shares must be held for at least 1 year from the exercise date

    Both conditions must be satisfied, so the qualifying date is the later of
    the two dates.

    Args:
        grant_date: Date the ISO was granted
        exercise_date: Date the ISO was exercised

    Returns:
        Date when the shares become eligible for qualifying disposition

    Example:
        >>> grant = date(2023, 1, 1)
        >>> exercise = date(2024, 6, 1)
        >>> qualifying_date = calculate_iso_qualifying_disposition_date(grant, exercise)
        >>> # qualifying_date will be June 1, 2025 (1 year from exercise)
        >>> # because that's later than January 1, 2025 (2 years from grant)
    """
    # Calculate 2 years from grant date
    try:
        two_years_from_grant = date(
            grant_date.year + 2,
            grant_date.month,
            grant_date.day
        )
    except ValueError:
        # Handle leap year case where grant was on Feb 29
        # and 2 years later is not a leap year
        two_years_from_grant = date(
            grant_date.year + 2,
            grant_date.month,
            28
        )

    # Calculate 1 year from exercise date
    try:
        one_year_from_exercise = date(
            exercise_date.year + 1,
            exercise_date.month,
            exercise_date.day
        )
    except ValueError:
        # Handle leap year case where exercise was on Feb 29
        # and 1 year later is not a leap year
        one_year_from_exercise = date(
            exercise_date.year + 1,
            exercise_date.month,
            28
        )

    # Qualifying date is the later of the two requirements
    return max(two_years_from_grant, one_year_from_exercise)


def is_iso_qualifying_disposition(
    grant_date: date,
    exercise_date: date,
    sale_date: date
) -> bool:
    """
    Determine if an ISO sale is a qualifying disposition.

    Args:
        grant_date: Date the ISO was granted
        exercise_date: Date the ISO was exercised
        sale_date: Date the shares are being sold

    Returns:
        True if the sale is a qualifying disposition, False otherwise
    """
    qualifying_date = calculate_iso_qualifying_disposition_date(grant_date, exercise_date)
    return sale_date >= qualifying_date


def calculate_holding_period_days(
    acquisition_date: date,
    disposition_date: date
) -> int:
    """
    Calculate the number of days between acquisition and disposition.

    Args:
        acquisition_date: Date shares were acquired (exercise date for options)
        disposition_date: Date shares are being disposed (sale/donation date)

    Returns:
        Number of days held
    """
    return (disposition_date - acquisition_date).days


def is_long_term_capital_gain(
    acquisition_date: date,
    disposition_date: date
) -> bool:
    """
    Determine if a disposition qualifies for long-term capital gains treatment.

    Long-term capital gains treatment requires holding the asset for more than
    365 days (not 366 days as sometimes mistakenly believed).

    Args:
        acquisition_date: Date shares were acquired
        disposition_date: Date shares are being disposed

    Returns:
        True if held for more than 365 days, False otherwise
    """
    holding_days = calculate_holding_period_days(acquisition_date, disposition_date)
    return holding_days > 365
