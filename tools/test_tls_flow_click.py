import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication


def wait_until(cond_fn, timeout_s=30.0, poll_ms=50):
    start = time.time()
    app = QApplication.instance()
    while time.time() - start < timeout_s:
        try:
            if cond_fn():
                return True
        except Exception:
            pass
        # Keep Qt event loop responsive
        if app:
            app.processEvents()
        time.sleep(poll_ms / 1000.0)
    return False


def pick_session_index(window, match_substring=None):
    """Return a proxy model index for the first Session row (optionally matching substring)."""
    proxy = window.timeline_proxy
    model = proxy

    # Iterate rows and find those labelled "Session" in column 0
    rows = model.rowCount()
    for r in range(rows):
        idx0 = model.index(r, 0)
        if not idx0.isValid():
            continue
        type_text = model.data(idx0, Qt.DisplayRole)
        if str(type_text).strip() != "Session":
            continue
        # Optional label filter (column 1 is the label)
        if match_substring:
            lbl_idx = model.index(r, 1)
            lbl_text = model.data(lbl_idx, Qt.DisplayRole) or ""
            if match_substring.lower() not in str(lbl_text).lower():
                continue
        return idx0
    return None


def run(file_path, match=None, dump_rows=10):
    # Ensure repository root is on sys.path
    here = Path(__file__).resolve()
    root = here.parents[1]  # repo root containing package modules
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # Lazy import after sys.path setup
    from xti_viewer.ui_main import XTIMainWindow

    # Create Qt app if not already existing
    app = QApplication.instance() or QApplication(sys.argv)

    win = XTIMainWindow()
    win.show()  # ensure widgets are constructed

    # Load the XTI file (parses in a background thread)
    win.load_xti_file(file_path)

    # Wait until parser is ready and timeline has rows
    ok = wait_until(lambda: getattr(win, "parser", None) is not None and win.timeline_proxy.rowCount() > 0, timeout_s=60)
    if not ok:
        print("[TEST] Timeout: parser or timeline not ready.")
        return 2

    # Find a session row to double-click
    idx_proxy = pick_session_index(win, match_substring=match)
    if idx_proxy is None:
        print("[TEST] No Session rows found in Flow Overview.")
        return 3

    # Simulate double-click behavior by invoking handler directly
    try:
        win.on_timeline_double_clicked(idx_proxy)
    except Exception as e:
        print(f"[TEST] Exception during double-click handler: {e}")
        return 4

    # Give UI a moment to populate the TLS Flow tab
    ok = wait_until(lambda: win.hex_tab_widget.currentIndex() == 2, timeout_s=5)
    if not ok:
        print("[TEST] TLS Flow tab was not activated (expected index 2).")
        # Continue to check tree anyway

    # Process events to allow tree population
    app.processEvents()
    time.sleep(0.1)
    app.processEvents()

    # Validate TLS tree contents
    count = win.tls_tree.topLevelItemCount()
    print(f"[TEST] TLS Flow top-level item count: {count}")

    # Dump a few rows for visibility
    rows_to_dump = min(dump_rows, count)
    for i in range(rows_to_dump):
        it = win.tls_tree.topLevelItem(i)
        step = it.text(0)
        direction = it.text(1)
        detail = it.text(2)
        ts = it.text(3)
        print(f"  [{i:02d}] Step={step!r} Dir={direction!r} Detail={detail!r} Time={ts!r}")

    # Also print sub-tabs content for Summary, Handshake, Ladder, Raw
    try:
        summary_text = getattr(win, 'tls_summary_view', None).text() if getattr(win, 'tls_summary_view', None) else ''
        print("\n[SUBTAB] Summary:")
        print(summary_text or "(empty)")
    except Exception:
        print("\n[SUBTAB] Summary: (unavailable)")
    try:
        handshake_text = getattr(win, 'tls_handshake_label', None).text() if getattr(win, 'tls_handshake_label', None) else ''
        print("\n[SUBTAB] Handshake:")
        print(handshake_text or "(empty)")
    except Exception:
        print("\n[SUBTAB] Handshake: (unavailable)")
    try:
        ladder_text = getattr(win, 'tls_ladder_label', None).text() if getattr(win, 'tls_ladder_label', None) else ''
        print("\n[SUBTAB] Ladder:")
        print(ladder_text or "(empty)")
    except Exception:
        print("\n[SUBTAB] Ladder: (unavailable)")
    try:
        raw_text = getattr(win, 'tls_raw_text', None).toPlainText() if getattr(win, 'tls_raw_text', None) else ''
        print("\n[SUBTAB] Raw:")
        print(raw_text or "(empty)")
    except Exception:
        print("\n[SUBTAB] Raw: (unavailable)")

    # Basic assertions for Summary decoded sections
    try:
        has_decoded = (
            ('Decoded Sections' in summary_text) or
            ('Offered Cipher Suites' in summary_text) or
            ('Offered Ciphers' in summary_text) or
            ('Certificates CNs' in summary_text)
        )
        if not has_decoded:
            print("[TEST] WARNING: Summary tab does not show decoded sections.")
    except Exception:
        pass

    # Outcome
    if count == 0:
        print("[TEST] FAILURE: TLS Flow shows no items.\n"
              "       - Either no TLS was detected in this session,\n"
              "       - or the analyzer was unavailable,\n"
              "       - or payload extraction failed.")
        return 5

    # Success
    print("[TEST] SUCCESS: TLS Flow populated.")
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Test TLS Flow tab population on session double-click.")
    ap.add_argument("file", help="Path to .xti file to open")
    ap.add_argument("--match", help="Substring to match a specific session label", default=None)
    ap.add_argument("--rows", type=int, help="Number of TLS rows to print", default=12)
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"File not found: {args.file}")
        sys.exit(1)

    rc = run(args.file, match=args.match, dump_rows=args.rows)
    # Ensure the Qt app exits cleanly
    app = QApplication.instance()
    if app:
        QTimer.singleShot(0, app.quit)
        app.exec()
    sys.exit(rc)
