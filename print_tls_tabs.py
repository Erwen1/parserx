"""
Print the content of all three TLS Flow tabs (Messages, Overview, Security) for the first TAC session.
"""
from pathlib import Path
from xti_viewer.xti_parser import XTIParser
from tls_flow_from_report import load_tls_report

def print_separator(title):
    """Print a section separator."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def print_messages_tab(data):
    """Print Messages tab content (TLS flow events grouped by phase)."""
    print_separator("MESSAGES TAB")
    
    flow_events = getattr(data, 'flow_events', None)
    if not flow_events:
        print("No flow events found.")
        return
    
    # Group messages by phase
    handshake_phase = []
    data_phase = []
    closure_phase = []
    
    for ev in flow_events:
        label = getattr(ev, 'label', '') or ''
        direction = getattr(ev, 'direction', '') or ''
        details = getattr(ev, 'details', '') or ''
        timestamp = getattr(ev, 'timestamp', '') or ''
        
        # Categorize by phase
        if any(x in label for x in ('Hello', 'Certificate', 'KeyExchange', 'Cipher', 'Finished')):
            handshake_phase.append((label, direction, details, timestamp))
        elif 'ApplicationData' in label or 'Data' in label:
            data_phase.append((label, direction, details, timestamp))
        elif 'Alert' in label or 'close' in label.lower():
            closure_phase.append((label, direction, details, timestamp))
        else:
            handshake_phase.append((label, direction, details, timestamp))
    
    # Print Handshake Phase
    if handshake_phase:
        print("📋 HANDSHAKE PHASE")
        print("-" * 80)
        for label, direction, details, timestamp in handshake_phase:
            arrow = "→" if "Client" in direction or "Sent" in direction else "←" if direction else ""
            print(f"  {label:<30} {arrow} {direction:<15} {details}")
            if timestamp:
                print(f"    Time: {timestamp}")
        print()
    
    # Print Application Data Phase
    if data_phase:
        print("📊 APPLICATION DATA PHASE")
        print("-" * 80)
        for label, direction, details, timestamp in data_phase:
            arrow = "→" if "Client" in direction or "Sent" in direction else "←" if direction else ""
            print(f"  {label:<30} {arrow} {direction:<15} {details}")
            if timestamp:
                print(f"    Time: {timestamp}")
        print()
    
    # Print Closure Phase
    if closure_phase:
        print("🔒 CLOSURE PHASE")
        print("-" * 80)
        for label, direction, details, timestamp in closure_phase:
            arrow = "→" if "Client" in direction or "Sent" in direction else "←" if direction else ""
            print(f"  {label:<30} {arrow} {direction:<15} {details}")
            if timestamp:
                print(f"    Time: {timestamp}")
        print()

def print_overview_tab(data, session_data):
    """Print Overview tab content (session summary, security config, statistics, decoded sections)."""
    print_separator("OVERVIEW TAB")
    
    summ = getattr(data, 'summary', None)
    if not summ:
        print("No summary data found.")
        return
    
    server = session_data.get('server') or 'Unknown'
    port = session_data.get('port') or 'N/A'
    protocol = session_data.get('protocol') or 'TCP'
    duration = session_data.get('duration') or 'N/A'
    ips = session_data.get('ips') or []
    ip_text = ", ".join(ips) if isinstance(ips, list) else str(ips)
    
    # Session Overview
    print("📋 SESSION OVERVIEW")
    print("-" * 80)
    print(f"Server:         {server}")
    print(f"Protocol:       {protocol}")
    print(f"Port:           {port}")
    print(f"Duration:       {duration}")
    print(f"IP:             {ip_text}")
    if summ.sni:
        print(f"SNI:            {summ.sni}")
    print()
    
    # Security Configuration
    print("🔐 SECURITY CONFIGURATION")
    print("-" * 80)
    if summ.version:
        print(f"Version:        {summ.version}")
    if summ.chosen_cipher:
        print(f"Cipher Suite:   {summ.chosen_cipher}")
        
        # Security badges
        badges = []
        if 'ECDHE' in summ.chosen_cipher or 'DHE' in summ.chosen_cipher:
            badges.append("✓ Perfect Forward Secrecy")
        if 'GCM' in summ.chosen_cipher or 'CHACHA20' in summ.chosen_cipher:
            badges.append("✓ AEAD Mode")
        if 'AES_256' in summ.chosen_cipher:
            badges.append("256-bit Encryption")
        elif 'AES_128' in summ.chosen_cipher:
            badges.append("128-bit Encryption")
        
        if badges:
            print(f"Features:       {', '.join(badges)}")
    
    if summ.certificates is not None and summ.certificates > 0:
        print(f"Certificates:   {summ.certificates}")
    print()
    
    # Message Statistics
    print("📊 MESSAGE STATISTICS")
    print("-" * 80)
    flow_events = getattr(data, 'flow_events', None) or []
    handshake_count = sum(1 for ev in flow_events if any(x in (getattr(ev, 'label', '') or '') for x in ('Hello', 'Certificate', 'KeyExchange', 'Cipher', 'Finished')))
    data_count = sum(1 for ev in flow_events if 'ApplicationData' in (getattr(ev, 'label', '') or ''))
    alert_count = sum(1 for ev in flow_events if 'Alert' in (getattr(ev, 'label', '') or ''))
    
    print(f"Handshake:      {handshake_count}")
    print(f"App Data:       {data_count}")
    print(f"Alerts:         {alert_count}")
    print(f"Total:          {len(flow_events)}")
    print()
    
    # Handshake Flow
    print("🔄 HANDSHAKE FLOW")
    print("-" * 80)
    flow_labels = [getattr(ev, 'label', '') or '' for ev in flow_events]
    print(" → ".join(flow_labels[:15]))  # First 15 messages
    if len(flow_labels) > 15:
        print(f"... and {len(flow_labels) - 15} more messages")
    print()
    
    # Decoded sections
    decoded = getattr(data, 'decoded', None)
    if decoded:
        # ClientHello
        ch = getattr(decoded, 'client_hello', None)
        if ch:
            print("📤 DECODED CLIENTHELLO")
            print("-" * 80)
            if getattr(ch, 'version', None):
                print(f"Version:            {ch.version}")
            if getattr(ch, 'cipher_suites', None):
                ciphers = ch.cipher_suites[:5] if len(ch.cipher_suites) > 5 else ch.cipher_suites
                print(f"Cipher Suites:      {', '.join(ciphers)}")
                if len(ch.cipher_suites) > 5:
                    print(f"                    (+{len(ch.cipher_suites) - 5} more)")
            if getattr(ch, 'sni', None):
                print(f"SNI:                {ch.sni}")
            if getattr(ch, 'extensions', None):
                print(f"Extensions:         {', '.join(ch.extensions)}")
            if getattr(ch, 'supported_groups', None):
                print(f"Supported Groups:   {ch.supported_groups}")
            if getattr(ch, 'signature_algorithms', None):
                print(f"Signature Algos:    {ch.signature_algorithms}")
            print()
        
        # ServerHello
        sh = getattr(decoded, 'server_hello', None)
        if sh:
            print("📥 DECODED SERVERHELLO")
            print("-" * 80)
            if getattr(sh, 'version', None):
                print(f"Version:        {sh.version}")
            if getattr(sh, 'cipher', None):
                print(f"Chosen Cipher:  {sh.cipher}")
            if getattr(sh, 'extensions', None):
                print(f"Extensions:     {sh.extensions}")
            if getattr(sh, 'compression', None) is not None:
                print(f"Compression:    {sh.compression}")
            print()
        
        # PKI Certificate Chain
        pki = getattr(decoded, 'pki_chain', None)
        if pki and getattr(pki, 'certificates', None):
            print("📜 PKI CERTIFICATE CHAIN")
            print("-" * 80)
            certs = pki.certificates
            print(f"Total Certificates: {len(certs)}\n")
            for idx, cert in enumerate(certs, start=1):
                print(f"  Certificate #{idx}")
                if getattr(cert, 'subject', None):
                    print(f"    Subject:    {cert.subject}")
                if getattr(cert, 'issuer', None):
                    print(f"    Issuer:     {cert.issuer}")
                if getattr(cert, 'valid_from', None) and getattr(cert, 'valid_to', None):
                    print(f"    Validity:   {cert.valid_from} → {cert.valid_to}")
                if getattr(cert, 'public_key', None):
                    print(f"    Public Key: {cert.public_key}")
                print()
        
        # Cipher Suite Negotiation
        csn = getattr(decoded, 'cipher_suite_negotiation', None)
        if csn:
            print("🔑 CIPHER SUITE NEGOTIATION")
            print("-" * 80)
            if getattr(csn, 'chosen', None):
                print(f"Chosen:         {csn.chosen}")
            if getattr(csn, 'key_exchange', None):
                print(f"Key Exchange:   {csn.key_exchange}")
            if getattr(csn, 'authentication', None):
                print(f"Authentication: {csn.authentication}")
            if getattr(csn, 'aead', None) is not None:
                print(f"AEAD:           {csn.aead}")
            print()

def print_security_tab(data):
    """Print Security tab content (ladder diagram, cipher analysis, certificates, raw APDUs)."""
    print_separator("SECURITY TAB")
    
    summ = getattr(data, 'summary', None)
    handshake = getattr(data, 'handshake', None)
    
    # ASCII Ladder Diagram (using flow_events instead)
    flow_events = getattr(data, 'flow_events', None)
    if flow_events:
        print("🪜 ASCII LADDER DIAGRAM")
        print("-" * 80)
        print("Client                                                    Server")
        print("   |                                                          |")
        
        for ev in flow_events:
            label = getattr(ev, 'label', '') or ''
            direction = getattr(ev, 'direction', '') or ''
            timestamp = getattr(ev, 'timestamp', '') or ''
            
            if 'ME->SIM' in direction:
                # Client → Server
                arrow = f"{label} ─────────────────────────────────>"
                print(f"   {arrow}")
            else:
                # Server → Client  
                arrow = f"<───────────────────────────────── {label}"
                print(f"   {arrow}")
            
            if timestamp:
                print(f"   [{timestamp}]")
        
        print("   |                                                          |")
        print()
    
    # Cipher Suite Analysis
    if summ:
        print("🔐 CIPHER SUITE ANALYSIS")
        print("-" * 80)
        if summ.version:
            print(f"TLS Version:      {summ.version}")
        if summ.chosen_cipher:
            print(f"Cipher Suite:     {summ.chosen_cipher}")
            
            # Analysis
            analysis = []
            if 'ECDHE' in summ.chosen_cipher or 'DHE' in summ.chosen_cipher:
                analysis.append("✓ Perfect Forward Secrecy (ephemeral keys)")
            if 'GCM' in summ.chosen_cipher or 'CHACHA20' in summ.chosen_cipher:
                analysis.append("✓ AEAD mode (authenticated encryption)")
            if 'ECDSA' in summ.chosen_cipher:
                analysis.append("✓ ECDSA authentication")
            elif 'RSA' in summ.chosen_cipher:
                analysis.append("✓ RSA authentication")
            
            if analysis:
                print("\nSecurity Features:")
                for feature in analysis:
                    print(f"  {feature}")
        print()
    
    # Certificate Chain
    decoded = getattr(data, 'decoded', None)
    if decoded:
        pki = getattr(decoded, 'pki_chain', None)
        if pki and getattr(pki, 'certificates', None):
            print("📜 CERTIFICATE CHAIN DETAILS")
            print("-" * 80)
            certs = pki.certificates
            for idx, cert in enumerate(certs, start=1):
                print(f"\nCertificate #{idx}:")
                print("─" * 40)
                if getattr(cert, 'subject', None):
                    print(f"Subject:           {cert.subject}")
                if getattr(cert, 'issuer', None):
                    print(f"Issuer:            {cert.issuer}")
                if getattr(cert, 'valid_from', None):
                    print(f"Valid From:        {cert.valid_from}")
                if getattr(cert, 'valid_to', None):
                    print(f"Valid To:          {cert.valid_to}")
                if getattr(cert, 'public_key', None):
                    print(f"Public Key:        {cert.public_key}")
                if getattr(cert, 'signature_algorithm', None):
                    print(f"Signature:         {cert.signature_algorithm}")
                if getattr(cert, 'subject_alternative_names', None):
                    san = cert.subject_alternative_names
                    if isinstance(san, list):
                        print(f"SAN:               {', '.join(san[:3])}")
                        if len(san) > 3:
                            print(f"                   (+{len(san) - 3} more)")
                    else:
                        print(f"SAN:               {san}")
            print()
    
    # Raw APDUs (summary)
    raw_apdus = getattr(data, 'raw_apdus', None)
    if raw_apdus:
        print("📋 RAW APDUs SUMMARY")
        print("-" * 80)
        print(f"Total APDUs: {len(raw_apdus)}")
        print("\nFirst 5 APDUs:")
        for idx, apdu in enumerate(raw_apdus[:5], start=1):
            direction = getattr(apdu, 'direction', '') or ''
            hex_data = getattr(apdu, 'hex', '') or ''
            timestamp = getattr(apdu, 'timestamp', '') or ''
            
            arrow = "→" if "Sent" in direction else "←"
            hex_preview = hex_data[:40] + "..." if len(hex_data) > 40 else hex_data
            print(f"  {idx}. {arrow} {hex_preview} [{timestamp}]")
        print()

def main():
    """Main function to print TLS Flow tabs for HL7812 first TAC session."""
    # Path to HL7812 file
    xti_file = Path("HL7812_fallback_NOK.xti")
    
    if not xti_file.exists():
        print(f"Error: {xti_file} not found!")
        return
    
    print(f"Loading {xti_file}...")
    parser = XTIParser()
    parser.parse_file(str(xti_file))
    
    # Find first TAC session
    groups = parser.get_channel_groups()
    tac_session = None
    
    for group in groups:
        server = group.get('server', '') or group.get('label', '')
        if 'TAC' in server.upper():
            tac_session = group
            break
    
    if not tac_session:
        print("No TAC session found!")
        return
    
    print(f"Found TAC session: {tac_session.get('server', 'Unknown')}")
    print(f"Port: {tac_session.get('port', 'N/A')}")
    print(f"Duration: {tac_session.get('duration', 'N/A')}")
    
    # Load TLS report
    base_dir = xti_file.parent
    report_path = None
    for name in ("tac_session_report.md", "tac_tls_flow.md"):
        p = base_dir / name
        if p.exists():
            report_path = p
            break
    
    if not report_path:
        print("\nNo TLS report found. Run the TAC session analyzer first.")
        return
    
    print(f"Loading TLS report from {report_path}...")
    data = load_tls_report(str(report_path))
    
    # Print all three tabs
    print_messages_tab(data)
    print_overview_tab(data, tac_session)
    print_security_tab(data)
    
    print("\n" + "=" * 80)
    print("  COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    main()
