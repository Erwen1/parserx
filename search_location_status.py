#!/usr/bin/env python3
"""
Search for Envelope Location Status Events in XTI file
Looks for service status: no service, limited service, normal service
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from xti_viewer.xti_parser import XTIParser
import re

def search_location_status():
    """Search for envelope location status events"""
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    print(f"Searching for Envelope Location Status in HL7812_fallback_NOK.xti")
    print(f"Total trace items: {len(trace_items)}")
    
    # Search patterns for service status
    service_patterns = [
        r"no service",
        r"limited service", 
        r"normal service",
        r"service.*status",
        r"location.*status",
        r"network.*status",
        r"registration.*status",
        r"attach.*status"
    ]
    
    # Find envelope events
    envelope_events = []
    location_events = []
    service_events = []
    
    for i, item in enumerate(trace_items):
        summary_lower = item.summary.lower()
        
        # Check for envelope events
        if "envelope" in summary_lower:
            envelope_events.append({
                'index': i,
                'summary': item.summary,
                'item': item
            })
            
            # Get full content from interpretation tree
            tree_content = get_tree_content(item.details_tree).lower()
            
            # Check for location/service status patterns
            for pattern in service_patterns:
                if re.search(pattern, summary_lower) or re.search(pattern, tree_content):
                    service_events.append({
                        'index': i,
                        'summary': item.summary,
                        'pattern_found': pattern,
                        'content_sample': tree_content[:500] if tree_content else "No content"
                    })
                    break
            
            # Check for location-related events
            if any(term in summary_lower or term in tree_content for term in ['location', 'position', 'coordinates', 'gps', 'cell', 'tower']):
                location_events.append({
                    'index': i,
                    'summary': item.summary,
                    'content_sample': tree_content[:300] if tree_content else "No content"
                })
    
    print("\n" + "="*80)
    print("ENVELOPE EVENTS ANALYSIS")
    print("="*80)
    
    print(f"\nTotal Envelope Events: {len(envelope_events)}")
    
    if envelope_events:
        print(f"\nAll Envelope Events:")
        for i, event in enumerate(envelope_events, 1):
            print(f"  {i:2d}. [Index {event['index']}] {event['summary']}")
            
            # Show some content from each envelope
            tree_content = get_tree_content(event['item'].details_tree)
            if tree_content and len(tree_content) > 50:
                print(f"      Content: {tree_content[:200]}...")
            elif tree_content:
                print(f"      Content: {tree_content}")
    
    print("\n" + "="*80)
    print("SERVICE STATUS SEARCH RESULTS")
    print("="*80)
    
    if service_events:
        print(f"\nFound {len(service_events)} items with service status indicators:")
        for event in service_events:
            print(f"\n[Index {event['index']}] {event['summary']}")
            print(f"  Pattern matched: {event['pattern_found']}")
            print(f"  Content sample: {event['content_sample']}")
    else:
        print("\nNo explicit service status indicators found.")
    
    print("\n" + "="*80)
    print("LOCATION-RELATED EVENTS")
    print("="*80)
    
    if location_events:
        print(f"\nFound {len(location_events)} location-related events:")
        for event in location_events[:10]:  # Show first 10
            print(f"\n[Index {event['index']}] {event['summary']}")
            print(f"  Content: {event['content_sample']}")
    else:
        print("\nNo location-related events found.")
    
    # Additional search for specific service status terms
    print("\n" + "="*80)
    print("DETAILED SERVICE STATUS SEARCH")
    print("="*80)
    
    specific_service_searches = {
        "No Service": ["no service", "not registered", "no network"],
        "Limited Service": ["limited service", "emergency only", "restricted"],
        "Normal Service": ["normal service", "registered", "full service", "network available"]
    }
    
    for status_type, search_terms in specific_service_searches.items():
        print(f"\nSearching for '{status_type}':")
        found_items = []
        
        for i, item in enumerate(trace_items):
            summary_lower = item.summary.lower()
            tree_content = get_tree_content(item.details_tree).lower()
            full_content = f"{summary_lower} {tree_content}"
            
            for term in search_terms:
                if term in full_content:
                    found_items.append({
                        'index': i,
                        'summary': item.summary,
                        'term': term,
                        'content': tree_content[:200]
                    })
                    break
        
        if found_items:
            print(f"  Found {len(found_items)} items:")
            for item in found_items[:5]:  # Show first 5
                print(f"    [Index {item['index']}] {item['summary']}")
                print(f"      Matched: '{item['term']}'")
                print(f"      Content: {item['content'][:150]}...")
        else:
            print(f"  No items found for '{status_type}'")

def get_tree_content(tree_node):
    """Get all content from a tree node recursively"""
    content_parts = []
    
    if tree_node.content:
        content_parts.append(str(tree_node.content))
    
    for child in tree_node.children:
        child_content = get_tree_content(child)
        if child_content:
            content_parts.append(child_content)
    
    return ' '.join(content_parts)

if __name__ == "__main__":
    search_location_status()