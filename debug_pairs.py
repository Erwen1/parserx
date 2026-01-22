#!/usr/bin/env python3
"""
Debug pair lookup for combined entries.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

print("=== Debugging Pair Lookup ===")

# Parse BC660K file
parser = XTIParser()
trace_items = parser.parse_file("BC660K_enable_OK.xti")

# Create model
model = InterpretationTreeModel()
model.load_trace_items(trace_items)

print(f"Loaded {model.rowCount()} combined entries")

# Look at the first few FETCH entries and their pairs
for i in range(min(20, model.rowCount())):
    index = model.index(i, 0)
    content = model.data(index, 0)
    
    if content.startswith("FETCH - FETCH") or content.startswith("TERMINAL RESPONSE"):
        trace_item = model.get_trace_item(index)
        pair = model.get_pair_info_for_item(trace_item)
        
        print(f"\nEntry {i}: {content}")
        print(f"  Trace item summary: {trace_item.summary}")
        print(f"  Trace item type: {trace_item.type}")
        
        if pair:
            print(f"  ✅ Has pair:")
            print(f"     Fetch: {pair.fetch_item.summary if pair.fetch_item else 'None'}")
            print(f"     Response: {pair.response_item.summary if pair.response_item else 'None'}")
            print(f"     Complete: {pair.is_complete}")
        else:
            print(f"  ❌ No pair found")

# Check how many fetch pairs exist in the model
print(f"\n📊 Pair Statistics:")
print(f"   Total fetch pairs: {len(model.fetch_pairs)}")

if len(model.fetch_pairs) > 0:
    first_pair = model.fetch_pairs[0]
    print(f"\nFirst pair example:")
    print(f"   Fetch: {first_pair.fetch_item.summary}")
    print(f"   Response: {first_pair.response_item.summary if first_pair.response_item else 'None'}")
    print(f"   Complete: {first_pair.is_complete}")