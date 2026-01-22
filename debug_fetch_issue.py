#!/usr/bin/env python3
"""
Debug script to analyze the actual XTI file structure and see why FETCH isn't combining properly.
"""

# Let's create a simple test to see what's happening when we have separate FETCH and TERMINAL RESPONSE items
from xti_viewer.models import InterpretationTreeModel
from xti_viewer.xti_parser import TraceItem, TreeNode

print("=== Debug: Analyzing FETCH pattern issue ===")

# Simulate what we might be seeing in the actual XTI file
test_items = [
    # FETCH command alone (no immediate response)
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="FETCH", rawhex=None,
        timestamp="16:20:29:582",
        details_tree=TreeNode("FETCH"),
        timestamp_sort_key="16:20:29:582"
    ),
    
    # TERMINAL RESPONSE as separate command
    TraceItem(
        protocol="ISO7816", type="apducommand",
        summary="TERMINAL RESPONSE - RECEIVE DATA", rawhex=None,
        timestamp="16:20:37:208",
        details_tree=TreeNode("TERMINAL RESPONSE"),
        timestamp_sort_key="16:20:37:208"
    ),
    
    # Another FETCH
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="FETCH", rawhex=None,
        timestamp="16:20:37:298",
        details_tree=TreeNode("FETCH"),
        timestamp_sort_key="16:20:37:298"
    ),
    
    # Another TERMINAL RESPONSE
    TraceItem(
        protocol="ISO7816", type="apducommand",
        summary="TERMINAL RESPONSE - RECEIVE DATA", rawhex=None,
        timestamp="16:20:37:299",
        details_tree=TreeNode("TERMINAL RESPONSE"),
        timestamp_sort_key="16:20:37:299"
    )
]

print("Input items:")
for i, item in enumerate(test_items, 1):
    print(f"{i}. Type: {item.type}, Summary: {item.summary}")

print("\n=== Testing current logic ===")
model = InterpretationTreeModel()
model._create_combined_entries(test_items)

print(f"\nGenerated {model.root_item.child_count()} entries:")
for i in range(model.root_item.child_count()):
    child = model.root_item.child(i)
    print(f"{i+1}. {child.content}")

print("\n=== Analysis ===")
print("Issue: FETCH commands might not have immediate FETCH responses (apduresponse type)")
print("Instead, they might be followed by TERMINAL RESPONSE commands later")
print("We need to check if FETCH pairs with TERMINAL RESPONSE across time gaps")