# Data Contract for User Profiles

This document defines the canonical format for user profile data in the Equity Financial Optimizer.

## Design Principles

1. **Clarity**: Field names should be self-explanatory
2. **Consistency**: Same concept = same field name everywhere
3. **Completeness**: Include all fields needed for calculations
4. **Simplicity**: No redundant or calculated fields
5. **Type Safety**: Numbers are numbers, dates are ISO strings
6. **Documentation**: Separate from data (this file, not in JSON)

## Profile Structure

```json
{
  "metadata": {
    "profile_version": "2.0",
    "created_date": "2024-01-01",
    "last_updated": "2024-01-01"
  },

  "personal_information": {
    "tax_filing_status": "single|married_filing_jointly|married_filing_separately|head_of_household",
    "state_of_residence": "California",
    "age": 35,
    "spouse_age": 32,  // optional
    "dependents_count": 2,  // optional

    // Tax rates (as decimals)
    "federal_tax_rate": 0.37,
    "state_tax_rate": 0.093,
    "fica_tax_rate": 0.0765,  // Social Security + Medicare
    "additional_medicare_rate": 0.009,  // On high earners
    "niit_rate": 0.038,  // Net Investment Income Tax

    // Computed rates for convenience
    "ordinary_income_rate": 0.50,  // All taxes on ordinary income
    "ltcg_rate": 0.35,  // All taxes on long-term capital gains
    "stcg_rate": 0.50   // Same as ordinary income
  },

  "income": {
    "annual_w2_income": 350000,
    "spouse_w2_income": 150000,  // optional
    "bonus_expected": 50000,
    "interest_income": 5000,
    "dividend_income": 12000,
    "other_income": 0
  },

  "equity_position": {
    "company": "Company Name",

    "original_grants": [
      {
        "grant_id": "GRANT-001",
        "grant_date": "2022-01-15",
        "type": "ISO|NSO|RSU",
        "total_shares": 100000,
        "strike_price": 2.50,  // 0 for RSUs
        "vesting_start_date": "2022-01-15",
        "vesting_schedule": "4_year_monthly_with_cliff",
        "cliff_months": 12
      }
    ],

    "exercised_lots": [
      {
        "lot_id": "LOT-001",
        "grant_id": "GRANT-001",  // Links to original grant
        "exercise_date": "2023-06-15",
        "shares": 10000,
        "type": "ISO|NSO|RSU",
        "strike_price": 2.50,
        "fmv_at_exercise": 10.00,
        "cost_basis": 2.50,  // For NSOs, includes ordinary income
        "taxes_paid": 0,  // Withholding or estimated taxes
        "amt_adjustment": 75000  // For ISOs only
      }
    ],

    "vested_unexercised": {
      "total_shares": 30000,
      "iso_shares": 20000,
      "nso_shares": 10000,
      "rsu_shares": 0
    },

    "unvested": {
      "total_shares": 45000,
      "monthly_vesting_rate": 2083,
      "next_vest_date": "2024-06-15",
      "final_vest_date": "2026-01-15"
    },

    "current_prices": {
      "last_409a_price": 25.00,
      "last_409a_date": "2024-01-01",
      "tender_offer_price": 56.00,  // If applicable
      "expected_409a_price": 30.00,  // Projection
      "expected_409a_date": "2024-07-01"
    }
  },

  "tax_situation": {
    "prior_year_taxes": {
      "year": 2023,
      "agi": 400000,
      "total_tax_paid": 150000,
      "amt_paid": 12000,
      "effective_rate": 0.40
    },

    "carryforwards": {
      "amt_credit": 15000,
      "capital_loss": 0,
      "charitable_deduction": 0
    },

    "estimated_taxes": {
      "federal_withholding": 150000,
      "state_withholding": 50000,
      "quarterly_payments": 0
    }
  },

  "financial_position": {
    "liquid_assets": {
      "cash": 50000,
      "taxable_investments": 300000,
      "retirement_accounts": 200000,
      "crypto": 50000,
      "total": 600000
    },

    "illiquid_assets": {
      "real_estate_equity": 250000,
      "private_investments": 0,
      "unvested_equity_value": 800000  // At current 409A
    },

    "liabilities": {
      "mortgage": 500000,
      "other_debt": 0,
      "total": 500000
    },

    "monthly_cash_flow": {
      "income": 41667,
      "expenses": 16500,
      "savings": 25167
    }
  },

  "goals_and_constraints": {
    "primary_goals": [
      {
        "goal": "maximize_charitable_impact",
        "priority": 1,
        "timeline": "ongoing"
      },
      {
        "goal": "home_purchase",
        "priority": 2,
        "timeline": "2_years",
        "amount_needed": 400000
      }
    ],

    "liquidity_needs": {
      "emergency_fund": 100000,
      "near_term_cash": 200000,  // Next 12 months
      "exercise_reserves": 100000,
      "tax_reserves": 150000
    },

    "risk_tolerance": "conservative|moderate|aggressive",
    "concentration_limit": 0.50,  // Max % in single stock
    "time_horizon_years": 10
  },

  "charitable_giving": {
    "pledge_percentage": 0.50,  // Of equity
    "company_match_ratio": 3.0,
    "donation_window_months": 36  // After liquidity event
  },

  "market_assumptions": {
    "scenarios": [
      {
        "name": "bear",
        "probability": 0.20,
        "price_change": -0.50,
        "timeline_years": 2
      },
      {
        "name": "base",
        "probability": 0.60,
        "price_change": 0.50,
        "timeline_years": 2
      },
      {
        "name": "bull",
        "probability": 0.20,
        "price_change": 2.00,
        "timeline_years": 2
      }
    ],

    "liquidity_timeline": {
      "ipo_earliest": 2026,
      "ipo_expected": 2028,
      "acquisition_probability": 0.30,
      "secondary_sales_frequency": "annual"
    }
  },

  "decision_parameters": {
    "tender_participation": {
      "max_shares_allowed": 20000,  // Company limit
      "target_proceeds": 500000,
      "max_percentage": 0.20  // Of vested shares
    },

    "exercise_strategy": "early_exercise|wait_until_liquid|amt_optimize",
    "donation_strategy": "immediate|multi_year|opportunistic"
  }
}
```

## Field Definitions

### metadata
- `profile_version`: Schema version for migrations
- `created_date`: ISO date when profile was created
- `last_updated`: ISO date of last modification

### personal_information
- All tax rates as decimals (0.37 not 37%)
- `ordinary_income_rate`: Combined federal + state + FICA + NIIT
- `ltcg_rate`: Combined long-term capital gains rate
- `stcg_rate`: Same as ordinary_income_rate

### equity_position
- `exercised_lots`: Array of all exercised share lots
- Each lot must have `shares` (not `shares_available`)
- `cost_basis`: Strike price for ISOs, exercise price for NSOs
- `type` must be "ISO", "NSO", or "RSU"

### Required Fields
These fields must always be present:
- metadata.profile_version
- personal_information.tax_filing_status
- personal_information.state_of_residence
- personal_information.ordinary_income_rate
- personal_information.ltcg_rate
- equity_position.company
- equity_position.exercised_lots (can be empty array)

### Optional Fields
All other fields are optional but should follow the schema when present.

## Migration from v1.x

To migrate existing profiles:
1. Rename `company_equity_position` → `equity_position`
2. Rename `total_ordinary_income_rate` → `ordinary_income_rate`
3. Rename `total_ltcg_rate` → `ltcg_rate`
4. Remove all `_note` fields
5. Convert string numbers to actual numbers
6. Ensure all lots have `shares` field
7. Update version to "2.0"
