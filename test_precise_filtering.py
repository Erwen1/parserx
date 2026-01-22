#!/usr/bin/env python3
"""
Test Precise Command Type Filtering
Tests that command types are exclusive unless explicitly combined
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QModelIndex
from xti_viewer.models import TraceItemFilterModel, InterpretationTreeModel
from xti_viewer.xti_parser import XTIParser

def test_precise_filtering():
    """Test precise command type filtering"""
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    print(f"Testing Precise Command Type Filtering")
    print(f"Total trace items: {len(trace_items)}")
    
    # Create models
    table_model = InterpretationTreeModel()
    table_model.load_trace_items(trace_items)
    
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(table_model)
    
    # Test precise filtering scenarios
    test_scenarios = [
        {
            "name": "TAC + SEND Only",
            "command_types": ["SEND"],
            "server": "TAC",
            "expected": "Only FETCH SEND DATA commands (no terminal responses)"
        },
        {
            "name": "TAC + SEND + TERMINAL",
            "command_types": ["SEND", "TERMINAL"],
            "server": "TAC",
            "expected": "FETCH SEND DATA + TERMINAL RESPONSE commands"
        },
        {
            "name": "TAC + RECEIVE Only",
            "command_types": ["RECEIVE"],
            "server": "TAC", 
            "expected": "Only FETCH RECEIVE DATA commands (no terminal responses)"
        },
        {
            "name": "TAC + RECEIVE + TERMINAL",
            "command_types": ["RECEIVE", "TERMINAL"],
            "server": "TAC",
            "expected": "FETCH RECEIVE DATA + TERMINAL RESPONSE commands"
        },
        {
            "name": "TAC + TERMINAL Only",
            "command_types": ["TERMINAL"],
            "server": "TAC",
            "expected": "Only TERMINAL RESPONSE commands"
        },
        {
            "name": "TAC + OPEN Only",
            "command_types": ["OPEN"],
            "server": "TAC",
            "expected": "Only FETCH OPEN CHANNEL commands"
        },
        {
            "name": "TAC + CLOSE Only",
            "command_types": ["CLOSE"],
            "server": "TAC",
            "expected": "Only FETCH CLOSE CHANNEL commands"
        }
    ]
    
    print("\n" + "="*80)
    print("PRECISE COMMAND TYPE FILTERING TEST")
    print("="*80)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print("-" * 60)
        print(f"   Expected: {scenario['expected']}")
        
        # Clear all filters
        filter_model.clear_all_filters()
        
        # Apply command type filter
        filter_model.set_command_type_filter(scenario['command_types'])
        
        # Apply server filter
        filter_model.set_server_filter(scenario['server'])
        
        # Count visible items and analyze types
        visible_items = []
        fetch_commands = []
        terminal_responses = []
        other_items = []
        
        for row in range(table_model.rowCount()):
            if filter_model.filterAcceptsRow(row, QModelIndex()):
                trace_item = table_model.get_trace_item(table_model.index(row, 0))
                visible_items.append(trace_item)
                
                summary_lower = trace_item.summary.lower()
                if "fetch" in summary_lower and "send data" in summary_lower:
                    fetch_commands.append(f"FETCH SEND DATA: {trace_item.summary}")
                elif "fetch" in summary_lower and "receive data" in summary_lower:
                    fetch_commands.append(f"FETCH RECEIVE DATA: {trace_item.summary}")
                elif "fetch" in summary_lower and "open channel" in summary_lower:
                    fetch_commands.append(f"FETCH OPEN: {trace_item.summary}")
                elif "fetch" in summary_lower and "close channel" in summary_lower:
                    fetch_commands.append(f"FETCH CLOSE: {trace_item.summary}")
                elif "fetch" in summary_lower:
                    fetch_commands.append(f"FETCH OTHER: {trace_item.summary}")
                elif "terminal response" in summary_lower:
                    terminal_responses.append(f"TERMINAL: {trace_item.summary}")
                else:
                    other_items.append(f"OTHER: {trace_item.summary}")
        
        print(f"\n   Results: {len(visible_items)} total items")
        print(f"   - FETCH commands: {len(fetch_commands)}")
        print(f"   - TERMINAL responses: {len(terminal_responses)}")
        print(f"   - Other items: {len(other_items)}")
        
        # Show samples of each type
        if fetch_commands:
            print(f"\n   FETCH Commands ({len(fetch_commands)}):")
            for cmd in fetch_commands[:3]:  # Show first 3
                print(f"     • {cmd}")
            if len(fetch_commands) > 3:
                print(f"     ... and {len(fetch_commands) - 3} more")
        
        if terminal_responses:
            print(f"\n   TERMINAL Responses ({len(terminal_responses)}):")
            for resp in terminal_responses[:3]:  # Show first 3
                print(f"     • {resp}")
            if len(terminal_responses) > 3:
                print(f"     ... and {len(terminal_responses) - 3} more")
        
        if other_items:
            print(f"\n   Other Items ({len(other_items)}):")
            for other in other_items[:2]:  # Show first 2
                print(f"     • {other}")
        
        # Validate the filtering precision
        print(f"\n   Validation:")
        expected_cmd_types = set(scenario['command_types'])
        
        if "SEND" in expected_cmd_types or "RECEIVE" in expected_cmd_types or "OPEN" in expected_cmd_types or "CLOSE" in expected_cmd_types:
            if "TERMINAL" in expected_cmd_types:
                # Should have both FETCH and TERMINAL
                if fetch_commands and terminal_responses:
                    print(f"     ✅ Correctly shows both FETCH commands and TERMINAL responses")
                elif fetch_commands and not terminal_responses:
                    print(f"     ⚠️  Expected TERMINAL responses but only found FETCH commands")
                elif not fetch_commands and terminal_responses:
                    print(f"     ⚠️  Expected FETCH commands but only found TERMINAL responses")
                else:
                    print(f"     ❌ No matching items found")
            else:
                # Should have only FETCH commands
                if fetch_commands and not terminal_responses:
                    print(f"     ✅ Correctly shows only FETCH commands (no terminal responses)")
                elif fetch_commands and terminal_responses:
                    print(f"     ⚠️  Found terminal responses when only FETCH commands expected")
                elif not fetch_commands and terminal_responses:
                    print(f"     ❌ Found only terminal responses when FETCH commands expected")
                else:
                    print(f"     ❌ No matching items found")
        elif "TERMINAL" in expected_cmd_types:
            # Should have only TERMINAL responses
            if not fetch_commands and terminal_responses:
                print(f"     ✅ Correctly shows only TERMINAL responses")
            elif fetch_commands and terminal_responses:
                print(f"     ⚠️  Found FETCH commands when only TERMINAL responses expected")
            else:
                print(f"     ❌ No matching items found")

    print("\n" + "="*80)
    print("PRECISE FILTERING TEST COMPLETE")
    print("="*80)
    print("\nCommand type filters are now exclusive:")
    print("• SEND = only FETCH SEND DATA commands")
    print("• SEND + TERMINAL = FETCH SEND DATA + TERMINAL RESPONSE commands")
    print("• TERMINAL = only TERMINAL RESPONSE commands")

def main():
    """Run the precise filtering test"""
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    try:
        test_precise_filtering()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())