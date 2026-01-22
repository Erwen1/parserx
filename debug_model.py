#!/usr/bin/env python3
"""
Debug script to see what InterpretationTreeModel produces vs what the UI shows.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

print("=== Debugging InterpretationTreeModel Output ===")

# Parse the same file the UI uses
parser = XTIParser()
trace_items = parser.parse_file("BC660K_enable_OK.xti")

print(f"Parsed {len(trace_items)} trace items")

# Create model exactly like the UI does
trace_model = InterpretationTreeModel()
trace_model.load_trace_items(trace_items)

print(f"Model has {trace_model.rowCount()} rows")

# Show what the model's data() method returns (this is what the UI displays)
print("\n=== Model data() output (what UI shows) ===")
for i in range(min(15, trace_model.rowCount())):
    index = trace_model.index(i, 0)  # Column 0 is the main display column
    data = trace_model.data(index, 0)  # DisplayRole = 0
    print(f"{i+1:2d}. {data}")

# Also check what the internal items have
print("\n=== Internal item content ===") 
for i in range(min(15, trace_model.root_item.child_count())):
    child = trace_model.root_item.child(i)
    print(f"{i+1:2d}. {child.content}")

# Check if they're different
print("\n=== Are they the same? ===")
for i in range(min(10, trace_model.rowCount())):
    index = trace_model.index(i, 0)
    data_content = trace_model.data(index, 0)
    child = trace_model.root_item.child(i)
    internal_content = child.content
    
    if data_content == internal_content:
        print(f"Row {i+1}: ✅ MATCH")
    else:
        print(f"Row {i+1}: ❌ DIFFERENT")
        print(f"  data(): {data_content}")
        print(f"  internal: {internal_content}")