"""
Centralized pledge calculation utility.

This module provides a single source of truth for calculating pledge obligations
from share sales. It implements the maximalist interpretation where pledge
percentages are calculated based on share counts, not dollar amounts.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from projections.projection_state import PledgeObligation


class PledgeCalculator:
    """Centralized calculator for pledge obligations from share sales."""

    @staticmethod
    def calculate_obligation(
        shares_sold: int,
        sale_price: float,
        pledge_percentage: float,
        sale_date: date,
        lot_id: str,
        pledge_window_years: int = 3
    ) -> PledgeObligation:
        """
        Calculate pledge obligation from a share sale.

        Uses the maximalist interpretation where the pledge percentage
        represents the ratio of donated shares to total disposition:
        shares_donated / (shares_sold + shares_donated) = pledge_percentage

        Solving for shares_donated:
        shares_donated = (pledge_percentage * shares_sold) / (1 - pledge_percentage)

        Args:
            shares_sold: Number of shares sold
            sale_price: Price per share at sale
            pledge_percentage: Pledge percentage (e.g., 0.5 for 50%)
            sale_date: Date of the sale transaction
            lot_id: Identifier of the lot being sold
            pledge_window_years: Years allowed to fulfill pledge (default: 3)

        Returns:
            PledgeObligation with calculated requirements

        Raises:
            ValueError: If pledge_percentage >= 1.0 or other invalid inputs
        """
        # Validate inputs
        if pledge_percentage > 1.0:
            raise ValueError(f"Pledge percentage must be less than or equal to 100%, got {pledge_percentage * 100}%")
        if pledge_percentage < 0:
            raise ValueError(f"Pledge percentage cannot be negative, got {pledge_percentage}")
        if shares_sold <= 0:
            raise ValueError(f"Shares sold must be positive, got {shares_sold}")
        if sale_price < 0:
            raise ValueError(f"Sale price cannot be negative, got {sale_price}")

        # Calculate required shares under maximalist interpretation
        if pledge_percentage == 0:
            shares_required = 0
            obligation_amount = 0.0
        else:
            shares_required = int((pledge_percentage * shares_sold) / (1 - pledge_percentage))
            obligation_amount = shares_required * sale_price

        # Create transaction ID
        transaction_id = f"{lot_id}_{sale_date.isoformat()}"

        # Calculate deadline
        deadline = sale_date + timedelta(days=pledge_window_years * 365)

        # Create and return obligation
        return PledgeObligation(
            parent_transaction_id=transaction_id,
            commencement_date=sale_date,
            match_window_closes=deadline,
            total_pledge_obligation=obligation_amount,
            donations_made=0.0,
            shares_sold=shares_sold,
            pledge_percentage=pledge_percentage,
            maximalist_shares_donated=0,
            outstanding_obligation=obligation_amount
        )

    @staticmethod
    def calculate_fulfillment_progress(
        obligation: PledgeObligation,
        shares_donated: int,
        donation_value: float
    ) -> PledgeObligation:
        """
        Update obligation with fulfillment progress.

        Args:
            obligation: Existing pledge obligation
            shares_donated: Additional shares donated
            donation_value: Dollar value of donation

        Returns:
            Updated PledgeObligation
        """
        # Update share count
        obligation.maximalist_shares_donated += shares_donated

        # Update dollar tracking
        obligation.donations_made += donation_value
        obligation.outstanding_obligation = max(
            0, obligation.total_pledge_obligation - obligation.donations_made
        )

        return obligation

    @staticmethod
    def shares_needed_for_fulfillment(obligation: PledgeObligation) -> int:
        """
        Calculate remaining shares needed to fulfill obligation.

        Args:
            obligation: Pledge obligation to check

        Returns:
            Number of shares still needed (0 if fulfilled)
        """
        required = obligation.maximalist_shares_required
        donated = obligation.maximalist_shares_donated
        return max(0, required - donated)

    @staticmethod
    def is_obligation_fulfilled(obligation: PledgeObligation) -> bool:
        """
        Check if obligation is fully satisfied under maximalist interpretation.

        Args:
            obligation: Pledge obligation to check

        Returns:
            True if obligation is fulfilled
        """
        return obligation.maximalist_shares_donated >= obligation.maximalist_shares_required

    @staticmethod
    def days_until_deadline(obligation: PledgeObligation, as_of_date: date) -> int:
        """
        Calculate days remaining until match window closes.

        Args:
            obligation: Pledge obligation
            as_of_date: Date to calculate from

        Returns:
            Days until match window closes (negative if past deadline)
        """
        return (obligation.match_window_closes - as_of_date).days

    @staticmethod
    def validate_donation_strategy(
        shares_to_sell: int,
        shares_to_donate: int,
        pledge_percentage: float
    ) -> bool:
        """
        Validate if a sell+donate strategy meets pledge requirements.

        Args:
            shares_to_sell: Planned shares to sell
            shares_to_donate: Planned shares to donate
            pledge_percentage: Pledge percentage commitment

        Returns:
            True if strategy meets pledge requirements
        """
        if shares_to_sell == 0 and shares_to_donate == 0:
            return True  # No action is valid

        if pledge_percentage == 0:
            return True  # No pledge requirement

        if pledge_percentage > 1:
            return False  # Invalid pledge percentage

        # Calculate required donation ratio
        actual_ratio = shares_to_donate / (shares_to_sell + shares_to_donate)
        required_ratio = pledge_percentage

        # Allow small tolerance for rounding
        return abs(actual_ratio - required_ratio) < 0.001


# Example usage and doctest
if __name__ == "__main__":
    # Example: 50% pledge on 1000 share sale at $60
    obligation = PledgeCalculator.calculate_obligation(
        shares_sold=1000,
        sale_price=60.0,
        pledge_percentage=0.5,
        sale_date=date(2025, 1, 15),
        lot_id="RSU_2021"
    )

    print(f"Shares sold: {obligation.shares_sold}")
    print(f"Shares required to donate: {obligation.maximalist_shares_required}")
    print(f"Dollar obligation: ${obligation.total_pledge_obligation:,.2f}")
    print(f"Match window closes: {obligation.match_window_closes}")

    # Validate strategies
    print("\nStrategy validation:")
    print(f"Sell 1000, donate 1000 (50%): {PledgeCalculator.validate_donation_strategy(1000, 1000, 0.5)}")
    print(f"Sell 1000, donate 500 (33%): {PledgeCalculator.validate_donation_strategy(1000, 500, 0.5)}")
