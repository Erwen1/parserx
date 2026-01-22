#!/usr/bin/env python3
"""
Complete XTI File Analysis and Filtering Test
Shows what's actually in your XTI file and tests all filtering combinations
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QModelIndex
from xti_viewer.models import TraceItemFilterModel, InterpretationTreeModel
from xti_viewer.xti_parser import XTIParser, extract_ips_from_interpretation_tree, tag_server_from_ips
from pathlib import Path
from collections import Counter

def find_xti_file():
    """Find an XTI file in the current directory"""
    # Priority order: first try the specific file, then any .xti file
    priority_files = ["HL7812_fallback_NOK.xti", "BC660K_enable_OK.xti"]
    
    for file_name in priority_files:
        if Path(file_name).exists():
            return file_name
    
    # Fallback to any .xti file
    current_dir = Path('.')
    xti_files = list(current_dir.glob('*.xti'))
    if xti_files:
        return str(xti_files[0])
    return None

def analyze_xti_content():
    """Analyze the actual content of the XTI file"""
    
    # Find and load XTI file
    xti_file = find_xti_file()
    if not xti_file:
        print("No XTI file found in current directory. Please place an .xti file here.")
        return
    
    print(f"Analyzing XTI file: {xti_file}")
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file(xti_file)
    
    if not trace_items:
        print("No trace items found in the XTI file.")
        return
    
    print(f"Total trace items: {len(trace_items)}")
    
    # Analyze content
    command_types = Counter()
    servers = Counter()
    protocols = Counter()
    summary_samples = []
    
    for item in trace_items:
        # Count protocols
        protocols[item.protocol or "Unknown"] += 1
        
        # Extract server info
        try:
            ips = extract_ips_from_interpretation_tree(item.details_tree)
            server_label = tag_server_from_ips(ips)
            servers[server_label] += 1
        except:
            servers["Unknown"] += 1
        
        # Classify command types
        summary_lower = item.summary.lower()
        if "terminal response" in summary_lower:
            command_types["TERMINAL"] += 1
        elif "fetch" in summary_lower:
            if "open channel" in summary_lower:
                command_types["OPEN"] += 1
            elif "close channel" in summary_lower:
                command_types["CLOSE"] += 1
            elif "send data" in summary_lower:
                command_types["SEND"] += 1
            elif "receive data" in summary_lower:
                command_types["RECEIVE"] += 1
            else:
                command_types["OTHER_FETCH"] += 1
        elif "envelope" in summary_lower:
            command_types["ENVELOPE"] += 1
        else:
            command_types["OTHER"] += 1
        
        # Collect summary samples
        if len(summary_samples) < 20:
            summary_samples.append(item.summary)
    
    print("\n" + "="*80)
    print("XTI FILE CONTENT ANALYSIS")
    print("="*80)
    
    print(f"\nPROTOCOLS FOUND:")
    for protocol, count in protocols.most_common():
        print(f"  {protocol}: {count}")
    
    print(f"\nSERVERS FOUND:")
    for server, count in servers.most_common():
        print(f"  {server}: {count}")
    
    print(f"\nCOMMAND TYPES FOUND:")
    for cmd_type, count in command_types.most_common():
        print(f"  {cmd_type}: {count}")
    
    print(f"\nSAMPLE SUMMARIES (first 20):")
    for i, summary in enumerate(summary_samples, 1):
        print(f"  {i:2d}. {summary}")
    
    return trace_items, command_types, servers

def test_practical_filtering_scenarios(trace_items, command_types, servers):
    """Test filtering scenarios based on what's actually in the file"""
    
    # Create models
    table_model = InterpretationTreeModel()
    table_model.load_trace_items(trace_items)
    
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(table_model)
    
    # Create test scenarios based on actual content
    scenarios = []
    
    # Test each command type individually
    for cmd_type in command_types.keys():
        scenarios.append({
            "name": f"Only {cmd_type} Commands",
            "command_types": [cmd_type] if cmd_type in ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"] else [],
            "server": ""
        })
    
    # Test each server individually  
    for server in servers.keys():
        if server != "Unknown":
            scenarios.append({
                "name": f"All Commands to {server} Server",
                "command_types": ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"],
                "server": server
            })
    
    # Test practical combinations
    if "ME" in servers:
        scenarios.extend([
            {
                "name": "OPEN Commands to ME Server",
                "command_types": ["OPEN"],
                "server": "ME"
            },
            {
                "name": "TERMINAL Responses from ME Server", 
                "command_types": ["TERMINAL"],
                "server": "ME"
            }
        ])
    
    if "TAC" in servers:
        scenarios.extend([
            {
                "name": "OPEN Commands to TAC Server",
                "command_types": ["OPEN"],
                "server": "TAC"
            },
            {
                "name": "All Commands to TAC Server",
                "command_types": ["OPEN", "SEND", "RECEIVE", "CLOSE", "ENVELOPE", "TERMINAL"],
                "server": "TAC"
            }
        ])
    
    print("\n" + "="*80)
    print("PRACTICAL FILTERING SCENARIOS")
    print("="*80)
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print("-" * 60)
        
        # Clear all filters
        filter_model.clear_all_filters()
        
        # Apply command type filter
        if scenario['command_types']:
            filter_model.set_command_type_filter(scenario['command_types'])
        
        # Apply server filter
        if scenario['server']:
            filter_model.set_server_filter(scenario['server'])
        
        # Count visible items
        visible_count = 0
        sample_items = []
        
        for row in range(table_model.rowCount()):
            if filter_model.filterAcceptsRow(row, QModelIndex()):
                visible_count += 1
                if len(sample_items) < 3:
                    trace_item = table_model.get_trace_item(table_model.index(row, 0))
                    sample_items.append(trace_item.summary)
        
        print(f"   Matching items: {visible_count}")
        
        if sample_items:
            print(f"   Sample results:")
            for j, summary in enumerate(sample_items, 1):
                print(f"     {j}. {summary}")
            if visible_count > len(sample_items):
                print(f"     ... and {visible_count - len(sample_items)} more")
        else:
            print("   No matching items found.")

def main():
    """Run the complete analysis"""
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    try:
        # First analyze what's in the file
        result = analyze_xti_content()
        if result:
            trace_items, command_types, servers = result
            
            # Then test practical filtering scenarios
            test_practical_filtering_scenarios(trace_items, command_types, servers)
            
            print("\n" + "="*80)
            print("ANALYSIS COMPLETE")
            print("="*80)
            print("\nThis shows:")
            print("1. What content is actually in your XTI file")
            print("2. What you'll see when using different filter combinations")
            print("3. Practical filtering scenarios for your specific data")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())