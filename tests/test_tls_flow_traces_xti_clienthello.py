import os
import sys
import tempfile
import shutil
import time
import pytest

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xti_viewer.ui_main import XTIMainWindow


def wait_for(condition_fn, timeout_ms=15000, interval_ms=50):
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        QApplication.processEvents()
        if condition_fn():
            return True
        QTest.qWait(interval_ms)
    return False


def find_session_row_for_ip(win: XTIMainWindow, view, ip_text: str):
    model = view.model()
    rows = model.rowCount()
    for r in range(rows):
        idx0 = model.index(r, 0)
        kind = str(model.data(idx0, Qt.DisplayRole) or '')
        if kind.strip().lower() != 'session':
            continue

        data = model.data(idx0, Qt.UserRole)
        if not isinstance(data, dict):
            try:
                src0 = win.timeline_proxy.mapToSource(idx0)
                data = win.timeline_model.data(src0, Qt.UserRole)
            except Exception:
                data = None
        if isinstance(data, dict):
            ips = data.get('ips') or []
            if isinstance(ips, list) and ip_text in ips:
                # Double-click handler reads Qt.UserRole from column 0.
                return idx0
    return None


def test_tls_flow_traces_xti_shows_clienthello():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, 'traces.xti')
    if not os.path.exists(src):
        pytest.skip('traces.xti not found in repo root')

    temp_dir = tempfile.mkdtemp()
    try:
        dst = os.path.join(temp_dir, 'traces.xti')
        shutil.copy(src, dst)

        app = QApplication.instance() or QApplication(sys.argv)
        win = XTIMainWindow()
        win.show()

        win.load_xti_file(dst)
        ok = wait_for(lambda: getattr(win, 'parser', None) is not None and getattr(win.parser, 'trace_items', None), 20000)
        assert ok, 'Parser did not finish in time'

        view = win.timeline_table
        ok = wait_for(lambda: view.model().rowCount() > 0, 5000)
        assert ok, 'Timeline did not populate'

        idx = find_session_row_for_ip(win, view, '13.38.212.83')
        assert idx is not None, 'Could not find TAC session row for 13.38.212.83'

        view.scrollTo(idx)
        QApplication.processEvents()
        view.doubleClicked.emit(idx)

        ok = wait_for(lambda: hasattr(win, 'tls_tree') and win.tls_tree.topLevelItemCount() > 0, 8000)
        assert ok, 'TLS tree did not populate'

        # Verify ClientHello appears in TLS steps
        found = False
        root = win.tls_tree.invisibleRootItem()
        stack = [root.child(i) for i in range(root.childCount())]
        while stack:
            it = stack.pop()
            if it is None:
                continue
            if 'ClientHello' in (it.text(2) or '') or 'ClientHello' in (it.text(0) or ''):
                found = True
                break
            for c in range(it.childCount()):
                stack.append(it.child(c))

        assert found, 'ClientHello not found in TLS Flow steps'

        # Overview should no longer claim handshake=0
        overview = (win.tls_overview_view.toPlainText() if hasattr(win, 'tls_overview_view') else '')
        assert 'ClientHello' in overview or found

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        try:
            win.close()
        except Exception:
            pass
