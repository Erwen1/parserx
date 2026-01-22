#!/usr/bin/env python3
"""
Deep analysis of specific payloads from the XTI file to find TLS handshakes.
"""

import sys
import os
from xti_viewer.xti_parser import XTIParser
from xti_viewer.protocol_analyzer import ProtocolAnalyzer, TlsAnalyzer
from xti_viewer.apdu_parser_construct import parse_apdu

def analyze_specific_payloads():
    """Look for TLS handshakes in the XTI file"""
    print("🔍 Deep payload analysis for TLS detection")
    print("=" * 60)
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    # Find all SEND/RECEIVE DATA commands
    data_commands = []
    for i, item in enumerate(trace_items):
        if ("send data" in item.summary.lower() or 
            "receive data" in item.summary.lower()):
            data_commands.append((i, item))
    
    print(f"📊 Found {len(data_commands)} SEND/RECEIVE DATA commands")
    print()
    
    tls_candidates = []
    interesting_payloads = []
    
    # Analyze all data commands for TLS patterns
    for i, (trace_idx, item) in enumerate(data_commands):
        if not item.rawhex:
            continue
        
        try:
            parsed = parse_apdu(item.rawhex)
            payload = extract_payload_from_apdu(parsed)
            
            if payload and len(payload) > 10:
                # Check for TLS record markers
                if len(payload) >= 5:
                    record_type = payload[0]
                    version_major = payload[1] if len(payload) > 1 else 0
                    version_minor = payload[2] if len(payload) > 2 else 0
                    
                    # Look for TLS record types
                    if record_type in [0x16, 0x17, 0x15, 0x14]:  # TLS record types
                        if version_major == 3 and version_minor in [1, 2, 3, 4]:
                            tls_candidates.append((trace_idx, payload, f"TLS record type 0x{record_type:02X}"))
                    
                    # Look for potential HTTP
                    payload_str = payload.decode('utf-8', errors='ignore')
                    if payload_str.startswith(('GET ', 'POST ', 'HTTP/')):
                        interesting_payloads.append((trace_idx, payload, "HTTP traffic"))
                    
                    # Look for JSON
                    if payload_str.strip().startswith('{'):
                        interesting_payloads.append((trace_idx, payload, "JSON data"))
                    
                    # Look for hostname patterns in hex
                    if b'eim' in payload or b'smdp' in payload or b'tac.' in payload:
                        interesting_payloads.append((trace_idx, payload, "Hostname pattern"))
                
        except Exception as e:
            continue
    
    print(f"🔒 Found {len(tls_candidates)} potential TLS records")
    print(f"📦 Found {len(interesting_payloads)} other interesting payloads")
    print()
    
    # Analyze TLS candidates
    if tls_candidates:
        print("🔒 TLS ANALYSIS")
        print("-" * 40)
        
        for trace_idx, payload, description in tls_candidates[:5]:  # Analyze first 5
            print(f"\n📦 Item #{trace_idx+1}: {description}")
            print(f"   📊 Payload: {len(payload)} bytes")
            print(f"   🔍 Hex: {payload[:50].hex()}")
            
            # Try TLS analysis
            tls_record = TlsAnalyzer.detect_tls_record(payload)
            if tls_record:
                record_type, version_major, version_minor = tls_record
                version_name = TlsAnalyzer.TLS_VERSIONS.get((version_major, version_minor), 
                                                           f"Unknown {version_major}.{version_minor}")
                print(f"   🔒 TLS Record: Type=0x{record_type:02X}, Version={version_name}")
                
                # Try ClientHello analysis
                if record_type == 0x16:  # Handshake record
                    tls_info = TlsAnalyzer.parse_client_hello(payload)
                    if tls_info:
                        print(f"   ✅ TLS ClientHello detected!")
                        print(f"      Version: {tls_info.version}")
                        if tls_info.sni_hostname:
                            print(f"      SNI: {tls_info.sni_hostname}")
                        print(f"      Cipher Suites: {len(tls_info.cipher_suites)}")
                        print(f"      Extensions: {', '.join(tls_info.extensions)}")
                    else:
                        print(f"   ⚠️  Could not parse as ClientHello")
    
    # Analyze other interesting payloads
    if interesting_payloads:
        print("\n📦 OTHER INTERESTING PAYLOADS")
        print("-" * 40)
        
        for trace_idx, payload, description in interesting_payloads[:5]:
            print(f"\n📦 Item #{trace_idx+1}: {description}")
            print(f"   📊 Payload: {len(payload)} bytes")
            
            if description == "Hostname pattern":
                print(f"   🔍 Hex: {payload.hex()}")
                # Try to decode as string
                try:
                    decoded = payload.decode('utf-8', errors='ignore')
                    print(f"   📄 String: {repr(decoded[:100])}")
                except:
                    pass
            
            elif description in ["HTTP traffic", "JSON data"]:
                try:
                    decoded = payload.decode('utf-8', errors='ignore')
                    print(f"   📄 Content: {decoded[:200]}")
                except:
                    print(f"   🔍 Hex: {payload[:50].hex()}")
    
    print("\n" + "=" * 60)
    print("📊 DEEP ANALYSIS SUMMARY")
    print("=" * 60)
    
    if tls_candidates:
        print(f"🔒 TLS Records Found: {len(tls_candidates)}")
        print("   → Protocol analyzer should detect these automatically")
    
    if interesting_payloads:
        print(f"📦 Interesting Payloads: {len(interesting_payloads)}")
        for _, _, desc in interesting_payloads:
            print(f"   • {desc}")
    
    print("\n💡 Next Steps:")
    print("   1. Open XTI viewer GUI and navigate to a SEND/RECEIVE DATA item")
    print("   2. Check the 'Analyze' tab for protocol analysis sections")
    print("   3. Look for 'Protocol Analysis' tree nodes in the TLV structure")
    print("   4. Check 'Channel Groups' tab for auto-detected roles")

def extract_payload_from_apdu(parsed_apdu):
    """Extract payload from parsed APDU with improved TLV traversal"""
    def search_tlv_recursively(tlvs, depth=0):
        if depth > 3:
            return None
        
        for tlv in tlvs:
            # Check if this TLV has raw data
            if hasattr(tlv, 'raw_value') and tlv.raw_value and len(tlv.raw_value) > 5:
                return tlv.raw_value
            
            # Check if this TLV has hex value we can decode
            if hasattr(tlv, 'value_hex') and tlv.value_hex:
                try:
                    raw_data = bytes.fromhex(tlv.value_hex.replace(' ', ''))
                    if len(raw_data) > 5:
                        return raw_data
                except:
                    pass
            
            # Look for decoded value that might contain hex data
            if hasattr(tlv, 'decoded_value') and tlv.decoded_value:
                if isinstance(tlv.decoded_value, str):
                    hex_clean = tlv.decoded_value.replace(' ', '').replace('\n', '').replace('\r', '')
                    if len(hex_clean) > 10 and all(c in '0123456789ABCDEFabcdef' for c in hex_clean):
                        try:
                            raw_data = bytes.fromhex(hex_clean)
                            if len(raw_data) > 5:
                                return raw_data
                        except:
                            pass
            
            # Recurse into children
            if hasattr(tlv, 'children') and tlv.children:
                result = search_tlv_recursively(tlv.children, depth + 1)
                if result:
                    return result
        
        return None
    
    return search_tlv_recursively(parsed_apdu.tlvs)

if __name__ == "__main__":
    analyze_specific_payloads()