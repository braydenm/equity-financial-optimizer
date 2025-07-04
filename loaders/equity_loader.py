"""
Direct equity lot loader from user profile JSON.

This module loads share lots from the json user profile or demo profile.
"""

from datetime import date, datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from projections.projection_state import (
    ShareLot, ShareType, LifecycleState, TaxTreatment
)
from calculators.tax_constants import LTCG_HOLDING_PERIOD_DAYS


class EquityLoader:
    """Loads share lots directly from user profile data."""

    def __init__(self, reference_date: Optional[date] = None):
        """Initialize equity loader.

        Args:
            reference_date: Date for determining vesting status (defaults to today)
        """
        self.reference_date = reference_date or date.today()

    def load_lots_from_profile(self, profile_data: Dict[str, Any]) -> List[ShareLot]:
        """
        Load all share lots from user profile data.

        This includes:
        - Exercised lots (RSUs, ISOs, NSOs)
        - Currently vested unexercised options
        - Future vesting events from vesting calendar

        Args:
            profile_data: Complete user profile dictionary

        Returns:
            List of ShareLot objects representing all equity positions
        """
        lots = []
        equity_pos = profile_data.get('equity_position', {})

        # 1. Load exercised lots
        lots.extend(self._load_exercised_lots(equity_pos))

        # 2. Load vested unexercised options
        lots.extend(self._load_vested_unexercised(equity_pos))

        # 3. Load future vesting events
        lots.extend(self._load_vesting_calendar(equity_pos))

        return lots

    def _load_exercised_lots(self, equity_position: Dict[str, Any]) -> List[ShareLot]:
        """Load already exercised share lots."""
        lots = []

        for lot_data in equity_position.get('exercised_lots', []):
            share_type = self._parse_share_type(lot_data['type'])
            exercise_date = datetime.fromisoformat(lot_data['exercise_date']).date()

            # Determine tax treatment based on holding period
            holding_period_days = (self.reference_date - exercise_date).days
            tax_treatment = TaxTreatment.LTCG if holding_period_days >= LTCG_HOLDING_PERIOD_DAYS else TaxTreatment.STCG

            lot = ShareLot(
                lot_id=lot_data['lot_id'],
                share_type=share_type,
                quantity=lot_data['shares'],
                strike_price=lot_data['strike_price'],
                cost_basis=lot_data.get('cost_basis', lot_data['strike_price']),
                grant_date=self._get_grant_date_from_grants(equity_position),
                exercise_date=exercise_date,
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=tax_treatment,
                fmv_at_exercise=lot_data.get('fmv_at_exercise'),
                amt_adjustment=lot_data.get('amt_adjustment'),
                grant_id=lot_data.get('grant_id') or self._get_grant_id_from_grants(equity_position)
            )
            lots.append(lot)

        return lots

    def _load_vested_unexercised(self, equity_position: Dict[str, Any]) -> List[ShareLot]:
        """Load currently vested but unexercised options."""
        lots = []
        
        # Process each grant
        for grant in equity_position.get('grants', []):
            vesting_status = grant.get('vesting_status', {})
            vested = vesting_status.get('vested_unexercised', {})
            
            # Skip if no vested unexercised shares
            if not vested:
                continue
                
            # Get grant details
            strike_price = grant.get('strike_price', 0.0)
            grant_date = datetime.fromisoformat(grant['grant_date']).date() if 'grant_date' in grant else None
            expiration_date = datetime.fromisoformat(grant['expiration_date']).date() if 'expiration_date' in grant else None
            grant_id = grant.get('grant_id')
            
            # ISO shares
            if vested.get('iso', 0) > 0:
                lot_id = f"ISO_{grant_id}" if grant_id else 'ISO'
                lots.append(ShareLot(
                    lot_id=lot_id,
                    share_type=ShareType.ISO,
                    quantity=vested['iso'],
                    strike_price=strike_price,
                    grant_date=grant_date,
                    exercise_date=None,
                    lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                    tax_treatment=TaxTreatment.NA,
                    expiration_date=expiration_date,
                    grant_id=grant_id
                ))
            
            # NSO shares
            if vested.get('nso', 0) > 0:
                lot_id = f"NSO_{grant_id}" if grant_id else 'NSO'
                lots.append(ShareLot(
                    lot_id=lot_id,
                    share_type=ShareType.NSO,
                    quantity=vested['nso'],
                    strike_price=strike_price,
                    grant_date=grant_date,
                    exercise_date=None,
                    lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                    tax_treatment=TaxTreatment.NA,
                    expiration_date=expiration_date,
                    grant_id=grant_id
                ))
            
            # RSU shares (if any vested but not released)
            if vested.get('rsu', 0) > 0:
                lot_id = f"VESTED_RSU_{grant_id}" if grant_id else 'VESTED_RSU'
                lots.append(ShareLot(
                    lot_id=lot_id,
                    share_type=ShareType.RSU,
                    quantity=vested['rsu'],
                    strike_price=0.0,  # RSUs have no strike price
                    grant_date=grant_date,
                    exercise_date=None,
                    lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                    tax_treatment=TaxTreatment.NA,
                    expiration_date=None,  # RSUs don't expire
                    grant_id=grant_id
                ))

        return lots

    def _load_vesting_calendar(self, equity_position: Dict[str, Any]) -> List[ShareLot]:
        """Load future vesting events from vesting calendar."""
        lots = []
        
        # First check the old location for backward compatibility
        unvested = equity_position.get('unvested', {})
        vesting_calendar = unvested.get('vesting_calendar', [])
        
        # If not found, check the new location within grants
        if not vesting_calendar:
            for grant in equity_position.get('grants', []):
                vesting_status = grant.get('vesting_status', {})
                unvested = vesting_status.get('unvested', {})
                grant_calendar = unvested.get('vesting_calendar', [])
                
                if grant_calendar:
                    # Get grant-specific details
                    strike_price = grant.get('strike_price', 0.0)
                    expiration_date = datetime.fromisoformat(grant['expiration_date']).date() if 'expiration_date' in grant else None
                    grant_id = grant.get('grant_id')
                    
                    # Process this grant's vesting calendar
                    for event in grant_calendar:
                        vest_date = datetime.fromisoformat(event['date']).date()
                        share_type = self._parse_share_type(event['share_type'])

                        # Generate unique lot ID for each vesting event
                        if grant_id:
                            lot_id = f"VEST_{vest_date.strftime('%Y%m%d')}_{event['share_type']}_{grant_id}"
                        else:
                            lot_id = f"VEST_{vest_date.strftime('%Y%m%d')}_{event['share_type']}"

                        # Determine lifecycle state based on vesting date
                        if vest_date <= self.reference_date:
                            lifecycle_state = LifecycleState.VESTED_NOT_EXERCISED
                        else:
                            lifecycle_state = LifecycleState.GRANTED_NOT_VESTED

                        # Use grant date from the grant
                        grant_date_obj = datetime.fromisoformat(grant['grant_date']).date() if 'grant_date' in grant else date(vest_date.year - 2, vest_date.month, vest_date.day)

                        lot = ShareLot(
                            lot_id=lot_id,
                            share_type=share_type,
                            quantity=event['shares'],
                            strike_price=strike_price,
                            grant_date=grant_date_obj,
                            exercise_date=None,
                            lifecycle_state=lifecycle_state,
                            tax_treatment=TaxTreatment.NA,
                            expiration_date=expiration_date,
                            grant_id=grant_id
                        )
                        lots.append(lot)
            
            # If we processed grants, return the lots
            if lots:
                return lots
        
        # Otherwise, process the old-style vesting calendar
        # Get strike price from original grants
        strike_price = self._get_strike_price_from_grants(equity_position)
        expiration_date = self._get_expiration_date_from_grants(equity_position)
        grant_id = self._get_grant_id_from_grants(equity_position)

        for event in vesting_calendar:
            vest_date = datetime.fromisoformat(event['date']).date()
            share_type = self._parse_share_type(event['share_type'])

            # Generate unique lot ID for each vesting event
            lot_id = f"VEST_{vest_date.strftime('%Y%m%d')}_{event['share_type']}"

            # Determine lifecycle state based on vesting date
            if vest_date <= self.reference_date:
                lifecycle_state = LifecycleState.VESTED_NOT_EXERCISED
            else:
                lifecycle_state = LifecycleState.GRANTED_NOT_VESTED

            # Determine grant date (approximation: 2 years before vesting)
            # This could be enhanced with actual grant data if available
            grant_date = date(vest_date.year - 2, vest_date.month, vest_date.day)

            lot = ShareLot(
                lot_id=lot_id,
                share_type=share_type,
                quantity=event['shares'],
                strike_price=strike_price if share_type != ShareType.RSU else 0.0,
                grant_date=grant_date,
                exercise_date=None,
                lifecycle_state=lifecycle_state,
                tax_treatment=TaxTreatment.NA,
                expiration_date=expiration_date if share_type != ShareType.RSU else None,
                grant_id=grant_id
            )
            lots.append(lot)

        return lots

    def _parse_share_type(self, type_str: str) -> ShareType:
        """Parse share type from string."""
        type_str = type_str.upper()
        if type_str == 'ISO':
            return ShareType.ISO
        elif type_str == 'NSO':
            return ShareType.NSO
        elif type_str == 'RSU':
            return ShareType.RSU
        else:
            raise ValueError(f"Unknown share type: {type_str}")

    def _get_strike_price_from_grants(self, equity_position: dict) -> float:
        """Extract strike price from original grants."""
        grants = equity_position.get('grants', [])
        if grants:
            return grants[0].get('strike_price', 0.0)
        return 0.0

    def _get_expiration_date_from_grants(self, equity_position: dict) -> Optional[date]:
        """Extract expiration date from original grants."""
        grants = equity_position.get('grants', [])
        if grants and 'expiration_date' in grants[0]:
            expiration_str = grants[0]['expiration_date']
            if expiration_str:
                return datetime.fromisoformat(expiration_str).date()
        return None

    def _get_grant_date_from_grants(self, equity_position: dict) -> Optional[date]:
        """Extract grant date from original grants."""
        grants = equity_position.get('grants', [])
        if grants and 'grant_date' in grants[0]:
            grant_str = grants[0]['grant_date']
            if grant_str:
                return datetime.fromisoformat(grant_str).date()
        return None

    def _get_grant_id_from_grants(self, equity_position: dict) -> Optional[str]:
        """Extract grant ID from original grants."""
        grants = equity_position.get('grants', [])
        if grants and 'grant_id' in grants[0]:
            return grants[0]['grant_id']
        return None

    def summarize_lots(self, lots: List[ShareLot]) -> Dict[str, Any]:
        """
        Create summary statistics for loaded lots.

        Args:
            lots: List of share lots to summarize

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            'total_lots': len(lots),
            'total_shares': sum(lot.quantity for lot in lots),
            'by_lifecycle_state': {},
            'by_share_type': {},
            'vesting_schedule': []
        }

        # Count by lifecycle state
        for lot in lots:
            state_name = lot.lifecycle_state.name
            if state_name not in summary['by_lifecycle_state']:
                summary['by_lifecycle_state'][state_name] = {'count': 0, 'shares': 0}
            summary['by_lifecycle_state'][state_name]['count'] += 1
            summary['by_lifecycle_state'][state_name]['shares'] += lot.quantity

        # Count by share type
        for lot in lots:
            type_name = lot.share_type.name
            if type_name not in summary['by_share_type']:
                summary['by_share_type'][type_name] = {'count': 0, 'shares': 0}
            summary['by_share_type'][type_name]['count'] += 1
            summary['by_share_type'][type_name]['shares'] += lot.quantity

        # Extract vesting schedule
        for lot in lots:
            if lot.lifecycle_state == LifecycleState.GRANTED_NOT_VESTED:
                # Extract date from lot ID if it's a vesting lot
                if 'VEST_' in lot.lot_id:
                    try:
                        date_part = lot.lot_id.split('_')[1]
                        vest_date = datetime.strptime(date_part, '%Y%m%d').date()
                        summary['vesting_schedule'].append({
                            'date': vest_date.isoformat(),
                            'shares': lot.quantity,
                            'type': lot.share_type.name
                        })
                    except (IndexError, ValueError):
                        pass

        # Sort vesting schedule by date
        summary['vesting_schedule'].sort(key=lambda x: x['date'])

        return summary


def load_equity_lots(profile_data: Dict[str, Any],
                    reference_date: Optional[date] = None) -> List[ShareLot]:
    """
    Convenience function to load equity lots from profile.

    Args:
        profile_data: User profile dictionary
        reference_date: Reference date for vesting determination

    Returns:
        List of ShareLot objects
    """
    loader = EquityLoader(reference_date)
    return loader.load_lots_from_profile(profile_data)
