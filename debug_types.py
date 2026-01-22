#!/usr/bin/env python3
"""Script pour déboguer les types de trace items."""

from xti_viewer.xti_parser import XTIParser

def debug_trace_types():
    """Debug les types de trace items."""
    
    # Parse le fichier BC660K
    parser = XTIParser()
    parser.parse_file('BC660K_enable_OK.xti')
    
    print("🔍 DEBUGGING TRACE ITEM TYPES:")
    print("="*80)
    
    # Regarder les 50 premiers items
    for i, item in enumerate(parser.trace_items[:50]):
        summary = item.summary[:80]
        print(f"{i+1:2d}. TYPE: '{item.type}' | SUMMARY: {summary}")
        
        # Identifier les FETCH et TERMINAL RESPONSE
        if item.summary and "FETCH" in item.summary.upper():
            print(f"    🔸 FETCH detected: type='{item.type}'")
        if item.summary and "TERMINAL RESPONSE" in item.summary.upper():
            print(f"    🔹 TERMINAL RESPONSE detected: type='{item.type}'")
        if item.summary and "ENVELOPE" in item.summary.upper():
            print(f"    📧 ENVELOPE detected: type='{item.type}'")
            
        print("-" * 60)

if __name__ == "__main__":
    debug_trace_types()