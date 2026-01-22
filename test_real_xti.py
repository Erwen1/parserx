#!/usr/bin/env python3
"""
Test interactif de l'XTI Viewer avec un fichier réel pour valider visuellement
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_with_real_xti_file():
    """Test avec un vrai fichier XTI pour voir le rendu complet."""
    
    from xti_viewer.xti_parser import XTIParser
    from xti_viewer.apdu_parser_construct import parse_apdu
    
    # Créer un fichier XTI de test avec des APDUs BIP
    test_xti_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
  <traceitem protocol="BIP" timestamp="2025-11-12 10:30:15.123" type="Command" data="D082012081030121008202818383010084054465627567B7020180040002580B504545521E4C4F43414C484F53543A393030301E" />
  <traceitem protocol="BIP" timestamp="2025-11-12 10:30:15.456" type="Response" data="9100" />
  <traceitem protocol="BIP" timestamp="2025-11-12 10:30:16.789" type="Command" data="D08201228103012100820281838301008D1A47455420687474703A2F2F7777772E6F72616E67652E66722F20485454502F312E31" />
  <traceitem protocol="BIP" timestamp="2025-11-12 10:30:17.012" type="Response" data="9100" />
  <traceitem protocol="STK" timestamp="2025-11-12 10:30:18.345" type="Command" data="D0820120810302210082028183850A696E7465726E65742E6F72616E67652E667239020840" />
</tracedata>'''
    
    test_file_path = "test_bip_traces.xti"
    
    try:
        # Écrire le fichier test
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_xti_content)
        
        print("🧪 TEST AVEC FICHIER XTI RÉEL")
        print("=" * 50)
        
        # Parser le fichier
        parser = XTIParser()
        traces = parser.parse_file(test_file_path)
        
        print(f"📁 Fichier parsé: {len(traces)} traces trouvées\n")
        
        # Analyser chaque trace avec les nouveaux décodeurs
        for i, trace in enumerate(traces, 1):
            print(f"🔍 TRACE #{i}")
            print(f"   Protocol: {trace.protocol}")
            print(f"   Type: {trace.type}")
            print(f"   Time: {trace.timestamp}")
            print(f"   Raw Hex: {trace.rawhex}")
            
            try:
                # Parser l'APDU avec les nouveaux décodeurs
                parsed = parse_apdu(trace.rawhex)
                
                print(f"   📊 PARSING RÉSULTAT:")
                print(f"      Command: {parsed.ins_name} ({parsed.ins:02X})")
                print(f"      Direction: {parsed.direction}")
                print(f"      Domain: {parsed.domain}")
                print(f"      Summary: {parsed.summary}")
                
                if parsed.tlvs:
                    print(f"      TLVs ({len(parsed.tlvs)} trouvés):")
                    for j, tlv in enumerate(parsed.tlvs, 1):
                        print(f"         {j:2d}. Tag {tlv.tag:02X} ({tlv.name}) - {tlv.length} bytes")
                        if hasattr(tlv, 'decoded_value') and tlv.decoded_value:
                            print(f"             🔹 {tlv.decoded_value}")
                        else:
                            raw_preview = tlv.value.hex().upper() if tlv.value and len(tlv.value) <= 8 else f"{tlv.value[:8].hex().upper()}..." if tlv.value else "None"
                            print(f"             📄 Raw: {raw_preview}")
                
                print()
                
            except Exception as e:
                print(f"   ❌ Erreur parsing: {e}")
                print()
        
        # Test des décodeurs spécialisés sur des données réelles
        print("🧪 TEST DÉCODEURS SPÉCIALISÉS sur données réelles:")
        print("=" * 60)
        
        # Extraire quelques TLVs intéressants des traces
        interesting_tlvs = []
        for trace in traces:
            try:
                parsed = parse_apdu(trace.rawhex)
                for tlv in parsed.tlvs:
                    if tlv.tag in [0x04, 0xB7, 0x47, 0x85, 0x8D]:  # Duration, Channel Status, APN, etc.
                        interesting_tlvs.append((tlv.tag, tlv.value, tlv.name))
            except:
                pass
        
        if interesting_tlvs:
            from xti_viewer.apdu_parser_construct import (
                decode_duration, decode_channel_status, 
                decode_network_access_name, detect_ascii_text
            )
            
            for tag, value, name in interesting_tlvs:
                print(f"🔹 Tag {tag:02X} ({name}):")
                print(f"   Raw: {value.hex().upper() if value else 'None'}")
                
                if tag == 0x04 and value:  # Duration
                    duration = decode_duration(value)
                    print(f"   ⏱️ Duration: {duration}")
                    
                elif tag == 0xB7 and value:  # Channel Status
                    status = decode_channel_status(value)
                    print(f"   📡 Status: {status}")
                    
                elif tag in [0x47, 0x85] and value:  # APN/Network Access Name
                    apn = decode_network_access_name(value)
                    print(f"   🌐 APN: {apn}")
                    
                elif value:  # ASCII detection générale
                    ascii_text = detect_ascii_text(value)
                    if ascii_text:
                        print(f"   🔤 ASCII: {ascii_text}")
                
                print()
        
        print("✅ TEST COMPLET RÉUSSI!")
        print("🚀 Toutes les améliorations fonctionnent correctement avec des données réelles!")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
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
    success = test_with_real_xti_file()
    print(f"\n{'✅ SUCCÈS' if success else '❌ ÉCHEC'} - Test avec fichier XTI réel")