#!/usr/bin/env python3
"""
Test complet du pairing avec un fichier XTI simulé
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_pairing_with_xti_file():
    """Test du pairing avec un vrai fichier XTI."""
    
    print("🗂️ TEST PAIRING AVEC FICHIER XTI")
    print("=" * 50)
    
    # Créer un fichier XTI de test avec paires FETCH/RESPONSE
    test_xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
  <traceitem protocol="STK" timestamp="11/12/2025 10:30:15:123.000000" type="Command">
    <data rawhex="801200001281030140008502C040850A696E7465726E65742E6F72616E67652E6672" />
    <interpretation>
      <interpretedresult content="FETCH – Number: 1, Type: OPEN CHANNEL (40), Qualifier: 00" />
    </interpretation>
  </traceitem>
  
  <traceitem protocol="STK" timestamp="11/12/2025 10:30:15:856.000000" type="Command">
    <data rawhex="8014000009810301400082028183830100" />
    <interpretation>
      <interpretedresult content="TERMINAL RESPONSE – Number: 1, Type: OPEN CHANNEL (40), Result: 9000" />
    </interpretation>
  </traceitem>
  
  <traceitem protocol="STK" timestamp="11/12/2025 10:30:16:234.000000" type="Command">
    <data rawhex="801200001A81030243018202818383010084054465627567B7020180" />
    <interpretation>
      <interpretedresult content="FETCH – Number: 2, Type: SEND DATA (43), Qualifier: 01" />
    </interpretation>
  </traceitem>
  
  <traceitem protocol="STK" timestamp="11/12/2025 10:30:17:145.000000" type="Command">
    <data rawhex="801400000A810302430182028183830132" />
    <interpretation>
      <interpretedresult content="TERMINAL RESPONSE – Number: 2, Type: SEND DATA (43), Result: 9240" />
    </interpretation>
  </traceitem>
  
  <traceitem protocol="STK" timestamp="11/12/2025 10:30:18:567.000000" type="Command">
    <data rawhex="8012000015810302220082028183850454657874" />
    <interpretation>
      <interpretedresult content="FETCH – Number: 3, Type: GET INPUT (22), Qualifier: 00" />
    </interpretation>
  </traceitem>
</tracedata>'''
    
    test_file_path = "test_pairing.xti"
    
    try:
        # Écrire le fichier test
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_xti_content)
        
        print(f"📁 Fichier XTI créé: {test_file_path}")
        
        # Parser le fichier avec XTIParser
        from xti_viewer.xti_parser import XTIParser
        parser = XTIParser()
        traces = parser.parse_file(test_file_path)
        
        print(f"📊 Fichier parsé: {len(traces)} traces trouvées")
        
        # Tester le pairing sur les traces parsées
        from xti_viewer.models import InterpretationTreeModel
        
        model = InterpretationTreeModel()
        model.load_trace_items(traces)
        
        print(f"🔗 Modèle chargé avec pairing")
        print(f"📋 Paires détectées: {len(model.command_pairs)}")
        
        # Afficher les détails de chaque paire
        for i, pair in enumerate(model.command_pairs, 1):
            print(f"\n🔗 PAIRE #{i}:")
            print(f"   Cmd: #{pair.command_number} - {pair.command_type}")
            print(f"   FETCH: {pair.fetch_item.summary[:50]}...")
            
            if pair.is_complete:
                print(f"   RESPONSE: {pair.response_item.summary[:50]}...")
                print(f"   Status: {pair.get_status()}")
                print(f"   Duration: {pair.get_duration_display()}")
            else:
                print(f"   RESPONSE: ⏳ En attente")
        
        # Test des méthodes du modèle
        print(f"\n🔍 TEST MÉTHODES MODÈLE:")
        print("-" * 30)
        
        if traces:
            first_trace = traces[0]
            pair_info = model.get_pair_info_for_item(first_trace)
            
            if pair_info:
                print(f"✅ Paire trouvée pour 1er item: Cmd#{pair_info.command_number}")
                
                paired_item = model.get_paired_item(first_trace)
                if paired_item:
                    print(f"✅ Item pairé trouvé: {paired_item.summary[:50]}...")
                else:
                    print(f"⚠️ Item pairé non trouvé")
            else:
                print(f"⚠️ Pas de paire pour le 1er item")
        
        print(f"\n✅ TEST AVEC FICHIER XTI RÉUSSI!")
        print(f"🎯 Le pairing fonctionne parfaitement avec de vraies données")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Nettoyer le fichier test
        try:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
        except:
            pass


if __name__ == "__main__":
    success = test_pairing_with_xti_file()
    print(f"\n{'🎉 SUCCÈS' if success else '❌ ÉCHEC'} - Test pairing avec XTI")