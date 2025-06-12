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

# Import tax constants from ISO calculator
from calculators.iso_exercise_calculator import (
    FEDERAL_TAX_BRACKETS,
    FEDERAL_STANDARD_DEDUCTION,
    AMT_EXEMPTION_AMOUNT,
    AMT_PHASEOUT_THRESHOLD,
    AMT_THRESHOLD,
    AMT_RATE_LOW,
    AMT_RATE_HIGH,
    CA_TAX_BRACKETS,
    CA_STANDARD_DEDUCTION,
    CA_AMT_EXEMPTION,
    CA_AMT_RATE,
    CA_AMT_PHASEOUT_START,
    CA_AMT_PHASEOUT_RATE,
    calculate_tax_from_brackets
)

# Federal Long-Term Capital Gains Tax Brackets (2024)
FEDERAL_LTCG_BRACKETS = {
    'single': [
        (44625, 0.00),   # 0% bracket
        (492300, 0.15),  # 15% bracket
        (float('inf'), 0.20)  # 20% bracket
    ],
    'married_filing_jointly': [
        (89250, 0.00),   # 0% bracket
        (553850, 0.15),  # 15% bracket
        (float('inf'), 0.20)  # 20% bracket
    ],
    'married_filing_separately': [
        (44625, 0.00),   # 0% bracket
        (276900, 0.15),  # 15% bracket
        (float('inf'), 0.20)  # 20% bracket
    ],
    'head_of_household': [
        (59750, 0.00),   # 0% bracket
        (523050, 0.15),  # 15% bracket
        (float('inf'), 0.20)  # 20% bracket
    ]
}


@dataclass
class CharitableDeductionResult:
    """Result of applying charitable deduction limits."""
    cash_deduction_used: float
    stock_deduction_used: float
    total_deduction_used: float
    cash_carryforward: float
    stock_carryforward: float
    total_carryforward: float


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

    # Combined results
    total_tax: float
    effective_tax_rate: float
    marginal_tax_rate: float

    # Deductions
    charitable_deduction_result: CharitableDeductionResult
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

    # Charitable deduction AGI limits
    AGI_LIMIT_CASH = 0.50  # 50% for cash donations
    AGI_LIMIT_STOCK = 0.30  # 30% for appreciated stock #Claude TODO: Check if it's a bit redundant that we speficy this in both this calculator as well as the share_donation_calculator? are a bunch of the computations being redone multiple times?

    def calculate_annual_tax(
        self,
        year: int,
        user_profile: UserProfile,
        w2_income: float,
        spouse_income: float = 0.0,
        other_ordinary_income: float = 0.0,
        exercise_components: Optional[List[ISOExerciseComponents]] = None,
        nso_exercise_components: Optional[List[NSOExerciseComponents]] = None,
        sale_components: Optional[List[ShareSaleComponents]] = None,
        donation_components: Optional[List[DonationComponents]] = None,
        cash_donation_components: Optional[List[CashDonationComponents]] = None,
        filing_status: Optional[str] = None,
        include_california: Optional[bool] = None,
        existing_amt_credit: float = 0.0,
        carryforward_cash_deduction: float = 0.0,
        carryforward_stock_deduction: float = 0.0
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
            carryforward_cash_deduction: Charitable cash deduction carryforward
            carryforward_stock_deduction: Charitable stock deduction carryforward

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

        # Calculate charitable deductions with AGI limits
        deduction_result = self._apply_charitable_deduction_limits(
            agi, donation_components, cash_donation_components,
            carryforward_cash_deduction, carryforward_stock_deduction
        )

        # Calculate federal tax
        federal_result = self._calculate_federal_tax(
            ordinary_income, cap_gains, exercise_components,
            deduction_result.total_deduction_used,
            filing_status, user_profile, existing_amt_credit
        )

        # Calculate California tax if applicable
        if include_california:
            ca_result = self._calculate_california_tax(
                ordinary_income, cap_gains, exercise_components,
                deduction_result.total_deduction_used,
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
            # Deductions
            charitable_deduction_result=deduction_result,
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
        carryforward_cash: float,
        carryforward_stock: float
    ) -> CharitableDeductionResult:
        """Apply AGI limits to charitable deductions."""
        # Calculate total donations by type
        stock_donations = sum(d.donation_value for d in donation_components)
        cash_donations = sum(d.amount for d in cash_donation_components)

        # Add carryforwards
        total_stock_available = stock_donations + carryforward_stock
        total_cash_available = cash_donations + carryforward_cash

        # Apply AGI limits
        stock_limit = agi * self.AGI_LIMIT_STOCK
        cash_limit = agi * self.AGI_LIMIT_CASH

        # Stock deductions use 30% limit
        stock_used = min(total_stock_available, stock_limit)
        stock_carryforward = total_stock_available - stock_used

        # Cash deductions use 50% limit (minus any stock deductions)
        cash_limit_after_stock = max(0, cash_limit - stock_used)
        cash_used = min(total_cash_available, cash_limit_after_stock)
        cash_carryforward = total_cash_available - cash_used

        return CharitableDeductionResult(
            cash_deduction_used=cash_used,
            stock_deduction_used=stock_used,
            total_deduction_used=cash_used + stock_used,
            cash_carryforward=cash_carryforward,
            stock_carryforward=stock_carryforward,
            total_carryforward=cash_carryforward + stock_carryforward
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

        # AMT calculation
        amt_income = agi + cap_gains['iso_bargain_element']  # Add ISO bargain element

        # Calculate AMT exemption with phaseout
        exemption = AMT_EXEMPTION_AMOUNT[filing_status]
        phaseout_threshold = AMT_PHASEOUT_THRESHOLD[filing_status]

        if amt_income > phaseout_threshold:
            exemption_phaseout = (amt_income - phaseout_threshold) * 0.25
            exemption = max(exemption - exemption_phaseout, 0)

        amt_taxable_income = max(amt_income - exemption, 0)

        # Calculate AMT using two-tier rate structure
        if amt_taxable_income <= AMT_THRESHOLD:
            amt = amt_taxable_income * AMT_RATE_LOW
        else:
            amt = AMT_THRESHOLD * AMT_RATE_LOW + (amt_taxable_income - AMT_THRESHOLD) * AMT_RATE_HIGH

        # Apply existing AMT credit
        regular_tax_after_credit = max(0, regular_tax - existing_amt_credit)
        amt_credit_used = regular_tax - regular_tax_after_credit

        # Determine which tax applies
        is_amt = amt > regular_tax_after_credit
        tax_owed = max(amt, regular_tax_after_credit)
        amt_credit_generated = max(0, amt - regular_tax) if is_amt else 0

        # Calculate AMT credit carryforward
        amt_credit_carryforward = existing_amt_credit - amt_credit_used + amt_credit_generated

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
        ca_taxable_income = max(0, ca_agi - CA_STANDARD_DEDUCTION[filing_status] - charitable_deduction)
        ca_regular_tax = calculate_tax_from_brackets(
            ca_taxable_income, CA_TAX_BRACKETS[filing_status]
        )

        # CA AMT
        ca_amt_income = ca_agi + cap_gains['iso_bargain_element']
        ca_amt_exemption = CA_AMT_EXEMPTION[filing_status]

        # Apply phaseout
        if ca_amt_income > CA_AMT_PHASEOUT_START[filing_status]:
            ca_amt_exemption -= (ca_amt_income - CA_AMT_PHASEOUT_START[filing_status]) * CA_AMT_PHASEOUT_RATE
            ca_amt_exemption = max(0, ca_amt_exemption)

        ca_amt = max(0, ca_amt_income - ca_amt_exemption) * CA_AMT_RATE
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
        previous_threshold = 0
        for threshold, rate in ltcg_brackets:
            if income_level >= threshold:
                # Already above this bracket, skip
                previous_threshold = threshold
                continue

            # Calculate how much LTCG falls in this bracket
            bracket_room = threshold - max(income_level, previous_threshold)
            ltcg_in_bracket = min(remaining_ltcg, bracket_room)

            if ltcg_in_bracket > 0:
                ltcg_tax += ltcg_in_bracket * rate
                remaining_ltcg -= ltcg_in_bracket
                income_level += ltcg_in_bracket

            previous_threshold = threshold

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
            for lower, upper, rate in CA_TAX_BRACKETS[filing_status]:
                if ordinary_income > lower:
                    ca_marginal = rate
                if ordinary_income <= upper:
                    break

        # Calculate total marginal rate from components
        total_marginal = federal_marginal + ca_marginal

        # Add FICA/Medicare if income is below cap (simplified)
        # Above ~$160k, only Medicare applies
        if ordinary_income < 160000:
            total_marginal += user_profile.fica_tax_rate
        else:
            total_marginal += 0.0145  # Medicare portion only

        # Add additional Medicare tax for high earners
        if ordinary_income > 200000:  # Single filer threshold
            total_marginal += user_profile.additional_medicare_rate

        return total_marginal
