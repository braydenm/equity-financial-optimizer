"""
Share sale calculator that extracts tax components from share sales.

This calculator extracts tax components from share sales (e.g., in tender offers
or open market sales) without any strategy logic or optimization. It returns
components that are aggregated annually for proper tax calculation.

Refactored to support annual tax composition:
- calculate_sale_components() returns components for annual aggregation
- All tax calculation happens in the annual tax calculator
"""

from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from datetime import datetime, date
from calculators.components import ShareSaleComponents, DispositionType


class ShareSaleCalculator:
    """Pure share sale tax calculations.

    This calculator knows nothing about strategies or optimization.
    It simply calculates capital gains tax impact for given lot selections.
    """



    @staticmethod
    def calculate_sale_components(
        lot_id: str,
        sale_date: date,
        shares_to_sell: int,
        sale_price: float,
        cost_basis: float,
        exercise_date: date,
        is_iso: bool = False,
        grant_date: Optional[date] = None,
        fmv_at_exercise: Optional[float] = None
    ) -> ShareSaleComponents:
        """
        Calculate components from share sale for annual tax aggregation.

        This function extracts the tax components from a share sale action
        without calculating the actual tax. The components are used by the
        annual tax calculator to determine actual tax liability.

        Args:
            lot_id: Identifier for the lot being sold
            sale_date: Date of sale
            shares_to_sell: Number of shares to sell
            sale_price: Price per share at sale
            cost_basis: Cost basis per share
            exercise_date: Date shares were acquired
            is_iso: Whether these are ISO shares
            grant_date: Original grant date (for ISOs)
            fmv_at_exercise: Fair market value at exercise (for ISOs)

        Returns:
            ShareSaleComponents containing all relevant data for tax calculation
        """
        # Calculate proceeds and gain
        gross_proceeds = shares_to_sell * sale_price
        total_gain = shares_to_sell * (sale_price - cost_basis)

        # Calculate holding period
        holding_period_days = (sale_date - exercise_date).days
        is_long_term = holding_period_days > 365

        # Initialize component values
        short_term_gain = 0.0
        long_term_gain = 0.0
        ordinary_income = 0.0
        disposition_type = DispositionType.REGULAR_SALE
        is_qualifying_disposition = None
        amt_adjustment_reversal = 0.0

        # Determine disposition type and gains
        if is_iso and grant_date and exercise_date:
            # Check for qualifying disposition (1 year from exercise AND 2 years from grant)
            years_from_grant = (sale_date - grant_date).days / 365.25
            years_from_exercise = (sale_date - exercise_date).days / 365.25

            if years_from_grant >= 2 and years_from_exercise >= 1:
                # Qualifying disposition - all gain is LTCG
                disposition_type = DispositionType.QUALIFYING_ISO
                is_qualifying_disposition = True
                long_term_gain = total_gain
            else:
                # Disqualifying disposition - complex tax treatment
                disposition_type = DispositionType.DISQUALIFYING_ISO
                is_qualifying_disposition = False

                if fmv_at_exercise is None:
                    raise ValueError(
                        f"FMV at exercise is required for disqualifying ISO disposition. "
                        f"Lot {lot_id} is being sold as a disqualifying disposition but "
                        f"fmv_at_exercise was not provided. This value is critical for "
                        f"calculating the correct ordinary income vs capital gain split."
                    )

                # Calculate original bargain element
                original_bargain_element = shares_to_sell * (fmv_at_exercise - cost_basis)

                # Handle different price scenarios for disqualifying disposition
                if total_gain <= 0:
                    # Selling at a loss (sale price <= strike price)
                    ordinary_income = 0
                    # The entire loss is a capital loss
                    if is_long_term:
                        long_term_gain = total_gain  # This will be negative
                    else:
                        short_term_gain = total_gain  # This will be negative
                    amt_adjustment_reversal = 0
                else:
                    # Selling at a gain (sale price > strike price)
                    # Ordinary income is lesser of:
                    # 1. Total gain on sale, or
                    # 2. Original bargain element at exercise
                    ordinary_income = min(total_gain, original_bargain_element)

                    # Any remaining gain is capital gain
                    remaining_gain = total_gain - ordinary_income
                    if remaining_gain > 0:
                        if is_long_term:
                            long_term_gain = remaining_gain
                        else:
                            short_term_gain = remaining_gain

                    # AMT adjustment reversal for the portion that becomes ordinary income
                    amt_adjustment_reversal = ordinary_income
        else:
            # Regular sale - use standard LTCG/STCG rules
            if is_long_term:
                long_term_gain = total_gain
            else:
                short_term_gain = total_gain

        return ShareSaleComponents(
            lot_id=lot_id,
            sale_date=sale_date,
            shares_sold=shares_to_sell,
            sale_price=sale_price,
            cost_basis=cost_basis,
            gross_proceeds=gross_proceeds,
            exercise_date=exercise_date,
            holding_period_days=holding_period_days,
            short_term_gain=short_term_gain,
            long_term_gain=long_term_gain,
            ordinary_income=ordinary_income,
            disposition_type=disposition_type,
            is_qualifying_disposition=is_qualifying_disposition,
            amt_adjustment_reversal=amt_adjustment_reversal
        )

    @staticmethod
    def validate_lot_selection(
        lots: List[Dict],
        lot_selections: Dict[str, int]
    ) -> Tuple[bool, List[str]]:
        """Validate that lot selections are feasible.

        Args:
            lots: List of available lots
            lot_selections: Map of lot_id to shares to sell

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check each selection
        for lot_id, shares_to_sell in lot_selections.items():
            # Check lot exists
            lot = next((l for l in lots if l.get('lot_id') == lot_id), None)
            if not lot:
                errors.append(f"Lot {lot_id} not found")
                continue

            # Check shares available
            shares_available = lot['shares']
            if shares_to_sell > shares_available:
                errors.append(
                    f"Lot {lot_id}: requested {shares_to_sell} shares "
                    f"but only {shares_available} available"
                )

            # Check non-negative shares (0 shares is valid edge case)
            if shares_to_sell < 0:
                errors.append(f"Lot {lot_id}: shares to sell must be non-negative")

        return (len(errors) == 0, errors)
