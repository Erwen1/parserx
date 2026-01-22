#!/usr/bin/env python3
"""Script pour tester le nouveau format combiné Universal Tracer-style."""

from xti_viewer.xti_parser import XTIParser
from xti_viewer.models import InterpretationTreeModel

def test_combined_format():
    """Test le nouveau format combiné comme Universal Tracer."""
    
    # Parse le fichier BC660K
    parser = XTIParser()
    try:
        parser.parse_file('BC660K_enable_OK.xti')
        print(f"✅ Parsed {len(parser.trace_items)} trace items")
    except Exception as e:
        print(f"❌ Error parsing: {e}")
        return
    
    # Créer le modèle
    model = InterpretationTreeModel()
    
    try:
        model.load_trace_items(parser.trace_items)
        print("✅ Model loaded successfully")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return
    
    # Afficher les 20 premiers éléments dans le nouveau format
    print("\n" + "="*100)
    print("🎯 NEW COMBINED FORMAT (Universal Tracer-style):")
    print("="*100)
    
    from PySide6.QtCore import Qt
    
    for i in range(min(20, model.rowCount())):
        index = model.index(i, 0)
        if index.isValid():
            display_text = model.data(index, Qt.DisplayRole)
            protocol = model.data(model.index(i, 1), Qt.DisplayRole)
            item_type = model.data(model.index(i, 2), Qt.DisplayRole)
            timestamp = model.data(model.index(i, 3), Qt.DisplayRole)
            
            print(f"{i+1:2d}. [{protocol or 'Unknown':10s}] {display_text}")
            if timestamp:
                print(f"    Time: {timestamp}")
            print("-" * 80)

if __name__ == "__main__":
    test_combined_format()