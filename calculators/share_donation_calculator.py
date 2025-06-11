"""
Share Donation Calculator - Tax-optimized charitable giving calculations.

This calculator handles the complex tax implications of donating shares vs cash,
including AGI limitations, carryforward rules, and company matching programs.
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass


@dataclass
class DonationResult:
    """Results from a donation calculation."""
    donation_value: float           # Fair market value of donation
    tax_deduction: float           # Amount deductible this year
    tax_savings: float             # Actual tax saved this year
    carryforward: float            # Excess deduction to carry forward
    company_match: float           # Company match amount
    total_impact: float            # Total to charity (donation + match)
    net_cost: float                # Cost to donor after tax benefits
    impact_multiple: float         # Total impact / net cost
    deduction_type: str            # '30%' or '50%' limit
    warnings: List[str]            # Any special considerations


class ShareDonationCalculator:
    """
    Pure share donation tax calculations.
    
    This calculator handles:
    - Direct share donations (avoid capital gains)
    - AGI-based deduction limitations
    - Carryforward calculations
    - Company match programs
    - Comparison with sell-and-donate strategies
    """
    
    # Tax year-specific parameters
    AGI_LIMIT_STOCK = 0.30  # 30% of AGI for appreciated stock
    AGI_LIMIT_CASH = 0.50   # 50% of AGI for cash (60% federal in 2025, but CA is 50%)
    CARRYFORWARD_YEARS = 5  # Maximum carryforward period
    
    @staticmethod
    def calculate_donation(
        agi: float,
        tax_rate: float,
        existing_deductions: float = 0.0,
        company_match_ratio: float = 0.0,
        pledge_percentage: float = 0.5,
        eligible_vested_shares: int = 0,
        shares_already_donated: int = 0,
        # Cash donation parameters
        cash_amount: Optional[float] = None,
        # Share donation parameters
        shares: Optional[int] = None,
        share_price: Optional[float] = None,
        cost_basis: Optional[float] = None,
        holding_period_months: Optional[int] = None,
        asset_type: Optional[str] = None,  # 'ISO', 'NSO', 'RSU', 'STOCK'
    ) -> DonationResult:
        """
        Unified donation calculator that handles cash, shares, or both flexibly.
        
        This function merges cash and share donation logic to handle:
        - Cash only donations (50% AGI limit, no company match)
        - Share only donations (30% AGI limit for LTCG, company match applies)
        - Combined cash + share donations in same year (optimized AGI usage)
        
        Args:
            agi: Adjusted gross income
            tax_rate: Marginal tax rate (decimal)
            existing_deductions: Other charitable deductions this year
            company_match_ratio: Company match ratio (e.g., 3.0 for 3:1, applies to shares only)
            pledge_percentage: Pledge percentage (e.g., 0.5 for 50%)
            eligible_vested_shares: Total vested shares eligible for matching
            shares_already_donated: Shares already donated (reduces match eligibility)
            cash_amount: Cash amount to donate (optional)
            shares: Number of shares to donate (optional)
            share_price: Current fair market value per share
            cost_basis: Cost basis per share
            holding_period_months: How long shares have been held
            asset_type: Type of equity ('ISO', 'NSO', 'RSU', 'STOCK')
            
        Returns:
            DonationResult with combined calculations
            
        Raises:
            ValueError: If neither cash nor share parameters are provided
        """
        # Determine what donations are being made
        has_cash = cash_amount is not None and cash_amount > 0
        has_shares = all(param is not None for param in [shares, share_price, cost_basis, holding_period_months, asset_type]) and shares > 0
        
        if not has_cash and not has_shares:
            raise ValueError("Must provide either cash_amount or complete share parameters (or both)")
        
        warnings = []
        total_donation_value = 0.0
        total_tax_deduction = 0.0
        total_tax_savings = 0.0
        total_carryforward = 0.0
        company_match = 0.0
        
        # Track AGI limits and usage
        agi_limit_30 = ShareDonationCalculator.AGI_LIMIT_STOCK * agi  # For appreciated stock
        agi_limit_50 = ShareDonationCalculator.AGI_LIMIT_CASH * agi   # For cash
        remaining_30_bucket = max(0, agi_limit_30 - existing_deductions)
        remaining_50_bucket = max(0, agi_limit_50 - existing_deductions)
        
        # Process share donation first (to prioritize company match)
        if has_shares:
            share_donation_value = shares * share_price
            total_donation_value += share_donation_value
            
            # Check holding period for deduction eligibility
            if holding_period_months < 12:
                # Short-term holdings
                if asset_type in ['ISO', 'NSO']:
                    warnings.append(f"Donating {asset_type} held <1 year may trigger ordinary income tax")
                    if asset_type == 'ISO':
                        warnings.append("ISO donation <1 year from exercise is a disqualifying disposition")
                
                # Short-term donations limited to cost basis, use 50% bucket
                share_deduction_value = shares * cost_basis
                share_bucket = '50%'
                available_bucket = remaining_50_bucket
            else:
                # Long-term appreciated property, use 30% bucket
                share_deduction_value = share_donation_value
                share_bucket = '30%'
                available_bucket = remaining_30_bucket
            
            # Apply share deduction against appropriate bucket
            share_deduction_used = min(share_deduction_value, available_bucket)
            share_carryforward = share_deduction_value - share_deduction_used
            
            if share_carryforward > 0:
                warnings.append(f"${share_carryforward:,.0f} from shares will carry forward")
            
            # Update bucket usage
            if share_bucket == '30%':
                remaining_30_bucket -= share_deduction_used
            else:
                remaining_50_bucket -= share_deduction_used
            
            total_tax_deduction += share_deduction_used
            total_carryforward += share_carryforward
            
            # Calculate company match (only applies to shares)
            remaining_eligible_shares = max(0, int(pledge_percentage * eligible_vested_shares) - shares_already_donated)
            max_match_value = remaining_eligible_shares * share_price * company_match_ratio
            company_match = min(share_donation_value * company_match_ratio, max_match_value)
        
        # Process cash donation
        if has_cash:
            total_donation_value += cash_amount
            
            # Cash uses 50% AGI bucket
            cash_deduction_used = min(cash_amount, remaining_50_bucket)
            cash_carryforward = cash_amount - cash_deduction_used
            
            if cash_carryforward > 0:
                warnings.append(f"${cash_carryforward:,.0f} from cash will carry forward")
            
            total_tax_deduction += cash_deduction_used
            total_carryforward += cash_carryforward
        
        # Calculate tax savings and costs
        total_tax_savings = total_tax_deduction * tax_rate
        total_impact = total_donation_value + company_match
        
        # Calculate net cost
        if has_shares:
            # For shares, net cost considers foregone after-tax value
            capital_gains = shares * (share_price - cost_basis)
            if holding_period_months >= 12:
                capital_gains_tax = capital_gains * 0.35 if capital_gains > 0 else 0  # Assumed LTCG rate
            else:
                capital_gains_tax = capital_gains * tax_rate if capital_gains > 0 else 0
            share_after_tax_value = (shares * share_price) - capital_gains_tax
        else:
            share_after_tax_value = 0
        
        # Net cost = (cash donated + share after-tax value) - tax savings
        net_cost = (cash_amount or 0) + share_after_tax_value - total_tax_savings
        
        # Impact multiple
        impact_multiple = total_impact / net_cost if net_cost > 0 else float('inf')
        
        # Determine deduction type for display
        if has_cash and has_shares:
            deduction_type = "Mixed (30%/50%)"
        elif has_shares and holding_period_months >= 12:
            deduction_type = "30%"
        else:
            deduction_type = "50%"
        
        return DonationResult(
            donation_value=total_donation_value,
            tax_deduction=total_tax_deduction,
            tax_savings=total_tax_savings,
            carryforward=total_carryforward,
            company_match=company_match,
            total_impact=total_impact,
            net_cost=net_cost,
            impact_multiple=impact_multiple,
            deduction_type=deduction_type,
            warnings=warnings
        )
    
    # REMOVED: calculate_share_donation() and calculate_cash_donation()
    # These functions have been replaced by the unified calculate_donation() function above.
    # The unified function handles both cash and share donations, including combined scenarios,
    # with better composability for the projection system.
    #
    # For share donations, use: calculate_donation(shares=X, share_price=Y, cost_basis=Z, ...)
    # For cash donations, use: calculate_donation(cash_amount=X, ...)
    # For combined donations, use: calculate_donation(cash_amount=X, shares=Y, share_price=Z, ...)
    
    @staticmethod
    def calculate_sell_then_donate(
        shares: int,
        share_price: float,
        cost_basis: float,
        holding_period_months: int,
        donation_percentage: float,  # What % of proceeds to donate
        agi: float,
        tax_rate: float,
        ltcg_rate: float = 0.35,  # Long-term capital gains rate
        existing_deductions: float = 0.0,
        company_match_ratio: float = 0.0,
        pledge_percentage: float = 0.5,
        eligible_vested_shares: int = 0,
        shares_already_donated: int = 0
    ) -> DonationResult:
        """
        Calculate impact of selling shares then donating cash proceeds.
        
        Args:
            shares: Number of shares to sell
            share_price: Current price per share
            cost_basis: Cost basis per share
            holding_period_months: How long shares have been held
            donation_percentage: Portion of after-tax proceeds to donate (0.0-1.0)
            agi: Adjusted gross income
            tax_rate: Marginal ordinary income tax rate
            ltcg_rate: Long-term capital gains rate
            existing_deductions: Other charitable deductions this year
            company_match_ratio: Company match ratio
            pledge_percentage: Pledge percentage (e.g., 0.5 for 50%)
            eligible_vested_shares: Total vested shares eligible for matching program
            shares_already_donated: Shares already donated (reduces match eligibility)
            
        Returns:
            DonationResult with all calculations
        """
        warnings = []
        
        # Calculate sale proceeds and taxes
        sale_proceeds = shares * share_price
        capital_gains = shares * (share_price - cost_basis)
        
        if capital_gains > 0:
            if holding_period_months >= 12:
                capital_gains_tax = capital_gains * ltcg_rate
            else:
                capital_gains_tax = capital_gains * tax_rate
                warnings.append("Short-term capital gains taxed at ordinary income rate")
        else:
            capital_gains_tax = 0
            if capital_gains < 0:
                warnings.append("Capital loss can offset other gains or carry forward")
        
        # After-tax proceeds
        after_tax_proceeds = sale_proceeds - capital_gains_tax
        
        # Amount to donate
        donation_amount = after_tax_proceeds * donation_percentage
        
        # Calculate donation impact (this is a cash donation)
        result = ShareDonationCalculator.calculate_donation(
            agi=agi,
            tax_rate=tax_rate,
            existing_deductions=existing_deductions,
            company_match_ratio=company_match_ratio,
            pledge_percentage=pledge_percentage,
            eligible_vested_shares=eligible_vested_shares,
            shares_already_donated=shares_already_donated,
            cash_amount=donation_amount
        )
        
        # Add sale-specific warnings
        result.warnings.extend(warnings)
        
        return result
    
    
    @staticmethod
    def calculate_multiyear_optimization(
        annual_agi: List[float],
        donation_amounts: List[float],
        donation_types: List[str],  # 'stock' or 'cash' for each year
        tax_rates: List[float],
        starting_carryforward: float = 0.0
    ) -> List[Dict]:
        """
        Calculate optimal deduction usage across multiple years.
        
        Args:
            annual_agi: AGI for each year
            donation_amounts: Donation amount for each year
            donation_types: Type of donation each year ('stock' or 'cash')
            tax_rates: Marginal tax rate for each year
            starting_carryforward: Any existing carryforward
            
        Returns:
            List of dicts with yearly deduction details
        """
        results = []
        carryforward = starting_carryforward
        carryforward_years = []  # Track when each carryforward expires
        
        for year, (agi, donation, dtype, tax_rate) in enumerate(
            zip(annual_agi, donation_amounts, donation_types, tax_rates)
        ):
            # Determine AGI limit for this year
            if dtype == 'stock':
                agi_limit = agi * ShareDonationCalculator.AGI_LIMIT_STOCK
            else:
                agi_limit = agi * ShareDonationCalculator.AGI_LIMIT_CASH
            
            # Current year donation plus any carryforward
            available_deduction = donation + carryforward
            
            # Apply AGI limit
            used_deduction = min(available_deduction, agi_limit)
            
            # Calculate what portion came from current vs carryforward
            current_year_used = min(donation, used_deduction)
            carryforward_used = used_deduction - current_year_used
            
            # Update carryforward
            new_carryforward = donation - current_year_used
            remaining_carryforward = carryforward - carryforward_used
            
            # Add new carryforward with expiration tracking
            if new_carryforward > 0:
                carryforward_years.append({
                    'amount': new_carryforward,
                    'expires': year + ShareDonationCalculator.CARRYFORWARD_YEARS
                })
            
            # Remove expired carryforwards
            active_carryforwards = []
            total_carryforward = 0
            for cf in carryforward_years:
                if cf['expires'] > year:
                    active_carryforwards.append(cf)
                    total_carryforward += cf['amount']
            
            carryforward_years = active_carryforwards
            carryforward = total_carryforward + remaining_carryforward
            
            # Calculate tax benefit
            tax_benefit = used_deduction * tax_rate
            
            results.append({
                'year': year + 1,
                'agi': agi,
                'donation': donation,
                'type': dtype,
                'agi_limit': agi_limit,
                'deduction_used': used_deduction,
                'tax_benefit': tax_benefit,
                'new_carryforward': new_carryforward,
                'total_carryforward': carryforward,
                'carryforward_expiring': [cf for cf in carryforward_years if cf['expires'] == year + 1]
            })
        
        return results
    
    # COMMENTED OUT: calculate_cost_basis_election_benefit() - Advanced Tax Optimization
    #
    # This function analyzes the benefit of making a cost basis election for donated shares.
    # For long-term donations, you can elect to deduct cost basis instead of FMV,
    # which moves the deduction from 30% AGI limit (stock) to 50% AGI limit (cash).
    # Currently unused but represents sophisticated tax planning that most users miss.
    #
    # Future Use Case: Advanced tax optimization scenarios
    # - "Should I make a cost basis election for my ISO/NSO donation?"
    # - Generate scenario variants with/without election to show benefit
    # - Help users discover tax optimization opportunities they might overlook
    #
    # This is particularly valuable for ISOs and NSOs where the basis vs FMV difference
    # can be significant, and AGI bucket utilization varies by year.
    # When advanced features are built, this will enable sophisticated tax planning.
    #
    # @staticmethod
    # def calculate_cost_basis_election_benefit(
    #     shares: int,
    #     share_price: float,
    #     cost_basis: float,
    #     exercise_price: float,  # For options
    #     asset_type: str,  # 'ISO' or 'NSO'
    #     agi: float,
    #     tax_rate: float,
    #     has_other_50pct_donations: float = 0.0,
    #     has_other_30pct_donations: float = 0.0
    # ) -> Dict[str, float]:
    #     """
    #     Calculate benefit of making cost basis election for donated shares.
    #     
    #     For long-term donations, you can elect to deduct cost basis instead
    #     of FMV, which moves the deduction from 30% to 50% AGI limit.
    #     
    #     Returns:
    #         Dict with 'with_election' and 'without_election' tax benefits
    #     """
    #     # Without election: FMV deduction subject to 30% limit
    #     fmv_deduction = shares * share_price
    #     limit_30 = agi * ShareDonationCalculator.AGI_LIMIT_STOCK
    #     available_30 = max(0, limit_30 - has_other_30pct_donations)
    #     deduction_without = min(fmv_deduction, available_30)
    #     
    #     # With election: Cost basis deduction subject to 50% limit
    #     if asset_type == 'ISO':
    #         # For ISOs, cost basis = strike price
    #         basis_deduction = shares * cost_basis
    #     elif asset_type == 'NSO':
    #         # For NSOs, cost basis = exercise price (includes ordinary income)
    #         basis_deduction = shares * exercise_price
    #     else:
    #         # Regular stock
    #         basis_deduction = shares * cost_basis
    #     
    #     limit_50 = agi * ShareDonationCalculator.AGI_LIMIT_CASH
    #     available_50 = max(0, limit_50 - has_other_50pct_donations)
    #     deduction_with = min(basis_deduction, available_50)
    #     
    #     return {
    #         'without_election': {
    #             'deduction': deduction_without,
    #             'tax_benefit': deduction_without * tax_rate,
    #             'deduction_type': '30%',
    #             'deduction_value': fmv_deduction
    #         },
    #         'with_election': {
    #             'deduction': deduction_with,
    #             'tax_benefit': deduction_with * tax_rate,
    #             'deduction_type': '50%',
    #             'deduction_value': basis_deduction
    #         },
    #         'election_benefit': (deduction_with - deduction_without) * tax_rate
    #     }