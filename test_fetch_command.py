#!/usr/bin/env python3
"""
Test FETCH command parsing from the user's specific hex.
"""

from xti_viewer.apdu_parser_construct import parse_apdu

def test_fetch_command():
    """Test the FETCH command from user's example."""
    # User's FETCH command: → 00000000  80 12 00 00 20
    fetch_hex = "8012000020"
    
    print("Testing FETCH Command:")
    print(f"Hex: {fetch_hex}")
    print()
    
    result = parse_apdu(fetch_hex)
    
    print(f"Summary: {result.summary}")
    print(f"Command: {result.ins_name}")
    print(f"Direction: {result.direction}")
    print(f"Domain: {result.domain}")
    print(f"CLA: 0x{result.cla:02X}")
    print(f"INS: 0x{result.ins:02X}")
    print(f"P1: 0x{result.p1:02X}")
    print(f"P2: 0x{result.p2:02X}")
    print(f"Le: {result.le}")
    print()
    
    print("TLVs found:")
    if result.tlvs:
        for i, tlv in enumerate(result.tlvs, 1):
            print(f"  {i}. Tag 0x{tlv.tag:02X}: {tlv.name}")
            print(f"     Length: {tlv.length}")
            print(f"     Value: {tlv.decoded_value}")
    else:
        print("  (No TLVs - this is expected for a FETCH command)")


def test_fetch_response():
    """Test the FETCH response from user's example."""
    # User's FETCH response: ← D0 1E 81 03 01 40 03 82 02 81 82 05 00 35 01 03 39 02 05 78 3C 03 01 00 35 3E 05 21 08 08 08 08 90 00
    response_hex = "D01E8103014003820281820500350103390205783C030100353E0521080808089000"
    
    print("\n" + "="*60)
    print("Testing FETCH Response:")
    print(f"Hex: {response_hex}")
    print()
    
    result = parse_apdu(response_hex)
    
    print(f"Summary: {result.summary}")
    print(f"Command: {result.ins_name}")
    print(f"Direction: {result.direction}")
    print(f"Domain: {result.domain}")
    print(f"SW: 0x{result.sw:04X} ({result.sw_description})")
    print()
    
    print("TLVs found:")
    if result.tlvs:
        for i, tlv in enumerate(result.tlvs, 1):
            print(f"  {i:2d}. Tag 0x{tlv.tag:02X}: {tlv.name}")
            print(f"      Length: {tlv.length} bytes")
            print(f"      Decoded: {tlv.decoded_value}")
            print(f"      Raw: {tlv.value_hex}")
            print()
    else:
        print("  No TLVs found")


if __name__ == "__main__":
    test_fetch_command()
    test_fetch_response()