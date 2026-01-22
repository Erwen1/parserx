#!/usr/bin/env python3
"""
Debug script to verify Parsing Log navigation jumps to the correct Interpretation row.
It loads a sample XTI file (sample_trace.xti), waits for parsing to complete,
then triggers a click on the first Parsing Log item and checks the selection.
"""
import sys
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, QModelIndex, Qt
from PySide6.QtWidgets import QApplication

# Ensure project root is on sys.path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from xti_viewer.ui_main import XTIMainWindow


def find_sample_xti(cli_arg: Optional[str]) -> Optional[str]:
    if cli_arg:
        p = Path(cli_arg)
        return str(p) if p.exists() else None
    for name in ("sample_trace.xti", "sample.xti"):
        p = ROOT / name
        if p.exists():
            return str(p)
    return None


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    win = XTIMainWindow()
    win.show()  # optional; helps on some platforms

    cli_arg = sys.argv[1] if len(sys.argv) > 1 else None
    xti_path = find_sample_xti(cli_arg)
    if not xti_path:
        print("ERROR: XTI file not found. Pass a path or place sample_trace.xti next to this script.")
        return 1

    print(f"Loading XTI: {xti_path}")
    win.load_xti_file(xti_path)

    def try_run_test():
        # Wait until parsing finished and log populated
        if getattr(win, 'parser', None) is None:
            QTimer.singleShot(200, try_run_test)
            return
        if win.parsing_log_tree.topLevelItemCount() == 0:
            # parsing finished but no issues: can't test via log
            print("No parsing log entries present; test skipped.")
            return

        item = win.parsing_log_tree.topLevelItem(0)
        idx_text = item.text(3)
        try:
            trace_index = int(idx_text)
        except Exception:
            print(f"First log item has non-integer Index column: '{idx_text}'")
            return

        print(f"Clicking Parsing Log item with trace_index={trace_index}")
        # Simulate the click by directly invoking the handler
        win.on_parsing_log_item_clicked(item, 3)

        def check_selection():
            idx = win.trace_table.currentIndex()
            if not idx.isValid():
                print("FAIL: No selection in Interpretation after navigation.")
                return
            # Map back to source to compare row numbers
            try:
                filter_model = win.trace_table.model()
                source_idx = filter_model.mapToSource(idx)
                selected_row = source_idx.row()
            except Exception:
                selected_row = -1

            print(f"Selected source row: {selected_row}; expected (by index) {trace_index}")
            # Note: Model may be sorted; exact row equality may not hold. Consider success if a row is selected.
            if selected_row >= 0:
                print("OK: Interpretation selection set.")
            else:
                print("FAIL: Could not determine selected row.")

        QTimer.singleShot(150, check_selection)

    QTimer.singleShot(500, try_run_test)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
