"""
Debug the channel group filtering to see why OPEN CHANNEL is missing
and why some interpretations are blank.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from xti_viewer.xti_parser import XTIParser

def debug_channel_group_filtering():
    """Debug what's happening with channel group filtering."""
    
    xti_file = r"C:\Users\T0319884\Documents\coding\python\parserx\HL7812_fallback_NOK.xti"
    
    print("🔍 Debugging Channel Group Filtering")
    print("=" * 80)
    
    parser = XTIParser()
    parser.parse_file(xti_file)
    
    print(f"✓ Loaded {len(parser.trace_items)} trace items")
    print(f"✓ Found {len(parser.channel_sessions)} channel sessions")
    print()
    
    # Get channel groups
    groups = parser.get_channel_groups()
    print(f"✓ Found {len(groups)} channel groups")
    print()
    
    # Find TAC groups
    for group_idx, group in enumerate(groups):
        if "TAC" in group.get('server', ''):
            print(f"\n{'='*80}")
            print(f"📊 TAC GROUP {group_idx + 1}: {group.get('server', 'Unknown')}")
            print(f"{'='*80}")
            
            sessions = group.get("sessions", [])
            print(f"Sessions: {len(sessions)}")
            
            for sess_idx, session in enumerate(sessions):
                print(f"\n  Session {sess_idx + 1}:")
                print(f"    Channel ID: {session.channel_id}")
                print(f"    Protocol: {session.protocol}, Port: {session.port}")
                print(f"    Trace item indexes: {session.traceitem_indexes}")
                
                # Show first 10 items in this session
                print(f"\n    First items in session:")
                for idx in session.traceitem_indexes[:10]:
                    item = parser.trace_items[idx]
                    summary_display = item.summary if item.summary.strip() else "[BLANK INTERPRETATION]"
                    print(f"    [{idx:4d}] {item.type:15s} | {summary_display}")
                
                if len(session.traceitem_indexes) > 10:
                    print(f"    ... ({len(session.traceitem_indexes) - 10} more)")
            
            # Now look for OPEN CHANNEL commands around this session
            print(f"\n  🔍 Looking for OPEN CHANNEL commands near this session...")
            
            first_idx = sessions[0].traceitem_indexes[0] if sessions else 0
            
            # Look back 10 items
            print(f"\n  Items BEFORE first session item (looking back from index {first_idx}):")
            for idx in range(max(0, first_idx - 10), first_idx):
                item = parser.trace_items[idx]
                icon = "🔓" if "OPEN" in item.summary else ""
                summary_display = item.summary if item.summary.strip() else "[BLANK]"
                print(f"    [{idx:4d}] {item.type:15s} | {icon} {summary_display}")
            
            break  # Just examine first TAC group

if __name__ == "__main__":
    debug_channel_group_filtering()
