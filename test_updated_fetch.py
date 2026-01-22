#!/usr/bin/env python3
"""
Test the updated FETCH pairing logic.
"""
from xti_viewer.models import InterpretationTreeModel, CommandResponsePairingManager, CommandResponsePair
from xti_viewer.xti_parser import TraceItem, TreeNode

# Create test data simulating real XTI structure
test_items = [
    # FETCH command alone
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="FETCH", rawhex=None,
        timestamp="16:20:29:582",
        details_tree=TreeNode("FETCH"),
        timestamp_sort_key="16:20:29:582"
    ),
    
    # TERMINAL RESPONSE as separate command (paired with above FETCH)
    TraceItem(
        protocol="ISO7816", type="apducommand",
        summary="TERMINAL RESPONSE - RECEIVE DATA", rawhex=None,
        timestamp="16:20:37:208",
        details_tree=TreeNode("TERMINAL RESPONSE"),
        timestamp_sort_key="16:20:37:208"
    ),
    
    # SW Response to TERMINAL RESPONSE
    TraceItem(
        protocol="ISO7816", type="apduresponse",
        summary="SW: 9143 - Command correctly executed, and 67 byte(s) Proactive Command is available", 
        rawhex=None, timestamp="16:20:37:209",
        details_tree=TreeNode("SW Response"),
        timestamp_sort_key="16:20:37:209"
    ),
    
    # Another FETCH
    TraceItem(
        protocol="ISO7816", type="apducommand", 
        summary="FETCH", rawhex=None,
        timestamp="16:20:37:298",
        details_tree=TreeNode("FETCH"),
        timestamp_sort_key="16:20:37:298"
    ),
    
    # Another TERMINAL RESPONSE (paired with above FETCH)
    TraceItem(
        protocol="ISO7816", type="apducommand",
        summary="TERMINAL RESPONSE - CLOSE CHANNEL", rawhex=None,
        timestamp="16:20:37:299",
        details_tree=TreeNode("TERMINAL RESPONSE"),
        timestamp_sort_key="16:20:37:299"
    ),
    
    # SW Response to second TERMINAL RESPONSE
    TraceItem(
        protocol="ISO7816", type="apduresponse",
        summary="SW: 9120 - Command correctly executed, and 32 byte(s) Proactive Command is available", 
        rawhex=None, timestamp="16:20:37:300",
        details_tree=TreeNode("SW Response"),
        timestamp_sort_key="16:20:37:300"
    )
]

print("=== Testing Updated FETCH Pairing Logic ===")

# Create model and set up pairing manager manually
model = InterpretationTreeModel()

# Manually create pairs to simulate what pairing manager would do
model.pairing_manager = CommandResponsePairingManager()
model.pairing_manager.analyze_trace_items(test_items)

print("Input items:")
for i, item in enumerate(test_items, 1):
    print(f"{i}. Type: {item.type}, Summary: {item.summary}")

print("\n=== Testing new logic ===")
model._create_combined_entries(test_items)

print(f"\nGenerated {model.root_item.child_count()} entries:")
for i in range(model.root_item.child_count()):
    child = model.root_item.child(i)
    print(f"{i+1}. {child.content}")

print("\n=== Expected Universal Tracer Format ===")
print("1. FETCH - FETCH - RECEIVE DATA")
print("2. TERMINAL RESPONSE - RECEIVE DATA - SW: 9143 - Command correctly executed, and 67 byte(s) Proactive Command is available")
print("3. FETCH - FETCH - CLOSE CHANNEL") 
print("4. TERMINAL RESPONSE - CLOSE CHANNEL - SW: 9120 - Command correctly executed, and 32 byte(s) Proactive Command is available")