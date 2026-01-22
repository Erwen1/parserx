import pytest
from xti_viewer.ui_main import XTIMainWindow
from PySide6.QtWidgets import QApplication

# Minimal app context needed for widgets
app = QApplication.instance() or QApplication([])


def test_parse_hex_simple():
    win = XTIMainWindow()
    data = win._parse_hex_input_bytes("80 F2 00 00 00")
    assert data == bytes([0x80, 0xF2, 0x00, 0x00, 0x00])


def test_parse_hex_with_offsets_and_ascii():
    win = XTIMainWindow()
    text = "0000: 80 F2 00 00 00  ........................"
    data = win._parse_hex_input_bytes(text)
    assert len(data) == 5


def test_json_detection():
    win = XTIMainWindow()
    json_bytes = b'{"hello":"world"}'
    win.analyze_hex_input.setPlainText(' '.join(f'{b:02X}' for b in json_bytes))
    win.on_analyze_hex_clicked()
    # Ensure status updated bytes count
    assert "bytes" in win.analyze_hex_status.text()


def test_asn1_sequence_heuristic():
    win = XTIMainWindow()
    # Simple DER-like: SEQUENCE tag + length + payload
    data = bytes([0x30, 0x03, 0x02, 0x01, 0x05])
    parsed = win._parse_hex_input_bytes(' '.join(f'{b:02X}' for b in data))
    assert parsed == data
