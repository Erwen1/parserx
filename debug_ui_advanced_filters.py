#!/usr/bin/env python3
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTime
from xti_viewer.ui_main import XTIMainWindow


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = XTIMainWindow()

    # Ensure command actions exist (compact menu mode)
    actions = getattr(win, 'command_actions', {})
    if not actions:
        print("[FAIL] command_actions not found; cannot test menu-based filters")
        return 1

    # 1) All selected => filter_model should have empty command_type_filter (no filtering)
    win.select_all_command_types()
    cmd_filter = getattr(win.filter_model, 'command_type_filter', None)
    print(f"All selected -> command_type_filter={cmd_filter}")
    if cmd_filter:
        print("[FAIL] Expected no filter when all types selected")
        return 1

    # 2) Select only OPEN and CLOSE
    # First clear all, then enable OPEN and CLOSE
    win.select_none_command_types()
    actions['OPEN'].setChecked(True)
    actions['CLOSE'].setChecked(True)
    win.on_command_filter_changed()

    cmd_filter = getattr(win.filter_model, 'command_type_filter', [])
    print(f"Select OPEN+CLOSE -> command_type_filter={cmd_filter}")
    expect = set(['OPEN', 'CLOSE'])
    if set(cmd_filter) != expect:
        print("[FAIL] OPEN+CLOSE selection not reflected in model")
        return 1

    # 3) Toggle extended type: PLI
    actions['PLI'].setChecked(True)
    win.on_command_filter_changed()
    cmd_filter = set(getattr(win.filter_model, 'command_type_filter', []))
    if 'PLI' not in cmd_filter:
        print("[FAIL] Extended type PLI not included after selection")
        return 1
    print("Extended PLI OK")

    # 4) Server filter set to DP+
    combo = getattr(win, 'server_combo', None)
    if combo:
        combo.setCurrentText('DP+')
        win.on_server_filter_changed('DP+')
        server_filter = getattr(win.filter_model, 'server_filter', '')
        print(f"Server combo -> server_filter={server_filter}")
        if server_filter != 'DP+':
            print("[FAIL] Server filter not applied")
            return 1
    else:
        print("[WARN] server_combo missing; skipping server filter test")

    # 5) Time range: set From=00:00:00 To=23:59:59 and verify filter fields updated
    start = QTime(0, 0, 0)
    end = QTime(23, 59, 59)
    # Ensure trace bounds are set so UI handler applies the filter
    win.trace_start_time = start
    win.trace_end_time = end
    win.start_time_edit.setTime(start)
    win.end_time_edit.setTime(end)
    win.on_time_range_changed()
    if not (getattr(win.filter_model, 'time_range_start', None) and getattr(win.filter_model, 'time_range_end', None)):
        print("[FAIL] Time range filter values not set in model")
        return 1

    print("[PASS] UI Advanced Filters basic interactions verified")
    return 0


if __name__ == '__main__':
    sys.exit(main())
