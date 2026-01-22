"""
Debug DNS by ME filtering to see what's being shown.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from xti_viewer.xti_parser import XTIParser, tag_server_from_ips, extract_ips_from_interpretation_tree

def debug_dns_by_me_filter():
    """Debug what DNS by ME filter shows."""
    
    xti_file = r"C:\Users\T0319884\Documents\coding\python\parserx\HL7812_fallback_NOK.xti"
    
    print("🔍 Debugging DNS by ME Filter")
    print("=" * 80)
    
    parser = XTIParser()
    parser.parse_file(xti_file)
    
    print(f"✓ Loaded {len(parser.trace_items)} trace items")
    print()
    
    # Analyze sessions manually
    print("Analyzing channel sessions...")
    print()
    
    me_sessions = []
    current_session = None
    
    for idx, item in enumerate(parser.trace_items):
        summary = item.summary.lower()
        
        if "open channel" in summary:
            ips = extract_ips_from_interpretation_tree(item.details_tree)
            server = tag_server_from_ips(ips)
            
            print(f"[{idx:4d}] OPEN CHANNEL - Server: {server}, IPs: {ips}")
            
            if server == "ME":
                current_session = {
                    'start': idx,
                    'items': [idx],
                    'ips': ips
                }
        
        elif "close channel" in summary and current_session:
            current_session['items'].append(idx)
            current_session['end'] = idx
            me_sessions.append(current_session)
            print(f"[{idx:4d}] CLOSE CHANNEL - ME session closed")
            current_session = None
        
        elif current_session:
            current_session['items'].append(idx)
    
    print()
    print(f"Found {len(me_sessions)} ME (DNS by ME) sessions")
    print()
    
    # Show what would be displayed
    for i, session in enumerate(me_sessions[:3]):  # First 3 sessions
        print(f"\n{'='*80}")
        print(f"ME Session {i+1}: {len(session['items'])} items")
        print(f"{'='*80}")
        
        print(f"IPs: {session['ips']}")
        print()
        print("Items in session:")
        for idx in session['items'][:10]:
            item = parser.trace_items[idx]
            print(f"  [{idx:4d}] {item.summary}")
        
        if len(session['items']) > 10:
            print(f"  ... ({len(session['items']) - 10} more)")
    
    # Count all items that would be shown
    all_me_items = set()
    for session in me_sessions:
        all_me_items.update(session['items'])
    
    print()
    print(f"\n{'='*80}")
    print(f"Total items that SHOULD be shown with 'DNS by ME' filter: {len(all_me_items)}")
    print(f"Total items in file: {len(parser.trace_items)}")
    print(f"Percentage that should be filtered: {(1 - len(all_me_items)/len(parser.trace_items))*100:.1f}%")
    print(f"{'='*80}")

if __name__ == "__main__":
    debug_dns_by_me_filter()
