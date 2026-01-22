import pytest
from xti_viewer.apdu_parser_construct import parse_ber_tlv


def make_tlv(tag: int, length_bytes: bytes, fill: int) -> bytes:
    return bytes([tag]) + length_bytes + bytes([fill]) * int.from_bytes(length_bytes if length_bytes[0] <= 0x7F else length_bytes[1:], 'big')


def test_short_form_length_7f():
    # Tag 0x01, length 0x7F (127), value = 0xAA * 127
    tlv = bytes([0x01, 0x7F]) + bytes([0xAA]) * 0x7F
    tlvs = parse_ber_tlv(tlv)
    assert len(tlvs) == 1
    assert tlvs[0].length == 0x7F
    assert len(bytes.fromhex(tlvs[0].value_hex)) == 0x7F


def test_long_form_0x81_128():
    # Tag 0x01, length 0x81 0x80 (128)
    tlv = bytes([0x01, 0x81, 0x80]) + bytes([0xBB]) * 0x80
    tlvs = parse_ber_tlv(tlv)
    assert len(tlvs) == 1
    assert tlvs[0].length == 0x80
    assert len(bytes.fromhex(tlvs[0].value_hex)) == 0x80


def test_long_form_0x82_300():
    # Tag 0x01, length 0x82 0x01 0x2C (300)
    tlv = bytes([0x01, 0x82, 0x01, 0x2C]) + bytes([0xCC]) * 300
    tlvs = parse_ber_tlv(tlv)
    assert len(tlvs) == 1
    assert tlvs[0].length == 300
    assert len(bytes.fromhex(tlvs[0].value_hex)) == 300
