#!/usr/bin/env python3
"""
Debug what command types are extracted for FETCH commands.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xti_viewer.xti_parser import XTIParser

def debug_command_type_extraction():
    """Debug command type extraction for FETCH commands"""
    
    # Load and parse the XTI file
    print("Loading HL7812_fallback_NOK.xti...")
    parser = XTIParser()
    
    try:
        parser.parse_file("HL7812_fallback_NOK.xti")
        print(f"✅ Successfully loaded {len(parser.trace_items)} trace items")
    except Exception as e:
        print(f"❌ Failed to load XTI file: {e}")
        return
    
    print("\n" + "="*70)
    print("DEBUG: Command Type Extraction for FETCH Commands")
    print("="*70)
    
    sorted_items = sorted(parser.trace_items, key=lambda x: x.timestamp_sort_key)
    
    for i, current in enumerate(sorted_items):
        if current.type == "ppscommand" and "fetch" in current.summary.lower():
            print(f"\nFETCH Command [{i}]: {current.summary}")
            
            # Check immediate response
            fetch_response = None
            if (i + 1 < len(sorted_items) and sorted_items[i + 1].type == "apduresponse"):
                fetch_response = sorted_items[i + 1]
                print(f"  Immediate response: {fetch_response.summary}")
                
                # Extract command type from the FETCH response interpretation
                command_type = ""
                if fetch_response.summary.startswith("FETCH - "):
                    command_type = fetch_response.summary.replace("FETCH - ", "")
                    print(f"  Extracted command type: '{command_type}'")
                else:
                    print(f"  ❌ Response doesn't start with 'FETCH - '")
            else:
                print(f"  ❌ No immediate apduresponse found")
            
            # Check for terminal response
            terminal_response = None
            for j in range(i + 1, min(i + 5, len(sorted_items))):  # Check next 5 items
                if (sorted_items[j].type == "apducommand" and 
                    "terminal response" in sorted_items[j].summary.lower()):
                    terminal_response = sorted_items[j]
                    print(f"  Terminal response: {terminal_response.summary}")
                    
                    terminal_summary = terminal_response.summary
                    command_type_alt = terminal_summary.replace("TERMINAL RESPONSE - ", "").replace("TERMINAL RESPONSE", "").strip()
                    if command_type_alt.startswith("- "):
                        command_type_alt = command_type_alt[2:]
                    print(f"  Terminal command type: '{command_type_alt}'")
                    break
            
            # Show what the combined summary would be
            if fetch_response and fetch_response.summary.startswith("FETCH - "):
                command_type = fetch_response.summary.replace("FETCH - ", "")
            elif terminal_response:
                terminal_summary = terminal_response.summary
                command_type = terminal_summary.replace("TERMINAL RESPONSE - ", "").replace("TERMINAL RESPONSE", "").strip()
                if command_type.startswith("- "):
                    command_type = command_type[2:]
            else:
                command_type = ""
            
            combined_summary = f"FETCH - FETCH - {command_type}" if command_type else "FETCH - FETCH"
            print(f"  Final combined summary: '{combined_summary}'")
            
            # Check if it would match OPEN filter
            summary_lower = combined_summary.lower()
            open_match = "fetch" in summary_lower and "open channel" in summary_lower
            print(f"  Would match OPEN filter: {open_match}")

if __name__ == "__main__":
    debug_command_type_extraction()