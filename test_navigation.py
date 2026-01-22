"""Verify double-click navigation data is correct"""
import sys
sys.path.append(r"c:\Users\T0319884\Documents\coding\python\parserx")

from PySide6.QtWidgets import QApplication
from xti_viewer.xti_parser import XTIParser
from xti_viewer.ui_main import XTIMainWindow
from xti_viewer.validation import ValidationManager

xti_path = r"c:\Users\T0319884\Documents\coding\python\parserx\test.xti"

app = QApplication(sys.argv)
parser = XTIParser()
parser.parse_file(xti_path)
mw = XTIMainWindow()
mw.parser = parser
mw.populate_flow_timeline(parser)

print("=== Flow Overview Event Navigation Data ===")
for r in range(mw.timeline_model.rowCount()):
    idx = mw.timeline_model.index(r, 0)
    data = mw.timeline_model.data(idx, 256)
    if data and data.get("kind") == "Event":
        trace_idx = data.get("index")
        label = data.get("label")
        print(f"Event: {label}")
        print(f"  -> Will navigate to trace index: {trace_idx}")
        if trace_idx is not None and 0 <= trace_idx < len(parser.trace_items):
            item = parser.trace_items[trace_idx]
            print(f"  -> Trace item summary: {item.summary[:80]}")
        print()

# Build parsing log
vm = ValidationManager()
for i, ti in enumerate(parser.trace_items):
    vm.validate_trace_item(ti, i)
vm.finalize_validation()

print("\n=== Parsing Log Critical Navigation Data ===")
for issue in vm.get_critical_issues():
    if "Link Dropped" in issue.message or "BIP" in issue.category:
        print(f"Issue: {issue.category} | {issue.message}")
        print(f"  -> Will navigate to trace index: {issue.trace_index}")
        if 0 <= issue.trace_index < len(parser.trace_items):
            item = parser.trace_items[issue.trace_index]
            print(f"  -> Trace item summary: {item.summary[:80]}")
        print()
