#!/usr/bin/env python3
"""
Test the combined inspector tree functionality.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

print("=== Testing Combined Inspector Tree ===")

# Parse BC660K file
parser = XTIParser()
trace_items = parser.parse_file("BC660K_enable_OK.xti")

# Create model
model = InterpretationTreeModel()
model.load_trace_items(trace_items)

print(f"Loaded {model.rowCount()} combined entries")

# Find a FETCH entry
fetch_index = None
for i in range(model.rowCount()):
    index = model.index(i, 0)
    content = model.data(index, 0)
    if content.startswith("FETCH - FETCH"):
        fetch_index = i
        print(f"Found FETCH entry at index {i}: {content}")
        break

if fetch_index is not None:
    # Get the trace item and check if it's part of a pair
    source_index = model.index(fetch_index, 0)
    trace_item = model.get_trace_item(source_index)
    
    print(f"\nTrace item summary: {trace_item.summary}")
    
    # Check if it's part of a pair
    pair = model.get_pair_info_for_item(trace_item)
    
    if pair and pair.is_complete and pair.response_item:
        print(f"\n✅ Found complete pair!")
        print(f"   FETCH item: {pair.fetch_item.summary}")
        print(f"   Response item: {pair.response_item.summary}")
        
        # Show what the combined inspector would display
        print(f"\n📋 Combined Inspector would show:")
        response_summary = pair.response_item.summary
        command_type = "UNKNOWN"
        if " - " in response_summary:
            command_type = response_summary.split(" - ", 1)[1]
        
        print(f"Root: [+] FETCH - FETCH - {command_type}")
        print(f"├── [+] FETCH")
        print(f"│   └── [:] Raw Data: 0x{pair.fetch_item.rawhex}")
        print(f"│       Type : ISO7816")
        print(f"│       Time Stamp : {pair.fetch_item.timestamp}")
        print(f"│       Duration : 118570 ns")
        print(f"└── [+] FETCH - {command_type}")
        print(f"    ├── [+] Command Details (from response interpretation)")
        print(f"    ├── [:] SW: {getattr(pair.response_item, 'sw_code', 'N/A')}")
        print(f"    └── [:] Raw Data: 0x{pair.response_item.rawhex}")
        
    else:
        print(f"❌ No complete pair found for this item")
        
else:
    print("❌ No FETCH entries found in the trace")

print("\n" + "=" * 50)
print("✅ Test completed - check the actual UI to see the enhanced inspector!")