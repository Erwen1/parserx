"""Quick test to verify Flow Overview events and Parsing Log for test.xti"""
import sys
sys.path.append(r"c:\Users\T0319884\Documents\coding\python\parserx")

from PySide6.QtWidgets import QApplication
from xti_viewer.xti_parser import XTIParser
from xti_viewer.ui_main import XTIMainWindow
from xti_viewer.validation import ValidationManager

xti_path = r"c:\Users\T0319884\Documents\coding\python\parserx\test.xti"

# Create QApplication
app = QApplication(sys.argv)

# Parse the trace
parser = XTIParser()
parser.parse_file(xti_path)

# Build Flow Overview timeline
mw = XTIMainWindow()
mw.parser = parser
mw.populate_flow_timeline(parser)

# Extract events
events = []
for r in range(mw.timeline_model.rowCount()):
    idx = mw.timeline_model.index(r, 0)
    data = mw.timeline_model.data(idx, 256)  # Qt.UserRole
    if data and data.get("kind") == "Event":
        events.append(data)

print("Flow Overview Events:")
for e in events:
    print(f"  {e.get('time', '')} | {e.get('label', '')} (idx={e.get('index')})")

# Collect Parsing Log issues
vm = ValidationManager()
for i, ti in enumerate(parser.trace_items):
    vm.validate_trace_item(ti, i)
vm.finalize_validation()

print("\nParsing Log Critical:")
for issue in vm.get_critical_issues():
    print(f"  {issue.category} | {issue.message} (idx={issue.trace_index})")
