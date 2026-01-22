#!/usr/bin/env python3
"""
Step-by-step debug of filterAcceptsRow method for specific items.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import QModelIndex, Qt

def debug_filter_accepts_row():
    """Debug the filterAcceptsRow method step by step"""
    
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
    print("STEP-BY-STEP DEBUG: filterAcceptsRow for TAC OPEN CHANNEL items")
    print("="*70)
    
    # Set up combined filters
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_server_filter("TAC")
    
    # Debug the known TAC OPEN CHANNEL items
    tac_open_items = [63, 580]  # These are trace item indices
    
    for trace_item_idx in tac_open_items:
        trace_item = parser.trace_items[trace_item_idx]
        print(f"\n{'='*50}")
        print(f"DEBUGGING TRACE ITEM [{trace_item_idx}]: {trace_item.summary}")
        print(f"{'='*50}")
        
        # Find the model row for this trace item
        model_row = None
        for row in range(model.rowCount()):
            model_index = model.index(row, 0)
            row_trace_item = model.data(model_index, Qt.UserRole)
            if row_trace_item == trace_item:
                model_row = row
                break
        
        if model_row is None:
            print("❌ Could not find model row for this trace item!")
            continue
            
        print(f"🔍 Model row: {model_row}")
        
        # Step 1: Get summary
        model_index = model.index(model_row, 0)
        summary = model.data(model_index, Qt.DisplayRole)
        print(f"📋 Summary: {summary}")
        
        # Step 2: Check command type filter
        summary_lower = summary.lower()
        command_match = False
        for cmd_type in filter_model.command_type_filter:
            if cmd_type == "OPEN":
                # Match FETCH commands that open channels, not terminal responses
                if "fetch" in summary_lower and "open channel" in summary_lower:
                    command_match = True
                    break
        
        print(f"🔧 Command type filter pass: {command_match}")
        if not command_match:
            print("❌ FAILED: Command type filter")
            continue
        
        # Step 3: Check server filter
        print(f"🌐 Server filter: {filter_model.server_filter}")
        
        # Analyze sessions if needed
        filter_model.analyze_channel_sessions()
        
        item_in_target_server_session = False
        
        # Check session membership using corrected logic
        for session_id, server_label in filter_model.active_sessions.items():
            print(f"    Checking session {session_id}: {server_label}")
            session_item_indices = filter_model.session_items.get(session_id, [])
            print(f"    Session items: {len(session_item_indices)} items")
            
            # Get the TraceItem for this model row
            model_index = model.index(model_row, 0)
            row_trace_item = model.data(model_index, Qt.UserRole)
            
            if row_trace_item:
                try:
                    # Find the index of this trace item in the original trace_items list
                    found_trace_item_index = model.trace_items.index(row_trace_item)
                    print(f"    Row trace item index: {found_trace_item_index}")
                    
                    if found_trace_item_index in session_item_indices:
                        print(f"    ✅ Found in session {session_id}")
                        if server_label == "TAC":
                            item_in_target_server_session = True
                            print(f"    ✅ Server matches TAC filter")
                            break
                        else:
                            print(f"    ❌ Server {server_label} doesn't match TAC filter")
                    else:
                        print(f"    ❌ Not found in this session")
                        
                except ValueError:
                    print(f"    ❌ TraceItem not found in model.trace_items list")
                    continue
        
        print(f"🏢 Server filter pass: {item_in_target_server_session}")
        
        # Step 4: Call actual filterAcceptsRow
        accepts = filter_model.filterAcceptsRow(model_row, QModelIndex())
        print(f"🎯 Final result: {accepts}")
        
        if not accepts:
            print("❌ FAILED: Combined filter rejects this item")
        else:
            print("✅ SUCCESS: Combined filter accepts this item")

if __name__ == "__main__":
    debug_filter_accepts_row()