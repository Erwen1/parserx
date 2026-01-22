"""Comprehensive test of all protocol analysis features in the UI."""

from xti_viewer.xti_parser import XTIParser
from xti_viewer.apdu_parser_construct import parse_apdu
from xti_viewer.protocol_analyzer import ProtocolAnalyzer

def extract_payload_like_ui(parsed_apdu):
    """Extract payload exactly like UI does - recursive TLV search."""
    def search_tlv_recursively(tlvs, depth=0):
        if depth > 3 or not tlvs:
            return None
        
        for tlv in tlvs:
            # Try raw_value
            if hasattr(tlv, 'raw_value') and tlv.raw_value and len(tlv.raw_value) > 5:
                return tlv.raw_value
            
            # Try value_hex
            if hasattr(tlv, 'value_hex') and tlv.value_hex:
                try:
                    raw_data = bytes.fromhex(tlv.value_hex.replace(' ', ''))
                    if len(raw_data) > 5:
                        return raw_data
                except:
                    pass
            
            # Try decoded_value
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

def test_all_features():
    """Test all protocol analysis features."""
    
    print("="*80)
    print("COMPREHENSIVE PROTOCOL ANALYSIS TEST")
    print("="*80)
    
    parser = XTIParser()
    trace_items = parser.parse_file("HL7812_fallback_NOK.xti")
    
    print(f"\n[INFO] Loaded {len(trace_items)} trace items")
    
    # Test cases: known items with specific protocol types
    test_cases = [
        {"idx": 29, "type": "DNS Query", "expect": "eim-demo-lab"},
        {"idx": 46, "type": "DNS Response", "expect": "IP addresses"},
        {"idx": 74, "type": "TLS ServerHello", "expect": "TLS 1.2"},
        {"idx": 114, "type": "TLS Application Data", "expect": "encrypted"},
    ]
    
    results = {
        "payload_extraction": 0,
        "protocol_detection": 0,
        "bip_stripping": 0,
        "role_detection": 0,
        "total_tests": len(test_cases)
    }
    
    for test in test_cases:
        idx = test["idx"]
        expected_type = test["type"]
        
        print(f"\n{'='*80}")
        print(f"TEST: Item #{idx + 1} - Expected: {expected_type}")
        print(f"{'='*80}")
        
        if idx >= len(trace_items):
            print("[SKIP] Item index out of range")
            continue
        
        item = trace_items[idx]
        print(f"Summary: {item.summary}")
        print(f"Time: {item.timestamp}")
        
        try:
            # Parse APDU
            parsed = parse_apdu(item.rawhex)
            print(f"\n[APDU] INS: {parsed.ins_name}, TLVs: {len(parsed.tlvs)}")
            
            # TEST 1: Payload Extraction from Nested TLVs
            print(f"\n[TEST 1] PAYLOAD EXTRACTION FROM NESTED TLVs")
            print("-" * 80)
            payload = extract_payload_like_ui(parsed)
            
            if payload:
                print(f"[PASS] Extracted {len(payload)} bytes")
                print(f"       First 32 bytes: {payload[:32].hex()}")
                results["payload_extraction"] += 1
                
                # Check for BIP wrapper pattern
                if len(payload) > 12:
                    if payload[0:2] == b'\x02\x03':
                        print(f"[INFO] Detected BIP header pattern: {payload[:4].hex()}")
                    elif payload[0:1] in [b'\x16', b'\x17', b'\x14', b'\x15']:
                        print(f"[INFO] Detected TLS record type: 0x{payload[0]:02x}")
                    else:
                        print(f"[INFO] Unknown wrapper, first bytes: {payload[:4].hex()}")
            else:
                print(f"[FAIL] No payload extracted")
                continue
            
            # TEST 2: Protocol Detection Accuracy
            print(f"\n[TEST 2] PROTOCOL DETECTION ACCURACY")
            print("-" * 80)
            
            channel_info = {}
            analysis = ProtocolAnalyzer.analyze_payload(payload, channel_info)
            
            print(f"Detected Type: {analysis.payload_type}")
            print(f"Classification: {analysis.raw_classification}")
            
            # Check if detection matches expected type
            detected_correctly = False
            if "DNS" in expected_type and analysis.dns_info:
                detected_correctly = True
                print(f"[PASS] DNS detected correctly")
                results["protocol_detection"] += 1
                
                dns = analysis.dns_info
                print(f"       Transaction ID: 0x{dns.transaction_id:04x}")
                print(f"       Is Query: {dns.is_query}")
                print(f"       Questions: {len(dns.questions)}")
                print(f"       Answers: {len(dns.answers)}")
                
                if dns.questions:
                    for q in dns.questions:
                        print(f"       - QNAME: {q['name']} ({q['type']})")
                if dns.answers:
                    for a in dns.answers[:3]:
                        print(f"       - Answer: {a['name']} -> {a['data']} (TTL: {a['ttl']})")
                
            elif "TLS" in expected_type and analysis.tls_info:
                detected_correctly = True
                print(f"[PASS] TLS detected correctly")
                results["protocol_detection"] += 1
                
                tls = analysis.tls_info
                print(f"       Handshake Type: {tls.handshake_type}")
                print(f"       Version: {tls.version}")
                if tls.sni_hostname:
                    print(f"       SNI: {tls.sni_hostname}")
                if tls.cipher_suites:
                    print(f"       Cipher Suites: {len(tls.cipher_suites)}")
                    for cipher in tls.cipher_suites[:3]:
                        print(f"       - {cipher}")
                        
            elif "TLS" in expected_type and analysis.payload_type.name.startswith("TLS"):
                detected_correctly = True
                print(f"[PASS] TLS record type detected")
                results["protocol_detection"] += 1
                
            else:
                print(f"[FAIL] Expected {expected_type}, got {analysis.payload_type}")
            
            # TEST 3: BIP Header Stripping
            print(f"\n[TEST 3] BIP HEADER STRIPPING")
            print("-" * 80)
            
            # Check if BIP wrapper was properly handled
            if payload[0:2] == b'\x02\x03':
                print(f"[INFO] BIP wrapper present in raw payload")
                
                # Check if protocol was still detected (meaning wrapper was stripped)
                if detected_correctly:
                    print(f"[PASS] BIP wrapper was stripped, protocol detected")
                    results["bip_stripping"] += 1
                else:
                    print(f"[FAIL] BIP wrapper not stripped properly")
            else:
                print(f"[INFO] No BIP wrapper detected (direct protocol data)")
                if detected_correctly:
                    results["bip_stripping"] += 1
            
            # TEST 4: Channel Role Detection
            print(f"\n[TEST 4] CHANNEL ROLE DETECTION")
            print("-" * 80)
            
            if analysis.channel_role:
                print(f"[PASS] Role detected: {analysis.channel_role}")
                results["role_detection"] += 1
                
                # Verify role makes sense
                expected_role = "eIM" if "eim" in test.get("expect", "").lower() else None
                if expected_role and analysis.channel_role == expected_role:
                    print(f"[PASS] Role matches expected: {expected_role}")
            else:
                print(f"[WARN] No role detected")
                
                # Check if hostname was found (role should be detectable)
                if analysis.dns_info and analysis.dns_info.questions:
                    hostname = analysis.dns_info.questions[0].get('name', '')
                    print(f"[INFO] Hostname found: {hostname}")
                    if 'eim' in hostname.lower():
                        print(f"[FAIL] Should have detected eIM role from hostname")
                elif analysis.tls_info and analysis.tls_info.sni_hostname:
                    print(f"[INFO] SNI found: {analysis.tls_info.sni_hostname}")
                    if 'eim' in analysis.tls_info.sni_hostname.lower():
                        print(f"[FAIL] Should have detected eIM role from SNI")
                else:
                    print(f"[INFO] No hostname/SNI available for role detection")
                    results["role_detection"] += 1  # Not applicable
            
            print(f"\n" + "="*80)
            print(f"ITEM SUMMARY:")
            print(f"  Payload Extraction: {'PASS' if payload else 'FAIL'}")
            print(f"  Protocol Detection: {'PASS' if detected_correctly else 'FAIL'}")
            print(f"  Role Detection: {'PASS' if analysis.channel_role else 'N/A'}")
            
        except Exception as e:
            print(f"\n[ERROR] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
    
    # Final Results
    print(f"\n")
    print(f"{'='*80}")
    print(f"FINAL TEST RESULTS")
    print(f"{'='*80}")
    print(f"")
    print(f"1. Payload Extraction from Nested TLVs: {results['payload_extraction']}/{results['total_tests']} PASS")
    print(f"2. Protocol Detection Accuracy:          {results['protocol_detection']}/{results['total_tests']} PASS")
    print(f"3. BIP Header Stripping:                 {results['bip_stripping']}/{results['total_tests']} PASS")
    print(f"4. Channel Role Detection:               {results['role_detection']}/{results['total_tests']} PASS")
    print(f"")
    
    total_passed = sum([results['payload_extraction'], results['protocol_detection'], 
                       results['bip_stripping'], results['role_detection']])
    total_possible = results['total_tests'] * 4
    
    percentage = (total_passed / total_possible * 100) if total_possible > 0 else 0
    
    print(f"Overall Score: {total_passed}/{total_possible} ({percentage:.1f}%)")
    print(f"")
    
    if percentage >= 75:
        print(f"[SUCCESS] Protocol analysis is working well!")
    elif percentage >= 50:
        print(f"[WARNING] Some issues detected, review failures above")
    else:
        print(f"[CRITICAL] Major issues detected, protocol analysis needs fixes")
    
    print(f"{'='*80}")

if __name__ == "__main__":
    test_all_features()
