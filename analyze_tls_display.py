"""
Analyze TLS Flow Tab Display Issues
"""
import sys
sys.path.insert(0, r'c:\Users\T0319884\Documents\coding\python\parserx')

from pathlib import Path
from xti_viewer.xti_parser import XTIParser

# Load test file
parser = XTIParser()
parser.parse_file(r'c:\Users\T0319884\Documents\coding\python\parserx\test.xti')

# Get channel groups (sessions)
groups = parser.get_channel_groups()

print("=" * 80)
print("TLS FLOW TAB ANALYSIS")
print("=" * 80)
print()

# Find TAC sessions
tac_sessions = [g for g in groups if 'TAC' in str(g.get('server', ''))]

if tac_sessions:
    print(f"Found {len(tac_sessions)} TAC session(s)")
    print()
    
    for idx, session in enumerate(tac_sessions[:1], 1):  # Analyze first TAC session
        print(f"SESSION {idx}: {session.get('server')}")
        print(f"  Port: {session.get('port')}")
        print(f"  Protocol: {session.get('protocol')}")
        print(f"  Opened: {session.get('opened_at')}")
        print(f"  Closed: {session.get('closed_at')}")
        print(f"  Duration: {session.get('duration')}")
        print()
        
        # Get session indexes
        session_indexes = []
        for sess in session.get('sessions', []):
            if sess.traceitem_indexes:
                session_indexes.extend(sess.traceitem_indexes)
        session_indexes = sorted(set(session_indexes))
        
        print(f"  Total trace items in session: {len(session_indexes)}")
        print()
        
        # Check if normalized report exists
        base_dir = Path(r'c:\Users\T0319884\Documents\coding\python\parserx')
        report_found = False
        for name in ("tac_session_report.md", "tac_tls_flow.md"):
            p = base_dir / name
            if p.exists():
                print(f"  ✓ Found report: {name}")
                report_found = True
                
                # Load and analyze report
                try:
                    from tls_flow_from_report import load_tls_report
                    data = load_tls_report(str(p))
                    
                    print(f"    Flow events: {len(data.flow_events) if data.flow_events else 0}")
                    print(f"    Handshake sequence: {len(data.handshake.sequence) if data.handshake else 0} steps")
                    
                    if data.summary:
                        print(f"    SNI: {data.summary.sni}")
                        print(f"    Version: {data.summary.version}")
                        print(f"    Chosen cipher: {data.summary.chosen_cipher}")
                        print(f"    Certificates: {data.summary.certificates}")
                    
                    print()
                    print("  FLOW EVENTS SAMPLE (first 10):")
                    for i, ev in enumerate((data.flow_events or [])[:10], 1):
                        print(f"    {i}. {ev.direction} | {ev.label} | {ev.details}")
                    
                    print()
                    print("  HANDSHAKE SEQUENCE:")
                    if data.handshake and data.handshake.sequence:
                        print(f"    {' → '.join(data.handshake.sequence)}")
                    
                    # Check decoded sections
                    print()
                    print("  DECODED SECTIONS:")
                    if data.decoded:
                        if data.decoded.client_hello:
                            print("    ✓ ClientHello decoded")
                            if data.decoded.client_hello.sni:
                                print(f"      SNI: {data.decoded.client_hello.sni}")
                            if data.decoded.client_hello.cipher_suites:
                                print(f"      Cipher suites: {len(data.decoded.client_hello.cipher_suites)}")
                        if data.decoded.server_hello:
                            print("    ✓ ServerHello decoded")
                            if data.decoded.server_hello.cipher:
                                print(f"      Chosen: {data.decoded.server_hello.cipher}")
                        if data.decoded.pki_chain:
                            print("    ✓ PKI Chain decoded")
                            if data.decoded.pki_chain.certificates:
                                print(f"      Certificates: {len(data.decoded.pki_chain.certificates)}")
                        if data.decoded.cipher_suite_negotiation:
                            print("    ✓ Cipher Suite Negotiation decoded")
                    else:
                        print("    ✗ No decoded sections (will use markdown fallback)")
                    
                except Exception as e:
                    print(f"    ✗ Error loading report: {e}")
                
                break
        
        if not report_found:
            print("  ✗ No normalized report found (will use basic scan)")
            print()
            
            # Simulate basic scan
            print("  BASIC SCAN SIMULATION:")
            print("    This would parse trace items and extract TLS records...")
            
            # Check actual trace items
            print()
            print("  TRACE ITEMS SAMPLE (first 10):")
            for idx in session_indexes[:10]:
                if 0 <= idx < len(parser.trace_items):
                    ti = parser.trace_items[idx]
                    print(f"    [{idx}] {ti.summary[:60]}")

print()
print("=" * 80)
print("ISSUES IDENTIFIED:")
print("=" * 80)
print()

issues = []
recommendations = []

# Check for common issues
if not report_found:
    issues.append("1. No normalized TLS report found (tac_session_report.md)")
    recommendations.append("   → Run TLS analysis to generate normalized report")

issues.append("2. Steps tab shows generic badges instead of actual message names")
recommendations.append("   → Show 'ClientHello', 'ServerHello', 'Certificate' instead of 'Handshake'")

issues.append("3. Direction column shows 'SIM→ME' or 'ME→SIM' which may be unclear")
recommendations.append("   → Add visual arrows: → for outgoing, ← for incoming")

issues.append("4. Detail column may be too long and wrapped")
recommendations.append("   → Truncate long details with ellipsis, show full in preview")

issues.append("5. Summary tab has too much information at once")
recommendations.append("   → Group related info with clear visual hierarchy")

issues.append("6. Handshake tab shows sequence as linear text")
recommendations.append("   → Use visual timeline with colored badges and direction indicators")

issues.append("7. Ladder tab shows two-column text")
recommendations.append("   → Add visual connection lines between steps")

issues.append("8. PKI certificates shown as flat list")
recommendations.append("   → Show certificate chain hierarchy visually")

for issue in issues:
    print(issue)

print()
print("RECOMMENDATIONS:")
for rec in recommendations:
    print(rec)

print()
print("=" * 80)
