"""Test exactly what the UI shows for protocol analysis."""

from xti_viewer.xti_parser import XTIParser
from xti_viewer.apdu_parser_construct import parse_apdu
from xti_viewer.protocol_analyzer import ProtocolAnalyzer

def extract_payload_like_ui(parsed_apdu):
    """Extract payload exactly like the UI does."""
    def search_tlv_recursively(tlvs, depth=0):
        if depth > 3 or not tlvs:
            return None
        
        for tlv in tlvs:
            # Try raw_value attribute first
            if hasattr(tlv, 'raw_value') and tlv.raw_value and len(tlv.raw_value) > 5:
                return tlv.raw_value
            
            # Try value_hex attribute
            if hasattr(tlv, 'value_hex') and tlv.value_hex:
                try:
                    raw_data = bytes.fromhex(tlv.value_hex.replace(' ', ''))
                    if len(raw_data) > 5:
                        return raw_data
                except:
                    pass
            
            # Try decoded_value attribute
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
            
            # Search in children recursively
            if hasattr(tlv, 'children') and tlv.children:
                result = search_tlv_recursively(tlv.children, depth + 1)
                if result:
                    return result
        
        return None
    
    return search_tlv_recursively(parsed_apdu.tlvs)

def is_send_receive_data(parsed_apdu, trace_item):
    """Check if this is SEND/RECEIVE DATA like the UI does."""
    return ("SEND DATA" in parsed_apdu.ins_name or 
            "RECEIVE DATA" in parsed_apdu.ins_name or
            "send data" in trace_item.summary.lower() or
            "receive data" in trace_item.summary.lower())

def test_ui_display():
    """Test what the UI actually displays."""
    
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    print("="*80)
    print("TESTING ACTUAL UI DISPLAY FOR PROTOCOL ANALYSIS")
    print("="*80)
    
    # Test specific items we know should have protocol data
    test_items = [
        (29, "DNS Query"),
        (46, "DNS Response"),
        (74, "TLS ServerHello"),
        (114, "TLS Application Data"),
    ]
    
    for item_idx, expected_type in test_items:
        if item_idx >= len(trace_items):
            continue
        
        item = trace_items[item_idx]
        
        print(f"\n{'='*80}")
        print(f"TESTING ITEM #{item_idx + 1}: {expected_type}")
        print(f"{'='*80}")
        print(f"Summary: {item.summary}")
        print(f"Time: {item.timestamp}")
        
        try:
            # Parse APDU
            parsed = parse_apdu(item.rawhex)
            print(f"\nParsed APDU:")
            print(f"  INS Name: {parsed.ins_name}")
            print(f"  Command Type: {parsed.command_type}")
            
            # Check if SEND/RECEIVE DATA
            is_data_cmd = is_send_receive_data(parsed, item)
            print(f"  Is SEND/RECEIVE DATA: {is_data_cmd}")
            
            if is_data_cmd:
                # Extract payload like UI does
                payload = extract_payload_like_ui(parsed)
                
                if payload:
                    print(f"\nPayload Extracted: {len(payload)} bytes")
                    print(f"First 40 bytes (hex): {payload[:40].hex()}")
                    
                    # Analyze like UI does
                    channel_info = {}
                    analysis = ProtocolAnalyzer.analyze_payload(payload, channel_info)
                    
                    print(f"\n{'*'*80}")
                    print("WHAT THE UI WOULD SHOW:")
                    print(f"{'*'*80}")
                    
                    # Quick Summary section
                    summary_text = parsed.summary
                    if analysis.tls_info:
                        tls = analysis.tls_info
                        summary_text += f" | TLS {tls.handshake_type} ({tls.version})"
                        if tls.sni_hostname:
                            summary_text += f" | SNI: {tls.sni_hostname}"
                    elif analysis.dns_info:
                        dns = analysis.dns_info
                        qtype = "Query" if dns.is_query else "Response"
                        summary_text += f" | DNS {qtype}"
                        if dns.questions:
                            summary_text += f" | {dns.questions[0]['name']}"
                    elif analysis.json_content:
                        summary_text += f" | JSON Message"
                    elif analysis.asn1_structure:
                        summary_text += f" | ASN.1/BER Structure"
                    else:
                        summary_text += f" | {analysis.raw_classification}"
                    
                    if analysis.channel_role:
                        summary_text += f" | Role: {analysis.channel_role}"
                    
                    print(f"\nQUICK SUMMARY:")
                    print(f"  {summary_text}")
                    
                    # Command card
                    cmd_text = f"{parsed.ins_name} (0x{parsed.ins:02X})"
                    if analysis.tls_info:
                        tls = analysis.tls_info
                        cmd_text += f" • {tls.handshake_type} ({tls.version})"
                        if tls.cipher_suites:
                            cmd_text += f" • {len(tls.cipher_suites)} cipher suites"
                    elif analysis.dns_info:
                        dns = analysis.dns_info
                        qtype = "DNS Query" if dns.is_query else "DNS Response"
                        cmd_text += f" • {qtype}"
                        if dns.questions:
                            cmd_text += f" • {len(dns.questions)} question(s)"
                        if dns.answers:
                            cmd_text += f" • {len(dns.answers)} answer(s)"
                    
                    print(f"\nCOMMAND CARD:")
                    print(f"  {cmd_text}")
                    
                    # Key TLVs card
                    tlv_parts = []
                    if analysis.tls_info and analysis.tls_info.sni_hostname:
                        tlv_parts.append(f"SNI: {analysis.tls_info.sni_hostname}")
                    elif analysis.dns_info:
                        dns = analysis.dns_info
                        if dns.questions:
                            qname = dns.questions[0]['name']
                            if len(qname) > 30:
                                qname = qname[:27] + "..."
                            tlv_parts.append(f"QNAME: {qname}")
                        if dns.answers and not dns.is_query:
                            tlv_parts.append(f"{len(dns.answers)} answer(s)")
                    
                    if tlv_parts:
                        print(f"\nKEY TLVs CARD:")
                        print(f"  {' • '.join(tlv_parts)}")
                    
                    # Protocol Analysis Tree
                    print(f"\nPROTOCOL ANALYSIS TREE:")
                    if analysis.tls_info:
                        tls = analysis.tls_info
                        print(f"  [PROTOCOL] Protocol Analysis")
                        print(f"    [TLS] TLS Handshake - Version: {tls.version}")
                        if tls.sni_hostname:
                            print(f"      [SNI] Server Name Indication: {tls.sni_hostname}")
                        if tls.cipher_suites:
                            print(f"      [CIPHERS] Cipher Suites: {len(tls.cipher_suites)} suites")
                            for cipher in tls.cipher_suites[:3]:
                                print(f"        - {cipher}")
                        if tls.extensions:
                            print(f"      [EXT] Extensions: {len(tls.extensions)} extensions")
                    
                    elif analysis.dns_info:
                        dns = analysis.dns_info
                        print(f"  [PROTOCOL] Protocol Analysis")
                        qtype = "Query" if dns.is_query else "Response"
                        print(f"    [DNS] DNS Message - {qtype} (ID: 0x{dns.transaction_id:04X})")
                        for q in dns.questions:
                            print(f"      [Q] Question: {q['name']} ({q['type']})")
                        for ans in dns.answers:
                            print(f"      [A] Answer ({ans['type']}): {ans['name']} -> {ans['data']}")
                    
                    elif analysis.asn1_structure:
                        print(f"  [PROTOCOL] Protocol Analysis")
                        print(f"    [ASN1] ASN.1/BER Structure - {len(analysis.asn1_structure)} tags")
                    
                    if analysis.channel_role:
                        print(f"      [ROLE] Channel Role: {analysis.channel_role}")
                    
                else:
                    print("\n[WARNING] No payload extracted by UI method")
            else:
                print("\n[INFO] Not a SEND/RECEIVE DATA command")
                
        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_ui_display()
