import os
import sys

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xti_viewer.apdu_parser_construct import parse_apdu


def test_parse_apdu_proactive_command_d0_long_length_includes_payload_tlv():
    # Representative FETCH response from traces.xti (contains: D0 81 8E ... 36 81 80 16 03 03 ...)
    rawhex = (
        "D0818E"
        "8103014301"
        "82028121"
        "0500"
        "368180"
        "160303007B010000770303B7AF1C4FA65921FC03BB33BB3ED61F9041BBF95AC4125C38A89A6C8873B65C3C"
        "00000800AEC02B008C008B01000046000100010100000027002500002265696D2D64656D6F2D6C61622E65752E7461632E7468616C6573636C6F75642E696F"
        "000A000400020017000B00020100000D000400020403"
        "9000"
    )

    ap = parse_apdu(rawhex)

    assert ap.command_type == "Proactive Command Response"
    assert ap.ins_name == "FETCH RESPONSE"
    tags = [t.tag for t in ap.tlvs]

    # Should see Command Details (0x81) and the payload container (0x36) at minimum.
    assert 0x81 in tags
    assert 0x36 in tags

    # And the 0x36 value should begin with a TLS record header.
    payload_tlv = next(t for t in ap.tlvs if t.tag == 0x36)
    b = bytes.fromhex((payload_tlv.value_hex or ""))
    assert b[:3] == bytes.fromhex("160303")
