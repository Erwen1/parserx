#!/usr/bin/env python3
"""Script pour analyser les 100 premiers éléments du fichier XTI BC660K."""

from xti_viewer.xti_parser import XTIParser
import sys

def analyze_first_100_commands():
    """Analyse et affiche les 100 premiers éléments de trace."""
    
    # Charger le fichier XTI
    parser = XTIParser()
    try:
        parser.parse_file('BC660K_enable_OK.xti')
    except Exception as e:
        print(f"❌ Erreur lors du parsing: {e}")
        return
    
    print(f'📊 Total trace items: {len(parser.trace_items)}')
    print('=' * 100)
    print('🔍 First 100 trace items:')
    print('=' * 100)
    
    # Afficher les 100 premiers items
    for i, item in enumerate(parser.trace_items[:100]):
        protocol = item.protocol or "Unknown"
        item_type = item.type or "Unknown" 
        summary = item.summary[:120] if item.summary else "No summary"
        
        print(f'{i+1:3d}. [{protocol:12s}] {item_type:18s} - {summary}')
        
        if item.timestamp:
            print(f'     ⏰ Time: {item.timestamp}')
            
        # Afficher l'hex data si disponible
        if hasattr(item, 'rawhex') and item.rawhex:
            hex_preview = item.rawhex[:40] + "..." if len(item.rawhex) > 40 else item.rawhex
            print(f'     🔧 Hex: {hex_preview}')
            
        print()

if __name__ == "__main__":
    analyze_first_100_commands()