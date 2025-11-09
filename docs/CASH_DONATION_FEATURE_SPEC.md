# Cash Donation Feature Specification

## Current State: Partial Implementation

### What's Built (Working)
- `CashDonationComponents` class for tax calculations
- `calculate_cash_donation_components()` method in ShareDonationCalculator
- Annual tax calculator fully supports cash donations via `cash_donation_components` parameter
- Federal AGI limits: 60% for cash (temporary through 2025), 30% for stock
- California AGI limits: 50% for cash, 30% for stock
- Carryforward tracking for both federal and state
- CSV output field `charitable_deduction_cash` in annual_tax_detail.csv
- Comprehensive test coverage proving tax calculations work

### What's Missing (Gap)
- No user input mechanism (UserProfile lacks cash donation fields)
- No action type for cash donations (only share DONATE exists)
- Projection calculator never creates CashDonationComponents
- Annual tax calculator never receives cash_donation_components parameter
- No matching eligibility logic for cash donations from sale proceeds

## Company Donation Matching Requirements

Per equity-donation-matching-faq.md:
- Cash donations eligible for matching ONLY if from liquidity event proceeds
- 3-year window from liquidity event date
- Must apply cash to tender events to discharge pledge obligations FIFO style
- Match ratio depends on which grant was sold - simple if there's only 1 grant.
- Cannot exceed remaining proceeds from specific event - there's a calculator to estimate how many share equivalents you can use.

## Implementation Complexity

### Edge Cases to Handle
1. **Multiple liquidity events** - Which proceeds are being donated?
2. **Window timing** - Each event has its own 3-year window.
3. **Proceeds tracking** - Cannot donate more than net proceeds from event

### Why This Is Complex
Unlike share donations (where grant_id determines match ratio), cash donations require:
- Ensuring donation doesn't exceed available proceeds

## Implementation Options

### Cash Donation with Event Attribution

```python
# Extend PlannedAction to include source_event_id:
{
  "action_type": "donate",
  "lot_id": "CASH",
  "quantity": 50000,
  # "source_event_id": "tender_2025_05", not sure this matters, should be calculated on the fly FIFO style and return a visible warning if there's no eligible pledge obligation that can allow for matching
}
```
**Pros**: Full matching support

## Testing Requirements

Before implementation:
1. Verify no regression in existing share donation flow
2. Test interaction with carryforward tracking
3. Validate federal vs state limit differences
4. Test mixed cash + stock donations in same year
5. Ensure AMT calculations unaffected

## Files to Modify

1. `projections/projection_state.py` - Add field to UserProfile
2. `projections/projection_calculator.py` - Create cash components (~5 lines)
3. `loaders/profile_loader.py` - Load new field
4. `tests/test_cash_donation_e2e.py` - New E2E test
Check for other files.