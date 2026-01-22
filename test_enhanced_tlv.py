#!/usr/bin/env python3
"""
Test enhanced TLV decoding.
"""

from xti_viewer.apdu_parser_construct import parse_apdu

def test_enhanced_decoding():
    """Test the enhanced TLV decoding."""
    # User's FETCH response data
    hex_data = "D01E8103014003820281820500350103390205783C030100353E0521080808089000"
    
    print("Enhanced TLV Decoding Test")
    print("=" * 50)
    
    result = parse_apdu(hex_data)
    
    print(f"Command: {result.ins_name}")
    print(f"Summary: {result.summary}")
    print(f"Status: {result.sw_description}")
    print()
    
    print("TLV Structure (Enhanced):")
    print("─" * 80)
    
    for i, tlv in enumerate(result.tlvs, 1):
        print(f"{i:2d}. Tag 0x{tlv.tag:02X}: {tlv.name}")
        print(f"    Length: {tlv.length} bytes")  
        print(f"    Value: {tlv.decoded_value}")
        print(f"    Offset: 0x{tlv.byte_offset:04X}")
        print()
    
    print("Expected Output Comparison:")
    print("─" * 40)
    expected = {
        0x81: "Number: 1, Type: 0x40 (OPEN CHANNEL), Qualifier: 0x03 → Immediate link establishment + Automatic reconnection",
        0x82: "Source: SIM (0x81), Destination: ME (0x82)",
        0x05: "(empty)",
        0x35: "0x03 → Default bearer for requested transport layer",
        0x39: "0x0578 → 1400 bytes", 
        0x3C: "Protocol: 0x01 → UDP, Port: 0x0035 → 53",
        0x3E: "Type: 0x21 → IPv4, IP: 8.8.8.8"
    }
    
    for tlv in result.tlvs:
        if tlv.tag in expected:
            expected_val = expected[tlv.tag]
            actual_val = tlv.decoded_value
            match = "✅" if expected_val in actual_val or actual_val in expected_val else "❌"
            print(f"{match} Tag 0x{tlv.tag:02X}: {tlv.name}")
            print(f"    Expected: {expected_val}")
            print(f"    Actual:   {actual_val}")
            print()


if __name__ == "__main__":
    test_enhanced_decoding()