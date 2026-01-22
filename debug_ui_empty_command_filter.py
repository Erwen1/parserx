#!/usr/bin/env python3
import sys
from PySide6.QtWidgets import QApplication
from xti_viewer.ui_main import XTIMainWindow
from xti_viewer.xti_parser import XTIParser

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()

    # Parse a sample trace so we have rows
    parser = XTIParser()
    try:
        parser.parse_file('sample_trace.xti')
        win.parser = parser
        win.trace_model.parser = parser
        win.trace_model.load_trace_items(parser.trace_items)
    except Exception as e:
        print(f"[WARN] Could not parse sample_trace.xti: {e}")

    # Ensure baseline with filter disabled (all selected)
    win.select_all_command_types()
    total_before = win.filter_model.rowCount()

    # Deselect all command types (should hide everything)
    win.select_none_command_types()
    cmd_filter = getattr(win.filter_model, 'command_type_filter', 'UNSET')

    if cmd_filter != []:
        print(f"[FAIL] Expected empty list for none selected, got {cmd_filter}")
        return 1

    # After applying empty filter, expect zero rows
    filtered_rows = win.filter_model.rowCount()
    print(f"Rows before: {total_before} after none-selected filter: {filtered_rows}")
    if filtered_rows != 0:
        print("[FAIL] Expected zero rows after selecting no command types")
        return 1

    # Now select all -> filter disabled -> rows restored
    win.select_all_command_types()
    if win.filter_model.command_type_filter is not None:
        print(f"[FAIL] Expected None (disabled) when all selected, got {win.filter_model.command_type_filter}")
        return 1
    restored_rows = win.filter_model.rowCount()
    print(f"Rows restored after all-selected: {restored_rows}")
    if restored_rows != total_before:
        print("[FAIL] Row count mismatch after restoring all-selected")
        return 1

    print("[PASS] Empty command type selection hides all rows; all-selected restores them")
    return 0

if __name__ == '__main__':
    sys.exit(main())
