"""Debug why protocol analysis isn't showing in UI."""

from xti_viewer.xti_parser import XTIParser
from xti_viewer.apdu_parser_construct import parse_apdu
from xti_viewer.protocol_analyzer import ProtocolAnalyzer

def test_send_data_item():
    """Test protocol analysis on a SEND DATA item."""
    
    # Parse the XTI file
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    print(f"[OK] Loaded {len(trace_items)} trace items\n")
    
    # Find SEND DATA or RECEIVE DATA items
    send_receive_items = []
    for item in trace_items:
        if "SEND DATA" in item.summary or "RECEIVE DATA" in item.summary:
            send_receive_items.append(item)
    
    print(f"[DATA] Found {len(send_receive_items)} SEND/RECEIVE DATA items\n")
    
    # Test the first few
    for i, item in enumerate(send_receive_items[:5]):
        print(f"{'='*60}")
        print(f"Item #{i}: {item.summary}")
        print(f"Time: {item.timestamp}")
        print(f"Raw hex length: {len(item.rawhex)}")
        
        try:
            # Parse APDU
            parsed = parse_apdu(item.rawhex)
            print(f"[OK] APDU parsed successfully")
            print(f"   INS Name: {parsed.ins_name}")
            print(f"   Command Type: {parsed.command_type}")
            print(f"   TLVs found: {len(parsed.tlvs)}")
            
            # Check if this is SEND/RECEIVE DATA
            is_send_receive = ("SEND DATA" in parsed.ins_name or 
                             "RECEIVE DATA" in parsed.ins_name or
                             "send data" in item.summary.lower() or
                             "receive data" in item.summary.lower())
            
            print(f"   Is SEND/RECEIVE DATA: {is_send_receive}")
            
            if is_send_receive and parsed.tlvs:
                print(f"\n   [TLV] Structure:")
                for j, tlv in enumerate(parsed.tlvs):
                    print(f"      TLV {j}: Tag={tlv.tag_hex}, Name={tlv.name}, Len={tlv.length}")
                    print(f"              Value hex (first 40 chars): {tlv.value_hex[:40] if tlv.value_hex else 'None'}")
                    
                    # Try to extract payload
                    if tlv.value_hex and len(tlv.value_hex) > 20:
                        payload_bytes = bytes.fromhex(tlv.value_hex)
                        print(f"              [OK] Found payload: {len(payload_bytes)} bytes")
                        
                        # Try protocol analysis
                        channel_info = {}
                        analysis = ProtocolAnalyzer.analyze_payload(payload_bytes, channel_info)
                        
                        print(f"\n   [ANALYSIS] Protocol Analysis:")
                        print(f"      Classification: {analysis.raw_classification}")
                        print(f"      Payload Type: {analysis.payload_type}")
                        if analysis.tls_info:
                            print(f"      TLS Version: {analysis.tls_info.version}")
                            print(f"      TLS SNI: {analysis.tls_info.sni_hostname}")
                        if analysis.dns_info:
                            print(f"      DNS Type: {'Query' if analysis.dns_info.is_query else 'Response'}")
                            print(f"      DNS Questions: {analysis.dns_info.questions}")
                        if analysis.channel_role:
                            print(f"      Channel Role: {analysis.channel_role}")
                    
                    # Check children
                    if tlv.children:
                        print(f"              Has {len(tlv.children)} children")
                        for k, child in enumerate(tlv.children):
                            print(f"                 Child {k}: Tag={child.tag_hex}, Name={child.name}, Len={child.length}")
                            if child.value_hex and len(child.value_hex) > 20:
                                print(f"                          [OK] Child has payload: {len(child.value_hex)//2} bytes")
        
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        print()

if __name__ == "__main__":
    test_send_data_item()
