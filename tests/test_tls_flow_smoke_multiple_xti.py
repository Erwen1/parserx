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


def wait_for(condition_fn, timeout_ms=20000, interval_ms=50):
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        QApplication.processEvents()
        if condition_fn():
            return True
        QTest.qWait(interval_ms)
    return False


def _iter_tree_items(tree):
    root = tree.invisibleRootItem()
    stack = [root.child(i) for i in range(root.childCount())]
    while stack:
        it = stack.pop()
        if it is None:
            continue
        yield it
        for c in range(it.childCount()):
            stack.append(it.child(c))


def _find_session_rows(win: XTIMainWindow, max_rows: int = 8):
    view = win.timeline_table
    model = view.model()
    rows = model.rowCount()
    found = []
    for r in range(rows):
        idx0 = model.index(r, 0)
        kind = str(model.data(idx0, Qt.DisplayRole) or '').strip().lower()
        if kind != 'session':
            continue

        data = model.data(idx0, Qt.UserRole)
        if not isinstance(data, dict):
            try:
                src0 = win.timeline_proxy.mapToSource(idx0)
                data = win.timeline_model.data(src0, Qt.UserRole)
            except Exception:
                data = None
        if not isinstance(data, dict):
            continue

        # Prefer TLS-like sessions: port 443 if available
        port = data.get('port')
        if str(port).strip() not in ('443', '443.0'):
            continue

        found.append((idx0, data))
        if len(found) >= max_rows:
            break

    # Fallback: if nothing matched port 443, take first sessions
    if not found:
        for r in range(rows):
            idx0 = model.index(r, 0)
            kind = str(model.data(idx0, Qt.DisplayRole) or '').strip().lower()
            if kind != 'session':
                continue
            data = model.data(idx0, Qt.UserRole)
            if isinstance(data, dict):
                found.append((idx0, data))
                if len(found) >= max_rows:
                    break

    return found


@pytest.mark.parametrize(
    'xti_name',
    [
        'HL7812_fallback_NOK.xti',
        'ME310_enable_OK.xti',
        'BC660K_enable_OK.xti',
        'traces.xti',
        'test.xti',
        'sample_trace.xti',
    ],
)
def test_tls_flow_smoke_multiple_xti(xti_name: str):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, xti_name)
    if not os.path.exists(src):
        pytest.skip(f'{xti_name} not found')

    temp_dir = tempfile.mkdtemp()
    try:
        dst = os.path.join(temp_dir, xti_name)
        shutil.copy(src, dst)

        app = QApplication.instance() or QApplication(sys.argv)
        win = XTIMainWindow()
        win.show()

        win.load_xti_file(dst)
        ok = wait_for(lambda: getattr(win, 'parser', None) is not None and getattr(win.parser, 'trace_items', None), 30000)
        assert ok, f'Parser did not finish in time for {xti_name}'

        view = win.timeline_table
        ok = wait_for(lambda: view.model().rowCount() > 0, 20000)
        if not ok:
            pytest.skip(f'Timeline did not populate for {xti_name} (no sessions/events in this trace?)')

        sessions = _find_session_rows(win, max_rows=6)
        if not sessions:
            pytest.skip(f'No session rows found for {xti_name} (trace may not contain TLS sessions)')

        for (idx0, data) in sessions:
            prev_summary = ''
            try:
                prev_summary = win.tls_summary_label.text() if hasattr(win, 'tls_summary_label') else ''
            except Exception:
                prev_summary = ''

            view.scrollTo(idx0)
            QApplication.processEvents()
            view.doubleClicked.emit(idx0)

            # Wait for a fresh population (summary changes and tree has content)
            ok = wait_for(
                lambda: (
                    hasattr(win, 'tls_tree')
                    and win.tls_tree.topLevelItemCount() > 0
                    and (
                        (hasattr(win, 'tls_summary_label') and (win.tls_summary_label.text() or '') != prev_summary)
                        or (not hasattr(win, 'tls_summary_label'))
                    )
                ),
                20000,
            )
            assert ok, f'TLS Flow did not populate for {xti_name}'

            # Messages tab: ensure at least one TLS-like keyword appears in the Steps tree.
            keywords = ('ClientHello', 'ServerHello', 'Certificate', 'ChangeCipherSpec', 'Finished', 'ApplicationData', 'TLS Alert', 'Alert')
            found_kw = False
            for it in _iter_tree_items(win.tls_tree):
                if any(k in (it.text(0) or '') for k in keywords) or any(k in (it.text(2) or '') for k in keywords):
                    found_kw = True
                    break
            assert found_kw, f'TLS Flow Steps look empty/non-informative for {xti_name}'

            # Overview tab: assert key sections + scope clarity exist
            overview = win.tls_overview_view.toPlainText() if hasattr(win, 'tls_overview_view') else ''
            assert 'Session Overview' in overview
            assert 'Security Configuration' in overview
            assert 'Cipher Suite Negotiation' in overview
            assert 'Scope:' in overview

            # Security tab: ladder and cipher analysis present
            security = win.tls_security_view.toPlainText() if hasattr(win, 'tls_security_view') else ''
            assert 'TLS Handshake Ladder Diagram' in security
            assert 'Cipher Suite Analysis' in security
            assert 'Version:' in security

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        try:
            win.close()
        except Exception:
            pass
