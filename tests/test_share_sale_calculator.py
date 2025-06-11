"""
Tests for the share sale calculator.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.share_sale_calculator import ShareSaleCalculator


def test_basic_tender_calculation():
    """Test basic tender tax calculation."""
    
    # Sample lots
    lots = [
        {
            'lot_id': 'LOT-001',
            'shares': 1000,
            'strike_price': 10.0,
            'current_status': 'LTCG_eligible'
        },
        {
            'lot_id': 'LOT-002',
            'shares': 500,
            'strike_price': 5.0,
            'current_status': 'STCG'
        }
    ]
    
    # Sell specific lots
    lot_selections = {
        'LOT-001': 500,  # 500 LTCG shares
        'LOT-002': 300   # 300 STCG shares
    }
    
    tax_rates = {
        'ltcg_rate': 0.243,      # 24.3% LTCG
        'ordinary_income_rate': 0.486  # 48.6% STCG
    }
    
    tender_price = 25.0
    
    result = ShareSaleCalculator.calculate_tender_tax(
        lots, lot_selections, tender_price, tax_rates
    )
    
    print("Basic Tender Calculation Test")
    print("=" * 50)
    print(f"Shares sold: {result['shares_sold']}")
    print(f"Gross proceeds: ${result['gross_proceeds']:,.2f}")
    print(f"LTCG gain: ${result['ltcg_gain']:,.2f}")
    print(f"STCG gain: ${result['stcg_gain']:,.2f}")
    print(f"Total tax: ${result['total_tax']:,.2f}")
    print(f"Net proceeds: ${result['net_proceeds']:,.2f}")
    print(f"Effective tax rate: {result['effective_tax_rate']:.1%}")
    
    # Verify calculations
    assert result['shares_sold'] == 800
    assert result['gross_proceeds'] == 20000  # 800 * 25
    
    # LTCG: 500 shares * (25 - 10) = 7500 gain * 0.243 = 1822.50
    assert abs(result['ltcg_tax'] - 1822.50) < 0.01
    
    # STCG: 300 shares * (25 - 5) = 6000 gain * 0.486 = 2916.00
    assert abs(result['stcg_tax'] - 2916.00) < 0.01
    
    print("\n✓ All calculations verified")


def test_lot_validation():
    """Test lot selection validation."""
    
    lots = [
        {
            'lot_id': 'LOT-001',
            'shares': 1000,
            'strike_price': 10.0
        }
    ]
    
    # Test valid selection
    valid_selection = {'LOT-001': 500}
    is_valid, errors = ShareSaleCalculator.validate_lot_selection(lots, valid_selection)
    assert is_valid
    assert len(errors) == 0
    
    # Test invalid selections
    invalid_selections = [
        ({'LOT-999': 100}, "Lot LOT-999 not found"),
        ({'LOT-001': 2000}, "requested 2000 shares but only 1000 available"),
        ({'LOT-001': -5}, "shares to sell must be non-negative")
    ]
    
    print("\nLot Validation Tests")
    print("=" * 50)
    
    for selection, expected_error in invalid_selections:
        is_valid, errors = ShareSaleCalculator.validate_lot_selection(lots, selection)
        assert not is_valid
        assert any(expected_error in error for error in errors)
        print(f"✓ Correctly rejected: {selection} - {errors[0]}")


# Donation impact testing removed - will be in separate donation_impact.py tests


def test_edge_cases():
    """Test edge cases and error handling."""
    
    print("\nEdge Case Tests")
    print("=" * 50)
    
    # Empty lot selection
    result = ShareSaleCalculator.calculate_tender_tax(
        [], {}, 25.0, {'ltcg_rate': 0.243}
    )
    assert result['shares_sold'] == 0
    assert result['total_tax'] == 0
    print("✓ Empty selection handled correctly")
    
    # Zero shares in selection
    lots = [{'lot_id': 'LOT-001', 'shares': 100, 'strike_price': 10}]
    result = ShareSaleCalculator.calculate_tender_tax(
        lots, {'LOT-001': 0}, 25.0, {'ltcg_rate': 0.243}
    )
    assert result['shares_sold'] == 0
    print("✓ Zero shares handled correctly")
    
    # Missing tax rates (should use defaults)
    result = ShareSaleCalculator.calculate_tender_tax(
        lots, {'LOT-001': 50}, 25.0, {}
    )
    assert result['total_tax'] > 0  # Should use default rates
    print("✓ Missing tax rates handled with defaults")


def run_all_tests():
    """Run all tender calculator tests."""
    print("Running Tender Calculator Tests")
    print("=" * 70)
    
    test_basic_tender_calculation()
    test_lot_validation()
    test_edge_cases()
    
    print("\n" + "=" * 70)
    print("All tests passed! ✅")


if __name__ == "__main__":
    run_all_tests()