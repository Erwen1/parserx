import os
import sys
import shutil
import tempfile
import time
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xti_viewer.ui_main import XTIMainWindow

def wait_for(condition_fn, timeout_ms=10000, interval_ms=50):
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        QApplication.processEvents()
        if condition_fn():
            return True
        QTest.qWait(interval_ms)
    return False

def find_row_by_server(view, server_name: str):
    model = view.model()
    rows = model.rowCount()
    for r in range(rows):
        # Check Label or Server column (columns 1 or 5 usually, but we can check data role)
        # In FlowTimelineModel, label is col 1, server is col 5
        idx_label = model.index(r, 1)
        idx_server = model.index(r, 5)
        label = str(model.data(idx_label, Qt.DisplayRole) or "")
        server = str(model.data(idx_server, Qt.DisplayRole) or "")
        
        if server_name.lower() in server.lower() or server_name.lower() in label.lower():
            return idx_label
    return None

def test_tls_flow_visuals_real_file():
    # Setup temp dir
    temp_dir = tempfile.mkdtemp()
    try:
        # Copy real file
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        real_xti = os.path.join(repo_root, 'HL7812_fallback_NOK.xti')
        
        if not os.path.exists(real_xti):
            pytest.skip("HL7812_fallback_NOK.xti not found")

        shutil.copy(real_xti, temp_dir)
        xti_path = os.path.join(temp_dir, 'HL7812_fallback_NOK.xti')

        # Init App
        app = QApplication.instance() or QApplication(sys.argv)
        win = XTIMainWindow()
        win.show()

        # Load XTI
        win.load_xti_file(xti_path)
        ok = wait_for(lambda: getattr(win, 'parser', None) is not None and win.parser.trace_items, 15000)
        assert ok, 'Parser did not finish in time'

        # Ensure timeline has content
        view = win.timeline_table
        ok = wait_for(lambda: view.model().rowCount() > 0, 3000)
        assert ok, 'Timeline not populated'

        # Find TAC Session row
        # We know from dump it's Group[2] server=TAC
        idx_session = find_row_by_server(view, 'TAC')
        assert idx_session is not None, 'Could not find TAC session in timeline'

        # Double click session
        view.scrollTo(idx_session)
        QApplication.processEvents()
        view.doubleClicked.emit(idx_session)

        # Wait for TLS tab
        ok = wait_for(lambda: hasattr(win, 'tls_tree') and win.hex_tab_widget.currentIndex() == 2, 3000)
        assert ok, 'TLS Flow tab was not activated'
        
        ok = wait_for(lambda: hasattr(win, 'tls_tree') and win.tls_tree.topLevelItemCount() > 0, 3000)
        assert ok, 'TLS Flow tree has no content'

        # Verify Content for HL7812_fallback_NOK.xti
        
        # 1. Check Tree Items
        tree = win.tls_tree
        root = tree.invisibleRootItem()
        child_count = root.childCount()
        assert child_count > 10, "TLS tree should have many items (handshake + data)"
        
        # Check for specific events
        found_client_hello = False
        found_server_hello = False
        found_cert = False
        found_app_data = False
        
        for i in range(child_count):
            item = root.child(i)
            text = item.text(2) # Detail column
            if "ClientHello" in text:
                found_client_hello = True
            if "ServerHello" in text:
                found_server_hello = True
            if "Certificate CN:" in text:
                found_cert = True
            if "Application Data" in text:
                found_app_data = True

        assert found_client_hello, "Missing ClientHello"
        assert found_server_hello, "Missing ServerHello"
        assert found_cert, "Missing Certificates"
        assert found_app_data, "Missing Application Data"

        # 2. Check Summary View
        summary_text = win.tls_summary_view.text()
        print(f"Summary Text: {summary_text}")
        
        assert "SNI: eim-demo-lab.eu.tac.thalescloud.io" in summary_text
        assert "Version: TLS 1.2" in summary_text
        # Note: The dump showed "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256"
        assert "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256" in summary_text

        print("PASS: TLS Flow visuals verified for HL7812_fallback_NOK.xti")

    finally:
        shutil.rmtree(temp_dir)
        if 'win' in locals():
            win.close()

if __name__ == "__main__":
    test_tls_flow_visuals_real_file()
