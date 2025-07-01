#!/usr/bin/env python3
"""
Test to verify NSO exercise uses correct FMV during tender offers.

This test checks if NSO exercises during a tender offer use the tender price
as FMV rather than the 409a price projections.
"""

import sys
import os
from datetime import date
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.portfolio_manager import PortfolioManager


def test_tender_nso_exercise_fmv():
    """Test that NSO exercises during tender use tender price as FMV."""
    print("NSO Tender Exercise FMV Test")
    print("=" * 70)
    
    # Create test profile with tender offer
    test_profile = {
        "metadata": {
            "profile_version": "2.0",
            "created_date": "2025-01-01",
            "last_updated": "2025-01-01"
        },
        "personal_information": {
            "tax_filing_status": "single",
            "state_of_residence": "California",
            "age": 35,
            "federal_tax_rate": 0.37,
            "federal_ltcg_rate": 0.2,
            "state_tax_rate": 0.093,
            "state_ltcg_rate": 0.093,
            "fica_tax_rate": 0.0145,
            "additional_medicare_rate": 0.009,
            "niit_rate": 0.038
        },
        "income": {
            "annual_w2_income": 200000,
            "spouse_w2_income": 0,
            "other_income": 0,
            "interest_income": 0,
            "dividend_income": 0
        },
        "equity_position": {
            "company": "Test Company",
            "grants": [{
                "grant_id": "GRANT-001",
                "grant_date": "2023-01-01",
                "type": "NSO",
                "total_shares": 10000,
                "strike_price": 10.0,
                "vesting_start_date": "2023-01-01",
                "expiration_date": "2033-01-01",
                "charitable_program": {
                    "pledge_percentage": 0.0,
                    "company_match_ratio": 0.0
                },
                "vesting_status": {
                    "vested_unexercised": {
                        "nso": 5000
                    },
                    "unvested": {
                        "total_shares": 5000,
                        "vesting_calendar": []
                    }
                }
            }],
            "exercised_lots": [],
            "current_prices": {
                "last_409a_price": 25.0,
                "last_409a_date": "2024-12-01",
                "tender_offer_price": 56.0,
                "last_tender_offer_date": "2025-06-01"
            }
        },
        "tax_situation": {
            "estimated_taxes": {
                "quarterly_payments": 0,
                "regular_income_withholding_rate": 0.35,
                "supplemental_income_withholding_rate": 0.33
            }
        },
        "financial_position": {
            "liquid_assets": {
                "cash": 100000,
                "taxable_investments": 0,
                "retirement_accounts": 0,
                "crypto": 0,
                "total": 100000
            },
            "monthly_cash_flow": {
                "income": 16667,
                "expenses": 8000,
                "savings": 8667
            }
        },
        "goals_and_constraints": {
            "liquidity_needs": {
                "emergency_fund": 50000,
                "near_term_cash": 0,
                "exercise_reserves": 50000,
                "tax_reserves": 0
            },
            "risk_tolerance": "moderate",
            "concentration_limit": 0.5,
            "time_horizon_years": 5
        }
    }
    
    # Write test profile
    with open('test_tender_profile.json', 'w') as f:
        json.dump(test_profile, f, indent=2)
    
    # Create test scenario with NSO exercise on tender date
    test_scenario = {
        "scenario_name": "nso_tender_exercise",
        "description": "NSO exercise during tender offer",
        "actions": [
            {
                "action_date": "2025-06-01",  # Same as tender date
                "action_type": "exercise",
                "lot_id": "NSO",
                "quantity": 1000,
                "notes": "Exercise NSOs during tender"
            },
            {
                "action_date": "2025-06-01",  
                "action_type": "sell",
                "lot_id": "NSO_EX_20250601",
                "quantity": 1000,
                "notes": "Cashless sale at tender price"
            }
        ]
    }
    
    # Write test scenario
    os.makedirs('scenarios/test', exist_ok=True)
    with open('scenarios/test/001_nso_tender_exercise.json', 'w') as f:
        json.dump(test_scenario, f, indent=2)
    
    # Run scenario
    manager = PortfolioManager()
    manager._data_source = 'test'  # Use test data source
    manager._profile_data = test_profile
    
    # Load initial lots from test profile
    from loaders.equity_loader import EquityLoader
    equity_loader = EquityLoader()
    manager._initial_lots = equity_loader.load_lots_from_profile(test_profile)
    
    # Create user profile
    from projections.projection_state import UserProfile
    manager._user_profile = UserProfile(
        federal_tax_rate=0.37,
        federal_ltcg_rate=0.20,
        state_tax_rate=0.093,
        state_ltcg_rate=0.093,
        fica_tax_rate=0.0145,
        additional_medicare_rate=0.009,
        niit_rate=0.038,
        annual_w2_income=200000,
        spouse_w2_income=0,
        other_income=0,
        current_cash=100000,
        exercise_reserves=50000,
        pledge_percentage=0.0,
        company_match_ratio=0.0,
        filing_status="single",
        state_of_residence="California",
        regular_income_withholding_rate=0.35,
        supplemental_income_withholding_rate=0.33
    )
    
    # Execute scenario
    try:
        result = manager.execute_single_scenario(
            scenario_path='001_nso_tender_exercise',
            price_scenario='moderate',
            projection_years=1,
            output_dir='output/test_tender'
        )
        
        # Analyze results
        print(f"\nProfile Settings:")
        print(f"  409a Price: ${test_profile['equity_position']['current_prices']['last_409a_price']}")
        print(f"  Tender Price: ${test_profile['equity_position']['current_prices']['tender_offer_price']}")
        print(f"  Tender Date: {test_profile['equity_position']['current_prices']['last_tender_offer_date']}")
        
        # Check NSO exercise components
        yearly_state = result.yearly_states[0]
        nso_components = yearly_state.annual_tax_components.nso_exercise_components
        
        if nso_components:
            nso_comp = nso_components[0]
            print(f"\nNSO Exercise Analysis:")
            print(f"  Strike Price: ${10.0}")
            print(f"  FMV Used: ${nso_comp.fmv_at_exercise}")
            print(f"  Bargain Element: ${nso_comp.bargain_element:,.2f}")
            
            # Check if tender price was used as FMV
            expected_bargain = (56.0 - 10.0) * 1000  # tender_price - strike_price
            actual_bargain = nso_comp.bargain_element
            
            if abs(expected_bargain - actual_bargain) < 0.01:
                print(f"\n✅ SUCCESS: NSO exercise correctly used tender price as FMV!")
                print(f"   Expected bargain element: ${expected_bargain:,.2f}")
                print(f"   Actual bargain element: ${actual_bargain:,.2f}")
            else:
                print(f"\n❌ ERROR: NSO exercise did not use tender price as FMV!")
                print(f"   Expected bargain element (using tender price): ${expected_bargain:,.2f}")
                print(f"   Actual bargain element: ${actual_bargain:,.2f}")
                print(f"   Appears to have used 409a price instead")
        
        # Check sale components
        sale_components = yearly_state.annual_tax_components.sale_components
        if sale_components:
            sale_comp = sale_components[0]
            print(f"\nSale Analysis:")
            print(f"  Sale Price: ${sale_comp.sale_price}")
            print(f"  Cost Basis: ${sale_comp.cost_basis}")
            print(f"  Capital Gain: ${sale_comp.short_term_gain + sale_comp.long_term_gain:,.2f}")
            
    except Exception as e:
        print(f"\nError running test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if os.path.exists('test_tender_profile.json'):
            os.remove('test_tender_profile.json')
        if os.path.exists('scenarios/test/001_nso_tender_exercise.json'):
            os.remove('scenarios/test/001_nso_tender_exercise.json')
        if os.path.exists('scenarios/test'):
            os.rmdir('scenarios/test')
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_tender_nso_exercise_fmv()