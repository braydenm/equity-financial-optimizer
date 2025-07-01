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
from typing import List, Optional


class PledgeCalculator:
    """Centralized calculator for pledge obligations from share sales."""

    @staticmethod
    def calculate_sale_obligation(
        shares_sold: int,
        pledge_percentage: float,
        sale_date: date,
        event_id: str,
        grant_id: Optional[str] = None,
        match_ratio: float = 3.0
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
            pledge_percentage: Pledge percentage (e.g., 0.5 for 50%)
            sale_date: Date of the sale transaction
            event_id: ID of the liquidity event containing this sale
            grant_id: ID of the grant these shares came from
            match_ratio: Company match ratio for this grant

        Returns:
            PledgeObligation with calculated requirements

        Raises:
            ValueError: If pledge_percentage >= 1.0 or other invalid inputs
        """
        # Validate inputs
        if pledge_percentage >= 1.0:
            raise ValueError(f"Pledge percentage must be less than 100%, got {pledge_percentage * 100}%")
        if pledge_percentage < 0:
            raise ValueError(f"Pledge percentage cannot be negative, got {pledge_percentage}")
        if shares_sold <= 0:
            raise ValueError(f"Shares sold must be positive, got {shares_sold}")

        # Calculate required shares under maximalist interpretation
        if pledge_percentage == 0:
            shares_required = 0
        else:
            shares_required = int((pledge_percentage * shares_sold) / (1 - pledge_percentage))

        # Create and return obligation
        return PledgeObligation(
            source_event_id=event_id,
            obligation_type="sale",
            creation_date=sale_date,
            shares_obligated=shares_required,
            shares_fulfilled=0,
            pledge_percentage=pledge_percentage,
            grant_id=grant_id,
            match_ratio=match_ratio
        )

    @staticmethod
    def calculate_ipo_remainder_obligation(
        total_vested_shares: int,
        pledge_percentage: float,
        existing_obligations: List[PledgeObligation],
        ipo_date: date,
        ipo_event_id: str,
        grant_id: Optional[str] = None,
        match_ratio: float = 3.0
    ) -> Optional[PledgeObligation]:
        """
        Calculate remaining pledge obligation at IPO.
        
        At IPO, user must fulfill pledge on ALL vested eligible shares,
        not just those sold. This creates an obligation for any unfulfilled
        portion of the total pledge commitment.
        
        Args:
            total_vested_shares: Total vested eligible shares at IPO
            pledge_percentage: Pledge percentage for these shares
            existing_obligations: All existing pledge obligations
            ipo_date: Date of the IPO
            ipo_event_id: ID of the IPO liquidity event
            grant_id: ID of the grant (for grant-specific tracking)
            match_ratio: Company match ratio
        
        Returns:
            PledgeObligation for remainder, or None if already fulfilled
        """
        # Calculate total shares that should be pledged
        total_pledge_shares = int(total_vested_shares * pledge_percentage)
        
        # Calculate shares already obligated from sales
        already_obligated = sum(
            o.shares_obligated 
            for o in existing_obligations 
            if o.grant_id == grant_id  # Only count obligations from same grant
        )
        
        
        # Calculate remaining obligation
        remainder = total_pledge_shares - already_obligated
        
        if remainder > 0:
            return PledgeObligation(
                source_event_id=ipo_event_id,
                obligation_type="ipo_remainder",
                creation_date=ipo_date,
                shares_obligated=remainder,
                shares_fulfilled=0,
                pledge_percentage=pledge_percentage,
                grant_id=grant_id,
                match_ratio=match_ratio
            )
        
        return None

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

        if pledge_percentage >= 1:
            return False  # Invalid pledge percentage

        # Calculate required donation ratio
        actual_ratio = shares_to_donate / (shares_to_sell + shares_to_donate)
        required_ratio = pledge_percentage

        # Allow small tolerance for rounding
        return abs(actual_ratio - required_ratio) < 0.001

