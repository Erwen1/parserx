#!/usr/bin/env python3
"""
Test with the correct user's Open Channel response data.
"""

from xti_viewer.apdu_parser_construct import parse_ber_tlv

def test_correct_user_data():
    """Test with the actual Open Channel response from user's example."""
    # The hex bytes from the user's example (reconstructed correctly)
    response_lines = [
        "D0 41 81 03 01 43 01 82 02 81 21 05 00 36 34 01",
        "32 01 00 00 01 00 00 00 00 00 00 0C 65 69 6D 2D", 
        "64 65 6D 6F 2D 6C 61 62 02 65 75 03 74 61 63 0B",
        "74 68 61 6C 65 73 63 6C 6F 75 64 02 69 6F 00 00",
        "1C 00 01 90 00"
    ]
    
    # Join and clean up the hex string
    full_response = ''.join(''.join(line.split()) for line in response_lines)
    
    print("Analyzing correct Open Channel response data:")
    print(f"Full response: {full_response}")
    print()
    
    try:
        data = bytes.fromhex(full_response)
        
        # Skip the response header and SW (D041...9000)
        # TLV data starts after D041
        tlv_data = data[2:-2]  # Skip D041 at start and 9000 at end
        
        print(f"TLV portion: {tlv_data.hex().upper()}")
        print()
        
        tlvs = parse_ber_tlv(tlv_data)
        
        print("Parsed TLVs from Open Channel response:")
        print("=" * 70)
        
        for i, tlv in enumerate(tlvs, 1):
            print(f"{i:2d}. Tag 0x{tlv.tag:02X}: {tlv.name}")
            print(f"    Length: {tlv.length} bytes")
            print(f"    Raw hex: {tlv.value_hex}")
            print(f"    Decoded: {tlv.decoded_value}")
            print(f"    Offset: 0x{tlv.byte_offset:04X}")
            print()
        
        # Now look specifically for the tags user mentioned as "Unknown"
        print("Checking tags that should now be properly decoded:")
        print("=" * 70)
        
        # Tag 0x36 with length 0x34 = 52 bytes (Bearer Parameters)
        tag_36_tlvs = [tlv for tlv in tlvs if tlv.tag == 0x36]
        if tag_36_tlvs:
            tlv = tag_36_tlvs[0]
            print(f"✅ Tag 0x36 (Bearer Parameters): Found!")
            print(f"    Length: {tlv.length} bytes (should be 52)")
            print(f"    Was 'Unknown Tag', now shows: {tlv.name}")
            print(f"    Decoded: {tlv.decoded_value}")
            print()
            
            # Look for DNS names in this tag
            if tlv.length == 52:  # The 52-byte bearer parameters mentioned by user
                raw_value = bytes.fromhex(tlv.value_hex)
                ascii_parts = []
                for i in range(len(raw_value)):
                    if 32 <= raw_value[i] <= 126:
                        ascii_parts.append(chr(raw_value[i]))
                    else:
                        ascii_parts.append('.')
                ascii_repr = ''.join(ascii_parts)
                print(f"    ASCII representation: {ascii_repr}")
                
                # Check for the DNS names mentioned by user
                full_ascii = raw_value.decode('ascii', errors='ignore')
                if 'eim-demo-lab' in full_ascii:
                    print(f"    ✅ Found 'eim-demo-lab' in Bearer Parameters!")
                if 'thalescloud' in full_ascii:
                    print(f"    ✅ Found 'thalescloud' in Bearer Parameters!")
        else:
            print("❌ Tag 0x36 (Bearer Parameters) not found")
        
        print()
        
        # Look for other specific tags
        specific_tags = {
            0x30: "Channel Status", 
            0x31: "Buffer Size",
            0x32: "Network Access Name",
            0x0C: "Alpha Identifier"
        }
        
        for tag_num, tag_name in specific_tags.items():
            matching_tlvs = [tlv for tlv in tlvs if tlv.tag == tag_num]
            if matching_tlvs:
                for tlv in matching_tlvs:
                    print(f"✅ Tag 0x{tag_num:02X} ({tag_name}): {tlv.decoded_value}")
            else:
                print(f"❌ Tag 0x{tag_num:02X} ({tag_name}): Not found")
        
        print()
        print("Looking for DNS domain strings in all TLVs:")
        print("-" * 50)
        
        target_domains = ['eim-demo-lab.eu', 'tac.thalescloud.io']
        for tlv in tlvs:
            try:
                # Convert hex value to bytes and check for ASCII domains
                value_bytes = bytes.fromhex(tlv.value_hex)
                ascii_text = value_bytes.decode('ascii', errors='ignore')
                
                for domain in target_domains:
                    if domain.replace('.', '') in ascii_text.replace('.', ''):
                        print(f"✅ Found '{domain}' components in Tag 0x{tlv.tag:02X}")
                        print(f"    ASCII content: {ascii_text}")
            except:
                pass
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_correct_user_data()