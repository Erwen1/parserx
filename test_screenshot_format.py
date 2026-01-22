#!/usr/bin/env python3
"""
Test with full screenshot data.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.models import InterpretationTreeModel
from xti_viewer.xti_parser import TraceItem, TreeNode

# Create test data exactly matching multiple entries from screenshot
test_items = [
    # APDU Command: MANAGE CHANNEL + response
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="APDU Command: MANAGE CHANNEL", rawhex=None,
        timestamp="16:16:21:272",
        details_tree=TreeNode("MANAGE CHANNEL"),
        timestamp_sort_key="16:16:21:272"
    ),
    TraceItem(
        protocol="ISO7816", type="apduresponse",
        summary="APDU Response", rawhex=None,
        timestamp="16:16:22:273",
        details_tree=TreeNode("Response"), 
        timestamp_sort_key="16:16:22:273"
    ),
    
    # SELECT FILE + response (with actual data)
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="SELECT FILE -  (A00000084455F1279166010101)", rawhex=None,
        timestamp="16:16:22:288",
        details_tree=TreeNode("SELECT FILE"),
        timestamp_sort_key="16:16:22:288"
    ),
    # Assuming there would be a response, but let's add UNKNOWN instead
    
    # APDU Command: UNKNOWN + response
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="APDU Command: UNKNOWN", rawhex=None,
        timestamp="16:16:23:304",
        details_tree=TreeNode("UNKNOWN"),
        timestamp_sort_key="16:16:23:304"
    ),
    TraceItem(
        protocol="ISO7816", type="apduresponse",
        summary="APDU Response", rawhex=None,
        timestamp="16:16:24:313",
        details_tree=TreeNode("Response"), 
        timestamp_sort_key="16:16:24:313"
    ),
    
    # FETCH (standalone for now)
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="FETCH", rawhex=None,
        timestamp="16:16:37:477",
        details_tree=TreeNode("FETCH"),
        timestamp_sort_key="16:16:37:477"
    )
]

print("=== Testing Full Screenshot Format ===")
model = InterpretationTreeModel()
model.load_trace_items(test_items)

print(f"\nGenerated {model.root_item.child_count()} entries:")
for i in range(model.root_item.child_count()):
    child = model.root_item.child(i)
    print(f"{i+1}. {child.content}")

print(f"\n=== Expected Universal Tracer Format ===")
print("1. APDU Command: MANAGE CHANNEL - APDU Response")
print("2. SELECT FILE -  (A00000084455F1279166010101)")
print("3. APDU Command: UNKNOWN - APDU Response") 
print("4. FETCH - FETCH")