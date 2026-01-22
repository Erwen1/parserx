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


def find_session_row(view, contains_text: str | None = None) -> int | None:
    model = view.model()
    cols = model.columnCount()
    needle = (contains_text or "").strip().lower()
    for r in range(model.rowCount()):
        kind = model.data(model.index(r, 0), Qt.DisplayRole)
        if str(kind).strip().lower() != "session":
            continue
        if not needle:
            return r

        row_text = " ".join(
            [str(model.data(model.index(r, c), Qt.DisplayRole) or "") for c in range(cols)]
        ).lower()
        if needle in row_text:
            return r
    return None


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()
    win.show()

    hl = os.path.join(os.path.dirname(__file__), "HL7812_fallback_NOK.xti")
    if not os.path.exists(hl):
        print("SKIP: HL7812_fallback_NOK.xti not found")
        return 0

    win.load_xti_file(hl)
    ok = wait_for(lambda: getattr(win, "parser", None) is not None and win.parser.trace_items, 20000)
    assert ok, "Parser did not finish in time"

    view = win.timeline_table
    ok = wait_for(lambda: view.model().rowCount() > 0, 5000)
    assert ok, "Timeline has no rows"

    # Prefer TAC session if present (most relevant for the report files)
    row = find_session_row(view, "tac")
    if row is None:
        row = find_session_row(view)
    assert row is not None, "No Session row found in timeline"

    idx_label = view.model().index(row, 1)
    view.doubleClicked.emit(idx_label)

    ok = wait_for(lambda: win.hex_tab_widget.currentIndex() == 2, 3000)
    assert ok, "TLS Flow tab was not activated"

    ok = wait_for(
        lambda: getattr(win, "tls_tree", None) is not None and win.tls_tree.topLevelItemCount() > 0,
        8000,
    )
    assert ok, "TLS tree did not populate in time"

    # Ensure report-mode renderer was used (quick-scan now has similar grouping).
    assert getattr(win, "_tls_flow_render_mode", None) == "report", "Expected report-mode TLS rendering"

    # (render mode already asserted above)

    # Report-based rendering creates phase group headers at the top level.
    top0 = win.tls_tree.topLevelItem(0)
    top0_text = (top0.text(0) if top0 is not None else "")
    assert "Handshake Phase" in top0_text, "Expected report-based TLS rendering (phase groups)"

    # Spot-check report timestamp format for HL7812
    # (If report is used, we expect the known HL date marker to appear somewhere.)
    found_hl_date = False
    root = win.tls_tree.invisibleRootItem()
    stack = []
    for i in range(root.childCount()):
        stack.append(root.child(i))
    while stack:
        it = stack.pop()
        ts = ""
        try:
            ts = it.text(3)
        except Exception:
            ts = ""
        if "11/06/2025" in (ts or ""):
            found_hl_date = True
            break
        try:
            for c in range(it.childCount()):
                stack.append(it.child(c))
        except Exception:
            pass

    assert found_hl_date, "Expected HL7812 report timestamps (11/06/2025) somewhere in TLS tree"

    print("PASS: HL7812 uses matching TLS report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
