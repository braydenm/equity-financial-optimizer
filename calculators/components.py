"""
Component data structures for calculator results.

These dataclasses represent the tax components extracted from individual actions,
which are then aggregated annually for actual tax calculation. This separation
enables proper annual tax composition while maintaining calculator composability.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Dict, List
from enum import Enum


class DispositionType(Enum):
    """Type of share disposition for tax purposes."""
    QUALIFYING_ISO = "qualifying_iso"
    DISQUALIFYING_ISO = "disqualifying_iso"
    REGULAR_SALE = "regular_sale"
    DONATION = "donation"


@dataclass
class ISOExerciseComponents:
    """Components from ISO exercise for annual tax calculation."""
    # Exercise details
    lot_id: str
    exercise_date: date
    shares_exercised: int
    strike_price: float
    fmv_at_exercise: float

    # Cash flow
    exercise_cost: float

    # AMT components
    bargain_element: float  # FMV - strike price at exercise

    # For tracking
    grant_date: date  # Needed for qualifying disposition determination

    # NEW: Display fields for CSV export
    action_date: Optional[date] = None
    action_type: str = "exercise"
    calculator_name: str = "iso_exercise_calculator"

    def __post_init__(self):
        """Validate components."""
        if self.shares_exercised < 0:
            raise ValueError("Shares exercised cannot be negative")
        if self.strike_price < 0:
            raise ValueError("Strike price cannot be negative")
        if self.fmv_at_exercise < 0:
            raise ValueError("FMV cannot be negative")


@dataclass
class NSOExerciseComponents:
    """Components from NSO exercise for annual tax calculation."""
    # Exercise details
    lot_id: str
    exercise_date: date
    shares_exercised: int
    strike_price: float
    fmv_at_exercise: float

    # Cash flow
    exercise_cost: float

    # Ordinary income components
    bargain_element: float  # FMV - strike price at exercise (creates ordinary income)

    # For tracking
    grant_date: date  # Needed for holding period tracking

    # NEW: Display fields for CSV export
    action_date: Optional[date] = None
    action_type: str = "exercise"
    calculator_name: str = "nso_exercise_calculator"

    def __post_init__(self):
        """Validate components."""
        if self.shares_exercised < 0:
            raise ValueError("Shares exercised cannot be negative")
        if self.strike_price < 0:
            raise ValueError("Strike price cannot be negative")
        if self.fmv_at_exercise < 0:
            raise ValueError("FMV cannot be negative")


@dataclass
class ShareSaleComponents:
    """Components from share sale for annual tax calculation."""
    # Sale details
    lot_id: str
    sale_date: date
    shares_sold: int
    sale_price: float

    # Basis and proceeds
    cost_basis: float
    gross_proceeds: float

    # Holding period
    exercise_date: date
    holding_period_days: int

    # Disposition classification
    disposition_type: DispositionType

    # Capital gain components (mutually exclusive)
    short_term_gain: float = 0.0
    long_term_gain: float = 0.0
    ordinary_income: float = 0.0  # For disqualifying dispositions
    is_qualifying_disposition: Optional[bool] = None  # Only for ISOs

    # NEW: Display fields for CSV export
    action_date: Optional[date] = None
    action_type: str = "sell"
    calculator_name: str = "share_sale_calculator"
    tax_treatment: str = ""  # "STCG", "LTCG", "Qualifying", "Disqualifying"

    # For ISO disqualifying dispositions
    amt_adjustment_reversal: float = 0.0  # Reversal of previous AMT adjustment

    def __post_init__(self):
        """Validate components and enforce business rules."""
        if self.shares_sold < 0:
            raise ValueError("Shares sold cannot be negative")
        if self.sale_price < 0:
            raise ValueError("Sale price cannot be negative")

        # Validate gain types based on disposition type
        if self.disposition_type == DispositionType.DISQUALIFYING_ISO:
            # Disqualifying ISO dispositions can have:
            # 1. Only ordinary income (sale between strike and FMV at exercise)
            # 2. Ordinary income + capital gain (sale above FMV at exercise)
            # 3. Only capital loss (sale below strike price)
            capital_gains_count = sum(1 for g in [self.short_term_gain, self.long_term_gain] if g != 0)

            # Check for invalid combinations
            if capital_gains_count > 1:
                raise ValueError("Cannot have both short-term and long-term gains in same sale")

            # If there's a capital loss (negative gain), ordinary income should be 0
            if (self.short_term_gain < 0 or self.long_term_gain < 0) and self.ordinary_income > 0:
                raise ValueError("Cannot have ordinary income when selling at a loss")

            # If there's ordinary income and capital gain, both should be positive
            if self.ordinary_income > 0 and capital_gains_count > 0:
                if self.short_term_gain < 0 or self.long_term_gain < 0:
                    raise ValueError("Cannot mix ordinary income with capital losses")
        else:
            # Non-disqualifying dispositions should have at most one type of gain/loss
            gains_set = sum(1 for g in [self.short_term_gain, self.long_term_gain, self.ordinary_income] if g != 0)
            if gains_set > 1:
                raise ValueError("Non-disqualifying dispositions cannot have multiple types of gains or losses")


@dataclass
class DonationComponents:
    """Components from charitable donation for annual tax calculation."""
    # Donation details
    lot_id: str
    donation_date: date
    shares_donated: int
    fmv_at_donation: float

    # Basis (for deduction calculation)
    cost_basis: float
    exercise_date: date
    holding_period_days: int

    # Deduction components
    donation_value: float  # FMV for long-term, basis for short-term
    deduction_type: str  # 'stock' or 'cash'

    # Company match
    company_match_ratio: float = 0.0
    company_match_amount: float = 0.0

    # Pledge tracking
    pledge_amount_satisfied: float = 0.0
    pledge_id: Optional[str] = None

    # NEW: Display fields for CSV export
    action_date: Optional[date] = None
    action_type: str = "donate"
    calculator_name: str = "share_donation_calculator"

    def __post_init__(self):
        """Validate components."""
        if self.shares_donated < 0:
            raise ValueError("Shares donated cannot be negative")
        if self.fmv_at_donation < 0:
            raise ValueError("FMV cannot be negative")
        if self.company_match_ratio < 0:
            raise ValueError("Company match ratio cannot be negative")


@dataclass
class CashDonationComponents:
    """Components from cash charitable donation."""
    donation_date: date
    amount: float

    # Company match
    company_match_ratio: float = 0.0
    company_match_amount: float = 0.0

    # Pledge tracking
    pledge_amount_satisfied: float = 0.0
    pledge_id: Optional[str] = None

    # NEW: Display fields for CSV export
    action_date: Optional[date] = None
    action_type: str = "cash_donate"
    calculator_name: str = "cash_donation_calculator"


@dataclass
class AnnualTaxComponents:
    """Aggregated tax components for a single year."""
    year: int

    # Income components
    w2_income: float = 0.0
    spouse_income: float = 0.0
    other_ordinary_income: float = 0.0

    # Capital gains
    short_term_capital_gains: float = 0.0
    long_term_capital_gains: float = 0.0

    # AMT adjustments
    iso_bargain_element: float = 0.0

    # Deductions
    charitable_deductions_cash: float = 0.0
    charitable_deductions_stock: float = 0.0

    # Component lists
    iso_exercise_components: List[ISOExerciseComponents] = field(default_factory=list)
    nso_exercise_components: List[NSOExerciseComponents] = field(default_factory=list)
    sale_components: List[ShareSaleComponents] = field(default_factory=list)
    donation_components: List[DonationComponents] = field(default_factory=list)
    cash_donation_components: List[CashDonationComponents] = field(default_factory=list)

    @property
    def total_ordinary_income(self) -> float:
        """Calculate total ordinary income including disqualifying dispositions."""
        base_income = self.w2_income + self.spouse_income + self.other_ordinary_income
        disqualifying_income = sum(s.ordinary_income for s in self.sale_components)
        return base_income + disqualifying_income

    @property
    def total_capital_gains(self) -> float:
        """Calculate total capital gains."""
        return self.short_term_capital_gains + self.long_term_capital_gains

    @property
    def adjusted_gross_income(self) -> float:
        """Calculate AGI for deduction limits."""
        return self.total_ordinary_income + self.total_capital_gains

    def aggregate_components(self):
        """Aggregate all components into annual totals."""
        # Reset aggregates
        self.short_term_capital_gains = 0.0
        self.long_term_capital_gains = 0.0
        self.iso_bargain_element = 0.0
        self.charitable_deductions_stock = 0.0

        # Aggregate ISO exercises
        for exercise in self.iso_exercise_components:
            self.iso_bargain_element += exercise.bargain_element

        # Aggregate NSO exercises (adds to ordinary income)
        for exercise in self.nso_exercise_components:
            self.other_ordinary_income += exercise.bargain_element

        # Aggregate sales
        for sale in self.sale_components:
            self.short_term_capital_gains += sale.short_term_gain
            self.long_term_capital_gains += sale.long_term_gain

        # Aggregate donations
        for donation in self.donation_components:
            if donation.deduction_type == 'stock':
                self.charitable_deductions_stock += donation.donation_value

        # Aggregate cash donations
        for cash_donation in self.cash_donation_components:
            self.charitable_deductions_cash += cash_donation.amount
