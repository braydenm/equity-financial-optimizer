"""
Tax constants for 2025 tax year calculations.

This module consolidates all tax-related constants used throughout the equity financial optimizer.
The structure is designed to be extensible for future multi-year support.

Future enhancement: Add year-indexed dictionaries and accessor functions
to support multi-year projections with appropriate tax rates per year.

Example future API:
    get_federal_brackets(year=2026, filing_status='single')
    get_amt_exemption(year=2026, filing_status='married_filing_jointly')
"""

# Default tax year for calculations
DEFAULT_TAX_YEAR = 2025

# ===== FEDERAL TAX CONSTANTS =====

# Federal Tax Brackets (2025 values)
# Format: (lower_bound, upper_bound, rate)
FEDERAL_TAX_BRACKETS = {
    'single': [
        (0, 11925, 0.10),
        (11926, 48475, 0.12),
        (48476, 103350, 0.22),
        (103351, 197300, 0.24),
        (197301, 250525, 0.32),
        (250526, 626350, 0.35),
        (626351, float('inf'), 0.37)
    ],
    'married_filing_jointly': [
        (0, 23850, 0.10),
        (23851, 96950, 0.12),
        (96951, 206700, 0.22),
        (206701, 394600, 0.24),
        (394601, 501050, 0.32),
        (501051, 752700, 0.35),
        (752701, float('inf'), 0.37)
    ]
}

# Federal Standard Deductions (2025 values)
FEDERAL_STANDARD_DEDUCTION = {
    'single': 15000,
    'married_filing_jointly': 30000
}

# Federal Long-Term Capital Gains Brackets (2025 values)
# Format: (lower_bound, upper_bound, rate)
FEDERAL_LTCG_BRACKETS = {
    'single': [
        (0, 48350, 0.00),   # 0% bracket
        (48351, 533400, 0.15),  # 15% bracket
        (533401, float('inf'), 0.20)  # 20% bracket
    ],
    'married_filing_jointly': [
        (0, 96700, 0.00),    # 0% bracket
        (96701, 600050, 0.15),   # 15% bracket
        (600051, float('inf'), 0.20)  # 20% bracket
    ]
}

# ===== AMT CONSTANTS =====

# AMT Exemption Amounts (2025 values)
AMT_EXEMPTION_AMOUNT = {
    'single': 88100,
    'married_filing_jointly': 137000
}

# AMT Phaseout Thresholds (2025 values)
AMT_PHASEOUT_THRESHOLD = {
    'single': 649570,
    'married_filing_jointly': 1113120
}

# AMT Phaseout Rate
AMT_PHASEOUT_RATE = 0.25  # 25 cents per dollar of income above threshold

# AMT Tax Rates
AMT_RATE_LOW = 0.26   # 26% on first $239,900
AMT_RATE_HIGH = 0.28  # 28% on amounts above
AMT_THRESHOLD = 239900  # Threshold between 26% and 28% rates

# ===== CALIFORNIA STATE TAX CONSTANTS =====

# California Tax Brackets (2025 values)
# Note: California has different brackets for single vs married filing jointly
# Format: (lower_bound, upper_bound, rate) - different from federal brackets
CALIFORNIA_TAX_BRACKETS = {
    'single': [
        (0, 10412, 0.01),
        (10413, 24684, 0.02),
        (24685, 38959, 0.04),
        (38960, 54081, 0.06),
        (54082, 68350, 0.08),
        (68351, 349137, 0.093),
        (349138, 418961, 0.103),
        (418962, 698271, 0.113),
        (698272, float('inf'), 0.123)
    ],
    'married_filing_jointly': [
        (0, 20824, 0.01),
        (20825, 49368, 0.02),
        (49369, 77918, 0.04),
        (77919, 108162, 0.06),
        (108163, 136700, 0.08),
        (136701, 698274, 0.093),
        (698275, 837922, 0.103),
        (837923, 1396542, 0.113),
        (1396543, float('inf'), 0.123)
    ]
}

# California Standard Deductions (2025 values)
CALIFORNIA_STANDARD_DEDUCTION = {
    'single': 5809,
    'married_filing_jointly': 11618
}

# California Mental Health Tax
# Additional 1% tax on income over $1 million
CALIFORNIA_MENTAL_HEALTH_TAX_THRESHOLD = 1000000
CALIFORNIA_MENTAL_HEALTH_TAX_RATE = 0.01

# California does not have preferential LTCG rates
# LTCG is taxed as ordinary income in California

# California State Disability Insurance (SDI) - 2025 values
CALIFORNIA_SDI_RATE = 0.012  # 1.2% for 2025 (no wage base limit)

# California supplemental withholding rate (2025)
# Applies to bonuses, stock compensation, and other supplemental wages
CALIFORNIA_SUPPLEMENTAL_WITHHOLDING_RATE = 0.1023  # 10.23% for 2025

# California AMT Parameters (2025 values)
CALIFORNIA_AMT_EXEMPTION = {
    'single': 85084,
    'married_filing_jointly': 109288
}

CALIFORNIA_AMT_RATE = 0.07  # 7% flat rate

CALIFORNIA_AMT_PHASEOUT_START = {
    'single': 328049,
    'married_filing_jointly': 437381
}

CALIFORNIA_AMT_PHASEOUT_RATE = 0.25  # 25 cents per dollar above threshold

# ===== CHARITABLE DEDUCTION LIMITS =====

# Federal AGI Limits for Charitable Deductions (2025 values)
# IMPORTANT: The federal cash donation limit was temporarily increased to 60%
# for tax years 2018-2025. This limit is expected to reset to 50% in 2026
# unless new legislation is passed to extend the increased limit.
# Source: CARES Act and subsequent extensions
FEDERAL_CHARITABLE_AGI_LIMITS = {
    'cash': 0.60,    # 60% of AGI for cash donations (2025 only - expires end of year)
    'stock': 0.30,   # 30% of AGI for appreciated stock donations
}

# California AGI Limits for Charitable Deductions (2025 values)
# California maintains the traditional 50% limit for cash donations
# and does not conform to the temporary federal increase
CALIFORNIA_CHARITABLE_AGI_LIMITS = {
    'cash': 0.50,    # 50% of AGI for cash donations (California standard limit)
    'stock': 0.30,   # 30% of AGI for appreciated stock donations
}

# Carryforward period for excess charitable deductions
CHARITABLE_CARRYFORWARD_YEARS = 5

# Basis Election AGI Limits for Charitable Deductions (2025 values)
# When taxpayers elect to use cost basis instead of FMV for stock donations,
# they receive a higher AGI limit but lower deduction amount
# Source: IRS Publication 526 - Charitable Contributions
FEDERAL_CHARITABLE_BASIS_ELECTION_AGI_LIMITS = {
    'stock': 0.50,   # 50% of AGI for stock donations when using cost basis election
}

# California Basis Election AGI Limits for Charitable Deductions (2025 values)
# California generally follows federal rules for basis election
CALIFORNIA_CHARITABLE_BASIS_ELECTION_AGI_LIMITS = {
    'stock': 0.50,   # 50% of AGI for stock donations when using cost basis election
}

# ===== OTHER TAX CONSTANTS =====

# Net Investment Income Tax (NIIT)
NIIT_RATE = 0.038  # 3.8% on investment income
NIIT_THRESHOLD = {
    'single': 200000,
    'married_filing_jointly': 250000
}

# Additional Medicare Tax
ADDITIONAL_MEDICARE_RATE = 0.009  # 0.9% on high earners
ADDITIONAL_MEDICARE_THRESHOLD = {
    'single': 200000,
    'married_filing_jointly': 250000
}

# Social Security wage base (2025)
SOCIAL_SECURITY_WAGE_BASE = 176100
SOCIAL_SECURITY_RATE = 0.062  # Employee portion

# Medicare rate (no wage limit)
MEDICARE_RATE = 0.0145  # Employee portion

# Federal supplemental withholding rate (2025)
# Applies to bonuses, stock compensation (RSUs, NSOs), and other supplemental wages
FEDERAL_SUPPLEMENTAL_WITHHOLDING_RATE = 0.22  # 22% flat rate

# ===== HOLDING PERIOD CONSTANTS =====

# Days required for long-term capital gains treatment
LTCG_HOLDING_PERIOD_DAYS = 366  # More than 365 days (366+ days)

# ISO qualifying disposition requirements
ISO_QUALIFYING_DISPOSITION_YEARS_FROM_GRANT = 2  # 2 years from grant
ISO_QUALIFYING_DISPOSITION_YEARS_FROM_EXERCISE = 1  # 1 year from exercise

# ===== FUTURE EXTENSIBILITY =====

# When multi-year support is needed, transform to:
# FEDERAL_TAX_BRACKETS_BY_YEAR = {
#     2025: {'single': [...], 'married_filing_jointly': [...]},
#     2026: {'single': [...], 'married_filing_jointly': [...]},
# }
#
# def get_federal_brackets(year=DEFAULT_TAX_YEAR, filing_status='single'):
#     """Get federal tax brackets for a specific year and filing status."""
#     if year not in FEDERAL_TAX_BRACKETS_BY_YEAR:
#         year = DEFAULT_TAX_YEAR
#     return FEDERAL_TAX_BRACKETS_BY_YEAR[year][filing_status]
#
# Similar patterns would apply to other year-dependent constants
