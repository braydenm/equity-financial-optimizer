# PledgeObligation Code Audit Report

## Executive Summary

The PledgeObligation system is a sophisticated feature for tracking charitable pledge commitments arising from equity sales. This audit reveals a well-architected system with strong separation of concerns, though there are some notable peculiarities and opportunities for improvement.

**Critical Finding**: The current implementation models pledge obligations incorrectly. It assumes obligations only arise from share sales, but per Anthropic's donation matching FAQ, obligations also arise at IPO for all vested shares (regardless of sales). This architectural mismatch needs correction.

## Architecture Overview

### Core Components

1. **Two PledgeObligation Classes** (Peculiarity #1)
   - `calculators/components.py:222-263`: Original class with methods
   - `projections/projection_state.py:158-219`: Dataclass version used in projections
   - **Finding**: Duplicate implementations could lead to confusion and maintenance issues

2. **PledgeCalculator** (`projections/pledge_calculator.py`)
   - Centralized calculation logic using "maximalist interpretation"
   - Formula: `shares_donated / (shares_sold + shares_donated) = pledge_percentage`
   - Handles IPO window constraints and match deadline calculations

3. **PledgeState** (`projections/projection_state.py:222-314`)
   - Container for multiple obligations with FIFO discharge logic
   - Tracks match window closures and lost opportunities
   - Processes donations against oldest obligations first

## Data Flow Analysis

### 1. Configuration Layer
```
User Profile (JSON) → Grant-specific charitable_program
                    → pledge_percentage (e.g., 0.5 for 50%)
                    → company_match_ratio (e.g., 3.0 for 3:1)
                    → assumed_ipo date
```

### 2. Obligation Creation
```
Share Sale Event → ProjectionCalculator._process_sale()
                → Looks up grant-specific settings
                → PledgeCalculator.calculate_obligation()
                → Creates PledgeObligation with:
                  - Maximalist share requirement
                  - Match window deadline (min of 3 years or IPO+1 year)
                  - Transaction tracking ID
```

### 3. Obligation Fulfillment
```
Donation Event → ProjectionCalculator._process_donation()
               → PledgeState.discharge_donation()
               → FIFO allocation to obligations
               → Tracks match-eligible amounts
               → Updates share counts
```

### 4. Annual Processing
```
Year End → Process window closures
         → Calculate lost match opportunities
         → Track year-specific metrics:
           - pledge_shares_obligated_this_year
           - pledge_shares_donated_this_year
           - pledge_shares_expired_this_year
```

### 5. Output Generation
```
CSV Generation → Annual summary includes:
               - Current year obligations/donations
               - Cumulative outstanding shares
               - Expired shares
               → All pledge columns preserved as integers
```

## Key Interfaces and Dependencies

### Input Interfaces
1. **UserProfile**: Provides default pledge_percentage and company_match_ratio
2. **Grant Data**: Per-grant charitable_program overrides
3. **Scenario Actions**: SELL actions trigger obligations, DONATE actions discharge them
4. **Market Data**: Sale prices for obligation valuation

### Internal Interfaces
1. **PledgeCalculator → PledgeObligation**: Creates obligations with proper constraints
2. **ProjectionCalculator → PledgeState**: Manages obligation lifecycle
3. **PledgeState → YearlyState**: Tracks year-specific metrics
4. **YearlyState → CSV Generators**: Outputs tracking data

### Output Interfaces
1. **CSV Files**: Annual summaries with pledge tracking columns
2. **ProjectionResult**: Contains complete pledge state history
3. **Warning System**: Could alert on approaching deadlines (not currently implemented)

## Peculiarities and Findings

### 1. Dual PledgeObligation Implementations
- **Issue**: Two different classes with same name but different structures
- **Risk**: Confusion about which to use, potential divergence
- **Recommendation**: Consolidate to single implementation or clearly differentiate purposes

### 2. Maximalist Interpretation Hardcoded
- **Finding**: System only supports maximalist interpretation (share-based)
- **Impact**: Less flexibility for users who prefer dollar-based pledges
- **Opportunity**: Add configuration option for interpretation method

### 3. Grant-Specific Settings Fallback Logic
- **Implementation**: Complex fallback from grant → profile → defaults
- **Peculiarity**: Uses first grant's settings if grant_id lookup fails
- **Risk**: Silent use of wrong pledge percentage

### 4. Integer Share Tracking with Float Calculations
- **Finding**: Calculations use float but track integer shares
- **Risk**: Rounding errors in obligation calculations
- **Current Mitigation**: "within 1 share" fulfillment tolerance

### 5. Lost Match Opportunity Calculation
- **Implementation**: Calculated at year-end, not real-time
- **Impact**: Users don't see approaching deadline warnings
- **Opportunity**: Add proactive deadline notifications

### 6. FIFO Discharge Assumption
- **Finding**: Always discharges oldest obligations first
- **Impact**: Users cannot optimize which obligations to fulfill
- **Consideration**: May not be tax-optimal in all cases

### 7. No Partial Obligation Tracking
- **Finding**: Obligations are binary (fulfilled or not)
- **Missing**: Percentage completion visibility
- **Impact**: Users can't see progress toward large obligations

## Testing Coverage

The system has comprehensive test coverage with 52+ test files covering:
- IPO pledge integration scenarios
- Zero donation edge cases
- Year-specific tracking
- Company match interactions
- Grant-specific charitable programs
- Window expiration scenarios

## Recommendations

### High Priority
1. **Consolidate PledgeObligation Classes**: Merge or clearly differentiate the two implementations
2. **Add Deadline Warnings**: Implement proactive notifications for approaching match windows
3. **Improve Grant Lookup**: Make grant-specific setting resolution more explicit and logged

### Medium Priority
1. **Configuration Flexibility**: Add option for minimalist (dollar-based) interpretation
2. **Progress Tracking**: Show percentage completion for each obligation
3. **Optimize Discharge Strategy**: Allow user control over FIFO vs. strategic fulfillment

### Low Priority
1. **Enhanced Reporting**: Add dedicated pledge tracking reports beyond CSV
2. **What-If Analysis**: Tools to model different fulfillment strategies
3. **Historical Tracking**: Maintain history of obligation modifications

## Security and Performance Considerations

### Security
- No sensitive data exposure identified
- Pledge percentages properly validated (0-100%)
- Transaction IDs prevent duplicate obligations

### Performance
- O(n) complexity for obligation discharge (acceptable for typical portfolio sizes)
- Year-end processing could be optimized with indexed lookups
- CSV generation efficient with single-pass processing

## Conclusion

The PledgeObligation system is well-designed with clear separation of concerns and comprehensive tracking. The maximalist interpretation and grant-specific settings show thoughtful product design. Main areas for improvement center on consolidating duplicate code, adding user visibility features, and providing more flexibility in fulfillment strategies.

The system successfully handles complex scenarios including IPO windows, company match deadlines, and multi-year tracking. With the recommended improvements, it could provide even better user guidance and tax optimization opportunities.

---

## Implementation Plan

### Overview

This implementation plan addresses the critical architectural mismatch identified in the audit. The current system only creates pledge obligations from share sales, but per Anthropic's donation matching program documentation, obligations can also arise at IPO for all vested eligible shares. Additionally, the system needs to properly track liquidity events as containers for cash donation tracking.

### Phase 1: Data Model Refactoring

#### 1.1 Create LiquidityEvent Model

**Location**: `calculators/components.py` (or new file `calculators/liquidity_event.py`)

```python
@dataclass
class LiquidityEvent:
    """Track each liquidity event separately"""
    event_id: str
    event_date: date
    event_type: str  # "tender_offer", "ipo", "secondary_offering"
    price_per_share: float
    
    # What happened in this event
    shares_vested_at_event: int
    shares_sold: int
    exercise_costs: float = 0.0
    taxes_withheld: float = 0.0
    net_proceeds: float = 0.0
    
    # Donation tracking for this event
    cash_donated_from_event: float = 0.0
    match_window_closes: date = field(init=False)
    
    def __post_init__(self):
        self.match_window_closes = self.event_date + timedelta(days=3*365)
    
    @property
    def remaining_donatable_proceeds(self) -> float:
        """Cash still available to donate from this event"""
        return self.net_proceeds - self.cash_donated_from_event
    
    def is_window_open(self, as_of_date: date) -> bool:
        return as_of_date <= self.match_window_closes
```

#### 1.2 Update PledgeObligation Model

**Action**: Remove the duplicate class in `calculators/components.py:222-263`

**Action**: Update the dataclass in `projections/projection_state.py`:

```python
@dataclass
class PledgeObligation:
    """Obligation created by sale or IPO"""
    source_event_id: str  # Links to LiquidityEvent
    obligation_type: str  # "sale" or "ipo_remainder"
    creation_date: date
    shares_obligated: int
    shares_fulfilled: int = 0
    pledge_percentage: float = 0.5
    
    # Remove these fields (now tracked in LiquidityEvent):
    # - match_window_closes (look up via source_event_id)
    # - commencement_date (use creation_date)
    
    @property
    def is_fulfilled(self) -> bool:
        return self.shares_fulfilled >= self.shares_obligated
```

#### 1.3 Update Profile Loading

**Location**: `loaders/profile_loader.py`

Add support for loading liquidity events:

```python
def load_liquidity_events(profile_data: dict) -> List[LiquidityEvent]:
    """Load liquidity events from profile, with backwards compatibility"""
    events = []
    
    # Load explicit liquidity events
    if "liquidity_events" in profile_data:
        for event_data in profile_data["liquidity_events"]:
            events.append(LiquidityEvent(**event_data))
    
    # Backwards compatibility: convert old fields
    if "last_tender_offer_date" in profile_data and not events:
        events.append(LiquidityEvent(
            event_id="tender_historical",
            event_date=parse_date(profile_data["last_tender_offer_date"]),
            event_type="tender_offer",
            price_per_share=profile_data.get("last_tender_price", 0.0),
            shares_vested_at_event=0  # Will need calculation
        ))
    
    return events
```

### Phase 2: Core Logic Updates

#### 2.1 Update PledgeCalculator

**Location**: `projections/pledge_calculator.py`

Add methods for IPO obligation creation:

```python
@staticmethod
def calculate_ipo_remainder_obligation(
    total_vested_shares: int,
    pledge_percentage: float,
    existing_obligations: List[PledgeObligation],
    ipo_date: date,
    ipo_event_id: str
) -> Optional[PledgeObligation]:
    """
    Calculate remaining pledge obligation at IPO.
    
    At IPO, user must fulfill pledge on ALL vested eligible shares,
    not just those sold.
    """
    # Total shares that should be pledged
    total_pledge_shares = int(total_vested_shares * pledge_percentage)
    
    # Shares already obligated from sales
    already_obligated = sum(o.shares_obligated for o in existing_obligations)
    
    # Remaining obligation
    remainder = total_pledge_shares - already_obligated
    
    if remainder > 0:
        return PledgeObligation(
            source_event_id=ipo_event_id,
            obligation_type="ipo_remainder",
            creation_date=ipo_date,
            shares_obligated=remainder,
            pledge_percentage=pledge_percentage
        )
    
    return None
```

#### 2.2 Update ProjectionCalculator

**Location**: `projections/projection_calculator.py`

Add liquidity event tracking:

```python
def _process_year_actions(self, year: int, ...):
    # ... existing code ...
    
    # Check for IPO in this year
    for event in self.liquidity_events:
        if event.event_type == "ipo" and event.event_date.year == year:
            # Calculate total vested eligible shares
            vested_shares = self._calculate_vested_eligible_shares(event.event_date)
            
            # Create IPO remainder obligation
            ipo_obligation = PledgeCalculator.calculate_ipo_remainder_obligation(
                total_vested_shares=vested_shares,
                pledge_percentage=self.profile.pledge_percentage,
                existing_obligations=pledge_state.obligations,
                ipo_date=event.event_date,
                ipo_event_id=event.event_id
            )
            
            if ipo_obligation:
                pledge_state.add_obligation(ipo_obligation)
                yearly_state.pledge_shares_obligated_this_year += ipo_obligation.shares_obligated
```

### Phase 3: Cash Donation Tracking

#### 3.1 Update Donation Processing

Track which liquidity event provided the cash for donations:

```python
def _process_donation(self, action: Action, ...):
    # For cash donations, need to track source liquidity event
    if action.donation_type == "cash":
        # Find liquidity event that provided these funds
        source_event = self._find_source_liquidity_event(
            donation_date=action.action_date,
            donation_amount=action.amount
        )
        
        if source_event:
            # Update the event's tracking
            source_event.cash_donated_from_event += action.amount
            
            # Check if within match window
            if not source_event.is_window_open(action.action_date):
                # Track as ineligible for match
                yearly_state.ineligible_donations += action.amount
```

### Phase 4: Testing

#### 4.1 Create Failing Test

**Location**: `tests/test_ipo_remainder_obligation.py`

```python
def test_ipo_creates_remainder_obligation():
    """Test that IPO creates obligation for all vested shares, not just sold shares"""
    
    # Setup: Profile with 10,000 vested shares, 50% pledge
    profile = UserProfile(
        grants=[{
            "grant_id": "ISO_001",
            "total_shares": 10000,
            "vested_shares": 10000,
            "charitable_program": {
                "pledge_percentage": 0.5,
                "company_match_ratio": 3.0
            }
        }],
        liquidity_events=[{
            "event_id": "ipo_2026",
            "event_date": "2026-03-15",
            "event_type": "ipo",
            "price_per_share": 75.0
        }]
    )
    
    # Scenario: Sell only 2000 shares before IPO
    scenario = Scenario(
        actions=[
            Action(
                action_date=date(2025, 6, 1),
                action_type=ActionType.SELL,
                lot_id="ISO_001",
                quantity=2000
            )
        ]
    )
    
    # Run projection
    result = run_projection(profile, scenario)
    
    # Get 2026 state (IPO year)
    ipo_year_state = result.yearly_states[2026]
    
    # Expected behavior:
    # - 50% pledge on 10,000 vested shares = 5,000 share obligation
    # - Sale created obligation for 1,000 shares (50% of 2,000)
    # - IPO should create remainder obligation for 4,000 shares
    
    # This will FAIL with current implementation
    # Current: Only tracks 1,000 share obligation from sale
    # Expected: Should track 5,000 total (1,000 from sale + 4,000 from IPO)
    
    total_obligations = sum(
        o.shares_obligated for o in ipo_year_state.pledge_state.obligations
    )
    
    assert total_obligations == 5000, f"Expected 5000 total obligation, got {total_obligations}"
    
    # Check IPO remainder obligation exists
    ipo_obligations = [
        o for o in ipo_year_state.pledge_state.obligations 
        if o.obligation_type == "ipo_remainder"
    ]
    
    assert len(ipo_obligations) == 1, "Should have one IPO remainder obligation"
    assert ipo_obligations[0].shares_obligated == 4000
```

### Phase 5: CSV Output Updates

#### 5.1 Add Liquidity Event Tracking

Create new CSV generator for liquidity events:

```python
def generate_liquidity_events_csv(result: ProjectionResult, output_path: str):
    """Generate CSV tracking all liquidity events and their utilization"""
    rows = []
    
    for event in result.liquidity_events:
        row = {
            'event_id': event.event_id,
            'event_date': event.event_date,
            'event_type': event.event_type,
            'price_per_share': event.price_per_share,
            'shares_sold': event.shares_sold,
            'net_proceeds': event.net_proceeds,
            'cash_donated': event.cash_donated_from_event,
            'remaining_donatable': event.remaining_donatable_proceeds,
            'match_window_closes': event.match_window_closes,
            'window_status': 'open' if event.is_window_open(date.today()) else 'closed'
        }
        rows.append(row)
```

### Phase 6: Migration and Rollout

1. **Add feature flag** to enable new IPO obligation logic
2. **Run parallel testing** with existing scenarios
3. **Create migration script** for existing user data
4. **Update documentation** with new behavior
5. **Gradual rollout** with monitoring

### Success Criteria

1. The failing test case passes
2. All existing tests continue to pass
3. IPO events properly create remainder obligations
4. Cash donations correctly track source liquidity events
5. CSV outputs include new liquidity event information
6. No regressions in existing functionality

### Timeline Estimate

- Phase 1 (Data Model): 1-2 days
- Phase 2 (Core Logic): 2-3 days
- Phase 3 (Cash Tracking): 1-2 days
- Phase 4 (Testing): 1 day
- Phase 5 (CSV Updates): 1 day
- Phase 6 (Migration): 2-3 days

Total: 8-12 days of development work