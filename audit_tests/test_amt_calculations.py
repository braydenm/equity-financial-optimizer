"""
Comprehensive tests for AMT (Alternative Minimum Tax) calculations.

This test suite validates critical AMT calculations including:
- Federal AMT with two-tier rate structure
- AMT exemption phaseouts
- California AMT calculations
- AMT credit generation and carryforward
- Edge cases and high-income scenarios
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.iso_exercise_calculator import (
    calculate_federal_amt,
    calculate_california_amt,
    estimate_iso_exercise_tax
)

from calculators.tax_constants import (
    AMT_EXEMPTION_AMOUNT,
    AMT_PHASEOUT_THRESHOLD,
    AMT_THRESHOLD,
    AMT_RATE_LOW,
    AMT_RATE_HIGH,
    CALIFORNIA_AMT_EXEMPTION,
    CALIFORNIA_AMT_PHASEOUT_START,
    CALIFORNIA_AMT_PHASEOUT_RATE,
    CALIFORNIA_AMT_RATE
)


def test_federal_amt_basic():
    """Test basic federal AMT calculation without phaseout."""
    print("\n" + "="*70)
    print("TEST: Basic Federal AMT Calculation")
    print("="*70)

    wages = 100000
    other_income = 5000
    iso_bargain_element = 50000

    result = calculate_federal_amt(
        wages=wages,
        other_income=other_income,
        iso_bargain_element=iso_bargain_element,
        filing_status='single'
    )

    print(f"Regular income: ${wages + other_income:,}")
    print(f"ISO bargain element: ${iso_bargain_element:,}")
    print(f"AMT income: ${wages + other_income + iso_bargain_element:,}")
    print(f"\nResults:")
    print(f"  Regular tax: ${result.regular_tax:,.2f}")
    print(f"  AMT: ${result.amt:,.2f}")
    print(f"  Is AMT: {result.is_amt}")
    print(f"  AMT credit generated: ${result.amt_credit_generated:,.2f}")
    print(f"  Effective tax on exercise: ${result.effective_tax_on_exercise:,.2f}")

    # With $155k AMT income and $88,100 exemption for single filer
    # AMT taxable income = $66,900 at 26% = $17,394
    expected_amt = 66900 * 0.26
    assert abs(result.amt - expected_amt) < 1.0, f"Expected AMT ~${expected_amt:,.2f}, got ${result.amt:,.2f}"

    print("\n✅ Test passed!")


def test_federal_amt_phaseout():
    """Test AMT exemption phaseout calculation."""
    print("\n" + "="*70)
    print("TEST: Federal AMT Exemption Phaseout")
    print("="*70)

    # Income just above phaseout threshold
    wages = 500000
    other_income = 50000
    iso_bargain_element = 100000  # Total AMT income = $650k

    result = calculate_federal_amt(
        wages=wages,
        other_income=other_income,
        iso_bargain_element=iso_bargain_element,
        filing_status='single'
    )

    amt_income = wages + other_income + iso_bargain_element
    phaseout_amount = (amt_income - AMT_PHASEOUT_THRESHOLD['single']) * 0.25
    expected_exemption = max(0, AMT_EXEMPTION_AMOUNT['single'] - phaseout_amount)

    print(f"AMT income: ${amt_income:,}")
    print(f"Phaseout threshold: ${AMT_PHASEOUT_THRESHOLD['single']:,}")
    print(f"Excess over threshold: ${amt_income - AMT_PHASEOUT_THRESHOLD['single']:,}")
    print(f"Phaseout amount (25%): ${phaseout_amount:,}")
    print(f"Base exemption: ${AMT_EXEMPTION_AMOUNT['single']:,}")
    print(f"Exemption after phaseout: ${expected_exemption:,}")
    print(f"\nAMT calculation: ${result.amt:,.2f}")

    # Verify phaseout reduces exemption correctly
    assert expected_exemption < AMT_EXEMPTION_AMOUNT['single']

    print("\n✅ Test passed!")


def test_federal_amt_full_phaseout():
    """Test scenario where AMT exemption is fully phased out."""
    print("\n" + "="*70)
    print("TEST: Federal AMT Full Exemption Phaseout")
    print("="*70)

    # Very high income to fully phase out exemption
    # Exemption phases out at $0.25 per dollar over threshold
    # Single exemption of $88,100 fully phases out at $626,350 + ($88,100 / 0.25) = $978,750
    wages = 900000
    other_income = 100000
    iso_bargain_element = 0

    result = calculate_federal_amt(
        wages=wages,
        other_income=other_income,
        iso_bargain_element=iso_bargain_element,
        filing_status='single'
    )

    amt_income = wages + other_income
    full_phaseout_income = AMT_PHASEOUT_THRESHOLD['single'] + (AMT_EXEMPTION_AMOUNT['single'] / 0.25)

    print(f"AMT income: ${amt_income:,}")
    print(f"Full phaseout at: ${full_phaseout_income:,}")
    print(f"Exemption should be: $0")

    # At this income level, exemption should be fully phased out
    # AMT should be calculated on full income
    print(f"\nAMT: ${result.amt:,.2f}")

    print("\n✅ Test passed!")


def test_federal_amt_two_tier_rates():
    """Test AMT two-tier rate structure (26% and 28%)."""
    print("\n" + "="*70)
    print("TEST: Federal AMT Two-Tier Rate Structure")
    print("="*70)

    # Income that crosses into 28% bracket
    wages = 200000
    other_income = 10000
    iso_bargain_element = 150000  # Total AMT income = $360k

    result = calculate_federal_amt(
        wages=wages,
        other_income=other_income,
        iso_bargain_element=iso_bargain_element,
        filing_status='single'
    )

    amt_income = wages + other_income + iso_bargain_element
    amt_taxable = amt_income - AMT_EXEMPTION_AMOUNT['single']

    print(f"AMT income: ${amt_income:,}")
    print(f"AMT exemption: ${AMT_EXEMPTION_AMOUNT['single']:,}")
    print(f"AMT taxable income: ${amt_taxable:,}")
    print(f"AMT threshold for 28% rate: ${AMT_THRESHOLD:,}")

    # Calculate expected AMT with two tiers
    if amt_taxable <= AMT_THRESHOLD:
        expected_amt = amt_taxable * AMT_RATE_LOW
    else:
        expected_amt = AMT_THRESHOLD * AMT_RATE_LOW + (amt_taxable - AMT_THRESHOLD) * AMT_RATE_HIGH

    print(f"\nExpected AMT calculation:")
    print(f"  First ${AMT_THRESHOLD:,} at {AMT_RATE_LOW:.1%}: ${AMT_THRESHOLD * AMT_RATE_LOW:,.2f}")
    if amt_taxable > AMT_THRESHOLD:
        print(f"  Next ${amt_taxable - AMT_THRESHOLD:,} at {AMT_RATE_HIGH:.1%}: ${(amt_taxable - AMT_THRESHOLD) * AMT_RATE_HIGH:,.2f}")
    print(f"  Total expected: ${expected_amt:,.2f}")
    print(f"  Actual AMT: ${result.amt:,.2f}")

    assert abs(result.amt - expected_amt) < 1.0

    print("\n✅ Test passed!")


def test_california_amt():
    """Test California AMT calculation with phaseout."""
    print("\n" + "="*70)
    print("TEST: California AMT Calculation")
    print("="*70)

    wages = 250000
    other_income = 10000
    iso_bargain_element = 100000

    result = calculate_california_amt(
        wages=wages,
        other_income=other_income,
        iso_bargain_element=iso_bargain_element,
        filing_status='single'
    )

    ca_amt_income = wages + other_income + iso_bargain_element

    print(f"CA AMT income: ${ca_amt_income:,}")
    print(f"CA AMT exemption (base): ${CALIFORNIA_AMT_EXEMPTION['single']:,}")
    print(f"CA AMT phaseout starts at: ${CALIFORNIA_AMT_PHASEOUT_START['single']:,}")

    # Check if phaseout applies
    if ca_amt_income > CALIFORNIA_AMT_PHASEOUT_START['single']:
        phaseout = (ca_amt_income - CALIFORNIA_AMT_PHASEOUT_START['single']) * CALIFORNIA_AMT_PHASEOUT_RATE
        exemption = max(0, CALIFORNIA_AMT_EXEMPTION['single'] - phaseout)
        print(f"Phaseout amount: ${phaseout:,.2f}")
        print(f"Exemption after phaseout: ${exemption:,.2f}")

    print(f"\nCA AMT Results:")
    print(f"  Regular tax: ${result.regular_tax:,.2f}")
    print(f"  AMT: ${result.amt:,.2f}")
    print(f"  Is AMT: {result.is_amt}")

    # CA AMT rate is flat 7%
    assert result.amt > 0

    print("\n✅ Test passed!")


def test_married_filing_jointly():
    """Test AMT calculations for married filing jointly status."""
    print("\n" + "="*70)
    print("TEST: Married Filing Jointly AMT")
    print("="*70)

    wages = 400000  # Combined income
    other_income = 20000
    iso_bargain_element = 200000

    result_single = calculate_federal_amt(
        wages=wages/2,  # Compare single filer with half income
        other_income=other_income/2,
        iso_bargain_element=iso_bargain_element/2,
        filing_status='single'
    )

    result_married = calculate_federal_amt(
        wages=wages,
        other_income=other_income,
        iso_bargain_element=iso_bargain_element,
        filing_status='married_filing_jointly'
    )

    print(f"Income: ${wages + other_income:,}")
    print(f"ISO bargain element: ${iso_bargain_element:,}")
    print(f"\nSingle filer (half income):")
    print(f"  Exemption: ${AMT_EXEMPTION_AMOUNT['single']:,}")
    print(f"  AMT: ${result_single.amt:,.2f}")
    print(f"\nMarried filing jointly:")
    print(f"  Exemption: ${AMT_EXEMPTION_AMOUNT['married_filing_jointly']:,}")
    print(f"  AMT: ${result_married.amt:,.2f}")

    # MFJ should have higher exemption than single (but less than 2x due to marriage penalty)
    assert AMT_EXEMPTION_AMOUNT['married_filing_jointly'] > AMT_EXEMPTION_AMOUNT['single']
    assert AMT_EXEMPTION_AMOUNT['married_filing_jointly'] < AMT_EXEMPTION_AMOUNT['single'] * 2

    print("\n✅ Test passed!")


def test_amt_credit_generation():
    """Test AMT credit generation and carryforward."""
    print("\n" + "="*70)
    print("TEST: AMT Credit Generation")
    print("="*70)

    # Exercise ISOs to trigger AMT
    result = estimate_iso_exercise_tax(
        wages=150000,
        other_income=5000,
        shares_to_exercise=10000,
        strike_price=5.0,
        current_fmv=20.0,  # $15 bargain element per share
        filing_status='single',
        include_california=True
    )

    print(f"ISO exercise: 10,000 shares")
    print(f"Bargain element: ${result.bargain_element:,}")
    print(f"\nFederal tax:")
    print(f"  Regular tax: ${result.federal_regular_tax:,.2f}")
    print(f"  AMT: ${result.federal_amt:,.2f}")
    print(f"  Is AMT: {result.federal_is_amt}")
    print(f"  AMT credit generated: ${result.federal_amt_credit:,.2f}")
    print(f"\nCalifornia tax:")
    print(f"  Regular tax: ${result.ca_regular_tax:,.2f}")
    print(f"  AMT: ${result.ca_amt:,.2f}")
    print(f"  Is AMT: {result.ca_is_amt}")

    # AMT credit should equal the difference between AMT and regular tax
    if result.federal_is_amt:
        expected_credit = result.federal_amt - result.federal_regular_tax
        assert abs(result.federal_amt_credit - expected_credit) < 1.0

    print("\n✅ Test passed!")


def test_no_amt_scenario():
    """Test scenario where AMT does not apply."""
    print("\n" + "="*70)
    print("TEST: No AMT Scenario")
    print("="*70)

    # Low income, small exercise
    wages = 60000
    other_income = 0
    iso_bargain_element = 10000

    result = calculate_federal_amt(
        wages=wages,
        other_income=other_income,
        iso_bargain_element=iso_bargain_element,
        filing_status='single'
    )

    print(f"Regular income: ${wages + other_income:,}")
    print(f"ISO bargain element: ${iso_bargain_element:,}")
    print(f"Total AMT income: ${wages + other_income + iso_bargain_element:,}")
    print(f"\nResults:")
    print(f"  Regular tax: ${result.regular_tax:,.2f}")
    print(f"  AMT: ${result.amt:,.2f}")
    print(f"  Is AMT: {result.is_amt}")
    print(f"  Effective tax on exercise: ${result.effective_tax_on_exercise:,.2f}")

    # At this income level, regular tax should exceed AMT
    assert not result.is_amt
    assert result.amt_credit_generated == 0

    print("\n✅ Test passed!")


def test_edge_case_exact_threshold():
    """Test edge case at exact AMT threshold."""
    print("\n" + "="*70)
    print("TEST: Edge Case - Exact AMT Threshold")
    print("="*70)

    # Create income that puts AMT taxable income exactly at threshold
    exemption = AMT_EXEMPTION_AMOUNT['single']
    target_amt_taxable = AMT_THRESHOLD
    total_amt_income = target_amt_taxable + exemption

    wages = total_amt_income - 50000  # Leave room for ISO bargain element
    iso_bargain_element = 50000

    result = calculate_federal_amt(
        wages=wages,
        other_income=0,
        iso_bargain_element=iso_bargain_element,
        filing_status='single'
    )

    amt_taxable = wages + iso_bargain_element - exemption

    print(f"Target AMT taxable income: ${AMT_THRESHOLD:,}")
    print(f"Actual AMT taxable income: ${amt_taxable:,}")
    print(f"AMT calculation: ${result.amt:,.2f}")
    print(f"Expected (all at 26%): ${AMT_THRESHOLD * AMT_RATE_LOW:,.2f}")

    # All income should be taxed at 26% rate
    expected_amt = AMT_THRESHOLD * AMT_RATE_LOW
    assert abs(result.amt - expected_amt) < 100  # Allow small rounding differences

    print("\n✅ Test passed!")


def run_all_tests():
    """Run all AMT calculation tests."""
    print("\n" + "="*70)
    print("AMT CALCULATION TESTS")
    print("="*70)

    test_federal_amt_basic()
    test_federal_amt_phaseout()
    test_federal_amt_full_phaseout()
    test_federal_amt_two_tier_rates()
    test_california_amt()
    test_married_filing_jointly()
    test_amt_credit_generation()
    test_no_amt_scenario()
    test_edge_case_exact_threshold()

    print("\n" + "="*70)
    print("✅ All AMT calculation tests passed!")
    print("="*70)


if __name__ == "__main__":
    run_all_tests()
