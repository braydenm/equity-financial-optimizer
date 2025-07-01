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
    "tax_filing_status": "single|married_filing_jointly|married_filing_separately|head_of_household", // Extensive testing for married_filing_separately. No testing or implementation for married_filing_separately or head_of_household.
    "state_of_residence": "California", // Other states not yet supported / tested
    "age": 35, // currently used
    "spouse_age": 32,  // optional
    "dependents_count": 2,  // Not currently used

    // Tax rates (as decimals)
    "federal_tax_rate": 0.37,
    "federal_ltcg_rate": 0.20,  // Federal LTCG rate (0%, 15%, or 20% based on income)
    "state_tax_rate": 0.093,
    "state_ltcg_rate": 0.093,  // State LTCG rate (often same as state rate)
    "fica_tax_rate": 0.0765,  // Social Security + Medicare
    "additional_medicare_rate": 0.009,  // On high earners
    "niit_rate": 0.038  // Net Investment Income Tax
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

    "grants": [
      {
        "grant_id": "GRANT-001",
        "grant_date": "2022-01-15",
        "type": "ISO|NSO|RSU",
        "total_shares": 100000,  // or "total_options" for compatibility
        "isos": 50000,  // ISO portion of total
        "nsos": 50000,  // NSO portion of total
        "strike_price": 2.50,  // 0 for RSUs
        "vesting_start_date": "2022-01-15",
        "expiration_date": "2032-01-15",

        "charitable_program": {
          "pledge_percentage": 0.50,  // 0.50 = 50% pledge, 0.25 = 25% pledge, 0 = no program
          "company_match_ratio": 3.0,  // 3.0 = 3:1 match, 1.0 = 1:1 match
          "notes": "50% pledge with 3:1 match for employees joining before 2024"
        },

        // NEW: Actual vesting data - this is the source of truth
        "vesting_status": {
          "vested_unexercised": {
            "iso": 20000,
            "nso": 10000
          },
          "unvested": {
            "total_shares": 20000,
            "vesting_calendar": [
              {"date": "2025-07-01", "shares": 2000, "share_type": "ISO"},
              {"date": "2025-10-01", "shares": 2000, "share_type": "NSO"}
              // ... more vesting events
            ]
          }
        }
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

    // DEPRECATED: vested_unexercised and unvested have been moved into each grant's vesting_status
    // These top-level fields should no longer be used

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
      "quarterly_payments": 0,
      "regular_income_withholding_rate": 0.35,
      "supplemental_income_withholding_rate": 0.33
    }
  },

  "_comments": {
    "regular_income_withholding_rate": "35% (Example Rate) = Federal Income Tax (varies by bracket) + Medicare (1.45%) + Social Security (6.2% up to wage cap) + State Tax (varies by state) + State SDI (varies by state)",
    "supplemental_income_withholding_rate": "33% (Example Rate) = Federal Supplemental Tax (22% or 37%) + Medicare (1.45%) + Social Security (6.2% up to wage cap) + State Supplemental Tax (varies by state) + State SDI (varies by state)"
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
      "unvested_equity_value": 800000  // At current 409A. Not used.
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

  // MIGRATION NOTE: charitable_giving has been moved to per-grant level
  // Each grant in grants now has its own charitable_program object
  // This reflects that charitable programs are determined by employment timing, not user choice
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
- `federal_tax_rate`: Federal marginal tax rate
- `federal_ltcg_rate`: Federal LTCG rate (will be overridden by bracket calculation)
- `state_tax_rate`: State marginal tax rate
- `state_ltcg_rate`: State LTCG rate (usually same as state rate)
- Tax calculations now use proper brackets, not combined flat rates

### equity_position
### tax_situation
- `regular_income_withholding_rate`: Combined withholding rate for W2 wages, interest, dividends, and bonuses (as decimal)
- `supplemental_income_withholding_rate`: Combined withholding rate for stock compensation income (as decimal)
- `quarterly_payments`: Estimated tax payments made quarterly

### equity_position
- `grants`: Array of all equity grants
  - Each grant must have `vesting_status` with actual vesting data
  - `vesting_status.vested_unexercised`: Shares vested but not yet exercised (by type)
  - `vesting_status.unvested.vesting_calendar`: Future vesting events with dates and share counts
  - DO NOT use `_vesting_schedule_DEPRECATED` or `_cliff_months_DEPRECATED` fields
  - Validation: exercised (from lots) + vested_unexercised + unvested must equal total_shares/total_options

- `exercised_lots`: Array of all exercised share lots
  - Each lot must have `shares` (not `shares_available`)
  - Each lot must have `grant_id` linking to the original grant
  - `cost_basis`: Strike price for ISOs, exercise price for NSOs
  - `type` must be "ISO", "NSO", or "RSU"

### Required Fields
These fields must always be present:
- metadata.profile_version
- personal_information.tax_filing_status
- personal_information.state_of_residence
- personal_information.federal_tax_rate
- personal_information.federal_ltcg_rate
- personal_information.state_tax_rate
- personal_information.state_ltcg_rate
- equity_position.company
- equity_position.exercised_lots (can be empty array)

### Optional Fields
All other fields are optional but should follow the schema when present.
