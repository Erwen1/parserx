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

    me310 = os.path.join(os.path.dirname(__file__), "ME310_enable_OK.xti")
    if not os.path.exists(me310):
        print("SKIP: ME310_enable_OK.xti not found")
        return 0

    # There is a tac_session_report.md in the repo folder that is for HL7812.
    # This test asserts that when loading ME310, we do NOT use that stale report.
    win.load_xti_file(me310)
    ok = wait_for(lambda: getattr(win, "parser", None) is not None and win.parser.trace_items, 20000)
    assert ok, "Parser did not finish in time"

    view = win.timeline_table
    ok = wait_for(lambda: view.model().rowCount() > 0, 5000)
    assert ok, "Timeline has no rows"

    row = find_session_row(view, "tac")
    if row is None:
        row = find_session_row(view)
    assert row is not None, "No Session row found in timeline"

    # Double-click the session label column
    idx_label = view.model().index(row, 1)
    view.doubleClicked.emit(idx_label)

    ok = wait_for(lambda: win.hex_tab_widget.currentIndex() == 2, 3000)
    assert ok, "TLS Flow tab was not activated"

    ok = wait_for(
        lambda: getattr(win, 'tls_tree', None) is not None and win.tls_tree.topLevelItemCount() > 0,
        8000,
    )
    assert ok, "TLS tree did not populate in time"

    assert getattr(win, "_tls_flow_render_mode", None) == "quick-scan", "Expected quick-scan rendering (report should be skipped)"

    # If report was (wrongly) applied, we'd see HL7812 timestamps (11/06/2025) in rendered tree rows.
    # For ME310 we expect 10/20/2025 timestamps in at least one TLS event row.
    # Column 3 holds timestamps; column 2 holds details.
    timestamps = []
    try:
        tree = win.tls_tree
        top = tree.topLevelItemCount()
        for i in range(top):
            parent = tree.topLevelItem(i)
            # phase groups may exist (report mode), so walk children too
            stack = [parent]
            while stack:
                it = stack.pop()
                try:
                    timestamps.append(it.text(3))
                except Exception:
                    pass
                try:
                    for c in range(it.childCount()):
                        stack.append(it.child(c))
                except Exception:
                    pass
    except Exception:
        timestamps = []

    joined = "\n".join([t for t in timestamps if t])
    if joined:
        sample = "\n".join(joined.splitlines()[:40])
        print("DEBUG: TLS tree timestamp sample (first 40 lines):\n" + sample)
    else:
        print("DEBUG: No non-empty timestamp strings found in TLS tree column 3")

    assert "10/20/2025" in joined, "Expected ME310 timestamps in TLS tree rows (live scan fallback)"
    assert "11/06/2025" not in joined, "Stale HL7812 report seems to have been applied"

    # Quick-scan Overview should include the Cipher Suite Negotiation section.
    # (Whether chosen cipher is decoded depends on the trace contents, but the section must exist.)
    try:
        overview_html = win.tls_overview_view.toHtml()
    except Exception:
        overview_html = ""
    assert "Cipher Suite Negotiation" in overview_html, "Expected Cipher Suite Negotiation section in quick-scan Overview"

    print("PASS: ME310 uses live TLS scan (ignores stale HL report)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
