import os
import sys
import shutil
import tempfile
import time
import pytest

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xti_viewer.ui_main import XTIMainWindow


def wait_for(condition_fn, timeout_ms=20000, interval_ms=50):
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        QApplication.processEvents()
        if condition_fn():
            return True
        QTest.qWait(interval_ms)
    return False


def test_scenario_window_runs_and_produces_rows():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, 'traces.xti')
    if not os.path.exists(src):
        pytest.skip('traces.xti not found')

    temp_dir = tempfile.mkdtemp()
    try:
        dst = os.path.join(temp_dir, 'traces.xti')
        shutil.copy(src, dst)

        app = QApplication.instance() or QApplication(sys.argv)
        win = XTIMainWindow()
        win.show()

        win.load_xti_file(dst)
        ok = wait_for(lambda: getattr(win, 'parser', None) is not None and getattr(win.parser, 'trace_items', None), 30000)
        assert ok, 'Parser did not finish in time'

        # Open scenario window and run
        win.open_scenario_window()

        # Find the ScenarioWindow instance among top-level widgets
        scenario = None
        for w in QApplication.topLevelWidgets():
            if w.windowTitle() == 'Scenario Results':
                scenario = w
                break
        assert scenario is not None, 'Scenario window did not open'

        # Click Run
        scenario.run_btn.click()

        ok = wait_for(lambda: scenario.results_tree.topLevelItemCount() > 0, 5000)
        assert ok, 'Scenario results did not populate'

        # Ensure status column exists and has valid values
        for r in range(scenario.results_tree.topLevelItemCount()):
            it = scenario.results_tree.topLevelItem(r)
            assert it is not None
            assert (it.text(1) or '').strip() in ('OK', 'WARN', 'FAIL')

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        try:
            win.close()
        except Exception:
            pass
