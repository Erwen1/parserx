"""Test what the UI ACTUALLY shows when you click on items."""

from xti_viewer.xti_parser import XTIParser
from xti_viewer.apdu_parser_construct import parse_apdu
from xti_viewer.protocol_analyzer import ProtocolAnalyzer

def extract_payload_ui_method(parsed_apdu):
    """Exact UI payload extraction."""
    def search_tlv_recursively(tlvs, depth=0):
        if depth > 3 or not tlvs:
            return None
        
        for tlv in tlvs:
            if hasattr(tlv, 'raw_value') and tlv.raw_value and len(tlv.raw_value) > 5:
                return tlv.raw_value
            
            if hasattr(tlv, 'value_hex') and tlv.value_hex:
                try:
                    raw_data = bytes.fromhex(tlv.value_hex.replace(' ', ''))
                    if len(raw_data) > 5:
                        return raw_data
                except:
                    pass
            
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
            
            if hasattr(tlv, 'children') and tlv.children:
                result = search_tlv_recursively(tlv.children, depth + 1)
                if result:
                    return result
        
        return None
    
    return search_tlv_recursively(parsed_apdu.tlvs)

def is_send_receive_data(parsed_apdu, trace_item):
    """Check if SEND/RECEIVE DATA like UI does."""
    return ("SEND DATA" in parsed_apdu.ins_name or 
            "RECEIVE DATA" in parsed_apdu.ins_name or
            "send data" in trace_item.summary.lower() or
            "receive data" in trace_item.summary.lower())

def simulate_ui_click(item_index):
    """Simulate clicking on an item in the UI."""
    
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    if item_index >= len(trace_items):
        print(f"[ERROR] Item {item_index} out of range")
        return
    
    item = trace_items[item_index]
    
    print("="*80)
    print(f"SIMULATING UI CLICK ON ITEM #{item_index + 1}")
    print("="*80)
    print(f"Summary: {item.summary}")
    print(f"Time: {item.timestamp}\n")
    
    try:
        # Parse APDU (what update_analyze_view does)
        parsed = parse_apdu(item.rawhex)
        
        # Check if SEND/RECEIVE DATA
        if not is_send_receive_data(parsed, item):
            print("[INFO] Not a SEND/RECEIVE DATA command - no protocol analysis")
            return
        
        # Extract payload
        payload = extract_payload_ui_method(parsed)
        
        if not payload:
            print("[INFO] No payload extracted - no protocol analysis")
            return
        
        print(f"[PAYLOAD] Extracted {len(payload)} bytes")
        print(f"          First 40 bytes: {payload[:40].hex()}\n")
        
        # Analyze payload
        channel_info = {}
        analysis = ProtocolAnalyzer.analyze_payload(payload, channel_info)
        
        # === WHAT THE UI SHOWS ===
        
        print("+"*80)
        print("WHAT YOU SEE IN THE UI:")
        print("+"*80)
        
        # 1. QUICK SUMMARY (top banner)
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
        
        print("\n[QUICK SUMMARY]")
        print(f"{summary_text}\n")
        
        # 2. COMMAND CARD
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
        
        print("[COMMAND CARD]")
        print(f"Command: {cmd_text}\n")
        
        # 3. KEY TLVs CARD
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
            print("[KEY TLVs CARD]")
            print(f"Key TLVs: {' • '.join(tlv_parts)}\n")
        
        # 4. DIRECTION CARD
        direction_text = parsed.direction
        if analysis.channel_role:
            direction_text += f" ({analysis.channel_role})"
        
        print(f"[DIRECTION CARD]")
        print(f"Direction: {direction_text}\n")
        
        # 5. PROTOCOL ANALYSIS TREE (in TLV Structure section)
        print("[PROTOCOL ANALYSIS TREE]")
        print("TLV Structure:")
        print("  ...")
        print("  [PROTOCOL] Protocol Analysis")
        print(f"             Classification: {analysis.raw_classification}")
        
        if analysis.tls_info:
            tls = analysis.tls_info
            print(f"    [TLS] TLS Handshake")
            print(f"          Version: {tls.version}")
            if tls.sni_hostname:
                print(f"      [SNI] Server Name Indication")
                print(f"            {tls.sni_hostname}")
            if tls.cipher_suites:
                print(f"      [CIPHERS] Cipher Suites ({len(tls.cipher_suites)} suites)")
                for cipher in tls.cipher_suites[:3]:
                    print(f"                {cipher}")
            if tls.extensions:
                print(f"      [EXT] Extensions ({len(tls.extensions)} extensions)")
                print(f"            {', '.join(tls.extensions[:5])}")
        
        if analysis.dns_info:
            dns = analysis.dns_info
            qtype = "Query" if dns.is_query else "Response"
            print(f"    [DNS] DNS Message")
            print(f"          {qtype} (ID: 0x{dns.transaction_id:04X})")
            
            for q in dns.questions:
                print(f"      [Q] Question")
                print(f"          {q['name']} ({q['type']})")
            
            for ans in dns.answers[:3]:
                print(f"      [A] Answer ({ans['type']})")
                print(f"          {ans['name']} -> {str(ans['data'])[:50]}...")
                print(f"          TTL: {ans['ttl']}")
        
        if analysis.asn1_structure:
            print(f"    [ASN1] ASN.1/BER Structure")
            print(f"           {len(analysis.asn1_structure)} tags")
            for tag in analysis.asn1_structure[:3]:
                print(f"           - {tag}")
        
        if analysis.channel_role:
            print(f"      [ROLE] Channel Role")
            print(f"             {analysis.channel_role}")
        
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

def main():
    """Test key items."""
    print("\n")
    print("#"*80)
    print("# TESTING ACTUAL UI DISPLAY FOR KEY PROTOCOL ITEMS")
    print("#"*80)
    print("\n")
    
    # Test DNS Query
    print("\n")
    simulate_ui_click(29)  # DNS Query
    
    # Test DNS Response
    print("\n")
    simulate_ui_click(46)  # DNS Response
    
    # Test TLS
    print("\n")
    simulate_ui_click(74)  # TLS ServerHello
    
    # Test TLS Change Cipher Spec (the one that was failing)
    print("\n")
    simulate_ui_click(114)  # TLS Change Cipher Spec
    
    print("\n")
    print("#"*80)
    print("# TEST COMPLETE")
    print("#"*80)

if __name__ == "__main__":
    main()
