#!/usr/bin/env python3
"""
Debug the FETCH response parsing step by step.
"""

def debug_apdu_parsing():
    """Debug the parsing step by step."""
    hex_data = "D01E8103014003820281820500350103390205783C030100353E0521080808089000"
    
    print("Debugging APDU parsing:")
    print(f"Hex: {hex_data}")
    print(f"Length: {len(hex_data)//2} bytes")
    
    data = bytes.fromhex(hex_data)
    print(f"First few bytes: {' '.join(f'{b:02X}' for b in data[:10])}")
    print(f"Last few bytes: {' '.join(f'{b:02X}' for b in data[-6:])}")
    
    # Check if last 2 bytes are status word
    sw = (data[-2] << 8) | data[-1]
    print(f"Last 2 bytes as SW: 0x{sw:04X}")
    
    # Check the structure
    if len(data) >= 2:
        # Try parsing as response
        response_data = data[:-2]  # All except SW
        print(f"Response data (without SW): {' '.join(f'{b:02X}' for b in response_data[:10])}...")
        
        # Check if it starts with D0 (proactive command tag)
        if response_data[0] == 0xD0:
            length = response_data[1]
            print(f"D0 tag found, length: {length}")
            
            if length <= len(response_data) - 2:
                tlv_data = response_data[2:2+length]
                print(f"TLV data: {' '.join(f'{b:02X}' for b in tlv_data[:10])}...")
                
                # Try parsing TLVs
                try:
                    from xti_viewer.apdu_parser_construct import parse_ber_tlv
                    tlvs = parse_ber_tlv(tlv_data)
                    print(f"✅ Found {len(tlvs)} TLVs:")
                    for i, tlv in enumerate(tlvs[:5], 1):
                        print(f"  {i}. Tag 0x{tlv.tag:02X}: {tlv.name} (len: {tlv.length})")
                        if tlv.tag == 0x3E:  # Network Access Name
                            print(f"      💡 This is the Network Access Name: {tlv.decoded_value}")
                except Exception as e:
                    print(f"❌ TLV parsing failed: {e}")
        else:
            print("Not a proactive command (doesn't start with D0)")


if __name__ == "__main__":
    debug_apdu_parsing()