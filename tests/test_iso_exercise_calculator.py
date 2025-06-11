"""
Tests for ISO exercise calculator module.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.iso_exercise_calculator import (
    estimate_iso_exercise_tax,
    # find_amt_breakeven,
    calculate_federal_amt,
    calculate_california_amt,
    format_tax_estimate
)


def test_basic_amt_calculation():
    """Test basic AMT calculation matches reference values."""
    # Test case from reference calculator defaults
    wages = 100000
    interest_div = 1000
    shares = 5000  # 25% of 20000
    strike = 5.00
    fmv = 15.00
    
    result = estimate_iso_exercise_tax(
        wages=wages,
        other_income=interest_div,
        shares_to_exercise=shares,
        strike_price=strike,
        current_fmv=fmv,
        filing_status='single',
        include_california=True
    )
    
    print("Basic AMT Calculation Test")
    print("=" * 50)
    print(f"Wages: ${wages:,}")
    print(f"Other Income: ${interest_div:,}")
    print(f"Shares: {shares:,} @ ${strike} (FMV: ${fmv})")
    print(f"Bargain Element: ${result.bargain_element:,}")
    print()
    print(format_tax_estimate(result))
    print()
    
    # Basic sanity checks
    assert result.bargain_element == 50000, f"Expected bargain element of $50,000, got ${result.bargain_element:,}"
    assert result.exercise_cost == 25000, f"Expected exercise cost of $25,000, got ${result.exercise_cost:,}"
    assert result.shares_exercised == shares
    
    # Should trigger AMT with this bargain element
    assert result.federal_is_amt or result.ca_is_amt, "Expected AMT to apply"
    
    return result


def test_no_amt_scenario():
    """Test scenario where AMT should not apply."""
    # Lower income and small exercise
    result = estimate_iso_exercise_tax(
        wages=50000,
        other_income=0,
        shares_to_exercise=100,
        strike_price=5.00,
        current_fmv=10.00,  # Small gain
        filing_status='single',
        include_california=True
    )
    
    print("No AMT Scenario Test")
    print("=" * 50)
    print(format_tax_estimate(result))
    print()
    
    # With small bargain element, AMT shouldn't apply
    assert result.bargain_element == 500
    assert not result.federal_is_amt, "Federal AMT should not apply for small exercise"
    
    return result


# COMMENTED OUT: test_breakeven_calculation() - find_amt_breakeven was commented out
# This test used find_amt_breakeven() which is now commented out for future scenario construction use
# When AMT optimization features are re-enabled, this test should be uncommented
#
# def test_breakeven_calculation():
#     """Test AMT breakeven finder."""
#     wages = 100000
#     other_income = 1000
#     total_shares = 20000
#     strike = 5.00
#     fmv = 15.00
#     
#     breakeven = find_amt_breakeven(
#         wages=wages,
#         other_income=other_income,
#         total_shares_available=total_shares,
#         strike_price=strike,
#         current_fmv=fmv,
#         filing_status='single',
#         include_california=True
#     )
#     
#     print("AMT Breakeven Test")
#     print("=" * 50)
#     print(f"Total shares available: {total_shares:,}")
#     print(f"Federal AMT breakeven: {breakeven['federal_breakeven']:,} shares")
#     print(f"California AMT breakeven: {breakeven['california_breakeven']:,} shares")
#     print(f"Combined breakeven: {breakeven['combined_breakeven']:,} shares")
#     print()
#     
#     # Verify breakeven is reasonable
#     assert 0 < breakeven['combined_breakeven'] < total_shares
#     assert breakeven['federal_breakeven'] >= breakeven['combined_breakeven']
    assert breakeven['california_breakeven'] >= breakeven['combined_breakeven']
    
    # Verify that exercising at breakeven doesn't trigger AMT
    at_breakeven = estimate_iso_exercise_tax(
        wages=wages,
        other_income=other_income,
        shares_to_exercise=breakeven['combined_breakeven'],
        strike_price=strike,
        current_fmv=fmv,
        filing_status='single',
        include_california=True
    )
    
    assert not at_breakeven.federal_is_amt or not at_breakeven.ca_is_amt
    
    # Verify that exercising one more share triggers AMT
    if breakeven['combined_breakeven'] < total_shares:
        over_breakeven = estimate_iso_exercise_tax(
            wages=wages,
            other_income=other_income,
            shares_to_exercise=breakeven['combined_breakeven'] + 1,
            strike_price=strike,
            current_fmv=fmv,
            filing_status='single',
            include_california=True
        )
        
        assert over_breakeven.federal_is_amt or over_breakeven.ca_is_amt
    
    return breakeven


def test_married_filing_jointly():
    """Test calculations for married filing jointly."""
    result = estimate_iso_exercise_tax(
        wages=200000,  # Higher combined income
        other_income=2000,
        shares_to_exercise=10000,
        strike_price=5.00,
        current_fmv=15.00,
        filing_status='married_filing_jointly',
        include_california=True
    )
    
    print("Married Filing Jointly Test")
    print("=" * 50)
    print(format_tax_estimate(result))
    print()
    
    # Higher exemptions should apply
    assert result.bargain_element == 100000
    
    return result


def test_federal_only():
    """Test federal-only calculations (no CA tax)."""
    result = estimate_iso_exercise_tax(
        wages=100000,
        other_income=1000,
        shares_to_exercise=5000,
        strike_price=5.00,
        current_fmv=15.00,
        filing_status='single',
        include_california=False
    )
    
    print("Federal Only Test")
    print("=" * 50)
    print(format_tax_estimate(result))
    print()
    
    # No CA tax should be calculated
    assert result.ca_total == 0
    assert result.ca_regular_tax == 0
    assert result.ca_amt == 0
    
    return result


def test_high_income_scenario():
    """Test high income scenario with AMT phaseout."""
    result = estimate_iso_exercise_tax(
        wages=500000,  # High income
        other_income=50000,
        shares_to_exercise=15000,
        strike_price=5.00,
        current_fmv=25.00,  # Higher FMV
        filing_status='single',
        include_california=True
    )
    
    print("High Income Scenario Test")
    print("=" * 50)
    print(format_tax_estimate(result))
    print()
    
    # AMT should definitely apply
    assert result.federal_is_amt
    assert result.bargain_element == 300000
    
    return result


def run_all_tests():
    """Run all test cases."""
    print("Running Tax Estimator Tests")
    print("=" * 70)
    print()
    
    test_basic_amt_calculation()
    test_no_amt_scenario()
    # test_breakeven_calculation,  # Commented out - uses find_amt_breakeven
    test_married_filing_jointly()
    test_federal_only()
    test_high_income_scenario()
    
    print("All tests completed successfully!")


if __name__ == "__main__":
    run_all_tests()