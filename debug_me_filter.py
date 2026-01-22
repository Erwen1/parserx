"""
Debug ME filter to see what's being matched.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from xti_viewer.xti_parser import XTIParser, tag_server_from_ips
from xti_viewer.models import InterpretationTreeModel, TraceItemFilterModel
from PySide6.QtCore import Qt

xti_file = r"C:\Users\T0319884\Documents\coding\python\parserx\HL7812_fallback_NOK.xti"

print("🔍 Debugging ME Filter")
print("=" * 80)

# Parse
parser = XTIParser()
parser.parse_file(xti_file)

# Check ME sessions from parser
me_sessions = [s for s in parser.channel_sessions if tag_server_from_ips(s.ips) == "ME"]
me_item_indexes = set()
for session in me_sessions:
    me_item_indexes.update(session.traceitem_indexes)

print(f"Parser: {len(me_sessions)} ME sessions, {len(me_item_indexes)} unique items")
print(f"ME item indexes: {sorted(me_item_indexes)}")
print()

# Check what filter model sees
import os
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'
from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

tree_model = InterpretationTreeModel()
tree_model.parser = parser
tree_model.load_trace_items(parser.trace_items)

filter_model = TraceItemFilterModel()
filter_model.setSourceModel(tree_model)

# Apply ME filter
filter_model.clear_all_filters()
filter_model.set_server_filter("ME")

print(f"Filter model: {filter_model.rowCount()} rows shown")
print()

# Check what sessions the filter model analyzed
filter_model.analyze_channel_sessions()

print(f"Filter model active_sessions: {len(filter_model.active_sessions)}")
for session_id, server_label in filter_model.active_sessions.items():
    item_count = len(filter_model.session_items.get(session_id, []))
    print(f"  {session_id}: server='{server_label}', items={item_count}")
    if server_label == "ME":
        indexes = filter_model.session_items.get(session_id, [])
        print(f"    Indexes: {indexes}")

print()
print("Expected: 12 total ME items")
print(f"Actual filter showing: {filter_model.rowCount()} rows")
