"""
Test what gets displayed when clicking on a channel group.
This simulates the exact UI behavior.
"""

import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from xti_viewer.xti_parser import XTIParser

def test_channel_group_display():
    """Test what items are shown when clicking on a channel group."""
    
    # Parse the XTI file
    xti_file = r"C:\Users\T0319884\Documents\coding\python\parserx\BC660K_enable_OK.xti"
    
    print("🔍 Testing Channel Group Display")
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
    
    # Test first few groups
    for group_idx, group in enumerate(groups[:5]):  # Test first 5 groups
        print(f"\n{'='*80}")
        print(f"📊 GROUP {group_idx + 1}: {group.get('server', 'Unknown')} - {group.get('type', 'Unknown')}")
        print(f"   Port: {group.get('port', 'N/A')}, Protocol: {group.get('protocol', 'N/A')}")
        print(f"{'='*80}")
        
        sessions = group.get("sessions", [])
        print(f"   Sessions in group: {len(sessions)}")
        
        # Collect all trace item indexes (this is what UI does)
        all_indexes = []
        for session in sessions:
            all_indexes.extend(session.traceitem_indexes)
        
        # Remove duplicates and sort
        all_indexes = sorted(set(all_indexes))
        
        print(f"   Total items to display: {len(all_indexes)}")
        print()
        
        # Show what would be displayed
        print("   Items that will be shown:")
        print("   " + "-" * 76)
        
        # Group by command type
        command_types = {}
        for idx in all_indexes:
            item = parser.trace_items[idx]
            summary = item.summary.strip()
            command_types[summary] = command_types.get(summary, 0) + 1
        
        # Display summary
        for cmd_type, count in sorted(command_types.items()):
            icon = "🔓" if "OPEN" in cmd_type else "🔒" if "CLOSE" in cmd_type else "📤" if "SEND" in cmd_type else "📥" if "RECEIVE" in cmd_type else "📋"
            print(f"   {icon} {cmd_type:<50} x{count}")
        
        print()
        
        # Show first 3 and last 3 actual items
        print("   First items in sequence:")
        for idx in all_indexes[:3]:
            item = parser.trace_items[idx]
            print(f"   [{idx:4d}] {item.timestamp} | {item.summary}")
        
        if len(all_indexes) > 6:
            print(f"   ... ({len(all_indexes) - 6} more items) ...")
        
        if len(all_indexes) > 3:
            print("   Last items in sequence:")
            for idx in all_indexes[-3:]:
                item = parser.trace_items[idx]
                print(f"   [{idx:4d}] {item.timestamp} | {item.summary}")
        
        print()
        
        # Check if OPEN and CLOSE are included
        has_open = any("OPEN CHANNEL" in parser.trace_items[idx].summary for idx in all_indexes)
        has_close = any("CLOSE CHANNEL" in parser.trace_items[idx].summary for idx in all_indexes)
        
        if has_open:
            print("   ✅ OPEN CHANNEL command IS included")
        else:
            print("   ⚠️  OPEN CHANNEL command NOT found")
        
        if has_close:
            print("   ✅ CLOSE CHANNEL command IS included")
        else:
            print("   ⚠️  CLOSE CHANNEL command NOT found (session may still be open)")

if __name__ == "__main__":
    test_channel_group_display()
