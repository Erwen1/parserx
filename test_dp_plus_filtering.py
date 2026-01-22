#!/usr/bin/env python3
"""
Test filtering for DP+ server - OPEN CHANNEL commands only.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import QModelIndex

def test_dp_plus_filtering():
    """Test command type filtering (OPEN only) and server filtering (DP+ only)"""
    
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
    
    # Test 3: Clear command filter, apply server filter - DP+ only
    print("\n" + "="*60)
    print("TEST 3: Server filter - DP+ only")
    print("="*60)
    
    # Clear command filter first
    filter_model.clear_all_filters()
    
    # Apply DP+ server filter
    filter_model.set_server_filter("DP+")
    
    dp_plus_items = []
    for row in range(filter_model.rowCount()):
        index = filter_model.index(row, 0)
        summary = filter_model.data(index)
        dp_plus_items.append(summary)
    
    print(f"Items with DP+ server filter: {len(dp_plus_items)}")
    
    if len(dp_plus_items) > 0:
        for i, item in enumerate(dp_plus_items[:20]):  # Show first 20
            print(f"  {i+1:2d}. {item}")
        if len(dp_plus_items) > 20:
            print(f"  ... and {len(dp_plus_items) - 20} more")
    else:
        print("  ❌ No DP+ server items found")
    
    # Test 4: Combined filters - OPEN + DP+
    print("\n" + "="*60)
    print("TEST 4: Combined filters - OPEN + DP+")
    print("="*60)
    
    # Clear all filters first
    filter_model.clear_all_filters()
    
    # Apply both filters
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_server_filter("DP+")
    
    combined_items = []
    for row in range(filter_model.rowCount()):
        index = filter_model.index(row, 0)
        summary = filter_model.data(index)
        combined_items.append(summary)
    
    print(f"Items with OPEN + DP+ filters: {len(combined_items)}")
    
    if len(combined_items) > 0:
        for i, item in enumerate(combined_items):
            print(f"  {i+1:2d}. {item}")
        print("\n✅ SUCCESS: DP+ OPEN CHANNEL commands found!")
    else:
        print("  ❌ No DP+ OPEN CHANNEL commands found")
    
    # Test 5: Analyze what servers are available for OPEN CHANNEL commands
    print("\n" + "="*60)
    print("TEST 5: OPEN CHANNEL Server Analysis")
    print("="*60)
    
    from xti_viewer.xti_parser import extract_ips_from_interpretation_tree, tag_server_from_ips
    
    open_channel_servers = {}
    
    for item in parser.trace_items:
        summary_lower = item.summary.lower()
        if "fetch" in summary_lower and "open channel" in summary_lower:
            # Extract IPs from this item's details tree
            ips = extract_ips_from_interpretation_tree(item.details_tree)
            server_label = tag_server_from_ips(ips)
            
            if server_label not in open_channel_servers:
                open_channel_servers[server_label] = 0
            open_channel_servers[server_label] += 1
    
    print("OPEN CHANNEL commands by server:")
    for server, count in sorted(open_channel_servers.items()):
        print(f"  {server}: {count} commands")
    
    print("\nFilter test completed!")

if __name__ == "__main__":
    test_dp_plus_filtering()