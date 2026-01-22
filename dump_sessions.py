#!/usr/bin/env python3
import os
from xti_viewer.xti_parser import XTIParser, tag_server_from_ips

fname = os.path.join(os.getcwd(), "HL7812_fallback_NOK.xti")
parser = XTIParser()
items = parser.parse_file(fname)
print("Sessions:", len(parser.channel_sessions))
for i, s in enumerate(parser.channel_sessions):
    srv = tag_server_from_ips(s.ips)
    print(f"#{i+1} server={srv} ips={list(s.ips)} count={len(s.traceitem_indexes)}")
    # Show a few summaries
    for j, idx in enumerate(s.traceitem_indexes[:8]):
        it = items[idx]
        print("  -", it.summary)
    if len(s.traceitem_indexes) > 8:
        print("  ...")
