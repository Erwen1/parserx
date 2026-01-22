import os
import sys
import pytest
from PySide6.QtWidgets import QApplication

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xti_viewer.ui_main import XTIMainWindow


def _tls_record(content_type: int, version=(0x03, 0x03), payload: bytes = b"") -> bytes:
    maj, minr = version
    ln = len(payload)
    return bytes([content_type, maj, minr, (ln >> 8) & 0xFF, ln & 0xFF]) + payload


def _handshake_msg(hs_type: int, body: bytes = b"") -> bytes:
    ln = len(body)
    return bytes([hs_type, (ln >> 16) & 0xFF, (ln >> 8) & 0xFF, ln & 0xFF]) + body


def test_basic_tls_scan_reassembles_record_across_segments():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()

    # Build a minimal Handshake record (ClientHello) and split the header across segments.
    hs = _handshake_msg(0x01, b"")
    rec = _tls_record(22, (0x03, 0x03), hs)  # TLS 1.2

    segments = [
        {"dir": "SIM->ME", "ts": "", "data": rec[:2]},
        {"dir": "SIM->ME", "ts": "", "data": rec[2:]},
    ]

    events, hs_types, negotiated = win._basic_tls_detect_segments(segments)

    assert negotiated in (None, "TLS 1.2")
    assert any("ClientHello" in str(x) for x in hs_types)
    assert any("ClientHello" in (e.get("detail") or "") for e in events)


def test_basic_tls_scan_marks_finished_as_encrypted_only_after_ccs():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()

    ccs = _tls_record(20, (0x03, 0x03), b"\x01")
    finished = _tls_record(22, (0x03, 0x03), _handshake_msg(0x14, b""))

    # Split the Finished record so the handshake header crosses a segment boundary.
    segments = [
        {"dir": "SIM->ME", "ts": "", "data": ccs},
        {"dir": "SIM->ME", "ts": "", "data": finished[:1]},
        {"dir": "SIM->ME", "ts": "", "data": finished[1:]},
    ]

    events, hs_types, negotiated = win._basic_tls_detect_segments(segments)

    details = "\n".join([str(e.get("detail") or "") for e in events])

    assert "ChangeCipherSpec" in details
    assert "Encrypted Finished" in details
    # Make sure we didn't emit an Encrypted Finished placeholder without a Finished.
    assert details.count("Encrypted Finished") == 1


def test_basic_tls_scan_does_not_invent_encrypted_finished_on_ccs_only():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()

    ccs = _tls_record(20, (0x03, 0x03), b"\x01")
    segments = [{"dir": "SIM->ME", "ts": "", "data": ccs}]

    events, hs_types, negotiated = win._basic_tls_detect_segments(segments)

    details = "\n".join([str(e.get("detail") or "") for e in events])
    assert "ChangeCipherSpec" in details
    assert "Encrypted Finished" not in details
