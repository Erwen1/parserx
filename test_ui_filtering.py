"""
Test what the UI actually shows for server filters and channel groups.
This simulates the exact filtering logic used in the UI.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import Qt

def test_ui_filtering():
    """Test actual UI filtering behavior."""
    
    xti_file = r"C:\Users\T0319884\Documents\coding\python\parserx\HL7812_fallback_NOK.xti"
    
    print("🔍 Testing UI Filtering Behavior")
    print("=" * 80)
    
    # Parse the file
    parser = XTIParser()
    parser.parse_file(xti_file)
    
    print(f"✓ Loaded {len(parser.trace_items)} trace items")
    print(f"✓ Found {len(parser.channel_sessions)} channel sessions")
    print()
    
    # Create the models (simulating UI)
    tree_model = InterpretationTreeModel()
    tree_model.parser = parser  # Store parser for session analysis
    tree_model.load_trace_items(parser.trace_items)
    
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(tree_model)
    
    print(f"✓ Created tree model with {tree_model.rowCount()} rows (combined entries)")
    print()
    
    # Test 1: Server filter - TAC
    print("\n" + "="*80)
    print("TEST 1: Advanced Filter - Server = TAC")
    print("="*80)
    
    filter_model.clear_all_filters()
    filter_model.set_server_filter("TAC")
    
    tac_count = filter_model.rowCount()
    print(f"Filtered row count: {tac_count}")
    
    # Show first 10 items
    print("\nFirst 10 items shown:")
    for row in range(min(10, tac_count)):
        index = filter_model.index(row, 0)
        source_index = filter_model.mapToSource(index)
        summary = tree_model.data(source_index, Qt.DisplayRole)
        print(f"  [{row:3d}] {summary}")
    
    # Test 2: Server filter - DNS by ME
    print("\n" + "="*80)
    print("TEST 2: Advanced Filter - Server = DNS by ME")
    print("="*80)
    
    filter_model.clear_all_filters()
    filter_model.set_server_filter("DNS by ME")
    
    me_count = filter_model.rowCount()
    print(f"Filtered row count: {me_count}")
    
    # Show first 10 items
    print("\nFirst 10 items shown:")
    for row in range(min(10, me_count)):
        index = filter_model.index(row, 0)
        source_index = filter_model.mapToSource(index)
        summary = tree_model.data(source_index, Qt.DisplayRole)
        print(f"  [{row:3d}] {summary}")
    
    # Test 3: Server filter - Public DNS
    print("\n" + "="*80)
    print("TEST 3: Advanced Filter - Server = Public DNS")
    print("="*80)
    
    filter_model.clear_all_filters()
    filter_model.set_server_filter("Public DNS")
    
    dns_count = filter_model.rowCount()
    print(f"Filtered row count: {dns_count}")
    
    # Show first 10 items
    print("\nFirst 10 items shown:")
    for row in range(min(10, dns_count)):
        index = filter_model.index(row, 0)
        source_index = filter_model.mapToSource(index)
        summary = tree_model.data(source_index, Qt.DisplayRole)
        print(f"  [{row:3d}] {summary}")
    
    # Test 4: Channel Groups
    print("\n" + "="*80)
    print("TEST 4: Channel Groups Click Behavior")
    print("="*80)
    
    groups = parser.get_channel_groups()
    print(f"Total channel groups: {len(groups)}")
    print()
    
    # Test clicking on each type of group
    for group in groups[:5]:  # First 5 groups
        server_name = group.get('server', 'Unknown')
        print(f"\n--- Clicking on Group: {server_name} ({group.get('type', '')}) ---")
        
        # Simulate clicking on channel group (uses server filter)
        filter_model.clear_all_filters()
        filter_model.set_server_filter(server_name)
        
        group_count = filter_model.rowCount()
        print(f"Items shown: {group_count}")
        
        # Show first 5 items
        print("First 5 items:")
        for row in range(min(5, group_count)):
            index = filter_model.index(row, 0)
            source_index = filter_model.mapToSource(index)
            summary = tree_model.data(source_index, Qt.DisplayRole)
            print(f"  [{row:3d}] {summary}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total items in file: {len(parser.trace_items)}")
    print(f"Total model rows (combined): {tree_model.rowCount()}")
    print(f"TAC filter shows: {tac_count} rows")
    print(f"DNS by ME filter shows: {me_count} rows")
    print(f"Public DNS filter shows: {dns_count} rows")
    print()
    
    # Check if filters are working
    if tac_count == tree_model.rowCount() and me_count == tree_model.rowCount():
        print("⚠️  WARNING: All filters showing same count - filters NOT working!")
    else:
        print("✅ Filters are working - different counts for different servers")

if __name__ == "__main__":
    # Suppress Qt warnings
    import os
    os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'
    
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    test_ui_filtering()
