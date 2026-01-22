#!/usr/bin/env python3
"""
Test the exact hex data from the user's Open Channel example.
"""

from xti_viewer.apdu_parser_construct import parse_ber_tlv

def test_user_hex_data():
    """Test the hex data from the Open Channel command response."""
    # User's response hex data (after the FETCH response header)
    response_hex = "D041810301400382028182050036010339020578040301003E0521080808083C030100351C0001"
    
    print("Analyzing user's Open Channel response data:")
    print(f"Raw hex: {response_hex}")
    print()
    
    try:
        # Skip the response header (D041) and parse the TLV data
        data = bytes.fromhex(response_hex)
        
        # The TLV data starts after D041 
        tlv_data = data[2:]  # Skip D041
        
        print(f"TLV data: {tlv_data.hex().upper()}")
        print()
        
        tlvs = parse_ber_tlv(tlv_data)
        
        print("Parsed TLVs:")
        print("-" * 60)
        
        for i, tlv in enumerate(tlvs, 1):
            print(f"{i:2d}. Tag 0x{tlv.tag:02X}: {tlv.name}")
            print(f"    Length: {tlv.length} bytes")
            print(f"    Raw value: {tlv.value_hex}")
            print(f"    Decoded: {tlv.decoded_value}")
            print(f"    Offset: 0x{tlv.byte_offset:04X}")
            print()
        
        # Check specific tags the user mentioned
        print("Checking for specific tags mentioned by user:")
        print("-" * 60)
        
        expected_tags = {
            0x36: "Bearer Parameters (was showing as Unknown)",
            0x30: "Channel Status (was showing as Unknown)", 
            0x31: "Buffer Size (was showing as Unknown)",
            0x32: "Network Access Name (was showing as Unknown)",
            0x0C: "Alpha Identifier (was showing as Alpha Tag)"
        }
        
        found_tags = {tlv.tag: tlv for tlv in tlvs}
        
        for tag, description in expected_tags.items():
            if tag in found_tags:
                tlv = found_tags[tag]
                print(f"✅ 0x{tag:02X}: {description}")
                print(f"    Now shows: {tlv.name} = {tlv.decoded_value}")
            else:
                print(f"❌ 0x{tag:02X}: {description} - NOT FOUND")
            print()
        
        # Look for the DNS names the user mentioned
        print("Looking for DNS names mentioned by user:")
        print("-" * 60)
        expected_domains = ["eim-demo-lab.eu", "tac.thalescloud.io"]
        
        for tlv in tlvs:
            for domain in expected_domains:
                if domain in str(tlv.decoded_value):
                    print(f"✅ Found '{domain}' in tag 0x{tlv.tag:02X}: {tlv.name}")
                    print(f"    Full value: {tlv.decoded_value}")
        
    except Exception as e:
        print(f"Error parsing TLV data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_user_hex_data()