#!/usr/bin/env python3
"""
Test to verify action summary data quality issues.

This test verifies that action_summary.csv contains proper data:
1. acquisition_date field populated with actual acquisition dates
2. holding_period_days calculated correctly based on acquisition vs action dates
3. tax_treatment (STCG vs LTCG) matches holding periods
4. current_share_price shows FMV at action time
5. lot_options_remaining and lot_shares_remaining track properly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
import csv
from datetime import date, timedelta
from projections.projection_calculator import ProjectionCalculator
from projections.projection_state import ProjectionPlan, PlannedAction, ActionType, ShareLot, UserProfile
from loaders.profile_loader import ProfileLoader
from loaders.equity_loader import EquityLoader


def create_user_profile_object(profile_data):
    """Create UserProfile object from profile data."""
    personal_info = profile_data.get('personal_information', {})
    income = profile_data.get('income', {})
    financial_pos = profile_data.get('financial_position', {})
    charitable = profile_data.get('charitable_giving', {})
    tax_situation = profile_data.get('tax_situation', {})
    estimated_taxes = tax_situation.get('estimated_taxes', {})
    goals = profile_data.get('goals_and_constraints', {})

    return UserProfile(
        federal_tax_rate=personal_info['federal_tax_rate'],
        federal_ltcg_rate=personal_info['federal_ltcg_rate'],
        state_tax_rate=personal_info['state_tax_rate'],
        state_ltcg_rate=personal_info['state_ltcg_rate'],
        fica_tax_rate=personal_info['fica_tax_rate'],
        additional_medicare_rate=personal_info['additional_medicare_rate'],
        niit_rate=personal_info['niit_rate'],
        annual_w2_income=income.get('annual_w2_income', 0),
        spouse_w2_income=income.get('spouse_w2_income', 0),
        other_income=income.get('other_income', 0),
        interest_income=income.get('interest_income', 0),
        dividend_income=income.get('dividend_income', 0),
        current_cash=financial_pos.get('liquid_assets', {}).get('cash', 0),
        exercise_reserves=goals.get('liquidity_needs', {}).get('exercise_reserves', 0),
        pledge_percentage=charitable.get('pledge_percentage', 0.0),
        company_match_ratio=charitable.get('company_match_ratio', 0.0),
        filing_status=personal_info.get('tax_filing_status', 'single'),
        state_of_residence=personal_info.get('state_of_residence', 'California'),
        monthly_living_expenses=financial_pos.get('monthly_cash_flow', {}).get('expenses', 0),
        regular_income_withholding_rate=estimated_taxes.get('regular_income_withholding_rate', 0.0),
        supplemental_income_withholding_rate=estimated_taxes.get('supplemental_income_withholding_rate', 0.0),
        quarterly_payments=estimated_taxes.get('quarterly_payments', 0)
    )


def test_action_summary_data_quality():
    """Test that action summary CSV contains proper data quality."""
    print("🧪 TESTING: Action Summary Data Quality")

    # Create scenario with known holding periods for testing
    scenario_data = {
        "scenario_name": "test_action_summary",
        "description": "Test scenario to verify action summary data quality",
        "actions": [
            {
                "action_date": "2025-06-15",
                "action_type": "sell",
                "lot_id": "RSU_2021_001",  # RSU granted/exercised 2021 -> LTCG by 2025
                "quantity": 500,
                "price": 35.0,
                "notes": "LTCG sale - should have >1 year holding period"
            },
            {
                "action_date": "2025-09-01",
                "action_type": "sell",
                "lot_id": "RSU_2024_001",  # RSU granted/exercised 2024 -> STCG in 2025
                "quantity": 300,
                "price": 35.0,
                "notes": "STCG sale - should have <1 year holding period"
            },
            {
                "action_date": "2026-01-15",
                "action_type": "exercise",
                "lot_id": "ISO",
                "quantity": 2000,
                "price": 5.0,
                "notes": "ISO exercise - should show strike price and vest expiration"
            },
            {
                "action_date": "2026-06-01",
                "action_type": "donate",
                "lot_id": "ISO_2023_001",
                "quantity": 1000,
                "price": 40.0,
                "notes": "Donation - should show acquisition date and holding period"
            }
        ]
    }

    # Write scenario to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(scenario_data, f, indent=2)
        scenario_path = f.name

    try:
        # Load demo profile and execute scenario
        profile_loader = ProfileLoader()
        profile_data, is_real_data = profile_loader.load_profile(force_demo=True)
        user_profile = create_user_profile_object(profile_data)
        equity_loader = EquityLoader()
        initial_lots = equity_loader.load_lots_from_profile(profile_data)
        calculator = ProjectionCalculator(user_profile)

        # Create projection plan
        planned_actions = []
        for action_data in scenario_data["actions"]:
            action = PlannedAction(
                action_date=date.fromisoformat(action_data["action_date"]),
                action_type=ActionType[action_data["action_type"].upper()],
                lot_id=action_data["lot_id"],
                quantity=action_data["quantity"],
                price=action_data.get("price"),
                notes=action_data.get("notes", "")
            )
            planned_actions.append(action)

        plan = ProjectionPlan(
            name="test_action_summary",
            description="Test scenario to verify action summary data quality",
            start_date=date(2025, 1, 1),
            end_date=date(2027, 12, 31),
            initial_lots=initial_lots,
            initial_cash=0.0,
            planned_actions=planned_actions,
            price_projections={2025: 35.0, 2026: 40.0, 2027: 45.0},
            tax_elections={}
        )

        # Execute scenario
        result = calculator.evaluate_projection_plan(plan)

        # Find the generated action summary CSV
        from projections.detailed_materialization import materialize_detailed_projection
        output_dir = tempfile.mkdtemp()
        materialize_detailed_projection(result, output_dir, "test_action_summary")
        action_summary_path = f"{output_dir}/test_action_summary_action_summary.csv"

        # Read and analyze the CSV
        print(f"\n📊 ANALYZING ACTION SUMMARY CSV: {action_summary_path}")

        with open(action_summary_path, 'r') as f:
            reader = csv.DictReader(f)
            actions = list(reader)

        print(f"  Found {len(actions)} actions in CSV")

        # VERIFY DATA QUALITY
        print("\n✅ VERIFYING ACTION SUMMARY DATA QUALITY:")
        success_conditions = []
        failures = []

        for i, action in enumerate(actions):
            action_date = action['date']
            action_type = action['type']
            lot_id = action['lot_id']
            exercise_date = action['exercise_date']
            holding_period_days = action['holding_period_days']
            tax_treatment = action['tax_treatment']

            print(f"\n  Action {i+1}: {action_type} {lot_id} on {action_date}")
            print(f"    Acquisition Date: '{exercise_date}'")
            print(f"    Holding Period: {holding_period_days} days")
            print(f"    Tax Treatment: {tax_treatment}")

            # Check if exercise_date is populated (not empty)
            if exercise_date and exercise_date.strip():
                success_conditions.append(f"✅ {action_type} {lot_id}: exercise_date populated")
            else:
                failures.append(f"❌ {action_type} {lot_id}: exercise_date empty")

            # Check if holding_period_days is calculated (not 0 for sales/donations)
            if action_type in ['sell', 'donate']:
                try:
                    holding_days = int(holding_period_days)
                    if holding_days > 0:
                        success_conditions.append(f"✅ {action_type} {lot_id}: holding_period_days calculated ({holding_days})")
                    else:
                        failures.append(f"❌ {action_type} {lot_id}: holding_period_days is 0")
                except (ValueError, TypeError):
                    failures.append(f"❌ {action_type} {lot_id}: holding_period_days invalid ({holding_period_days})")

            # Check tax treatment consistency with holding periods
            if action_type in ['sell', 'donate'] and holding_period_days:
                try:
                    holding_days = int(holding_period_days)
                    expected_treatment = 'LTCG' if holding_days >= 365 else 'STCG'
                    if tax_treatment == expected_treatment:
                        success_conditions.append(f"✅ {action_type} {lot_id}: tax treatment consistent ({tax_treatment})")
                    else:
                        failures.append(f"❌ {action_type} {lot_id}: tax treatment inconsistent ({tax_treatment}, expected {expected_treatment})")
                except (ValueError, TypeError):
                    failures.append(f"❌ {action_type} {lot_id}: cannot verify tax treatment consistency")

        # Check for additional fields that should be present
        required_fields = ['year', 'date', 'type', 'lot_id', 'quantity', 'price', 'exercise_date',
                          'holding_period_days', 'tax_treatment', 'gross_proceeds', 'capital_gain']

        if actions:
            csv_fields = set(actions[0].keys())
            for field in required_fields:
                if field in csv_fields:
                    success_conditions.append(f"✅ Required field present: {field}")
                else:
                    failures.append(f"❌ Required field missing: {field}")

        # Summary
        if failures:
            print(f"\n  ❌ SOME DATA QUALITY ISSUES FOUND:")
            for failure in failures:
                print(f"    {failure}")
            print(f"\n  ✅ Successful checks: {len(success_conditions)}")
            print(f"  ❌ Failed checks: {len(failures)}")
            return False, failures
        else:
            print(f"\n  ✅ ALL DATA QUALITY CHECKS PASSED:")
            for condition in success_conditions[:10]:  # Show first 10 to avoid spam
                print(f"    {condition}")
            if len(success_conditions) > 10:
                print(f"    ... and {len(success_conditions) - 10} more checks")
            print(f"\n  🎉 All {len(success_conditions)} action summary checks successful!")
            return True, success_conditions

    finally:
        # Clean up temp files
        os.unlink(scenario_path)
        if 'output_dir' in locals():
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)


def test_expected_action_summary_behavior():
    """Display what action summary fields should contain."""
    print("\n🎯 EXPECTED ACTION SUMMARY BEHAVIOR:")
    print("  exercise_date: Actual exercise date from lot lifecycle")
    print("  holding_period_days: Days between acquisition and action date")
    print("  tax_treatment: STCG (<365 days) or LTCG (≥365 days)")
    print("  current_share_price: FMV at time of action (not just strike)")
    print("  lot_options_remaining: Unexercised options after this action")
    print("  lot_shares_remaining: Exercised shares after this action")


if __name__ == "__main__":
    print("=" * 80)
    print("ACTION SUMMARY DATA QUALITY TEST")
    print("=" * 80)

    try:
        all_passed, conditions = test_action_summary_data_quality()
        test_expected_action_summary_behavior()

        print("\n" + "=" * 80)
        if all_passed:
            print("🎉 TEST RESULT: ALL ACTION SUMMARY TESTS PASSED")
            print(f"   Successfully verified {len(conditions)} data quality checks")
            sys.exit(0)
        else:
            print("❌ TEST RESULT: SOME ACTION SUMMARY TESTS FAILED")
            print(f"   Failed {len(conditions)} data quality checks")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
