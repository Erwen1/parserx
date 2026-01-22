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


def _ext(ext_type: int, data: bytes) -> bytes:
    return bytes([(ext_type >> 8) & 0xFF, ext_type & 0xFF, (len(data) >> 8) & 0xFF, len(data) & 0xFF]) + data


def _clienthello_with_extensions(
    sni: str = "example.com",
    alpn: str = "h2",
    versions=(0x0304, 0x0303),
    group: int = 0x001D,
    sig_alg: int = 0x0804,
    cipher: int = 0x1301,
) -> bytes:
    legacy_version = b"\x03\x03"
    rnd = b"\x00" * 32
    session_id = b""
    session_id_len = bytes([len(session_id)])

    cipher_suites = bytes([(cipher >> 8) & 0xFF, cipher & 0xFF])
    cs_len = bytes([(len(cipher_suites) >> 8) & 0xFF, len(cipher_suites) & 0xFF])

    comp_methods = b"\x00"
    comp_len = bytes([len(comp_methods)])

    # SNI
    sni_bytes = sni.encode("utf-8")
    sni_entry = b"\x00" + bytes([(len(sni_bytes) >> 8) & 0xFF, len(sni_bytes) & 0xFF]) + sni_bytes
    sni_list = bytes([(len(sni_entry) >> 8) & 0xFF, len(sni_entry) & 0xFF]) + sni_entry
    ext_sni = _ext(0x0000, sni_list)

    # ALPN
    alpn_bytes = alpn.encode("ascii")
    alpn_item = bytes([len(alpn_bytes)]) + alpn_bytes
    alpn_list = bytes([(len(alpn_item) >> 8) & 0xFF, len(alpn_item) & 0xFF]) + alpn_item
    ext_alpn = _ext(0x0010, alpn_list)

    # supported_versions (client): len(1) + u16 list
    vers_list = b"".join([bytes([(v >> 8) & 0xFF, v & 0xFF]) for v in versions])
    ext_sv = _ext(0x002B, bytes([len(vers_list)]) + vers_list)

    # supported_groups: u16 list length + groups
    groups = bytes([(group >> 8) & 0xFF, group & 0xFF])
    ext_groups = _ext(0x000A, bytes([(len(groups) >> 8) & 0xFF, len(groups) & 0xFF]) + groups)

    # signature_algorithms: u16 list length + algs
    sigs = bytes([(sig_alg >> 8) & 0xFF, sig_alg & 0xFF])
    ext_sig = _ext(0x000D, bytes([(len(sigs) >> 8) & 0xFF, len(sigs) & 0xFF]) + sigs)

    # key_share: u16 list length + (group + key_len + key)
    key = b"\x00"
    ks_entry = bytes([(group >> 8) & 0xFF, group & 0xFF, 0x00, len(key)]) + key
    ext_ks = _ext(0x0033, bytes([(len(ks_entry) >> 8) & 0xFF, len(ks_entry) & 0xFF]) + ks_entry)

    exts = ext_sni + ext_alpn + ext_sv + ext_groups + ext_sig + ext_ks
    ext_len = bytes([(len(exts) >> 8) & 0xFF, len(exts) & 0xFF])

    body = (
        legacy_version
        + rnd
        + session_id_len
        + session_id
        + cs_len
        + cipher_suites
        + comp_len
        + comp_methods
        + ext_len
        + exts
    )
    return body


def _serverhello_tls13_selected(cipher: int = 0x1301, selected_version: int = 0x0304) -> bytes:
    legacy_version = b"\x03\x03"
    rnd = b"\x11" * 32
    session_id = b""
    session_id_len = bytes([len(session_id)])

    cs = bytes([(cipher >> 8) & 0xFF, cipher & 0xFF])
    comp = b"\x00"

    # supported_versions (server): just u16 selected
    sv = bytes([(selected_version >> 8) & 0xFF, selected_version & 0xFF])
    exts = _ext(0x002B, sv)
    ext_len = bytes([(len(exts) >> 8) & 0xFF, len(exts) & 0xFF])

    body = legacy_version + rnd + session_id_len + session_id + cs + comp + ext_len + exts
    return body


def test_basic_tls_scan_extracts_clienthello_extension_metadata_and_tls13_selected_version():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()

    ch = _handshake_msg(0x01, _clienthello_with_extensions())
    sh = _handshake_msg(0x02, _serverhello_tls13_selected())

    rec_ch = _tls_record(22, (0x03, 0x03), ch)
    rec_sh = _tls_record(22, (0x03, 0x03), sh)

    segments = [
        {"dir": "SIM->ME", "ts": "", "data": rec_ch},
        {"dir": "ME->SIM", "ts": "", "data": rec_sh},
    ]

    events, hs_types, negotiated = win._basic_tls_detect_segments(segments)
    meta = getattr(win, "_basic_tls_scan_meta", {}) or {}

    assert meta.get("sni") == "example.com"
    assert "h2" in (meta.get("alpn") or [])

    sv = meta.get("supported_versions") or []
    assert any("TLS 1.3" in str(x) for x in sv)

    groups = " ".join([str(x) for x in (meta.get("supported_groups") or [])])
    assert "x25519" in groups or "0x001D" in groups

    ks = " ".join([str(x) for x in (meta.get("key_share_groups") or [])])
    assert "x25519" in ks or "0x001D" in ks

    sigs = " ".join([str(x) for x in (meta.get("signature_algorithms") or [])])
    assert "rsa_pss_rsae_sha256" in sigs or "0x0804" in sigs

    assert meta.get("server_selected_version") in ("TLS 1.3", "0x0304")
    assert negotiated in ("TLS 1.3", "0x0304")
    assert any("ClientHello" in str(x) for x in hs_types)
    assert any("ServerHello" in str(x) for x in hs_types)
