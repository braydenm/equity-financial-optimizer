"""
Projection state models for multi-year equity scenario planning.

This module defines the data structures for tracking state across
multi-year projections including cash, taxes, equity holdings, and
donation obligations.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from decimal import Decimal
from enum import Enum
from calculators.tax_utils import calculate_iso_qualifying_disposition_date




class ShareType(Enum):
    """Types of equity shares."""
    ISO = "ISO"
    NSO = "NSO"
    RSU = "RSU"


class LifecycleState(Enum):
    """Current state of a share lot in its lifecycle."""
    GRANTED_NOT_VESTED = "granted_not_vested"
    VESTED_NOT_EXERCISED = "vested_not_exercised"
    EXERCISED_NOT_DISPOSED = "exercised_not_disposed"
    DISPOSED = "disposed"
    EXPIRED = "expired"


class TaxTreatment(Enum):
    """Tax treatment classification for shares."""
    LTCG = "LTCG"  # Long-term capital gains
    STCG = "STCG"  # Short-term capital gains
    DONATED = "donated"
    NA = "N/A"     # Not applicable (e.g., unexercised options)


class ActionType(Enum):
    """Types of actions that can be performed on equity."""
    EXERCISE = "exercise"
    SELL = "sell"
    DONATE = "donate"
    HOLD = "hold"
    VEST = "vest"


@dataclass
class ShareLot:
    """Individual lot of shares with specific characteristics."""
    lot_id: str
    share_type: ShareType
    quantity: int
    strike_price: float
    grant_date: date
    lifecycle_state: LifecycleState
    tax_treatment: TaxTreatment
    exercise_date: Optional[date] = None
    cost_basis: float = 0.0
    taxes_paid: float = 0.0
    amt_adjustment: float = 0.0
    fmv_at_exercise: Optional[float] = None  # Required for exercised lots, None for unexercised
    expiration_date: Optional[date] = None  # Expiration date for options
    grant_id: Optional[str] = None  # ID of the original grant this lot came from

    def __post_init__(self):
        """Validate ShareLot constraints after initialization."""
        # Unexercised options (ISO and NSO) must have expiration dates
        # Exercised options don't need expiration dates since they can't expire anymore
        if (self.share_type in [ShareType.ISO, ShareType.NSO] and
            self.expiration_date is None and
            self.lifecycle_state in [LifecycleState.GRANTED_NOT_VESTED, LifecycleState.VESTED_NOT_EXERCISED]):
            raise ValueError(
                f"ShareLot {self.lot_id}: Unexercised options (ISO/NSO) must have an expiration_date. "
                f"Share type {self.share_type.value} with lifecycle state {self.lifecycle_state.value} requires expiration_date to be set."
            )

        # Validate that options cannot expire before vesting
        if (self.share_type in [ShareType.ISO, ShareType.NSO] and
            self.expiration_date is not None and
            self.lot_id.startswith('VEST_')):
            try:
                # Extract vest date from lot ID (format: VEST_YYYYMMDD_TYPE)
                date_part = self.lot_id.split('_')[1]
                vest_date = date(int(date_part[:4]), int(date_part[4:6]), int(date_part[6:8]))

                # Ensure expiration is after vesting
                if self.expiration_date <= vest_date:
                    raise ValueError(
                        f"ShareLot {self.lot_id}: Options cannot expire before vesting. "
                        f"Vest date {vest_date} must be before expiration date {self.expiration_date}."
                    )
            except (IndexError, ValueError):
                # If we can't parse the date, skip this validation
                pass

    @property
    def iso_qualifying_date(self) -> Optional[date]:
        """Date when ISO shares become eligible for qualifying disposition."""
        if self.share_type != ShareType.ISO:
            return None
        if not self.exercise_date:
            return None
        return calculate_iso_qualifying_disposition_date(self.grant_date, self.exercise_date)


@dataclass
class PlannedAction:
    """An action planned to be taken on a specific date."""
    action_date: date
    action_type: ActionType
    lot_id: str
    quantity: int
    price: Optional[float] = None  # Price for sell/donate actions
    notes: str = ""


@dataclass
class TaxState:
    """Tax-related state for a given year."""
    regular_tax: float = 0.0
    amt_tax: float = 0.0
    total_tax: float = 0.0
    amt_credits_generated: float = 0.0
    amt_credits_used: float = 0.0
    amt_credits_remaining: float = 0.0

    # Separate federal/state components for detailed reporting
    federal_regular_tax: float = 0.0
    federal_amt_tax: float = 0.0
    ca_regular_tax: float = 0.0
    ca_amt_tax: float = 0.0


@dataclass
class CharitableDeductionState:
    """Charitable deduction state and carryforward tracking for both federal and state."""
    # Federal charitable deductions
    federal_current_year_deduction: float = 0.0
    federal_carryforward_remaining: Dict[int, float] = field(default_factory=dict)  # year -> amount
    federal_total_available: float = 0.0
    federal_expired_this_year: float = 0.0  # Amount that expired this year (lost tax benefit)

    # California charitable deductions
    ca_current_year_deduction: float = 0.0
    ca_carryforward_remaining: Dict[int, float] = field(default_factory=dict)  # year -> amount
    ca_total_available: float = 0.0
    ca_expired_this_year: float = 0.0      # Amount that expired this year (lost tax benefit)




@dataclass
class PledgeObligation:
    """Individual pledge obligation tracking from a specific tender/sale event."""
    parent_transaction_id: str  # Unique ID of the sale/tender that created this obligation
    commencement_date: Optional[date] = None  # Date when obligation was created (tender/sale date)
    match_window_closes: Optional[date] = None  # 3-year match window from commencement
    total_pledge_obligation: float = 0.0  # Total dollar obligation from pledge % of tender/sale proceeds
    donations_made: float = 0.0  # Total donations made toward this specific obligation
    shares_sold: int = 0  # Number of shares tendered/sold that created this obligation
    pledge_percentage: float = 0.5  # Pledge percentage (0.5 = 50%)
    maximalist_shares_donated: int = 0  # Number of shares actually donated toward this obligation
    outstanding_obligation: float = 0.0  # Remaining dollar obligation
    lost_match_opportunity: float = 0.0  # Forfeited company match value when window closes

    @property
    def match_eligibility_active(self) -> bool:
        """Check if company match window is still open."""
        if not self.match_window_closes:
            return True  # No window means always eligible
        from datetime import date
        return date.today() <= self.match_window_closes

    @property
    def maximalist_shares_required(self) -> int:
        """Number of shares required under maximalist interpretation."""
        # For 50% pledge: donate 1 share for every 1 share sold
        # For 25% pledge: donate 1 share for every 3 shares sold
        # shares_donated / (shares_sold + shares_donated) = pledge_percentage
        # Solving for shares_donated:
        # shares_donated = (pledge_percentage * shares_sold) / (1 - pledge_percentage)
        if self.pledge_percentage >= 1:
            return float('inf')  # Cannot fulfill 100% or more pledge
        return int((self.pledge_percentage * self.shares_sold) / (1 - self.pledge_percentage))

    @property
    def maximalist_obligation_shares(self) -> float:
        """Dollar value of shares required under maximalist interpretation at current price."""
        # This should be calculated based on share count * current price
        # Not as a percentage of proceeds
        return self.maximalist_shares_required  # Caller must multiply by price

    @property
    def maximalist_fulfillment(self) -> float:
        """Fulfillment % under maximalist interpretation (share count based)."""
        required = self.maximalist_shares_required
        if required == 0:
            return 0.0
        return min(1.0, self.maximalist_shares_donated / required)

    # @property
    # def minimalist_fulfillment(self) -> float:
    #     """Fulfillment % under minimalist interpretation (dollar based)."""
    #     if self.total_pledge_obligation == 0:
    #         return 0.0
    #     return self.donations_made / self.total_pledge_obligation

    @property
    def is_fulfilled(self) -> bool:
        """Check if this obligation is fully satisfied."""
        # Consider fulfilled if within 1 share of requirement
        required = self.maximalist_shares_required
        return abs(self.maximalist_shares_donated - required) <= 1


@dataclass
class PledgeState:
    """Collection of all pledge obligations with FIFO discharge tracking."""
    obligations: List[PledgeObligation] = field(default_factory=list)

    def add_obligation(self, obligation: PledgeObligation) -> None:
        """Add a new pledge obligation."""
        self.obligations.append(obligation)

    def discharge_donation(self, donation_amount: float, shares_donated: int = 0, donation_date: Optional[date] = None) -> dict:
        """Apply donation to obligations in FIFO order, respecting match window eligibility.

        Returns:
            dict with 'eligible_amount': amount applied to match-eligible obligations
        """
        remaining_amount = donation_amount
        remaining_shares = shares_donated
        eligible_match_amount = 0.0

        # Sort by commencement date to ensure FIFO discharge
        sorted_obligations = sorted(self.obligations, key=lambda o: o.commencement_date or date.min)

        for obligation in sorted_obligations:
            if remaining_amount <= 0 and remaining_shares <= 0:
                break

            # Check if match window is still open
            if (donation_date and obligation.match_window_closes and
                donation_date > obligation.match_window_closes):
                continue  # Skip closed match windows

            if obligation.outstanding_obligation > 0:
                # Apply dollar amount
                applied_amount = min(remaining_amount, obligation.outstanding_obligation)
                obligation.donations_made += applied_amount
                obligation.outstanding_obligation -= applied_amount
                remaining_amount -= applied_amount

                # Track amount applied to eligible obligation
                eligible_match_amount += applied_amount

                # Apply shares
                shares_needed = obligation.maximalist_shares_required - obligation.maximalist_shares_donated
                applied_shares = min(remaining_shares, shares_needed)
                obligation.maximalist_shares_donated += applied_shares
                remaining_shares -= applied_shares

        return {'eligible_amount': eligible_match_amount}

    @property
    def total_outstanding_obligation(self) -> float:
        """Total outstanding obligation across all pledges."""
        return sum(obligation.outstanding_obligation for obligation in self.obligations)

    def process_window_closures(self, current_year: int, current_price: float, company_match_ratio: float) -> float:
        """
        Process match window closures and calculate lost opportunities.

        Args:
            current_year: Current year being processed
            current_price: Current share price for valuation
            company_match_ratio: Company match ratio (e.g., 3.0 for 3:1)

        Returns:
            Total lost match opportunity value for this year
        """
        from datetime import date
        current_date = date(current_year, 12, 31)  # End of year processing
        total_lost_value = 0.0

        for obligation in self.obligations:
            if (obligation.match_window_closes and
                current_date > obligation.match_window_closes and
                obligation.lost_match_opportunity == 0.0):  # Not yet processed

                # Calculate unfulfilled shares
                unfulfilled_shares = obligation.maximalist_shares_required - obligation.maximalist_shares_donated

                if unfulfilled_shares > 0:
                    # Calculate lost company match value
                    lost_value = unfulfilled_shares * current_price * company_match_ratio
                    obligation.lost_match_opportunity = lost_value
                    total_lost_value += lost_value

        return total_lost_value

    @property
    def next_deadline(self) -> Optional[date]:
        """Next approaching match window close among unfulfilled obligations."""
        unfulfilled = [o for o in self.obligations if not o.is_fulfilled and o.match_window_closes]
        if not unfulfilled:
            return None
        return min(o.match_window_closes for o in unfulfilled)


@dataclass
class YearlyState:
    """Complete financial state for a specific year."""
    year: int

    # Cash flow
    starting_cash: float
    income: float
    exercise_costs: float
    tax_paid: float
    donation_value: float
    company_match_received: float  # Company match amount received this year
    ending_cash: float

    # Tax state
    tax_state: TaxState

    # Charitable deductions
    charitable_state: CharitableDeductionState

    # NEW: Store full charitable deduction results from annual tax calculator
    federal_charitable_deduction_result: Optional[Any] = None  # CharitableDeductionResult
    ca_charitable_deduction_result: Optional[Any] = None  # CharitableDeductionResult

    # Tax details
    gross_tax: float = 0.0
    tax_withholdings: float = 0.0

    # Additional financial tracking
    living_expenses: float = 0.0
    investment_income: float = 0.0
    investment_balance: float = 0.0
    lost_match_opportunities: float = 0.0  # Forfeited company match value from closed windows

    # Equity holdings
    equity_holdings: List[ShareLot] = field(default_factory=list)
    total_equity_value: float = 0.0

    # Disposal tracking - cumulative by lot_id
    shares_sold: Dict[str, int] = field(default_factory=dict)  # lot_id -> cumulative shares sold
    shares_donated: Dict[str, int] = field(default_factory=dict)  # lot_id -> cumulative shares donated

    # Pledge obligations
    pledge_state: PledgeState = field(default_factory=PledgeState)
    
    # Year-specific pledge tracking
    pledge_shares_obligated_this_year: int = 0
    pledge_shares_donated_this_year: int = 0
    pledge_shares_expired_this_year: int = 0

    # Additional metrics
    total_net_worth: float = 0.0

    # Annual tax components for detailed reporting
    annual_tax_components: Optional[Any] = None

    # Additional income tracking
    spouse_income: float = 0.0
    other_income: float = 0.0

    # Lifecycle event tracking
    vesting_events: List['VestingEvent'] = field(default_factory=list)
    expiration_events: List['ExpirationEvent'] = field(default_factory=list)

    def get_equity_value_by_type(self, share_type: ShareType) -> float:
        """Calculate total value of holdings by share type."""
        # Note: This would need current market price to calculate actual value
        return sum(lot.quantity for lot in self.equity_holdings if lot.share_type == share_type)

    def get_exercisable_options(self) -> List[ShareLot]:
        """Get all lots that can be exercised."""
        return [lot for lot in self.equity_holdings
                if lot.lifecycle_state == LifecycleState.VESTED_NOT_EXERCISED]

    def get_saleable_shares(self) -> List[ShareLot]:
        """Get all lots that can be sold."""
        return [lot for lot in self.equity_holdings
                if lot.lifecycle_state == LifecycleState.EXERCISED_NOT_DISPOSED]


@dataclass
class ProjectionPlan:
    """Complete plan for equity actions over multiple years."""
    name: str
    description: str
    start_date: date
    end_date: date

    # Initial state
    initial_lots: List[ShareLot]
    initial_cash: float

    # Planned actions
    planned_actions: List[PlannedAction] = field(default_factory=list)

    # Market assumptions
    price_projections: Dict[int, float] = field(default_factory=dict)  # year -> price

    # Tax elections
    tax_elections: Dict[str, Any] = field(default_factory=dict)  # Optional tax elections like charitable_basis_election_years

    def add_action(self, action: PlannedAction) -> None:
        """Add a planned action to the plan."""
        self.planned_actions.append(action)

    def get_actions_for_year(self, year: int) -> List[PlannedAction]:
        """Get all actions planned for a specific year."""
        return [action for action in self.planned_actions
                if action.action_date.year == year]

    def get_actions_for_lot(self, lot_id: str) -> List[PlannedAction]:
        """Get all actions planned for a specific lot."""
        return [action for action in self.planned_actions
                if action.lot_id == lot_id]


@dataclass
class ProjectionResult:
    """Results from evaluating a projection plan."""
    plan: ProjectionPlan
    user_profile: 'UserProfile'  # Added to maintain tax rates through materialization #Claude TODO: explain this forward reference, is this the simplest implementation or a risk of bugs?
    yearly_states: List[YearlyState]
    summary_metrics: Dict[str, Any] = field(default_factory=dict)

    def get_state_for_year(self, year: int) -> Optional[YearlyState]:
        """Get the state for a specific year."""
        for state in self.yearly_states:
            if state.year == year:
                return state
        return None

    def get_final_state(self) -> Optional[YearlyState]:
        """Get the final year's state."""
        if self.yearly_states:
            return max(self.yearly_states, key=lambda s: s.year)
        return None

    def calculate_summary_metrics(self) -> None:
        """Calculate high-level summary metrics across all years."""
        if not self.yearly_states:
            return

        final_state = self.get_final_state()
        total_taxes = sum(state.tax_state.total_tax for state in self.yearly_states)
        total_donations = sum(state.donation_value for state in self.yearly_states)
        total_company_match = sum(state.company_match_received for state in self.yearly_states)
        total_charitable_impact = total_donations + total_company_match
        total_lost_match_value = sum(state.lost_match_opportunities for state in self.yearly_states)

        # Calculate pledge share metrics from individual obligations
        pledge_shares_obligated = 0
        pledge_shares_donated = 0
        pledge_shares_outstanding = 0
        pledge_shares_expired_window = 0

        if final_state and final_state.pledge_state.obligations:
            from datetime import date as date_class
            final_year_end = date_class(final_state.year, 12, 31)

            for obligation in final_state.pledge_state.obligations:
                pledge_shares_obligated += obligation.maximalist_shares_required
                pledge_shares_donated += obligation.maximalist_shares_donated

                # Calculate shares with expired windows (unfulfilled obligations past window)
                if (obligation.match_window_closes and
                    final_year_end > obligation.match_window_closes and
                    not obligation.is_fulfilled):
                    pledge_shares_expired_window += (obligation.maximalist_shares_required - obligation.maximalist_shares_donated)

            pledge_shares_outstanding = pledge_shares_obligated - pledge_shares_donated

        # Calculate option expiration opportunity costs
        total_opportunity_cost = 0.0
        total_expired_shares = 0
        expiration_details = []

        for state in self.yearly_states:
            if hasattr(state, 'expiration_events') and state.expiration_events:
                for event in state.expiration_events:
                    if hasattr(event, 'opportunity_cost') and hasattr(event, 'quantity'):
                        opportunity_cost = event.opportunity_cost if hasattr(event, 'opportunity_cost') else 0
                        if opportunity_cost > 0:
                            total_opportunity_cost += opportunity_cost
                            total_expired_shares += event.quantity
                            expiration_details.append({
                                'year': state.year,
                                'lot_id': event.lot_id,
                                'quantity': event.quantity,
                                'opportunity_cost': opportunity_cost,
                                'per_share_loss': event.per_share_loss if hasattr(event, 'per_share_loss') else 0,
                                'notes': event.notes if hasattr(event, 'notes') else ''
                            })

        # Calculate pledge fulfillment rate
        pledge_fulfillment_rate = 0.0
        if pledge_shares_obligated > 0:
            pledge_fulfillment_rate = pledge_shares_donated / pledge_shares_obligated

        # Calculate total expired charitable deductions (federal only)
        total_expired_charitable = 0.0
        for state in self.yearly_states:
            if hasattr(state, 'charitable_state') and state.charitable_state:
                total_expired_charitable += state.charitable_state.federal_expired_this_year

        # Get AMT credits from final state (placeholder for now)
        amt_credits_final = getattr(final_state, 'amt_credits_balance', 0) if final_state else 0

        self.summary_metrics = {
            'total_cash_final': final_state.ending_cash if final_state else 0,
            'total_taxes_all_years': total_taxes,
            'total_donations_all_years': total_donations,
            'total_company_match_all_years': total_company_match,
            'total_charitable_impact': total_charitable_impact,
            'total_charitable_impact_all_years': total_charitable_impact,
            'total_lost_match_value': total_lost_match_value,
            'total_equity_value_final': final_state.total_equity_value if final_state else 0,
            'pledge_shares_obligated': pledge_shares_obligated,
            'pledge_shares_donated': pledge_shares_donated,
            'pledge_shares_outstanding': pledge_shares_outstanding,
            'pledge_shares_expired_window': pledge_shares_expired_window,
            'pledge_fulfillment_rate': pledge_fulfillment_rate,
            'outstanding_obligation': final_state.pledge_state.total_outstanding_obligation if final_state else 0,
            'amt_credits_final': amt_credits_final,
            'expired_charitable_deduction': total_expired_charitable,
            'expired_option_count': total_expired_shares,
            'expired_option_loss': total_opportunity_cost,
            'total_opportunity_cost': total_opportunity_cost,
            'total_expired_shares': total_expired_shares,
            'expiration_details': expiration_details
        }


@dataclass
class UserProfile:
    """Simplified user profile for projection calculations."""
    # Federal tax rates (for AMT calculation)
    federal_tax_rate: float      # Marginal federal rate
    federal_ltcg_rate: float     # Federal LTCG rate (0%, 15%, or 20%)

    # State tax rates
    state_tax_rate: float        # State marginal rate
    state_ltcg_rate: float       # State LTCG rate (usually = state rate)

    # FICA/Medicare
    fica_tax_rate: float         # Social Security + Medicare base
    additional_medicare_rate: float  # Additional 0.9% on high earners
    niit_rate: float             # Net Investment Income Tax (3.8%)

    # Income
    annual_w2_income: float

    # Financial position
    current_cash: float
    exercise_reserves: float

    # Goals and constraints
    pledge_percentage: float
    company_match_ratio: float

    # Fields with defaults
    spouse_w2_income: float = 0.0
    other_income: float = 0.0
    filing_status: str = "single"
    state_of_residence: str = "California"

    # Additional income sources (with defaults)
    interest_income: float = 0.0
    dividend_income: float = 0.0
    bonus_expected: float = 0.0

    # Expenses and cash flow
    monthly_living_expenses: float = 0.0

    # Tax withholding rates and payments
    regular_income_withholding_rate: float = 0.0
    supplemental_income_withholding_rate: float = 0.0
    quarterly_payments: float = 0.0

    # Investment tracking
    taxable_investments: float = 0.0
    investment_return_rate: float = 0.07  # Default 7% annual return #Claude TODO: Plan to move this out to be user specified.
    crypto: float = 0.0
    real_estate_equity: float = 0.0

    # Tax carryforwards
    amt_credit_carryforward: float = 0.0

    # IPO timing for pledge expiration calculations
    assumed_ipo: Optional[date] = None

    # Grant-specific charitable programs for per-grant pledge tracking
    grants: List[Dict[str, Any]] = field(default_factory=list)

    def get_total_agi(self) -> float:
        """Calculate total AGI for charitable deduction limits."""
        return (self.annual_w2_income + self.spouse_w2_income + self.other_income +
                self.interest_income + self.dividend_income + self.bonus_expected)

    def get_available_exercise_cash(self) -> float:
        """Get total cash available for exercising options."""
        return self.current_cash + self.exercise_reserves

    def calculate_match_cap(self, eligible_vested_shares: int, shares_already_donated: int, current_share_price: float) -> float:
        """
        Calculate company match limit based on actual program rules.

        Company match limit = (pledge_percentage × eligible_vested_shares - shares_already_donated) × current_share_price × company_match_ratio

        Args:
            eligible_vested_shares: Total vested shares eligible for matching program
            shares_already_donated: Shares already donated (reduces remaining match eligibility)
            current_share_price: Current share price for calculating dollar limits

        Returns:
            Maximum dollar amount company will match for additional donations
        """
        remaining_eligible_shares = max(0, int(self.pledge_percentage * eligible_vested_shares) - shares_already_donated)
        return remaining_eligible_shares * current_share_price * self.company_match_ratio

    def get_total_income(self) -> float:
        """Calculate total annual income from all sources."""
        return (self.annual_w2_income + self.spouse_w2_income + self.other_income +
                self.interest_income + self.dividend_income + self.bonus_expected)

    def get_annual_expenses(self) -> float:
        """Calculate total annual living expenses."""
        return self.monthly_living_expenses * 12

    def get_total_withholdings(self, regular_income: float = 0.0, supplemental_income: float = 0.0) -> float:
        """Calculate total tax withholdings and estimated payments based on income."""
        regular_withholding = regular_income * self.regular_income_withholding_rate
        supplemental_withholding = supplemental_income * self.supplemental_income_withholding_rate
        return regular_withholding + supplemental_withholding + self.quarterly_payments


def calculate_pledge_metrics_for_year(pledge_state: PledgeState, year: int) -> dict:
    """Calculate pledge share metrics as of end of specified year.

    Args:
        pledge_state: The pledge state containing all obligations
        year: The year to calculate metrics for (as of end of year)

    Returns:
        Dict with keys: obligated, donated, outstanding, expired_window
    """
    from datetime import date as date_class
    year_end = date_class(year, 12, 31)

    obligated = 0
    donated = 0
    expired_window = 0

    for obligation in pledge_state.obligations:
        # Only count obligations that existed by end of this year
        if obligation.commencement_date and obligation.commencement_date <= year_end:
            obligated += obligation.maximalist_shares_required
            donated += obligation.maximalist_shares_donated

            # Calculate shares with expired windows (unfulfilled obligations past window)
            if (obligation.match_window_closes and
                year_end > obligation.match_window_closes and
                not obligation.is_fulfilled):
                expired_window += (obligation.maximalist_shares_required - obligation.maximalist_shares_donated)

    outstanding = obligated - donated

    return {
        'obligated': obligated,
        'donated': donated,
        'outstanding': outstanding,
        'expired_window': expired_window
    }
