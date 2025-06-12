"""
Share donation calculator that extracts tax components from charitable donations.

This calculator extracts components from share and cash donations without
calculating actual tax benefits. Components are aggregated annually for
proper tax calculation including AGI-based deduction limits and carryforwards.

Refactored to support annual tax composition:
- calculate_share_donation_components() returns components for share donations
- calculate_cash_donation_components() returns components for cash donations
- All tax calculation happens in the annual tax calculator
"""

from typing import Optional
from datetime import date
from calculators.components import DonationComponents, CashDonationComponents


class ShareDonationCalculator:
    """
    Extracts components from charitable donations for annual tax calculation.

    This calculator knows nothing about tax rates or AGI limits. It simply
    extracts the components needed for the annual tax calculator to properly
    apply charitable deduction rules.
    """

    @staticmethod
    def calculate_share_donation_components(
        lot_id: str,
        donation_date: date,
        shares_donated: int,
        fmv_at_donation: float,
        cost_basis: float,
        acquisition_date: date,
        holding_period_days: int,
        company_match_ratio: float = 0.0,
        pledge_id: Optional[str] = None,
        pledge_amount_satisfied: float = 0.0
    ) -> DonationComponents:
        """
        Calculate components from share donation for annual tax aggregation.

        This function extracts the tax components from a share donation action
        without calculating the actual tax deduction. The components are used by
        the annual tax calculator to determine actual deductibility based on AGI.

        Args:
            lot_id: Identifier for the lot being donated
            donation_date: Date of donation
            shares_donated: Number of shares to donate
            fmv_at_donation: Fair market value per share at donation
            cost_basis: Cost basis per share
            acquisition_date: Date shares were acquired
            holding_period_days: Days held (for deduction calculation)
            company_match_ratio: Company match ratio (e.g., 3.0 for 3:1)
            pledge_id: Optional reference to pledge being satisfied
            pledge_amount_satisfied: Amount of pledge satisfied by this donation

        Returns:
            DonationComponents containing all relevant data for tax calculation
        """
        # Calculate donation value
        total_fmv = shares_donated * fmv_at_donation

        # Determine deduction value based on holding period
        if holding_period_days >= 365:
            # Long-term: deduct FMV
            donation_value = total_fmv
            deduction_type = 'stock'
        else:
            # Short-term: limited to cost basis
            donation_value = shares_donated * cost_basis
            deduction_type = 'stock'  # Still stock donation, but limited

        # Calculate company match
        company_match_amount = total_fmv * company_match_ratio

        return DonationComponents(
            lot_id=lot_id,
            donation_date=donation_date,
            shares_donated=shares_donated,
            fmv_at_donation=fmv_at_donation,
            cost_basis=cost_basis,
            acquisition_date=acquisition_date,
            holding_period_days=holding_period_days,
            donation_value=donation_value,
            deduction_type=deduction_type,
            company_match_ratio=company_match_ratio,
            company_match_amount=company_match_amount,
            pledge_amount_satisfied=pledge_amount_satisfied,
            pledge_id=pledge_id
        )

    @staticmethod
    def calculate_cash_donation_components(
        donation_date: date,
        amount: float,
        company_match_ratio: float = 0.0,
        pledge_id: Optional[str] = None,
        pledge_amount_satisfied: float = 0.0
    ) -> CashDonationComponents:
        """
        Calculate components from cash donation for annual tax aggregation.

        Args:
            donation_date: Date of donation
            amount: Cash amount donated
            company_match_ratio: Company match ratio (usually 0 for cash)
            pledge_id: Optional reference to pledge being satisfied
            pledge_amount_satisfied: Amount of pledge satisfied

        Returns:
            CashDonationComponents for annual tax calculation
        """
        company_match_amount = amount * company_match_ratio

        return CashDonationComponents(
            donation_date=donation_date,
            amount=amount,
            company_match_ratio=company_match_ratio,
            company_match_amount=company_match_amount,
            pledge_amount_satisfied=pledge_amount_satisfied,
            pledge_id=pledge_id
        )
