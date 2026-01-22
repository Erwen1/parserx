#!/usr/bin/env python3
"""
Final validation test: Confirm UI shows Universal Tracer format exactly.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

print("🎯 FINAL VALIDATION: Universal Tracer Format in XTI Viewer")
print("=" * 70)

# Parse BC660K file
parser = XTIParser()
trace_items = parser.parse_file("BC660K_enable_OK.xti")

# Create model exactly like UI does
model = InterpretationTreeModel()
model.load_trace_items(trace_items)

print(f"✅ Parsed {len(trace_items)} trace items → {model.rowCount()} combined entries")

# Test what UI will display (first 20 entries)
print("\n📺 WHAT THE UI NOW DISPLAYS:")
print("-" * 70)
for i in range(min(20, model.rowCount())):
    index = model.index(i, 0)
    ui_display = model.data(index, 0)  # This is what the UI shows
    print(f"{i+1:2d}. {ui_display}")

# Expected Universal Tracer format from attachment
expected = [
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

print("\n🎯 VALIDATION RESULTS:")
print("-" * 70)

perfect_match = True
for i, expected_entry in enumerate(expected):
    if i < model.rowCount():
        index = model.index(i, 0)
        actual = model.data(index, 0)
        match = actual == expected_entry
        
        status = "✅" if match else "❌"
        print(f"{status} Entry {i+1}: {'MATCH' if match else 'MISMATCH'}")
        
        if not match:
            perfect_match = False
            print(f"   Expected: {expected_entry}")
            print(f"   Actual:   {actual}")
    else:
        perfect_match = False
        print(f"❌ Entry {i+1}: MISSING")

print("\n" + "=" * 70)
if perfect_match:
    print("🎉 PERFECT SUCCESS! UI now displays Universal Tracer format exactly!")
    print("✅ All command types properly formatted")
    print("✅ FETCH commands show as 'FETCH - FETCH - [TYPE]'")
    print("✅ TERMINAL RESPONSE includes SW codes and descriptions") 
    print("✅ APDU Commands combined with responses")
    print("✅ SELECT FILE and GET RESPONSE show SW details")
else:
    print("❌ Some entries don't match - needs investigation")

print(f"\n📊 Format Statistics:")
fetch_count = sum(1 for i in range(model.rowCount()) 
                 if model.data(model.index(i, 0), 0).startswith("FETCH - FETCH"))
terminal_count = sum(1 for i in range(model.rowCount()) 
                    if model.data(model.index(i, 0), 0).startswith("TERMINAL RESPONSE"))
apdu_count = sum(1 for i in range(model.rowCount()) 
                if model.data(model.index(i, 0), 0).startswith("APDU Command:"))

print(f"   FETCH entries: {fetch_count}")
print(f"   TERMINAL RESPONSE entries: {terminal_count}")
print(f"   APDU Command entries: {apdu_count}")
print("=" * 70)