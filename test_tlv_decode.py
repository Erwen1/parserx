#!/usr/bin/env python3
"""
Quick test to verify TLV decoding improvements.
"""

from xti_viewer.apdu_parser_construct import parse_apdu

def test_open_channel_apdu():
    """Test the OPEN CHANNEL APDU from the user's example."""
    # User's example: FETCH command response with Bearer Parameters
    apdu_hex = "D0418103014003820281820500360103390205783C030100353E0521080808089000"
    
    print("Testing OPEN CHANNEL APDU decoding:")
    print(f"Raw hex: {apdu_hex}")
    print()
    
    result = parse_apdu(apdu_hex)
    
    print(f"Summary: {result.summary}")
    print(f"Command: {result.ins_name}")
    print(f"Domain: {result.domain}")
    print(f"Direction: {result.direction}")
    print()
    
    print("TLV Analysis:")
    for i, tlv in enumerate(result.tlvs):
        print(f"  {i+1:2d}. Tag {tlv.tag_hex}: {tlv.name}")
        print(f"      Length: {tlv.length}")
        print(f"      Value: {tlv.decoded_value}")
        print(f"      Offset: {tlv.byte_offset}")
        print()
    
    print("Key tags we're looking for:")
    tag_mapping = {
        0x30: "Channel Status",
        0x31: "Buffer Size", 
        0x32: "Network Access Name",
        0x36: "Bearer Parameters",
        0x0C: "Alpha Identifier"
    }
    
    found_tags = {tlv.tag for tlv in result.tlvs}
    for tag, expected_name in tag_mapping.items():
        if tag in found_tags:
            print(f"  ✅ Found {expected_name} (0x{tag:02X})")
        else:
            print(f"  ❌ Missing {expected_name} (0x{tag:02X})")


def test_simple_tlvs():
    """Test individual TLV tags."""
    print("\n" + "="*60)
    print("Testing individual TLV parsing:")
    
    test_cases = [
        # Tag 0x36 - Bearer Parameters  
        ("360403390278", "Bearer Parameters with data"),
        # Tag 0x30 - Channel Status
        ("30020001", "Channel Status"),
        # Tag 0x31 - Buffer Size
        ("31020100", "Buffer Size"),
        # Tag 0x0C - Alpha Identifier
        ("0C0C65696D2D64656D6F2D6C6162", "Alpha Identifier with text"),
        # Tag 0x32 - Network Access Name
        ("32087468616C6573636C6F7564", "Network Access Name")
    ]
    
    from xti_viewer.apdu_parser_construct import parse_ber_tlv
    
    for hex_data, description in test_cases:
        print(f"\nTesting {description}: {hex_data}")
        try:
            data = bytes.fromhex(hex_data)
            tlvs = parse_ber_tlv(data)
            
            for tlv in tlvs:
                print(f"  Tag {tlv.tag_hex}: {tlv.name}")
                print(f"  Decoded: {tlv.decoded_value}")
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    test_open_channel_apdu()
    test_simple_tlvs()