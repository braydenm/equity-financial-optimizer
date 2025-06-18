"""
Vesting event data structures for clean data contracts.

This module provides well-defined data types for lifecycle events,
eliminating the need for dictionary/object dual handling.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional, List

from projections.projection_state import ShareLot, ShareType


@dataclass
class VestingEvent:
    """Represents a vesting event for a share lot."""

    lot_id: str
    vest_date: date
    quantity: int
    share_type: ShareType
    notes: str = ""

    @classmethod
    def from_lot_transition(cls, lot: ShareLot, vest_date: date) -> 'VestingEvent':
        """Create VestingEvent from a lot transitioning to vested state."""
        return cls(
            lot_id=lot.lot_id,
            vest_date=vest_date,
            quantity=lot.quantity,
            share_type=lot.share_type,
            notes=f"Natural vesting transition on {vest_date}"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for CSV export."""
        return {
            'lot_id': self.lot_id,
            'vest_date': self.vest_date.isoformat(),
            'quantity': self.quantity,
            'share_type': self.share_type.name,
            'notes': self.notes
        }


@dataclass
class ExpirationEvent:
    """Represents an expiration event for options."""

    lot_id: str
    expiration_date: date
    quantity: int
    share_type: ShareType
    strike_price: float = 0.0
    market_price: float = 0.0
    notes: str = ""

    @property
    def opportunity_cost(self) -> float:
        """Calculate the opportunity cost of expiration."""
        if self.market_price > self.strike_price:
            return (self.market_price - self.strike_price) * self.quantity
        return 0.0

    @property
    def per_share_loss(self) -> float:
        """Calculate the per-share opportunity cost."""
        if self.market_price > self.strike_price:
            return self.market_price - self.strike_price
        return 0.0

    @classmethod
    def from_lot(cls, lot: ShareLot, expiration_date: date, market_price: float = 0.0) -> 'ExpirationEvent':
        """Create ExpirationEvent from an expiring lot."""
        return cls(
            lot_id=lot.lot_id,
            expiration_date=expiration_date,
            quantity=lot.quantity,
            share_type=lot.share_type,
            strike_price=lot.strike_price,
            market_price=market_price,
            notes=f"Options expired on {expiration_date}"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for CSV export."""
        return {
            'lot_id': self.lot_id,
            'expiration_date': self.expiration_date.isoformat(),
            'quantity': self.quantity,
            'share_type': self.share_type.name,
            'strike_price': self.strike_price,
            'market_price': self.market_price,
            'opportunity_cost': self.opportunity_cost,
            'notes': self.notes
        }


def process_natural_vesting(lots: List[ShareLot], year: int) -> List[VestingEvent]:
    """
    Process natural vesting transitions for lots in a given year.

    This replaces the dictionary-based approach with proper data types.

    Args:
        lots: List of share lots to check for vesting
        year: Current projection year

    Returns:
        List of VestingEvent objects
    """
    from projections.projection_state import LifecycleState

    vesting_events = []

    for lot in lots:
        # Check if this lot should vest in this year
        if (lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED and
            'VEST_' in lot.lot_id):

            try:
                # Extract vest date from lot ID (format: VEST_YYYYMMDD_TYPE)
                date_part = lot.lot_id.split('_')[1]
                vest_year = int(date_part[:4])
                vest_month = int(date_part[4:6])
                vest_day = int(date_part[6:8])

                if vest_year == year:
                    # This lot vests this year
                    vest_date = date(vest_year, vest_month, vest_day)
                    lot.lifecycle_state = LifecycleState.VESTED_NOT_EXERCISED

                    # Create proper vesting event
                    event = VestingEvent.from_lot_transition(lot, vest_date)
                    vesting_events.append(event)

            except (IndexError, ValueError):
                # If we can't parse the date, skip this lot
                continue

    return vesting_events


def process_natural_expiration(lots: List[ShareLot], year: int, market_price: float = 0.0) -> List['ExpirationEvent']:
    """
    Process natural expiration transitions for lots in a given year.

    This handles options that expire naturally based on their expiration date.

    Args:
        lots: List of share lots to check for expiration
        year: Current projection year
        market_price: Current market price for opportunity cost calculation

    Returns:
        List of ExpirationEvent objects
    """
    from projections.projection_state import LifecycleState

    expiration_events = []

    for lot in lots:
        # Check if this lot has an expiration date and should expire this year
        if (lot.expiration_date and
            lot.expiration_date.year == year and
            lot.lifecycle_state in [LifecycleState.GRANTED_NOT_VESTED, LifecycleState.VESTED_NOT_EXERCISED]):

            # Mark the lot as expired
            was_exercisable = lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED
            lot.lifecycle_state = LifecycleState.EXPIRED

            # Create expiration event with market price for opportunity cost calculation
            event = ExpirationEvent.from_lot(lot, lot.expiration_date, market_price)

            if was_exercisable and event.opportunity_cost > 0:
                event.notes = f"Vested options expired on {lot.expiration_date} - OPPORTUNITY COST: ${event.opportunity_cost:,.2f} (${event.per_share_loss:.2f}/share)"
            elif was_exercisable:
                event.notes = f"Vested options expired on {lot.expiration_date} (underwater - no opportunity cost)"
            else:
                event.notes = f"Unvested options expired on {lot.expiration_date}"

            expiration_events.append(event)

    return expiration_events
