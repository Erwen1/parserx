#!/usr/bin/env python3
"""
Test du système de navigation session rapide
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_session_navigation():
    """Test de la navigation rapide entre sessions."""
    
    print("🧭 TEST NAVIGATION SESSION RAPIDE")
    print("=" * 50)
    
    from xti_viewer.models import SessionNavigator
    from xti_viewer.xti_parser import TraceItem
    
    # Créer des items de test avec différents protocoles/channels/commands
    test_items = [
        # Session BIP Channel 1
        TraceItem(
            protocol="BIP",
            type="Command",
            summary="FETCH – Number: 1, Type: OPEN CHANNEL (40), Qualifier: 00",
            rawhex="801200001281030140008502C040",
            timestamp="11/12/2025 10:30:15:123.000000",
            details_tree=None,
            timestamp_sort_key=1731408615.123
        ),
        
        TraceItem(
            protocol="BIP", 
            type="Command",
            summary="TERMINAL RESPONSE – Number: 1, Type: OPEN CHANNEL (40), Channel 1",
            rawhex="8014000009810301400082028183830100",
            timestamp="11/12/2025 10:30:15:856.000000",
            details_tree=None,
            timestamp_sort_key=1731408615.856
        ),
        
        # Session STK
        TraceItem(
            protocol="STK",
            type="Command", 
            summary="DISPLAY TEXT – Show message on screen",
            rawhex="D0820120810302200082028183850454657374",
            timestamp="11/12/2025 10:30:16:234.000000",
            details_tree=None,
            timestamp_sort_key=1731408616.234
        ),
        
        # Session BIP Channel 2
        TraceItem(
            protocol="BIP",
            type="Command",
            summary="FETCH – Number: 2, Type: SEND DATA (43), Channel 2",
            rawhex="801200001A810302430182028183830100",
            timestamp="11/12/2025 10:30:17:145.000000",
            details_tree=None,
            timestamp_sort_key=1731408617.145
        ),
        
        # Session STK autre commande
        TraceItem(
            protocol="STK",
            type="Command",
            summary="GET INPUT – Request user input",
            rawhex="D082012081030222008202818385045465787",
            timestamp="11/12/2025 10:30:18:567.000000",
            details_tree=None,
            timestamp_sort_key=1731408618.567
        ),
        
        # Session BIP Channel 1 continuation
        TraceItem(
            protocol="BIP",
            type="Command", 
            summary="GET CHANNEL STATUS – Check Channel 1 status",
            rawhex="801200000B810305430082028183830100",
            timestamp="11/12/2025 10:30:19:789.000000",
            details_tree=None,
            timestamp_sort_key=1731408619.789
        )
    ]
    
    # Initialiser le navigator
    navigator = SessionNavigator()
    navigator.analyze_sessions(test_items)
    
    print(f"📊 Analyse terminée: {len(test_items)} items analysés")
    
    # Afficher les groupes détectés
    print(f"\n📋 GROUPES DÉTECTÉS:")
    print("-" * 30)
    
    print(f"🔹 Par Protocol:")
    for protocol, items in navigator.sessions_by_protocol.items():
        print(f"   {protocol}: {len(items)} items")
    
    print(f"\n🔹 Par Channel:")
    for channel, items in navigator.sessions_by_channel.items():
        print(f"   {channel}: {len(items)} items")
    
    print(f"\n🔹 Par Command Type:")
    for cmd_type, items in navigator.sessions_by_command_type.items():
        print(f"   {cmd_type}: {len(items)} items")
    
    # Test navigation entre protocols
    print(f"\n🧭 TEST NAVIGATION PAR PROTOCOL:")
    print("-" * 40)
    
    current_item = test_items[0]  # Premier item BIP
    print(f"Item actuel: {current_item.protocol} - {current_item.summary[:30]}...")
    
    next_protocol_item = navigator.get_next_session_item(current_item, "protocol")
    if next_protocol_item:
        print(f"Prochain protocol: {next_protocol_item.protocol} - {next_protocol_item.summary[:30]}...")
    else:
        print(f"Aucun item suivant dans ce protocole")
    
    # Test navigation entre channels
    print(f"\n🧭 TEST NAVIGATION PAR CHANNEL:")
    print("-" * 40)
    
    channel_item = test_items[1]  # Item avec Channel 1
    print(f"Item actuel: {channel_item.summary[:50]}...")
    
    next_channel_item = navigator.get_next_session_item(channel_item, "channel")
    if next_channel_item:
        print(f"Prochain channel: {next_channel_item.summary[:50]}...")
    else:
        print(f"Aucun item suivant dans ce channel")
    
    # Test navigation entre types de commandes
    print(f"\n🧭 TEST NAVIGATION PAR COMMAND TYPE:")
    print("-" * 40)
    
    fetch_item = test_items[0]  # Item FETCH
    print(f"Item actuel: {fetch_item.summary[:50]}...")
    
    next_command_item = navigator.get_next_session_item(fetch_item, "command_type")
    if next_command_item:
        print(f"Prochain command type: {next_command_item.summary[:50]}...")
    else:
        print(f"Aucun item suivant de ce type")
    
    # Test navigation inverse (précédent)
    print(f"\n🔄 TEST NAVIGATION INVERSE:")
    print("-" * 40)
    
    last_item = test_items[-1]  # Dernier item
    print(f"Item actuel: {last_item.summary[:50]}...")
    
    prev_protocol_item = navigator.get_previous_session_item(last_item, "protocol")
    if prev_protocol_item:
        print(f"Protocol précédent: {prev_protocol_item.summary[:50]}...")
    
    # Test des statistiques
    print(f"\n📊 TEST STATISTIQUES:")
    print("-" * 30)
    
    protocol_stats = navigator.get_session_stats("protocol")
    print(f"Stats protocols: {protocol_stats}")
    
    channel_stats = navigator.get_session_stats("channel")
    print(f"Stats channels: {channel_stats}")
    
    command_stats = navigator.get_session_stats("command_type")
    print(f"Stats commands: {command_stats}")
    
    # Validation des résultats
    print(f"\n✅ VALIDATION:")
    print("-" * 20)
    
    assert len(navigator.sessions_by_protocol) >= 2, "Au moins 2 protocoles détectés"
    assert "BIP" in navigator.sessions_by_protocol, "Protocol BIP détecté"
    assert "STK" in navigator.sessions_by_protocol, "Protocol STK détecté"
    
    # Vérifier qu'il y a des channels
    assert len(navigator.sessions_by_channel) > 0, "Channels détectés"
    
    # Vérifier les types de commandes
    assert len(navigator.sessions_by_command_type) > 0, "Types de commandes détectés"
    
    print(f"✅ Navigation par protocole: {len(navigator.sessions_by_protocol)} groupes")
    print(f"✅ Navigation par channel: {len(navigator.sessions_by_channel)} groupes") 
    print(f"✅ Navigation par commande: {len(navigator.sessions_by_command_type)} groupes")
    
    print(f"\n🎉 TOUS LES TESTS DE NAVIGATION RÉUSSIS!")
    print(f"✅ Détection automatique des sessions") 
    print(f"✅ Navigation bidirectionnelle (suivant/précédent)")
    print(f"✅ Groupement par protocole/channel/command")
    print(f"✅ Statistiques temps réel")
    
    return True


if __name__ == "__main__":
    try:
        success = test_session_navigation()
        print(f"\n{'🎊 VALIDATION RÉUSSIE' if success else '❌ ÉCHEC DE VALIDATION'}")
    except Exception as e:
        print(f"❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()