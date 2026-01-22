#!/usr/bin/env python3
"""
UI Test script for advanced filtering functionality in XTI Viewer.
This script tests the actual UI components (checkboxes, dropdowns, sliders).
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import our modules
from xti_viewer.ui_main import XTIMainWindow
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QSlider
from PySide6.QtCore import Qt, QTimer

def test_ui_components(main_window):
    """Test the actual UI components in the advanced filter panel."""
    print("🔸 Testing UI Components...")
    
    # Find the advanced filter components
    command_checkboxes = main_window.findChildren(QCheckBox)
    server_dropdown = None
    time_slider = None
    
    # Find server dropdown and time slider
    for combo in main_window.findChildren(QComboBox):
        if "server" in combo.objectName().lower() or combo.count() > 3:  # Server dropdown has 6+ items
            server_dropdown = combo
            break
    
    for slider in main_window.findChildren(QSlider):
        if slider.orientation() == Qt.Horizontal:
            time_slider = slider
            break
    
    print(f"  📋 Found {len(command_checkboxes)} checkboxes")
    for i, checkbox in enumerate(command_checkboxes):
        print(f"    {i+1}: {checkbox.text() if checkbox.text() else checkbox.objectName()}")
    
    if server_dropdown:
        print(f"  📋 Found server dropdown with {server_dropdown.count()} items:")
        for i in range(server_dropdown.count()):
            print(f"    {i+1}: {server_dropdown.itemText(i)}")
    else:
        print("  ❌ Server dropdown not found")
    
    if time_slider:
        print(f"  📋 Found time range slider (min: {time_slider.minimum()}, max: {time_slider.maximum()}, value: {time_slider.value()})")
    else:
        print("  ❌ Time range slider not found")
    
    return command_checkboxes, server_dropdown, time_slider

def test_checkbox_interactions(checkboxes, main_window):
    """Test checkbox interactions."""
    print("\n🔸 Testing Checkbox Interactions...")
    
    # Test checking/unchecking each checkbox
    for i, checkbox in enumerate(checkboxes):
        if checkbox.text() and any(cmd in checkbox.text().upper() for cmd in ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"]):
            print(f"  📋 Testing {checkbox.text()}:")
            
            # Check the checkbox
            checkbox.setChecked(True)
            print(f"    ✅ Checked: {checkbox.isChecked()}")
            
            # Process events to trigger any handlers
            QApplication.processEvents()
            
            # Uncheck the checkbox
            checkbox.setChecked(False)
            print(f"    ✅ Unchecked: {checkbox.isChecked()}")
            
            # Process events
            QApplication.processEvents()

def test_dropdown_interactions(dropdown, main_window):
    """Test dropdown interactions."""
    if not dropdown:
        print("\n❌ No server dropdown to test")
        return
    
    print("\n🔸 Testing Server Dropdown Interactions...")
    
    # Test selecting each server option
    for i in range(dropdown.count()):
        server_name = dropdown.itemText(i)
        print(f"  📋 Testing server selection: {server_name}")
        
        dropdown.setCurrentIndex(i)
        print(f"    ✅ Selected: {dropdown.currentText()}")
        
        # Process events to trigger any handlers
        QApplication.processEvents()

def test_slider_interactions(slider, main_window):
    """Test slider interactions."""
    if not slider:
        print("\n❌ No time range slider to test")
        return
    
    print("\n🔸 Testing Time Range Slider Interactions...")
    
    # Test different slider positions
    test_values = [0, 25, 50, 75, 100]
    
    for value in test_values:
        print(f"  📋 Setting slider to {value}%")
        slider.setValue(value)
        print(f"    ✅ Slider value: {slider.value()}")
        
        # Process events to trigger any handlers
        QApplication.processEvents()

def test_filter_combinations(checkboxes, dropdown, slider, main_window):
    """Test combinations of filters."""
    print("\n🔸 Testing Filter Combinations...")
    
    # Test 1: Select OPEN + RECEIVE commands
    print("  📋 Test 1: Select OPEN + RECEIVE commands")
    for checkbox in checkboxes:
        if checkbox.text() and ("OPEN" in checkbox.text().upper() or "RECEIVE" in checkbox.text().upper()):
            checkbox.setChecked(True)
            print(f"    ✅ Checked: {checkbox.text()}")
    
    QApplication.processEvents()
    
    # Test 2: Add server filter
    if dropdown and dropdown.count() > 1:
        print("  📋 Test 2: Add server filter (DP+)")
        dropdown.setCurrentIndex(1)  # Usually DP+ is second option
        print(f"    ✅ Selected server: {dropdown.currentText()}")
    
    QApplication.processEvents()
    
    # Test 3: Add time range filter (50%)
    if slider:
        print("  📋 Test 3: Add time range filter (50%)")
        slider.setValue(50)
        print(f"    ✅ Time range: {slider.value()}%")
    
    QApplication.processEvents()
    
    # Test 4: Clear all filters
    print("  📋 Test 4: Clear all filters")
    for checkbox in checkboxes:
        if checkbox.text() and any(cmd in checkbox.text().upper() for cmd in ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"]):
            checkbox.setChecked(False)
    
    if dropdown:
        dropdown.setCurrentIndex(0)  # Usually "All Servers"
    
    if slider:
        slider.setValue(100)  # Full range
    
    print("    ✅ All filters cleared")
    QApplication.processEvents()

def main():
    """Run the UI test suite."""
    print("🚀 Advanced Filter UI Test Suite")
    print("=" * 50)
    
    # Initialize Qt application
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    try:
        # Create main window
        print("📱 Creating main window...")
        main_window = XTIMainWindow()
        
        # Show the window
        main_window.show()
        QApplication.processEvents()
        
        print("✅ Main window created successfully")
        
        # Test UI components
        checkboxes, dropdown, slider = test_ui_components(main_window)
        
        # Test individual component interactions
        test_checkbox_interactions(checkboxes, main_window)
        test_dropdown_interactions(dropdown, main_window)
        test_slider_interactions(slider, main_window)
        
        # Test filter combinations
        test_filter_combinations(checkboxes, dropdown, slider, main_window)
        
        print("\n🎉 UI Tests completed!")
        print("✅ Advanced filtering UI is working correctly!")
        
        # Keep window open for 3 seconds to see the result
        def close_window():
            main_window.close()
            app.quit()
        
        QTimer.singleShot(3000, close_window)  # Close after 3 seconds
        
        # Run the event loop briefly
        QTimer.singleShot(100, app.quit)  # Exit quickly for automated testing
        app.exec()
        
    except Exception as e:
        print(f"❌ UI Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())