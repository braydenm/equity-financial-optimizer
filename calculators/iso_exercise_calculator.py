"""
ISO exercise calculator with AMT calculations.

This module calculates the tax impact of exercising Incentive Stock Options (ISOs),
including Alternative Minimum Tax (AMT) calculations for both federal and California taxes.

Refactored to support annual tax composition:
- calculate_exercise_components() returns components for annual aggregation
- estimate_iso_exercise_tax() remains for UI display estimates only
"""

from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from datetime import date
from calculators.components import ISOExerciseComponents, NSOExerciseComponents

# Import tax constants from centralized module
from calculators.tax_constants import (
    FEDERAL_TAX_BRACKETS,
    FEDERAL_STANDARD_DEDUCTION,
    AMT_EXEMPTION_AMOUNT,
    AMT_PHASEOUT_THRESHOLD,
    AMT_THRESHOLD,
    AMT_RATE_LOW,
    AMT_RATE_HIGH,
    AMT_PHASEOUT_RATE,
    CALIFORNIA_TAX_BRACKETS,
    CALIFORNIA_STANDARD_DEDUCTION,
    CALIFORNIA_AMT_EXEMPTION,
    CALIFORNIA_AMT_RATE,
    CALIFORNIA_AMT_PHASEOUT_START,
    CALIFORNIA_AMT_PHASEOUT_RATE
)

# Import AMT calculation functions
from calculators.amt_calculator import (
    calculate_federal_amt as calculate_federal_amt_centralized,
    AMTCalculationResult
)


@dataclass
class AMTCalculation:
    """Results from AMT calculation."""
    regular_tax: float
    amt: float
    is_amt: bool
    amt_credit_generated: float
    effective_tax_on_exercise: float


@dataclass
class TaxEstimate:
    """Complete tax estimate for ISO exercise."""
    # Federal
    federal_regular_tax: float
    federal_amt: float
    federal_is_amt: bool
    federal_amt_credit: float
    federal_total: float

    # California (if applicable)
    ca_regular_tax: float
    ca_amt: float
    ca_is_amt: bool
    ca_total: float

    # Combined
    total_tax: float
    effective_rate: float
    additional_tax_from_exercise: float

    # Exercise details
    shares_exercised: int
    bargain_element: float
    exercise_cost: float
    total_cash_needed: float





def calculate_tax_from_brackets_ca(
    income: float,
    brackets: List[Tuple[float, float, float]]
) -> float:
    """Calculate tax based on income and California-style tax brackets.

    California brackets are in format (lower, upper, rate) which matches
    the format used by federal brackets after the refactoring.
    """
    if income <= 0:
        return 0

    tax = 0
    for lower, upper, rate in brackets:
        if income > lower:
            taxable_amount = min(upper, income) - lower
            tax += taxable_amount * rate
            if income <= upper:
                break

    return tax


def calculate_federal_amt(
    wages: float,
    other_income: float,
    iso_bargain_element: float,
    filing_status: str = 'single'
) -> AMTCalculation:
    """Calculate federal AMT impact from ISO exercise using centralized AMT calculator."""
    # Use the centralized AMT calculator
    result = calculate_federal_amt_centralized(
        ordinary_income=wages + other_income,
        amt_adjustments=iso_bargain_element,
        capital_gains=0.0,  # No capital gains at exercise time (gains only occur when shares are sold)
        filing_status=filing_status,
        existing_amt_credit=0.0  # No existing credit for exercise estimates
    )

    # Convert to the expected AMTCalculation format
    return AMTCalculation(
        regular_tax=result.regular_tax,
        amt=result.amt_tax,
        is_amt=result.is_amt,
        amt_credit_generated=result.amt_credit_generated,
        effective_tax_on_exercise=result.effective_amt_on_adjustment
    )


def calculate_california_amt(
    wages: float,
    other_income: float,
    iso_bargain_element: float,
    filing_status: str = 'single'
) -> AMTCalculation:
    """Calculate California AMT impact from ISO exercise."""
    # Regular CA tax (ISO gain NOT included)
    ca_agi = wages + other_income
    ca_taxable_income = max(0, ca_agi - CALIFORNIA_STANDARD_DEDUCTION[filing_status])
    ca_regular_tax = calculate_tax_from_brackets_ca(
        ca_taxable_income,
        CALIFORNIA_TAX_BRACKETS[filing_status]
    )

    # CA AMT (ISO gain IS included)
    ca_amti = wages + other_income + iso_bargain_element
    ca_amt_exemption = CALIFORNIA_AMT_EXEMPTION[filing_status]

    # Apply phaseout
    if ca_amti > CALIFORNIA_AMT_PHASEOUT_START[filing_status]:
        ca_amt_exemption -= (ca_amti - CALIFORNIA_AMT_PHASEOUT_START[filing_status]) * CALIFORNIA_AMT_PHASEOUT_RATE
        ca_amt_exemption = max(0, ca_amt_exemption)

    ca_amt = max(0, ca_amti - ca_amt_exemption) * CALIFORNIA_AMT_RATE
    is_ca_amt = ca_amt > ca_regular_tax
    total_ca_tax = max(ca_regular_tax, ca_amt)

    # Calculate effective tax on the ISO exercise
    effective_tax = total_ca_tax - ca_regular_tax if iso_bargain_element > 0 else 0

    return AMTCalculation(
        regular_tax=ca_regular_tax,
        amt=ca_amt,
        is_amt=is_ca_amt,
        amt_credit_generated=0,  # CA AMT credit tracking not implemented. See other TODO note in annual_tax_calculator.py
        effective_tax_on_exercise=effective_tax
    )


def estimate_iso_exercise_tax(
    wages: float,
    other_income: float = 0,
    shares_to_exercise: int = 0,
    strike_price: float = 0,
    current_fmv: float = 0,
    filing_status: str = 'single',
    include_california: bool = True
) -> TaxEstimate:
    """
    Estimate total tax impact of exercising ISOs.

    Args:
        wages: W-2 income (after 401k/pre-tax deductions)
        other_income: Interest, dividends, and other ordinary income
        shares_to_exercise: Number of ISO shares to exercise
        strike_price: Exercise price per share
        current_fmv: Current fair market value per share
        filing_status: 'single' or 'married_filing_jointly'
        include_california: Whether to include CA tax calculations

    Returns:
        TaxEstimate with complete tax breakdown
    """
    # Calculate bargain element
    bargain_element = shares_to_exercise * max(0, current_fmv - strike_price)
    exercise_cost = shares_to_exercise * strike_price

    # Calculate baseline taxes (no exercise)
    baseline_federal = calculate_federal_amt(wages, other_income, 0, filing_status)

    # Calculate federal taxes with exercise
    federal_with_exercise = calculate_federal_amt(
        wages, other_income, bargain_element, filing_status
    )

    # California calculations
    if include_california:
        baseline_ca = calculate_california_amt(wages, other_income, 0, filing_status)
        ca_with_exercise = calculate_california_amt(
            wages, other_income, bargain_element, filing_status
        )
        ca_total = ca_with_exercise.amt if ca_with_exercise.is_amt else ca_with_exercise.regular_tax
        additional_ca_tax = ca_total - baseline_ca.regular_tax
    else:
        ca_with_exercise = AMTCalculation(0, 0, False, 0, 0)
        ca_total = 0
        additional_ca_tax = 0

    # Calculate totals
    federal_total = federal_with_exercise.amt if federal_with_exercise.is_amt else federal_with_exercise.regular_tax
    additional_federal_tax = federal_total - baseline_federal.regular_tax

    total_tax = federal_total + ca_total
    additional_tax = additional_federal_tax + additional_ca_tax

    total_income = wages + other_income + bargain_element
    effective_rate = total_tax / total_income if total_income > 0 else 0

    total_cash_needed = exercise_cost + total_tax

    return TaxEstimate(
        # Federal
        federal_regular_tax=federal_with_exercise.regular_tax,
        federal_amt=federal_with_exercise.amt,
        federal_is_amt=federal_with_exercise.is_amt,
        federal_amt_credit=federal_with_exercise.amt_credit_generated,
        federal_total=federal_total,

        # California
        ca_regular_tax=ca_with_exercise.regular_tax,
        ca_amt=ca_with_exercise.amt,
        ca_is_amt=ca_with_exercise.is_amt,
        ca_total=ca_total,

        # Combined
        total_tax=total_tax,
        effective_rate=effective_rate,
        additional_tax_from_exercise=additional_tax,

        # Exercise details
        shares_exercised=shares_to_exercise,
        bargain_element=bargain_element,
        exercise_cost=exercise_cost,
        total_cash_needed=total_cash_needed
    )


# COMMENTED OUT: find_amt_breakeven() - AMT Optimization Function
#
# This function finds the maximum ISO shares that can be exercised before triggering AMT.
# It's currently unused by the projection system but represents critical AMT optimization logic.
#
# Future Use Case: Scenario construction helpers that suggest AMT-optimal exercise amounts
# - "What's the max ISOs I can exercise before AMT?"
# - Generate exercise scenarios based on AMT breakeven analysis
# - Inform users of AMT thresholds before they construct scenarios
#
# The function uses binary search to find breakeven points for both federal and CA AMT.
# When scenario construction helpers are built, this will be the core intelligence for
# AMT-aware exercise planning.
#
# def find_amt_breakeven(
#     wages: float,
#     other_income: float,
#     total_shares_available: int,
#     strike_price: float,
#     current_fmv: float,
#     filing_status: str = 'single',
#     include_california: bool = True
# ) -> Dict[str, int]:
#     """
#     Find the maximum shares that can be exercised before triggering AMT.
#
#     Returns dict with:
#         - 'federal_breakeven': Max shares before federal AMT
#         - 'california_breakeven': Max shares before CA AMT (if applicable)
#         - 'combined_breakeven': Max shares before any AMT
#     """
#     if total_shares_available == 0 or current_fmv <= strike_price:
#         return {
#             'federal_breakeven': 0,
#             'california_breakeven': 0,
#             'combined_breakeven': 0
#         }
#
#     # Binary search for federal AMT breakeven
#     def find_federal_breakeven():
#         low, high = 0, total_shares_available
#
#         while high - low > 1:
#             mid = (low + high) // 2
#             result = estimate_iso_exercise_tax(
#                 wages, other_income, mid, strike_price, current_fmv,
#                 filing_status, False
#             )
#
#             if result.federal_is_amt:
#                 high = mid
#             else:
#                 low = mid
#
#         # Verify the boundary
#         if low < total_shares_available:
#             verify = estimate_iso_exercise_tax(
#                 wages, other_income, low + 1, strike_price, current_fmv,
#                 filing_status, False
#             )
#             if not verify.federal_is_amt:
#                 return low + 1
#
#         return low
#
#     # Binary search for CA AMT breakeven
#     def find_ca_breakeven():
#         if not include_california:
#             return total_shares_available
#
#         low, high = 0, total_shares_available
#
#         while high - low > 1:
#             mid = (low + high) // 2
#             bargain_element = mid * (current_fmv - strike_price)
#             ca_result = calculate_california_amt(
#                 wages, other_income, bargain_element, filing_status
#             )
#
#             if ca_result.is_amt:
#                 high = mid
#             else:
#                 low = mid
#
#         return low
#
#     federal_breakeven = find_federal_breakeven()
#     ca_breakeven = find_ca_breakeven()
#
#     # Combined breakeven is the minimum of both
#     combined_breakeven = min(federal_breakeven, ca_breakeven)
#
#     return {
#         'federal_breakeven': federal_breakeven,
#         'california_breakeven': ca_breakeven,
#         'combined_breakeven': combined_breakeven
#     }


def calculate_exercise_components(
    lot_id: str,
    exercise_date: date,
    shares_to_exercise: int,
    strike_price: float,
    current_fmv: float,
    grant_date: date
) -> ISOExerciseComponents:
    """
    Calculate components from ISO exercise for annual tax aggregation.

    This function extracts the tax components from an ISO exercise action
    without calculating the actual tax. The components are used by the
    annual tax calculator to determine actual tax liability.

    Args:
        lot_id: Identifier for the lot being exercised
        exercise_date: Date of exercise
        shares_to_exercise: Number of shares to exercise
        strike_price: Exercise price per share
        current_fmv: Fair market value per share at exercise
        grant_date: Original grant date (for qualifying disposition tracking)

    Returns:
        ISOExerciseComponents containing all relevant data for tax calculation
    """
    exercise_cost = shares_to_exercise * strike_price
    bargain_element = shares_to_exercise * max(0, current_fmv - strike_price)

    return ISOExerciseComponents(
        lot_id=lot_id,
        exercise_date=exercise_date,
        shares_exercised=shares_to_exercise,
        strike_price=strike_price,
        fmv_at_exercise=current_fmv,
        exercise_cost=exercise_cost,
        bargain_element=bargain_element,
        grant_date=grant_date
    )


def calculate_nso_exercise_components(
    lot_id: str,
    exercise_date: date,
    shares_to_exercise: int,
    strike_price: float,
    current_fmv: float,
    grant_date: date
) -> NSOExerciseComponents:
    """
    Calculate components from NSO exercise for annual tax aggregation.

    This function extracts the tax components from an NSO exercise action
    without calculating the actual tax. The components are used by the
    annual tax calculator to determine actual tax liability.

    NSO exercises create ordinary income equal to the bargain element
    (FMV - strike price) at the time of exercise.

    Args:
        lot_id: Identifier for the lot being exercised
        exercise_date: Date of exercise
        shares_to_exercise: Number of shares to exercise
        strike_price: Exercise price per share
        current_fmv: Fair market value per share at exercise
        grant_date: Original grant date (for holding period tracking)

    Returns:
        NSOExerciseComponents containing all relevant data for tax calculation
    """
    exercise_cost = shares_to_exercise * strike_price
    bargain_element = shares_to_exercise * max(0, current_fmv - strike_price)

    return NSOExerciseComponents(
        lot_id=lot_id,
        exercise_date=exercise_date,
        shares_exercised=shares_to_exercise,
        strike_price=strike_price,
        fmv_at_exercise=current_fmv,
        exercise_cost=exercise_cost,
        bargain_element=bargain_element,
        grant_date=grant_date
    )


def format_tax_estimate(estimate: TaxEstimate) -> str:
    """Format tax estimate for display."""
    lines = []
    lines.append("ISO Exercise Tax Estimate")
    lines.append("=" * 50)
    lines.append(f"Shares Exercised: {estimate.shares_exercised:,}")
    lines.append(f"Exercise Cost: ${estimate.exercise_cost:,.0f}")
    lines.append(f"Bargain Element: ${estimate.bargain_element:,.0f}")
    lines.append("")

    lines.append("Federal Tax Impact:")
    lines.append(f"  Regular Tax: ${estimate.federal_regular_tax:,.0f}")
    lines.append(f"  AMT: ${estimate.federal_amt:,.0f}")
    lines.append(f"  AMT Applies: {'Yes' if estimate.federal_is_amt else 'No'}")
    if estimate.federal_is_amt:
        lines.append(f"  AMT Credit Generated: ${estimate.federal_amt_credit:,.0f}")
    lines.append(f"  Federal Total: ${estimate.federal_total:,.0f}")
    lines.append("")

    if estimate.ca_total > 0:
        lines.append("California Tax Impact:")
        lines.append(f"  Regular Tax: ${estimate.ca_regular_tax:,.0f}")
        lines.append(f"  AMT: ${estimate.ca_amt:,.0f}")
        lines.append(f"  AMT Applies: {'Yes' if estimate.ca_is_amt else 'No'}")
        lines.append(f"  CA Total: ${estimate.ca_total:,.0f}")
        lines.append("")

    lines.append("Summary:")
    lines.append(f"  Total Tax: ${estimate.total_tax:,.0f}")
    lines.append(f"  Additional Tax from Exercise: ${estimate.additional_tax_from_exercise:,.0f}")
    lines.append(f"  Effective Tax Rate: {estimate.effective_rate:.1%}")
    lines.append(f"  Total Cash Needed: ${estimate.total_cash_needed:,.0f}")

    return "\n".join(lines)
