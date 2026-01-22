"""Test the actual flatten function"""
import sys
sys.path.append(r"c:\Users\T0319884\Documents\coding\python\parserx")

from xti_viewer.xti_parser import XTIParser

xti_path = r"c:\Users\T0319884\Documents\coding\python\parserx\test.xti"
parser = XTIParser()
parser.parse_file(xti_path)

item = parser.trace_items[128]  # BIP error

def _flatten_details(node) -> str:
    try:
        parts = []
        def rec(n):
            if not n:
                return
            name = getattr(n, 'name', '') or ''
            val = getattr(n, 'value', '') or ''
            content = getattr(n, 'content', '') or ''
            if name or val:
                parts.append(f"{name}: {val}")
            if content:
                parts.append(content)
            for ch in getattr(n, 'children', []) or []:
                rec(ch)
        rec(node)
        return "\n".join([p for p in parts if p]).lower()
    except Exception:
        return ""

d = _flatten_details(item.details_tree)
print("Flattened details:")
print(d)
print("\n\nChecking for patterns:")
print(f"'general result:' in d: {'general result:' in d}")
print(f"'bearer independent protocol error' in d: {'bearer independent protocol error' in d}")
