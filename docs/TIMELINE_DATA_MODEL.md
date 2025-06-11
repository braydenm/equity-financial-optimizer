# Timeline Data Model

## Overview

The timeline data model tracks equity shares through their complete lifecycle using two complementary timelines. This extends the existing `equity_position_timeline.csv` by tracking how lots evolve through state transitions over time.

## States

1. **Granted (Unvested)**: Shares granted but not vested
2. **Vested (Unexercised)**: Vested, awaiting exercise or expiration
3. **Exercised (Held)**: Exercised and holding
4. **Disposed (Sold)**: Sold for cash (terminal state)
5. **Disposed (Donated)**: Donated to charity (terminal state)
6. **Expired**: Not exercised before deadline (terminal state)

### Share Conservation
Shares are never created or destroyed after granting:
```
Total Shares = Granted + Vested + Exercised + Disposed(Sold) + Disposed(Donated) + Expired
```

### Transitions

| Transition | From → To | Financial Impact |
|------------|-----------|------------------|
| Granting | None → Granted | None |
| Vesting | Granted → Vested | None |
| Exercising | Vested → Exercised | Cash out (strike × shares), Tax (AMT/ordinary) |
| Selling | Exercised → Disposed(Sold) | Cash in, Capital gains tax, Pledge creation |
| Donating | Exercised → Disposed(Donated) | Tax deduction, Company match, Pledge fulfillment |
| Expiring | Vested → Expired | Total loss |

### Exercise Lot Creation
Format: `{PARENT_LOT_ID}_EX_{YYYYMMDD}`
- Example: `LOT-01` exercised on 2027-01-15 → `LOT-01_EX_20270115`
- Preserves: Parent reference, exercise date, strike price, FMV at exercise
- Enables: Tax basis tracking, holding period calculation

## Timeline Structures

### State Timeline
Tracks share quantities in each state at period end:
```csv
Lot_ID,State,2025-06,2026-06,2027-06,2028-06
LOT-02,Granted,0,0,0,0
LOT-02,Vested,0,0,0,0
LOT-02,Exercised,10000,10000,5000,5000
LOT-02,Disposed_Sold,0,0,3000,3000
LOT-02,Disposed_Donated,0,0,2000,2000
LOT-02,TOTAL,10000,10000,10000,10000
```

### State Transition Timeline
Records share movements between states:
```csv
Lot_ID,Transition,2025-06,2026-06,2027-06,2028-06
LOT-02,Vesting,0,0,0,0
LOT-02,Exercising,0,0,0,0
LOT-02,Selling,0,0,3000,0
LOT-02,Donating,0,0,2000,0
```

## Integration

1. `equity_position_timeline.csv` → Initial inventory
2. State Timeline → Current position by state
3. Transition Timeline → Action history
Putting this all together enables a complete audit trail with tax basis
