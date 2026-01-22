#!/usr/bin/env python3
"""
Test with exact format from screenshot.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.models import InterpretationTreeModel, TraceTreeItem
from xti_viewer.xti_parser import TraceItem, TreeNode

# Create test data exactly matching the screenshot
test_items = [
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="APDU Command: MANAGE CHANNEL", rawhex=None,
        timestamp="16:16:21:272",
        details_tree=TreeNode("MANAGE CHANNEL"),
        timestamp_sort_key="16:16:21:272"
    ),
    TraceItem(
        protocol="ISO7816", type="apduresponse",
        summary="APDU Response", rawhex=None,  # Just "APDU Response" - very generic
        timestamp="16:16:22:273",
        details_tree=TreeNode("Response"), 
        timestamp_sort_key="16:16:22:273"
    )
]

print("=== Debug: Testing exact screenshot format ===")
print("Input items:")
for i, item in enumerate(test_items, 1):
    print(f"{i}. Type: {item.type}, Summary: '{item.summary}'")

# Test our detection methods
model = InterpretationTreeModel()

print(f"\n=== Testing detection methods ===")
for i, item in enumerate(test_items, 1):
    print(f"\nItem {i}: '{item.summary}'")
    print(f"  _is_apdu_command: {model._is_apdu_command(item)}")
    print(f"  _is_apdu_response: {model._is_apdu_response(item)}")
    print(f"  _is_fetch_command: {model._is_fetch_command(item)}")

print(f"\n=== Testing combined entries ===")
model.root_item = TraceTreeItem()  # Reset
model._create_combined_entries(test_items)

print(f"Result: {model.root_item.child_count()} entries:")
for i in range(model.root_item.child_count()):
    child = model.root_item.child(i)
    print(f"{i+1}. '{child.content}'")