#!/usr/bin/env python3
"""
Basic tests for the Share Donation Calculator.

Simple validation that the calculator functions work and return expected data structures.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.share_donation_calculator import ShareDonationCalculator


def test_basic_share_donation():
    """Test basic share donation calculation works."""
    result = ShareDonationCalculator.calculate_donation(
        agi=200000,
        tax_rate=0.50,
        company_match_ratio=3.0,
        shares=1000,
        share_price=60.0,
        cost_basis=10.0,
        holding_period_months=24,
        asset_type='STOCK'
    )
    
    # Validate result has expected attributes
    assert hasattr(result, 'donation_value')
    assert hasattr(result, 'tax_deduction')
    assert hasattr(result, 'tax_savings')
    assert hasattr(result, 'company_match')
    assert hasattr(result, 'total_impact')
    assert hasattr(result, 'net_cost')
    assert hasattr(result, 'impact_multiple')
    
    # Basic sanity checks
    assert result.donation_value == 60000.0  # shares * price
    assert result.tax_deduction > 0
    assert result.total_impact >= result.donation_value


def test_cash_donation():
    """Test cash donation calculation works."""
    result = ShareDonationCalculator.calculate_donation(
        agi=200000,
        tax_rate=0.50,
        company_match_ratio=3.0,
        cash_amount=50000
    )
    
    # Validate result structure
    assert hasattr(result, 'donation_value')
    assert hasattr(result, 'total_impact')
    
    # Basic checks
    assert result.donation_value == 50000.0




def main():
    """Run all tests."""
    print("TESTING SHARE DONATION CALCULATOR")
    print("=" * 50)
    
    tests = [
        test_basic_share_donation,
        test_cash_donation,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            print(f"✅ {test_func.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__}: {e}")
            failed += 1
    
    print("-" * 50)
    print(f"Tests: {len(tests)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"💥 {failed} test(s) failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)