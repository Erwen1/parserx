"""Test event detection logic directly"""
import sys
sys.path.append(r"c:\Users\T0319884\Documents\coding\python\parserx")

from xti_viewer.xti_parser import XTIParser

xti_path = r"c:\Users\T0319884\Documents\coding\python\parserx\test.xti"
parser = XTIParser()
parser.parse_file(xti_path)

# Test BIP error detection
item_128 = parser.trace_items[128]
s = (item_128.summary or "").lower()

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

d = _flatten_details(getattr(item_128, 'details_tree', None))

print(f"Summary: '{s}'")
print(f"\nChecks:")
print(f"  'bearer independent protocol error' in s: {'bearer independent protocol error' in s}")
print(f"  'bip error' in s: {'bip error' in s}")
print(f"  'general result:' in d: {'general result:' in d}")
print(f"  'bearer independent protocol error' in d: {'bearer independent protocol error' in d}")

ev = None
if not ev and ("bearer independent protocol error" in s or "bip error" in s or ("general result:" in d and "bearer independent protocol error" in d)):
    print("\n✓ BIP error condition met!")
    # Try to extract cause code from raw hex
    import re
    raw_hex = (item_128.rawhex or "").replace(" ", "").upper()
    m = re.search(r"(?:03|83)023A([0-9A-F]{2})", raw_hex)
    if m:
        cause = m.group(1)
        ev = f"BIP Error: 0x{cause}"
    else:
        ev = "BIP Error"
    print(f"  Event: {ev}")
else:
    print("\n✗ BIP error condition NOT met")

# Test Link Dropped detection
print("\n\n=== Testing Link Dropped ===")
item_124 = parser.trace_items[124]
s_link = (item_124.summary or "").lower()
d_link = _flatten_details(getattr(item_124, 'details_tree', None))

print(f"Summary: '{s_link}'")
print(f"\nChecks:")
print(f"  'link dropped' in s: {'link dropped' in s_link}")
print(f"  'channel status' in s: {'channel status' in s_link}")
print(f"  'link off' in s: {'link off' in s_link}")
print(f"  'status:' in d: {'status:' in d_link}")
print(f"  'link dropped' in d: {'link dropped' in d_link}")
print(f"  'link off' in d: {'link off' in d_link}")

ev_link = None
if ("link dropped" in s_link) or ("channel status" in s_link and ("link off" in s_link or "pdp not activated" in s_link)) or ("status:" in d_link and ("link dropped" in d_link or "link off" in d_link)):
    print("\n✓ Link Dropped condition met!")
    # Try to extract channel ID
    m_id = re.search(r"identifier:\s*(\d+)", d_link)
    chan_id = m_id.group(1) if m_id else None
    ev_link = "Link Dropped" if not chan_id else f"Link Dropped (Channel {chan_id})"
    print(f"  Event: {ev_link}")
else:
    print("\n✗ Link Dropped condition NOT met")
