"""
Liquidity event tracking for donation matching program.

This module provides data structures for tracking liquidity events (tender offers,
IPO, etc.) and their associated donation windows and limits per the Anthropic
donation matching program requirements.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


@dataclass
class LiquidityEvent:
    """
    Track each liquidity event separately per the donation matching FAQ.
    
    Each liquidity event creates a 3-year window for donations and has
    specific tracking for proceeds and donation limits.
    """
    event_id: str
    event_date: date
    event_type: str  # "tender_offer", "ipo", "secondary_offering"
    price_per_share: float
    
    # What happened in this event
    shares_vested_at_event: int  # Total vested eligible shares at event time
    shares_sold: int = 0  # Actual shares sold in this event
    exercise_costs: float = 0.0  # Costs for any cashless exercises
    taxes_withheld: float = 0.0  # Taxes withheld on the transaction
    net_proceeds: float = 0.0  # Net cash received (for cash donation tracking)
    
    # Donation tracking for this event
    cash_donated_from_event: float = 0.0  # Cash donations using these proceeds
    shares_donated_in_window: int = 0  # Share donations during this window
    
    # Window tracking
    match_window_closes: date = field(init=False)
    
    def __post_init__(self):
        """Calculate the 3-year match window from event date."""
        # Per FAQ: "participants will have 3 years following an eligible liquidity event to make a donation"
        self.match_window_closes = self.event_date + timedelta(days=3*365)
    
    @property
    def remaining_donatable_proceeds(self) -> float:
        """Cash still available to donate from this event."""
        return max(0, self.net_proceeds - self.cash_donated_from_event)
    
    def is_window_open(self, as_of_date: date) -> bool:
        """Check if the match window is still open as of given date."""
        return as_of_date <= self.match_window_closes
    
    @property
    def gross_proceeds(self) -> float:
        """Calculate gross proceeds before costs and taxes."""
        return self.shares_sold * self.price_per_share
    
    def calculate_cash_donation_limit(self, pledge_percentage: float, vested_shares_at_donation: int) -> float:
        """
        Calculate the limit for cash donations from this event.
        
        Per FAQ: "The Company's obligation to match donations of cash and other assets 
        following a Liquidity Event will apply to the lesser of:
        (1) the net proceeds you have received in a Liquidity Event, minus any previous 
            donations of cash or other assets made with respect to such Liquidity Event
        (2) the value equal to the number of vested shares subject to your eligible equity 
            awards at the time of your donation multiplied by your pledged percentage, 
            minus any previously donated shares or share equivalents, multiplied by the 
            price shares were sold at in such Liquidity Event"
        """
        # Limit 1: Remaining proceeds from this event
        limit_1 = self.remaining_donatable_proceeds
        
        # Limit 2: Pledge-based limit using this event's price
        # This would need to account for all prior donations, handled at a higher level
        # For now, return the proceeds limit
        return limit_1
    
    def record_cash_donation(self, amount: float) -> None:
        """Record a cash donation against this event's proceeds."""
        if amount > self.remaining_donatable_proceeds:
            raise ValueError(
                f"Cannot donate ${amount:,.2f} from event {self.event_id}. "
                f"Only ${self.remaining_donatable_proceeds:,.2f} remains."
            )
        self.cash_donated_from_event += amount
    
    def record_share_donation(self, shares: int) -> None:
        """Record share donations made during this event's window."""
        self.shares_donated_in_window += shares