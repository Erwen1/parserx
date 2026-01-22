#!/usr/bin/env python3
"""
Debug the inspector tree structure for OPEN CHANNEL response.
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

print("=== Debugging OPEN CHANNEL Inspector Structure ===")

# Parse BC660K file
parser = XTIParser()
trace_items = parser.parse_file("BC660K_enable_OK.xti")

# Create model
model = InterpretationTreeModel()
model.load_trace_items(trace_items)

# Find OPEN CHANNEL entry
for i in range(model.rowCount()):
    index = model.index(i, 0)
    content = model.data(index, 0)
    
    if "OPEN CHANNEL" in content:
        print(f"Found: {content}")
        tree_item = model.get_tree_item(index)
        
        if tree_item.response_item:
            print(f"\n📋 Response Item Details:")
            print(f"   Summary: {tree_item.response_item.summary}")
            print(f"   Type: {tree_item.response_item.type}")
            print(f"   Has details_tree: {tree_item.response_item.details_tree is not None}")
            
            if tree_item.response_item.details_tree:
                print(f"\n🌳 Response Details Tree Structure:")
                print_tree_structure(tree_item.response_item.details_tree)
            else:
                print("   ❌ No details_tree found")
                
            # Check for SW code
            print(f"\n📟 SW Information:")
            print(f"   Has sw_code attribute: {hasattr(tree_item.response_item, 'sw_code')}")
            if hasattr(tree_item.response_item, 'sw_code'):
                print(f"   SW Code: {tree_item.response_item.sw_code}")
            
            # Check rawhex
            print(f"\n📦 Raw Data:")
            print(f"   Rawhex: {tree_item.response_item.rawhex[:50]}..." if tree_item.response_item.rawhex else "None")
            
        break
else:
    print("❌ No OPEN CHANNEL entry found")

print("\n" + "=" * 60)
print("This will help us understand the actual data structure.")