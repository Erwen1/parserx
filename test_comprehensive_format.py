#!/usr/bin/env python3
"""
Comprehensive test to verify all Universal Tracer formats.
"""
from xti_viewer.models import InterpretationTreeModel
from xti_viewer.xti_parser import TraceItem, TreeNode

# Create comprehensive test data based on universal_tracer_traces.txt
test_items = [
    # SELECT FILE command + response
    TraceItem(
        protocol=None, type="apducommand", 
        summary="SELECT FILE", rawhex=None,
        timestamp="2024-01-15 10:30:00.000",
        details_tree=TreeNode("SELECT FILE Command"),
        timestamp_sort_key="2024-01-15 10:30:00.000"
    ),
    TraceItem(
        protocol=None, type="apduresponse",
        summary="SW: 9000 - Normal processing. Command correctly executed, and no response data",
        rawhex=None, timestamp="2024-01-15 10:30:00.001",
        details_tree=TreeNode("Response"), timestamp_sort_key="2024-01-15 10:30:00.001"
    ),
    
    # FETCH command pattern
    TraceItem(
        protocol=None, type="apducommand", 
        summary="FETCH", rawhex=None,
        timestamp="2024-01-15 10:30:00.002",
        details_tree=TreeNode("FETCH Command"),
        timestamp_sort_key="2024-01-15 10:30:00.002"
    ),
    TraceItem(
        protocol=None, type="apduresponse",
        summary="FETCH - OPEN CHANNEL", rawhex=None,
        timestamp="2024-01-15 10:30:00.003",
        details_tree=TreeNode("FETCH Details"), timestamp_sort_key="2024-01-15 10:30:00.003"
    ),
    
    # TERMINAL RESPONSE pattern
    TraceItem(
        protocol=None, type="apducommand",
        summary="TERMINAL RESPONSE - OPEN CHANNEL", rawhex=None,
        timestamp="2024-01-15 10:30:00.004",
        details_tree=TreeNode("Terminal Response"), timestamp_sort_key="2024-01-15 10:30:00.004"
    ),
    TraceItem(
        protocol=None, type="apduresponse",
        summary="SW: 9143 - Command correctly executed, and 67 byte(s) Proactive Command is available",
        rawhex=None, timestamp="2024-01-15 10:30:00.005",
        details_tree=TreeNode("Status"), timestamp_sort_key="2024-01-15 10:30:00.005"
    ),
    
    # ENVELOPE command pattern
    TraceItem(
        protocol=None, type="apducommand",
        summary="ENVELOPE Event Download - Data Available", rawhex=None,
        timestamp="2024-01-15 10:30:00.006",
        details_tree=TreeNode("Envelope"), timestamp_sort_key="2024-01-15 10:30:00.006"
    ),
    TraceItem(
        protocol=None, type="apduresponse",
        summary="SW: 9110 - Command correctly executed, and 16 byte(s) Proactive Command is available",
        rawhex=None, timestamp="2024-01-15 10:30:00.007",
        details_tree=TreeNode("Response"), timestamp_sort_key="2024-01-15 10:30:00.007"
    )
]

# Test the format
print("=== Testing Comprehensive Universal Tracer Format ===")
model = InterpretationTreeModel()
model._create_combined_entries(test_items)

print(f"Generated {model.root_item.child_count()} combined entries:")
for i in range(model.root_item.child_count()):
    child = model.root_item.child(i)
    print(f"{i+1:2d}. {child.content}")

print("\n=== Expected Universal Tracer Output ===")
expected_formats = [
    "SELECT FILE - SW: 9000 - Normal processing. Command correctly executed, and no response data",
    "FETCH - FETCH - OPEN CHANNEL", 
    "TERMINAL RESPONSE - OPEN CHANNEL - SW: 9143 - Command correctly executed, and 67 byte(s) Proactive Command is available",
    "ENVELOPE Event Download - Data Available - SW: 9110 - Command correctly executed, and 16 byte(s) Proactive Command is available"
]

for i, expected in enumerate(expected_formats, 1):
    print(f"{i:2d}. {expected}")

print("\n=== Verification ===")
all_match = True
for i, expected in enumerate(expected_formats):
    if i < model.root_item.child_count():
        actual = model.root_item.child(i).content
        match = actual == expected
        print(f"Entry {i+1} match: {match}")
        if not match:
            print(f"  Expected: '{expected}'")
            print(f"  Actual:   '{actual}'")
            all_match = False
    else:
        print(f"Entry {i+1} missing!")
        all_match = False

if all_match:
    print("✅ SUCCESS: All Universal Tracer formats match!")
else:
    print("❌ FAILED: Some formats don't match Universal Tracer")