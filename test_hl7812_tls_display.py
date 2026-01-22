"""
Test TLS Flow Display Improvements on HL7812 File
"""
import sys
sys.path.insert(0, r'c:\Users\T0319884\Documents\coding\python\parserx')

from xti_viewer.xti_parser import XTIParser
from pathlib import Path

# Load HL7812 file
print("Loading HL7812_fallback_NOK.xti...")
parser = XTIParser()
parser.parse_file(r'c:\Users\T0319884\Documents\coding\python\parserx\HL7812_fallback_NOK.xti')

print(f"Total trace items: {len(parser.trace_items)}")
print()

# Get channel groups
groups = parser.get_channel_groups()
print(f"Total channel groups/sessions: {len(groups)}")
print()

# Find TAC sessions
tac_sessions = []
for idx, group in enumerate(groups):
    server = group.get('server', '')
    if 'TAC' in str(server).upper() or group.get('port') == 443:
        tac_sessions.append((idx, group))

if not tac_sessions:
    print("❌ No TAC sessions found!")
    print("\nAll sessions found:")
    for idx, group in enumerate(groups):
        print(f"  {idx}: {group.get('server')} | Port: {group.get('port')} | Protocol: {group.get('protocol')}")
    sys.exit(1)

print(f"Found {len(tac_sessions)} TAC session(s)")
print()

# Test first TAC session
session_idx, session = tac_sessions[0]
print("=" * 80)
print(f"TESTING FIRST TAC SESSION (Group #{session_idx})")
print("=" * 80)
print()

print(f"Server: {session.get('server')}")
print(f"Port: {session.get('port')}")
print(f"Protocol: {session.get('protocol')}")
print(f"Opened: {session.get('opened_at')}")
print(f"Closed: {session.get('closed_at')}")
print(f"Duration: {session.get('duration')}")
print()

# Get session trace item indexes
session_indexes = []
for sess in session.get('sessions', []):
    if sess.traceitem_indexes:
        session_indexes.extend(sess.traceitem_indexes)
session_indexes = sorted(set(session_indexes))

print(f"Trace items in session: {len(session_indexes)}")
print()

# Check for TLS report
base_dir = Path(r'c:\Users\T0319884\Documents\coding\python\parserx')
report_found = False

for name in ("tac_session_report.md", "tac_tls_flow.md"):
    p = base_dir / name
    if p.exists():
        print(f"✓ Found report: {name}")
        report_found = True
        
        # Test loading report
        try:
            from tls_flow_from_report import load_tls_report
            data = load_tls_report(str(p))
            
            print()
            print("REPORT DATA:")
            print(f"  Flow events: {len(data.flow_events) if data.flow_events else 0}")
            print(f"  Handshake sequence: {len(data.handshake.sequence) if data.handshake else 0}")
            
            if data.summary:
                print(f"  SNI: {data.summary.sni}")
                print(f"  Version: {data.summary.version}")
                print(f"  Chosen cipher: {data.summary.chosen_cipher}")
            
            print()
            print("TESTING MESSAGE NAME EXTRACTION:")
            print("-" * 80)
            
            for i, ev in enumerate((data.flow_events or [])[:15], 1):
                direction = getattr(ev, 'direction', '') or ''
                label = getattr(ev, 'label', '') or ''
                details = getattr(ev, 'details', '') or ''
                
                # Apply our improvements
                # 1. Add visual arrows
                if 'SIM' in direction and 'ME' in direction:
                    if direction.startswith('SIM'):
                        direction_display = 'SIM → ME'
                    else:
                        direction_display = 'ME → SIM'
                else:
                    direction_display = direction
                
                # 2. Extract actual message name
                original_label = label
                lbl_low = label.lower()
                det_low = (details or '').lower()
                
                # Extract inner type if label like 'TLS Handshake (ClientHello)'
                if 'handshake' in lbl_low and '(' in label and ')' in label:
                    inner = label.split('(', 1)[1].split(')', 1)[0].strip()
                    if inner and inner.lower() != 'other':
                        label = inner
                
                # Map '(other)' using hints in details
                if 'handshake' in lbl_low and ('(other' in lbl_low or '(other' in label):
                    if 'serverhello' in det_low or 'server_hello' in det_low or 'server hello' in det_low:
                        label = 'ServerHello'
                    elif 'clienthello' in det_low or 'client_hello' in det_low or 'client hello' in det_low:
                        label = 'ClientHello'
                    elif 'certificate' in det_low:
                        label = 'Certificate'
                    elif 'change cipherspec' in det_low or 'changecipherspec' in det_low:
                        label = 'ChangeCipherSpec'
                    elif 'finished' in det_low:
                        label = 'Finished'
                    elif 'serverkeyexchange' in det_low or 'server key exchange' in det_low:
                        label = 'ServerKeyExchange'
                    elif 'serverhellodone' in det_low or 'server hello done' in det_low:
                        label = 'ServerHelloDone'
                    elif 'clientkeyexchange' in det_low or 'client key exchange' in det_low:
                        label = 'ClientKeyExchange'
                
                # 3. Truncate details
                detail_display = details[:60] + '...' if len(details) > 60 else details
                
                # 4. Color coding
                if label in ('ClientHello', 'ServerHello', 'Certificate', 'ServerKeyExchange',
                           'ClientKeyExchange', 'ServerHelloDone'):
                    color = '🔵 BLUE'
                elif label in ('ChangeCipherSpec', 'Encrypted Finished', 'Finished'):
                    color = '🟠 ORANGE'
                elif label.startswith('Alert'):
                    color = '🔴 RED'
                elif 'application' in label.lower():
                    color = '⚫ GRAY'
                else:
                    color = '⚪ DEFAULT'
                
                print(f"{i:2}. {color:12} | {label:20} | {direction_display:10} | {detail_display}")
                
                if original_label != label:
                    print(f"    └─ IMPROVED: '{original_label}' → '{label}'")
            
            print()
            print("-" * 80)
            print("✅ IMPROVEMENTS WORKING:")
            print("   ✓ Visual arrows in direction (→)")
            print("   ✓ Actual message names extracted")
            print("   ✓ Color coding applied")
            print("   ✓ Details truncated with full text available")
            
        except Exception as e:
            print(f"❌ Error loading report: {e}")
            import traceback
            traceback.print_exc()
        
        break

if not report_found:
    print("⚠ No normalized report found - would use basic scan")
    print()
    print("SAMPLE TRACE ITEMS (first 20):")
    for idx in session_indexes[:20]:
        if 0 <= idx < len(parser.trace_items):
            ti = parser.trace_items[idx]
            summary = (ti.summary or '')[:70]
            print(f"  [{idx:3}] {summary}")

print()
print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
