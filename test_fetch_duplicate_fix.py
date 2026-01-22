"""Test to verify FETCH duplicate entries are fixed."""
from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

print("Loading HL7812_fallback_NOK.xti...")
parser = XTIParser()
parser.parse_file('HL7812_fallback_NOK.xti')

print(f"Total trace items: {len(parser.trace_items)}")

# Create the model
model = InterpretationTreeModel()
model.load_trace_items(parser.trace_items)

print("\n" + "=" * 80)
print("CHECKING FOR DUPLICATE FETCH ENTRIES (16:55:31.742 - 16:55:31.834)")
print("=" * 80)

# Find entries in the time range
entries_in_range = []
for i in range(model.rowCount()):
    index = model.index(i, 0)
    content = model.data(index, 0)
    
    # Get the trace item to check timestamp
    tree_item = model.get_tree_item(index)
    if tree_item and tree_item.trace_item:
        timestamp = tree_item.trace_item.timestamp
        # Check if it's in our target range
        if timestamp and "16:55:31" in timestamp:
            time_part = timestamp.split()[1] if ' ' in timestamp else timestamp
            # Extract milliseconds: 16:55:31:742 or 16:55:31.742
            if ':742' in time_part or '.742' in time_part or \
               ':756' in time_part or '.756' in time_part or \
               ':818' in time_part or '.818' in time_part or \
               ':833' in time_part or '.833' in time_part or \
               ':834' in time_part or '.834' in time_part:
                entries_in_range.append({
                    'index': i,
                    'timestamp': timestamp,
                    'content': content
                })

print(f"\nFound {len(entries_in_range)} entries in time range:\n")
for entry in entries_in_range:
    print(f"{entry['index']:3d}. [{entry['timestamp']}] {entry['content']}")

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

# Expected entries (no duplicates):
# 1. FETCH - FETCH - OPEN CHANNEL
# 2. TERMINAL RESPONSE - OPEN CHANNEL - SW: 910D
# 3. FETCH - FETCH - CLOSE CHANNEL  
# 4. TERMINAL RESPONSE - CLOSE CHANNEL - SW: 910F

# Check for duplicates
fetch_open_entries = [e for e in entries_in_range if 'FETCH' in e['content'] and 'OPEN CHANNEL' in e['content']]
fetch_close_entries = [e for e in entries_in_range if 'FETCH' in e['content'] and 'CLOSE CHANNEL' in e['content']]
terminal_open_entries = [e for e in entries_in_range if 'TERMINAL RESPONSE' in e['content'] and 'OPEN CHANNEL' in e['content']]
terminal_close_entries = [e for e in entries_in_range if 'TERMINAL RESPONSE' in e['content'] and 'CLOSE CHANNEL' in e['content']]

print(f"\nFETCH - OPEN CHANNEL entries: {len(fetch_open_entries)}")
for e in fetch_open_entries:
    print(f"  - {e['content']}")

print(f"\nFETCH - CLOSE CHANNEL entries: {len(fetch_close_entries)}")
for e in fetch_close_entries:
    print(f"  - {e['content']}")

print(f"\nTERMINAL RESPONSE - OPEN CHANNEL entries: {len(terminal_open_entries)}")
for e in terminal_open_entries:
    print(f"  - {e['content']}")

print(f"\nTERMINAL RESPONSE - CLOSE CHANNEL entries: {len(terminal_close_entries)}")
for e in terminal_close_entries:
    print(f"  - {e['content']}")

print("\n" + "=" * 80)
print("EXPECTED vs ACTUAL")
print("=" * 80)

expected_pattern = [
    "FETCH - FETCH - OPEN CHANNEL",
    "TERMINAL RESPONSE - OPEN CHANNEL",
    "FETCH - FETCH - CLOSE CHANNEL",
    "TERMINAL RESPONSE - CLOSE CHANNEL"
]

print("\nExpected entries (4 total):")
for i, exp in enumerate(expected_pattern, 1):
    print(f"  {i}. {exp}")

# Filter to just the main entries (not raw FETCH entries)
main_entries = [e for e in entries_in_range if not (e['content'] == 'FETCH - OPEN CHANNEL' or e['content'] == 'FETCH - CLOSE CHANNEL')]

print(f"\nActual main entries ({len(main_entries)} total):")
for i, e in enumerate(main_entries, 1):
    print(f"  {i}. {e['content']}")

print("\n" + "=" * 80)
if len(fetch_open_entries) == 1 and len(fetch_close_entries) == 1:
    print("✅ SUCCESS! No duplicate FETCH entries found.")
    print("✅ Only showing 'FETCH - FETCH - [TYPE]' format as expected.")
else:
    print("❌ ISSUE: Still seeing duplicate FETCH entries")
    print(f"   Expected: 1 FETCH - OPEN CHANNEL entry, got {len(fetch_open_entries)}")
    print(f"   Expected: 1 FETCH - CLOSE CHANNEL entry, got {len(fetch_close_entries)}")
print("=" * 80)
