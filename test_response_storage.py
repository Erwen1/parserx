#!/usr/bin/env python3
"""
Test if combined entries have response items stored.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

print("=== Testing Response Item Storage ===")

# Parse BC660K file
parser = XTIParser()
trace_items = parser.parse_file("BC660K_enable_OK.xti")

# Create model
model = InterpretationTreeModel()
model.load_trace_items(trace_items)

print(f"Loaded {model.rowCount()} combined entries")

# Check first few FETCH entries for stored response items
for i in range(min(15, model.rowCount())):
    index = model.index(i, 0)
    content = model.data(index, 0)
    
    if content.startswith("FETCH - FETCH"):
        tree_item = model.get_tree_item(index)
        
        print(f"\nEntry {i}: {content}")
        print(f"  Tree item has response_item: {hasattr(tree_item, 'response_item')}")
        
        if hasattr(tree_item, 'response_item') and tree_item.response_item:
            print(f"  ✅ Response item found: {tree_item.response_item.summary}")
            print(f"     Response type: {tree_item.response_item.type}")
        else:
            print(f"  ❌ No response item stored")
            
        print(f"  Fetch item: {tree_item.trace_item.summary}")
        break  # Just test the first FETCH entry

print("\n=== Testing UI Inspector Logic ===")
# Test what the UI would do
for i in range(min(15, model.rowCount())):
    index = model.index(i, 0)
    content = model.data(index, 0)
    
    if content.startswith("FETCH - FETCH"):
        tree_item = model.get_tree_item(index)
        
        if (tree_item and hasattr(tree_item, 'response_item') and 
            tree_item.response_item and tree_item.trace_item):
            print(f"✅ UI would call update_inspector_combined for: {content}")
            print(f"   Fetch: {tree_item.trace_item.summary}")
            print(f"   Response: {tree_item.response_item.summary}")
        else:
            print(f"❌ UI would call regular update_inspector for: {content}")
        break