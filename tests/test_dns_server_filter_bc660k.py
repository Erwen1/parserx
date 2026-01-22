import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from xti_viewer.xti_parser import XTIParser, tag_server_from_ips
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel


def _has_dns_label(label: str) -> bool:
    return isinstance(label, str) and ("dns" in label.lower())


def test_dns_server_filter_bc660k_shows_rows():
    xti_path = Path(__file__).resolve().parent.parent / "BC660K_enable_OK.xti"
    if not xti_path.exists():
        pytest.skip("BC660K_enable_OK.xti not found")

    app = QApplication.instance() or QApplication(sys.argv)

    parser = XTIParser()
    parser.parse_file(str(xti_path))

    session_labels = [tag_server_from_ips(s.ips) for s in parser.channel_sessions]
    if not any(_has_dns_label(lbl) for lbl in session_labels):
        pytest.skip("Trace does not contain DNS-labeled sessions")

    tree_model = InterpretationTreeModel()
    tree_model.parser = parser
    tree_model.load_trace_items(parser.trace_items)

    filter_model = TraceItemFilterModel()
    filter_model.setSourceModel(tree_model)

    filter_model.clear_all_filters()
    filter_model.set_server_filter("DNS")

    assert filter_model.rowCount() > 0
