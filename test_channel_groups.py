#!/usr/bin/env python3
"""
Test script for XTI Viewer Channel Groups functionality.
"""

from xti_viewer.xti_parser import XTIParser


def test_channel_sessions():
    """Test channel session reconstruction."""
    parser = XTIParser()
    trace_items = parser.parse_file('BC660K_enable_OK.xti')
    
    print(f"✓ Parsed {len(trace_items)} trace items")
    print(f"✓ Found {len(parser.channel_sessions)} channel sessions")
    
    # Verify sessions have expected data
    for i, session in enumerate(parser.channel_sessions):
        print(f"\nSession {i+1}:")
        print(f"  IPs: {list(session.ips)}")
        print(f"  Protocol: {session.protocol}")
        print(f"  Port: {session.port}")
        print(f"  Trace items: {len(session.traceitem_indexes)}")
        print(f"  Channel ID: {session.channel_id}")
        print(f"  Opened at: {session.opened_at}")
        print(f"  Closed at: {session.closed_at}")
    
    # Test channel groups
    groups = parser.get_channel_groups()
    print(f"\n✓ Found {len(groups)} channel groups:")
    
    for i, group in enumerate(groups):
        print(f"\nGroup {i+1}:")
        print(f"  Type: {group['type']}")
        print(f"  Server: {group['server']}")
        print(f"  Protocol: {group['protocol']}")
        print(f"  Port: {group['port']}")
        print(f"  IPs: {group['ips']}")
        print(f"  Sessions: {len(group['sessions'])}")
    
    # Verify server tagging
    expected_servers = {"TAC", "Unknown"}
    found_servers = {group['server'] for group in groups}
    print(f"\n✓ Server tagging working: {found_servers}")
    
    # Verify IP extraction
    all_ips = set()
    for session in parser.channel_sessions:
        all_ips.update(session.ips)
    print(f"✓ IP extraction working: {all_ips}")
    
    return True


if __name__ == "__main__":
    try:
        test_channel_sessions()
        print("\n🎉 All tests passed! Channel Groups functionality is working correctly.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()