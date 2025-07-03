"""Test that marginal rate calculation correctly uses filing status for Medicare threshold."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculators.annual_tax_calculator import AnnualTaxCalculator
from projections.projection_state import UserProfile


class TestMarginalRateMedicareThreshold:
    """Test marginal rate calculation with correct Medicare threshold by filing status."""
    
    def test_medicare_threshold_single_filer(self):
        """Test that single filers use $200,000 threshold for additional Medicare tax."""
        calculator = AnnualTaxCalculator()
        
        # Create a profile with known rates
        profile = UserProfile(
            federal_tax_rate=0.24,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0765,  # Social Security + Medicare
            additional_medicare_rate=0.009,  # 0.9%
            niit_rate=0.038,
            annual_w2_income=200000,
            current_cash=100000,
            exercise_reserves=50000,
            pledge_percentage=0.0,
            company_match_ratio=0.0,
            filing_status="single"
        )
        
        # Test just below threshold - should not include additional Medicare
        marginal_rate_below = calculator._estimate_marginal_rate(
            ordinary_income=199_000,
            filing_status="single",
            include_california=True,
            user_profile=profile
        )
        
        # Test just above threshold - should include additional Medicare
        marginal_rate_above = calculator._estimate_marginal_rate(
            ordinary_income=201_000,
            filing_status="single",
            include_california=True,
            user_profile=profile
        )
        
        # The difference should be the additional Medicare rate (0.9%)
        assert abs(marginal_rate_above - marginal_rate_below - 0.009) < 0.0001
    
    def test_medicare_threshold_married_filing_jointly(self):
        """Test that married filing jointly uses $250,000 threshold for additional Medicare tax."""
        calculator = AnnualTaxCalculator()
        
        # Create a profile with known rates
        profile = UserProfile(
            federal_tax_rate=0.24,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0765,  # Social Security + Medicare
            additional_medicare_rate=0.009,  # 0.9%
            niit_rate=0.038,
            annual_w2_income=200000,
            current_cash=100000,
            exercise_reserves=50000,
            pledge_percentage=0.0,
            company_match_ratio=0.0,
            filing_status="married_filing_jointly"
        )
        
        # Test just below MFJ threshold - should not include additional Medicare
        marginal_rate_below_mfj = calculator._estimate_marginal_rate(
            ordinary_income=249_000,
            filing_status="married_filing_jointly",
            include_california=True,
            user_profile=profile
        )
        
        # Test just above MFJ threshold - should include additional Medicare
        marginal_rate_above_mfj = calculator._estimate_marginal_rate(
            ordinary_income=251_000,
            filing_status="married_filing_jointly",
            include_california=True,
            user_profile=profile
        )
        
        # The difference at MFJ threshold should be the additional Medicare rate (0.9%)
        assert abs(marginal_rate_above_mfj - marginal_rate_below_mfj - 0.009) < 0.0001
    
    def test_filing_status_parameter_respected(self):
        """Test that the filing_status parameter overrides the profile's filing status."""
        calculator = AnnualTaxCalculator()
        
        # Create a profile with single filing status
        profile = UserProfile(
            federal_tax_rate=0.24,
            federal_ltcg_rate=0.15,
            state_tax_rate=0.093,
            state_ltcg_rate=0.093,
            fica_tax_rate=0.0765,
            additional_medicare_rate=0.009,
            niit_rate=0.038,
            annual_w2_income=200000,
            current_cash=100000,
            exercise_reserves=50000,
            pledge_percentage=0.0,
            company_match_ratio=0.0,
            filing_status="single"  # Profile says single
        )
        
        # Test with override to married_filing_jointly
        # Test at income level above single threshold but below MFJ threshold
        # Need higher income to avoid Social Security wage base complications
        test_income = 300_000
        
        marginal_rate_as_mfj_below = calculator._estimate_marginal_rate(
            ordinary_income=test_income - 51_000,  # $249k - below MFJ threshold
            filing_status="married_filing_jointly",  # Override to MFJ
            include_california=True,
            user_profile=profile
        )
        
        marginal_rate_as_mfj_above = calculator._estimate_marginal_rate(
            ordinary_income=test_income - 49_000,  # $251k - above MFJ threshold
            filing_status="married_filing_jointly",
            include_california=True,
            user_profile=profile
        )
        
        marginal_rate_as_single = calculator._estimate_marginal_rate(
            ordinary_income=test_income,  # Well above single threshold
            filing_status="single",  # Use single
            include_california=True,
            user_profile=profile
        )
        
        # Check that MFJ properly uses its threshold
        assert abs(marginal_rate_as_mfj_above - marginal_rate_as_mfj_below - 0.009) < 0.0001
        
        # Single at $300k should have additional Medicare
        # MFJ below threshold should not
        # The difference should include the additional Medicare rate
        difference = marginal_rate_as_single - marginal_rate_as_mfj_below
        # Should be at least 0.009 (may be more due to bracket differences)
        assert difference >= 0.009


if __name__ == "__main__":
    test = TestMarginalRateMedicareThreshold()
    test.test_medicare_threshold_single_filer()
    print("✓ Single filer test passed")
    test.test_medicare_threshold_married_filing_jointly()
    print("✓ Married filing jointly test passed")
    test.test_filing_status_parameter_respected()
    print("✓ Filing status parameter test passed")
    print("\nAll tests passed!")