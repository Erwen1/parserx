import os
import sys
import time

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Run Qt offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

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


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()
    win.show()

    sample = os.path.join(os.path.dirname(__file__), 'sample_trace.xti')
    if not os.path.exists(sample):
        print('SKIP: sample_trace.xti not found')
        return 0

    win.load_xti_file(sample)
    ok = wait_for(lambda: getattr(win, 'parser', None) is not None and win.parser.trace_items, 15000)
    assert ok, 'Parser did not finish in time'

    # Ensure timeline has content
    view = win.timeline_table
    ok = wait_for(lambda: view.model().rowCount() > 0, 3000)
    if not ok:
        # Synthesize timeline content if none present
        synthesize_session_from_trace(win)

    # Find a Session row; synthesize one if needed
    idx_session = find_first_row_by_kind(view, 'Session')
    if idx_session is None:
        synthesize_session_from_trace(win)
        idx_session = find_first_row_by_kind(view, 'Session')
        assert idx_session is not None, 'Failed to synthesize a Session row'

    # Double-click the session's label column for better hit area
    model = view.model()
    idx_label = model.index(idx_session.row(), 1)
    view.scrollTo(idx_label)
    QApplication.processEvents()
    view.doubleClicked.emit(idx_label)

    # Expect TLS tab activated (index 2) and content populated in tls_tree
    ok = wait_for(lambda: hasattr(win, 'tls_tree') and win.hex_tab_widget.currentIndex() == 2, 3000)
    assert ok, 'TLS Flow tab was not activated'

    ok = wait_for(lambda: hasattr(win, 'tls_tree') and win.tls_tree.topLevelItemCount() > 0, 3000)
    assert ok, 'TLS Flow tree has no content'

    print('PASS: Double-click Session populates TLS Flow')
    return 0


if __name__ == '__main__':
    sys.exit(main())
