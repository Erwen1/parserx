#!/usr/bin/env python3
"""
Test script to validate Universal Tracer format implementation.
"""
from xti_viewer.models import InterpretationTreeModel
from xti_viewer.xti_parser import TraceItem, TreeNode

# Create test data simulating the discovered pattern
test_items = [
    # FETCH command (type=apducommand)
    TraceItem(
        protocol=None,
        type="apducommand", 
        summary="FETCH",
        rawhex=None,
        timestamp="2024-01-15 10:30:00.000",
        details_tree=TreeNode("FETCH"),
        timestamp_sort_key="2024-01-15 10:30:00.000"
    ),
    # FETCH response with details (type=apduresponse)  
    TraceItem(
        protocol=None,
        type="apduresponse",
        summary="FETCH - POLL INTERVAL", 
        rawhex=None,
        timestamp="2024-01-15 10:30:00.001",
        details_tree=TreeNode("FETCH Details"),
        timestamp_sort_key="2024-01-15 10:30:00.001"
    ),
    # TERMINAL RESPONSE command (type=apducommand)
    TraceItem(
        protocol=None,
        type="apducommand",
        summary="TERMINAL RESPONSE - POLL INTERVAL",
        rawhex=None,
        timestamp="2024-01-15 10:30:00.002",
        details_tree=TreeNode("Terminal Response"),
        timestamp_sort_key="2024-01-15 10:30:00.002"
    ),
    # SW status response (type=apduresponse)
    TraceItem(
        protocol=None,
        type="apduresponse",
        summary="SW: 9120",
        rawhex=None,
        timestamp="2024-01-15 10:30:00.003", 
        details_tree=TreeNode("Status"),
        timestamp_sort_key="2024-01-15 10:30:00.003"
    )
]

# Test the format
print("=== Testing Universal Tracer Format ===")
model = InterpretationTreeModel()
model._create_combined_entries(test_items)

print(f"Generated {model.root_item.child_count()} combined entries:")
for i in range(model.root_item.child_count()):
    child = model.root_item.child(i)
    print(f"{i+1:2d}. {child.content}")

print("\n=== Expected Universal Tracer Output ===")
print(" 1. FETCH - FETCH - POLL INTERVAL") 
print(" 2. TERMINAL RESPONSE - POLL INTERVAL - SW: 9120")

print("\n=== Verification ===")
if model.root_item.child_count() >= 2:
    actual_1 = model.root_item.child(0).content
    actual_2 = model.root_item.child(1).content
    expected_1 = "FETCH - FETCH - POLL INTERVAL"
    expected_2 = "TERMINAL RESPONSE - POLL INTERVAL - SW: 9120"
    
    match_1 = actual_1 == expected_1
    match_2 = actual_2 == expected_2
    
    print(f"Entry 1 match: {match_1} ('{actual_1}' == '{expected_1}')")
    print(f"Entry 2 match: {match_2} ('{actual_2}' == '{expected_2}')")
    
    if match_1 and match_2:
        print("✅ SUCCESS: Universal Tracer format matches!")
    else:
        print("❌ FAILED: Format doesn't match Universal Tracer")
else:
    print("❌ FAILED: Not enough entries generated")