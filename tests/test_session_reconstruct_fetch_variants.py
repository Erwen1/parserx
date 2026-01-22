import os
import sys

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xti_viewer.xti_parser import XTIParser, TraceItem, TreeNode


def _node(text: str) -> TreeNode:
    n = TreeNode(text)
    return n


def test_reconstruct_sessions_accepts_fetch_fetch_variants():
    parser = XTIParser()

    # Minimal tree content to allow IP extraction without failing.
    details = _node("Address: 13.38.212.83")

    items = [
        TraceItem(protocol="ISO7816", type="apducommand", summary="FETCH", rawhex="8012000020", timestamp="", details_tree=_node("")),
        TraceItem(protocol="ISO7816", type="apduresponse", summary="FETCH - FETCH - OPEN CHANNEL", rawhex="D0...9000", timestamp="", details_tree=details),
        TraceItem(protocol="ISO7816", type="apducommand", summary="TERMINAL RESPONSE - OPEN CHANNEL", rawhex="80140000", timestamp="", details_tree=_node("Allocated Channel: 1")),
        TraceItem(protocol="ISO7816", type="apduresponse", summary="FETCH - FETCH - SEND DATA", rawhex="D0...9000", timestamp="", details_tree=_node("")),
        TraceItem(protocol="ISO7816", type="apduresponse", summary="FETCH - FETCH - CLOSE CHANNEL", rawhex="D0...9000", timestamp="", details_tree=_node("")),
        TraceItem(protocol="ISO7816", type="apducommand", summary="TERMINAL RESPONSE - CLOSE CHANNEL", rawhex="80140000", timestamp="", details_tree=_node("")),
    ]

    sessions = parser._reconstruct_sessions(items)
    assert len(sessions) == 1

    idxs = sessions[0].traceitem_indexes
    # Ensure we captured the OPEN and SEND/CLOSE items even with the extra FETCH token.
    assert 1 in idxs
    assert 3 in idxs
    assert 4 in idxs
