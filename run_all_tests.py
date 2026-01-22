#!/usr/bin/env python3
"""
Test runner script for advanced filtering functionality.
Runs all tests in sequence to verify the complete system.
"""

import sys
import subprocess
from pathlib import Path

def run_test(script_name, description):
    """Run a test script and report results."""
    print(f"🔄 Running {description}...")
    print("=" * 50)
    
    try:
        result = subprocess.run([
            sys.executable, script_name
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print(f"✅ {description} PASSED")
            print("Output:")
            print(result.stdout)
            if result.stderr:
                print("Stderr:")
                print(result.stderr)
        else:
            print(f"❌ {description} FAILED")
            print("Error Output:")
            print(result.stderr)
            print("Stdout:")
            print(result.stdout)
        
        print()
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ {description} CRASHED: {e}")
        print()
        return False

def main():
    """Run all advanced filter tests."""
    print("🚀 Advanced Filtering System Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        ("test_advanced_filters.py", "Advanced Filter Logic Tests"),
        ("test_ui_filters.py", "Advanced Filter UI Component Tests"),
    ]
    
    passed = 0
    total = len(tests)
    
    for script, description in tests:
        if run_test(script, description):
            passed += 1
    
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Tests Passed: {passed}/{total}")
    print(f"Tests Failed: {total - passed}/{total}")
    print()
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Advanced filtering system is fully functional!")
        print()
        print("🎯 READY FOR USE:")
        print("• Command Type Filtering (6 checkboxes)")
        print("• Server Filtering (6 server options)")  
        print("• Time Range Filtering (0-100% slider)")
        print("• Sequential Navigation (◄ ► arrows)")
        print("• Combined Multi-dimensional Filtering")
        print("• Real-time Filter Updates")
        print()
        print("🚀 Launch with: python -m xti_viewer.ui_main")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please review the test output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())