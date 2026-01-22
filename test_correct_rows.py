#!/usr/bin/env python3
"""
Test filtering with the correct model rows that have proper content.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import QModelIndex, Qt

def test_correct_rows():
    """Test filtering with correct rows that have FETCH OPEN CHANNEL content"""
    
    # Load and parse the XTI file
    print("Loading HL7812_fallback_NOK.xti...")
    parser = XTIParser()
    
    try:
        parser.parse_file("HL7812_fallback_NOK.xti")
        print(f"✅ Successfully loaded {len(parser.trace_items)} trace items")
    except Exception as e:
        print(f"❌ Failed to load XTI file: {e}")
        return
    
    # Create models
    model = InterpretationTreeModel()
    model.load_trace_items(parser.trace_items)
    
    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(model)
    
    print("\n" + "="*70)
    print("TESTING: Correct Model Rows for FETCH OPEN CHANNEL")
    print("="*70)
    
    # Set up combined filters
    filter_model.clear_all_filters()
    filter_model.set_command_type_filter(["OPEN"])
    filter_model.set_server_filter("TAC")
    
    # From the debug output, the FETCH OPEN CHANNEL rows are:
    # Row 6, 15, 40, 312, 318, 338
    fetch_open_rows = [6, 15, 40, 312, 318, 338]
    
    print(f"Testing {len(fetch_open_rows)} FETCH OPEN CHANNEL rows...")
    
    for model_row in fetch_open_rows:
        index = model.index(model_row, 0)
        item = index.internalPointer()
        
        print(f"\n{'='*40}")
        print(f"Testing Row {model_row}")
        print(f"{'='*40}")
        print(f"Content: '{item.content}'")
        print(f"Trace item: '{item.trace_item.summary if item.trace_item else 'None'}'")
        
        # Test command type filter
        summary_lower = item.content.lower()
        command_match = "fetch" in summary_lower and "open channel" in summary_lower
        print(f"Command filter match: {command_match}")
        
        # Test server filter by checking the underlying trace item
        if item.trace_item:
            from xti_viewer.xti_parser import extract_ips_from_interpretation_tree, tag_server_from_ips
            ips = extract_ips_from_interpretation_tree(item.trace_item.details_tree)
            server_label = tag_server_from_ips(ips)
            print(f"Server label: {server_label}")
            print(f"Server filter match: {server_label == 'TAC'}")
        
        # Test actual filter
        accepts = filter_model.filterAcceptsRow(model_row, QModelIndex())
        print(f"Filter accepts: {accepts}")
        
        if accepts:
            print("✅ SUCCESS: This row passes the combined filter!")
        else:
            print("❌ FAILED: This row is rejected by the combined filter")

if __name__ == "__main__":
    test_correct_rows()