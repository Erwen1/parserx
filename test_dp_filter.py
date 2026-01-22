"""
Test DP+ filter logic
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from xti_viewer.xti_parser import XTIParser, tag_server_from_ips
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import Qt
import os

os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'
from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

# Parse file
parser = XTIParser()
parser.parse_file('HL7812_fallback_NOK.xti')

# Check all sessions
print("All sessions in file:")
for i, s in enumerate(parser.channel_sessions):
    server = tag_server_from_ips(s.ips)
    print(f"  Session {i+1}: {server}, IPs: {s.ips}, Items: {len(s.traceitem_indexes)}")

print()

# Create models
tree_model = InterpretationTreeModel()
tree_model.parser = parser
tree_model.load_trace_items(parser.trace_items)

filter_model = TraceItemFilterModel()
filter_model.setSourceModel(tree_model)

# Test DP+ filter
print("Testing DP+ filter:")
filter_model.clear_all_filters()
filter_model.set_server_filter("DP+")

# Check session analysis
filter_model.analyze_channel_sessions()
print(f"Active sessions: {len(filter_model.active_sessions)}")
dp_sessions = [sid for sid, label in filter_model.active_sessions.items() if label == "DP+"]
print(f"DP+ sessions found: {len(dp_sessions)}")

result_count = filter_model.rowCount()
print(f"Filter result: {result_count} rows")
print()

if result_count == 0 and len(dp_sessions) == 0:
    print("✅ CORRECT: No DP+ sessions in file, filter shows 0 rows")
else:
    print(f"Filter model active_sessions by server:")
    for server_name in ["DP+", "TAC", "ME", "Google DNS"]:
        count = sum(1 for label in filter_model.active_sessions.values() if label == server_name)
        print(f"  {server_name}: {count} sessions")
