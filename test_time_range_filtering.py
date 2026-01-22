#!/usr/bin/env python3
"""
Test the new time range filtering functionality.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTime
from xti_viewer.ui_main import XTIMainWindow

def test_time_range_filtering():
    """Test the new time range filtering UI and functionality."""
    
    print("Testing Time Range Filtering...")
    print("="*50)
    
    # Create QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create main window
    window = XTIMainWindow()
    
    # Load the XTI file
    print("Loading XTI file...")
    try:
        window.load_file("HL7812_fallback_NOK.xti")
        print("✅ File loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load file: {e}")
        return
    
    # Check if time range was initialized
    if hasattr(window, 'trace_start_time') and window.trace_start_time:
        start_time = window.trace_start_time
        end_time = window.trace_end_time
        print(f"📅 Trace time range: {start_time.toString('hh:mm:ss')} - {end_time.toString('hh:mm:ss')}")
        
        # Test different time ranges
        print("\n🧪 Testing Time Range Filters:")
        
        # Test 1: Full range
        print("\nTest 1: Full time range")
        window.reset_time_filter()
        total_items = window.filter_model.rowCount()
        print(f"  Total items (all time): {total_items}")
        
        # Test 2: Last 5 minutes
        print("\nTest 2: Last 5 minutes")
        window.set_last_minutes(5)
        last_5min_items = window.filter_model.rowCount()
        print(f"  Items (last 5min): {last_5min_items}")
        
        # Test 3: Last 30 minutes
        print("\nTest 3: Last 30 minutes")
        window.set_last_minutes(30)
        last_30min_items = window.filter_model.rowCount()
        print(f"  Items (last 30min): {last_30min_items}")
        
        # Test 4: Custom range (middle 50% of trace)
        print("\nTest 4: Custom time range")
        trace_duration_sec = start_time.secsTo(end_time)
        if trace_duration_sec < 0:
            trace_duration_sec += 24 * 60 * 60
        
        quarter_duration = trace_duration_sec // 4
        custom_start = start_time.addSecs(quarter_duration)
        custom_end = end_time.addSecs(-quarter_duration)
        
        window.start_time_edit.setTime(custom_start)
        window.end_time_edit.setTime(custom_end)
        window.on_time_range_changed()
        custom_items = window.filter_model.rowCount()
        print(f"  Custom range ({custom_start.toString('hh:mm:ss')} - {custom_end.toString('hh:mm:ss')}): {custom_items}")
        
        # Test 5: Combined with other filters
        print("\nTest 5: Time range + Command type filter")
        window.reset_time_filter()
        
        # Apply OPEN command filter
        window.open_checkbox.setChecked(True)
        window.send_checkbox.setChecked(False)
        window.receive_checkbox.setChecked(False)
        window.close_checkbox.setChecked(False)
        window.envelope_checkbox.setChecked(False)
        window.terminal_checkbox.setChecked(False)
        window.on_command_filter_changed()
        
        open_all_time = window.filter_model.rowCount()
        print(f"  OPEN commands (all time): {open_all_time}")
        
        # Apply time filter as well
        window.set_last_minutes(30)
        open_last_30min = window.filter_model.rowCount()
        print(f"  OPEN commands (last 30min): {open_last_30min}")
        
        print("\n✅ Time range filtering tests completed!")
        
        # Show the window for manual testing
        print("\n🖥️  Opening window for manual testing...")
        window.show()
        
        return window
        
    else:
        print("❌ Time range was not initialized properly")
        return None

if __name__ == "__main__":
    window = test_time_range_filtering()
    
    if window:
        print("\n📝 Manual Testing Instructions:")
        print("1. Check the 'Time Range' section in Advanced Filters")
        print("2. Try adjusting the From/To time fields")
        print("3. Test the quick buttons: 'All Time', 'Last 5min', etc.")
        print("4. Combine time filtering with other filters")
        print("5. Verify the duration info updates correctly")
        print("\nClose the window when done testing.")
        
        # Run the application
        sys.exit(QApplication.instance().exec())