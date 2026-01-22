"""Debug script to inspect trace items for Link Dropped and BIP Error"""
import sys
sys.path.append(r"c:\Users\T0319884\Documents\coding\python\parserx")

from xti_viewer.xti_parser import XTIParser

xti_path = r"c:\Users\T0319884\Documents\coding\python\parserx\test.xti"
parser = XTIParser()
parser.parse_file(xti_path)

# Check the BIP error items
for idx in [128, 218, 306]:
    item = parser.trace_items[idx]
    print(f"\n=== Item {idx} ===")
    print(f"Summary: {item.summary}")
    print(f"Type: {item.type}")
    print(f"RawHex: {item.rawhex[:100] if item.rawhex else 'None'}")
    
    # Check details_tree
    def print_tree(node, indent=0):
        if not node:
            return
        name = getattr(node, 'name', '')
        value = getattr(node, 'value', '')
        content = getattr(node, 'content', '')
        if name or value or content:
            print(f"{'  ' * indent}{name}: {value} {content}")
        for ch in getattr(node, 'children', []) or []:
            print_tree(ch, indent + 1)
    
    if hasattr(item, 'details_tree') and item.details_tree:
        print("Details tree:")
        print_tree(item.details_tree)

# Look for ENVELOPE Channel Status
print("\n\n=== Searching for Channel Status ===")
for idx, item in enumerate(parser.trace_items):
    s = (item.summary or "").lower()
    if "channel status" in s and "envelope" in s:
        print(f"\nItem {idx}: {item.summary}")
        if hasattr(item, 'details_tree') and item.details_tree:
            print_tree(item.details_tree, 1)
