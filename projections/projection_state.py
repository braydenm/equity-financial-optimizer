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

if TYPE_CHECKING:
    from calculators.liquidity_event import LiquidityEvent




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
    """
    Pledge obligation tracking per the donation matching program.

    Obligations can be created by:
    1. Share sales during liquidity events
    2. IPO trigger for remaining unfulfilled pledge on all vested shares
    """
    source_event_id: str  # Links to LiquidityEvent that contains this obligation
    obligation_type: str  # "sale" or "ipo_remainder"
    creation_date: date  # When the obligation was created
    shares_obligated: int  # Number of shares required to fulfill pledge
    shares_fulfilled: int = 0  # Number of shares donated toward this obligation
    pledge_percentage: float = 0.5  # Pledge percentage that created this obligation
    grant_id: Optional[str] = None  # Which grant this obligation relates to

    # For tracking donation eligibility
    match_ratio: float = 3.0  # Company match ratio for this obligation

    @property
    def is_fulfilled(self) -> bool:
        """Check if this obligation is fully satisfied."""
        return self.shares_fulfilled >= self.shares_obligated

    @property
    def shares_remaining(self) -> int:
        """Number of shares still needed to fulfill this obligation."""
        return max(0, self.shares_obligated - self.shares_fulfilled)

    @property
    def fulfillment_percentage(self) -> float:
        """Percentage of obligation fulfilled (0.0 to 1.0)."""
        if self.shares_obligated == 0:
            return 1.0
        return min(1.0, self.shares_fulfilled / self.shares_obligated)


@dataclass
class PledgeState:
    """Collection of all pledge obligations with FIFO discharge tracking."""
    obligations: List[PledgeObligation] = field(default_factory=list)

    def add_obligation(self, obligation: PledgeObligation) -> None:
        """Add a new pledge obligation."""
        self.obligations.append(obligation)

    def apply_share_donation(self, shares_donated: int, donation_date: date, liquidity_events: List['LiquidityEvent']) -> dict:
        """
        Apply share donation to obligations in FIFO order.

        Only applies to obligations whose source liquidity event window is still open.

        Returns:
            dict with 'shares_credited': shares that count toward pledge fulfillment
        """
        remaining_shares = shares_donated
        shares_credited = 0

        # Sort by creation date to ensure FIFO discharge
        sorted_obligations = sorted(self.obligations, key=lambda o: o.creation_date)

        for obligation in sorted_obligations:
            if remaining_shares <= 0:
                break

            # Find the source liquidity event to check window
            source_event = next((e for e in liquidity_events if e.event_id == obligation.source_event_id), None)
            if source_event and not source_event.is_window_open(donation_date):
                continue  # Skip if window is closed

            # Apply shares to this obligation
            shares_needed = obligation.shares_remaining
            if shares_needed > 0:
                applied_shares = min(remaining_shares, shares_needed)
                obligation.shares_fulfilled += applied_shares
                remaining_shares -= applied_shares
                shares_credited += applied_shares

        return {'shares_credited': shares_credited, 'shares_uncredited': remaining_shares}

    @property
    def total_shares_obligated(self) -> int:
        """Total shares obligated across all pledges."""
        return sum(obligation.shares_obligated for obligation in self.obligations)

    @property
    def total_shares_fulfilled(self) -> int:
        """Total shares fulfilled across all obligations."""
        return sum(obligation.shares_fulfilled for obligation in self.obligations)

    @property
    def total_shares_remaining(self) -> int:
        """Total shares still needed to fulfill all obligations."""
        return sum(obligation.shares_remaining for obligation in self.obligations)

    def get_obligations_for_event(self, event_id: str) -> List[PledgeObligation]:
        """Get all obligations associated with a specific liquidity event."""
        return [o for o in self.obligations if o.source_event_id == event_id]


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
    shares_matched_this_year: int = 0  # Number of donated shares that received company match

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

        # Calculate pledge share metrics from yearly states
        pledge_shares_obligated = 0
        pledge_shares_donated = 0
        pledge_shares_outstanding = 0
        pledge_shares_expired_window = 0

        # Sum up expired shares and donations from all yearly states
        for state in self.yearly_states:
            if hasattr(state, 'pledge_shares_expired_this_year'):
                pledge_shares_expired_window += state.pledge_shares_expired_this_year
            
            # Sum up total shares donated across all years
            if hasattr(state, 'pledge_shares_donated_this_year'):
                pledge_shares_donated += state.pledge_shares_donated_this_year
            
            # Track obligated shares (cumulative)
            if hasattr(state, 'pledge_shares_obligated_this_year'):
                pledge_shares_obligated += state.pledge_shares_obligated_this_year

        # Outstanding is what remains at the end (only counting non-expired obligations)
        if final_state and final_state.pledge_state:
            # Only count shares as outstanding if their match window hasn't expired
            # Since we already counted expired shares, outstanding should exclude them
            total_remaining = final_state.pledge_state.total_shares_remaining
            # If we have expired shares, they should be subtracted from total remaining
            # because expired shares are no longer eligible for matching
            pledge_shares_outstanding = max(0, total_remaining - pledge_shares_expired_window)
            
        # For backward compatibility, if obligated wasn't tracked, use initial obligation
        if pledge_shares_obligated == 0 and final_state and final_state.pledge_state.obligations:
            for obligation in final_state.pledge_state.obligations:
                pledge_shares_obligated += obligation.shares_obligated

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

        # Calculate minimum cash balance across all years
        min_cash_balance = float('inf')
        min_cash_year = None
        for state in self.yearly_states:
            if state.ending_cash < min_cash_balance:
                min_cash_balance = state.ending_cash
                min_cash_year = state.year

        # Calculate years to burn AMT credits
        years_to_burn_amt_credits = 0
        initial_amt_credits = 0
        if self.yearly_states:
            # Find first year with AMT credits
            for i, state in enumerate(self.yearly_states):
                if hasattr(state, 'amt_credits_balance') and state.amt_credits_balance > 0:
                    initial_amt_credits = state.amt_credits_balance
                    # Find when credits reach zero
                    for j in range(i, len(self.yearly_states)):
                        if hasattr(self.yearly_states[j], 'amt_credits_balance'):
                            if self.yearly_states[j].amt_credits_balance == 0:
                                years_to_burn_amt_credits = j - i
                                break
                    # If still have credits at end, count total years
                    if years_to_burn_amt_credits == 0 and amt_credits_final > 0:
                        years_to_burn_amt_credits = len(self.yearly_states) - i
                    break

        # Calculate cash flow adequacy for each year
        cash_flow_issues = []
        years_with_insufficient_cash = 0

        for state in self.yearly_states:
            # Check if ending cash after all expenses and taxes is negative
            # or if there wasn't enough cash to pay taxes
            tax_obligation = state.tax_state.total_tax
            cash_available = state.starting_cash + state.income - state.exercise_costs

            if cash_available < tax_obligation:
                shortfall = tax_obligation - cash_available
                cash_flow_issues.append({
                    'year': state.year,
                    'tax_obligation': tax_obligation,
                    'cash_available': cash_available,
                    'shortfall': shortfall,
                    'ending_cash': state.ending_cash
                })
                years_with_insufficient_cash += 1

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
            'outstanding_obligation': pledge_shares_outstanding,
            'amt_credits_final': amt_credits_final,
            'expired_charitable_deduction': total_expired_charitable,
            'expired_option_count': total_expired_shares,
            'expired_option_loss': total_opportunity_cost,
            'total_opportunity_cost': total_opportunity_cost,
            'total_expired_shares': total_expired_shares,
            'expiration_details': expiration_details,
            'min_cash_balance': min_cash_balance,
            'min_cash_year': min_cash_year,
            'years_to_burn_amt_credits': years_to_burn_amt_credits,
            'initial_amt_credits': initial_amt_credits,
            'cash_flow_issues': cash_flow_issues,
            'years_with_insufficient_cash': years_with_insufficient_cash
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

    # Liquidity events for tracking donation windows and proceeds
    liquidity_events: List['LiquidityEvent'] = field(default_factory=list)

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


def calculate_pledge_metrics_for_year(pledge_state: PledgeState, year: int, liquidity_events: List['LiquidityEvent']) -> dict:
    """Calculate pledge share metrics as of end of specified year.

    Args:
        pledge_state: The pledge state containing all obligations
        year: The year to calculate metrics for (as of end of year)
        liquidity_events: List of liquidity events to check window expiration

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
        if obligation.creation_date and obligation.creation_date <= year_end:
            obligated += obligation.shares_obligated
            donated += obligation.shares_fulfilled

            # Calculate shares with expired windows (unfulfilled obligations past window)
            source_event = next((e for e in liquidity_events
                               if e.event_id == obligation.source_event_id), None)
            if (source_event and
                year_end > source_event.match_window_closes and
                not obligation.is_fulfilled):
                expired_window += obligation.shares_remaining

    outstanding = obligated - donated

    return {
        'obligated': obligated,
        'donated': donated,
        'outstanding': outstanding,
        'expired_window': expired_window
    }
