#!/usr/bin/env python3
"""
Test XTI Viewer interpretation format against Universal Tracer format using the actual BC660K file.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

# Load the actual BC660K XTI file
xti_file_path = "BC660K_enable_OK.xti"

print("=== Testing BC660K XTI File Against Universal Tracer Format ===")

try:
    # Parse the XTI file
    print(f"Loading XTI file: {xti_file_path}")
    parser = XTIParser()
    trace_items = parser.parse_file(xti_file_path)
    
    if not trace_items:
        print("❌ Failed to parse XTI file or no trace items found")
        sys.exit(1)
    
    print(f"✅ Loaded {len(trace_items)} trace items")
    
    # Process with our InterpretationTreeModel
    model = InterpretationTreeModel()
    model.load_trace_items(trace_items)
    
    print(f"\n=== XTI Viewer Interpretation Format ===")
    print(f"Generated {model.root_item.child_count()} entries:")
    
    # Show first 15 entries to match Universal Tracer sample
    max_entries = min(15, model.root_item.child_count())
    for i in range(max_entries):
        child = model.root_item.child(i)
        print(f"{i+1:2d}. {child.content}")
    
    if model.root_item.child_count() > 15:
        print(f"... and {model.root_item.child_count() - 15} more entries")
    
    print(f"\n=== Expected Universal Tracer Format (first 15 entries) ===")
    expected_formats = [
        "APDU Command: MANAGE CHANNEL - APDU Response",
        "SELECT FILE -  (A00000084455F1279166010101) - SW: 9000 - Normal processing. Command correctly executed, and no response data",
        "APDU Command: UNKNOWN - APDU Response",
        "APDU Command: MANAGE CHANNEL - APDU Response",
        "APDU Command: STATUS - APDU Response",
        "APDU Command: STATUS - APDU Response",
        "SELECT FILE -  (7FFF) - SW: 6145",
        "GET RESPONSE - SW: 910F - Command correctly executed, and 15 byte(s) Proactive Command is available",
        "APDU Command: STATUS - APDU Response",
        "FETCH - FETCH - POLL INTERVAL",
        "TERMINAL RESPONSE - POLL INTERVAL - SW: 9120 - Command correctly executed, and 32 byte(s) Proactive Command is available",
        "FETCH - FETCH - OPEN CHANNEL",
        "TERMINAL RESPONSE - OPEN CHANNEL - SW: 9143 - Command correctly executed, and 67 byte(s) Proactive Command is available",
        "FETCH - FETCH - SEND DATA",
        "TERMINAL RESPONSE - SEND DATA - SW: 9000 - Normal processing. Command correctly executed, and no response data"
    ]
    
    for i, expected in enumerate(expected_formats, 1):
        print(f"{i:2d}. {expected}")
    
    print(f"\n=== Comparison ===")
    matches = 0
    mismatches = 0
    
    for i in range(min(max_entries, len(expected_formats))):
        if i < model.root_item.child_count():
            actual = model.root_item.child(i).content
            expected = expected_formats[i]
            match = actual == expected
            
            if match:
                print(f"✅ Entry {i+1}: MATCH")
                matches += 1
            else:
                print(f"❌ Entry {i+1}: MISMATCH")
                print(f"   Expected: '{expected}'")
                print(f"   Actual:   '{actual}'")
                mismatches += 1
        else:
            print(f"❌ Entry {i+1}: MISSING (expected but not generated)")
            mismatches += 1
    
    print(f"\n=== Summary ===")
    print(f"✅ Matches: {matches}")
    print(f"❌ Mismatches: {mismatches}")
    
    if mismatches == 0:
        print("🎉 PERFECT MATCH: XTI Viewer format matches Universal Tracer exactly!")
    elif matches > mismatches:
        print("✅ MOSTLY CORRECT: Most entries match Universal Tracer format")
    else:
        print("❌ NEEDS WORK: Many entries don't match Universal Tracer format")
    
    # Additional analysis
    print(f"\n=== Detailed Analysis ===")
    
    # Check for FETCH entries
    fetch_count = 0
    terminal_response_count = 0
    apdu_command_count = 0
    
    for i in range(model.root_item.child_count()):
        content = model.root_item.child(i).content
        if content.startswith("FETCH - FETCH"):
            fetch_count += 1
        elif content.startswith("TERMINAL RESPONSE"):
            terminal_response_count += 1
        elif content.startswith("APDU Command:"):
            apdu_command_count += 1
    
    print(f"FETCH entries: {fetch_count}")
    print(f"TERMINAL RESPONSE entries: {terminal_response_count}")
    print(f"APDU Command entries: {apdu_command_count}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()