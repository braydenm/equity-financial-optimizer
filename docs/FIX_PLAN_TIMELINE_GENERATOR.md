# Fix Plan: Timeline Generator Profile Structure Mismatch

## Problem Summary

The `TimelineGenerator` class is failing to generate future vesting events, causing scenario execution failures when attempting to exercise future vested lots (e.g., "VEST_20250624_ISO"). The root cause is a structural mismatch between the expected and actual profile data formats.

### Current Behavior
- Timeline CSV only contains 3 exercised lots (VCS-93, VCS-196, VCS-107)
- No future vesting events are generated
- Scenarios fail with "Lot not found" errors for future vested shares

### Expected Behavior
- Timeline should include all exercised lots PLUS future vesting events
- Each vesting event should have a unique lot_id (e.g., "VEST_20250624_ISO")
- Scenarios should be able to reference and exercise these future lots

## Root Cause Analysis

### 1. Profile Structure Mismatch

**TimelineGenerator expects:**
```python
profile = {
    'equity_position': {
        'vested_unexercised': {
            'iso_shares': 1000,
            'nso_shares': 2000
        },
        'unvested': {
            'vesting_calendar': [
                {'date': '2025-07-24', 'shares': 3107, 'share_type': 'ISO'},
                ...
            ]
        }
    }
}
```

**Actual profile structure (v2.0) - supports multiple grants:**
```python
profile = {
    'equity_position': {
        'grants': [
            {
                'grant_id': 'ES-83',
                'vesting_status': {
                    'vested_unexercised': {
                        'iso': 0,
                        'nso': 0
                    },
                    'unvested': {
                        'remaining_unvested': 59029,
                        'vesting_calendar': [
                            {'date': '2025-07-24', 'shares': 3107, 'share_type': 'ISO'},
                            ...
                        ]
                    }
                }
            },
            {
                'grant_id': 'ES-84',  # Second grant example
                'vesting_status': { ... }
            }
        ]
    }
}
```

**Important:** The system supports multiple grants, but many current features only process the first grant (grants[0]). This limitation needs to be addressed.

### 2. Affected Components

1. **TimelineGenerator._create_timeline_rows()** - Line 93-97: Looks for `vested_unexercised` at wrong level
2. **TimelineGenerator._generate_vesting_events()** - Line 155-165: Looks for `unvested` at wrong level
3. **EquityLoader** - Has backward compatibility BUT creates duplicate lot IDs with multiple grants!
   - Creates 'ISO' and 'NSO' lot IDs without grant suffix
   - Multiple grants would create multiple lots with same ID (collision)
4. **Scenarios** - Expect lot IDs like "VEST_20250624_ISO" that are never generated
5. **Multiple Grants** - Current implementation often only processes grants[0], missing subsequent grants

### 3. Data Flow Impact

```
ProfileLoader → TimelineGenerator → CSV (missing vesting events)
                        ↓
                 EquityLoader (correctly loads from profile, ignores CSV)
                        ↓
                 Scenarios fail (reference non-existent lot IDs)
```

## Solution Options

### Option 1: Fix TimelineGenerator (Recommended)
**Pros:**
- Maintains current profile v2.0 structure
- Aligns with EquityLoader's approach
- No profile migration needed

**Cons:**
- Requires code changes to TimelineGenerator
- Need to ensure backward compatibility

### Option 2: Add Profile Transformation Layer
**Pros:**
- No changes to TimelineGenerator
- Clear separation of concerns

**Cons:**
- Additional complexity
- Performance overhead
- Duplicate data in memory

### Option 3: Migrate Profiles to Expected Structure
**Pros:**
- No code changes needed
- Simplifies data structure

**Cons:**
- Breaking change for existing users
- Requires migration script
- Loses grant-specific information

## Recommended Implementation Plan

### Phase 1: Fix Critical Lot ID Collision in EquityLoader (2 hours)

**CRITICAL**: Must fix EquityLoader first as it creates duplicate lot IDs with multiple grants!

```python
# Current problematic code in EquityLoader._load_vested_unexercised():
if vested.get('iso', 0) > 0:
    lots.append(ShareLot(
        lot_id='ISO',  # BUG: Same ID for all grants!
        ...
    ))

# Fix: Include grant_id in lot_id
if vested.get('iso', 0) > 0:
    lot_id = f"ISO_{grant_id}" if grant_id else 'ISO'
    lots.append(ShareLot(
        lot_id=lot_id,  # Now unique per grant
        ...
    ))
```

This change affects:
- All scenarios that reference 'ISO' or 'NSO' lots
- Need to update scenario generation to use grant-specific IDs
- May break existing scenarios (need migration plan)

### Phase 2: Update TimelineGenerator (3-4 hours)

1. **Update `_create_timeline_rows()` method to handle ALL grants:**
```python
def _create_timeline_rows(self, profile: Dict[str, Any], 
                         current_date: Optional[date] = None) -> List[Dict[str, Any]]:
    # ... existing code ...
    
    # Add support for grant-based structure
    grants = equity_pos.get('grants', [])
    
    # IMPORTANT: Process ALL grants, not just the first one
    for grant_idx, grant in enumerate(grants):
        vesting_status = grant.get('vesting_status', {})
        vested = vesting_status.get('vested_unexercised', {})
        grant_id = grant.get('grant_id', f'GRANT_{grant_idx}')
        
        # Add ISO shares with unique lot ID per grant
        if vested.get('iso', 0) > 0:
            rows.append({
                'date': current_date.isoformat(),
                'lot_id': f"ISO_{grant_id}",
                'grant_id': grant_id,
                'share_type': 'ISO',
                'quantity': vested['iso'],
                'strike_price': grant.get('strike_price', 0.0),
                'lifecycle_state': 'vested_not_exercised',
                'tax_treatment': 'N/A'
            })
        
        # Add NSO shares with unique lot ID per grant
        if vested.get('nso', 0) > 0:
            rows.append({
                'date': current_date.isoformat(),
                'lot_id': f"NSO_{grant_id}",
                'grant_id': grant_id,
                'share_type': 'NSO',
                'quantity': vested['nso'],
                'strike_price': grant.get('strike_price', 0.0),
                'lifecycle_state': 'vested_not_exercised',
                'tax_treatment': 'N/A'
            })
    
    # Maintain backward compatibility
    if not grants:
        # Fall back to old structure
        vested = equity_pos.get('vested_unexercised', {})
        # ... existing code ...
```

2. **Update `_generate_vesting_events()` method:**
```python
def _generate_vesting_events(self, equity_pos: Dict[str, Any],
                            current_date: date) -> List[Dict[str, Any]]:
    vesting_events = []
    
    # First try grant-based structure
    grants = equity_pos.get('grants', [])
    if grants:
        # Process ALL grants, not just the first one
        for grant_idx, grant in enumerate(grants):
            vesting_status = grant.get('vesting_status', {})
            unvested = vesting_status.get('unvested', {})
            vesting_calendar = unvested.get('vesting_calendar', [])
            
            strike_price = grant.get('strike_price', 0.0)
            grant_id = grant.get('grant_id', f'GRANT_{grant_idx}')
            
            for event in vesting_calendar:
                vest_date = datetime.fromisoformat(event['date']).date()
                # Include grant_id in lot_id for multiple grant support
                lot_id = f"VEST_{vest_date.strftime('%Y%m%d')}_{event['share_type']}_{grant_id}"
                
                # Determine lifecycle state
                if vest_date <= current_date:
                    lifecycle_state = 'vested_not_exercised'
                else:
                    lifecycle_state = 'granted_not_vested'
                
                vesting_events.append({
                    'date': vest_date.isoformat(),
                    'lot_id': lot_id,
                    'grant_id': grant_id,
                    'share_type': event['share_type'],
                    'quantity': event['shares'],
                    'strike_price': strike_price,
                    'lifecycle_state': lifecycle_state,
                    'tax_treatment': 'N/A'
                })
    else:
        # Fall back to old structure
        unvested = equity_pos.get('unvested', {})
        vesting_calendar = unvested.get('vesting_calendar', [])
        # ... existing code ...
    
    return vesting_events
```

### Phase 2: Add Tests (1-2 hours)

1. **Create test for single and multi-grant profiles:**
```python
def test_timeline_generator_single_grant_profile():
    """Test timeline generation with v2.0 single grant profile."""
    profile = {
        'equity_position': {
            'grants': [{
                'grant_id': 'TEST-001',
                'strike_price': 5.00,
                'vesting_status': {
                    'vested_unexercised': {
                        'iso': 1000,
                        'nso': 2000
                    },
                    'unvested': {
                        'vesting_calendar': [
                            {'date': '2025-07-24', 'shares': 3107, 'share_type': 'ISO'}
                        ]
                    }
                }
            }]
        }
    }
    
    generator = TimelineGenerator()
    timeline_rows = generator._create_timeline_rows(profile, date(2025, 6, 1))
    
    # Should have vested shares + future vesting event
    assert len(timeline_rows) == 3  # 1 ISO vested + 1 NSO vested + 1 future vest
    
    # Check vested shares
    iso_vested = next(r for r in timeline_rows if r['lot_id'] == 'ISO_TEST-001')
    assert iso_vested['quantity'] == 1000
    assert iso_vested['lifecycle_state'] == 'vested_not_exercised'
    
    # Check future vesting
    future_vest = next(r for r in timeline_rows if r['lot_id'].startswith('VEST_20250724_ISO'))
    assert future_vest['quantity'] == 3107
    assert future_vest['lifecycle_state'] == 'granted_not_vested'

def test_timeline_generator_multi_grant_profile():
    """Test timeline generation with multiple grants."""
    profile = {
        'equity_position': {
            'grants': [
                {
                    'grant_id': 'ES-83',
                    'strike_price': 5.00,
                    'vesting_status': {
                        'vested_unexercised': {'iso': 1000, 'nso': 0},
                        'unvested': {
                            'vesting_calendar': [
                                {'date': '2025-07-24', 'shares': 1000, 'share_type': 'ISO'}
                            ]
                        }
                    }
                },
                {
                    'grant_id': 'ES-84',
                    'strike_price': 10.00,
                    'vesting_status': {
                        'vested_unexercised': {'iso': 500, 'nso': 1500},
                        'unvested': {
                            'vesting_calendar': [
                                {'date': '2025-08-24', 'shares': 2000, 'share_type': 'NSO'}
                            ]
                        }
                    }
                }
            ]
        }
    }
    
    generator = TimelineGenerator()
    timeline_rows = generator._create_timeline_rows(profile, date(2025, 6, 1))
    
    # Should have shares from both grants
    assert len(timeline_rows) == 6  # Grant1: ISO vested + ISO future, Grant2: ISO vested + NSO vested + NSO future
    
    # Check grant 1 lots
    grant1_iso = next(r for r in timeline_rows if r['lot_id'] == 'ISO_ES-83')
    assert grant1_iso['quantity'] == 1000
    assert grant1_iso['strike_price'] == 5.00
    
    # Check grant 2 lots
    grant2_nso = next(r for r in timeline_rows if r['lot_id'] == 'NSO_ES-84')
    assert grant2_nso['quantity'] == 1500
    assert grant2_nso['strike_price'] == 10.00
```

2. **Test backward compatibility:**
```python
def test_timeline_generator_backward_compatibility():
    """Test timeline generation with old profile structure."""
    profile = {
        'equity_position': {
            'vested_unexercised': {
                'iso_shares': 1000,
                'nso_shares': 2000
            },
            'unvested': {
                'vesting_calendar': [
                    {'date': '2025-07-24', 'shares': 3107, 'share_type': 'ISO'}
                ]
            }
        }
    }
    
    generator = TimelineGenerator()
    timeline_rows = generator._create_timeline_rows(profile, date(2025, 6, 1))
    
    # Should still work with old structure
    assert len(timeline_rows) > 0
```

### Phase 3: Update Scenario Generation and Documentation (2 hours)

1. **Update natural evolution generator to use correct lot IDs**
2. **Document the lot ID naming convention:**
   - Exercised lots: Keep existing IDs (e.g., "VCS-93")
   - Vested unexercised: "{TYPE}_{GRANT_ID}" (e.g., "ISO_ES-83", "NSO_ES-84")
   - Future vests (single grant): "VEST_{YYYYMMDD}_{TYPE}" (e.g., "VEST_20250624_ISO")
   - Future vests (multiple grants): "VEST_{YYYYMMDD}_{TYPE}_{GRANT_ID}" (e.g., "VEST_20250624_ISO_ES-83")

3. **Add explicit multi-grant limitations documentation:**
   ```markdown
   ## Current Multi-Grant Limitations
   
   While the profile structure supports multiple grants, some features currently only process the first grant:
   - **CRITICAL**: EquityLoader creates duplicate 'ISO'/'NSO' lot IDs across grants
   - Charitable program settings (uses first grant's match ratio)
   - Some calculators may aggregate shares across grants
   - Scenarios need to reference specific grant IDs
   
   ## Breaking Changes with Multi-Grant Fix
   
   Fixing multi-grant support will change lot IDs:
   - Old: 'ISO', 'NSO' (collision with multiple grants)
   - New: 'ISO_ES-83', 'NSO_ES-84' (unique per grant)
   - Existing scenarios will need migration
   
   ## Future Multi-Grant Support
   
   Full multi-grant support requires:
   - Grant-specific charitable programs
   - Per-grant exercise strategies
   - Grant-specific tax treatment tracking
   - Automated scenario migration tools
   ```

### Phase 4: Validation & Documentation (1 hour)

1. **Run all existing tests to ensure no regression**
2. **Update documentation:**
   - Add note about profile v2.0 structure support
   - Document lot ID naming conventions
   - Update scenario creation examples

3. **Create migration guide for scenario authors:**
   - How to find correct lot IDs
   - How to reference future vesting events
   - Common patterns and examples

## Testing Strategy

### Unit Tests
1. Test TimelineGenerator with grant-based profile
2. Test TimelineGenerator with legacy profile structure
3. Test edge cases (no grants, empty vesting calendar, mixed structures)

### Integration Tests
1. Generate timeline → Load with EquityLoader → Execute scenario
2. Test all existing scenarios still work
3. Test new scenarios can reference future vesting lots

### Manual Testing
1. Run with actual user profile
2. Verify CSV output contains all expected lots
3. Run example scenarios that exercise future vests

## Risk Mitigation

1. **Backward Compatibility:** Maintain support for both profile structures
2. **Gradual Rollout:** Test with demo data first, then user data
3. **Clear Error Messages:** Add specific error when lot not found with suggestions
4. **Documentation:** Update all examples and guides before release

## Success Criteria

1. Timeline CSV includes all vesting events (past and future)
2. All existing scenarios continue to work
3. New scenarios can exercise future vested lots
4. No performance degradation
5. Clear documentation and examples

## Timeline

- Phase 1: 2 hours (Fix EquityLoader lot ID collision - CRITICAL)
- Phase 2: 3-4 hours (Update TimelineGenerator with multi-grant support)
- Phase 3: 1-2 hours (Add tests including multi-grant scenarios)
- Phase 4: 2 hours (Update scenario generation and multi-grant documentation)
- Phase 5: 1 hour (Validation & documentation)
- Phase 6: 1-2 hours (Scenario migration for lot ID changes)

**Total: 10-13 hours**

## Known Limitations & Future Work

### Current Multi-Grant Limitations
1. **CRITICAL BUG**: EquityLoader creates duplicate lot IDs for multiple grants
2. Many calculators only use the first grant's charitable program settings
3. Scenarios must be manually updated to reference grant-specific lot IDs
4. Some aggregation logic may not properly separate grants
5. No automated lot ID migration for existing scenarios

### Future Enhancements
1. Full per-grant charitable program tracking
2. Grant-specific exercise optimization
3. UI/tools to help users identify correct lot IDs across grants
4. Automatic lot ID resolution for scenarios

## Next Steps

1. Review and approve this plan
2. Create feature branch: `fix/timeline-generator-vesting-events`
3. Implement Phase 1 with frequent commits
4. Run tests after each phase
5. Submit PR with comprehensive testing