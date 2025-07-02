"""
Annual Tax Calculator - Computes actual tax liability from aggregated components.

This calculator takes tax components from individual actions (exercises, sales, donations)
and computes the actual annual tax liability. This is where tax brackets, AMT determination,
and charitable deduction limits are applied.

This separation enables proper tax calculation at the annual level while maintaining
composability of individual action calculations.
"""

from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from decimal import Decimal

from calculators.components import (
    ISOExerciseComponents,
    NSOExerciseComponents,
    ShareSaleComponents,
    DonationComponents,
    CashDonationComponents,
    AnnualTaxComponents
)
from projections.projection_state import UserProfile

# Import tax constants from centralized module
from calculators.tax_constants import (
    FEDERAL_TAX_BRACKETS,
    FEDERAL_STANDARD_DEDUCTION,
    FEDERAL_LTCG_BRACKETS,
    CALIFORNIA_TAX_BRACKETS,
    CALIFORNIA_STANDARD_DEDUCTION,
    CALIFORNIA_AMT_EXEMPTION,
    CALIFORNIA_AMT_RATE,
    CALIFORNIA_AMT_PHASEOUT_START,
    CALIFORNIA_AMT_PHASEOUT_RATE,
    FEDERAL_CHARITABLE_AGI_LIMITS,
    CALIFORNIA_CHARITABLE_AGI_LIMITS,
    FEDERAL_CHARITABLE_BASIS_ELECTION_AGI_LIMITS,
    CALIFORNIA_CHARITABLE_BASIS_ELECTION_AGI_LIMITS,
    CHARITABLE_CARRYFORWARD_YEARS,
    CHARITABLE_50PCT_ORG_OVERALL_LIMIT,
    MEDICARE_RATE,
    ADDITIONAL_MEDICARE_THRESHOLD,
    SOCIAL_SECURITY_WAGE_BASE
)

# Import AMT calculation functions
from calculators.amt_calculator import (
    calculate_amt_for_annual_tax,
    calculate_tax_from_brackets
)


def calculate_california_tax_from_brackets(income: float, brackets: list) -> float:
    """
    Calculate tax using California-style progressive tax brackets.

    California brackets are in format (lower, upper, rate) unlike federal
    brackets which are in format (threshold, rate).

    Args:
        income: Taxable income
        brackets: List of (lower, upper, rate) tuples

    Returns:
        Total tax owed
    """
    if income <= 0:
        return 0.0

    tax = 0.0
    for lower, upper, rate in brackets:
        if income > lower:
            taxable_amount = min(upper, income) - lower
            tax += taxable_amount * rate
            if income <= upper:
                break

    return tax


@dataclass
class CharitableDeductionResult:
    """Result of applying charitable deduction limits."""
    cash_deduction_used: float
    stock_deduction_used: float
    total_deduction_used: float
    cash_carryforward: float
    stock_carryforward: float
    total_carryforward: float
    # FIFO tracking for stock: creation_year -> amount consumed (for CSV display)
    carryforward_consumed_by_creation_year: Dict[int, float] = field(default_factory=dict)
    # FIFO tracking for stock: creation_year -> amount remaining (for CSV display)
    carryforward_remaining_by_creation_year: Dict[int, float] = field(default_factory=dict)
    # FIFO tracking for cash: creation_year -> amount remaining
    cash_carryforward_remaining_by_creation_year: Dict[int, float] = field(default_factory=dict)
    # Expiration tracking: total amount that expired this year
    expired_carryforward: float = 0.0
    expired_cash_carryforward: float = 0.0

    # NEW: Explicit IRS ordering breakdown
    cash_current_used: float = 0.0
    stock_current_used: float = 0.0
    cash_carryforward_used: float = 0.0
    stock_carryforward_used: float = 0.0


@dataclass
class AnnualTaxResult:
    """Comprehensive annual tax calculation results."""
    year: int

    # Income breakdown
    w2_income: float
    spouse_income: float
    other_ordinary_income: float
    short_term_capital_gains: float
    long_term_capital_gains: float
    total_ordinary_income: float
    total_capital_gains: float
    adjusted_gross_income: float

    # Federal tax calculation
    federal_taxable_income: float
    federal_regular_tax: float
    federal_amt_income: float
    federal_amt: float
    federal_is_amt: bool
    federal_tax_owed: float
    federal_amt_credit_generated: float
    federal_amt_credit_used: float
    federal_amt_credit_carryforward: float

    # California tax calculation
    ca_taxable_income: float
    ca_regular_tax: float
    ca_amt_income: float
    ca_amt: float
    ca_is_amt: bool
    ca_tax_owed: float
    # TODO: Add CA AMT credit tracking (ca_amt_credit_generated, ca_amt_credit_used, ca_amt_credit_carryforward)
    # California does have AMT credits similar to federal - if you pay CA AMT in one year,
    # you can use it as a credit against regular tax in future years when not in AMT.
    # Implementation would require:
    # 1. Tracking CA AMT credits separately from federal
    # 2. CA-specific credit usage rules (different from federal)
    # 3. Multi-year carryforward tracking for CA
    # Note: Only implement when a real use case requires CA AMT credit tracking

    # Combined results
    total_tax: float
    effective_tax_rate: float
    marginal_tax_rate: float

    # Deductions
    charitable_deduction_result: CharitableDeductionResult  # Federal charitable deductions
    ca_charitable_deduction_result: CharitableDeductionResult  # California charitable deductions
    standard_deduction_used: float

    # Component tracking
    exercise_components: List[ISOExerciseComponents] = field(default_factory=list)
    sale_components: List[ShareSaleComponents] = field(default_factory=list)
    donation_components: List[DonationComponents] = field(default_factory=list)
    cash_donation_components: List[CashDonationComponents] = field(default_factory=list)


class AnnualTaxCalculator:
    """
    Calculates actual annual tax liability from aggregated components.

    This calculator performs the actual tax computation that can only be done
    at the annual level, including:
    - Applying tax brackets to total income
    - Calculating AMT vs regular tax
    - Applying charitable deduction AGI limits
    - Determining effective and marginal tax rates
    """

    # Federal charitable deduction AGI limits - using centralized constants
    FEDERAL_AGI_LIMIT_CASH = FEDERAL_CHARITABLE_AGI_LIMITS['cash']  # 60% for cash donations (2025)
    FEDERAL_AGI_LIMIT_STOCK = FEDERAL_CHARITABLE_AGI_LIMITS['stock']  # 30% for appreciated stock
    FEDERAL_AGI_LIMIT_STOCK_BASIS_ELECTION = FEDERAL_CHARITABLE_BASIS_ELECTION_AGI_LIMITS['stock']  # 50% with basis election

    # California charitable deduction AGI limits
    CA_AGI_LIMIT_CASH = CALIFORNIA_CHARITABLE_AGI_LIMITS['cash']  # 50% for cash donations
    CA_AGI_LIMIT_STOCK = CALIFORNIA_CHARITABLE_AGI_LIMITS['stock']  # 30% for appreciated stock
    CA_AGI_LIMIT_STOCK_BASIS_ELECTION = CALIFORNIA_CHARITABLE_BASIS_ELECTION_AGI_LIMITS['stock']  # 50% with basis election

    def calculate_annual_tax(
        self,
        year: int,
        user_profile: UserProfile,
        w2_income: float = 0,
        spouse_income: float = 0,
        other_ordinary_income: float = 0,
        exercise_components: List[ISOExerciseComponents] = None,
        nso_exercise_components: List[NSOExerciseComponents] = None,
        sale_components: List[ShareSaleComponents] = None,
        donation_components: List[DonationComponents] = None,
        cash_donation_components: List[CashDonationComponents] = None,
        filing_status: Optional[str] = None,
        include_california: Optional[bool] = None,
        existing_amt_credit: float = 0,
        carryforward_cash_deduction: float = 0,
        carryforward_stock_deduction: float = 0,
        carryforward_cash_by_creation_year: Optional[Dict[int, float]] = None,
        carryforward_stock_by_creation_year: Optional[Dict[int, float]] = None,
        ca_carryforward_cash_deduction: float = 0,
        ca_carryforward_stock_deduction: float = 0,
        ca_carryforward_cash_by_creation_year: Optional[Dict[int, float]] = None,
        ca_carryforward_stock_by_creation_year: Optional[Dict[int, float]] = None,
        elect_basis_deduction: bool = False,
        fifty_pct_limit_org: bool = True
    ) -> AnnualTaxResult:
        """
        Calculate comprehensive annual tax from components.

        Args:
            year: Tax year
            user_profile: User profile with tax rates and filing status
            w2_income: W-2 wages
            spouse_income: Spouse's W-2 income
            other_ordinary_income: Interest, dividends, etc.
            exercise_components: ISO exercises this year
            nso_exercise_components: NSO exercises this year
            sale_components: Share sales this year
            donation_components: Share donations this year
            cash_donation_components: Cash donations this year
            filing_status: Override filing status (uses profile if None)
            include_california: Override CA tax inclusion (uses profile if None)
            existing_amt_credit: AMT credit from prior years
            carryforward_cash_deduction: Charitable cash deduction carryforward (legacy - use carryforward_cash_by_creation_year for FIFO)
            carryforward_stock_deduction: Charitable stock deduction carryforward (legacy - use carryforward_stock_by_creation_year for FIFO)
            carryforward_cash_by_creation_year: Federal cash carryforward by creation year for FIFO compliance
            carryforward_stock_by_creation_year: Federal stock carryforward by creation year for FIFO compliance
            ca_carryforward_cash_by_creation_year: CA cash carryforward by creation year for FIFO compliance
            ca_carryforward_stock_by_creation_year: CA stock carryforward by creation year for FIFO compliance
            elect_basis_deduction: If True, use cost basis instead of FMV for stock donations (To raise donation AGI limit)
            fifty_pct_limit_org: If True, donations are to 50% limit organizations (public charities). If False, donations are to 30% limit organizations (private foundations).

        Returns:
            AnnualTaxResult with comprehensive tax calculation
        """
        # Initialize component lists
        exercise_components = exercise_components or []
        nso_exercise_components = nso_exercise_components or []
        sale_components = sale_components or []
        donation_components = donation_components or []
        cash_donation_components = cash_donation_components or []



        # Use profile values if not overridden
        if filing_status is None:
            filing_status = user_profile.filing_status
        if include_california is None:
            include_california = user_profile.state_of_residence.lower() == 'california'

        # Aggregate income components
        ordinary_income, cap_gains = self._aggregate_income_components(
            w2_income, spouse_income, other_ordinary_income,
            exercise_components, nso_exercise_components, sale_components
        )

        total_ordinary = ordinary_income['total']
        short_term_gains = cap_gains['short_term']
        long_term_gains = cap_gains['long_term']
        total_gains = short_term_gains + long_term_gains

        # Calculate AGI
        agi = total_ordinary + total_gains

        # Handle backward compatibility for legacy carryforward parameters
        if carryforward_stock_by_creation_year is None and carryforward_stock_deduction > 0:
            # Convert legacy format to new format - assume current year creation for backward compatibility
            carryforward_stock_by_creation_year = {year: carryforward_stock_deduction}
        elif carryforward_stock_by_creation_year is None:
            carryforward_stock_by_creation_year = {}

        if ca_carryforward_stock_by_creation_year is None and ca_carryforward_stock_deduction > 0:
            # Convert legacy format to new format - assume current year creation for backward compatibility
            ca_carryforward_stock_by_creation_year = {year: ca_carryforward_stock_deduction}
        elif ca_carryforward_stock_by_creation_year is None:
            ca_carryforward_stock_by_creation_year = {}

        # Calculate federal charitable deductions with federal AGI limits using FIFO
        federal_deduction_result = self._apply_charitable_deduction_limits(
            agi, donation_components, cash_donation_components,
            carryforward_cash_by_creation_year, carryforward_stock_by_creation_year,
            cash_limit_pct=self.FEDERAL_AGI_LIMIT_CASH,
            stock_limit_pct=self.FEDERAL_AGI_LIMIT_STOCK_BASIS_ELECTION if elect_basis_deduction else self.FEDERAL_AGI_LIMIT_STOCK,
            elect_basis_deduction=elect_basis_deduction,
            fifty_pct_limit_org=fifty_pct_limit_org,
            current_year=year
        )

        # Calculate California charitable deductions with California AGI limits using FIFO
        ca_deduction_result = self._apply_charitable_deduction_limits(
            agi, donation_components, cash_donation_components,
            ca_carryforward_cash_by_creation_year, ca_carryforward_stock_by_creation_year,
            cash_limit_pct=self.CA_AGI_LIMIT_CASH,
            stock_limit_pct=self.CA_AGI_LIMIT_STOCK_BASIS_ELECTION if elect_basis_deduction else self.CA_AGI_LIMIT_STOCK,
            elect_basis_deduction=elect_basis_deduction,
            fifty_pct_limit_org=fifty_pct_limit_org,
            current_year=year
        )

        # Calculate federal tax
        federal_result = self._calculate_federal_tax(
            ordinary_income, cap_gains, exercise_components,
            federal_deduction_result.total_deduction_used,
            filing_status, user_profile, existing_amt_credit
        )

        # Calculate California tax if applicable
        if include_california:
            ca_result = self._calculate_california_tax(
                ordinary_income, cap_gains, exercise_components,
                ca_deduction_result.total_deduction_used,
                filing_status
            )
        else:
            ca_result = {
                'taxable_income': 0,
                'regular_tax': 0,
                'amt_income': 0,
                'amt': 0,
                'is_amt': False,
                'tax_owed': 0
            }

        # Calculate total tax and rates
        total_tax = federal_result['tax_owed'] + ca_result['tax_owed']
        effective_rate = total_tax / agi if agi > 0 else 0.0

        # Estimate marginal rate (simplified - would need more logic for accuracy)
        marginal_rate = self._estimate_marginal_rate(
            total_ordinary, filing_status, include_california, user_profile
        )

        return AnnualTaxResult(
            year=year,
            # Income breakdown
            w2_income=w2_income,
            spouse_income=spouse_income,
            other_ordinary_income=other_ordinary_income,
            short_term_capital_gains=short_term_gains,
            long_term_capital_gains=long_term_gains,
            total_ordinary_income=total_ordinary,
            total_capital_gains=total_gains,
            adjusted_gross_income=agi,
            # Federal tax
            federal_taxable_income=federal_result['taxable_income'],
            federal_regular_tax=federal_result['regular_tax'],
            federal_amt_income=federal_result['amt_income'],
            federal_amt=federal_result['amt'],
            federal_is_amt=federal_result['is_amt'],
            federal_tax_owed=federal_result['tax_owed'],
            federal_amt_credit_generated=federal_result['amt_credit_generated'],
            federal_amt_credit_used=federal_result['amt_credit_used'],
            federal_amt_credit_carryforward=federal_result['amt_credit_carryforward'],
            # California tax
            ca_taxable_income=ca_result['taxable_income'],
            ca_regular_tax=ca_result['regular_tax'],
            ca_amt_income=ca_result['amt_income'],
            ca_amt=ca_result['amt'],
            ca_is_amt=ca_result['is_amt'],
            ca_tax_owed=ca_result['tax_owed'],
            # Combined results
            total_tax=total_tax,
            effective_tax_rate=effective_rate,
            marginal_tax_rate=marginal_rate,
            # Deductions (both federal and state)
            charitable_deduction_result=federal_deduction_result,
            ca_charitable_deduction_result=ca_deduction_result,
            standard_deduction_used=FEDERAL_STANDARD_DEDUCTION[filing_status],
            # Components
            exercise_components=exercise_components,
            sale_components=sale_components,
            donation_components=donation_components,
            cash_donation_components=cash_donation_components
        )

    def _aggregate_income_components(
        self,
        w2_income: float,
        spouse_income: float,
        other_ordinary_income: float,
        exercise_components: List[ISOExerciseComponents],
        nso_exercise_components: List[NSOExerciseComponents],
        sale_components: List[ShareSaleComponents]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Aggregate income from all sources."""
        # Ordinary income
        nso_income = sum(e.bargain_element for e in nso_exercise_components)
        ordinary = {
            'w2': w2_income,
            'spouse': spouse_income,
            'other': other_ordinary_income,
            'nso_exercises': nso_income,
            'disqualifying_dispositions': sum(s.ordinary_income for s in sale_components),
            'total': w2_income + spouse_income + other_ordinary_income + nso_income +
                    sum(s.ordinary_income for s in sale_components)
        }

        # Capital gains
        cap_gains = {
            'short_term': sum(s.short_term_gain for s in sale_components),
            'long_term': sum(s.long_term_gain for s in sale_components),
            'iso_bargain_element': sum(e.bargain_element for e in exercise_components)
        }

        return ordinary, cap_gains

    def _apply_charitable_deduction_limits(
        self,
        agi: float,
        donation_components: List[DonationComponents],
        cash_donation_components: List[CashDonationComponents],
        carryforward_cash_by_creation_year: Optional[Dict[int, float]],
        carryforward_stock_by_creation_year: Optional[Dict[int, float]],
        cash_limit_pct: float = None,
        stock_limit_pct: float = None,
        elect_basis_deduction: bool = False,
        fifty_pct_limit_org: bool = True,
        current_year: int = None
    ) -> CharitableDeductionResult:
        """Apply AGI limits to charitable deductions with FIFO ordering.

        Args:
            agi: Adjusted gross income
            donation_components: Stock donations
            cash_donation_components: Cash donations
            carryforward_cash_by_creation_year: Cash donation carryforward by creation year for FIFO
            carryforward_stock_by_creation_year: Stock donation carryforward by creation year for FIFO
            cash_limit_pct: Cash donation AGI limit percentage (required if cash donations > 0)
            stock_limit_pct: Stock donation AGI limit percentage (required if stock donations > 0)
            elect_basis_deduction: If True, use cost basis instead of FMV for stock donations
            fifty_pct_limit_org: If True, donations are to 50% limit organizations (public charities).
                                For these organizations: cash gets 60% of AGI limit, stock gets 30% of AGI limit,
                                but stock deductions are further limited by (50% of AGI - cash deductions used)
            current_year: Current tax year for expiration checking
        """
        # Calculate total donations by type
        if elect_basis_deduction:
            # When electing basis, use cost basis for deduction amount
            # This provides access to higher AGI limit (50% vs 30%) for carryforward optimization
            basis_total = sum(d.cost_basis * d.shares_donated for d in donation_components)
            fmv_total = sum(d.donation_value for d in donation_components)
            stock_donations = basis_total


        else:
            # Default: use FMV (donation_value)
            stock_donations = sum(d.donation_value for d in donation_components)

        cash_donations = sum(d.amount for d in cash_donation_components)

        # Handle None carryforward dictionaries - convert to empty dict for processing
        if carryforward_cash_by_creation_year is None:
            carryforward_cash_by_creation_year = {}
        if carryforward_stock_by_creation_year is None:
            carryforward_stock_by_creation_year = {}



        # Don't expire carryforwards before processing - they can be used in their 5th year
        # Expiration happens AFTER consumption, not before

        # Calculate total available
        total_cash_carryforward = sum(carryforward_cash_by_creation_year.values())
        total_stock_carryforward = sum(carryforward_stock_by_creation_year.values())
        total_cash_available = cash_donations + total_cash_carryforward
        total_stock_available = stock_donations + total_stock_carryforward



        # Require limits to be set if donations exist
        if total_cash_available > 0 and cash_limit_pct is None:
            raise ValueError("cash_limit_pct must be provided when cash donations > 0")
        if total_stock_available > 0 and stock_limit_pct is None:
            raise ValueError("stock_limit_pct must be provided when stock donations > 0")

        # Set default limits to 0 if no donations (to avoid multiplication by None)
        if cash_limit_pct is None:
            cash_limit_pct = 0.0
        if stock_limit_pct is None:
            stock_limit_pct = 0.0

        # Apply AGI limits
        stock_limit = agi * stock_limit_pct
        cash_limit = agi * cash_limit_pct



        # Apply explicit IRS ordering: current year before carryforward, cash before stock

        # Step 1: Current year cash donations (up to cash limit)
        cash_current_used = min(cash_donations, cash_limit)
        remaining_cash_limit = cash_limit - cash_current_used

        # Step 2: Cash carryforward with FIFO ordering (up to remaining cash limit)
        cash_carryforward_used = 0.0
        cash_carryforward_consumed_by_creation_year = {}
        cash_carryforward_remaining_by_creation_year = {}
        
        # Use cash carryforward in FIFO order (oldest first)
        for creation_year in sorted(carryforward_cash_by_creation_year.keys()):
            if remaining_cash_limit <= 0:
                # No more limit available, carry forward the rest
                cash_carryforward_remaining_by_creation_year[creation_year] = carryforward_cash_by_creation_year[creation_year]
                continue
                
            available_from_year = carryforward_cash_by_creation_year[creation_year]
            used_from_year = min(available_from_year, remaining_cash_limit)
            
            if used_from_year > 0:
                cash_carryforward_consumed_by_creation_year[creation_year] = used_from_year
                cash_carryforward_used += used_from_year
                remaining_cash_limit -= used_from_year
                
            remaining_from_year = available_from_year - used_from_year
            if remaining_from_year > 0:
                cash_carryforward_remaining_by_creation_year[creation_year] = remaining_from_year

        # Calculate total cash used
        cash_used = cash_current_used + cash_carryforward_used

        # Step 3: Current year stock donations (up to stock limit)
        # For 50% limit organizations, also apply overall charitable limit
        if fifty_pct_limit_org and (cash_donations > 0 or stock_donations > 0):
            # Total donations to 50% orgs cannot exceed 50% of AGI
            overall_limit = agi * CHARITABLE_50PCT_ORG_OVERALL_LIMIT
            remaining_overall_after_cash = max(0, overall_limit - cash_used)  # Use total cash, not just current
            effective_stock_limit = min(stock_limit, remaining_overall_after_cash)
        else:
            effective_stock_limit = stock_limit

        stock_current_used = min(stock_donations, effective_stock_limit)
        remaining_stock_limit = stock_limit - stock_current_used

        # Step 4: Stock carryforward with FIFO ordering (up to remaining stock limit)
        # For 50% limit organizations, also check overall limit
        if fifty_pct_limit_org and (cash_donations > 0 or stock_donations > 0 or total_cash_carryforward > 0 or total_stock_carryforward > 0):
            overall_limit = agi * CHARITABLE_50PCT_ORG_OVERALL_LIMIT
            total_used_so_far = cash_used + stock_current_used  # Use total cash (current + carryforward)
            remaining_overall = max(0, overall_limit - total_used_so_far)
            effective_stock_limit = min(remaining_stock_limit, remaining_overall)
        else:
            effective_stock_limit = remaining_stock_limit



        # Track stock usage
        stock_used = stock_current_used
        stock_carryforward_used = 0.0
        carryforward_consumed_by_creation_year = {}
        carryforward_remaining_by_creation_year = {}

        # Use carryforward in FIFO order (oldest first) with effective stock limit
        # Note: Carryforwards can be used in their 5th year before expiring


        for creation_year in sorted(carryforward_stock_by_creation_year.keys()):
            if effective_stock_limit <= 0:
                # No more limit available, carry forward the rest
                carryforward_remaining_by_creation_year[creation_year] = carryforward_stock_by_creation_year[creation_year]

                continue

            available_from_year = carryforward_stock_by_creation_year[creation_year]
            used_from_year = min(available_from_year, effective_stock_limit)



            if used_from_year > 0:
                carryforward_consumed_by_creation_year[creation_year] = used_from_year
                stock_used += used_from_year
                stock_carryforward_used += used_from_year
                effective_stock_limit -= used_from_year


            remaining_from_year = available_from_year - used_from_year
            if remaining_from_year > 0:
                carryforward_remaining_by_creation_year[creation_year] = remaining_from_year

        # Apply expiration AFTER consumption - carryforwards expire at end of their 5th year
        # Handle cash expiration
        expired_cash_amount = 0.0
        if current_year is not None:
            for creation_year in list(cash_carryforward_remaining_by_creation_year.keys()):
                years_since_creation = current_year - creation_year
                amount = cash_carryforward_remaining_by_creation_year[creation_year]

                if years_since_creation >= CHARITABLE_CARRYFORWARD_YEARS:
                    expired_cash_amount += amount
                    del cash_carryforward_remaining_by_creation_year[creation_year]

        # Handle stock expiration
        expired_stock_amount = 0.0
        expired_carryforward = {}
        if current_year is not None:
            for creation_year in list(carryforward_remaining_by_creation_year.keys()):
                years_since_creation = current_year - creation_year
                amount = carryforward_remaining_by_creation_year[creation_year]

                if years_since_creation >= CHARITABLE_CARRYFORWARD_YEARS:
                    expired_carryforward[creation_year] = amount
                    expired_stock_amount += amount
                    del carryforward_remaining_by_creation_year[creation_year]

        # Add unused current year donations to carryforward tracking
        unused_current_year_cash = cash_donations - cash_current_used
        if unused_current_year_cash > 0:
            cash_carryforward_remaining_by_creation_year[current_year] = unused_current_year_cash
            
        unused_current_year_stock = stock_donations - stock_current_used
        if unused_current_year_stock > 0:
            carryforward_remaining_by_creation_year[current_year] = unused_current_year_stock

        # Calculate total carryforwards
        cash_carryforward = sum(cash_carryforward_remaining_by_creation_year.values())
        stock_carryforward = sum(carryforward_remaining_by_creation_year.values())



        return CharitableDeductionResult(
            cash_deduction_used=cash_used,
            stock_deduction_used=stock_used,
            total_deduction_used=cash_used + stock_used,
            cash_carryforward=cash_carryforward,
            stock_carryforward=stock_carryforward,
            total_carryforward=cash_carryforward + stock_carryforward,
            carryforward_consumed_by_creation_year=carryforward_consumed_by_creation_year,
            carryforward_remaining_by_creation_year=carryforward_remaining_by_creation_year,
            cash_carryforward_remaining_by_creation_year=cash_carryforward_remaining_by_creation_year,
            expired_carryforward=expired_stock_amount,
            expired_cash_carryforward=expired_cash_amount,
            # NEW: Explicit IRS ordering breakdown
            cash_current_used=cash_current_used,
            stock_current_used=stock_current_used,
            cash_carryforward_used=cash_carryforward_used,
            stock_carryforward_used=stock_carryforward_used
        )

    def _calculate_federal_tax(
        self,
        ordinary_income: Dict[str, float],
        cap_gains: Dict[str, float],
        exercise_components: List[ISOExerciseComponents],
        charitable_deduction: float,
        filing_status: str,
        user_profile: UserProfile,
        existing_amt_credit: float
    ) -> Dict[str, float]:
        """Calculate federal tax including AMT."""
        total_ordinary = ordinary_income['total']
        total_cap_gains = cap_gains['short_term'] + cap_gains['long_term']

        # Regular tax calculation
        agi = total_ordinary + total_cap_gains
        taxable_income = max(0, agi - FEDERAL_STANDARD_DEDUCTION[filing_status] - charitable_deduction)

        # Calculate regular tax on ordinary income and STCG
        ordinary_taxable = max(0, total_ordinary + cap_gains['short_term'] -
                              FEDERAL_STANDARD_DEDUCTION[filing_status] - charitable_deduction)
        regular_tax_on_ordinary = calculate_tax_from_brackets(
            ordinary_taxable, FEDERAL_TAX_BRACKETS[filing_status]
        )

        # Calculate LTCG tax using brackets
        # LTCG stacks on top of ordinary income for bracket determination
        ltcg_tax = self._calculate_federal_ltcg_tax(
            ordinary_income=ordinary_taxable,
            ltcg_amount=cap_gains['long_term'],
            filing_status=filing_status
        )
        regular_tax = regular_tax_on_ordinary + ltcg_tax

        # AMT calculation using centralized AMT calculator
        amt_result = calculate_amt_for_annual_tax(
            agi=agi,
            iso_bargain_element=cap_gains['iso_bargain_element'],
            filing_status=filing_status,
            existing_amt_credit=existing_amt_credit,
            regular_tax_before_credits=regular_tax
        )

        amt_income = amt_result['amt_income']
        amt = amt_result['amt']
        is_amt = amt_result['is_amt']
        tax_owed = amt_result['tax_owed']
        amt_credit_generated = amt_result['amt_credit_generated']
        amt_credit_used = amt_result['amt_credit_used']
        amt_credit_carryforward = amt_result['amt_credit_carryforward']

        return {
            'taxable_income': taxable_income,
            'regular_tax': regular_tax,
            'amt_income': amt_income,
            'amt': amt,
            'is_amt': is_amt,
            'tax_owed': tax_owed,
            'amt_credit_generated': amt_credit_generated,
            'amt_credit_used': amt_credit_used,
            'amt_credit_carryforward': amt_credit_carryforward
        }

    def _calculate_california_tax(
        self,
        ordinary_income: Dict[str, float],
        cap_gains: Dict[str, float],
        exercise_components: List[ISOExerciseComponents],
        charitable_deduction: float,
        filing_status: str
    ) -> Dict[str, float]:
        """Calculate California tax including AMT."""
        total_ordinary = ordinary_income['total']
        total_cap_gains = cap_gains['short_term'] + cap_gains['long_term']

        # Regular CA tax
        ca_agi = total_ordinary + total_cap_gains
        ca_taxable_income = max(0, ca_agi - CALIFORNIA_STANDARD_DEDUCTION[filing_status] - charitable_deduction)
        ca_regular_tax = calculate_california_tax_from_brackets(
            ca_taxable_income, CALIFORNIA_TAX_BRACKETS[filing_status]
        )

        # CA AMT
        ca_amt_income = ca_agi + cap_gains['iso_bargain_element']
        ca_amt_exemption = CALIFORNIA_AMT_EXEMPTION[filing_status]

        # Apply phaseout
        if ca_amt_income > CALIFORNIA_AMT_PHASEOUT_START[filing_status]:
            ca_amt_exemption -= (ca_amt_income - CALIFORNIA_AMT_PHASEOUT_START[filing_status]) * CALIFORNIA_AMT_PHASEOUT_RATE
            ca_amt_exemption = max(0, ca_amt_exemption)

        ca_amt = max(0, ca_amt_income - ca_amt_exemption) * CALIFORNIA_AMT_RATE
        is_ca_amt = ca_amt > ca_regular_tax
        ca_tax_owed = max(ca_regular_tax, ca_amt)

        return {
            'taxable_income': ca_taxable_income,
            'regular_tax': ca_regular_tax,
            'amt_income': ca_amt_income,
            'amt': ca_amt,
            'is_amt': is_ca_amt,
            'tax_owed': ca_tax_owed
        }

    def _calculate_federal_ltcg_tax(
        self,
        ordinary_income: float,
        ltcg_amount: float,
        filing_status: str
    ) -> float:
        """
        Calculate federal long-term capital gains tax using brackets.

        LTCG tax rates depend on total taxable income (ordinary + LTCG).
        The LTCG "stacks" on top of ordinary income to determine the applicable rate.

        Args:
            ordinary_income: Taxable ordinary income (after deductions)
            ltcg_amount: Long-term capital gains amount
            filing_status: Tax filing status

        Returns:
            Total LTCG tax
        """
        if ltcg_amount <= 0:
            return 0.0

        ltcg_brackets = FEDERAL_LTCG_BRACKETS[filing_status]
        ltcg_tax = 0.0

        # Start from where ordinary income ends
        income_level = ordinary_income
        remaining_ltcg = ltcg_amount

        # Apply LTCG tax brackets
        for lower, upper, rate in ltcg_brackets:
            if income_level >= upper:
                # Already above this bracket, skip
                continue

            # Calculate how much LTCG falls in this bracket
            bracket_start = max(income_level, lower)
            bracket_room = upper - bracket_start
            ltcg_in_bracket = min(remaining_ltcg, bracket_room)

            if ltcg_in_bracket > 0:
                ltcg_tax += ltcg_in_bracket * rate
                remaining_ltcg -= ltcg_in_bracket
                income_level += ltcg_in_bracket

            if remaining_ltcg <= 0:
                break

        return ltcg_tax

    def _estimate_marginal_rate(
        self,
        ordinary_income: float,
        filing_status: str,
        include_california: bool,
        user_profile: UserProfile
    ) -> float:
        """Estimate marginal tax rate (simplified)."""
        # Find federal marginal bracket
        federal_marginal = 0.0
        for lower, upper, rate in FEDERAL_TAX_BRACKETS[filing_status]:
            if ordinary_income > lower:
                federal_marginal = rate
            if ordinary_income <= upper:
                break

        # Add CA marginal if applicable
        ca_marginal = 0.0
        if include_california:
            for lower, upper, rate in CALIFORNIA_TAX_BRACKETS[filing_status]:
                if ordinary_income > lower:
                    ca_marginal = rate
                if ordinary_income <= upper:
                    break

        # Calculate total marginal rate from components
        total_marginal = federal_marginal + ca_marginal

        # Add FICA/Medicare if income is below cap (simplified)
        # Above Social Security wage base (~$160k), only Medicare applies
        if ordinary_income < SOCIAL_SECURITY_WAGE_BASE:
            total_marginal += user_profile.fica_tax_rate
        else:
            total_marginal += MEDICARE_RATE  # Medicare portion only

        # Add additional Medicare tax for high earners
        if ordinary_income > ADDITIONAL_MEDICARE_THRESHOLD['single']:  # Single filer threshold
            total_marginal += user_profile.additional_medicare_rate

        return total_marginal
