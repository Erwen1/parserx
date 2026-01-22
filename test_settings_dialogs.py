"""Test the new About and Preferences dialogs."""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

# Test the About dialog
def test_about_dialog():
    """Test About dialog."""
    print("\n=== Testing About Dialog ===")
    
    from xti_viewer.about_dialog import AboutDialog
    
    # Check class attributes
    print(f"✓ Version: {AboutDialog.VERSION}")
    print(f"✓ Author: {AboutDialog.AUTHOR}")
    print(f"✓ Email: {AboutDialog.EMAIL}")
    print(f"✓ Organization: {AboutDialog.ORGANIZATION}")
    print(f"✓ Description: {AboutDialog.DESCRIPTION[:50]}...")
    
    # Create dialog (won't show in automated test)
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = AboutDialog()
    
    # Check dialog properties
    print(f"✓ Window title: {dlg.windowTitle()}")
    print(f"✓ Minimum width: {dlg.minimumWidth()}px")
    print(f"✓ Minimum height: {dlg.minimumHeight()}px")
    
    print("\n✓ About dialog created successfully")
    return True

def test_preferences_dialog():
    """Test Preferences dialog."""
    print("\n=== Testing Preferences Dialog ===")
    
    from xti_viewer.preferences_dialog import PreferencesDialog
    
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = PreferencesDialog()
    
    # Check dialog properties
    print(f"✓ Window title: {dlg.windowTitle()}")
    print(f"✓ Minimum width: {dlg.minimumWidth()}px")
    print(f"✓ Minimum height: {dlg.minimumHeight()}px")
    
    # Check settings structure
    settings = dlg.get_settings()
    print(f"✓ Settings categories: {list(settings.keys())}")
    
    # Check each category
    for category, options in settings.items():
        print(f"  - {category}: {list(options.keys())}")
    
    # Check default values
    print(f"\n✓ Default font size: {settings['appearance']['font_size']}")
    print(f"✓ Default theme: {settings['appearance']['theme']}")
    print(f"✓ Confirm exit: {settings['behavior']['confirm_exit']}")
    print(f"✓ Max recent files: {settings['behavior']['max_recent_files']}")
    print(f"✓ Export format: {settings['export']['export_format']}")
    print(f"✓ Logging enabled: {settings['debugging']['enable_logging']}")
    
    print("\n✓ Preferences dialog created successfully")
    return True

def test_menu_integration():
    """Test that the dialogs are properly integrated in the menu."""
    print("\n=== Testing Menu Integration ===")
    
    # Check if the methods exist in ui_main.py
    import inspect
    from xti_viewer.ui_main import XTIMainWindow
    
    methods = ['open_about_dialog', 'open_preferences_dialog', 'open_network_settings_dialog']
    
    for method_name in methods:
        if hasattr(XTIMainWindow, method_name):
            method = getattr(XTIMainWindow, method_name)
            if callable(method):
                print(f"✓ Method '{method_name}' exists in XTIMainWindow")
                
                # Get method signature
                sig = inspect.signature(method)
                print(f"  Signature: {method_name}{sig}")
            else:
                print(f"✗ '{method_name}' exists but is not callable")
                return False
        else:
            print(f"✗ Method '{method_name}' not found in XTIMainWindow")
            return False
    
    print("\n✓ All menu integration methods exist")
    return True

def test_visual_demo():
    """Run a visual demo of the dialogs."""
    print("\n=== Visual Demo ===")
    print("Opening dialogs for visual inspection...")
    
    from xti_viewer.about_dialog import AboutDialog
    from xti_viewer.preferences_dialog import PreferencesDialog
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Create a simple launcher window
    window = QMainWindow()
    window.setWindowTitle("Dialog Demo")
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    # About button
    about_btn = QPushButton("Show About Dialog")
    def show_about():
        dlg = AboutDialog(window)
        dlg.exec()
    about_btn.clicked.connect(show_about)
    layout.addWidget(about_btn)
    
    # Preferences button
    pref_btn = QPushButton("Show Preferences Dialog")
    def show_preferences():
        dlg = PreferencesDialog(window)
        if dlg.exec():
            print("Preferences saved!")
            print(f"Settings: {dlg.get_settings()}")
    pref_btn.clicked.connect(show_preferences)
    layout.addWidget(pref_btn)
    
    # Close button
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(window.close)
    layout.addWidget(close_btn)
    
    window.setCentralWidget(central)
    window.resize(300, 150)
    window.show()
    
    print("✓ Demo window opened. Click buttons to test dialogs.")
    print("  Close the window when done testing.")
    
    app.exec()
    return True

def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Testing About and Preferences Dialogs")
    print("=" * 60)
    
    tests = [
        ("About Dialog", test_about_dialog),
        ("Preferences Dialog", test_preferences_dialog),
        ("Menu Integration", test_menu_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\n✗ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test_name} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{passed+failed} passed ({100*passed/(passed+failed):.1f}%)")
    print("=" * 60)
    
    # Ask if user wants to see visual demo
    print("\nWould you like to see a visual demo of the dialogs? (y/n)")
    print("(This will open a window - automated test mode will skip)")
    
    # For automated testing, just return
    if '--demo' in sys.argv:
        test_visual_demo()

if __name__ == "__main__":
    run_all_tests()
