from xti_viewer.xti_parser import XTIParser

p = XTIParser()
p.parse_file('HL7812_fallback_NOK.xti')
groups = p.get_channel_groups()

print(f"Total channel groups: {len(groups)}\n")
for i, g in enumerate(groups):
    print(f"{i+1}. Server: '{g.get('server', 'Unknown')}'")
    print(f"   Sessions: {len(g.get('sessions', []))}")
    if g.get('sessions'):
        session = g['sessions'][0]
        print(f"   IPs: {session.ips}")
        print(f"   Items: {len(session.traceitem_indexes)}")
    print()
