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

## Withholding Rate Fields

### Overview
The system uses simplified withholding rates to automatically calculate tax withholdings based on income type. This replaces the previous system of absolute withholding amounts.

### Required Withholding Rate Fields
- **regular_income_withholding_rate**: Combined withholding rate for W2 wages, interest, dividends, and bonuses
- **supplemental_income_withholding_rate**: Combined withholding rate for stock compensation (NSO exercises, RSU vesting)

### Calculating Your Withholding Rates

**Regular Income Withholding Rate** typically includes:
- Federal Income Tax (varies by bracket: 10%, 12%, 22%, 24%, 32%, 35%, 37%)
- Medicare Tax (1.45%)
- Additional Medicare Tax (0.9% above $200k single / $250k married)
- Social Security Tax (6.2% up to wage cap ~$176k)
- State Income Tax (varies by state)
- State Disability Insurance (varies by state)

**Supplemental Income Withholding Rate** typically includes:
- Federal Supplemental Tax (22% or 37% above $1M)
- Medicare Tax (1.45%)
- Additional Medicare Tax (0.9% above thresholds)
- Social Security Tax (6.2% up to wage cap)
- State Supplemental Tax (varies by state)
- State Disability Insurance (varies by state)

### Example Calculations

**California High-Income Example:**
```
Regular Income Rate: 37.9%
= Federal (24.6%) + Medicare (1.45%) + Additional Medicare (0.9%) + 
  Social Security (6.2%) + CA State (8.1%) + CA SDI (1.2%)

Supplemental Income Rate: 36.4%
= Federal Supplemental (22%) + Medicare (1.45%) + Additional Medicare (0.9%) + 
  Social Security (6.2%) + CA Supplemental (10.23%) + CA SDI (1.2%)
```

**Generic Example (Template Values):**
```
Regular Income Rate: 35%
Supplemental Income Rate: 33%
```

### How Withholding Rates Are Applied

1. **Regular Income**: Applied to W2 wages, spouse income, interest, dividends, and bonuses
2. **Supplemental Income**: Applied to NSO bargain elements and RSU vesting income
3. **Total Withholding**: Sum of both calculations plus any quarterly estimated payments

## Determining Your Rates

To fill in your profile:

1. **Federal Tax Rate**: Find your marginal bracket based on expected taxable income
2. **Federal LTCG Rate**: Use 0.20 if high income, 0.15 if middle income, 0.0 if low income
3. **State Rates**: Look up your state's tax rates (California residents typically use 0.093 for both)
4. **FICA**: Use 0.0765 if income under ~$160k, otherwise 0.0145
5. **Additional Medicare**: Use 0.009 if single with income >$200k or married >$250k
6. **NIIT**: Use 0.038 if you meet the income thresholds above
7. **Withholding Rates**: Calculate combined rates for regular and supplemental income as shown above

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