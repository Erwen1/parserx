#!/usr/bin/env python3
"""
Test filtering functionality on the current XTI file.
Tests command type filtering (OPEN CHANNEL only) and server filtering (TAC only).
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import QModelIndex

def test_filtering_on_current_file():
    """Test filtering functionality on HL7812_fallback_NOK.xti"""
    
    # Load and parse the XTI file
    print("Loading HL7812_fallback_NOK.xti...")
    parser = XTIParser()
    
    try:
        parser.parse_file("HL7812_fallback_NOK.xti")
        print(f"✅ Successfully loaded {len(parser.trace_items)} trace items")
    except Exception as e:
        print(f"❌ Failed to load XTI file: {e}")
        return
    
    # Create models
    model = InterpretationTreeModel()
    model.load_trace_items(parser.trace_items)
    
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(model)
    
    print(f"📊 Total items in model: {model.rowCount()}")
    
    # Test 1: Show all items first
    print("\n" + "="*60)
    print("TEST 1: All items (no filters)")
    print("="*60)
    
    all_items = []
    for row in range(filter_model.rowCount()):
        index = filter_model.index(row, 0)
        summary = filter_model.data(index)
        all_items.append(summary)
    
    print(f"Total visible items (no filter): {len(all_items)}")
    
    # Show some sample items
    print("\nSample items:")
    for i, item in enumerate(all_items[:10]):
        print(f"  {i+1:2d}. {item}")
    if len(all_items) > 10:
        print(f"  ... and {len(all_items) - 10} more")
    
    # Test 2: Filter by command type - OPEN CHANNEL only
    print("\n" + "="*60)
    print("TEST 2: Command type filter - OPEN only")
    print("="*60)
    
    filter_model.set_command_type_filter(["OPEN"])
    
    open_items = []
    for row in range(filter_model.rowCount()):
        index = filter_model.index(row, 0)
        summary = filter_model.data(index)
        open_items.append(summary)
    
    print(f"Items with OPEN filter: {len(open_items)}")
    
    for i, item in enumerate(open_items):
        print(f"  {i+1:2d}. {item}")
    
    # Test 3: Clear command filter, apply server filter - TAC only
    print("\n" + "="*60)
    print("TEST 3: Server filter - TAC only")
    print("="*60)
    
    # Clear command filter first
    filter_model.clear_all_filters()
    
    # Apply TAC server filter
    filter_model.set_server_filter("TAC")
    
    tac_items = []
    for row in range(filter_model.rowCount()):
        index = filter_model.index(row, 0)
        summary = filter_model.data(index)
        tac_items.append(summary)
    
    print(f"Items with TAC server filter: {len(tac_items)}")
    
    for i, item in enumerate(tac_items[:20]):  # Show first 20
        print(f"  {i+1:2d}. {item}")
    if len(tac_items) > 20:
        print(f"  ... and {len(tac_items) - 20} more")
    
    # Test 4: Combined filters - OPEN + TAC
    print("\n" + "="*60)
    print("TEST 4: Combined filters - OPEN + TAC")
    print("="*60)
    
    # Clear all filters first
    filter_model.clear_all_filters()
    
    # Apply both filters
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_server_filter("TAC")
    
    combined_items = []
    for row in range(filter_model.rowCount()):
        index = filter_model.index(row, 0)
        summary = filter_model.data(index)
        combined_items.append(summary)
    
    print(f"Items with OPEN + TAC filters: {len(combined_items)}")
    
    for i, item in enumerate(combined_items):
        print(f"  {i+1:2d}. {item}")
    
    # Test 5: Analyze what servers are available
    print("\n" + "="*60)
    print("TEST 5: Server analysis")
    print("="*60)
    
    # Clear all filters to analyze servers
    filter_model.clear_all_filters()
    filter_model.analyze_channel_sessions()
    
    print("Detected servers:")
    unique_servers = set(filter_model.active_sessions.values())
    for server in sorted(unique_servers):
        print(f"  - {server}")
    
    print(f"\nTotal sessions detected: {len(filter_model.active_sessions)}")
    
    # Test 6: Check for OPEN CHANNEL items specifically
    print("\n" + "="*60)
    print("TEST 6: OPEN CHANNEL detection analysis")
    print("="*60)
    
    open_channel_items = []
    fetch_open_items = []
    
    for item in parser.trace_items:
        summary_lower = item.summary.lower()
        if "open channel" in summary_lower:
            open_channel_items.append(item.summary)
            if "fetch" in summary_lower:
                fetch_open_items.append(item.summary)
    
    print(f"Total items containing 'open channel': {len(open_channel_items)}")
    print(f"FETCH items with 'open channel': {len(fetch_open_items)}")
    
    print("\nFETCH OPEN CHANNEL items:")
    for i, item in enumerate(fetch_open_items):
        print(f"  {i+1:2d}. {item}")
    
    print("\nFilter test completed!")

if __name__ == "__main__":
    test_filtering_on_current_file()