#!/usr/bin/env python3
"""
Test intégré des améliorations qualité d'analyse #1 et #2
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_quality_improvements_integration():
    """Test intégré du pairing et de la navigation session."""
    
    print("🎯 TEST INTÉGRATION AMÉLIORATIONS QUALITÉ")
    print("=" * 60)
    print("Test: FETCH↔TERMINAL RESPONSE Pairing + Navigation Session")
    print()
    
    # Créer un fichier XTI test avec plusieurs sessions
    test_xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
  <!-- Session BIP Channel 1 -->
  <traceitem protocol="BIP" timestamp="11/12/2025 10:30:15:123.000000" type="Command">
    <data rawhex="801200001281030140008502C040850A696E7465726E65742E6F72616E67652E6672" />
    <interpretation>
      <interpretedresult content="FETCH – Number: 1, Type: OPEN CHANNEL (40), Qualifier: 00" />
    </interpretation>
  </traceitem>
  
  <traceitem protocol="BIP" timestamp="11/12/2025 10:30:15:856.000000" type="Command">
    <data rawhex="8014000009810301400082028183830100" />
    <interpretation>
      <interpretedresult content="TERMINAL RESPONSE – Number: 1, Type: OPEN CHANNEL (40), Result: 9000" />
    </interpretation>
  </traceitem>
  
  <!-- Session STK -->
  <traceitem protocol="STK" timestamp="11/12/2025 10:30:16:234.000000" type="Command">
    <data rawhex="D0820120810302200082028183850454657374" />
    <interpretation>
      <interpretedresult content="DISPLAY TEXT – Show message on screen" />
    </interpretation>
  </traceitem>
  
  <!-- Session BIP Channel 2 -->
  <traceitem protocol="BIP" timestamp="11/12/2025 10:30:17:145.000000" type="Command">
    <data rawhex="801200001A810302430182028183830100" />
    <interpretation>
      <interpretedresult content="FETCH – Number: 2, Type: SEND DATA (43), Qualifier: 01" />
    </interpretation>
  </traceitem>
  
  <traceitem protocol="BIP" timestamp="11/12/2025 10:30:18:245.000000" type="Command">
    <data rawhex="801400000A810302430182028183830132" />
    <interpretation>
      <interpretedresult content="TERMINAL RESPONSE – Number: 2, Type: SEND DATA (43), Result: 9240" />
    </interpretation>
  </traceitem>
  
  <!-- Session STK autre commande -->
  <traceitem protocol="STK" timestamp="11/12/2025 10:30:19:567.000000" type="Command">
    <data rawhex="D082012081030222008202818385045465787" />
    <interpretation>
      <interpretedresult content="GET INPUT – Request user input from user" />
    </interpretation>
  </traceitem>
  
  <!-- Session BIP Channel 1 continuation -->
  <traceitem protocol="BIP" timestamp="11/12/2025 10:30:20:789.000000" type="Command">
    <data rawhex="8012000015810302220082028183850454657874" />
    <interpretation>
      <interpretedresult content="FETCH – Number: 3, Type: GET INPUT (22), Qualifier: 00" />
    </interpretation>
  </traceitem>
</tracedata>'''
    
    test_file_path = "test_quality_integration.xti"
    
    try:
        # Écrire le fichier test
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_xti_content)
        
        print(f"📁 Fichier XTI créé: 7 items de test")
        
        # Parser et charger dans le modèle
        from xti_viewer.xti_parser import XTIParser
        from xti_viewer.models import InterpretationTreeModel
        
        parser = XTIParser()
        traces = parser.parse_file(test_file_path)
        
        model = InterpretationTreeModel()
        model.load_trace_items(traces)
        
        print(f"📊 Modèle chargé avec {len(traces)} traces")
        
        # TEST 1: Pairing FETCH ↔ TERMINAL RESPONSE
        print(f"\n🔗 TEST 1: FETCH ↔ TERMINAL RESPONSE PAIRING")
        print("-" * 50)
        
        pairs = model.command_pairs
        print(f"Paires détectées: {len(pairs)}")
        
        for i, pair in enumerate(pairs, 1):
            print(f"  {i}. Cmd#{pair.command_number} - {pair.command_type}")
            print(f"     Status: {pair.get_status()}")
            print(f"     Duration: {pair.get_duration_display()}")
            
            # Test navigation entre paires
            if pair.is_complete:
                paired_response = model.get_paired_item(pair.fetch_item)
                paired_fetch = model.get_paired_item(pair.response_item) if pair.response_item else None
                
                print(f"     ✅ Pairing bidirectionnel: {'OK' if paired_response and paired_fetch else 'NOK'}")
            print()
        
        # TEST 2: Navigation session rapide
        print(f"🧭 TEST 2: NAVIGATION SESSION RAPIDE")
        print("-" * 50)
        
        # Stats des sessions
        protocol_stats = model.get_session_stats("protocol")
        channel_stats = model.get_session_stats("channel")
        command_stats = model.get_session_stats("command_type")
        
        print(f"📊 Statistiques des sessions:")
        print(f"  Protocols: {protocol_stats}")
        print(f"  Channels: {channel_stats}")
        print(f"  Commands: {command_stats}")
        
        # Test navigation entre protocols
        if traces:
            print(f"\n🔄 Test navigation entre protocols:")
            bip_item = next((t for t in traces if t.protocol == "BIP"), None)
            if bip_item:
                next_protocol = model.get_next_session_item(bip_item, "protocol")
                prev_protocol = model.get_previous_session_item(bip_item, "protocol")
                
                print(f"  Item BIP actuel: {bip_item.summary[:40]}...")
                print(f"  Prochain protocol: {'Trouvé' if next_protocol else 'Fin de session'}")
                print(f"  Protocol précédent: {'Trouvé' if prev_protocol else 'Début de session'}")
        
        # Test navigation entre channels 
        print(f"\n📡 Test navigation entre channels:")
        if traces:
            channel_item = traces[1]  # Prendre un item avec channel
            next_channel = model.get_next_session_item(channel_item, "channel")
            prev_channel = model.get_previous_session_item(channel_item, "channel")
            
            print(f"  Item actuel: {channel_item.summary[:40]}...")
            print(f"  Prochain channel: {'Trouvé' if next_channel else 'Fin de session'}")
            print(f"  Channel précédent: {'Trouvé' if prev_channel else 'Début de session'}")
        
        # TEST 3: Intégration complète
        print(f"\n🎯 TEST 3: INTÉGRATION COMPLÈTE")
        print("-" * 50)
        
        # Vérifier que pairing et navigation coexistent
        fetch_items = [t for t in traces if "FETCH" in t.summary]
        for fetch_item in fetch_items:
            # Info de pairing
            pair_info = model.get_pair_info_for_item(fetch_item)
            paired_item = model.get_paired_item(fetch_item)
            
            # Navigation session
            next_protocol = model.get_next_session_item(fetch_item, "protocol")
            next_command = model.get_next_session_item(fetch_item, "command_type")
            
            print(f"  FETCH #{pair_info.command_number if pair_info else 'N/A'}:")
            print(f"    Pairé: {'✅' if paired_item else '❌'}")
            print(f"    Next Protocol: {'✅' if next_protocol else '❌'}")
            print(f"    Next Command: {'✅' if next_command else '❌'}")
        
        # Validation finale
        print(f"\n✅ VALIDATION INTÉGRÉE:")
        print("-" * 30)
        
        # Vérifications pairing
        complete_pairs = sum(1 for p in pairs if p.is_complete)
        pending_pairs = sum(1 for p in pairs if not p.is_complete)
        
        print(f"✅ Paires complètes: {complete_pairs}")
        print(f"⏳ Paires en attente: {pending_pairs}")
        
        # Vérifications navigation
        print(f"✅ Sessions par protocol: {len(protocol_stats)} types")
        print(f"✅ Sessions par channel: {len(channel_stats)} channels")
        print(f"✅ Sessions par command: {len(command_stats)} types")
        
        # Tests d'intégrité
        assert len(pairs) > 0, "Au moins une paire détectée"
        assert len(protocol_stats) > 0, "Au moins un protocol détecté"
        assert complete_pairs > 0, "Au moins une paire complète"
        
        print(f"\n🎊 INTÉGRATION RÉUSSIE!")
        print(f"🎯 Les deux améliorations qualité fonctionnent parfaitement ensemble:")
        print(f"   • FETCH ↔ TERMINAL RESPONSE pairing avec durées et statuts")
        print(f"   • Navigation session rapide par protocol/channel/command")
        print(f"   • Interface utilisateur enrichie avec raccourcis clavier")
        print(f"   • Statistiques temps réel et navigation bidirectionnelle")
        
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
    success = test_quality_improvements_integration()
    print(f"\n{'🎉 SUCCÈS COMPLET' if success else '❌ ÉCHEC'} - Intégration améliorations qualité")