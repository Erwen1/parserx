"""Test to verify TERMINAL RESPONSE SW codes are included in sessions."""
from xti_viewer.xti_parser import XTIParser

print("Loading HL7812_fallback_NOK.xti...")
parser = XTIParser()
parser.parse_file('HL7812_fallback_NOK.xti')

print(f"Total trace items: {len(parser.trace_items)}")
print(f"Total sessions: {len(parser.channel_sessions)}")

# Find the session around 16:55:31
target_session = None
for session in parser.channel_sessions:
    if session.opened_at:
        time_str = session.opened_at.strftime("%H:%M:%S")
        if time_str.startswith("16:55:31"):
            target_session = session
            break

if not target_session:
    print("❌ Could not find target session")
    exit(1)

print("\n" + "=" * 80)
print("SESSION ANALYSIS (First BIP session around 16:55:31)")
print("=" * 80)

print(f"\nSession details:")
print(f"  Opened at: {target_session.opened_at}")
print(f"  Closed at: {target_session.closed_at}")
print(f"  Channel ID: {target_session.channel_id}")
print(f"  Protocol: {target_session.protocol}")
print(f"  Port: {target_session.port}")
print(f"  Total trace items in session: {len(target_session.traceitem_indexes)}")

print(f"\nTrace items in session:")
for i, idx in enumerate(target_session.traceitem_indexes):
    item = parser.trace_items[idx]
    print(f"{i+1:2d}. [{idx:4d}] {item.timestamp} | {item.summary[:80]}")

print("\n" + "=" * 80)
print("CHECKING FOR TERMINAL RESPONSE SW CODES")
print("=" * 80)

# Check for TERMINAL RESPONSE - OPEN CHANNEL
has_terminal_open = False
has_terminal_open_sw = False

# Check for TERMINAL RESPONSE - CLOSE CHANNEL
has_terminal_close = False
has_terminal_close_sw = False

for i, idx in enumerate(target_session.traceitem_indexes):
    item = parser.trace_items[idx]
    
    if "TERMINAL RESPONSE - OPEN CHANNEL" in item.summary:
        has_terminal_open = True
        print(f"✓ Found TERMINAL RESPONSE - OPEN CHANNEL at index {idx}")
        
        # Check if next item is SW response
        if i + 1 < len(target_session.traceitem_indexes):
            next_idx = target_session.traceitem_indexes[i + 1]
            next_item = parser.trace_items[next_idx]
            if "SW:" in next_item.summary and "910D" in next_item.summary:
                has_terminal_open_sw = True
                print(f"  ✓ SW response (910D) included at index {next_idx}")
            else:
                print(f"  ⚠ Next item is: {next_item.summary[:60]}")
    
    if "TERMINAL RESPONSE - CLOSE CHANNEL" in item.summary:
        has_terminal_close = True
        print(f"✓ Found TERMINAL RESPONSE - CLOSE CHANNEL at index {idx}")
        
        # Check if next item is SW response
        if i + 1 < len(target_session.traceitem_indexes):
            next_idx = target_session.traceitem_indexes[i + 1]
            next_item = parser.trace_items[next_idx]
            if "SW:" in next_item.summary and "910F" in next_item.summary:
                has_terminal_close_sw = True
                print(f"  ✓ SW response (910F) included at index {next_idx}")
            else:
                print(f"  ⚠ Next item is: {next_item.summary[:60]}")

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

if has_terminal_open and has_terminal_open_sw:
    print("✅ TERMINAL RESPONSE - OPEN CHANNEL with SW: 910D is included in session")
else:
    if has_terminal_open and not has_terminal_open_sw:
        print("❌ TERMINAL RESPONSE - OPEN CHANNEL found but SW: 910D is MISSING")
    else:
        print("⚠️  TERMINAL RESPONSE - OPEN CHANNEL not found in this session")

if has_terminal_close and has_terminal_close_sw:
    print("✅ TERMINAL RESPONSE - CLOSE CHANNEL with SW: 910F is included in session")
else:
    if has_terminal_close and not has_terminal_close_sw:
        print("❌ TERMINAL RESPONSE - CLOSE CHANNEL found but SW: 910F is MISSING")
    else:
        print("⚠️  TERMINAL RESPONSE - CLOSE CHANNEL not found in this session")

print("\n" + "=" * 80)
if has_terminal_open_sw and has_terminal_close_sw:
    print("✅ SUCCESS! All TERMINAL RESPONSE SW codes are included in the session")
    print("✅ When double-clicking the session in Flow Overview, all items will be shown")
else:
    print("❌ ISSUE: Some TERMINAL RESPONSE SW codes are missing from the session")
print("=" * 80)
