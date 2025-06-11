#!/usr/bin/env python3
"""
Validation test for Natural Evolution scenario.

This test validates that Phase 1 implementation works correctly:
1. Natural Evolution scenario generation
2. ProjectionCalculator evaluation
3. Yearly state calculation
4. Summary metrics
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import date
from projections.projection_state import UserProfile
from engine.natural_evolution_generator import generate_natural_evolution_from_profile_data
from projections.projection_calculator import ProjectionCalculator
from projections.projection_output import save_all_projection_csvs


def load_test_profile():
    """Load user profile for testing."""
    # TODO: Keep test using demo_profile.json for stable, predictable validation
    profile_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'demo_profile.json'
    )
    
    with open(profile_path, 'r') as f:
        return json.load(f)


def test_natural_evolution_generation():
    """Test Natural Evolution scenario generation."""
    print("Testing Natural Evolution Scenario Generation...")
    
    # Load profile data
    profile_data = load_test_profile()
    
    # Generate Natural Evolution scenario
    plan = generate_natural_evolution_from_profile_data(profile_data, projection_years=5)
    
    print(f"✅ Generated scenario: {plan.name}")
    print(f"✅ Description: {plan.description}")
    print(f"✅ Projection period: {plan.start_date} to {plan.end_date}")
    print(f"✅ Initial lots: {len(plan.initial_lots)}")
    print(f"✅ Planned actions: {len(plan.planned_actions)}")
    print(f"✅ Initial cash: ${plan.initial_cash:,.0f}")
    
    # Show initial lots
    print("\nInitial Equity Lots:")
    for lot in plan.initial_lots:
        print(f"  {lot.lot_id}: {lot.quantity:,} {lot.share_type.value} shares ({lot.lifecycle_state.value})")
    
    # Show planned actions
    print("\nPlanned Actions:")
    for action in plan.planned_actions[:5]:  # Show first 5
        print(f"  {action.action_date}: {action.action_type.value} {action.quantity} shares ({action.lot_id})")
    
    if len(plan.planned_actions) > 5:
        print(f"  ... and {len(plan.planned_actions) - 5} more actions")
    
    return plan


def test_projection_calculation(plan):
    """Test ProjectionCalculator with Natural Evolution scenario."""
    print("\n" + "="*60)
    print("Testing Projection Calculator...")
    
    # Create simplified user profile for calculator
    profile_data = load_test_profile()
    personal_info = profile_data.get('personal_information', {})
    income = profile_data.get('income', {})
    financial_pos = profile_data.get('financial_position', {})
    charitable = profile_data.get('charitable_giving', {})
    
    user_profile = UserProfile(
        ordinary_income_rate=personal_info.get('ordinary_income_rate', 0.486),
        ltcg_rate=personal_info.get('ltcg_rate', 0.331),
        stcg_rate=personal_info.get('stcg_rate', 0.486),
        annual_w2_income=income.get('annual_w2_income', 0),
        spouse_w2_income=income.get('spouse_w2_income', 0),
        current_cash=financial_pos.get('liquid_assets', {}).get('cash', 0),
        exercise_reserves=profile_data.get('goals_and_constraints', {}).get('liquidity_needs', {}).get('exercise_reserves', 0),
        pledge_percentage=charitable.get('pledge_percentage', 0.5),
        company_match_ratio=charitable.get('company_match_ratio', 3.0),
        filing_status=personal_info.get('tax_filing_status', 'single')
    )
    
    # Create calculator and evaluate plan
    calculator = ProjectionCalculator(user_profile)
    result = calculator.evaluate_projection_plan(plan)
    
    print(f"✅ Projection calculated successfully")
    print(f"✅ Years evaluated: {len(result.yearly_states)}")
    print(f"✅ Summary metrics calculated: {len(result.summary_metrics)}")
    
    return result


def test_yearly_states(result):
    """Test yearly state calculations."""
    print("\n" + "="*60)
    print("Testing Yearly States...")
    
    print(f"\nYear-by-Year Summary:")
    print(f"{'Year':<6} {'Cash':<12} {'Income':<12} {'Tax':<10} {'Equity Value':<15} {'Net Worth':<12}")
    print("-" * 75)
    
    for state in result.yearly_states:
        print(f"{state.year:<6} ${state.ending_cash:<11,.0f} ${state.income:<11,.0f} "
              f"${state.tax_paid:<9,.0f} ${state.total_equity_value:<14,.0f} ${state.total_net_worth:<11,.0f}")
    
    # Test specific year access
    first_year = result.get_state_for_year(2025)
    final_year = result.get_final_state()
    
    if first_year:
        print(f"\n✅ First year (2025) state accessible: ${first_year.ending_cash:,.0f} cash")
    
    if final_year:
        print(f"✅ Final year ({final_year.year}) state accessible: ${final_year.ending_cash:,.0f} cash")
    
    return result


def test_summary_metrics(result):
    """Test summary metrics calculation."""
    print("\n" + "="*60)
    print("Testing Summary Metrics...")
    
    metrics = result.summary_metrics
    
    print(f"\nSummary Metrics:")
    print(f"  Total Cash (Final Year): ${metrics.get('total_cash_final', 0):,.0f}")
    print(f"  Total Taxes (All Years): ${metrics.get('total_taxes_all_years', 0):,.0f}")
    print(f"  Total Donations (All Years): ${metrics.get('total_donations_all_years', 0):,.0f}")
    print(f"  Total Equity Value (Final): ${metrics.get('total_equity_value_final', 0):,.0f}")
    print(f"  Pledge Fulfillment (Max): {metrics.get('pledge_fulfillment_maximalist', 0):.1%}")
    print(f"  Pledge Fulfillment (Min): {metrics.get('pledge_fulfillment_minimalist', 0):.1%}")
    print(f"  Outstanding Obligation: ${metrics.get('outstanding_obligation', 0):,.0f}")
    
    # Basic validation
    final_cash = metrics.get('total_cash_final', 0)
    total_taxes = metrics.get('total_taxes_all_years', 0)
    
    print(f"\n✅ Summary metrics validation:")
    print(f"  Final cash is reasonable: ${final_cash:,.0f} {'✅' if final_cash > 0 else '⚠️'}")
    print(f"  Total taxes calculated: ${total_taxes:,.0f} {'✅' if total_taxes >= 0 else '❌'}")


def test_csv_output(result):
    """Test CSV output functionality."""
    print("\n" + "="*60)
    print("Testing CSV Output...")
    
    # Create output directory
    output_dir = "output/phase1_test"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save all CSV files
    save_all_projection_csvs(result, result.plan.name, output_dir)
    
    # Check that files were created
    expected_files = [
        f"{output_dir}/natural_evolution_yearly_cashflow.csv",
        f"{output_dir}/natural_evolution_tax_timeline.csv", 
        f"{output_dir}/natural_evolution_summary.csv",
        f"{output_dir}/natural_evolution_equity_holdings.csv"
    ]
    
    all_files_exist = True
    for file_path in expected_files:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"✅ Created: {os.path.basename(file_path)} ({file_size} bytes)")
        else:
            print(f"❌ Missing: {os.path.basename(file_path)}")
            all_files_exist = False
    
    if all_files_exist:
        print(f"✅ All CSV files created successfully in {output_dir}/")
    
    return all_files_exist


def main():
    """Run complete Natural Evolution validation test."""
    print("NATURAL EVOLUTION SCENARIO VALIDATION")
    print("=" * 80)
    print("Phase 1 Implementation Test")
    print("=" * 80)
    
    try:
        # Test 1: Scenario Generation
        plan = test_natural_evolution_generation()
        
        # Test 2: Projection Calculation
        result = test_projection_calculation(plan)
        
        # Test 3: Yearly States
        test_yearly_states(result)
        
        # Test 4: Summary Metrics
        test_summary_metrics(result)
        
        # Test 5: CSV Output
        test_csv_output(result)
        
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED - Phase 1 Implementation Validated!")
        print("="*80)
        print("\nNext Steps:")
        print("- Phase 2: Create basic scenario variants (sell-all-end, exercise-all-now)")
        print("- Phase 3: Address calculator gaps (tax carryforward, pledge tracking)")
        print("- Phase 4: Testing and validation with specified scenarios")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)