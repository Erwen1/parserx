import pytest
from xti_viewer.apdu_parser_construct import parse_apdu


def flatten_tlvs(tlvs):
    for t in tlvs:
        yield t
        if getattr(t, "children", None):
            yield from flatten_tlvs(t.children)


def test_proactive_fetch_response_decodes_inner_tlvs():
    # Proactive command (FETCH response): D0 length ... followed by SW 9000
    s = "D01E8103014003820281820500350103390205783C030100353E0521080808089000"
    info = parse_apdu(s)
    # Expect SW and SIM Toolkit domain
    assert info.sw == 0x9000
    assert "SIM Toolkit" in info.domain
    # Ensure inner TLVs exist (Command Details 0x81 and Device Identity 0x82)
    tags = {t.tag for t in info.tlvs}
    assert 0x81 in tags
    assert 0x82 in tags


def test_aid_tag_84_is_labeled_aid():
    # Response containing FCI-like template (0x62) with AID 0x84; ends with SW 9000
    s = (
        "6243820278218410A0000000871002F230FF018907020000A50E8103000000820100"
        "830400023B1C8A01058B032F0602C60F9001B083018183010183010A83010B8102FFFF9000"
    )
    info = parse_apdu(s)
    # Top-level 0x62 should be recognized as FCP Template when wrapping AID/FCI
    top_62 = [t for t in info.tlvs if t.tag == 0x62]
    assert top_62, "Expected top-level 0x62 container present"
    assert top_62[0].name in ("FCP Template", "FCI Template"), top_62[0].name

    # Find any TLV with tag 0x84 and ensure name is 'AID'
    found = [(t.tag, t.name) for t in flatten_tlvs(info.tlvs) if t.tag == 0x84]
    assert found, "Expected TLV tag 0x84 present"
    assert all(name == "AID" for _, name in found)
