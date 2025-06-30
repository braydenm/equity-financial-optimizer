#!/usr/bin/env python3
"""
Scenario Analysis - Main CLI for single equity optimization scenario execution.

Execute and analyze individual equity optimization scenarios.
"""

import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from engine.portfolio_manager import PortfolioManager
from projections.projection_output import save_all_projection_csvs


def print_scenario_results(result, detailed=True, verbose=False):
    """Print formatted results for a scenario."""
    metrics = result.summary_metrics
    final_state = result.get_final_state()

    print(f"\n{'='*80}")
    print(f"SCENARIO: {result.plan.name}")
    print(f"{'='*80}")

    # Financial outcomes - Accounting table format
    print(f"\nFINAL BALANCE SHEET ({final_state.year}):")
    print(f"  {'ASSETS':<25} {'AMOUNT':<15}")
    print(f"  {'-'*40}")
    print(f"  {'Cash Position':<25} ${metrics['total_cash_final']:>13,.0f}")
    print(f"  {'Investment Balance':<25} ${final_state.investment_balance:>13,.0f}")
    print(f"  {'Equity Holdings':<25} ${metrics['total_equity_value_final']:>13,.0f}")

    # Add other assets if they exist
    crypto = getattr(result.user_profile, 'crypto', 0) if hasattr(result, 'user_profile') else 0
    real_estate = getattr(result.user_profile, 'real_estate_equity', 0) if hasattr(result, 'user_profile') else 0
    if crypto > 0:
        print(f"  {'Crypto Assets':<25} ${crypto:>13,.0f}")
    if real_estate > 0:
        print(f"  {'Real Estate Equity':<25} ${real_estate:>13,.0f}")

    print(f"  {'-'*40}")
    total_assets = metrics['total_cash_final'] + final_state.investment_balance + metrics['total_equity_value_final'] + crypto + real_estate
    print(f"  {'TOTAL ASSETS':<25} ${total_assets:>13,.0f}")

    # Liabilities
    outstanding_pledge = metrics['outstanding_obligation']
    if outstanding_pledge > 0:
        print(f"\n  {'LIABILITIES':<25} {'AMOUNT':<15}")
        print(f"  {'-'*40}")
        print(f"  {'Outstanding Pledges':<25} ${outstanding_pledge:>13,.0f}")
        print(f"  {'-'*40}")
        print(f"  {'TOTAL LIABILITIES':<25} ${outstanding_pledge:>13,.0f}")
        net_worth = total_assets - outstanding_pledge
    else:
        net_worth = total_assets

    print(f"\n  {'='*40}")
    print(f"  {'NET WORTH':<25} ${net_worth:>13,.0f}")
    print(f"  {'='*40}")

    # Cumulative metrics - Enhanced with charitable impact breakdown
    print(f"\nCUMULATIVE METRICS:")
    print(f"  💸 Total Taxes Paid: ${metrics['total_taxes_all_years']:,.0f}")

    # Charitable impact breakdown
    total_donations = metrics['total_donations_all_years']
    total_company_match = metrics.get('total_company_match_all_years', 0)
    total_charitable_impact = total_donations + total_company_match
    print(f"  🎁 Total Charitable Impact: ${total_charitable_impact:,.0f}")
    print(f"    ├─ Personal Donations: ${total_donations:,.0f}")
    print(f"    └─ Company Match Earned: ${total_company_match:,.0f}")

    # Pledge tracking
    print(f"  📋 Outstanding Pledge Liability: ${metrics['outstanding_obligation']:,.0f}")

    # Calculate outstanding company match opportunity
    pledge_shares_outstanding = metrics.get('pledge_shares_outstanding', 0)
    if hasattr(result, 'user_profile') and hasattr(result.user_profile, 'company_match_ratio'):
        match_ratio = result.user_profile.company_match_ratio
        # Estimate outstanding match based on current equity value and outstanding pledge shares
        if pledge_shares_outstanding > 0 and final_state:
            avg_share_price = metrics['total_equity_value_final'] / max(1, sum(lot.quantity for lot in final_state.equity_holdings))
            outstanding_match_opportunity = pledge_shares_outstanding * avg_share_price * match_ratio
            print(f"  🤝 Outstanding Company Match Opportunity: ${outstanding_match_opportunity:,.0f}")

    print(f"  ✅ Pledge Status: {metrics.get('pledge_shares_donated', 0):,}/{metrics.get('pledge_shares_obligated', 0):,} shares")

    # Expired opportunities
    pledge_shares_expired = metrics.get('pledge_shares_expired_window', 0)
    if pledge_shares_expired > 0:
        print(f"  ⚠️  Expired Match Window: {pledge_shares_expired:,} shares (match opportunity lost)")
        # Calculate expired match value
        if hasattr(result, 'user_profile') and hasattr(result.user_profile, 'company_match_ratio') and final_state:
            avg_share_price = metrics['total_equity_value_final'] / max(1, sum(lot.quantity for lot in final_state.equity_holdings))
            expired_match_value = pledge_shares_expired * avg_share_price * result.user_profile.company_match_ratio
            print(f"  💸 Expired Match Value: ${expired_match_value:,.0f}")

    # Total expired charitable carryforward (not remaining)
    expired_charitable_deduction = metrics.get('expired_charitable_deduction', 0)
    print(f"  📝 Total Expired Charitable Carryforward: ${expired_charitable_deduction:,.0f}")
    if expired_charitable_deduction > 1000:
        print(f"    ❗️ WARNING: These deductions expired after 5-year carryforward period. Consider timing donations to maximize deduction utilization")

    # Enhanced equity position with all lifecycle states
    print(f"\nEQUITY POSITION BY STATE:")

    # Initialize counters for all states
    granted_unvested = 0
    vested_unexercised = 0
    exercised_held = 0
    disposed_sold = 0
    disposed_donated = 0
    expired_shares = 0

    # Count shares in current holdings
    for lot in final_state.equity_holdings:
        if lot.lifecycle_state.value == 'granted_not_vested':
            granted_unvested += lot.quantity
        elif lot.lifecycle_state.value == 'vested_not_exercised':
            vested_unexercised += lot.quantity
        elif lot.lifecycle_state.value == 'exercised_not_disposed':
            exercised_held += lot.quantity

    # Count disposed shares from all yearly states (sold/donated)
    for state in result.yearly_states:
        for action in result.plan.planned_actions:
            if action.action_date.year == state.year:
                if action.action_type.value == 'sell':
                    disposed_sold += action.quantity
                elif action.action_type.value == 'donate':
                    disposed_donated += action.quantity

    # Count expired shares from metrics
    expired_shares = metrics.get('total_expired_shares', 0)

    total_shares = granted_unvested + vested_unexercised + exercised_held + disposed_sold + disposed_donated + expired_shares

    print(f"  {'State':<20} {'Shares':<10} {'% of Total':<10}")
    print(f"  {'-'*40}")
    if granted_unvested > 0:
        print(f"  {'Granted (Unvested)':<20} {granted_unvested:>9,} {granted_unvested/max(1,total_shares)*100:>8.1f}%")
    if vested_unexercised > 0:
        print(f"  {'Vested (Unexercised)':<20} {vested_unexercised:>9,} {vested_unexercised/max(1,total_shares)*100:>8.1f}%")
    if exercised_held > 0:
        print(f"  {'Exercised (Held)':<20} {exercised_held:>9,} {exercised_held/max(1,total_shares)*100:>8.1f}%")
    if disposed_sold > 0:
        print(f"  {'Disposed (Sold)':<20} {disposed_sold:>9,} {disposed_sold/max(1,total_shares)*100:>8.1f}%")
    if disposed_donated > 0:
        print(f"  {'Disposed (Donated)':<20} {disposed_donated:>9,} {disposed_donated/max(1,total_shares)*100:>8.1f}%")
    if expired_shares > 0:
        print(f"  {'Expired (Lost)':<20} {expired_shares:>9,} {expired_shares/max(1,total_shares)*100:>8.1f}%")

    print(f"  {'-'*40}")
    print(f"  {'TOTAL':<20} {total_shares:>9,} {'100.0%':>8}")

    if detailed and final_state and verbose:
        # Display opportunity cost warnings if any exist
        total_opportunity_cost = metrics.get('total_opportunity_cost', 0)
        total_expired_shares = metrics.get('total_expired_shares', 0)
        expiration_details = metrics.get('expiration_details', [])

        if total_opportunity_cost > 0:
            print(f"\n⚠️  OPTION EXPIRATION WARNINGS:")
            print(f"  💸 Total Opportunity Cost: ${total_opportunity_cost:,.2f}")
            print(f"  📉 Total Expired Shares: {total_expired_shares:,} shares")
            print(f"  📊 Average Loss per Share: ${total_opportunity_cost/total_expired_shares:.2f}")

            for detail in expiration_details:
                print(f"  🔥 {detail['year']}: Lot {detail['lot_id']} - {detail['quantity']:,} shares expired - LOST ${detail['opportunity_cost']:,.0f} (${detail['per_share_loss']:.2f}/share)")

            print(f"  ⚡ Consider exercising valuable vested options before expiration!")

        # AMT Credit consumption warning
        amt_credits_final = metrics.get('amt_credits_final', 0)
        if amt_credits_final > 0:
            # Calculate AMT credit consumption rate from final years
            final_year_consumption = 0
            penultimate_year_consumption = 0

            if len(result.yearly_states) >= 2:
                # Get consumption from last two years to estimate rate
                for i, state in enumerate(result.yearly_states[-2:]):
                    if hasattr(state, 'tax_state') and hasattr(state.tax_state, 'amt_credit_used'):
                        consumption = state.tax_state.amt_credit_used
                        if i == 0:
                            penultimate_year_consumption = consumption
                        else:
                            final_year_consumption = consumption

            # Use average of last two years, or final year if only one available
            avg_consumption = final_year_consumption
            if penultimate_year_consumption > 0:
                avg_consumption = (final_year_consumption + penultimate_year_consumption) / 2

            if avg_consumption > 0:
                years_to_consume = amt_credits_final / avg_consumption
                if years_to_consume > 20:
                    print(f"\n⚠️  AMT CREDIT CONSUMPTION WARNING:")
                    print(f"  💰 AMT credits of ${amt_credits_final:,.0f} will take >{years_to_consume:.0f} years to consume at current rate of ${avg_consumption:,.0f}/year")
                    print(f"  📈 Consider strategies to accelerate AMT credit usage")
            elif amt_credits_final > 50000:  # Warn for large unused credits even if no recent consumption
                print(f"\n⚠️  AMT CREDIT ACCUMULATION WARNING:")
                print(f"  💰 Large AMT credit balance of ${amt_credits_final:,.0f} with no recent consumption")
                print(f"  📈 Consider strategies to utilize these credits")

        # Pledge obligation expiration warnings
        pledge_shares_outstanding = metrics.get('pledge_shares_outstanding', 0)
        pledge_shares_expired = metrics.get('pledge_shares_expired', 0)
        outstanding_obligation = metrics.get('outstanding_obligation', 0)

        if pledge_shares_outstanding > 0:
            print(f"\n⚠️  PLEDGE OBLIGATION WARNINGS:")
            print(f"  📋 Outstanding pledge: {pledge_shares_outstanding:,} shares (${outstanding_obligation:,.0f})")
            print(f"  ⏰ These obligations have active match windows - donate before expiration!")

        if pledge_shares_expired > 0:
            print(f"\n⚠️  EXPIRED PLEDGE OBLIGATIONS:")
            print(f"  💸 Lost match opportunities: {pledge_shares_expired:,} shares")
            print(f"  🔥 These pledges expired without being fulfilled - company match no longer available")
            print(f"  📝 Consider replanning future strategies to avoid missed deadlines")



        # Comprehensive financial summary
        print(f"\nFINANCIAL SUMMARY:")
        print(f"  {'Year':<6} {'Income':>10} {'Expenses':>10} {'Exercise':>10} {'Sales':>10} {'Tax':>10} {'Donations':>10} {'Net Flow':>10} {'Eff Tax%':>9}")
        print(f"  {'-'*95}")
        for state in result.yearly_states:
            # Calculate total income from all sources
            investment_income = state.investment_income if hasattr(state, 'investment_income') else 0
            total_income = (state.income + state.spouse_income + state.other_income + investment_income)

            # Get expenses and other cash flows
            expenses = state.living_expenses if hasattr(state, 'living_expenses') else 0
            exercise_costs = state.exercise_costs

            # Calculate sale proceeds from components
            sale_proceeds = 0
            if state.annual_tax_components and hasattr(state.annual_tax_components, 'sale_components'):
                sale_proceeds = sum(comp.gross_proceeds for comp in state.annual_tax_components.sale_components)

            # Tax info
            gross_tax = state.gross_tax if hasattr(state, 'gross_tax') else state.tax_state.total_tax
            withholdings = state.tax_withholdings if hasattr(state, 'tax_withholdings') else 0
            net_tax = state.tax_paid  # This is net of withholdings

            # Donations
            donations = state.donation_value

            # Net cash flow
            net_flow = total_income + sale_proceeds - expenses - exercise_costs - net_tax

            # Effective tax rate
            eff_tax_rate = (gross_tax / total_income * 100) if total_income > 0 else 0

            print(f"  {state.year:<6} ${total_income:>9,.0f} ${expenses:>9,.0f} ${exercise_costs:>9,.0f} "
                  f"${sale_proceeds:>9,.0f} ${net_tax:>9,.0f} ${donations:>9,.0f} ${net_flow:>9,.0f} {eff_tax_rate:>8.1f}%")

        # Tax breakdown by major components (like Schedule K-1)
        print(f"\nTAX BREAKDOWN BY MAJOR COMPONENTS:")
        print(f"  {'Year':<6} {'W2 Income':>12} {'Spouse Inc':>12} {'NSO Ord':>12} {'STCG':>12} {'LTCG':>12} {'ISO AMT':>12} {'Reg Tax':>12} {'AMT Tax':>12} {'Total Tax':>12}")
        print(f"  {'-'*120}")
        for state in result.yearly_states:
            # Extract component details from annual tax components or use state values
            w2_income = state.income
            spouse_income = state.spouse_income if hasattr(state, 'spouse_income') else 0

            nso_ordinary = 0
            stcg = 0
            ltcg = 0
            iso_bargain = 0

            if state.annual_tax_components:
                # Extract from exercise components
                if hasattr(state.annual_tax_components, 'exercise_components'):
                    for comp in state.annual_tax_components.exercise_components:
                        if hasattr(comp, 'ordinary_income'):
                            nso_ordinary += comp.ordinary_income
                        if hasattr(comp, 'amt_adjustment'):
                            iso_bargain += comp.amt_adjustment

                # Extract from sale components
                if hasattr(state.annual_tax_components, 'sale_components'):
                    for comp in state.annual_tax_components.sale_components:
                        if hasattr(comp, 'short_term_gain'):
                            stcg += comp.short_term_gain
                        if hasattr(comp, 'long_term_gain'):
                            ltcg += comp.long_term_gain

            # Get tax calculations from tax state
            regular_tax = 0
            amt_tax = 0
            total_tax = 0

            if hasattr(state, 'tax_state') and state.tax_state:
                total_tax = state.tax_state.total_tax
                # Try to get regular vs AMT breakdown if available
                if hasattr(state.tax_state, 'federal_regular_tax'):
                    regular_tax = state.tax_state.federal_regular_tax + (state.tax_state.ca_regular_tax if hasattr(state.tax_state, 'ca_regular_tax') else 0)
                if hasattr(state.tax_state, 'federal_amt_tax'):
                    amt_tax = state.tax_state.federal_amt_tax + (state.tax_state.ca_amt_tax if hasattr(state.tax_state, 'ca_amt_tax') else 0)

                # If we don't have the breakdown, show total in regular tax column
                if regular_tax == 0 and amt_tax == 0:
                    regular_tax = total_tax

            print(f"  {state.year:<6} ${w2_income:>11,.0f} ${spouse_income:>11,.0f} ${nso_ordinary:>11,.0f} "
                  f"${stcg:>11,.0f} ${ltcg:>11,.0f} ${iso_bargain:>11,.0f} ${regular_tax:>11,.0f} "
                  f"${amt_tax:>11,.0f} ${total_tax:>11,.0f}")

        # Cash flow waterfall
        print(f"\nCASH FLOW WATERFALL:")
        print(f"  {'Year':<6} {'Start Cash':>12} {'+ Income':>12} {'+ Sales':>12} {'- Expenses':>12} {'- Exercise':>12} {'- Tax':>12} {'= End Cash':>12}")
        print(f"  {'-'*102}")
        for state in result.yearly_states:
            total_income = (state.income + state.spouse_income + state.other_income +
                          (state.investment_income if hasattr(state, 'investment_income') else 0))
            expenses = state.living_expenses if hasattr(state, 'living_expenses') else 0

            # Calculate sale proceeds from components
            sale_proceeds = 0
            if state.annual_tax_components and hasattr(state.annual_tax_components, 'sale_components'):
                sale_proceeds = sum(comp.gross_proceeds for comp in state.annual_tax_components.sale_components)

            print(f"  {state.year:<6} ${state.starting_cash:>11,.0f} ${total_income:>11,.0f} "
                  f"${sale_proceeds:>11,.0f} ${expenses:>11,.0f} ${state.exercise_costs:>11,.0f} "
                  f"${state.tax_paid:>11,.0f} ${state.ending_cash:>11,.0f}")

        # Investment tracking with equity details
        if any(hasattr(state, 'investment_balance') and state.investment_balance > 0 for state in result.yearly_states):
            print(f"\nINVESTMENT TRACKING:")
            print(f"  {'Year':<6} {'Price/Share':>12} {'Shares Held':>12} {'Equity Value':>12} {'Other Invst':>12} {'Total Port':>12} {'Equity %':>12}")
            print(f"  {'-'*84}")
            initial_investments = result.user_profile.taxable_investments
            for i, state in enumerate(result.yearly_states):
                # Get price per share from projections
                share_price = result.plan.price_projections.get(state.year, 0)

                # Calculate held shares
                held_shares = sum(lot.quantity for lot in state.equity_holdings
                                if lot.lifecycle_state.value in ['exercised_not_disposed', 'vested_not_exercised'])

                # Calculate equity value
                equity_value = state.total_equity_value

                # Other investments (taxable investments + crypto + real estate)
                taxable_investments = state.investment_balance if hasattr(state, 'investment_balance') else 0
                crypto = result.user_profile.crypto if hasattr(result.user_profile, 'crypto') else 0
                real_estate = result.user_profile.real_estate_equity if hasattr(result.user_profile, 'real_estate_equity') else 0
                other_investments = taxable_investments + crypto + real_estate

                # Total portfolio value
                total_portfolio = equity_value + other_investments

                # Equity percentage of total portfolio
                equity_percentage = (equity_value / total_portfolio * 100) if total_portfolio > 0 else 0

                print(f"  {state.year:<6} ${share_price:>11.2f} {held_shares:>11,} ${equity_value:>11,.0f} "
                      f"${other_investments:>11,.0f} ${total_portfolio:>11,.0f} {equity_percentage:>11.1f}%")

        # Assets breakdown table
        print(f"\nASSETS BREAKDOWN:")
        print(f"  {'Year':<6} {'Cash':>12} {'Investments':>12} {'Equity':>12} {'Crypto':>12} {'Real Estate':>12} {'Total NW':>12} {'YoY Growth':>12}")
        print(f"  {'-'*102}")
        prev_net_worth = 0
        for i, state in enumerate(result.yearly_states):
            cash = state.ending_cash
            investments = state.investment_balance if hasattr(state, 'investment_balance') else 0
            equity = state.total_equity_value

            # Add crypto and real estate from user profile (these don't change in current model)
            crypto = result.user_profile.crypto if hasattr(result.user_profile, 'crypto') else 0
            real_estate = result.user_profile.real_estate_equity if hasattr(result.user_profile, 'real_estate_equity') else 0

            # Calculate total net worth including all assets
            net_worth = cash + investments + equity + crypto + real_estate

            if i == 0:
                # Calculate starting net worth including all components
                start_cash = state.starting_cash
                start_investments = result.user_profile.taxable_investments
                start_equity = sum(lot.quantity for lot in result.plan.initial_lots
                                 if lot.lifecycle_state.value in ['exercised_not_disposed', 'vested_not_exercised']) * \
                               result.plan.price_projections[state.year]
                prev_net_worth = start_cash + start_investments + start_equity + crypto + real_estate

            yoy_growth = ((net_worth / prev_net_worth - 1) * 100) if prev_net_worth > 0 else 0
            print(f"  {state.year:<6} ${cash:>11,.0f} ${investments:>11,.0f} "
                  f"${equity:>11,.0f} ${crypto:>11,.0f} ${real_estate:>11,.0f} ${net_worth:>11,.0f} {yoy_growth:>11.1f}%")
            prev_net_worth = net_worth

        # Charitable donations table (only if donations exist)
        total_donations = sum(state.donation_value for state in result.yearly_states)
        if total_donations > 0 or (final_state and final_state.pledge_state.total_outstanding_obligation > 0):
            print(f"\nCHARITABLE ACTIVITY:")
            print(f"  {'Year':<6} {'Donated':>12} {'Match Earned':>12} {'Deduction':>12} {'Carried Fwd':>12} {'Pledge Oblig':>12}")
            print(f"  {'-'*78}")

            for state in result.yearly_states:
                donation_value = state.donation_value

                # Calculate company match from donation components
                company_match = 0
                if state.annual_tax_components and state.annual_tax_components.donation_components:
                    for comp in state.annual_tax_components.donation_components:
                        company_match += comp.company_match if hasattr(comp, 'company_match') else 0

                # Get charitable deduction info from tax state
                deduction_used = 0
                carryforward = 0
                if hasattr(state, 'charitable_state'):
                    deduction_used = state.charitable_state.federal_current_year_deduction + state.charitable_state.ca_current_year_deduction
                    carryforward = sum(state.charitable_state.federal_carryforward_remaining.values()) + sum(state.charitable_state.ca_carryforward_remaining.values())

                # Get pledge obligation
                pledge_obligation = state.pledge_state.total_outstanding_obligation if state.pledge_state else 0

                print(f"  {state.year:<6} ${donation_value:>11,.0f} ${company_match:>11,.0f} "
                      f"${deduction_used:>11,.0f} ${carryforward:>11,.0f} ${pledge_obligation:>11,.0f}")

            # Add pledge fulfillment summary if pledges exist
            if final_state and final_state.pledge_state and final_state.pledge_state.obligations:
                print(f"\n  Pledge Summary:")
                total_pledged = sum(o.total_pledge_obligation for o in final_state.pledge_state.obligations)
                total_fulfilled = sum(o.donations_made for o in final_state.pledge_state.obligations)
                fulfillment_pct = (total_fulfilled / total_pledged * 100) if total_pledged > 0 else 0
                print(f"    Total Pledged: ${total_pledged:,.0f}")
                print(f"    Total Fulfilled: ${total_fulfilled:,.0f} ({fulfillment_pct:.1f}%)")
                print(f"    Outstanding: ${final_state.pledge_state.total_outstanding_obligation:,.0f}")

def print_raw_data_tables(result):
    """Print raw data tables that map 1:1 to CSV outputs."""
    print(f"\n{'='*80}")
    print("RAW DATA TABLES")
    print(f"{'='*80}")
    print("The following tables contain raw data that maps directly to CSV outputs.")
    print("Data is formatted for easy copy/paste into spreadsheets (no $ or % symbols).")

    # 1. ANNUAL CASH FLOW TABLE
    print(f"\n{'-'*80}")
    print("ANNUAL CASH FLOW (→ yearly_cashflow.csv)")
    print(f"{'-'*80}")
    print(f"{'Year':<6} {'Income':<12} {'Expenses':<12} {'Exercise':<12} {'Tax':<12} {'Donations':<12} {'End_Cash':<12}")
    print(f"{'-'*80}")

    for state in result.yearly_states:
        year_income = state.income
        year_expenses = state.living_expenses
        year_exercise = state.exercise_costs
        year_tax = state.tax_paid
        year_donations = state.donation_value
        end_cash = state.ending_cash

        print(f"{state.year:<6} {year_income:<12.0f} {year_expenses:<12.0f} {year_exercise:<12.0f} {year_tax:<12.0f} {year_donations:<12.0f} {end_cash:<12.0f}")

    # 2. TAX BREAKDOWN TABLE
    print(f"\n{'-'*80}")
    print("TAX BREAKDOWN (→ tax_timeline.csv)")
    print(f"{'-'*80}")
    print(f"{'Year':<6} {'Regular_Tax':<12} {'AMT_Tax':<12} {'Total_Tax':<12} {'AMT_Credits':<12}")
    print(f"{'-'*80}")

    for state in result.yearly_states:
        tax_state = state.tax_state if hasattr(state, 'tax_state') else None
        regular_tax = tax_state.regular_tax if tax_state else 0
        amt_tax = tax_state.amt_tax if tax_state else 0
        total_tax = tax_state.total_tax if tax_state else state.tax_paid
        amt_credits = tax_state.amt_credits_remaining if tax_state else 0

        print(f"{state.year:<6} {regular_tax:<12.0f} {amt_tax:<12.0f} {total_tax:<12.0f} {amt_credits:<12.0f}")

    # 3. ASSETS BREAKDOWN TABLE
    print(f"\n{'-'*80}")
    print("ASSETS BREAKDOWN (→ annual_summary.csv)")
    print(f"{'-'*80}")
    print(f"{'Year':<6} {'Cash':<12} {'Investments':<12} {'Equity':<12} {'Crypto':<12} {'Real_Estate':<12} {'Total_NW':<12} {'YoY_Growth':<12}")
    print(f"{'-'*80}")

    prev_net_worth = 0
    for state in result.yearly_states:
        cash = state.ending_cash
        investments = state.investment_balance
        equity = state.total_equity_value

        # Add crypto and real estate from user profile
        crypto = result.user_profile.crypto if hasattr(result.user_profile, 'crypto') else 0
        real_estate = result.user_profile.real_estate_equity if hasattr(result.user_profile, 'real_estate_equity') else 0

        # Calculate total net worth including all assets
        total_nw = cash + investments + equity + crypto + real_estate
        yoy_growth = ((total_nw - prev_net_worth) / prev_net_worth * 100) if prev_net_worth > 0 else 0

        print(f"{state.year:<6} {cash:<12.0f} {investments:<12.0f} {equity:<12.0f} {crypto:<12.0f} {real_estate:<12.0f} {total_nw:<12.0f} {yoy_growth:<12.1f}")
        prev_net_worth = total_nw

    # 4. ACTION SUMMARY TABLE
    print(f"\n{'-'*80}")
    print("ACTION SUMMARY (→ action_summary.csv)")
    print(f"{'-'*80}")
    print(f"{'Date':<12} {'Action_Type':<12} {'Lot_ID':<20} {'Quantity':<12}")
    print(f"{'-'*80}")

    for action in result.plan.planned_actions:
        action_date = action.action_date.strftime('%Y-%m-%d')
        action_type = str(action.action_type).replace('ActionType.', '')
        lot_id = action.lot_id
        quantity = action.quantity

        print(f"{action_date:<12} {action_type:<12} {lot_id:<20} {quantity:<12.0f}")

def resolve_scenario_path(scenario_input, use_demo=False):
    """Resolve scenario path from either full name or 3-digit identifier.

    Args:
        scenario_input: Either full scenario name (e.g., '001_exercise_all_vested')
                       or just 3-digit identifier (e.g., '001')
        use_demo: Whether to force demo scenarios

    Returns:
        Full scenario path or raises ValueError if not found
    """
    # Determine which directory to search
    if use_demo:
        scenarios_dir = Path("scenarios/demo")
    else:
        # Check if user scenarios exist, otherwise fall back to demo
        user_dir = Path("scenarios/user")
        demo_dir = Path("scenarios/demo")
        scenarios_dir = user_dir if user_dir.exists() else demo_dir

    # If input is just 3 digits, find matching scenario
    if len(scenario_input) == 3 and scenario_input.isdigit():
        pattern = f"{scenario_input}_*.json"
        matching_files = list(scenarios_dir.glob(pattern))

        if not matching_files:
            raise ValueError(f"No scenario found with identifier '{scenario_input}' in {scenarios_dir}")
        elif len(matching_files) > 1:
            raise ValueError(f"Multiple scenarios found with identifier '{scenario_input}': {[f.stem for f in matching_files]}")

        return matching_files[0].stem  # Return filename without .json extension

    # Otherwise, treat as full scenario name
    scenario_file = scenarios_dir / f"{scenario_input}.json"
    if not scenario_file.exists():
        raise ValueError(f"Scenario file not found: {scenario_file}")

    return scenario_input


def execute_scenario(scenario_input, price_scenario="moderate", projection_years=5, use_demo=False, verbose=False):
    """Execute and display a single scenario.

    Args:
        scenario_input: Either full scenario name or 3-digit identifier
        price_scenario: Price growth assumption
        projection_years: Years to project
        use_demo: Force use of demo data
    """
    # Resolve the scenario path
    try:
        scenario_path = resolve_scenario_path(scenario_input, use_demo)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return None

    manager = PortfolioManager()
    manager.load_user_data(force_demo=use_demo)

    print(f"\nExecuting scenario: {scenario_path}")
    print(f"Price assumption: {price_scenario} ({projection_years} years)")

    # Warn users about short projection implications
    if projection_years < 5:
        print(f"⚠️  Short projection period ({projection_years} years):")
        print(f"   • Charitable carryforward expiration effects not visible (need 5+ years)")
        print(f"   • Long-term tax optimization opportunities may be missed")

    result = manager.execute_single_scenario(
        scenario_path=scenario_path,
        price_scenario=price_scenario,
        projection_years=projection_years
    )

    print_scenario_results(result, detailed=True, verbose=verbose)

    # NEW: Generate CSV outputs
    if result:
        # Extract scenario name from path
        scenario_name = os.path.basename(scenario_path)
        if scenario_name.endswith('.json'):
            scenario_name = scenario_name[:-5]

        output_dir = manager._generate_output_path(scenario_name, price_scenario)
        save_all_projection_csvs(result, scenario_name, output_dir)
        print(f"\n📊 CSV files saved to: {output_dir}/")

    if verbose:
        print_raw_data_tables(result)
    return result


def list_available_scenarios():
    """List available scenario files."""
    print("EQUITY FINANCIAL OPTIMIZER - SCENARIO ANALYSIS")
    print("="*80)

    print("Available scenarios:")

    # Show demo scenarios
    demo_scenarios_dir = Path("scenarios/demo")
    if demo_scenarios_dir.exists():
        print("  Demo scenarios (safe example data):")
        for scenario_file in sorted(demo_scenarios_dir.glob("*.json")):
            scenario_name = scenario_file.name.replace(".json", "")
            print(f"    • {scenario_name}")
    else:
        print("  Demo scenarios: Not found")

    # Show user scenarios
    user_scenarios_dir = Path("scenarios/user")
    if user_scenarios_dir.exists():
        print("  User scenarios (your personal data):")
        for scenario_file in sorted(user_scenarios_dir.glob("*.json")):
            scenario_name = scenario_file.name.replace(".json", "")
            print(f"    • {scenario_name}")
    else:
        print("  User scenarios: Not configured")

    print("\nData sources:")
    user_profile_exists = Path("data/user_profile.json").exists()
    demo_profile_exists = Path("data/demo_profile.json").exists()

    if user_profile_exists:
        print("  🔒 User profile configured (will use your personal data)")
    else:
        print("  ⚠️  User profile not found (will use demo data)")

    if demo_profile_exists:
        print("  🧪 Demo profile available (safe example data)")
    else:
        print("  ❌ Demo profile missing")

    print("\nUsage examples:")
    print("  python run_scenario_analysis.py 001_exercise_all_vested")
    print("  python run_scenario_analysis.py 000 --demo")
    print("  python run_scenario_analysis.py 002 --price aggressive --years 7")
    print("\nNote: You can use just the 3-digit identifier (e.g., '001') instead of the full name")


def main():
    """Main entry point for scenario analysis."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Execute single equity optimization scenario analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 001_exercise_all_vested
  %(prog)s 000 --demo
  %(prog)s 002 --price aggressive --years 7
  %(prog)s 206 --verbose --years 15

Note: You can use just the 3-digit identifier (e.g., '001') instead of the full scenario name
Use --verbose to show detailed financial tables and raw data analysis

Projection Period Guidelines:
  • Years 1-4: Basic analysis, no carryforward expiration tracking
  • Years 5+: Full analysis including 5-year carryforward expiration effects
  • Years 10+: Complete long-term planning with all tax implications
        """
    )

    parser.add_argument('scenario', nargs='?', help='Scenario name or 3-digit ID (e.g., 001_exercise_all_vested or just 001)')
    parser.add_argument('--price', default='moderate',
                       choices=['conservative', 'moderate', 'aggressive', 'flat', 'historical_tech'],
                       help='Price growth scenario (default: moderate)')
    parser.add_argument('--years', type=int, default=5,
                       help='Projection years (default: 5). Use 5+ for carryforward expiration tracking.')
    parser.add_argument('--demo', action='store_true',
                       help='Force use of demo data (safe example data)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed tables and analysis (default: show summary only)')

    args = parser.parse_args()

    if args.scenario:
        execute_scenario(args.scenario, args.price, args.years, args.demo, args.verbose)
    else:
        list_available_scenarios()


if __name__ == "__main__":
    main()
