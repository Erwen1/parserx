import os
import sys
import shutil
import tempfile
import time
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xti_viewer.ui_main import XTIMainWindow

def wait_for(condition_fn, timeout_ms=10000, interval_ms=50):
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        QApplication.processEvents()
        if condition_fn():
            return True
        QTest.qWait(interval_ms)
    return False

def find_first_row_by_kind(view, kind_text: str):
    model = view.model()
    rows = model.rowCount()
    for r in range(rows):
        idx0 = model.index(r, 0)
        kind = model.data(idx0, Qt.DisplayRole)
        if str(kind).strip().lower() == kind_text.lower():
            return idx0
    return None

def synthesize_session_from_trace(win: XTIMainWindow):
    """Create a synthetic Session in the timeline that references OPEN/CLOSE indices if present."""
    # Find OPEN/CLOSE in parser.trace_items
    open_idx = None
    close_idx = None
    for i, ti in enumerate(getattr(win.parser, 'trace_items', []) or []):
        s = (ti.summary or '').upper()
        if open_idx is None and 'OPEN CHANNEL' in s:
            open_idx = i
        if 'CLOSE CHANNEL' in s:
            close_idx = i
    if open_idx is None:
        # Use first 20 items as a fallback window
        idxs = list(range(0, min(20, len(win.parser.trace_items))))
    else:
        end = close_idx if close_idx is not None and close_idx > open_idx else min(open_idx + 50, len(win.parser.trace_items))
        idxs = list(range(open_idx, end))
    # Build minimal timeline items with a single session
    items = [
        {
            'kind': 'Session',
            'label': 'Synthetic Session',
            'time': '',
            'port': '',
            'protocol': 'BIP',
            'role': '',
            'server': 'TAC',
            'ips': [],
            'opened': '',
            'closed': '',
            'duration': '',
            'session_indexes': idxs,
            'group_index': -1,
            'sort_key': '',
        }
    ]
    win.timeline_model.set_timeline(items)
    QApplication.processEvents()

def test_tls_flow_content():
    # Setup temp dir
    temp_dir = tempfile.mkdtemp()
    try:
        # Copy sample files
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_xti = os.path.join(repo_root, 'sample_trace.xti')
        report_md = os.path.join(repo_root, 'tac_session_report.md')
        
        if not os.path.exists(sample_xti) or not os.path.exists(report_md):
            pytest.skip("Sample files not found")

        shutil.copy(sample_xti, temp_dir)
        shutil.copy(report_md, temp_dir)
        
        xti_path = os.path.join(temp_dir, 'sample_trace.xti')

        # Init App
        app = QApplication.instance() or QApplication(sys.argv)
        win = XTIMainWindow()
        win.show()

        # Load XTI
        win.load_xti_file(xti_path)
        ok = wait_for(lambda: getattr(win, 'parser', None) is not None and win.parser.trace_items, 15000)
        assert ok, 'Parser did not finish in time'

        # Ensure timeline has content
        view = win.timeline_table
        ok = wait_for(lambda: view.model().rowCount() > 0, 3000)
        if not ok:
            synthesize_session_from_trace(win)

        # Find Session row
        idx_session = find_first_row_by_kind(view, 'Session')
        if idx_session is None:
            synthesize_session_from_trace(win)
            idx_session = find_first_row_by_kind(view, 'Session')
            assert idx_session is not None, 'Failed to synthesize a Session row'

        # Double click session
        model = view.model()
        idx_label = model.index(idx_session.row(), 1)
        view.scrollTo(idx_label)
        QApplication.processEvents()
        view.doubleClicked.emit(idx_label)

        # Wait for TLS tab
        ok = wait_for(lambda: hasattr(win, 'tls_tree') and win.hex_tab_widget.currentIndex() == 2, 3000)
        assert ok, 'TLS Flow tab was not activated'
        
        ok = wait_for(lambda: hasattr(win, 'tls_tree') and win.tls_tree.topLevelItemCount() > 0, 3000)
        assert ok, 'TLS Flow tree has no content'

        # Verify Content
        # 1. Check Tree Items
        tree = win.tls_tree
        root = tree.invisibleRootItem()
        child_count = root.childCount()
        assert child_count > 0, "TLS tree should have children"
        
        # Check for specific TLS events from report
        # [TLS] TLS | SIM->ME | ... | TLS Handshake (ClientHello)
        found_client_hello = False
        for i in range(child_count):
            item = root.child(i)
            text = item.text(2) # Detail column
            if "ClientHello" in text:
                found_client_hello = True
                break
        assert found_client_hello, "Did not find ClientHello in TLS tree"

        # 2. Check Summary View
        summary_text = win.tls_summary_view.text()
        assert "SNI: eim-demo-lab.eu.tac.thalescloud.io" in summary_text
        assert "Version: TLS 1.2" in summary_text
        assert "Chosen Cipher: TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256" in summary_text

        # 3. Check Raw View
        raw_text = win.tls_raw_text.toPlainText()
        assert "FETCH - OPEN CHANNEL" in raw_text
        assert "TERMINAL RESPONSE - CLOSE CHANNEL" in raw_text

    finally:
        shutil.rmtree(temp_dir)
        if 'win' in locals():
            win.close()

if __name__ == "__main__":
    test_tls_flow_content()
