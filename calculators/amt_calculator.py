"""
Alternative Minimum Tax (AMT) calculator module.

This module provides centralized AMT calculation functions to avoid duplication
across different calculators. It handles exemption phaseouts and the two-tier
AMT rate structure.
"""

from typing import Dict, Optional
from dataclasses import dataclass

from .tax_constants import (
    AMT_EXEMPTION_AMOUNT,
    AMT_PHASEOUT_THRESHOLD,
    AMT_PHASEOUT_RATE,
    AMT_RATE_LOW,
    AMT_RATE_HIGH,
    AMT_THRESHOLD,
    FEDERAL_TAX_BRACKETS,
    FEDERAL_STANDARD_DEDUCTION
)


@dataclass
class AMTCalculationResult:
    """Result of AMT calculation with all relevant components."""
    regular_tax: float
    amt_income: float
    amt_exemption: float
    amt_taxable_income: float
    amt_tax: float
    is_amt: bool
    amt_credit_generated: float
    effective_amt_on_adjustment: float  # Additional tax due to AMT adjustment (e.g., ISO bargain element)


def calculate_amt_exemption_with_phaseout(amt_income: float, filing_status: str = 'single') -> float:
    """
    Calculate AMT exemption amount with phaseout.

    The AMT exemption phases out at 25 cents per dollar of AMT income above the threshold.

    Args:
        amt_income: Alternative Minimum Taxable Income (AMTI)
        filing_status: 'single' or 'married_filing_jointly'

    Returns:
        AMT exemption amount after phaseout
    """
    exemption = AMT_EXEMPTION_AMOUNT[filing_status]
    phaseout_threshold = AMT_PHASEOUT_THRESHOLD[filing_status]

    if amt_income > phaseout_threshold:
        exemption_phaseout = (amt_income - phaseout_threshold) * AMT_PHASEOUT_RATE
        exemption = max(exemption - exemption_phaseout, 0)

    return exemption


def calculate_amt_tax(amt_taxable_income: float) -> float:
    """
    Calculate AMT using the two-tier rate structure.

    AMT uses a two-tier system:
    - 26% on the first $239,900 of AMT taxable income
    - 28% on amounts above $239,900

    Args:
        amt_taxable_income: AMT taxable income after exemption

    Returns:
        Total AMT tax
    """
    if amt_taxable_income <= 0:
        return 0.0

    if amt_taxable_income <= AMT_THRESHOLD:
        return amt_taxable_income * AMT_RATE_LOW
    else:
        return AMT_THRESHOLD * AMT_RATE_LOW + (amt_taxable_income - AMT_THRESHOLD) * AMT_RATE_HIGH


def calculate_tax_from_brackets(taxable_income: float, brackets: list) -> float:
    """
    Calculate tax using progressive tax brackets.

    Args:
        taxable_income: Income subject to tax
        brackets: List of (lower, upper, rate) tuples

    Returns:
        Total tax owed
    """
    if taxable_income <= 0:
        return 0.0

    tax = 0.0

    for lower, upper, rate in brackets:
        if taxable_income > lower:
            taxable_in_bracket = min(upper, taxable_income) - lower
            tax += taxable_in_bracket * rate
            if taxable_income <= upper:
                break

    return tax


def calculate_federal_amt(
    ordinary_income: float,
    amt_adjustments: float = 0.0,
    capital_gains: float = 0.0,
    filing_status: str = 'single',
    existing_amt_credit: float = 0.0
) -> AMTCalculationResult:
    """
    Calculate federal AMT with all components.

    This is the main AMT calculation function that determines if AMT applies
    and calculates any AMT credit generated.

    Args:
        ordinary_income: W2 wages + other ordinary income (before deductions)
        amt_adjustments: AMT preference items (e.g., ISO bargain element)
        capital_gains: Capital gains (both short and long term)
        filing_status: 'single' or 'married_filing_jointly'
        existing_amt_credit: AMT credit carryforward from prior years

    Returns:
        AMTCalculationResult with all calculation components
    """
    # Calculate regular tax (without AMT adjustments)
    agi = ordinary_income + capital_gains
    standard_deduction = FEDERAL_STANDARD_DEDUCTION[filing_status]
    taxable_income = max(0, agi - standard_deduction)

    # Regular tax uses the bracket system
    regular_tax = calculate_tax_from_brackets(
        taxable_income,
        FEDERAL_TAX_BRACKETS[filing_status]
    )

    # AMT calculation (with AMT adjustments)
    amt_income = ordinary_income + capital_gains + amt_adjustments

    # Calculate AMT exemption with phaseout
    amt_exemption = calculate_amt_exemption_with_phaseout(amt_income, filing_status)
    amt_taxable_income = max(0, amt_income - amt_exemption)

    # Calculate AMT tax
    amt_tax = calculate_amt_tax(amt_taxable_income)

    # Apply existing AMT credit to regular tax
    regular_tax_after_credit = max(0, regular_tax - existing_amt_credit)
    amt_credit_used = regular_tax - regular_tax_after_credit

    # Determine which tax applies
    is_amt = amt_tax > regular_tax_after_credit

    # AMT credit is generated when you pay AMT
    # It's the excess of AMT over regular tax (before credits)
    amt_credit_generated = max(0, amt_tax - regular_tax) if is_amt else 0.0

    # Calculate the effective additional tax due to AMT adjustments
    # This is useful for understanding the tax impact of ISO exercises
    effective_amt_on_adjustment = 0.0
    if amt_adjustments > 0 and is_amt:
        # Calculate what AMT would have been without the adjustment
        amt_income_without_adjustment = ordinary_income + capital_gains
        exemption_without_adjustment = calculate_amt_exemption_with_phaseout(
            amt_income_without_adjustment, filing_status
        )
        amt_taxable_without = max(0, amt_income_without_adjustment - exemption_without_adjustment)
        amt_tax_without = calculate_amt_tax(amt_taxable_without)

        # The difference is the effective tax on the adjustment
        effective_amt_on_adjustment = amt_tax - max(amt_tax_without, regular_tax)

    return AMTCalculationResult(
        regular_tax=regular_tax,
        amt_income=amt_income,
        amt_exemption=amt_exemption,
        amt_taxable_income=amt_taxable_income,
        amt_tax=amt_tax,
        is_amt=is_amt,
        amt_credit_generated=amt_credit_generated,
        effective_amt_on_adjustment=effective_amt_on_adjustment
    )


def calculate_amt_for_annual_tax(
    agi: float,
    iso_bargain_element: float,
    filing_status: str = 'single',
    existing_amt_credit: float = 0.0,
    regular_tax_before_credits: float = 0.0
) -> Dict[str, float]:
    """
    Calculate AMT for annual tax computation.

    This is a simplified interface for the annual tax calculator that returns
    a dictionary matching the expected format.

    Args:
        agi: Adjusted Gross Income (wages + capital gains + other income)
        iso_bargain_element: Total ISO bargain element for the year
        filing_status: 'single' or 'married_filing_jointly'
        existing_amt_credit: AMT credit from prior years
        regular_tax_before_credits: Regular tax calculated separately

    Returns:
        Dictionary with AMT calculation results
    """
    # AMT income includes the ISO bargain element
    amt_income = agi + iso_bargain_element

    # Calculate AMT exemption and tax
    amt_exemption = calculate_amt_exemption_with_phaseout(amt_income, filing_status)
    amt_taxable_income = max(0, amt_income - amt_exemption)
    amt_tax = calculate_amt_tax(amt_taxable_income)

    # Apply AMT credit to regular tax
    regular_tax_after_credit = max(0, regular_tax_before_credits - existing_amt_credit)
    amt_credit_used = regular_tax_before_credits - regular_tax_after_credit

    # Determine if AMT applies
    is_amt = amt_tax > regular_tax_after_credit
    tax_owed = max(amt_tax, regular_tax_after_credit)

    # Calculate AMT credit generated
    amt_credit_generated = max(0, amt_tax - regular_tax_before_credits) if is_amt else 0.0

    # Calculate AMT credit carryforward
    amt_credit_carryforward = existing_amt_credit - amt_credit_used + amt_credit_generated

    return {
        'amt_income': amt_income,
        'amt': amt_tax,
        'is_amt': is_amt,
        'tax_owed': tax_owed,
        'amt_credit_generated': amt_credit_generated,
        'amt_credit_used': amt_credit_used,
        'amt_credit_carryforward': amt_credit_carryforward
    }
