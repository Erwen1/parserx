#!/usr/bin/env python3
"""
Detailed Server Detection Analysis
Checks what IP addresses are in the XTI file and how channel sessions work
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from xti_viewer.xti_parser import XTIParser, extract_ips_from_interpretation_tree, tag_server_from_ips
import re

def analyze_server_detection():
    """Analyze server detection in detail"""
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    print(f"Analyzing server detection in HL7812_fallback_NOK.xti")
    print(f"Total trace items: {len(trace_items)}")
    
    # Track channel sessions
    channel_sessions = {}
    current_channel = None
    
    # Look for IP addresses and channel operations
    ip_findings = []
    channel_operations = []
    
    for i, item in enumerate(trace_items):
        # Extract IPs from this item
        ips = extract_ips_from_interpretation_tree(item.details_tree)
        if ips:
            server_label = tag_server_from_ips(ips)
            ip_findings.append({
                'index': i,
                'summary': item.summary,
                'ips': ips,
                'server': server_label
            })
        
        # Look for channel operations in summary
        summary_lower = item.summary.lower()
        if "open channel" in summary_lower or "close channel" in summary_lower:
            channel_operations.append({
                'index': i,
                'summary': item.summary,
                'type': 'OPEN' if 'open channel' in summary_lower else 'CLOSE',
                'ips': ips,
                'server': tag_server_from_ips(ips) if ips else 'Unknown'
            })
        
        # Also check for any mentions of known server IPs in the details
        tree_content = get_tree_content(item.details_tree)
        if any(ip in tree_content for ip in ["34.8.202.126", "13.38.212.83", "52.47.40.152", "13.39.169.102"]):
            ip_findings.append({
                'index': i,
                'summary': item.summary,
                'ips': extract_server_ips_from_content(tree_content),
                'server': 'Found server IP in content',
                'content_sample': tree_content[:200] + "..." if len(tree_content) > 200 else tree_content
            })
    
    print("\n" + "="*80)
    print("IP ADDRESS FINDINGS")
    print("="*80)
    
    if ip_findings:
        for finding in ip_findings[:10]:  # Show first 10
            print(f"\nIndex {finding['index']}: {finding['summary']}")
            print(f"  IPs found: {finding['ips']}")
            print(f"  Server: {finding['server']}")
            if 'content_sample' in finding:
                print(f"  Content: {finding['content_sample']}")
    else:
        print("No IP addresses found in trace items")
    
    print(f"\nTotal items with IPs: {len(ip_findings)}")
    
    print("\n" + "="*80)
    print("CHANNEL OPERATIONS")
    print("="*80)
    
    if channel_operations:
        for op in channel_operations:
            print(f"\nIndex {op['index']}: {op['type']} - {op['summary']}")
            print(f"  IPs: {op['ips']}")
            print(f"  Server: {op['server']}")
    else:
        print("No channel operations found")
    
    print(f"\nTotal channel operations: {len(channel_operations)}")
    
    # Look for any text containing server names or IPs
    print("\n" + "="*80)
    print("SEARCHING FOR SERVER REFERENCES IN TEXT")
    print("="*80)
    
    server_references = []
    for i, item in enumerate(trace_items[:50]):  # Check first 50 items
        tree_content = get_tree_content(item.details_tree)
        content_lower = tree_content.lower()
        
        # Check for server names or IPs
        if any(term in content_lower for term in ['tac', 'dp+', '34.8.202.126', '13.38.212.83']):
            server_references.append({
                'index': i,
                'summary': item.summary,
                'content_sample': tree_content[:300]
            })
    
    if server_references:
        for ref in server_references[:5]:  # Show first 5
            print(f"\nIndex {ref['index']}: {ref['summary']}")
            print(f"  Content: {ref['content_sample']}")
    else:
        print("No server references found in first 50 items")

def get_tree_content(tree_node):
    """Get all content from a tree node recursively"""
    content = [tree_node.content] if tree_node.content else []
    
    for child in tree_node.children:
        content.append(get_tree_content(child))
    
    return ' '.join(str(c) for c in content if c)

def extract_server_ips_from_content(content):
    """Extract known server IPs from content"""
    server_ips = ["34.8.202.126", "13.38.212.83", "52.47.40.152", "13.39.169.102"]
    found_ips = []
    
    for ip in server_ips:
        if ip in content:
            found_ips.append(ip)
    
    return found_ips

if __name__ == "__main__":
    analyze_server_detection()