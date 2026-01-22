import os
import sys
import time

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Run Qt offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest

from xti_viewer.ui_main import XTIMainWindow


def wait_for(condition_fn, timeout_ms=10000, interval_ms=50):
    """Pump the Qt loop until condition_fn() is True or timeout."""
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

    # Load file
    win.load_xti_file(sample)

    # Wait for parser to attach
    ok = wait_for(lambda: getattr(win, "parser", None) is not None and win.parser.trace_items, 15000)
    assert ok, "Parser did not finish in time"

    # Populate timeline should already run in on_parsing_finished; ensure model has rows
    view = win.timeline_table
    model = view.model()

    def find_first_event_index():
        # Scan proxy model for a row whose first column (Type) equals 'Event'
        rows = model.rowCount()
        for r in range(rows):
            idx0 = model.index(r, 0)
            kind = model.data(idx0, Qt.DisplayRole)
            if str(kind).strip().lower() == "event":
                return idx0
        return None

    idx0 = find_first_event_index()
    if idx0 is None:
        # Inject a synthetic 'Cold Reset' event into parser and rebuild models
        from xti_viewer.xti_parser import TraceItem, TreeNode
        now_sort = str(int(time.time() * 1000))
        synthetic = TraceItem(
            protocol="SYSTEM",
            type="EVENT",
            summary="Card Event: Cold Reset",
            rawhex=None,
            timestamp="12/01/2025 00:00:00:000.000000",
            details_tree=TreeNode("Card Event: Cold Reset"),
            timestamp_sort_key=now_sort,
        )
        win.parser.trace_items.append(synthetic)
        win.trace_model.load_trace_items(win.parser.trace_items)
        win.populate_flow_timeline(win.parser)
        assert wait_for(lambda: view.model().rowCount() > 0, 2000)
        idx0 = find_first_event_index()
        assert idx0 is not None, "Failed to inject Event row for testing"

    # Fetch payload and target trace index for later assertion
    # Map to source to ask model for UserRole (ui_main uses source's UserRole)
    src0 = win.timeline_proxy.mapToSource(idx0)
    payload = win.timeline_model.data(src0, Qt.UserRole)
    assert payload and payload.get("kind") == "Event", "Payload missing or not Event"
    target_trace_index = payload.get("index")
    assert isinstance(target_trace_index, int), "Event payload missing 'index'"
    target_item = win.parser.trace_items[target_trace_index]

    # Simulate double-click on the center of the row in the label column for better hit
    idx_label = model.index(idx0.row(), 1)
    # Ensure the row is visible, then emit doubleClicked directly for reliability offscreen
    view.scrollTo(idx_label)
    QApplication.processEvents()
    view.doubleClicked.emit(idx_label)

    # Expect Interpretation tab selected and current selected item equals target_item
    ok = wait_for(lambda: win.tab_widget.currentIndex() == 0, 3000)
    assert ok, "Interpretation tab was not activated by timeline double-click"

    def selected_trace_item():
        filt_idx = win.trace_table.currentIndex()
        if not filt_idx.isValid():
            return None
        src_idx = win.filter_model.mapToSource(filt_idx)
        return win.trace_model.get_trace_item(src_idx)

    ok = wait_for(lambda: selected_trace_item() is not None, 3000)
    assert ok, "No selection in Interpretation after double-click"

    sel_item = selected_trace_item()
    assert sel_item == target_item, (
        f"Selected item mismatch: expected trace index {target_trace_index}, got different item"
    )

    print("PASS: Double-click on Event navigates to Interpretation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
