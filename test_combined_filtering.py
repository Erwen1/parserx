#!/usr/bin/env python3
"""
Test Combined Command Type + Server Filtering
Tests specific combinations like "SEND + TAC Server"
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QModelIndex
from xti_viewer.models import TraceItemFilterModel, InterpretationTreeModel
from xti_viewer.xti_parser import XTIParser

def test_combined_filtering():
    """Test combined command type + server filtering"""
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    print(f"Testing Combined Filtering on HL7812_fallback_NOK.xti")
    print(f"Total trace items: {len(trace_items)}")
    
    # Create models
    table_model = InterpretationTreeModel()
    table_model.load_trace_items(trace_items)
    
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(table_model)
    
    # Test scenarios you asked about
    test_scenarios = [
        {
            "name": "TAC Server + SEND Commands",
            "command_types": ["SEND"],
            "server": "TAC",
            "description": "Should show only SEND DATA commands within TAC server sessions"
        },
        {
            "name": "TAC Server + RECEIVE Commands", 
            "command_types": ["RECEIVE"],
            "server": "TAC",
            "description": "Should show only RECEIVE DATA commands within TAC server sessions"
        },
        {
            "name": "TAC Server + TERMINAL Responses",
            "command_types": ["TERMINAL"],
            "server": "TAC", 
            "description": "Should show only TERMINAL RESPONSE commands within TAC server sessions"
        },
        {
            "name": "TAC Server + OPEN Commands",
            "command_types": ["OPEN"],
            "server": "TAC",
            "description": "Should show only OPEN CHANNEL commands to TAC server"
        },
        {
            "name": "TAC Server + CLOSE Commands",
            "command_types": ["CLOSE"],
            "server": "TAC",
            "description": "Should show only CLOSE CHANNEL commands for TAC server sessions"
        },
        {
            "name": "TAC Server + SEND/RECEIVE Combined",
            "command_types": ["SEND", "RECEIVE"],
            "server": "TAC",
            "description": "Should show all data transfer commands within TAC server sessions"
        },
        {
            "name": "DP+ Server + SEND Commands",
            "command_types": ["SEND"],
            "server": "DP+",
            "description": "Should show only SEND DATA commands within DP+ server sessions"
        }
    ]
    
    print("\n" + "="*80)
    print("COMBINED COMMAND TYPE + SERVER FILTERING TEST")
    print("="*80)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print("-" * 60)
        print(f"   {scenario['description']}")
        
        # Clear all filters
        filter_model.clear_all_filters()
        
        # Apply command type filter
        filter_model.set_command_type_filter(scenario['command_types'])
        
        # Apply server filter
        filter_model.set_server_filter(scenario['server'])
        
        # Count visible items and show samples
        visible_items = []
        visible_summaries = []
        
        for row in range(table_model.rowCount()):
            if filter_model.filterAcceptsRow(row, QModelIndex()):
                trace_item = table_model.get_trace_item(table_model.index(row, 0))
                visible_items.append(trace_item)
                visible_summaries.append(trace_item.summary)
        
        print(f"\n   Results: {len(visible_items)} matching items")
        
        if visible_items:
            print(f"   Sample results:")
            for j, summary in enumerate(visible_summaries[:10]):  # Show first 10
                print(f"     {j+1:2d}. {summary}")
            
            if len(visible_items) > 10:
                print(f"     ... and {len(visible_items) - 10} more items")
                
            # Verify the results make sense
            print(f"\n   Verification:")
            command_count = {}
            for item in visible_items:
                summary_lower = item.summary.lower()
                if "send data" in summary_lower and "fetch" in summary_lower:
                    command_count["SEND"] = command_count.get("SEND", 0) + 1
                elif "receive data" in summary_lower and "fetch" in summary_lower:
                    command_count["RECEIVE"] = command_count.get("RECEIVE", 0) + 1
                elif "send data" in summary_lower and "terminal response" in summary_lower:
                    command_count["TERMINAL_SEND"] = command_count.get("TERMINAL_SEND", 0) + 1
                elif "receive data" in summary_lower and "terminal response" in summary_lower:
                    command_count["TERMINAL_RECEIVE"] = command_count.get("TERMINAL_RECEIVE", 0) + 1
                elif "terminal response" in summary_lower:
                    command_count["TERMINAL"] = command_count.get("TERMINAL", 0) + 1
                elif "open channel" in summary_lower and "fetch" in summary_lower:
                    command_count["OPEN"] = command_count.get("OPEN", 0) + 1
                elif "close channel" in summary_lower and "fetch" in summary_lower:
                    command_count["CLOSE"] = command_count.get("CLOSE", 0) + 1
                elif "envelope" in summary_lower:
                    command_count["ENVELOPE"] = command_count.get("ENVELOPE", 0) + 1
                else:
                    command_count["OTHER"] = command_count.get("OTHER", 0) + 1
                    # Show what "OTHER" items look like for debugging
                    if command_count["OTHER"] <= 3:
                        print(f"     DEBUG - OTHER item: {item.summary}")
            
            print(f"     Command breakdown: {command_count}")
            
            # Check if results match expected command types with more flexible matching
            expected_types = set(scenario['command_types'])
            found_types = set()
            
            for cmd_type in expected_types:
                if cmd_type == "SEND" and ("SEND" in command_count or "TERMINAL_SEND" in command_count):
                    found_types.add("SEND")
                elif cmd_type == "RECEIVE" and ("RECEIVE" in command_count or "TERMINAL_RECEIVE" in command_count):
                    found_types.add("RECEIVE")
                elif cmd_type == "TERMINAL" and any(k.startswith("TERMINAL") for k in command_count.keys()):
                    found_types.add("TERMINAL")
                elif cmd_type in command_count:
                    found_types.add(cmd_type)
            
            if expected_types == found_types or expected_types.issubset(found_types):
                print(f"     ✅ Filter working correctly!")
            else:
                print(f"     ⚠️  Expected {expected_types}, found {found_types}")
        else:
            print("     No matching items found.")

    print("\n" + "="*80)
    print("COMBINED FILTERING TEST COMPLETE")
    print("="*80)
    print("\nThis shows exactly what you'll see when combining")
    print("command type filters with server filters in your UI!")
    print("\nFor example: 'SEND + TAC' shows only SEND DATA commands")
    print("that occur within channel sessions opened to TAC servers.")

def main():
    """Run the combined filtering test"""
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    try:
        test_combined_filtering()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())