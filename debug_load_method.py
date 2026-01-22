#!/usr/bin/env python3
"""
Debug script to test if our load_trace_items method works as expected.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.models import InterpretationTreeModel
from xti_viewer.xti_parser import TraceItem, TreeNode

# Create test data that matches what we see in the screenshot
test_items = [
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="APDU Command: MANAGE CHANNEL", rawhex=None,
        timestamp="16:16:21:272",
        details_tree=TreeNode("MANAGE CHANNEL Command"),
        timestamp_sort_key="16:16:21:272"
    ),
    TraceItem(
        protocol="ISO7816", type="apduresponse",
        summary="APDU Response", rawhex=None,
        timestamp="16:16:22:273",
        details_tree=TreeNode("Response"), 
        timestamp_sort_key="16:16:22:273"
    ),
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="SELECT FILE", rawhex=None,
        timestamp="16:16:22:288",
        details_tree=TreeNode("SELECT FILE"),
        timestamp_sort_key="16:16:22:288"
    ),
    TraceItem(
        protocol="ISO7816", type="apduresponse",
        summary="SW: 9000", rawhex=None,
        timestamp="16:16:22:289",
        details_tree=TreeNode("SW Response"), 
        timestamp_sort_key="16:16:22:289"
    ),
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="FETCH", rawhex=None,
        timestamp="16:16:37:477",
        details_tree=TreeNode("FETCH"),
        timestamp_sort_key="16:16:37:477"
    )
]

print("=== Debug: Testing load_trace_items method ===")
print("Input items:")
for i, item in enumerate(test_items, 1):
    print(f"{i}. Type: {item.type}, Summary: {item.summary}")

try:
    model = InterpretationTreeModel()
    print(f"\nCalling load_trace_items with {len(test_items)} items...")
    model.load_trace_items(test_items)
    
    print(f"\nResult: {model.root_item.child_count()} entries generated:")
    for i in range(model.root_item.child_count()):
        child = model.root_item.child(i)
        print(f"{i+1}. {child.content}")
        
    if model.root_item.child_count() == 0:
        print("❌ ERROR: No entries generated! Something is wrong.")
    elif model.root_item.child_count() == len(test_items):
        print("⚠️ WARNING: Same number of entries as input - might be showing individual items instead of combined")
    else:
        print("✅ SUCCESS: Combined entries generated")
        
except Exception as e:
    print(f"❌ ERROR: Exception occurred: {e}")
    import traceback
    traceback.print_exc()