#!/usr/bin/env python3
"""
Detailed analysis of OPEN CHANNEL commands and their target servers.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xti_viewer.xti_parser import XTIParser, extract_ips_from_interpretation_tree, tag_server_from_ips

def analyze_open_channel_servers():
    """Analyze which servers the OPEN CHANNEL commands connect to"""
    
    # Load and parse the XTI file
    print("Loading HL7812_fallback_NOK.xti...")
    parser = XTIParser()
    
    try:
        parser.parse_file("HL7812_fallback_NOK.xti")
        print(f"✅ Successfully loaded {len(parser.trace_items)} trace items")
    except Exception as e:
        print(f"❌ Failed to load XTI file: {e}")
        return
    
    print("\n" + "="*70)
    print("DETAILED ANALYSIS: OPEN CHANNEL Commands and Target Servers")
    print("="*70)
    
    open_channel_details = []
    
    for i, item in enumerate(parser.trace_items):
        summary_lower = item.summary.lower()
        if "fetch" in summary_lower and "open channel" in summary_lower:
            # Extract IPs from this item's details tree
            ips = extract_ips_from_interpretation_tree(item.details_tree)
            server_label = tag_server_from_ips(ips)
            
            open_channel_details.append({
                'index': i,
                'summary': item.summary,
                'ips': list(ips),
                'server': server_label,
                'timestamp': item.timestamp
            })
    
    print(f"Found {len(open_channel_details)} FETCH OPEN CHANNEL commands:")
    print()
    
    for i, details in enumerate(open_channel_details, 1):
        print(f"OPEN CHANNEL #{i}:")
        print(f"  Summary: {details['summary']}")
        print(f"  Target Server: {details['server']}")
        print(f"  IPs: {details['ips']}")
        print(f"  Timestamp: {details['timestamp']}")
        print(f"  Item Index: {details['index']}")
        print()
    
    # Summary by server
    server_counts = {}
    for details in open_channel_details:
        server = details['server']
        server_counts[server] = server_counts.get(server, 0) + 1
    
    print("="*50)
    print("SUMMARY BY TARGET SERVER:")
    print("="*50)
    for server, count in sorted(server_counts.items()):
        print(f"  {server}: {count} OPEN CHANNEL commands")
    
    # Check why TAC filter might not work with OPEN commands
    print("\n" + "="*50)
    print("TAC CONNECTION ANALYSIS:")
    print("="*50)
    
    tac_related_items = []
    for item in parser.trace_items:
        ips = extract_ips_from_interpretation_tree(item.details_tree)
        server_label = tag_server_from_ips(ips)
        if server_label == "TAC":
            tac_related_items.append({
                'summary': item.summary,
                'type': item.type,
                'server': server_label
            })
    
    print(f"Total TAC-related items: {len(tac_related_items)}")
    
    # Group by type
    tac_by_type = {}
    for item in tac_related_items:
        item_type = item['type']
        if item_type not in tac_by_type:
            tac_by_type[item_type] = []
        tac_by_type[item_type].append(item['summary'])
    
    for item_type, summaries in tac_by_type.items():
        print(f"\n{item_type} ({len(summaries)} items):")
        unique_summaries = list(set(summaries))
        for summary in sorted(unique_summaries[:5]):  # Show first 5 unique
            count = summaries.count(summary)
            print(f"  - {summary} (×{count})")
        if len(unique_summaries) > 5:
            print(f"  ... and {len(unique_summaries) - 5} more types")

if __name__ == "__main__":
    analyze_open_channel_servers()