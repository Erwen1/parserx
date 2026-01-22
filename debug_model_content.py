#!/usr/bin/env python3
"""
Debug the actual content in the model items.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import QModelIndex, Qt

def debug_model_content():
    """Debug the actual content in model items"""
    
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
    
    print("\n" + "="*70)
    print("DEBUG: Model Content Analysis")
    print("="*70)
    
    print(f"Model has {model.rowCount()} rows")
    
    # Check the first 20 rows of the model
    for row in range(min(20, model.rowCount())):
        index = model.index(row, 0)
        
        # Get the internal item
        item = index.internalPointer()
        
        print(f"\nRow {row}:")
        print(f"  Item type: {type(item).__name__}")
        print(f"  Item content: '{item.content}'")
        print(f"  Item trace_item: {item.trace_item.summary if item.trace_item else 'None'}")
        
        # Test get_display_text
        display_text = item.get_display_text(0)
        print(f"  get_display_text(0): '{display_text}'")
        
        # Test model's data method
        model_data = model.data(index, Qt.DisplayRole)
        print(f"  model.data(DisplayRole): '{model_data}'")
        
        # Check if this might be a FETCH OPEN CHANNEL
        if item.trace_item and "fetch" in item.trace_item.summary.lower():
            print(f"  🔍 FETCH item detected!")
            
    # Look specifically for rows that should be FETCH OPEN CHANNEL
    print(f"\n{'='*50}")
    print("Looking for FETCH OPEN CHANNEL items specifically...")
    print("="*50)
    
    found_open_channel = []
    for row in range(model.rowCount()):
        index = model.index(row, 0)
        item = index.internalPointer()
        
        # Check content for open channel
        content_lower = item.content.lower()
        if "fetch" in content_lower and "open channel" in content_lower:
            found_open_channel.append((row, item))
    
    print(f"Found {len(found_open_channel)} FETCH OPEN CHANNEL items in model:")
    
    for row, item in found_open_channel:
        print(f"\nRow {row}:")
        print(f"  Content: '{item.content}'")
        print(f"  Trace item summary: '{item.trace_item.summary if item.trace_item else 'None'}'")
        
        # Get model data
        index = model.index(row, 0)
        model_data = model.data(index, Qt.DisplayRole)
        print(f"  Model data: '{model_data}'")

if __name__ == "__main__":
    debug_model_content()