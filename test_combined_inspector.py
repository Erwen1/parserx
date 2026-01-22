#!/usr/bin/env python3
"""
Test the enhanced combined inspector tree.
"""
import sys
sys.path.insert(0, '.')

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel
from xti_viewer.ui_main import XTIViewerMainWindow

def print_tree_structure(node, indent=0, prefix=""):
    """Print tree structure recursively."""
    print("  " * indent + prefix + node.content)
    for i, child in enumerate(node.children):
        is_last = i == len(node.children) - 1
        child_prefix = "└── " if is_last else "├── "
        print_tree_structure(child, indent + 1, child_prefix)

print("=== Testing Enhanced Combined Inspector ===")

# Parse BC660K file
parser = XTIParser()
trace_items = parser.parse_file("BC660K_enable_OK.xti")

# Create model
model = InterpretationTreeModel()
model.load_trace_items(trace_items)

# Create a mock main window to test the inspector logic
class MockMainWindow:
    def get_sw_description(self, sw_code):
        sw_descriptions = {
            "9000": "Normal processing. Command correctly executed, and no response data",
            "9110": "Command correctly executed, and 16 byte(s) Proactive Command is available",
            "9120": "Command correctly executed, and 32 byte(s) Proactive Command is available", 
            "9143": "Command correctly executed, and 67 byte(s) Proactive Command is available",
            "910F": "Command correctly executed, and 15 byte(s) Proactive Command is available",
            "910D": "Command correctly executed, and 13 byte(s) Proactive Command is available",
        }
        return sw_descriptions.get(sw_code, "")
    
    def copy_tree_with_inspector_formatting(self, original_node, is_last=False, is_main_level=False, depth=0):
        from xti_viewer.xti_parser import TreeNode
        content = original_node.content.strip()
        
        has_children = len(original_node.children) > 0
        
        if is_main_level:
            if has_children:
                prefix = "|---[+] " if not is_last else "\\---[+] "
            else:
                prefix = "|---[:] " if not is_last else "\\---[:] "
        else:
            if has_children:
                prefix = "|    |---[+] " if not is_last else "|    \\---[+] "
            else:
                prefix = "|    |---[:] " if not is_last else "|    \\---[:] "
        
        new_node = TreeNode(f"{prefix}{content}")
        
        for i, child in enumerate(original_node.children):
            is_child_last = i == len(original_node.children) - 1
            new_child = self.copy_tree_with_inspector_formatting(child, is_child_last, False, depth + 1)
            new_node.add_child(new_child)
        
        return new_node

mock_window = MockMainWindow()

# Find OPEN CHANNEL entry
for i in range(model.rowCount()):
    index = model.index(i, 0)
    content = model.data(index, 0)
    
    if "OPEN CHANNEL" in content:
        print(f"Found: {content}")
        tree_item = model.get_tree_item(index)
        
        if tree_item.response_item:
            fetch_item = tree_item.trace_item
            response_item = tree_item.response_item
            
            print(f"\n🔧 Creating Combined Inspector Tree...")
            
            # Simulate the create_combined_inspector_tree method
            from xti_viewer.xti_parser import TreeNode
            
            command_type = "OPEN CHANNEL"
            root = TreeNode(f"[+] FETCH - FETCH - {command_type}")
            
            # FETCH section
            fetch_node = TreeNode("|---[+] FETCH")
            raw_data_text = f"     \\---[:] Raw Data: 0x{fetch_item.rawhex}\n              Type : ISO7816\n              Time Stamp : 16:16:37.535.000000\n              Duration : 118570 ns\n              Elapsed Time : 1348692 ns"
            fetch_raw_node = TreeNode(raw_data_text)
            fetch_node.add_child(fetch_raw_node)
            root.add_child(fetch_node)
            
            # Response section
            response_node = TreeNode(f"\\---[+] FETCH - {command_type}")
            
            # Add details from response
            if response_item.details_tree and response_item.details_tree.children:
                for i, child_node in enumerate(response_item.details_tree.children):
                    is_last_detail = i == len(response_item.details_tree.children) - 1
                    enhanced_child = mock_window.copy_tree_with_inspector_formatting(child_node, is_last_detail, True, 1)
                    response_node.add_child(enhanced_child)
            
            # Add SW code
            if response_item.rawhex and len(response_item.rawhex) >= 4:
                sw_code = response_item.rawhex[-4:].upper()
                sw_description = mock_window.get_sw_description(sw_code)
                sw_text = f"SW: {sw_code}"
                if sw_description:
                    sw_text += f" - {sw_description}"
                sw_node = TreeNode(f"|---[:] {sw_text}")
                response_node.add_child(sw_node)
            
            # Add raw data
            response_raw_text = f"\\---[:] Raw Data: 0x{response_item.rawhex}\n              Type : ISO7816\n              Time Stamp : 16:16:37.535.000000\n              Duration : 1018032 ns\n              Elapsed Time : 768200 ns"
            response_raw_node = TreeNode(response_raw_text)
            response_node.add_child(response_raw_node)
            
            root.add_child(response_node)
            
            print(f"\n🌳 Generated Combined Inspector Tree:")
            print_tree_structure(root)
            
        break
        
print("\n" + "=" * 60)
print("✅ Test completed - this shows what the inspector should display!")