#!/usr/bin/env python3
"""
Simple test runner without Unicode characters.
Tests all advanced filtering features.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import our modules
from xti_viewer.models import TraceItemFilterModel
from xti_viewer.xti_parser import TraceItem, TreeNode
from PySide6.QtCore import QModelIndex, Qt, QAbstractItemModel
from PySide6.QtWidgets import QApplication

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

def create_test_data():
    """Create test trace items."""
    return [
        TraceItem(
            protocol="TCP", type="COMMAND", summary="FETCH - OPEN CHANNEL",
            rawhex="1234", timestamp="01/01/2024 10:00:00:000",
            details_tree=TreeNode("FETCH - OPEN CHANNEL"),
            timestamp_sort_key="2024-01-01T10:00:00.000"
        ),
        TraceItem(
            protocol="TCP", type="RESPONSE", summary="TERMINAL RESPONSE - OPEN CHANNEL",
            rawhex="5678", timestamp="01/01/2024 10:00:01:000",
            details_tree=TreeNode("TERMINAL RESPONSE - OPEN CHANNEL"),
            timestamp_sort_key="2024-01-01T10:00:01.000"
        ),
        TraceItem(
            protocol="TCP", type="COMMAND", summary="FETCH - SEND DATA",
            rawhex="ABCD", timestamp="01/01/2024 10:00:02:000",
            details_tree=TreeNode("FETCH - SEND DATA"),
            timestamp_sort_key="2024-01-01T10:00:02.000"
        ),
        TraceItem(
            protocol="ENVELOPE", type="COMMAND", summary="ENVELOPE - DATA TRANSFER",
            rawhex="MNOP", timestamp="01/01/2024 10:00:05:000",
            details_tree=TreeNode("ENVELOPE - DATA TRANSFER"),
            timestamp_sort_key="2024-01-01T10:00:05.000"
        ),
    ]

def test_command_filters():
    """Test command type filtering."""
    print("Testing Command Type Filters...")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    test_items = create_test_data()
    trace_model = TestTraceModel(test_items)
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(trace_model)
    
    # Test OPEN filter
    filter_model.set_command_type_filter(["OPEN"])
    open_count = sum(1 for row in range(trace_model.rowCount()) 
                    if filter_model.filterAcceptsRow(row, QModelIndex()))
    
    # Test ENVELOPE filter
    filter_model.set_command_type_filter(["ENVELOPE"])
    envelope_count = sum(1 for row in range(trace_model.rowCount()) 
                        if filter_model.filterAcceptsRow(row, QModelIndex()))
    
    print(f"  OPEN filter: {open_count} items found")
    print(f"  ENVELOPE filter: {envelope_count} items found")
    
    return open_count == 2 and envelope_count == 1

def test_time_filter():
    """Test time range filtering."""
    print("Testing Time Range Filter...")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    test_items = create_test_data()
    trace_model = TestTraceModel(test_items)
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(trace_model)
    
    # Test 50% time range
    filter_model.clear_all_filters()
    filter_model.set_time_range_filter(0.5)
    half_count = sum(1 for row in range(trace_model.rowCount()) 
                    if filter_model.filterAcceptsRow(row, QModelIndex()))
    
    # Test 100% time range
    filter_model.set_time_range_filter(1.0)
    full_count = sum(1 for row in range(trace_model.rowCount()) 
                    if filter_model.filterAcceptsRow(row, QModelIndex()))
    
    print(f"  50% time range: {half_count} items found")
    print(f"  100% time range: {full_count} items found")
    
    return half_count < full_count and full_count == 4

def test_search_filter():
    """Test search text filtering."""
    print("Testing Search Text Filter...")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    test_items = create_test_data()
    trace_model = TestTraceModel(test_items)
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(trace_model)
    
    # Test search for "OPEN"
    filter_model.clear_all_filters()
    filter_model.set_search_text("open")
    open_search = sum(1 for row in range(trace_model.rowCount()) 
                     if filter_model.filterAcceptsRow(row, QModelIndex()))
    
    # Test search for "ENVELOPE"
    filter_model.set_search_text("envelope")
    envelope_search = sum(1 for row in range(trace_model.rowCount()) 
                         if filter_model.filterAcceptsRow(row, QModelIndex()))
    
    print(f"  Search 'open': {open_search} items found")
    print(f"  Search 'envelope': {envelope_search} items found")
    
    return open_search == 2 and envelope_search == 1

def main():
    """Run all tests."""
    print("Advanced Filter Test Suite")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 3
    
    try:
        if test_command_filters():
            print("  PASS: Command type filters")
            tests_passed += 1
        else:
            print("  FAIL: Command type filters")
        
        if test_time_filter():
            print("  PASS: Time range filter")
            tests_passed += 1
        else:
            print("  FAIL: Time range filter")
        
        if test_search_filter():
            print("  PASS: Search text filter")
            tests_passed += 1
        else:
            print("  FAIL: Search text filter")
        
        print()
        print(f"Results: {tests_passed}/{total_tests} tests passed")
        
        if tests_passed == total_tests:
            print("SUCCESS: All advanced filters working!")
            return 0
        else:
            print("FAILURE: Some tests failed")
            return 1
    
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())