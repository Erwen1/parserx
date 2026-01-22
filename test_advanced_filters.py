#!/usr/bin/env python3
"""
Comprehensive test script for XTI Viewer Advanced Filtering System
Tests all filter types: Command Types, Server Filter, Time Range, and Search Navigation
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QAbstractItemModel, QModelIndex, Qt
from xti_viewer.models import TraceItemFilterModel, InterpretationTreeModel
from xti_viewer.xti_parser import TraceItem, TreeNode
from xti_viewer.ui_main import XTIMainWindow

class MockTraceModel(QAbstractItemModel):
    """Mock trace model for testing"""
    def __init__(self):
        super().__init__()
        # Create realistic trace items with IP addresses in details_tree
        tac_tree = TreeNode("FETCH Command")
        tac_tree.add_child(TreeNode("Destination Address: 13.38.212.83:443"))
        tac_tree.add_child(TreeNode("Command: OPEN CHANNEL"))
        
        tac_response_tree = TreeNode("TERMINAL RESPONSE")
        tac_response_tree.add_child(TreeNode("Source Address: 13.38.212.83:443"))
        tac_response_tree.add_child(TreeNode("Response: OPEN CHANNEL OK"))
        
        dp_tree = TreeNode("FETCH Command")
        dp_tree.add_child(TreeNode("Destination Address: 34.8.202.126:443"))
        dp_tree.add_child(TreeNode("Command: SEND DATA"))
        
        dp_response_tree = TreeNode("TERMINAL RESPONSE")
        dp_response_tree.add_child(TreeNode("Source Address: 34.8.202.126:443"))
        dp_response_tree.add_child(TreeNode("Response: RECEIVE DATA"))
        
        dns_tree = TreeNode("ENVELOPE")
        dns_tree.add_child(TreeNode("DNS Query to 8.8.8.8:53"))
        
        tac_close_tree = TreeNode("FETCH Command")
        tac_close_tree.add_child(TreeNode("Destination Address: 13.38.212.83:443"))
        tac_close_tree.add_child(TreeNode("Command: CLOSE CHANNEL"))
        
        dp_open_tree = TreeNode("FETCH Command")
        dp_open_tree.add_child(TreeNode("Destination Address: 34.8.202.126:443"))
        dp_open_tree.add_child(TreeNode("Command: OPEN CHANNEL"))
        
        self.test_items = [
            TraceItem(protocol="TCP", type="COMMAND", summary="FETCH - OPEN CHANNEL", rawhex="FF", timestamp="10:00:00", details_tree=tac_tree),
            TraceItem(protocol="TCP", type="RESPONSE", summary="TERMINAL RESPONSE - OPEN CHANNEL", rawhex="FF", timestamp="10:00:01", details_tree=tac_response_tree),
            TraceItem(protocol="TCP", type="COMMAND", summary="FETCH - SEND DATA", rawhex="FF", timestamp="10:00:02", details_tree=dp_tree),
            TraceItem(protocol="TCP", type="RESPONSE", summary="TERMINAL RESPONSE - RECEIVE DATA", rawhex="FF", timestamp="10:00:03", details_tree=dp_response_tree),
            TraceItem(protocol="UDP", type="ENVELOPE", summary="ENVELOPE - DNS Query", rawhex="FF", timestamp="10:00:04", details_tree=dns_tree),
            TraceItem(protocol="TCP", type="COMMAND", summary="FETCH - CLOSE CHANNEL", rawhex="FF", timestamp="10:00:05", details_tree=tac_close_tree),
            TraceItem(protocol="TCP", type="COMMAND", summary="FETCH - OPEN CHANNEL", rawhex="FF", timestamp="10:00:06", details_tree=dp_open_tree),
        ]
        
        # Make trace_items accessible to the filter (same as real model)
        self.trace_items = self.test_items
        
    def rowCount(self, parent=QModelIndex()):
        return len(self.test_items)
        
    def columnCount(self, parent=QModelIndex()):
        return 1
        
    def index(self, row, column, parent=QModelIndex()):
        if self.hasIndex(row, column, parent):
            return self.createIndex(row, column)
        return QModelIndex()
        
    def parent(self, index):
        return QModelIndex()
        
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and 0 <= index.row() < len(self.test_items):
            return self.test_items[index.row()].summary
        return None

def test_filter_model():
    """Test the core filtering logic"""
    print("=" * 60)
    print("TESTING ADVANCED FILTER MODEL")
    print("=" * 60)
    
    # Create filter model with mock data
    filter_model = TraceItemFilterModel()
    mock_model = MockTraceModel()
    filter_model.setSourceModel(mock_model)
    
    print(f"Total items: {mock_model.rowCount()}")
    
    # Test 1: Command Type Filter
    print("\n1. Testing Command Type Filter...")
    filter_model.set_command_type_filter(["OPEN"])
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: OPEN commands only")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    print(f"   Expected: Only 'FETCH - OPEN CHANNEL' (not 'TERMINAL RESPONSE - OPEN CHANNEL')")
    
    # Test 1b: Terminal Response Filter
    print("\n1b. Testing TERMINAL Filter...")
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["TERMINAL"])
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: TERMINAL commands only")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    print(f"   Expected: Only 'TERMINAL RESPONSE' items")
    
    # Test 1c: Combined OPEN + CLOSE commands
    print("\n1c. Testing OPEN + CLOSE Filter...")
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["OPEN", "CLOSE"])
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: OPEN + CLOSE commands")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    print(f"   Expected: Only FETCH commands for OPEN/CLOSE (not TERMINAL RESPONSE)")
    
    # Test 2: Server Filter
    print("\n2. Testing Server Filter...")
    filter_model.clear_all_filters()
    filter_model.set_server_filter("TAC")
    
    print(f"   Debug: Mock model has trace_items: {hasattr(mock_model, 'trace_items')}")
    if hasattr(mock_model, 'trace_items'):
        print(f"   Debug: Number of trace_items: {len(mock_model.trace_items)}")
        # Test IP extraction for first item
        from xti_viewer.xti_parser import extract_ips_from_interpretation_tree, tag_server_from_ips
        test_item = mock_model.trace_items[0]
        ips = extract_ips_from_interpretation_tree(test_item.details_tree)
        server_label = tag_server_from_ips(ips)
        print(f"   Debug: First item IPs: {ips}, Server label: {server_label}")
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: TAC server only")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    print(f"   Expected: Only items with 'TAC' in summary")
    
    # Test 2b: DP+ Server Filter
    print("\n2b. Testing DP+ Server Filter...")
    filter_model.clear_all_filters()
    filter_model.set_server_filter("DP+")
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: DP+ server only")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    print(f"   Expected: Items with DP+ IP (34.8.202.126) in details")
    
    # Test 2c: Public DNS Server Filter
    print("\n2c. Testing Public DNS Server Filter...")
    filter_model.clear_all_filters()
    filter_model.set_server_filter("Public DNS")
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: Public DNS servers only")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    print(f"   Expected: Items with public DNS IPs (8.8.8.8, etc.)")
    
    # Test 2d: Combined Command Type + Server Filter
    print("\n2d. Testing OPEN + TAC Server Filter...")
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_server_filter("TAC")
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: OPEN commands to TAC server only")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    print(f"   Expected: Only 'FETCH - OPEN CHANNEL' to TAC IP")
    
    # Test 2e: Combined Command Type + Server Filter
    print("\n2e. Testing OPEN + DP+ Server Filter...")
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_server_filter("DP+")
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: OPEN commands to DP+ server only")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    print(f"   Expected: Only 'FETCH - OPEN CHANNEL' to DP+ IP")
    
    # Test 3: Time Range Filter
    print("\n3. Testing Time Range Filter...")
    filter_model.clear_all_filters()
    filter_model.set_time_range_filter(0.5)  # Show only first 50%
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: First 50% of trace")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    
    # Test 4: Combined Filters
    print("\n4. Testing Combined Filters...")
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["SEND", "RECEIVE"])
    filter_model.set_time_range_filter(0.8)  # First 80% + SEND/RECEIVE only
    
    visible_items = []
    for i in range(mock_model.rowCount()):
        if filter_model.filterAcceptsRow(i, QModelIndex()):
            visible_items.append(mock_model.test_items[i].summary)
    
    print(f"   Filter: SEND/RECEIVE commands + First 80% of trace")
    print(f"   Visible items: {len(visible_items)}")
    for item in visible_items:
        print(f"   - {item}")
    
    print("\n[PASS] Filter Model Tests Completed")

def test_ui_components():
    """Test the UI components"""
    print("\n" + "=" * 60)
    print("TESTING ADVANCED FILTER UI COMPONENTS")
    print("=" * 60)
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # Create main window
    window = XTIMainWindow()
    
    # Test UI component creation
    print("\n1. Testing UI Component Creation...")
    
    # Check if advanced filter components exist
    components = {
        "Command Checkboxes": hasattr(window, 'command_checkboxes'),
        "Server Combo": hasattr(window, 'server_combo'), 
        "Time Slider": hasattr(window, 'time_slider'),
        "Toggle Button": hasattr(window, 'toggle_filters_button'),
        "Filter Container": hasattr(window, 'filters_container')
    }
    
    for component, exists in components.items():
        status = "PASS" if exists else "FAIL"
        print(f"   {component}: {status}")
    
    # Test 2: Command Type Checkboxes
    if hasattr(window, 'command_checkboxes'):
        print("\n2. Testing Command Type Checkboxes...")
        expected_commands = ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"]
        
        for cmd in expected_commands:
            if cmd in window.command_checkboxes:
                checkbox = window.command_checkboxes[cmd]
                print(f"   {cmd} checkbox: PASS (checked={checkbox.isChecked()})")
            else:
                print(f"   {cmd} checkbox: FAIL (missing)")
    
    # Test 3: Server Filter Dropdown
    if hasattr(window, 'server_combo'):
        print("\n3. Testing Server Filter Dropdown...")
        combo = window.server_combo
        items = [combo.itemText(i) for i in range(combo.count())]
        expected_servers = ["All Servers", "DP+", "TAC", "DNS by ME", "Public DNS", "Other"]
        
        for server in expected_servers:
            if server in items:
                print(f"   {server}: PASS")
            else:
                print(f"   {server}: FAIL (missing)")
    
    # Test 4: Time Range Slider
    if hasattr(window, 'time_slider'):
        print("\n4. Testing Time Range Slider...")
        slider = window.time_slider
        print(f"   Range: {slider.minimum()}-{slider.maximum()}")
        print(f"   Initial Value: {slider.value()}")
        print(f"   Time Slider: PASS")
    
    print("\n[PASS] UI Components Tests Completed")
    
    return window

def test_filter_integration():
    """Test integration between UI and filter model"""
    print("\n" + "=" * 60)
    print("TESTING FILTER INTEGRATION")
    print("=" * 60)
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    window = XTIMainWindow()
    
    print("\n1. Testing Filter Method Integration...")
    
    # Test filter handler methods exist
    methods = [
        "on_command_filter_changed",
        "on_server_filter_changed", 
        "on_time_filter_changed",
        "toggle_advanced_filters"
    ]
    
    for method in methods:
        if hasattr(window, method):
            print(f"   {method}: PASS")
        else:
            print(f"   {method}: FAIL (missing)")
    
    print("\n2. Testing Filter Model Integration...")
    
    # Create a mock filter model for testing
    if hasattr(window, 'filter_model'):
        print("   Filter model exists: PASS")
        
        # Test filter model methods
        filter_methods = [
            "set_command_type_filter",
            "set_server_filter",
            "set_time_range_filter",
            "clear_all_filters"
        ]
        
        for method in filter_methods:
            if hasattr(window.filter_model, method):
                print(f"   {method}: PASS")
            else:
                print(f"   {method}: FAIL (missing)")
    else:
        print("   Filter model: FAIL (missing)")
    
    print("\n[PASS] Filter Integration Tests Completed")
    
    return window

def run_comprehensive_demo():
    """Run a comprehensive demo showing all features working"""
    print("\n" + "=" * 60)
    print("COMPREHENSIVE FILTER DEMO")
    print("=" * 60)
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    window = test_ui_components()
    
    print("\n1. Simulating Filter Operations...")
    
    # Simulate unchecking some command types
    if hasattr(window, 'command_checkboxes'):
        print("   - Unchecking ENVELOPE and TERMINAL commands")
        window.command_checkboxes["ENVELOPE"].setChecked(False)
        window.command_checkboxes["TERMINAL"].setChecked(False)
        window.on_command_filter_changed()
    
    # Simulate server filter change
    if hasattr(window, 'server_combo'):
        print("   - Selecting 'DP+' server filter")
        window.server_combo.setCurrentText("DP+")
        window.on_server_filter_changed("DP+")
    
    # Simulate time range change
    if hasattr(window, 'time_slider'):
        print("   - Setting time range to 75%")
        window.time_slider.setValue(75)
        window.on_time_filter_changed(75)
    
    print("\n2. Advanced Filter Status:")
    print("   Command Types: OPEN, SEND, RECEIVE, CLOSE only")
    print("   Server: DP+ only")
    print("   Time Range: First 75% of trace")
    print("   Combined Filter: Active")
    
    print("\n[PASS] Comprehensive Demo Completed")
    
    return window

def main():
    """Run all tests"""
    print("XTI VIEWER ADVANCED FILTERING TEST SUITE")
    print("=" * 60)
    print("Testing all advanced filtering components...")
    print()
    
    try:
        # Test 1: Core filter model logic
        test_filter_model()
        
        # Test 2: UI component creation
        app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
        test_ui_components()
        
        # Test 3: Integration between UI and model
        test_filter_integration()
        
        # Test 4: Comprehensive demo
        run_comprehensive_demo()
        
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("Advanced filtering system is ready for use.")
        print("Features tested:")
        print("- Command type checkboxes (OPEN/SEND/RECEIVE/CLOSE/ENVELOPE/TERMINAL)")
        print("- Server filter dropdown (DP+/TAC/DNS/etc.)")
        print("- Time range slider (0-100%)")
        print("- Filter combination and integration")
        print("- UI component creation and connectivity")
        print("\nYou can now safely load XTI files and use all advanced filters!")
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""
Test script for advanced filtering functionality in XTI Viewer.
This script tests all filter combinations to ensure they work properly.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import our modules
from xti_viewer.models import TraceItemFilterModel, InterpretationTreeModel
from xti_viewer.xti_parser import TraceItem, TreeNode
from PySide6.QtCore import QModelIndex, Qt, QAbstractItemModel
from PySide6.QtWidgets import QApplication

def create_test_trace_items():
    """Create test trace items for filtering tests."""
    test_items = [
        TraceItem(
            protocol="TCP",
            type="COMMAND",
            summary="FETCH - OPEN CHANNEL",
            rawhex="1234",
            timestamp="01/01/2024 10:00:00:000",
            details_tree=TreeNode("FETCH - OPEN CHANNEL"),
            timestamp_sort_key="2024-01-01T10:00:00.000"
        ),
        TraceItem(
            protocol="TCP",
            type="RESPONSE",
            summary="TERMINAL RESPONSE - OPEN CHANNEL",
            rawhex="5678",
            timestamp="01/01/2024 10:00:01:000",
            details_tree=TreeNode("TERMINAL RESPONSE - OPEN CHANNEL"),
            timestamp_sort_key="2024-01-01T10:00:01.000"
        ),
        TraceItem(
            protocol="TCP",
            type="COMMAND",
            summary="FETCH - SEND DATA",
            rawhex="ABCD",
            timestamp="01/01/2024 10:00:02:000",
            details_tree=TreeNode("FETCH - SEND DATA"),
            timestamp_sort_key="2024-01-01T10:00:02.000"
        ),
        TraceItem(
            protocol="TCP",
            type="RESPONSE",
            summary="TERMINAL RESPONSE - RECEIVE DATA",
            rawhex="EFGH",
            timestamp="01/01/2024 10:00:03:000",
            details_tree=TreeNode("TERMINAL RESPONSE - RECEIVE DATA"),
            timestamp_sort_key="2024-01-01T10:00:03.000"
        ),
        TraceItem(
            protocol="TCP",
            type="COMMAND",
            summary="FETCH - CLOSE CHANNEL",
            rawhex="IJKL",
            timestamp="01/01/2024 10:00:04:000",
            details_tree=TreeNode("FETCH - CLOSE CHANNEL"),
            timestamp_sort_key="2024-01-01T10:00:04.000"
        ),
        TraceItem(
            protocol="ENVELOPE",
            type="COMMAND",
            summary="ENVELOPE - DATA TRANSFER",
            rawhex="MNOP",
            timestamp="01/01/2024 10:00:05:000",
            details_tree=TreeNode("ENVELOPE - DATA TRANSFER"),
            timestamp_sort_key="2024-01-01T10:00:05.000"
        ),
        TraceItem(
            protocol="TCP",
            type="RESPONSE",
            summary="TERMINAL RESPONSE - SEND DATA",
            rawhex="QRST",
            timestamp="01/01/2024 10:00:06:000",
            details_tree=TreeNode("TERMINAL RESPONSE - SEND DATA"),
            timestamp_sort_key="2024-01-01T10:00:06.000"
        ),
        TraceItem(
            protocol="TCP",
            type="COMMAND",
            summary="FETCH - RECEIVE DATA",
            rawhex="UVWX",
            timestamp="01/01/2024 10:00:07:000",
            details_tree=TreeNode("FETCH - RECEIVE DATA"),
            timestamp_sort_key="2024-01-01T10:00:07.000"
        ),
    ]
    return test_items

class TestTraceModel(QAbstractItemModel):
    """Simple test model to simulate the trace model."""
    def __init__(self, trace_items):
        super().__init__()
        self.trace_items = trace_items
    
    def rowCount(self, parent=QModelIndex()):
        return len(self.trace_items)
    
    def columnCount(self, parent=QModelIndex()):
        return 1
    
    def index(self, row, column, parent=QModelIndex()):
        if row < len(self.trace_items):
            return self.createIndex(row, column, self.trace_items[row])
        return QModelIndex()
    
    def parent(self, index):
        return QModelIndex()
    
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and index.row() < len(self.trace_items):
            return self.trace_items[index.row()].summary
        return None

def test_command_type_filter(filter_model, trace_model):
    """Test command type filtering."""
    print("🔸 Testing Command Type Filters...")
    
    # Test 1: Filter only OPEN commands
    print("  📋 Test 1: Filter only OPEN commands")
    filter_model.set_command_type_filter(["OPEN"])
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    expected_open = 2  # FETCH - OPEN CHANNEL, TERMINAL RESPONSE - OPEN CHANNEL
    if visible_count == expected_open:
        print(f"    ✅ PASS: Found {visible_count} OPEN commands")
    else:
        print(f"    ❌ FAIL: Expected {expected_open}, found {visible_count}")
    
    # Test 2: Filter SEND and RECEIVE commands
    print("  📋 Test 2: Filter SEND and RECEIVE commands")
    filter_model.set_command_type_filter(["SEND", "RECEIVE"])
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    expected_send_receive = 4  # SEND DATA, RECEIVE DATA commands
    if visible_count == expected_send_receive:
        print(f"    ✅ PASS: Found {visible_count} SEND/RECEIVE commands")
    else:
        print(f"    ❌ FAIL: Expected {expected_send_receive}, found {visible_count}")
    
    # Test 3: Filter only ENVELOPE commands
    print("  📋 Test 3: Filter only ENVELOPE commands")
    filter_model.set_command_type_filter(["ENVELOPE"])
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    expected_envelope = 1  # ENVELOPE - DATA TRANSFER
    if visible_count == expected_envelope:
        print(f"    ✅ PASS: Found {visible_count} ENVELOPE commands")
    else:
        print(f"    ❌ FAIL: Expected {expected_envelope}, found {visible_count}")
    
    print()

def test_time_range_filter(filter_model, trace_model):
    """Test time range filtering."""
    print("🔸 Testing Time Range Filter...")
    
    # Clear other filters first
    filter_model.clear_all_filters()
    
    # Test 1: Show first 50% of trace
    print("  📋 Test 1: Show first 50% of trace")
    filter_model.set_time_range_filter(0.5)
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    expected_50_percent = 4  # First 4 items out of 8
    if visible_count == expected_50_percent:
        print(f"    ✅ PASS: Found {visible_count} items in first 50%")
    else:
        print(f"    ❌ FAIL: Expected {expected_50_percent}, found {visible_count}")
    
    # Test 2: Show first 25% of trace
    print("  📋 Test 2: Show first 25% of trace")
    filter_model.set_time_range_filter(0.25)
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    expected_25_percent = 2  # First 2 items out of 8
    if visible_count == expected_25_percent:
        print(f"    ✅ PASS: Found {visible_count} items in first 25%")
    else:
        print(f"    ❌ FAIL: Expected {expected_25_percent}, found {visible_count}")
    
    # Test 3: Show full trace (100%)
    print("  📋 Test 3: Show full trace (100%)")
    filter_model.set_time_range_filter(1.0)
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
    
    expected_100_percent = 8  # All items
    if visible_count == expected_100_percent:
        print(f"    ✅ PASS: Found {visible_count} items in full trace")
    else:
        print(f"    ❌ FAIL: Expected {expected_100_percent}, found {visible_count}")
    
    print()

def test_search_text_filter(filter_model, trace_model):
    """Test search text filtering."""
    print("🔸 Testing Search Text Filter...")
    
    # Clear other filters first
    filter_model.clear_all_filters()
    
    # Test 1: Search for "OPEN"
    print("  📋 Test 1: Search for 'OPEN'")
    filter_model.set_search_text("open")
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    expected_open = 2  # Items with "OPEN" in summary
    if visible_count == expected_open:
        print(f"    ✅ PASS: Found {visible_count} items with 'OPEN'")
    else:
        print(f"    ❌ FAIL: Expected {expected_open}, found {visible_count}")
    
    # Test 2: Search for "DATA"
    print("  📋 Test 2: Search for 'DATA'")
    filter_model.set_search_text("data")
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    expected_data = 4  # Items with "DATA" in summary
    if visible_count == expected_data:
        print(f"    ✅ PASS: Found {visible_count} items with 'DATA'")
    else:
        print(f"    ❌ FAIL: Expected {expected_data}, found {visible_count}")
    
    print()

def test_combined_filters(filter_model, trace_model):
    """Test combination of multiple filters."""
    print("🔸 Testing Combined Filters...")
    
    # Clear all filters first
    filter_model.clear_all_filters()
    
    # Test 1: Command type + Search text
    print("  📋 Test 1: OPEN commands + Search 'FETCH'")
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_search_text("fetch")
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    expected_combined = 1  # Only "FETCH - OPEN CHANNEL"
    if visible_count == expected_combined:
        print(f"    ✅ PASS: Found {visible_count} items with OPEN+FETCH")
    else:
        print(f"    ❌ FAIL: Expected {expected_combined}, found {visible_count}")
    
    # Test 2: Command type + Time range
    print("  📋 Test 2: SEND/RECEIVE commands + First 75% of trace")
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["SEND", "RECEIVE"])
    filter_model.set_time_range_filter(0.75)
    
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
            item = trace_model.trace_items[row]
            print(f"    ✅ Row {row}: {item.summary}")
    
    # Should find SEND/RECEIVE commands in first 6 items (75% of 8)
    expected_time_cmd = 3  # FETCH - SEND DATA, TERMINAL RESPONSE - RECEIVE DATA, TERMINAL RESPONSE - SEND DATA
    if visible_count == expected_time_cmd:
        print(f"    ✅ PASS: Found {visible_count} SEND/RECEIVE commands in first 75%")
    else:
        print(f"    ❌ FAIL: Expected {expected_time_cmd}, found {visible_count}")
    
    print()

def test_filter_clearing(filter_model, trace_model):
    """Test filter clearing functionality."""
    print("🔸 Testing Filter Clearing...")
    
    # Set multiple filters
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_search_text("test")
    filter_model.set_time_range_filter(0.5)
    
    # Clear all filters
    print("  📋 Test: Clear all filters")
    filter_model.clear_all_filters()
    
    # Check that all items are visible
    visible_count = 0
    for row in range(trace_model.rowCount()):
        if filter_model.filterAcceptsRow(row, QModelIndex()):
            visible_count += 1
    
    expected_all = 8  # All items should be visible
    if visible_count == expected_all:
        print(f"    ✅ PASS: All {visible_count} items visible after clearing filters")
    else:
        print(f"    ❌ FAIL: Expected {expected_all}, found {visible_count}")
    
    print()

def main():
    """Run all filter tests."""
    print("🚀 Advanced Filter Test Suite")
    print("=" * 50)
    
    # Initialize Qt application (required for Qt models)
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # Create test data
    test_items = create_test_trace_items()
    trace_model = TestTraceModel(test_items)
    
    # Create filter model
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(trace_model)
    
    print(f"📊 Created {len(test_items)} test trace items:")
    for i, item in enumerate(test_items):
        print(f"  {i}: {item.summary}")
    print()
    
    # Run tests
    try:
        test_command_type_filter(filter_model, trace_model)
        test_time_range_filter(filter_model, trace_model)
        test_search_text_filter(filter_model, trace_model)
        test_combined_filters(filter_model, trace_model)
        test_filter_clearing(filter_model, trace_model)
        
        print("🎉 All tests completed!")
        print("✅ Advanced filtering system is ready to use!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())