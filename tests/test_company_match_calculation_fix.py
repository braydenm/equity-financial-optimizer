#!/usr/bin/env python3
"""
Test to demonstrate and fix the company match calculation issue.

The issue: company_match_amount is always 0.0 in the CSV outputs because
the projection calculator hardcodes it to 0 instead of calculating it.
"""

import sys
import os
from decimal import Decimal
from datetime import date

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.share_donation_calculator import ShareDonationCalculator
from calculators.components import DonationComponents


def test_share_donation_calculator_company_match():
    """Test that ShareDonationCalculator correctly calculates company match."""
    
    # Test data
    donation_date = date(2025, 9, 1)
    shares_donated = 6000
    fmv_at_donation = 56.0865  # ~$336,519 total
    cost_basis = 4.48
    exercise_date = date(2024, 11, 4)
    holding_period_days = 301
    company_match_ratio = 3.0  # 3:1 match
    
    # Calculate donation components
    components = ShareDonationCalculator.calculate_share_donation_components(
        lot_id="VCS-93",
        donation_date=donation_date,
        shares_donated=shares_donated,
        fmv_at_donation=fmv_at_donation,
        cost_basis=cost_basis,
        exercise_date=exercise_date,
        holding_period_days=holding_period_days,
        company_match_ratio=company_match_ratio
    )
    
    # Verify calculations
    expected_total_fmv = shares_donated * fmv_at_donation
    expected_company_match = expected_total_fmv * company_match_ratio
    
    print(f"Donation FMV: ${expected_total_fmv:,.2f}")
    print(f"Company match ratio: {company_match_ratio}x")
    print(f"Expected company match: ${expected_company_match:,.2f}")
    print(f"Actual company match: ${components.company_match_amount:,.2f}")
    
    # This should pass - the calculator is working correctly
    assert abs(components.company_match_amount - expected_company_match) < 0.01, \
        f"Company match calculation error: expected ${expected_company_match:,.2f}, got ${components.company_match_amount:,.2f}"
    
    print("✅ ShareDonationCalculator correctly calculates company match")
    
    return components


def test_projection_calculator_company_match_issue():
    """
    Demonstrate the issue in projection_calculator where company_match_amount
    is hardcoded to 0.0 instead of being calculated.
    """
    print("\n" + "="*80)
    print("ISSUE: In projection_calculator._process_donation():")
    print("- Line ~1043: company_match_amount = 0.0  # Hardcoded!")
    print("- The DonationComponents is created with this 0 value")
    print("- This causes all CSV outputs to show company_match_amount = 0.0")
    print("="*80)
    
    print("\nThe fix is simple - remove the hardcoded 0 and let the calculator do its job:")
    print("BEFORE: company_match_amount = 0.0")
    print("AFTER: Remove this line entirely - DonationComponents will be created")
    print("       with the correct calculation from ShareDonationCalculator")


if __name__ == "__main__":
    print("Testing company match calculation issue...\n")
    
    # Test that the calculator itself works correctly
    test_share_donation_calculator_company_match()
    
    # Explain the issue in projection calculator
    test_projection_calculator_company_match_issue()
    
    print("\n✅ Tests complete - issue identified!")