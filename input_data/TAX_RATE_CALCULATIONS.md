# Tax Rate Components

This document explains the individual tax rate components required in user profiles.

## Overview

The Equity Financial Optimizer uses a component-based tax calculation system that applies progressive tax brackets rather than flat rates. Your profile must include separate federal and state tax rates, which the system uses to calculate taxes accurately at the annual level.

## Required Tax Rate Fields

### Federal Rates
- **federal_tax_rate**: Your marginal federal income tax bracket (e.g., 0.37 for 37%)
- **federal_ltcg_rate**: Your nominal federal long-term capital gains rate (0.20 for 20%)
  - Note: The system actually applies 0%/15%/20% brackets based on total income

### State Rates  
- **state_tax_rate**: Your state's marginal income tax rate (e.g., 0.093 for California's 9.3%)
- **state_ltcg_rate**: Your state's capital gains rate (often same as state income rate)

### FICA and Medicare
- **fica_tax_rate**: Social Security + Medicare base rate
  - Use 0.0765 (7.65%) if below Social Security wage cap (~$160k)
  - Use 0.0145 (1.45%) if above cap (Medicare only)
- **additional_medicare_rate**: 0.009 (0.9%) for high earners
  - Applies to income over $200k (single) or $250k (married)

### Investment Tax
- **niit_rate**: 0.038 (3.8%) Net Investment Income Tax
  - Applies when AGI exceeds $200k (single) or $250k (married)

## How These Rates Are Used

The system does NOT simply multiply your income by these rates. Instead:

1. **Progressive Brackets**: Federal and state income taxes use progressive brackets
2. **LTCG Brackets**: Long-term capital gains use 0%/15%/20% federal brackets based on total income
3. **AMT Calculation**: Determined annually by comparing regular tax vs Alternative Minimum Tax
4. **Annual Aggregation**: All tax components from the year's actions are aggregated before calculating tax

## Determining Your Rates

To fill in your profile:

1. **Federal Tax Rate**: Find your marginal bracket based on expected taxable income
2. **Federal LTCG Rate**: Use 0.20 if high income, 0.15 if middle income, 0.0 if low income
3. **State Rates**: Look up your state's tax rates (California residents typically use 0.093 for both)
4. **FICA**: Use 0.0765 if income under ~$160k, otherwise 0.0145
5. **Additional Medicare**: Use 0.009 if single with income >$200k or married >$250k
6. **NIIT**: Use 0.038 if you meet the income thresholds above

## Example for High-Income California Resident

```json
"federal_tax_rate": 0.37,
"federal_ltcg_rate": 0.20,
"state_tax_rate": 0.093,
"state_ltcg_rate": 0.093,
"fica_tax_rate": 0.0145,
"additional_medicare_rate": 0.009,
"niit_rate": 0.038
```

Remember: These are just the rate inputs. The actual tax calculation uses sophisticated bracket calculations to determine your true tax liability.