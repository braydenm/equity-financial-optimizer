#!/usr/bin/env python3
"""
Run all tests in the test suite.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_test_file(test_file):
    """Run a single test file and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {test_file.name}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ PASSED")
            return True
        else:
            print("❌ FAILED")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run all tests and report results."""
    print("RUNNING ALL TESTS")
    print("="*80)
    
    # Find all test files
    test_dir = Path(__file__).parent / "tests"
    test_files = sorted(test_dir.glob("test_*.py"))
    

    
    results = {}
    
    for test_file in test_files:
        success = run_test_file(test_file)
        results[test_file.name] = "PASSED" if success else "FAILED"
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results.values() if r == "PASSED")
    failed = sum(1 for r in results.values() if r == "FAILED")
    skipped = sum(1 for r in results.values() if r == "SKIPPED")
    
    for test_name, result in results.items():
        status = {"PASSED": "✅", "FAILED": "❌", "SKIPPED": "⏭️ "}[result]
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {len(results)} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏭️  Skipped: {skipped}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {failed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())