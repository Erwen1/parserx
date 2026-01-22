import os
import sys
import time

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Run Qt offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
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


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()
    win.show()

    sample = os.path.join(os.path.dirname(__file__), "sample_trace.xti")
    if not os.path.exists(sample):
        print("SKIP: sample_trace.xti not found")
        return 0

    win.load_xti_file(sample)
    ok = wait_for(lambda: getattr(win, "parser", None) is not None and win.parser.trace_items, 15000)
    assert ok, "Parser did not finish in time"

    # Select a row in Interpretation while unfiltered
    view = win.trace_table
    model = view.model()
    rows = model.rowCount()
    assert rows > 0, "No rows to test"

    target_row = min(5, rows - 1)
    idx = model.index(target_row, 0)
    view.scrollTo(idx)
    view.setCurrentIndex(idx)
    QApplication.processEvents()

    # Remember what source-row got stored
    remembered = getattr(win, "_last_selected_source_row_unfiltered", None)
    assert remembered is not None, "No remembered row stored"

    # Simulate session filter being applied (like Flow Overview double-click)
    # Apply a minimal session filter (like Flow Overview double-click)
    win.filter_model.set_session_filter(list(range(0, min(3, len(win.parser.trace_items)))))
    win.clear_filter_button.setVisible(True)
    QApplication.processEvents()

    # Clear filter using the same handler the button uses
    win.clear_command_family_filter()

    # Expect current selection maps back to remembered source row
    ok = wait_for(lambda: view.currentIndex().isValid(), 2000)
    assert ok, "No current index after clearing filter"

    # Compare selection by mapping current proxy index back to source
    src = win.filter_model.mapToSource(view.currentIndex())
    assert src.isValid(), "Current selection did not map to source"
    assert src.row() == remembered, f"Expected restored source row {remembered}, got {src.row()}"

    print("PASS: Clear Filter restores last selected Interpretation row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
