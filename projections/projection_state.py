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

    def __post_init__(self):
        """Validate ShareLot constraints after initialization."""
        # Options (ISO and NSO) must have expiration dates
        if self.share_type in [ShareType.ISO, ShareType.NSO] and self.expiration_date is None:
            raise ValueError(
                f"ShareLot {self.lot_id}: Options (ISO/NSO) must have an expiration_date. "
                f"Share type {self.share_type.value} requires expiration_date to be set."
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


@dataclass
class CharitableDeductionState:
    """Charitable deduction state and carryforward tracking."""
    current_year_deduction: float = 0.0
    carryforward_remaining: Dict[int, float] = field(default_factory=dict)  # year -> amount
    total_available: float = 0.0


@dataclass
class PledgeObligation:
    """Individual pledge obligation tracking from a specific tender/sale event."""
    parent_transaction_id: str  # Unique ID of the sale/tender that created this obligation
    commencement_date: Optional[date] = None  # Date when obligation was created (tender/sale date)
    deadline_date: Optional[date] = None  # 3-year deadline from commencement
    total_pledge_obligation: float = 0.0  # Total dollar obligation from pledge % of tender/sale proceeds
    donations_made: float = 0.0  # Total donations made toward this specific obligation
    shares_sold: int = 0  # Number of shares tendered/sold that created this obligation
    pledge_percentage: float = 0.5  # Pledge percentage (0.5 = 50%)
    maximalist_shares_donated: int = 0  # Number of shares actually donated toward this obligation
    outstanding_obligation: float = 0.0  # Remaining dollar obligation

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

    def discharge_donation(self, donation_amount: float, shares_donated: int = 0) -> None:
        """Apply donation to obligations in FIFO order."""
        remaining_amount = donation_amount
        remaining_shares = shares_donated

        # Sort by commencement date to ensure FIFO discharge
        sorted_obligations = sorted(self.obligations, key=lambda o: o.commencement_date or date.min)

        for obligation in sorted_obligations:
            if remaining_amount <= 0 and remaining_shares <= 0:
                break

            if obligation.outstanding_obligation > 0:
                # Apply dollar amount
                applied_amount = min(remaining_amount, obligation.outstanding_obligation)
                obligation.donations_made += applied_amount
                obligation.outstanding_obligation -= applied_amount
                remaining_amount -= applied_amount

                # Apply shares
                shares_needed = obligation.maximalist_shares_required - obligation.maximalist_shares_donated
                applied_shares = min(remaining_shares, shares_needed)
                obligation.maximalist_shares_donated += applied_shares
                remaining_shares -= applied_shares

    @property
    def total_outstanding_obligation(self) -> float:
        """Total outstanding obligation across all pledges."""
        return sum(obligation.outstanding_obligation for obligation in self.obligations)

    @property
    def next_deadline(self) -> Optional[date]:
        """Next approaching deadline among unfulfilled obligations."""
        unfulfilled = [o for o in self.obligations if not o.is_fulfilled and o.deadline_date]
        if not unfulfilled:
            return None
        return min(o.deadline_date for o in unfulfilled)


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
    ending_cash: float

    # Tax state
    tax_state: TaxState

    # Charitable deductions
    charitable_state: CharitableDeductionState

    # Tax details
    gross_tax: float = 0.0
    tax_withholdings: float = 0.0

    # Additional financial tracking
    living_expenses: float = 0.0
    investment_income: float = 0.0
    investment_balance: float = 0.0

    # Equity holdings
    equity_holdings: List[ShareLot] = field(default_factory=list)
    total_equity_value: float = 0.0

    # Disposal tracking - cumulative by lot_id
    shares_sold: Dict[str, int] = field(default_factory=dict)  # lot_id -> cumulative shares sold
    shares_donated: Dict[str, int] = field(default_factory=dict)  # lot_id -> cumulative shares donated

    # Pledge obligations
    pledge_state: PledgeState = field(default_factory=PledgeState)

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
    user_profile: 'UserProfile'  # Added to maintain tax rates through materialization #TODO explain this forward reference, is this the simplest implementation or a risk of bugs?
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

        # Calculate overall pledge fulfillment from individual obligations
        pledge_fulfillment_max = 0.0
        if final_state and final_state.pledge_state.obligations:
            total_obligations = len(final_state.pledge_state.obligations)
            fulfilled_obligations = sum(1 for obs in final_state.pledge_state.obligations if obs.maximalist_fulfillment >= 1.0)
            pledge_fulfillment_max = fulfilled_obligations / total_obligations if total_obligations > 0 else 0.0

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

        self.summary_metrics = {
            'total_cash_final': final_state.ending_cash if final_state else 0,
            'total_taxes_all_years': total_taxes,
            'total_donations_all_years': total_donations,
            'total_equity_value_final': final_state.total_equity_value if final_state else 0,
            'pledge_fulfillment_maximalist': pledge_fulfillment_max,
            'outstanding_obligation': final_state.pledge_state.total_outstanding_obligation if final_state else 0,
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

    # Tax withholdings and payments
    federal_withholding: float = 0.0
    state_withholding: float = 0.0
    quarterly_payments: float = 0.0

    # Base withholding for normal years (optional)
    base_federal_withholding: float = 0.0
    base_state_withholding: float = 0.0

    # Investment tracking
    taxable_investments: float = 0.0
    investment_return_rate: float = 0.07  # Default 7% annual return #Claude TODO: Plan to move this out to be user specified.

    # Tax carryforwards
    amt_credit_carryforward: float = 0.0

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

    def get_total_withholdings(self) -> float:
        """Calculate total tax withholdings and estimated payments."""
        return self.federal_withholding + self.state_withholding + self.quarterly_payments
