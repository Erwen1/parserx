#!/usr/bin/env python3
"""
Test the improved response parsing logic directly.
"""

def test_response_parsing():
    """Test the response parsing with debug info."""
    from xti_viewer.apdu_parser_construct import create_apdu_schema, parse_ber_tlv
    
    hex_data = "D01E8103014003820281820500350103390205783C030100353E0521080808089000"
    data = bytes.fromhex(hex_data)
    
    print("Testing response parsing:")
    print(f"Data length: {len(data)} bytes")
    
    # Test the construct schema
    schemas = create_apdu_schema()
    if schemas is None:
        print("❌ Construct schemas not available")
        return
    
    print("✅ Construct schemas available")
    
    try:
        # Try parsing as response
        parsed_resp = schemas['response'].parse(data)
        print(f"✅ Response parsed successfully")
        print(f"SW: 0x{parsed_resp.sw:04X}")
        print(f"Data length: {len(parsed_resp.data)} bytes")
        
        # Check the data
        if parsed_resp.data:
            print(f"Data starts with: {' '.join(f'{b:02X}' for b in parsed_resp.data[:6])}")
            
            # Check if it's proactive command
            if len(parsed_resp.data) >= 2 and parsed_resp.data[0] == 0xD0:
                print("✅ Detected proactive command (D0 tag)")
                
                length_byte = parsed_resp.data[1]
                print(f"Length: {length_byte}")
                
                if length_byte <= len(parsed_resp.data) - 2:
                    proactive_tlv_data = parsed_resp.data[2:2+length_byte]
                    print(f"TLV data length: {len(proactive_tlv_data)}")
                    
                    # Parse TLVs
                    tlvs = parse_ber_tlv(proactive_tlv_data)
                    print(f"✅ Found {len(tlvs)} TLVs:")
                    
                    for i, tlv in enumerate(tlvs, 1):
                        print(f"  {i}. Tag 0x{tlv.tag:02X}: {tlv.name}")
                        if tlv.tag == 0x3E:  # Network Access Name
                            print(f"      🎯 Network Access Name: {tlv.decoded_value}")
                        elif tlv.tag in [0x01, 0x81]:  # Command Details
                            print(f"      📋 Command Details: {tlv.decoded_value}")
                else:
                    print("❌ Invalid length byte")
            else:
                print("❌ Not a proactive command")
        else:
            print("❌ No data in response")
    
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_response_parsing()