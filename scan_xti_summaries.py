#!/usr/bin/env python3
import os
from xti_viewer.xti_parser import XTIParser

fname = os.path.join(os.getcwd(), "HL7812_fallback_NOK.xti")
print("File:", fname)
parser = XTIParser()
items = parser.parse_file(fname)
print("Total:", len(items))
count_open = 0
count_term_open = 0
count_term_close = 0
for it in items:
    s = it.summary.strip()
    if s.startswith("FETCH - OPEN CHANNEL"):
        count_open += 1
    if s.startswith("TERMINAL RESPONSE - OPEN CHANNEL"):
        count_term_open += 1
    if s.startswith("TERMINAL RESPONSE - CLOSE CHANNEL"):
        count_term_close += 1

print("OPEN:", count_open, "TERM_OPEN:", count_term_open, "TERM_CLOSE:", count_term_close)
# Show first few terminal response summaries
shown = 0
for it in items:
    s = it.summary.strip()
    if s.startswith("TERMINAL RESPONSE") and shown < 10:
        print("TR:", s)
        shown += 1
