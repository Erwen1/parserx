#!/usr/bin/env python3
"""
Test the complete OPEN CHANNEL inspector structure.
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

print("=== Testing Complete OPEN CHANNEL Inspector ===")

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
            
            if tree_item.response_item.details_tree:
                print(f"\n🌳 Complete Response Details Tree:")
                print_tree_structure(tree_item.response_item.details_tree)
                
                print(f"\n✅ Key elements found:")
                # Check for the missing elements
                tree_content = str(tree_item.response_item.details_tree)
                
                if "SIM/ME Interface Transport Level" in tree_content:
                    print("   ✅ SIM/ME Interface Transport Level")
                else:
                    print("   ❌ Missing SIM/ME Interface Transport Level")
                
                if "Transport protocol type: UDP" in tree_content:
                    print("   ✅ Transport protocol type: UDP")
                else:
                    print("   ❌ Missing Transport protocol type: UDP")
                    
                if "Port Number: 53" in tree_content:
                    print("   ✅ Port Number: 53")
                else:
                    print("   ❌ Missing Port Number: 53")
                    
                if "Other Address (Data Destination Address)" in tree_content:
                    print("   ✅ Other Address (Data Destination Address)")
                else:
                    print("   ❌ Missing Other Address (Data Destination Address)")
                    
                if "Address: 8:8:8:8" in tree_content:
                    print("   ✅ Address: 8:8:8:8")
                else:
                    print("   ❌ Missing Address: 8:8:8:8")
                    
            else:
                print("   ❌ No details_tree found")
            
        break
else:
    print("❌ No OPEN CHANNEL entry found")

print("\n" + "=" * 60)
print("This shows the complete interpretation structure the inspector should display!")