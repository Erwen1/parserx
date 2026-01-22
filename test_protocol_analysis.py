#!/usr/bin/env python3
"""
Test script for protocol analysis on HL7812_fallback_NOK.xti file.
This script will analyze the XTI file to demonstrate the new protocol features.
"""

import sys
import os
from xti_viewer.xti_parser import XTIParser
from xti_viewer.protocol_analyzer import ProtocolAnalyzer, ChannelRoleDetector
from xti_viewer.apdu_parser_construct import parse_apdu

def analyze_xti_file(file_path):
    """Analyze the XTI file for protocol features"""
    print(f"🔍 Analyzing XTI file: {os.path.basename(file_path)}")
    print("=" * 60)
    
    # Parse the XTI file
    try:
        parser = XTIParser()
        trace_items = parser.parse_file(file_path)
        print(f"✅ Loaded {len(trace_items)} trace items")
    except Exception as e:
        print(f"❌ Failed to load XTI file: {e}")
        return
    
    # Find SEND/RECEIVE DATA commands
    data_commands = []
    for i, item in enumerate(trace_items):
        if ("send data" in item.summary.lower() or 
            "receive data" in item.summary.lower()):
            data_commands.append((i, item))
    
    print(f"📊 Found {len(data_commands)} SEND/RECEIVE DATA commands")
    print()
    
    if not data_commands:
        print("ℹ️  No SEND/RECEIVE DATA commands found for protocol analysis")
        return
    
    # Analyze first few data commands for protocol content
    print("🔬 Analyzing SEND/RECEIVE DATA payloads...")
    print("-" * 60)
    
    roles_detected = set()
    protocols_found = {}
    
    for i, (trace_idx, item) in enumerate(data_commands[:10]):  # Check first 10
        print(f"\n📦 Item #{trace_idx+1}: {item.summary[:60]}...")
        
        if not item.rawhex:
            print("   ⚠️  No raw data available")
            continue
        
        try:
            # Parse APDU
            parsed = parse_apdu(item.rawhex)
            print(f"   📋 APDU: {parsed.ins_name} (0x{parsed.ins:02X})")
            
            # Debug: Show TLV structure
            print(f"   🔍 TLVs: {len(parsed.tlvs)} top-level")
            for j, tlv in enumerate(parsed.tlvs[:3]):  # Show first 3 TLVs
                if hasattr(tlv, 'tag'):
                    print(f"      TLV[{j}]: Tag=0x{tlv.tag:02X}, Name='{getattr(tlv, 'name', 'Unknown')}'")
                    if hasattr(tlv, 'decoded_value'):
                        decoded_preview = str(tlv.decoded_value)[:50]
                        print(f"               Value='{decoded_preview}{'...' if len(str(tlv.decoded_value)) > 50 else ''}'")
            
            # Extract payload
            payload = extract_payload_from_apdu(parsed)
            if not payload:
                print("   ⚠️  No payload data found")
                continue
            
            print(f"   📊 Payload: {len(payload)} bytes - {payload[:20].hex() if len(payload) >= 20 else payload.hex()}")
            
            # Analyze protocol
            analysis = ProtocolAnalyzer.analyze_payload(payload)
            print(f"   🎯 Type: {analysis.raw_classification}")
            
            if analysis.payload_type.value not in protocols_found:
                protocols_found[analysis.payload_type.value] = 0
            protocols_found[analysis.payload_type.value] += 1
            
            # Check for TLS with SNI
            if analysis.tls_info:
                print(f"   🔒 TLS: {analysis.tls_info.version}")
                if analysis.tls_info.sni_hostname:
                    print(f"   🌐 SNI: {analysis.tls_info.sni_hostname}")
                    role = ChannelRoleDetector.detect_role_from_sni(analysis.tls_info.sni_hostname)
                    if role:
                        print(f"   🎭 Role: {role}")
                        roles_detected.add(role)
                if analysis.tls_info.cipher_suites:
                    print(f"   🔐 Ciphers: {len(analysis.tls_info.cipher_suites)} offered")
                    print(f"       • {analysis.tls_info.cipher_suites[0]}")
                if not analysis.tls_info.compliance_ok:
                    print(f"   ⚠️  Compliance: {'; '.join(analysis.tls_info.compliance_issues)}")
            
            # Check for DNS
            if analysis.dns_info:
                print(f"   🌐 DNS: {'Query' if analysis.dns_info.is_query else 'Response'}")
                for q in analysis.dns_info.questions:
                    print(f"       • Query: {q['name']} ({q['type']})")
                for a in analysis.dns_info.answers:
                    print(f"       • Answer: {a['name']} -> {a['data']}")
            
            # Check for JSON
            if analysis.json_content:
                print(f"   📄 JSON: {len(analysis.json_content)} keys")
                key_fields = []
                for key in ['function', 'transactionId', 'resultCode']:
                    if key in analysis.json_content:
                        key_fields.append(f"{key}={analysis.json_content[key]}")
                if key_fields:
                    print(f"       • {', '.join(key_fields)}")
            
            # Check for ASN.1
            if analysis.asn1_structure:
                print(f"   📋 ASN.1: {len(analysis.asn1_structure)} structures")
                print(f"       • {analysis.asn1_structure[0]}")
            
            # Check for certificates
            if analysis.certificates:
                print(f"   🔐 Certificates: {len(analysis.certificates)}")
                for cert in analysis.certificates:
                    print(f"       • Subject: {cert.subject_cn}")
            
            # Channel role
            if analysis.channel_role:
                print(f"   🎯 Detected Role: {analysis.channel_role}")
                roles_detected.add(analysis.channel_role)
                
        except Exception as e:
            print(f"   ❌ Analysis failed: {e}")
            continue
    
    print("\n" + "=" * 60)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 60)
    
    print(f"🎭 Detected Channel Roles: {len(roles_detected)}")
    for role in sorted(roles_detected):
        print(f"   • {role}")
    
    print(f"\n🔬 Protocol Types Found:")
    for protocol, count in sorted(protocols_found.items()):
        print(f"   • {protocol}: {count} instances")
    
    # Check Channel Groups
    print(f"\n📋 Channel Groups Analysis:")
    try:
        channel_groups = parser.get_channel_groups()
        print(f"   • Total sessions: {len(channel_groups)}")
        
        servers = {}
        for group in channel_groups:
            server = group.get('server', 'Unknown')
            if server not in servers:
                servers[server] = 0
            servers[server] += 1
        
        print("   • Server distribution:")
        for server, count in sorted(servers.items()):
            print(f"     - {server}: {count} sessions")
            
    except Exception as e:
        print(f"   ❌ Channel groups analysis failed: {e}")
    
    print("\n🎉 Protocol analysis test completed!")
    print("\n💡 To see full analysis:")
    print("   1. Open the XTI viewer GUI")
    print("   2. Check 'Channel Groups' tab for auto-detected roles")  
    print("   3. Select SEND/RECEIVE DATA items in the trace")
    print("   4. View 'Analyze' tab for detailed protocol breakdown")

def extract_payload_from_apdu(parsed_apdu):
    """Extract payload from parsed APDU with improved TLV traversal"""
    try:
        # Look for payload data in TLV structure
        def search_tlv_recursively(tlvs, depth=0):
            if depth > 3:  # Prevent infinite recursion
                return None
            
            for tlv in tlvs:
                # Check if this TLV has raw data
                if hasattr(tlv, 'raw_value') and tlv.raw_value:
                    if len(tlv.raw_value) > 5:  # Minimum meaningful payload size
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
                    # Check if decoded_value looks like hex
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
        
        # Search through all TLVs recursively
        return search_tlv_recursively(parsed_apdu.tlvs)
        
    except Exception as e:
        print(f"   🐛 Payload extraction error: {e}")
        return None

def main():
    """Main test function"""
    file_path = "HL7812_fallback_NOK.xti"
    
    if not os.path.exists(file_path):
        print(f"❌ XTI file not found: {file_path}")
        print("Please ensure the file exists in the current directory.")
        return 1
    
    analyze_xti_file(file_path)
    return 0

if __name__ == "__main__":
    sys.exit(main())