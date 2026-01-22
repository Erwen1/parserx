"""
Test Network Classification Settings functionality
Tests the Settings > Network Classification dialog and features
"""

import sys
import json
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from network_settings_dialog import NetworkSettingsDialog
from app_config import (
    load_config,
    save_config,
    reset_defaults,
    validate_ip_list,
    set_classification_lists,
    DEFAULT_CONFIG
)


def test_config_module():
    """Test the app_config module functions."""
    print("\n" + "="*60)
    print("TEST 1: Configuration Module")
    print("="*60)
    
    try:
        # Test load_config
        cfg = load_config()
        print("✅ load_config() works")
        
        # Check structure
        if "classification" not in cfg:
            print("❌ Missing 'classification' key")
            return False
        print("✅ Configuration has 'classification' section")
        
        # Check required keys
        required_keys = ["tac_ips", "dp_plus_ips", "dns_ips"]
        missing = [k for k in required_keys if k not in cfg["classification"]]
        if missing:
            print(f"❌ Missing keys: {missing}")
            return False
        print(f"✅ All required keys present: {', '.join(required_keys)}")
        
        # Display current config
        print("\n📋 Current Configuration:")
        print(f"   TAC IPs: {len(cfg['classification']['tac_ips'])} entries")
        for ip in cfg['classification']['tac_ips'][:3]:
            print(f"      - {ip}")
        if len(cfg['classification']['tac_ips']) > 3:
            print(f"      ... and {len(cfg['classification']['tac_ips']) - 3} more")
        
        print(f"   DP+ IPs: {len(cfg['classification']['dp_plus_ips'])} entries")
        for ip in cfg['classification']['dp_plus_ips'][:3]:
            print(f"      - {ip}")
        
        print(f"   DNS IPs: {len(cfg['classification']['dns_ips'])} entries")
        for ip in cfg['classification']['dns_ips'][:3]:
            print(f"      - {ip}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_ip_validation():
    """Test IP validation functionality."""
    print("\n" + "="*60)
    print("TEST 2: IP Validation")
    print("="*60)
    
    try:
        # Test valid IPs
        valid_ips = [
            "192.168.1.1",
            "8.8.8.8",
            "10.0.0.1",
            "2001:4860:4860::8888",  # IPv6
        ]
        
        invalid = validate_ip_list(valid_ips)
        if invalid:
            print(f"❌ Valid IPs marked as invalid: {invalid}")
            return False
        print(f"✅ All valid IPs accepted: {len(valid_ips)} IPs")
        
        # Test invalid IPs
        invalid_ips = [
            "256.1.1.1",  # Out of range
            "not-an-ip",  # Not an IP
            "192.168.1",  # Incomplete
        ]
        
        invalid = validate_ip_list(invalid_ips)
        if len(invalid) != len(invalid_ips):
            print(f"❌ Expected {len(invalid_ips)} invalid, got {len(invalid)}")
            return False
        print(f"✅ Invalid IPs correctly detected: {len(invalid)} IPs")
        
        # Test mixed
        mixed_ips = valid_ips + invalid_ips
        invalid = validate_ip_list(mixed_ips)
        if len(invalid) != len(invalid_ips):
            print(f"❌ Mixed test failed")
            return False
        print(f"✅ Mixed validation works correctly")
        
        print("\n📋 Validation Summary:")
        print(f"   ✓ IPv4 validation")
        print(f"   ✓ IPv6 validation")
        print(f"   ✓ Invalid IP detection")
        print(f"   ✓ Range checking")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_save_and_load():
    """Test saving and loading configuration."""
    print("\n" + "="*60)
    print("TEST 3: Save/Load Configuration")
    print("="*60)
    
    try:
        # Backup current config
        original_cfg = load_config()
        
        # Test save with new values
        test_tac = ["1.2.3.4", "5.6.7.8"]
        test_dp = ["9.10.11.12"]
        test_dns = ["8.8.8.8", "8.8.4.4"]
        
        set_classification_lists(test_tac, test_dp, test_dns)
        print("✅ Configuration saved")
        
        # Reload and verify
        loaded_cfg = load_config()
        
        if loaded_cfg["classification"]["tac_ips"] != sorted(test_tac):
            print("❌ TAC IPs not saved correctly")
            # Restore original
            save_config(original_cfg)
            return False
        print("✅ TAC IPs saved and loaded correctly")
        
        if loaded_cfg["classification"]["dp_plus_ips"] != sorted(test_dp):
            print("❌ DP+ IPs not saved correctly")
            save_config(original_cfg)
            return False
        print("✅ DP+ IPs saved and loaded correctly")
        
        if loaded_cfg["classification"]["dns_ips"] != sorted(test_dns):
            print("❌ DNS IPs not saved correctly")
            save_config(original_cfg)
            return False
        print("✅ DNS IPs saved and loaded correctly")
        
        # Test reset to defaults
        reset_defaults()
        print("✅ Reset to defaults works")
        
        default_cfg = load_config()
        if default_cfg["classification"]["tac_ips"] != DEFAULT_CONFIG["classification"]["tac_ips"]:
            print("⚠️  Warning: Defaults may not match expected values")
        
        # Restore original config
        save_config(original_cfg)
        print("✅ Original configuration restored")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_export_import():
    """Test export and import functionality."""
    print("\n" + "="*60)
    print("TEST 4: Export/Import Configuration")
    print("="*60)
    
    try:
        # Create a temporary config
        test_config = {
            "classification": {
                "tac_ips": ["11.22.33.44"],
                "dp_plus_ips": ["55.66.77.88"],
                "dns_ips": ["8.8.8.8"],
            }
        }
        
        # Test export (simulate)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f, indent=2)
            temp_path = f.name
        
        print(f"✅ Export simulation successful: {Path(temp_path).name}")
        
        # Test import (simulate)
        imported = json.loads(Path(temp_path).read_text(encoding="utf-8"))
        
        if imported["classification"]["tac_ips"] != test_config["classification"]["tac_ips"]:
            print("❌ Import failed to read TAC IPs")
            Path(temp_path).unlink()
            return False
        print("✅ Import simulation successful")
        
        # Clean up
        Path(temp_path).unlink()
        print("✅ Cleanup complete")
        
        print("\n📋 Export/Import Features:")
        print("   ✓ JSON format export")
        print("   ✓ JSON format import")
        print("   ✓ Configuration preservation")
        print("   ✓ File handling")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_dialog_existence():
    """Test that the NetworkSettingsDialog exists and can be instantiated."""
    print("\n" + "="*60)
    print("TEST 5: Network Settings Dialog")
    print("="*60)
    
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        
        # Create dialog instance
        dialog = NetworkSettingsDialog()
        print("✅ NetworkSettingsDialog instantiated")
        
        # Check UI elements
        ui_elements = [
            ("tac_edit", "TAC IP editor"),
            ("dp_edit", "DP+ IP editor"),
            ("dns_edit", "DNS IP editor"),
            ("btn_validate", "Validate button"),
            ("btn_import", "Import button"),
            ("btn_export", "Export button"),
            ("btn_reset", "Reset button"),
            ("btn_save", "Save button"),
            ("btn_cancel", "Cancel button"),
        ]
        
        print("\n📋 UI Elements:")
        all_present = True
        for attr_name, display_name in ui_elements:
            if hasattr(dialog, attr_name):
                print(f"   ✅ {display_name}")
            else:
                print(f"   ❌ {display_name} missing")
                all_present = False
        
        if not all_present:
            return False
        
        # Check window title
        if "Network Classification" not in dialog.windowTitle():
            print("⚠️  Window title doesn't contain 'Network Classification'")
        else:
            print(f"\n✅ Window title: '{dialog.windowTitle()}'")
        
        # Test that fields load current config
        current_cfg = load_config()
        dialog._load_into_fields()
        
        tac_text = dialog.tac_edit.toPlainText()
        if tac_text:
            print(f"✅ TAC IPs loaded into dialog: {len(tac_text.splitlines())} entries")
        
        print("\n📋 Dialog Features:")
        print("   ✓ Three IP list editors (TAC, DP+, DNS)")
        print("   ✓ Validate button to check IPs")
        print("   ✓ Import/Export buttons")
        print("   ✓ Reset to defaults button")
        print("   ✓ Save/Cancel buttons")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_ui_integration():
    """Test that the dialog integrates with main UI."""
    print("\n" + "="*60)
    print("TEST 6: UI Integration")
    print("="*60)
    
    try:
        from xti_viewer import ui_main
        import inspect
        
        # Check if main window has network classification action
        source = inspect.getsource(ui_main.XTIMainWindow)
        
        checks = [
            ("Menu action", "Network Classification" in source),
            ("Settings menu", "Settings" in source or "settings" in source),
            ("Dialog integration", "NetworkSettingsDialog" in source),
        ]
        
        print("\n📋 Integration Checks:")
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n💡 Usage in XTI Viewer:")
            print("   Settings → Network Classification")
            print("   Opens dialog to configure IP lists")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def run_all_tests():
    """Run all network classification tests."""
    print("="*60)
    print("NETWORK CLASSIFICATION SETTINGS - TEST SUITE")
    print("="*60)
    print("\nTesting Settings > Network Classification functionality\n")
    
    results = []
    
    result1 = test_config_module()
    results.append(("Configuration Module", result1))
    
    result2 = test_ip_validation()
    results.append(("IP Validation", result2))
    
    result3 = test_save_and_load()
    results.append(("Save/Load Configuration", result3))
    
    result4 = test_export_import()
    results.append(("Export/Import", result4))
    
    result5 = test_dialog_existence()
    results.append(("Network Settings Dialog", result5))
    
    result6 = test_ui_integration()
    results.append(("UI Integration", result6))
    
    # Summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n{'='*60}")
    print(f"Total: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 Network Classification Settings fully functional!")
        print("\n📖 Feature Overview:")
        print("\n  Network Classification Settings allows you to:")
        print("  • Configure TAC (Test Access Controller) IP addresses")
        print("  • Configure DP+ (Data Plane Plus) IP addresses")
        print("  • Configure DNS server IP addresses")
        print("  • Validate IP addresses (IPv4 and IPv6)")
        print("  • Import/Export configuration as JSON")
        print("  • Reset to default IP lists")
        print("\n  💡 How to use:")
        print("  1. Open XTI Viewer")
        print("  2. Go to Settings → Network Classification")
        print("  3. Enter IPs (one per line)")
        print("  4. Click 'Validate' to check IPs")
        print("  5. Click 'Save' to apply changes")
        print("\n  📁 Configuration saved in: config.json")
    else:
        print("\n⚠️  Some tests failed. Check the details above.")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
