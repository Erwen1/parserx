"""Quick check to see what's at index 14."""
from xti_viewer.xti_parser import XTIParser

parser = XTIParser()
parser.parse_file('HL7812_fallback_NOK.xti')

print("Items around index 14:")
for i in range(12, 20):
    item = parser.trace_items[i]
    print(f"{i:4d}. {item.type:15s} | {item.summary[:80]}")
