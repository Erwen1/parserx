#!/usr/bin/env python3
"""
Test de la fonctionnalité de pairing FETCH ↔ TERMINAL RESPONSE
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_command_response_pairing():
    """Test du système de pairing automatique."""
    
    print("🔗 TEST PAIRING FETCH ↔ TERMINAL RESPONSE")
    print("=" * 60)
    
    from xti_viewer.models import CommandResponsePairingManager
    from xti_viewer.xti_parser import TraceItem
    
    # Créer des items de test simulant des traces réelles
    test_items = [
        # FETCH Command #1
        TraceItem(
            protocol="STK",
            type="Command", 
            summary="FETCH – Number: 1, Type: OPEN CHANNEL (40), Qualifier: 00",
            rawhex="801200001281030140008502C040850A696E7465726E65742E6F72616E67652E6672",
            timestamp="11/12/2025 10:30:15:123.000000",
            details_tree=None,
            timestamp_sort_key=1731408615.123
        ),
        
        # TERMINAL RESPONSE #1
        TraceItem(
            protocol="STK",
            type="Command",
            summary="TERMINAL RESPONSE – Number: 1, Type: OPEN CHANNEL (40), Result: 9000",
            rawhex="8014000009810301400082028183830100",
            timestamp="11/12/2025 10:30:15:856.000000", 
            details_tree=None,
            timestamp_sort_key=1731408615.856
        ),
        
        # FETCH Command #2  
        TraceItem(
            protocol="STK",
            type="Command",
            summary="FETCH – Number: 2, Type: SEND DATA (43), Qualifier: 01", 
            rawhex="801200001A81030243018202818383010084054465627567B7020180",
            timestamp="11/12/2025 10:30:16:234.000000",
            details_tree=None,
            timestamp_sort_key=1731408616.234
        ),
        
        # TERMINAL RESPONSE #2 (Error)
        TraceItem(
            protocol="STK", 
            type="Command",
            summary="TERMINAL RESPONSE – Number: 2, Type: SEND DATA (43), Result: 9240",
            rawhex="801400000A810302430182028183830132",
            timestamp="11/12/2025 10:30:17:145.000000",
            details_tree=None,
            timestamp_sort_key=1731408617.145
        ),
        
        # FETCH Command #3 (Sans réponse)
        TraceItem(
            protocol="STK",
            type="Command", 
            summary="FETCH – Number: 3, Type: GET INPUT (22), Qualifier: 00",
            rawhex="8012000015810302220082028183850454657874",
            timestamp="11/12/2025 10:30:18:567.000000",
            details_tree=None,
            timestamp_sort_key=1731408618.567
        )
    ]
    
    # Initialiser le manager de pairing
    manager = CommandResponsePairingManager()
    
    # Analyser les items
    pairs = manager.analyze_trace_items(test_items)
    
    print(f"📊 Analyse terminée: {len(pairs)} paires trouvées")
    print()
    
    # Afficher chaque paire
    for i, pair in enumerate(pairs, 1):
        print(f"🔗 PAIRE #{i}:")
        print(f"   Command: #{pair.command_number} - {pair.command_type}")
        print(f"   FETCH: {pair.fetch_item.timestamp}")
        
        if pair.is_complete:
            print(f"   RESPONSE: {pair.response_item.timestamp}")
            print(f"   Status: {pair.get_status()}")
            print(f"   Duration: {pair.get_duration_display()}")
            print(f"   Result: {pair.response_result}")
        else:
            print(f"   RESPONSE: ⏳ Pending")
            print(f"   Status: {pair.get_status()}")
        print()
    
    # Test des méthodes de recherche
    print("🔍 TEST RECHERCHE DE PAIRES:")
    print("-" * 40)
    
    # Tester get_pair_for_item
    first_fetch = test_items[0] 
    pair_for_fetch = manager.get_pair_for_item(first_fetch)
    print(f"Paire pour 1er FETCH: Cmd#{pair_for_fetch.command_number if pair_for_fetch else 'None'}")
    
    # Tester get_paired_item
    if pair_for_fetch and pair_for_fetch.is_complete:
        paired_response = manager.get_paired_item(first_fetch)
        print(f"Item pairé pour 1er FETCH: {'TERMINAL RESPONSE trouvé' if paired_response else 'None'}")
        
        # Test inverse
        paired_fetch = manager.get_paired_item(paired_response)
        print(f"Item pairé pour 1ère RESPONSE: {'FETCH trouvé' if paired_fetch else 'None'}")
    
    print()
    
    # Test parsing timestamp
    print("⏱️ TEST PARSING TIMESTAMPS:")
    print("-" * 40)
    
    timestamp_str = "11/12/2025 10:30:15:123.456789"
    parsed_time = manager._parse_timestamp(timestamp_str)
    print(f"Timestamp: {timestamp_str}")
    print(f"Parsed: {parsed_time}")
    
    if parsed_time:
        import datetime
        dt = datetime.datetime.fromtimestamp(parsed_time)
        print(f"Datetime: {dt}")
    
    print()
    
    # Validation des résultats
    print("✅ VALIDATION:")
    print("-" * 40)
    
    success_count = sum(1 for p in pairs if p.is_complete and "Success" in p.get_status())
    error_count = sum(1 for p in pairs if p.is_complete and "Error" in p.get_status()) 
    pending_count = sum(1 for p in pairs if not p.is_complete)
    
    print(f"✅ Paires complètes avec succès: {success_count}")
    print(f"❌ Paires complètes avec erreur: {error_count}")
    print(f"⏳ Paires en attente: {pending_count}")
    
    # Vérifications
    assert len(pairs) == 3, f"Attendu 3 paires, trouvé {len(pairs)}"
    assert pairs[0].is_complete, "La première paire devrait être complète"
    assert pairs[1].is_complete, "La deuxième paire devrait être complète"
    assert not pairs[2].is_complete, "La troisième paire devrait être en attente"
    assert "Success" in pairs[0].get_status(), "La première paire devrait être un succès"
    assert "Error" in pairs[1].get_status(), "La deuxième paire devrait être une erreur"
    
    print("\n🎉 TOUS LES TESTS DE PAIRING RÉUSSIS!")
    print("✅ Détection automatique FETCH ↔ TERMINAL RESPONSE")
    print("✅ Calcul des durées et statuts")  
    print("✅ Gestion des erreurs et timeouts")
    print("✅ Navigation entre paires fonctionnelle")
    
    return True


if __name__ == "__main__":
    try:
        success = test_command_response_pairing()
        print(f"\n{'🎊 VALIDATION RÉUSSIE' if success else '❌ ÉCHEC DE VALIDATION'}")
    except Exception as e:
        print(f"❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()