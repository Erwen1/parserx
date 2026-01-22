#!/usr/bin/env python3
"""
Real XTI File Advanced Filtering Test
Tests filtering combinations on actual XTI trace data
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QModelIndex
from xti_viewer.models import TraceItemFilterModel, InterpretationTreeModel
from xti_viewer.xti_parser import XTIParser
from pathlib import Path

def find_xti_file():
    """Find an XTI file in the current directory"""
    current_dir = Path('.')
    xti_files = list(current_dir.glob('*.xti'))
    if xti_files:
        return str(xti_files[0])
    return None

def test_filtering_combinations():
    """Test various filtering combinations on real XTI data"""
    
    # Find and load XTI file
    xti_file = find_xti_file()
    if not xti_file:
        print("No XTI file found in current directory. Please place an .xti file here.")
        return
    
    print(f"Loading XTI file: {xti_file}")
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file(xti_file)
    
    if not trace_items:
        print("No trace items found in the XTI file.")
        return
    
    print(f"Loaded {len(trace_items)} trace items")
    
    # Create table model and filter model
    table_model = InterpretationTreeModel()
    table_model.load_trace_items(trace_items)
    
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(table_model)
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "All Command Types + TAC Server",
            "command_types": ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"],
            "server": "TAC"
        },
        {
            "name": "Only OPEN Commands + TAC Server",
            "command_types": ["OPEN"],
            "server": "TAC"
        },
        {
            "name": "Only TERMINAL Response + TAC Server",
            "command_types": ["TERMINAL"],
            "server": "TAC"
        },
        {
            "name": "Only SEND/RECEIVE + TAC Server",
            "command_types": ["SEND", "RECEIVE"],
            "server": "TAC"
        },
        {
            "name": "All Command Types + DP+ Server",
            "command_types": ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"],
            "server": "DP+"
        },
        {
            "name": "Only OPEN Commands + DP+ Server",
            "command_types": ["OPEN"],
            "server": "DP+"
        },
        {
            "name": "Only TERMINAL Response + DP+ Server",
            "command_types": ["TERMINAL"],
            "server": "DP+"
        },
        {
            "name": "Only SEND/RECEIVE + DP+ Server",
            "command_types": ["SEND", "RECEIVE"],
            "server": "DP+"
        },
        {
            "name": "All Command Types + Public DNS",
            "command_types": ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"],
            "server": "Public DNS"
        },
        {
            "name": "Only ENVELOPE + Public DNS",
            "command_types": ["ENVELOPE"],
            "server": "Public DNS"
        }
    ]
    
    print("\n" + "="*80)
    print("ADVANCED FILTERING TEST RESULTS ON REAL XTI DATA")
    print("="*80)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print("-" * 60)
        
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
        
        print(f"   Total matching items: {len(visible_items)}")
        
        if visible_items:
            print(f"   First 5 examples:")
            for j, summary in enumerate(visible_summaries[:5]):
                print(f"   {j+1:2d}. {summary}")
            
            if len(visible_items) > 5:
                print(f"   ... and {len(visible_items) - 5} more items")
                
            # Show command type breakdown
            command_breakdown = {}
            server_info = {}
            
            for item in visible_items:
                # Determine command type from summary
                summary_lower = item.summary.lower()
                if "terminal response" in summary_lower:
                    cmd_type = "TERMINAL"
                elif "fetch" in summary_lower:
                    if "open channel" in summary_lower:
                        cmd_type = "OPEN"
                    elif "close channel" in summary_lower:
                        cmd_type = "CLOSE"
                    elif "send data" in summary_lower:
                        cmd_type = "SEND"
                    elif "receive data" in summary_lower:
                        cmd_type = "RECEIVE"
                    else:
                        cmd_type = "OTHER_FETCH"
                elif "envelope" in summary_lower:
                    cmd_type = "ENVELOPE"
                else:
                    cmd_type = "OTHER"
                
                command_breakdown[cmd_type] = command_breakdown.get(cmd_type, 0) + 1
                
                # Extract server info
                try:
                    from xti_viewer.xti_parser import extract_ips_from_interpretation_tree, tag_server_from_ips
                    ips = extract_ips_from_interpretation_tree(item.details_tree)
                    server_label = tag_server_from_ips(ips)
                    server_info[server_label] = server_info.get(server_label, 0) + 1
                except:
                    server_info["Unknown"] = server_info.get("Unknown", 0) + 1
            
            print(f"   \n   Command Type Breakdown:")
            for cmd_type, count in sorted(command_breakdown.items()):
                print(f"     {cmd_type}: {count}")
                
            print(f"   \n   Server Breakdown:")
            for server, count in sorted(server_info.items()):
                print(f"     {server}: {count}")
        else:
            print("   No matching items found.")
    
    print("\n" + "="*80)
    print("FILTERING TEST COMPLETE")
    print("="*80)
    print("\nThis shows exactly what your advanced filters will display")
    print("when you select different command types and servers in the UI!")

def main():
    """Run the real filtering test"""
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    try:
        test_filtering_combinations()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())