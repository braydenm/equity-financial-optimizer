"""
Share sale calculator with capital gains tax calculations.

This calculator performs tax calculations for selling shares (e.g., in tender offers
or open market sales) without any strategy logic or optimization. It simply
calculates the tax impact of selling specific lots at a given price.
"""

from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from datetime import datetime


class ShareSaleCalculator:
    """Pure share sale tax calculations.
    
    This calculator knows nothing about strategies or optimization.
    It simply calculates capital gains tax impact for given lot selections.
    """
    
    @staticmethod
    def calculate_tender_tax(
        lots: List[Dict],
        lot_selections: Dict[str, int],
        tender_price: float,
        tax_rates: Dict
    ) -> Dict:
        """Calculate tax impact of selling specific lots.
        
        Args:
            lots: List of available lots with cost basis
            lot_selections: Map of lot_id to shares to sell
            tender_price: Price per share in tender offer
            tax_rates: Tax rate configuration with keys:
                - ltcg_rate: Combined LTCG tax rate
                - ordinary_income_rate: Combined STCG tax rate
            
        Returns:
            Detailed tax breakdown including:
            - gross_proceeds: Total proceeds before tax
            - ltcg_proceeds: Proceeds from LTCG lots
            - stcg_proceeds: Proceeds from STCG lots
            - ltcg_gain: Total LTCG gain
            - stcg_gain: Total STCG gain
            - ltcg_tax: Tax on LTCG
            - stcg_tax: Tax on STCG
            - total_tax: Combined tax liability
            - net_proceeds: After-tax proceeds
            - effective_tax_rate: Overall tax rate
            - lot_details: Per-lot breakdown
        """
        # Validate lot selections for better composability
        is_valid, errors = ShareSaleCalculator.validate_lot_selection(lots, lot_selections)
        if not is_valid:
            raise ValueError(f"Invalid lot selection: {'; '.join(errors)}")
        
        # Convert to Decimal for precision
        tender_price_dec = Decimal(str(tender_price))
        
        # Initialize totals
        total_shares = 0
        gross_proceeds = Decimal("0")
        ltcg_gain = Decimal("0")
        stcg_gain = Decimal("0")
        ltcg_proceeds = Decimal("0")
        stcg_proceeds = Decimal("0")
        lot_details = []
        
        # Get tax rates
        ltcg_rate = Decimal(str(tax_rates.get('ltcg_rate', 0.243)))
        stcg_rate = Decimal(str(tax_rates.get('ordinary_income_rate', 0.486)))
        
        # Process each lot selection
        for lot_id, shares_to_sell in lot_selections.items():
            if shares_to_sell <= 0:
                continue
                
            # Find the lot
            lot = next((l for l in lots if l.get('lot_id') == lot_id), None)
            if not lot:
                raise ValueError(f"Lot {lot_id} not found")
            
            # Validate shares available
            shares_available = lot.get('shares_available', lot.get('shares', 0))
            if shares_to_sell > shares_available:
                raise ValueError(
                    f"Lot {lot_id} only has {shares_available} shares available, "
                    f"cannot sell {shares_to_sell}"
                )
            
            # Calculate proceeds and gain for this lot
            lot_proceeds = tender_price_dec * shares_to_sell
            strike_price = Decimal(str(lot.get('strike_price', 0)))
            gain_per_share = tender_price_dec - strike_price
            total_gain = gain_per_share * shares_to_sell
            
            # Determine tax treatment
            is_ltcg = lot.get('current_status') == 'LTCG_eligible'
            
            if is_ltcg:
                ltcg_gain += total_gain
                ltcg_proceeds += lot_proceeds
                lot_tax = total_gain * ltcg_rate
                tax_type = "LTCG"
                tax_rate = ltcg_rate
            else:
                stcg_gain += total_gain
                stcg_proceeds += lot_proceeds
                lot_tax = total_gain * stcg_rate
                tax_type = "STCG"
                tax_rate = stcg_rate
            
            # Update totals
            total_shares += shares_to_sell
            gross_proceeds += lot_proceeds
            
            # Record lot details
            lot_details.append({
                'lot_id': lot_id,
                'shares_sold': shares_to_sell,
                'strike_price': float(strike_price),
                'proceeds': float(lot_proceeds),
                'gain': float(total_gain),
                'tax_type': tax_type,
                'tax_rate': float(tax_rate),
                'tax_owed': float(lot_tax)
            })
        
        # Calculate total tax
        ltcg_tax = ltcg_gain * ltcg_rate
        stcg_tax = stcg_gain * stcg_rate
        total_tax = ltcg_tax + stcg_tax
        net_proceeds = gross_proceeds - total_tax
        
        # Calculate effective rate
        effective_rate = float(total_tax / gross_proceeds) if gross_proceeds > 0 else 0
        
        return {
            'gross_proceeds': float(gross_proceeds),
            'ltcg_proceeds': float(ltcg_proceeds),
            'stcg_proceeds': float(stcg_proceeds),
            'ltcg_gain': float(ltcg_gain),
            'stcg_gain': float(stcg_gain),
            'ltcg_tax': float(ltcg_tax),
            'stcg_tax': float(stcg_tax),
            'total_tax': float(total_tax),
            'net_proceeds': float(net_proceeds),
            'effective_tax_rate': effective_rate,
            'shares_sold': total_shares,
            'lot_details': lot_details
        }
    
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
    
