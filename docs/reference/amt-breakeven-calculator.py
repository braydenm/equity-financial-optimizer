"""
2025 AMT BREAKEVEN CALCULATOR - SIMPLIFIED VERSION
=================================================
Analyzes optimal ISO exercise strategies considering Federal and California AMT.
"""

# ==============================================================================
# USER INPUTS - MODIFY ONLY THE PLACEHOLDERS IN THIS SECTION
# ==============================================================================

# Income Information
wages = 100000              # W-2 Box 1 (AFTER 401k/pre-tax deductions)
interest_div_income = 1000  # Total interest and dividend income
ltcg_income = 0            # Long-term capital gains realized in 2025

# ISO Grant Details
iso_shares = 20000         # Total shares available to exercise
iso_strike_price = 5.00    # Exercise price per share
iso_fmv = 15.00           # Current fair market value per share

# Tax Configuration
filing_status = 'single'   # Options: 'single' or 'married_filing_jointly'
include_california = True  # Set False for federal-only analysis

# Analysis Scenarios - specify percentages (0-100) or special keywords
# Special keywords: 'amt_breakeven', 'fed_breakeven', 'ca_breakeven'
scenarios_to_analyze = [0, 25, 50, 75, 100, 'amt_breakeven']

# ==============================================================================
# END OF USER INPUTS
# ==============================================================================

print("=" * 80)
print("2025 AMT BREAKEVEN CALCULATOR")
print("=" * 80)
print("\nASSUMPTIONS:")
print("1. Tax year 2025 with federal tax brackets per IRS Rev. Proc. 2024-40")
print("2. ISOs held for qualifying disposition (>1 year after exercise)")
print("3. No immediate sale - analyzing tax impact of exercise only")
print("4. All taxes paid at year-end (no quarterly estimates)")
print("5. No prior year AMT credits available")
print("6. Standard deduction claimed (no itemization)")
print("7. CA tax brackets estimated with 3.3% inflation from 2024")
print("8. Exercise occurs on single date")
print("9. W-2 income is after 401k/pre-tax deductions")
print("=" * 80)

import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Dict, Tuple, List, Union
import csv
from datetime import datetime

# ==============================================================================
# TAX ENGINE - 2025 TAX CONSTANTS AND CALCULATION FUNCTIONS
# ==============================================================================

# Federal Tax Brackets (2025)
FEDERAL_TAX_BRACKETS = {
    'single': [
        (0, 11925, 0.10), (11926, 48475, 0.12), (48476, 103350, 0.22),
        (103351, 197300, 0.24), (197301, 250525, 0.32), (250526, 626350, 0.35),
        (626351, float('inf'), 0.37)
    ],
    'married_filing_jointly': [
        (0, 23850, 0.10), (23851, 96950, 0.12), (96951, 206700, 0.22),
        (206701, 394600, 0.24), (394601, 487450, 0.32), (487451, 751600, 0.35),
        (751601, float('inf'), 0.37)
    ]
}

# Long-term Capital Gains Tax Brackets
LTCG_RATES = {
    'single': [
        (0, 48350, 0), (48351, 533400, 0.15), (533401, float('inf'), 0.20)
    ],
    'married_filing_jointly': [
        (0, 96700, 0), (96701, 600050, 0.15), (600051, float('inf'), 0.20)
    ]
}

# Standard Deductions
FEDERAL_STANDARD_DEDUCTION = {'single': 15000, 'married_filing_jointly': 30000}

# AMT Parameters
AMT_EXEMPTION_AMOUNT = {'single': 88100, 'married_filing_jointly': 137000}
AMT_PHASEOUT_THRESHOLD = {'single': 626350, 'married_filing_jointly': 1252700}
AMT_THRESHOLD = 239100
AMT_RATE_LOW = 0.26
AMT_RATE_HIGH = 0.28

# Other Federal Tax Parameters
NIIT_THRESHOLD = {'single': 200000, 'married_filing_jointly': 250000}
NIIT_RATE = 0.038
ADDITIONAL_MEDICARE_THRESHOLD = {'single': 200000, 'married_filing_jointly': 250000}
ADDITIONAL_MEDICARE_RATE = 0.009

# California Tax Brackets (2025 estimated with 3.3% inflation)
CA_TAX_BRACKETS = {
    'single': [
        (0, 11110, 0.01), (11111, 26293, 0.02), (26294, 41478, 0.04),
        (41479, 57362, 0.06), (57363, 72523, 0.08), (72524, 370100, 0.093),
        (370101, 444746, 0.103), (444747, 744580, 0.113), (744581, float('inf'), 0.123)
    ],
    'married_filing_jointly': [
        (0, 22220, 0.01), (22221, 52585, 0.02), (52586, 82956, 0.04),
        (82957, 114723, 0.06), (114724, 145047, 0.08), (145048, 740200, 0.093),
        (740201, 889491, 0.103), (889492, 1489160, 0.113), (1489161, float('inf'), 0.123)
    ]
}

# California Standard Deductions
CA_STANDARD_DEDUCTION = {'single': 5540, 'married_filing_jointly': 11080}

# California AMT Parameters
CA_AMT_EXEMPTION = {'single': 85084, 'married_filing_jointly': 109288}
CA_AMT_RATE = 0.07
CA_AMT_PHASEOUT_START = {'single': 328049, 'married_filing_jointly': 437381}
CA_AMT_PHASEOUT_RATE = 0.25

# California Other Taxes
CA_MENTAL_HEALTH_TAX_THRESHOLD = 1000000
CA_MENTAL_HEALTH_TAX_RATE = 0.01
CA_SDI_RATE = 0.012
CA_SDI_WAGE_BASE = float('inf')

@dataclass
class TaxCalculationResult:
    """Complete tax calculation results."""
    # Federal components
    federal_agi: float
    federal_taxable_income: float
    federal_ordinary_tax: float
    federal_ltcg_tax: float
    federal_amt: float
    federal_niit: float
    federal_additional_medicare: float
    is_amt: bool
    amt_credit_generated: float

    # California components
    ca_agi: float
    ca_taxable_income: float
    ca_amti: float
    ca_ordinary_tax: float
    ca_mental_health_tax: float
    ca_amt: float
    is_ca_amt: bool
    ca_sdi: float

    # Totals
    total_federal: float
    total_california: float
    total_tax_liability: float
    effective_rate: float

    # ISO specific
    iso_gain: float
    shares_exercised: int

@dataclass
class ExerciseScenario:
    """Represents a single ISO exercise scenario."""
    description: str
    shares: int
    tax_result: TaxCalculationResult
    exercise_cost: float
    total_cash_needed: float
    additional_tax_vs_baseline: float

# Tax Calculation Functions
def calculate_tax(income: float, brackets: List[Tuple[float, float, float]]) -> float:
    """Calculate tax based on income and tax brackets."""
    if income <= 0:
        return 0
    tax = 0
    for lower, upper, rate in brackets:
        if income > lower:
            taxable_amount = min(upper, income) - lower
            tax += taxable_amount * rate
            if income <= upper:
                break
    return tax

def calculate_ltcg_tax(base_income: float, ltcg: float, ltcg_brackets: Dict, filer_type: str) -> float:
    """Calculate long-term capital gains tax with preferential rates."""
    if ltcg <= 0:
        return 0

    total_income = base_income
    ltcg_tax = 0

    for lower, upper, rate in ltcg_brackets[filer_type]:
        if total_income < upper:
            taxable_in_bracket = min(ltcg, upper - total_income)
            ltcg_tax += taxable_in_bracket * rate
            total_income += taxable_in_bracket
            ltcg -= taxable_in_bracket
            if ltcg <= 0:
                break

    return ltcg_tax

def calculate_amt_exemption(amt_income: float, exemption_amount: float, phaseout_start: float) -> float:
    """Calculate AMT exemption with phaseout."""
    if amt_income <= phaseout_start:
        return exemption_amount
    exemption_phaseout = (amt_income - phaseout_start) * 0.25
    return max(exemption_amount - exemption_phaseout, 0)

def calculate_amt(amt_income: float, ltcg_income: float, exemption: float, filer_type: str) -> float:
    """Calculate AMT with preferential LTCG rates."""
    amt_taxable_income = max(amt_income - exemption, 0)

    if amt_taxable_income == 0:
        return 0

    # Separate ordinary income from LTCG
    ordinary_amt_income = max(amt_taxable_income - ltcg_income, 0)
    amt_ltcg_income = min(ltcg_income, amt_taxable_income)

    # Calculate AMT on ordinary income
    ordinary_amt_tax = calculate_tax(
        ordinary_amt_income,
        [(0, AMT_THRESHOLD, AMT_RATE_LOW), (AMT_THRESHOLD, float('inf'), AMT_RATE_HIGH)]
    )

    # Calculate AMT on LTCG (uses preferential rates)
    ltcg_amt_tax = calculate_ltcg_tax(ordinary_amt_income, amt_ltcg_income, LTCG_RATES, filer_type)

    return ordinary_amt_tax + ltcg_amt_tax

def calculate_comprehensive_tax(
    wages: float,
    interest_div: float,
    ltcg: float,
    iso_shares: int,
    iso_strike: float,
    iso_fmv: float,
    filer_type: str,
    include_state: bool = True
) -> TaxCalculationResult:
    """Master function that calculates all federal and state taxes."""

    # Calculate ISO gain
    iso_gain = iso_shares * (iso_fmv - iso_strike)

    # Federal calculations
    federal_agi = wages + interest_div + ltcg
    federal_taxable_income = max(0, federal_agi - FEDERAL_STANDARD_DEDUCTION[filer_type])

    # Regular federal tax
    ordinary_income = max(0, federal_taxable_income - ltcg)
    federal_ordinary_tax = calculate_tax(ordinary_income, FEDERAL_TAX_BRACKETS[filer_type])
    federal_ltcg_tax = calculate_ltcg_tax(ordinary_income, ltcg, LTCG_RATES, filer_type)
    total_regular_tax = federal_ordinary_tax + federal_ltcg_tax

    # AMT calculation
    amt_income = wages + interest_div + iso_gain + ltcg
    amt_exemption = calculate_amt_exemption(
        amt_income,
        AMT_EXEMPTION_AMOUNT[filer_type],
        AMT_PHASEOUT_THRESHOLD[filer_type]
    )
    federal_amt = calculate_amt(amt_income, ltcg, amt_exemption, filer_type)

    # Determine if AMT applies
    is_amt = federal_amt > total_regular_tax
    federal_tax_before_credits = max(total_regular_tax, federal_amt)

    # AMT credit
    amt_credit_generated = 0
    if is_amt and iso_gain > 0:
        amt_credit_generated = federal_amt - total_regular_tax

    # NIIT
    investment_income = interest_div + ltcg
    agi_for_niit = wages + interest_div + ltcg
    federal_niit = 0
    if agi_for_niit > NIIT_THRESHOLD[filer_type]:
        federal_niit = min(investment_income, agi_for_niit - NIIT_THRESHOLD[filer_type]) * NIIT_RATE

    # Additional Medicare
    federal_additional_medicare = 0
    if wages > ADDITIONAL_MEDICARE_THRESHOLD[filer_type]:
        federal_additional_medicare = (wages - ADDITIONAL_MEDICARE_THRESHOLD[filer_type]) * ADDITIONAL_MEDICARE_RATE

    # Total federal
    total_federal = federal_tax_before_credits + federal_niit + federal_additional_medicare

    # California calculations
    if include_state:
        # Regular CA tax (ISO gain NOT included)
        ca_agi = wages + interest_div + ltcg
        ca_taxable_income = max(0, ca_agi - CA_STANDARD_DEDUCTION[filer_type])
        ca_ordinary_tax = calculate_tax(ca_taxable_income, CA_TAX_BRACKETS[filer_type])

        # Mental Health Tax
        ca_mental_health_tax = 0
        if ca_agi > CA_MENTAL_HEALTH_TAX_THRESHOLD:
            ca_mental_health_tax = (ca_agi - CA_MENTAL_HEALTH_TAX_THRESHOLD) * CA_MENTAL_HEALTH_TAX_RATE

        total_regular_ca_tax = ca_ordinary_tax + ca_mental_health_tax

        # CA AMT (ISO gain IS included)
        ca_amti = wages + interest_div + ltcg + iso_gain
        ca_amt_exemption = CA_AMT_EXEMPTION[filer_type]
        if ca_amti > CA_AMT_PHASEOUT_START[filer_type]:
            ca_amt_exemption -= (ca_amti - CA_AMT_PHASEOUT_START[filer_type]) * CA_AMT_PHASEOUT_RATE
            ca_amt_exemption = max(0, ca_amt_exemption)

        ca_amt = max(0, ca_amti - ca_amt_exemption) * CA_AMT_RATE
        is_ca_amt = ca_amt > total_regular_ca_tax

        # CA payroll taxes
        ca_sdi = wages * CA_SDI_RATE

        # Total California
        total_california = max(total_regular_ca_tax, ca_amt) + ca_sdi
    else:
        ca_agi = 0
        ca_taxable_income = 0
        ca_amti = 0
        ca_ordinary_tax = 0
        ca_mental_health_tax = 0
        ca_amt = 0
        is_ca_amt = False
        ca_sdi = 0
        total_california = 0

    # Combined results
    total_tax_liability = total_federal + total_california
    total_income = wages + interest_div + ltcg + iso_gain
    effective_rate = total_tax_liability / total_income if total_income > 0 else 0

    return TaxCalculationResult(
        federal_agi=federal_agi,
        federal_taxable_income=federal_taxable_income,
        federal_ordinary_tax=federal_ordinary_tax,
        federal_ltcg_tax=federal_ltcg_tax,
        federal_amt=federal_amt,
        federal_niit=federal_niit,
        federal_additional_medicare=federal_additional_medicare,
        is_amt=is_amt,
        amt_credit_generated=amt_credit_generated,
        ca_agi=ca_agi,
        ca_taxable_income=ca_taxable_income,
        ca_amti=ca_amti,
        ca_ordinary_tax=ca_ordinary_tax,
        ca_mental_health_tax=ca_mental_health_tax,
        ca_amt=ca_amt,
        is_ca_amt=is_ca_amt,
        ca_sdi=ca_sdi,
        total_federal=total_federal,
        total_california=total_california,
        total_tax_liability=total_tax_liability,
        effective_rate=effective_rate,
        iso_gain=iso_gain,
        shares_exercised=iso_shares
    )

# ==============================================================================
# ANALYSIS FUNCTIONS - BREAKEVEN CALCULATIONS AND SCENARIO GENERATION
# ==============================================================================

def find_amt_breakeven(wages, interest_div, ltcg, iso_details, filer_type, include_state=True):
    """Find the exact number of ISOs that can be exercised before triggering ANY AMT."""
    max_shares = iso_details['shares']
    strike = iso_details['strike_price']
    fmv = iso_details['fmv']

    if max_shares == 0:
        return 0

    # Check if even 1 share triggers AMT
    one_share = calculate_comprehensive_tax(wages, interest_div, ltcg, 1, strike, fmv, filer_type, include_state)
    if one_share.is_amt or (include_state and one_share.is_ca_amt):
        return 0

    # Check if full exercise doesn't trigger AMT
    full_exercise = calculate_comprehensive_tax(wages, interest_div, ltcg, max_shares, strike, fmv, filer_type, include_state)
    if not full_exercise.is_amt and not (include_state and full_exercise.is_ca_amt):
        return max_shares

    # Binary search for breakeven
    low = 0
    high = max_shares

    while high - low > 1:
        mid = (low + high) // 2
        result = calculate_comprehensive_tax(wages, interest_div, ltcg, mid, strike, fmv, filer_type, include_state)

        if result.is_amt or (include_state and result.is_ca_amt):
            high = mid
        else:
            low = mid

    return low

def find_federal_amt_breakeven(wages, interest_div, ltcg, iso_details, filer_type, include_state=True):
    """Find the exact number of ISOs that can be exercised before triggering FEDERAL AMT only."""
    max_shares = iso_details['shares']
    strike = iso_details['strike_price']
    fmv = iso_details['fmv']

    if max_shares == 0:
        return 0

    # Binary search
    low = 0
    high = max_shares

    while high - low > 1:
        mid = (low + high) // 2
        result = calculate_comprehensive_tax(wages, interest_div, ltcg, mid, strike, fmv, filer_type, include_state)

        if result.is_amt:
            high = mid
        else:
            low = mid

    # Verify the boundary
    if low < max_shares:
        verify = calculate_comprehensive_tax(wages, interest_div, ltcg, low + 1, strike, fmv, filer_type, include_state)
        if not verify.is_amt:
            return low + 1

    return low

def find_ca_amt_breakeven(wages, interest_div, ltcg, iso_details, filer_type):
    """Find the exact number of ISOs that can be exercised before triggering CALIFORNIA AMT only."""
    max_shares = iso_details['shares']
    strike = iso_details['strike_price']
    fmv = iso_details['fmv']

    if max_shares == 0:
        return 0

    # Binary search
    low = 0
    high = max_shares

    while high - low > 1:
        mid = (low + high) // 2
        result = calculate_comprehensive_tax(wages, interest_div, ltcg, mid, strike, fmv, filer_type, True)

        if result.is_ca_amt:
            high = mid
        else:
            low = mid

    # Verify the boundary
    if low < max_shares:
        verify = calculate_comprehensive_tax(wages, interest_div, ltcg, low + 1, strike, fmv, filer_type, True)
        if not verify.is_ca_amt:
            return low + 1

    return low

def generate_scenario(shares, wages, interest_div, ltcg, iso_details, filer_type, include_state, baseline_tax):
    """Generate a single exercise scenario."""
    result = calculate_comprehensive_tax(
        wages, interest_div, ltcg, shares,
        iso_details['strike_price'], iso_details['fmv'],
        filer_type, include_state
    )

    exercise_cost = shares * iso_details['strike_price']
    additional_tax = result.total_tax_liability - baseline_tax
    total_cash = exercise_cost + result.total_tax_liability

    return ExerciseScenario(
        description=f"{shares:,} shares",
        shares=shares,
        tax_result=result,
        exercise_cost=exercise_cost,
        total_cash_needed=total_cash,
        additional_tax_vs_baseline=additional_tax
    )

def create_scenarios_from_input(scenarios_list, iso_details, breakeven_results, wages, interest_div, ltcg, filer_type, include_state):
    """Create scenarios based on user-defined list."""
    scenarios = []

    # Calculate baseline (no exercise)
    baseline = calculate_comprehensive_tax(wages, interest_div, ltcg, 0,
                                         iso_details['strike_price'], iso_details['fmv'],
                                         filer_type, include_state)
    baseline_tax = baseline.total_tax_liability

    for scenario_input in scenarios_list:
        if isinstance(scenario_input, str):
            # Handle special keywords
            if scenario_input == 'amt_breakeven':
                shares = breakeven_results['combined_breakeven']
                description = f"AMT Breakeven ({shares:,} shares)"
            elif scenario_input == 'fed_breakeven':
                shares = breakeven_results['fed_breakeven']
                description = f"Fed AMT Breakeven ({shares:,} shares)"
            elif scenario_input == 'ca_breakeven' and include_state:
                shares = breakeven_results['ca_breakeven']
                description = f"CA AMT Breakeven ({shares:,} shares)"
            else:
                continue
        elif isinstance(scenario_input, (int, float)):
            # Handle percentage inputs
            if 0 <= scenario_input <= 100:
                shares = int(iso_details['shares'] * scenario_input / 100)
                description = f"{scenario_input}% ({shares:,} shares)"
            else:
                continue
        else:
            continue

        # Generate the scenario
        scenario = generate_scenario(shares, wages, interest_div, ltcg, iso_details,
                                   filer_type, include_state, baseline_tax)
        scenario.description = description
        scenarios.append(scenario)

    return scenarios

# ==============================================================================
# VISUALIZATION FUNCTIONS - SIMPLIFIED
# ==============================================================================

def create_simplified_visualizations(scenarios, breakeven_results, iso_details, include_state):
    """Create two simplified charts for tax analysis."""

    # Set up the figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)

    # Chart 1: Tax by Scenario (Stacked Bar)
    scenario_names = [s.description for s in scenarios]
    x_pos = np.arange(len(scenarios))

    federal_tax = [s.tax_result.total_federal for s in scenarios]
    ca_tax = [s.tax_result.total_california for s in scenarios] if include_state else [0] * len(scenarios)

    # Create stacked bars
    bars1 = ax1.bar(x_pos, federal_tax, color='#3498db', label='Federal Tax')
    if include_state:
        bars2 = ax1.bar(x_pos, ca_tax, bottom=federal_tax, color='#f39c12', label='California Tax')

    # Format Chart 1
    ax1.set_xlabel('Exercise Scenario', fontsize=12)
    ax1.set_ylabel('Total Tax ($)', fontsize=12)
    ax1.set_title('Tax Impact by Exercise Scenario', fontsize=14, fontweight='bold')
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(scenario_names, rotation=45, ha='right')
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))
    ax1.legend()
    ax1.grid(True, axis='y', alpha=0.3)
    ax1.set_axisbelow(True)

    # Chart 2: AMT Trigger Analysis
    max_shares = iso_details['shares']
    if max_shares > 0:
        share_points = np.linspace(0, max_shares, 200)
        total_tax = []

        for shares in share_points:
            result = calculate_comprehensive_tax(
                wages, interest_div_income, ltcg_income,
                int(shares), iso_details['strike_price'], iso_details['fmv'],
                filing_status, include_state
            )
            total_tax.append(result.total_tax_liability)

        # Plot total tax curve
        ax2.plot(share_points, total_tax, color='black', linewidth=3, label='Total Tax')

        # Mark breakeven points
        fed_breakeven = breakeven_results['fed_breakeven']
        if 0 < fed_breakeven < max_shares:
            ax2.axvline(x=fed_breakeven, color='#e74c3c', linestyle='--', linewidth=2, label='Fed AMT Trigger')
            ax2.text(fed_breakeven, ax2.get_ylim()[1]*0.9, f'{fed_breakeven:,}',
                    ha='center', va='top', fontsize=10, color='#e74c3c', fontweight='bold')

        if include_state:
            ca_breakeven = breakeven_results['ca_breakeven']
            if 0 < ca_breakeven < max_shares:
                ax2.axvline(x=ca_breakeven, color='#e67e22', linestyle='--', linewidth=2, label='CA AMT Trigger')
                ax2.text(ca_breakeven, ax2.get_ylim()[1]*0.8, f'{ca_breakeven:,}',
                        ha='center', va='top', fontsize=10, color='#e67e22', fontweight='bold')

    # Format Chart 2
    ax2.set_xlabel('Number of ISOs Exercised', fontsize=12)
    ax2.set_ylabel('Total Tax ($)', fontsize=12)
    ax2.set_title('AMT Trigger Points', fontsize=14, fontweight='bold')
    ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_axisbelow(True)

    return fig

# ==============================================================================
# CSV EXPORT FUNCTION
# ==============================================================================

def export_results_to_csv(scenarios, breakeven_results, iso_details, filename='amt_analysis_2025.csv'):
    """Export analysis results to CSV file."""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Header
        writer.writerow(['2025 ISO AMT Analysis'])
        writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M')])
        writer.writerow([])

        # Breakeven Summary
        writer.writerow(['BREAKEVEN SUMMARY'])
        writer.writerow(['Combined AMT Breakeven:', breakeven_results['combined_breakeven']])
        writer.writerow(['Federal AMT Breakeven:', breakeven_results['fed_breakeven']])
        if 'ca_breakeven' in breakeven_results:
            writer.writerow(['California AMT Breakeven:', breakeven_results['ca_breakeven']])
        writer.writerow([])

        # Scenario Details
        writer.writerow(['SCENARIO DETAILS'])
        headers = ['Scenario', 'Shares', 'Exercise Cost', 'Federal Tax', 'CA Tax',
                  'Total Tax', 'Additional Tax', 'Total Cash', 'Fed AMT?', 'CA AMT?']
        writer.writerow(headers)

        for scenario in scenarios:
            writer.writerow([
                scenario.description,
                scenario.shares,
                f"${scenario.exercise_cost:,.0f}",
                f"${scenario.tax_result.total_federal:,.0f}",
                f"${scenario.tax_result.total_california:,.0f}",
                f"${scenario.tax_result.total_tax_liability:,.0f}",
                f"${scenario.additional_tax_vs_baseline:,.0f}",
                f"${scenario.total_cash_needed:,.0f}",
                'Yes' if scenario.tax_result.is_amt else 'No',
                'Yes' if scenario.tax_result.is_ca_amt else 'No'
            ])

    return filename

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def run_analysis():
    """Execute the complete AMT breakeven analysis."""

    # Package inputs
    iso_details = {
        'shares': iso_shares,
        'strike_price': iso_strike_price,
        'fmv': iso_fmv,
    }

    # Display inputs
    print(f"\nYOUR TAX SCENARIO:")
    print(f"  Filing Status: {filing_status.replace('_', ' ').title()}")
    print(f"  W-2 Income: ${wages:,}")
    print(f"  Interest/Dividends: ${interest_div_income:,}")
    print(f"  Capital Gains: ${ltcg_income:,}")
    print(f"\nISO DETAILS:")
    print(f"  Shares Available: {iso_shares:,}")
    print(f"  Strike Price: ${iso_strike_price}")
    print(f"  Current FMV: ${iso_fmv}")
    print(f"  Gain per Share: ${iso_fmv - iso_strike_price:.2f}")
    print(f"  Total Potential Gain: ${iso_shares * (iso_fmv - iso_strike_price):,.0f}")
    print(f"\nANALYSIS OPTIONS:")
    print(f"  Include California: {'Yes' if include_california else 'No (Federal Only)'}")
    print(f"  Scenarios: {scenarios_to_analyze}")
    print("=" * 80)

    # Find breakeven points
    print("\n[*] CALCULATING BREAKEVEN POINTS...")

    combined_breakeven = find_amt_breakeven(
        wages, interest_div_income, ltcg_income, iso_details, filing_status, include_california
    )

    fed_breakeven = find_federal_amt_breakeven(
        wages, interest_div_income, ltcg_income, iso_details, filing_status, include_california
    )

    ca_breakeven = iso_shares  # Default to max if not including CA
    if include_california:
        ca_breakeven = find_ca_amt_breakeven(
            wages, interest_div_income, ltcg_income, iso_details, filing_status
        )

    breakeven_results = {
        'combined_breakeven': combined_breakeven,
        'fed_breakeven': fed_breakeven,
        'ca_breakeven': ca_breakeven
    }

    # Display breakeven results
    print(f"\n[*] BREAKEVEN ANALYSIS RESULTS:")
    print(f"  Combined AMT Breakeven: {combined_breakeven:,} shares ({combined_breakeven/iso_shares*100:.1f}%)")
    print(f"  Federal AMT Breakeven: {fed_breakeven:,} shares ({fed_breakeven/iso_shares*100:.1f}%)")
    if include_california:
        print(f"  California AMT Breakeven: {ca_breakeven:,} shares ({ca_breakeven/iso_shares*100:.1f}%)")

        # Identify limiting factor
        if ca_breakeven < fed_breakeven:
            print(f"  [!] California AMT is the limiting factor")
        elif fed_breakeven < ca_breakeven:
            print(f"  [!] Federal AMT is the limiting factor")
        else:
            print(f"  [!] Both AMTs trigger at the same point")

    # Generate scenarios
    print(f"\n[*] GENERATING SCENARIOS...")
    scenarios = create_scenarios_from_input(
        scenarios_to_analyze, iso_details, breakeven_results,
        wages, interest_div_income, ltcg_income, filing_status, include_california
    )

    # Display scenario comparison
    print(f"\n[*] SCENARIO COMPARISON:")
    print("-" * 120)
    if include_california:
        print(f"{'Scenario':<25} {'Shares':>10} {'Exercise':>12} {'Fed Tax':>12} {'CA Tax':>12} {'Total Tax':>12} {'Addl Tax':>12} {'Cash Need':>12}")
    else:
        print(f"{'Scenario':<25} {'Shares':>10} {'Exercise':>12} {'Fed Tax':>12} {'Total Tax':>12} {'Addl Tax':>12} {'Cash Need':>12}")
    print("-" * 120)

    for scenario in scenarios:
        if include_california:
            print(f"{scenario.description:<25} {scenario.shares:>10,} "
                  f"${scenario.exercise_cost:>11,.0f} "
                  f"${scenario.tax_result.total_federal:>11,.0f} "
                  f"${scenario.tax_result.total_california:>11,.0f} "
                  f"${scenario.tax_result.total_tax_liability:>11,.0f} "
                  f"${scenario.additional_tax_vs_baseline:>11,.0f} "
                  f"${scenario.total_cash_needed:>11,.0f}")
        else:
            print(f"{scenario.description:<25} {scenario.shares:>10,} "
                  f"${scenario.exercise_cost:>11,.0f} "
                  f"${scenario.tax_result.total_federal:>11,.0f} "
                  f"${scenario.tax_result.total_tax_liability:>11,.0f} "
                  f"${scenario.additional_tax_vs_baseline:>11,.0f} "
                  f"${scenario.total_cash_needed:>11,.0f}")

        # Add AMT indicators
        amt_notes = []
        if scenario.tax_result.is_amt:
            amt_notes.append("Federal AMT applies")
        if include_california and scenario.tax_result.is_ca_amt:
            amt_notes.append("CA AMT applies")
        if amt_notes:
            print(f"  -> {', '.join(amt_notes)}")

    # Key insights
    print(f"\n[*] KEY INSIGHTS:")

    # Find scenario with highest tax efficiency (lowest effective rate before hitting AMT)
    best_scenario = None
    for scenario in scenarios:
        if scenario.shares > 0 and not scenario.tax_result.is_amt and not scenario.tax_result.is_ca_amt:
            if best_scenario is None or scenario.shares > best_scenario.shares:
                best_scenario = scenario

    if best_scenario:
        print(f"  [+] Maximum shares without AMT: {best_scenario.shares:,}")
        print(f"      Effective tax rate: {best_scenario.tax_result.effective_rate:.1%}")

    # Cash requirements insight
    max_scenario = max(scenarios, key=lambda s: s.shares)
    if max_scenario.total_cash_needed > 100000:
        print(f"  [$] Full exercise requires ${max_scenario.total_cash_needed:,.0f} in cash")

    # AMT credit insight
    if max_scenario.tax_result.amt_credit_generated > 0:
        print(f"  [+] Full exercise generates ${max_scenario.tax_result.amt_credit_generated:,.0f} in AMT credits")

    # Multi-year strategy
    if combined_breakeven < iso_shares * 0.5:
        print(f"  [*] Consider spreading exercise over multiple years to stay under AMT")

    # Create visualizations
    print(f"\n[*] GENERATING VISUALIZATIONS...")
    fig = create_simplified_visualizations(scenarios, breakeven_results, iso_details, include_california)

    # Export results
    csv_file = export_results_to_csv(scenarios, breakeven_results, iso_details)
    print(f"[+] Results exported to {csv_file}")

    # Save and show visualization
    fig.savefig('amt_analysis_2025.png', dpi=300, bbox_inches='tight', facecolor='white')
    print(f"[+] Visualization saved to amt_analysis_2025.png")

    plt.show()

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    return {
        'scenarios': scenarios,
        'breakeven_results': breakeven_results,
        'figure': fig
    }

# Execute the analysis
if __name__ == "__main__":
    results = run_analysis()
