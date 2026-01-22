#!/usr/bin/env python3
"""
Debug FETCH response structure for detailed interpretation.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

def print_tree_structure(node, indent=0, prefix=""):
    """Print tree structure recursively."""
    print("  " * indent + prefix + node.content)
    for i, child in enumerate(node.children):
        is_last = i == len(node.children) - 1
        child_prefix = "└── " if is_last else "├── "
        print_tree_structure(child, indent + 1, child_prefix)

print("=== Debugging FETCH Response Structure ===")

# Parse BC660K file
parser = XTIParser()
trace_items = parser.parse_file("BC660K_enable_OK.xti")

# Look for FETCH command followed by its response
for i, item in enumerate(trace_items):
    if item.summary == "FETCH" and item.rawhex == "8012000020":
        print(f"Found FETCH command at index {i}")
        print(f"  Summary: {item.summary}")
        print(f"  Type: {item.type}")
        print(f"  Rawhex: {item.rawhex}")
        
        # Check the next item (should be the FETCH response)
        if i + 1 < len(trace_items):
            response = trace_items[i + 1]
            print(f"\nFETCH Response at index {i+1}:")
            print(f"  Summary: {response.summary}")
            print(f"  Type: {response.type}")
            print(f"  Rawhex: {response.rawhex}")
            print(f"  Has details_tree: {response.details_tree is not None}")
            
            if response.details_tree:
                print(f"\n🌳 FETCH Response Details Tree:")
                print_tree_structure(response.details_tree)
                
        # Also check what comes after (looking for TERMINAL RESPONSE)
        for j in range(i + 2, min(i + 5, len(trace_items))):
            next_item = trace_items[j]
            if "TERMINAL RESPONSE" in next_item.summary:
                print(f"\nTERMINAL RESPONSE at index {j}:")
                print(f"  Summary: {next_item.summary}")
                print(f"  Type: {next_item.type}")
                break
        
        break
else:
    print("❌ No FETCH command with rawhex 8012000020 found")

print("\n" + "=" * 60)
print("This will help us understand which item has the detailed interpretation.")