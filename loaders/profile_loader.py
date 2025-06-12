"""
Secure Profile Loader - Handles sensitive user data with fallback to demo data.

This module provides secure loading of user profiles with automatic fallback
to demo data when sensitive personal data is not available. This ensures:
1. Sensitive data stays private (user_profile.json is git-ignored)
2. System works out-of-the-box with demo data
3. Clear messaging about which data source is being used
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Tuple


class ProfileLoader:
    """Secure profile loader with automatic fallback to demo data."""

    # Standard profile file paths relative to project root
    USER_PROFILE_PATH = "data/user_profile.json"
    DEMO_PROFILE_PATH = "data/demo_profile.json"
    TEMPLATE_PROFILE_PATH = "data/user_profile_template.json"

    def __init__(self, project_root: str = None):
        """Initialize profile loader.

        Args:
            project_root: Path to project root directory. If None, auto-detects.
        """
        if project_root is None:
            # Auto-detect project root (assumes this file is in loaders/ subdirectory)
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = Path(project_root)

    def load_profile(self, verbose: bool = True, force_demo: bool = False) -> Tuple[Dict[str, Any], bool]:
        """Load user profile with secure fallback logic.

        Args:
            verbose: Whether to print status messages
            force_demo: If True, force use of demo data regardless of user_profile.json existence

        Returns:
            Tuple of (profile_data, is_real_data)
            - profile_data: Loaded JSON profile data
            - is_real_data: True if loaded from user_profile.json, False if demo data

        Raises:
            FileNotFoundError: If neither user profile nor demo profile can be loaded
            ValueError: If profile data is invalid
        """
        # If force_demo is True, skip user profile and go directly to demo
        if force_demo:
            if verbose:
                print("🧪 Forcing use of demo financial data from demo_profile.json")
                print("   (Safe example data - no personal information)")
        else:
            # Try to load real user profile first
            user_profile_path = self.project_root / self.USER_PROFILE_PATH

            if user_profile_path.exists():
                try:
                    profile_data = self._load_json_file(user_profile_path)
                    self._validate_profile_data(profile_data)

                    if verbose:
                        print("🔒 Using personal financial data from user_profile.json")
                        print("   (This file contains sensitive data and is not committed to git)")

                    return profile_data, True

                except (json.JSONDecodeError, ValueError) as e:
                    if verbose:
                        print(f"⚠️  Error loading user_profile.json: {e}")
                        print("   Falling back to demo data...")

        # Fallback to demo profile
        demo_profile_path = self.project_root / self.DEMO_PROFILE_PATH

        if not demo_profile_path.exists():
            raise FileNotFoundError(
                f"Neither {self.USER_PROFILE_PATH} nor {self.DEMO_PROFILE_PATH} found. "
                f"To get started:\n"
                f"1. Copy {self.TEMPLATE_PROFILE_PATH} to {self.USER_PROFILE_PATH}\n"
                f"2. Fill in your real financial data\n"
                f"3. Run scenarios normally"
            )

        try:
            profile_data = self._load_json_file(demo_profile_path)
            self._validate_profile_data(profile_data)

            if verbose:
                print("🧪 Using demo financial data from demo_profile.json")
                print("   (Safe example data - no personal information)")
                print("   To use your real data: copy user_profile_template.json to user_profile.json")

            return profile_data, False

        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Error loading demo profile: {e}")

    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Load and parse JSON file."""
        with open(file_path, 'r') as f:
            return json.load(f)

    def _validate_profile_data(self, profile_data: Dict[str, Any]) -> None:
        """Validate that profile data has required structure and add defaults for optional sections."""
        # Core required sections
        required_sections = [
            'metadata',
            'personal_information',
            'income',
            'equity_position'
        ]

        for section in required_sections:
            if section not in profile_data:
                raise ValueError(f"Profile missing required section: '{section}'")

        # Check profile version
        metadata = profile_data.get('metadata', {})
        version = metadata.get('profile_version')
        if version != "2.0":
            raise ValueError(f"Profile version '{version}' not supported. Expected '2.0'")

        # Validate required fields within core sections
        self._validate_required_fields(profile_data)

        # Add defaults for optional sections
        self._add_optional_section_defaults(profile_data)

    def _validate_required_fields(self, profile_data: Dict[str, Any]) -> None:
        """Validate required fields within each section."""
        # personal_information required fields
        personal = profile_data.get('personal_information', {})
        required_personal_fields = ['ordinary_income_rate', 'ltcg_rate', 'stcg_rate', 'tax_filing_status', 'state_of_residence']
        for field in required_personal_fields:
            if field not in personal:
                raise ValueError(f"Profile missing required field 'personal_information.{field}'")

        # income required fields
        income = profile_data.get('income', {})
        required_income_fields = ['annual_w2_income']
        for field in required_income_fields:
            if field not in income:
                raise ValueError(f"Profile missing required field 'income.{field}'")

        # equity_position required fields
        equity = profile_data.get('equity_position', {})
        if 'current_prices' not in equity or 'last_409a_price' not in equity['current_prices']:
            raise ValueError("Profile missing required field 'equity_position.current_prices.last_409a_price'")

    def _add_optional_section_defaults(self, profile_data: Dict[str, Any]) -> None:
        """Add default values for optional sections and fields."""
        # Add defaults to income section
        income = profile_data.setdefault('income', {})
        income.setdefault('spouse_w2_income', 0)
        income.setdefault('interest_income', 0)
        income.setdefault('other_income', 0)
        income.setdefault('dividend_income', 0)

        # Add defaults for financial_position section
        financial = profile_data.setdefault('financial_position', {})
        liquid_assets = financial.setdefault('liquid_assets', {})
        liquid_assets.setdefault('cash', 0)

        # Add defaults for goals_and_constraints section
        goals = profile_data.setdefault('goals_and_constraints', {})
        liquidity_needs = goals.setdefault('liquidity_needs', {})
        liquidity_needs.setdefault('exercise_reserves', 0)

        # Add defaults for charitable_giving section
        charitable = profile_data.setdefault('charitable_giving', {})
        charitable.setdefault('pledge_percentage', 0.0)
        charitable.setdefault('company_match_ratio', 0.0)

    def get_profile_status(self) -> Dict[str, Any]:
        """Get status of available profile files."""
        user_profile_path = self.project_root / self.USER_PROFILE_PATH
        demo_profile_path = self.project_root / self.DEMO_PROFILE_PATH
        template_profile_path = self.project_root / self.TEMPLATE_PROFILE_PATH

        return {
            'user_profile_exists': user_profile_path.exists(),
            'demo_profile_exists': demo_profile_path.exists(),
            'template_profile_exists': template_profile_path.exists(),
            'user_profile_path': str(user_profile_path),
            'demo_profile_path': str(demo_profile_path),
            'template_profile_path': str(template_profile_path),
            'is_using_real_data': user_profile_path.exists(),
            'setup_instructions': self._get_setup_instructions()
        }

    def _get_setup_instructions(self) -> Dict[str, str]:
        """Get setup instructions based on current state."""
        user_profile_path = self.project_root / self.USER_PROFILE_PATH
        template_profile_path = self.project_root / self.TEMPLATE_PROFILE_PATH

        if user_profile_path.exists():
            return {
                'status': 'ready',
                'message': 'User profile configured. System will use your personal data.'
            }
        elif template_profile_path.exists():
            return {
                'status': 'setup_needed',
                'message': f'Copy {self.TEMPLATE_PROFILE_PATH} to {self.USER_PROFILE_PATH} and fill in your data.'
            }
        else:
            return {
                'status': 'missing_template',
                'message': f'Template file {self.TEMPLATE_PROFILE_PATH} not found. Repository may be incomplete.'
            }


# Convenience functions for common use cases
def load_user_profile(project_root: str = None, verbose: bool = True, force_demo: bool = False) -> Tuple[Dict[str, Any], bool]:
    """Convenience function to load user profile with fallback.

    Args:
        project_root: Path to project root. If None, auto-detects.
        verbose: Whether to print loading status messages.
        force_demo: If True, force use of demo data regardless of user_profile.json existence.

    Returns:
        Tuple of (profile_data, is_real_data)
    """
    loader = ProfileLoader(project_root)
    return loader.load_profile(verbose=verbose, force_demo=force_demo)


def get_profile_loader(project_root: str = None) -> ProfileLoader:
    """Get a profile loader instance.

    Args:
        project_root: Path to project root. If None, auto-detects.

    Returns:
        ProfileLoader instance
    """
    return ProfileLoader(project_root)


def check_profile_setup(project_root: str = None) -> None:
    """Print profile setup status and instructions.

    Args:
        project_root: Path to project root. If None, auto-detects.
    """
    return ProfileLoader(project_root)


def check_profile_setup(project_root: str = None) -> None:
    """Print profile setup status and instructions.

    Args:
        project_root: Path to project root. If None, auto-detects.
    """
    loader = ProfileLoader(project_root)
    status = loader.get_profile_status()

    print("\n🔐 PROFILE SETUP STATUS")
    print("=" * 50)

    if status['is_using_real_data']:
        print("✅ Using personal financial data (user_profile.json)")
        print("   Your sensitive data is secure and not committed to git.")
    else:
        print("🧪 Using demo financial data (demo_profile.json)")
        print("   This is safe example data with no personal information.")

    print(f"\nFiles found:")
    print(f"  📄 User Profile: {'✅' if status['user_profile_exists'] else '❌'} {status['user_profile_path']}")
    print(f"  📄 Demo Profile: {'✅' if status['demo_profile_exists'] else '❌'} {status['demo_profile_path']}")
    print(f"  📄 Template:     {'✅' if status['template_profile_exists'] else '❌'} {status['template_profile_path']}")

    instructions = status['setup_instructions']
    if instructions['status'] == 'setup_needed':
        print(f"\n📝 To use your real financial data:")
        print(f"   1. cp '{ProfileLoader.TEMPLATE_PROFILE_PATH}' '{ProfileLoader.USER_PROFILE_PATH}'")
        print(f"   2. Edit {ProfileLoader.USER_PROFILE_PATH} with your real financial information")
        print(f"   3. Run scenarios normally - system will automatically use your data")
        print(f"\n   Your user_profile.json file is git-ignored and stays private.")
    elif instructions['status'] == 'ready':
        print(f"\n✅ Setup complete: {instructions['message']}")
    else:
        print(f"\n⚠️  Issue: {instructions['message']}")
