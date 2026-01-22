#!/usr/bin/env python3
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTime

from xti_viewer.ui_main import XTIMainWindow
from xti_viewer.xti_parser import XTIParser

TARGET_FILE = os.path.join(os.getcwd(), "HL7812_fallback_NOK.xti")


def collect_visible_summaries(win):
    # Iterate filtered rows and collect summary texts
    fm = win.filter_model
    summaries = []
    rows = fm.rowCount()
    for r in range(rows):
        idx = fm.index(r, 0)
        s = fm.data(idx)
        if isinstance(s, str):
            summaries.append(s)
    return summaries


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    if not os.path.exists(TARGET_FILE):
        print(f"[FAIL] File not found: {TARGET_FILE}")
        return 1

    # Parse file directly (bypass background thread for test)
    parser = XTIParser()
    trace_items = parser.parse_file(TARGET_FILE)
    if not trace_items:
        print("[FAIL] No trace items parsed")
        return 1

    # Build window and inject parsed state like on_parsing_finished
    win = XTIMainWindow()
    win.trace_items = trace_items
    win.parser = parser
    win.validation_manager = getattr(win, 'validation_manager', None)
    win.trace_model.parser = parser
    win.trace_model.load_trace_items(trace_items)

    # Initialize time range so time filter works
    win.initialize_time_range()

    # Ensure command types are all selected (no type filter)
    win.select_all_command_types()

    # Server filter: DNS by ME
    win.server_combo.setCurrentText('DNS by ME')
    win.on_server_filter_changed('DNS by ME')

    # Expand time to full range
    win.reset_time_filter()

    summaries = collect_visible_summaries(win)
    has_open = any(s.startswith('FETCH - OPEN CHANNEL') for s in summaries)

    # Check for separate TERMINAL RESPONSE rows
    has_term_open_row = any(s.startswith('TERMINAL RESPONSE - OPEN CHANNEL') for s in summaries)

    # Also check combined FETCH rows for paired TERMINAL RESPONSE
    fm = win.filter_model
    paired_term_open_in_fetch = False
    for r in range(fm.rowCount()):
        pidx = fm.index(r, 0)
        s = fm.data(pidx)
        if isinstance(s, str) and s.startswith('FETCH - FETCH - OPEN CHANNEL'):
            # Map to source and access internal pointer
            sidx = fm.mapToSource(pidx)
            tree_item = win.trace_model.get_tree_item(sidx)
            # Use pairing manager to check TERMINAL RESPONSE pairing
            pair = win.trace_model.get_pair_info_for_item(tree_item.trace_item) if tree_item else None
            if pair and pair.response_item and isinstance(pair.response_item.summary, str):
                if pair.response_item.summary.startswith('TERMINAL RESPONSE - OPEN CHANNEL'):
                    paired_term_open_in_fetch = True
                    break

    print(f"Visible rows: {len(summaries)}")
    print(f"Contains FETCH - OPEN CHANNEL: {has_open}")
    print(f"Separate TERMINAL RESPONSE - OPEN CHANNEL row: {has_term_open_row}")
    print(f"Paired TERMINAL RESPONSE inside FETCH row: {paired_term_open_in_fetch}")

    if not has_open:
        print("[FAIL] Missing FETCH - OPEN CHANNEL under DNS by ME filter")
        return 1
    if not (has_term_open_row or paired_term_open_in_fetch):
        print("[FAIL] TERMINAL RESPONSE - OPEN CHANNEL not present (row or paired)")
        return 1

    print("[PASS] DNS by ME filter includes OPEN and TERMINAL RESPONSE (row or paired)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
