#!/usr/bin/env python3
"""
Comprehensive test suite for CSV generation validation.

This test validates that all CSV outputs contain the correct data and format.
It specifically tests for the issues identified in the CSV generation review.

Run with: python3 tests/test_csv_generation.py
"""

import sys
import os
import csv
from datetime import date, timedelta
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projections.projection_state import (
    ProjectionPlan, ProjectionResult, YearlyState, ShareLot, PlannedAction,
    UserProfile, TaxState, CharitableDeductionState, PledgeState, PledgeObligation,
    ShareType, LifecycleState, TaxTreatment, ActionType
)
from projections.projection_calculator import ProjectionCalculator
from projections.projection_output import save_all_projection_csvs
from calculators.components import AnnualTaxComponents, ShareSaleComponents, DonationComponents


class CSVValidationError(Exception):
    """Custom exception for CSV validation failures."""
    pass


def create_test_data() -> tuple[UserProfile, ProjectionPlan]:
    """Create test data with known values for validation."""
    # Create user profile with spouse income
    profile = UserProfile(
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0765,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        annual_w2_income=300000,
        spouse_w2_income=150000,  # Should show in CSV
        other_income=10000,
        current_cash=100000,
        exercise_reserves=50000,
        pledge_percentage=0.5,
        company_match_ratio=3.0,
        filing_status="married_filing_jointly",
        state_of_residence="California"
    )

    # Create projection plan with various lot types
    plan = ProjectionPlan(
        name="CSV Test Scenario",
        description="Test scenario for CSV generation validation",
        start_date=date(2025, 1, 1),
        end_date=date(2027, 12, 31),
        initial_lots=[
            # Future vesting event (will vest naturally in 2025)
            ShareLot(
                lot_id="VEST_20250601_ISO",
                share_type=ShareType.ISO,
                quantity=2500,
                strike_price=10.0,
                grant_date=date(2023, 1, 1),
                lifecycle_state=LifecycleState.GRANTED_NOT_VESTED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2033, 1, 1)
            ),
            # Future vesting event that remains granted throughout test period
            ShareLot(
                lot_id="VEST_20280101_ISO",
                share_type=ShareType.ISO,
                quantity=3000,
                strike_price=10.0,
                grant_date=date(2024, 1, 1),
                lifecycle_state=LifecycleState.GRANTED_NOT_VESTED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2034, 1, 1)
            ),
            # Vested ISOs (should be renamed from VESTED_ISO to ISO)
            ShareLot(
                lot_id="VESTED_ISO",
                share_type=ShareType.ISO,
                quantity=10000,
                strike_price=5.0,
                grant_date=date(2022, 1, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2032, 1, 1)
            ),
            # Exercised shares ready to sell
            ShareLot(
                lot_id="RSU_2021",
                share_type=ShareType.RSU,
                quantity=2000,
                strike_price=0.0,
                grant_date=date(2021, 1, 1),
                lifecycle_state=LifecycleState.EXERCISED_NOT_DISPOSED,
                tax_treatment=TaxTreatment.LTCG,
                exercise_date=date(2021, 1, 1),
                cost_basis=0.0,
                fmv_at_exercise=20.0
            ),
            # NSO lot that will expire
            ShareLot(
                lot_id="NSO_EXPIRING",
                share_type=ShareType.NSO,
                quantity=1000,
                strike_price=15.0,
                grant_date=date(2020, 1, 1),
                lifecycle_state=LifecycleState.VESTED_NOT_EXERCISED,
                tax_treatment=TaxTreatment.NA,
                expiration_date=date(2030, 1, 1)
            )
        ],
        initial_cash=100000
    )

    # Add planned actions
    actions = [
        # Exercise with cost (should show exercise_cost in annual_summary)
        PlannedAction(
            action_date=date(2025, 7, 1),
            action_type=ActionType.EXERCISE,
            lot_id="VESTED_ISO",
            quantity=5000,
            price=50.0,
            notes="Exercise half of vested ISOs"
        ),
        # Sale creating pledge (should calculate correctly per formula)
        PlannedAction(
            action_date=date(2025, 8, 1),
            action_type=ActionType.SELL,
            lot_id="RSU_2021",
            quantity=1000,
            price=60.0,
            notes="Sell RSUs creating pledge obligation"
        ),
        # Donation (should show in charitable_carryforward.csv)
        PlannedAction(
            action_date=date(2025, 9, 1),
            action_type=ActionType.DONATE,
            lot_id="RSU_2021",
            quantity=1000,
            price=60.0,
            notes="Donate to fulfill pledge"
        ),
        # Let NSO expire (should show in Expired state)
        # No action needed - it expires naturally
    ]

    for action in actions:
        plan.add_action(action)

    # Set price projections
    plan.price_projections = {
        2025: 50.0,
        2026: 60.0,
        2027: 70.0
    }

    return profile, plan


def validate_annual_tax_detail_csv(filepath: str) -> None:
    """Validate annual_tax_detail.csv contains all required fields."""
    print("\nValidating annual_tax_detail.csv...")

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise CSVValidationError("annual_tax_detail.csv is empty")

    # Check for 2025 row (year with actions)
    year_2025 = next((r for r in rows if r['year'] == '2025'), None)
    if not year_2025:
        raise CSVValidationError("No 2025 data in annual_tax_detail.csv")

    # Validate spouse income is present
    spouse_income = float(year_2025.get('spouse_income', 0))
    if spouse_income != 150000:
        raise CSVValidationError(f"Expected spouse_income=150000, got {spouse_income}")

    # Validate gains are present (from RSU sale)
    ltcg = float(year_2025.get('long_term_gains', 0))
    if ltcg <= 0:
        raise CSVValidationError(f"Expected long_term_gains > 0 from RSU sale, got {ltcg}")

    # Validate ISO bargain element (from exercise)
    iso_bargain = float(year_2025.get('iso_bargain_element', 0))
    if iso_bargain <= 0:
        raise CSVValidationError(f"Expected iso_bargain_element > 0 from ISO exercise, got {iso_bargain}")

    # Validate charitable deduction (from donation)
    stock_deduction = float(year_2025.get('charitable_deduction_stock', 0))
    if stock_deduction <= 0:
        raise CSVValidationError(f"Expected charitable_deduction_stock > 0 from donation, got {stock_deduction}")

    print("✅ annual_tax_detail.csv validation passed")


def validate_state_timeline_csv(filepath: str) -> None:
    """Validate state_timeline.csv tracks all states correctly."""
    print("\nValidating state_timeline.csv...")

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Check for granted shares tracking
    granted_rows = [r for r in rows if r['State'] == 'Granted']
    if not any(int(r.get('2025', 0)) > 0 for r in granted_rows):
        raise CSVValidationError("No granted shares found in state_timeline.csv")

    # Check for VESTED_ISO renamed to ISO
    lot_ids = set(r['Lot_ID'] for r in rows)
    if 'VESTED_ISO' in lot_ids and 'ISO' not in lot_ids:
        raise CSVValidationError("VESTED_ISO not renamed to ISO in state_timeline.csv")

    # Check for group TOTAL rows
    total_rows = [r for r in rows if r['State'] == 'TOTAL']
    if not total_rows:
        raise CSVValidationError("No TOTAL rows found for lot groups")

    # Check for SUBTOTAL rows for exercised lots
    subtotal_rows = [r for r in rows if r['State'] == 'SUBTOTAL']
    exercised_lots = [lid for lid in lot_ids if '_EX_' in lid]
    if exercised_lots and not subtotal_rows:
        raise CSVValidationError("No SUBTOTAL rows found for exercised lots")

    print("✅ state_timeline.csv validation passed")


def validate_transition_timeline_csv(filepath: str) -> None:
    """Validate transition_timeline.csv shows all transitions."""
    print("\nValidating transition_timeline.csv...")

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Check for vesting transitions
    vesting_rows = [r for r in rows if r['Transition'] == 'Vesting']
    if not any(int(r.get('2025', 0)) > 0 for r in vesting_rows):
        raise CSVValidationError("No vesting transitions found in 2025")

    # Check for exercising transitions
    exercising_rows = [r for r in rows if r['Transition'] == 'Exercising']
    if not any(int(r.get('2025', 0)) > 0 for r in exercising_rows):
        raise CSVValidationError("No exercising transitions found in 2025")

    # Check for selling transitions
    selling_rows = [r for r in rows if r['Transition'] == 'Selling']
    if not any(int(r.get('2025', 0)) > 0 for r in selling_rows):
        raise CSVValidationError("No selling transitions found in 2025")

    # Check for donating transitions
    donating_rows = [r for r in rows if r['Transition'] == 'Donating']
    if not any(int(r.get('2025', 0)) > 0 for r in donating_rows):
        raise CSVValidationError("No donating transitions found in 2025")

    # Check for only positive values
    for row in rows:
        for year in ['2025', '2026', '2027']:
            if year in row:
                value = float(row.get(year, 0))
                if value < 0:
                    raise CSVValidationError(f"Negative value {value} found in transition_timeline.csv")

    print("✅ transition_timeline.csv validation passed")


def validate_pledge_obligations_csv(filepath: str) -> None:
    """Validate pledge_obligations.csv calculates correctly."""
    print("\nValidating pledge_obligations.csv...")

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise CSVValidationError("No pledge obligations found")

    # Find the RSU sale pledge
    rsu_pledge = next((r for r in rows if 'RSU_2021' in r.get('source_sale_lot', '')), None)
    if not rsu_pledge:
        raise CSVValidationError("No pledge from RSU_2021 sale found")

    # Validate pledge calculation
    # Formula: shares_donated = (pledge_percentage * shares_sold) / (1 - pledge_percentage)
    # For 50% pledge and 1000 shares sold: (0.5 * 1000) / (1 - 0.5) = 1000 shares
    pledge_percentage = float(rsu_pledge.get('pledge_percentage', 0))
    if abs(pledge_percentage - 0.5) > 0.01:
        raise CSVValidationError(f"Expected pledge_percentage=0.5, got {pledge_percentage}")

    # The pledge amount should be based on share count, not proceeds percentage
    sale_proceeds = float(rsu_pledge.get('sale_proceeds', 0))
    pledge_amount = float(rsu_pledge.get('pledge_amount', 0))

    # For 50% pledge, need to donate 1000 shares (at $60 = $60,000)
    expected_pledge = 60000  # 1000 shares * $60
    if abs(pledge_amount - expected_pledge) > 100:
        raise CSVValidationError(f"Expected pledge_amount≈{expected_pledge}, got {pledge_amount}")

    print("✅ pledge_obligations.csv validation passed")


def validate_charitable_carryforward_csv(filepath: str) -> None:
    """Validate charitable_carryforward.csv shows donations."""
    print("\nValidating charitable_carryforward.csv...")

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Find 2025 row
    year_2025 = next((r for r in rows if r['year'] == '2025'), None)
    if not year_2025:
        raise CSVValidationError("No 2025 data in charitable_carryforward.csv")

    # Should show stock donations (1000 shares * $60)
    stock_donations = float(year_2025.get('stock_donations', 0))
    if stock_donations != 60000:
        raise CSVValidationError(f"Expected stock_donations=60000, got {stock_donations}")

    # Should show AGI including spouse income
    agi = float(year_2025.get('agi', 0))
    # AGI = W2 + spouse + other + LTCG from sale
    # 300k + 150k + 10k + 60k = 520k minimum
    if agi < 520000:
        raise CSVValidationError(f"Expected agi >= 520000, got {agi}")

    print("✅ charitable_carryforward.csv validation passed")


def validate_annual_summary_csv(filepath: str) -> None:
    """Validate annual_summary.csv shows all key metrics."""
    print("\nValidating annual_summary.csv...")

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Find 2025 row
    year_2025 = next((r for r in rows if r['year'] == '2025'), None)
    if not year_2025:
        raise CSVValidationError("No 2025 data in annual_summary.csv")

    # Should show exercise costs (5000 shares * $5)
    exercise_costs = float(year_2025.get('exercise_costs', 0))
    if exercise_costs != 25000:
        raise CSVValidationError(f"Expected exercise_costs=25000, got {exercise_costs}")

    # Should show sale proceeds (1000 shares * $60)
    sale_proceeds = float(year_2025.get('sale_proceeds', 0))
    if sale_proceeds != 60000:
        raise CSVValidationError(f"Expected sale_proceeds=60000, got {sale_proceeds}")

    # Should show donations (1000 shares * $60)
    donations = float(year_2025.get('donations', 0))
    if donations != 60000:
        raise CSVValidationError(f"Expected donations=60000, got {donations}")

    print("✅ annual_summary.csv validation passed")


def validate_holding_period_tracking_csv(filepath: str) -> None:
    """Validate holding_period_tracking.csv shows correct periods."""
    print("\nValidating holding_period_tracking.csv...")

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Should have entries for all lots
    if len(rows) < 3:  # At least the initial lots
        raise CSVValidationError(f"Expected at least 3 lots in holding_period_tracking, got {len(rows)}")

    # Check that exercised ISO lot has long-term status after 2+ years
    iso_lot = next((r for r in rows if r['lot_id'] == 'VESTED_ISO_EX_20250701'), None)
    if not iso_lot:
        raise CSVValidationError("VESTED_ISO_EX_20250701 not found in holding_period_tracking.csv")

    if iso_lot.get('holding_status') != 'long-term':
        raise CSVValidationError(f"Expected VESTED_ISO_EX_20250701 holding_status=long-term, got {iso_lot.get('holding_status')}")

    print("✅ holding_period_tracking.csv validation passed")


def run_csv_generation_test():
    """Run comprehensive CSV generation test."""
    print("\n" + "="*70)
    print("CSV GENERATION VALIDATION TEST")
    print("="*70)

    # Create test data
    profile, plan = create_test_data()

    # Run projection
    print("\nRunning projection...")
    calculator = ProjectionCalculator(profile)
    result = calculator.evaluate_projection_plan(plan)

    # Generate CSVs
    output_dir = "output/csv_test"
    os.makedirs(output_dir, exist_ok=True)
    save_all_projection_csvs(result, "csv_test", output_dir)
    print(f"✅ CSVs generated in {output_dir}/")

    # Validate each CSV
    try:
        validate_annual_tax_detail_csv(f"{output_dir}/csv_test_annual_tax_detail.csv")
        validate_state_timeline_csv(f"{output_dir}/csv_test_state_timeline.csv")
        validate_transition_timeline_csv(f"{output_dir}/csv_test_transition_timeline.csv")
        validate_pledge_obligations_csv(f"{output_dir}/csv_test_pledge_obligations.csv")
        validate_charitable_carryforward_csv(f"{output_dir}/csv_test_charitable_carryforward.csv")
        validate_annual_summary_csv(f"{output_dir}/csv_test_annual_summary.csv")
        validate_holding_period_tracking_csv(f"{output_dir}/csv_test_holding_period_tracking.csv")

        print("\n" + "="*70)
        print("✅ ALL CSV VALIDATION TESTS PASSED!")
        print("="*70)

    except CSVValidationError as e:
        print(f"\n❌ CSV Validation Failed: {e}")
        print("="*70)
        raise
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        print("="*70)
        raise


if __name__ == "__main__":
    run_csv_generation_test()
