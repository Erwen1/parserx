#!/usr/bin/env python3
"""
Debug the combined filtering issue - why OPEN + TAC returns 0 items.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import QModelIndex

def debug_combined_filtering():
    """Debug why OPEN + TAC combined filter returns 0 items"""
    
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
    
    print("\n" + "="*70)
    print("DEBUG: Combined Filtering Issue Analysis")
    print("="*70)
    
    # Step 1: Analyze session detection for TAC items
    print("\n1. Session Analysis:")
    filter_model.analyze_channel_sessions()
    
    print(f"Active sessions: {len(filter_model.active_sessions)}")
    for session_id, server in filter_model.active_sessions.items():
        items = filter_model.session_items.get(session_id, [])
        print(f"  {session_id}: {server} - {len(items)} items")
        
        # Check for OPEN CHANNEL commands in TAC sessions
        if server == "TAC":
            print(f"    TAC Session items (indices): {items}")
            open_commands = []
            for item_idx in items:
                if item_idx < len(parser.trace_items):
                    item = parser.trace_items[item_idx]
                    if "fetch" in item.summary.lower() and "open channel" in item.summary.lower():
                        open_commands.append((item_idx, item.summary))
            print(f"    OPEN CHANNEL commands in this TAC session: {open_commands}")
    
    # Step 2: Test individual filters
    print("\n2. Testing Individual Filters:")
    
    # Test OPEN filter only
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["OPEN"])
    open_count = filter_model.rowCount()
    print(f"OPEN filter only: {open_count} items")
    
    # Get some examples
    open_examples = []
    for row in range(min(5, open_count)):
        index = filter_model.index(row, 0)
        summary = filter_model.data(index)
        # Get source row index
        source_index = filter_model.mapToSource(index)
        source_row = source_index.row()
        open_examples.append((source_row, summary))
    
    print("OPEN examples (source_row, summary):")
    for src_row, summary in open_examples:
        print(f"  [{src_row}] {summary}")
    
    # Test TAC filter only
    filter_model.clear_all_filters()
    filter_model.set_server_filter("TAC")
    tac_count = filter_model.rowCount()
    print(f"\nTAC filter only: {tac_count} items")
    
    # Step 3: Test combined filter with debug
    print("\n3. Testing Combined Filter with Debug:")
    filter_model.clear_all_filters()
    
    # Apply both filters
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_server_filter("TAC")
    
    combined_count = filter_model.rowCount()
    print(f"OPEN + TAC combined: {combined_count} items")
    
    # If combined count is 0, let's debug why
    if combined_count == 0:
        print("\n4. Debugging why combined filter fails:")
        
        # Check if our known TAC OPEN CHANNEL items pass the filter
        known_tac_open_indices = [63, 580]  # From previous analysis
        
        for idx in known_tac_open_indices:
            item = parser.trace_items[idx]
            print(f"\nChecking item [{idx}]: {item.summary}")
            
            # Test command type filter
            summary_lower = item.summary.lower()
            command_match = "fetch" in summary_lower and "open channel" in summary_lower
            print(f"  Command type match: {command_match}")
            
            # Test server filter manually
            from xti_viewer.xti_parser import extract_ips_from_interpretation_tree, tag_server_from_ips
            ips = extract_ips_from_interpretation_tree(item.details_tree)
            server_label = tag_server_from_ips(ips)
            print(f"  Server label: {server_label}")
            print(f"  Server filter match: {server_label == 'TAC'}")
            
            # Check session membership
            in_tac_session = False
            for session_id, session_server in filter_model.active_sessions.items():
                if session_server == "TAC":
                    session_items = filter_model.session_items.get(session_id, [])
                    if idx in session_items:
                        in_tac_session = True
                        print(f"  Found in TAC session {session_id}")
                        break
            
            if not in_tac_session:
                print(f"  WARNING: Item not found in any TAC session!")
            
            # Test the actual filter method
            # We need to find the model row for this trace item index
            model_row = None
            for row in range(model.rowCount()):
                model_index = model.index(row, 0)
                trace_item = model.data(model_index, role=0x100)  # Qt.UserRole
                if trace_item == item:
                    model_row = row
                    break
            
            if model_row is not None:
                print(f"  Model row: {model_row}")
                accepts = filter_model.filterAcceptsRow(model_row, QModelIndex())
                print(f"  Filter accepts: {accepts}")

if __name__ == "__main__":
    debug_combined_filtering()