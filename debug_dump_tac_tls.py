"""Dump TAC session UI + raw + TLS Flow results to terminal.

Usage:
  python debug_dump_tac_tls.py HL7812_fallback_NOK.xti

This script programmatically loads the XTI file using existing parser/UI
classes and simulates the double-click on a TAC session:
  1. Prints the session summary (what the UI shows in TLS summary label)
  2. Prints raw trace items belonging to the TAC session (indexes + hex)
  3. Prints TLS Flow events (Steps tree) with direction, detail, time
  4. Prints handshake label and condensed summary view text
  5. Prints any raw TLS APDU text captured in the Raw tab
"""

from __future__ import annotations
import sys
from pathlib import Path
import argparse

from PySide6.QtWidgets import QApplication

# Optional import of full TLS reconstruction helpers
try:  # pragma: no cover
    from tls_full_reconstruct import (
        TLSReassembler,
        parse_client_hello_details,
        parse_server_hello_details,
        parse_cert_chain,
        scan_der_certificates_from_records,
        cert_summary,
        extract_payload_from_tlv,
    )
except Exception:  # If not available, full mode will be disabled
    TLSReassembler = None  # type: ignore
    parse_client_hello_details = parse_server_hello_details = parse_cert_chain = scan_der_certificates_from_records = cert_summary = extract_payload_from_tlv = None  # type: ignore

def _build_args():
    p = argparse.ArgumentParser(description="Dump TAC session details including TLS analysis")
    p.add_argument("xti_file", help="Path to XTI capture file")
    p.add_argument("--full", action="store_true", help="Include full TLS handshake reconstruction and decoding")
    p.add_argument("--truncate-hex", type=int, default=0, help="Truncate long APDU hex payload display to N chars (0 = no truncate)")
    p.add_argument("--json", action="store_true", help="Emit full TLS section as JSON when --full is used")
    return p


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_dump_tac_tls.py <xti_file> [--full] [--truncate-hex N] [--json]")
        return 1
    args = _build_args().parse_args()
    xti_path = Path(args.xti_file)
    if not xti_path.exists():
        print(f"File not found: {xti_path}")
        return 1

    # Lazy import heavy UI only after checking arguments
    from xti_viewer.xti_parser import XTIParser
    from xti_viewer.ui_main import XTIMainWindow

    app = QApplication.instance() or QApplication([])

    parser = XTIParser()
    try:
        parser.parse_file(str(xti_path))
    except Exception as e:
        print(f"Parse failed: {e}")
        return 1

    win = XTIMainWindow()
    # Provide required attributes normally set by threaded load path
    class _DummyProgress:
        def close(self):
            pass
    win.progress_dialog = _DummyProgress()  # avoid attribute error in on_parsing_finished
    win.current_file_path = str(xti_path)   # used for status/title updates

    # Directly invoke post-parse logic (bypassing thread machinery)
    try:
        win.on_parsing_finished(parser)
    except Exception as e:
        print(f"Failed to initialize UI models: {e}")
        return 1

    groups = []
    try:
        groups = parser.get_channel_groups()
    except Exception as e:
        print(f"Failed to get channel groups: {e}")
        return 1

    tac_groups = [g for g in groups if str(g.get("server", "")).upper() == "TAC"]
    if not tac_groups:
        print("No TAC session found in this capture.")
        return 0

    # Take first TAC group
    session_data = tac_groups[0]

    print("\n=== TAC Session Summary (Raw Group Data) ===")
    for k in ["server", "protocol", "port", "opened_at", "closed_at", "duration", "ips"]:
        v = session_data.get(k)
        if isinstance(v, list):
            v = ", ".join(map(str, v))
        print(f"{k}: {v}")

    # Collect raw trace items for this session
    session_indexes = []
    try:
        # Each entry has a 'sessions' list of ChannelSession objects
        for s in session_data.get("sessions", []):
            session_indexes.extend(s.traceitem_indexes)
    except Exception:
        pass
    session_indexes = sorted(set(session_indexes))

    print("\n=== Raw Trace Items In TAC Session ===")
    trace_items = parser.trace_items
    for idx in session_indexes:
        if 0 <= idx < len(trace_items):
            ti = trace_items[idx]
            rawhex = (ti.rawhex or "").upper()
            if args.truncate_hex and len(rawhex) > args.truncate_hex:
                display_hex = rawhex[:args.truncate_hex] + f"...(+{len(rawhex)-args.truncate_hex})"
            else:
                display_hex = rawhex
            print(f"[{idx}] {ti.timestamp or ''} | {ti.protocol or ''} | {ti.type or ''} | {ti.summary} | HEX({len(rawhex)}): {display_hex}")

    # Simulate TLS population path (same as double-click). Prefer report, fallback to basic scan.
    populated = False
    try:
        populated = win._populate_tls_from_report(session_data)  # type: ignore[attr-defined]
    except Exception:
        populated = False
    if not populated:
        try:
            populated = win._populate_tls_from_basic_scan(session_data)  # type: ignore[attr-defined]
        except Exception:
            populated = False

    print("\n=== TLS Flow Population Result ===")
    print(f"Populated: {populated}")

    # Extract UI fields now populated
    def safe_txt(obj, attr, default=""):
        try:
            o = getattr(obj, attr, None)
            if o is None:
                return default
            # QTextEdit or QLabel differences
            if hasattr(o, "toPlainText"):
                return o.toPlainText()
            if hasattr(o, "text"):
                return o.text()
            return str(o)
        except Exception:
            return default

    print("\n--- TLS Summary Label ---")
    print(safe_txt(win, "tls_summary_label"))
    print("\n--- TLS Summary View ---")
    print(safe_txt(win, "tls_summary_view"))
    print("\n--- TLS Handshake Label ---")
    print(safe_txt(win, "tls_handshake_label"))
    print("\n--- TLS Raw Text ---")
    raw_block = safe_txt(win, "tls_raw_text")
    if raw_block.strip():
        print(raw_block)
    else:
        print("(empty)")

    # Steps tree events
    print("\n=== TLS Flow Events (Steps Tab) ===")
    try:
        tree = getattr(win, "tls_tree", None)
        if tree is None:
            print("No tls_tree available")
        else:
            count = tree.topLevelItemCount()
            print(f"Total events: {count}")
            for i in range(count):
                item = tree.topLevelItem(i)
                if not item:
                    continue
                step = item.text(0)
                direction = item.text(1)
                detail = item.text(2)
                time = item.text(3)
                print(f"{i:03d}: Step={step} | Dir={direction} | Detail={detail} | Time={time}")
    except Exception as e:
        print(f"Failed to enumerate TLS events: {e}")

    # Optional full TLS reconstruction section
    if args.full and TLSReassembler is not None:
        try:
            print("\n=== Full TLS Handshake Reconstruction (Detailed) ===")
            from xti_viewer.apdu_parser_construct import parse_apdu  # local import
            reasm = TLSReassembler()
            for i in session_indexes:
                ti = parser.trace_items[i]
                rawhex = getattr(ti, 'rawhex', '')
                if not rawhex:
                    continue
                parsed = parse_apdu(rawhex)
                if not parsed:
                    continue
                name = (parsed.ins_name or '').upper()
                summ = (getattr(ti, 'summary', '') or '').upper()
                if all(x not in name for x in ('SEND DATA','RECEIVE DATA')) and all(x not in summ for x in ('SEND DATA','RECEIVE DATA')):
                    continue
                payload = extract_payload_from_tlv(parsed) if extract_payload_from_tlv else None
                if not payload:
                    try:
                        payload = bytes.fromhex(rawhex.replace(' ', ''))
                    except Exception:
                        payload = None
                if not payload:
                    continue
                direction = getattr(parsed, 'direction', '') or 'SIM->ME'
                reasm.feed_bytes(direction, payload)

            chronological = [(seq, d, t, r) for seq, d, t, r in sorted(reasm.all_records, key=lambda q: q[0])]

            # Assemble full handshake messages preserving completion sequence for ordering
            def assemble_handshakes(records):
                msgs = []  # (completion_seq, hs_type, full_record_bytes)
                cur_type = None
                needed = 0
                body_buf = bytearray()
                header_buf = bytearray()
                header_needed = 4
                version_bytes = b"\x03\x03"  # default TLS 1.2
                for seq, _dir, ctype, rec in records:
                    if ctype != 0x16:
                        continue
                    frag = rec[5:5 + ((rec[3] << 8) | rec[4])]
                    j = 0
                    m = len(frag)
                    if len(rec) >= 5:
                        version_bytes = rec[1:3]  # capture latest seen version
                    while j < m:
                        # Need header if starting new handshake message
                        if cur_type is None and header_needed > 0:
                            take_h = min(header_needed, m - j)
                            header_buf.extend(frag[j:j+take_h])
                            j += take_h
                            header_needed -= take_h
                            if header_needed > 0:
                                continue
                            if len(header_buf) == 4:
                                cur_type = header_buf[0]
                                needed = (header_buf[1] << 16) | (header_buf[2] << 8) | header_buf[3]
                                orig_len = needed
                            else:
                                cur_type = None; needed = 0; header_needed = 4; header_buf.clear(); continue
                            header_buf.clear()
                        take = min(needed, m - j)
                        if take > 0:
                            body_buf.extend(frag[j:j+take])
                            j += take
                            needed -= take
                        if needed == 0 and cur_type is not None:
                            # Build synthetic complete record for parser helpers
                            total_len = 4 + len(body_buf)
                            record = b"\x16" + version_bytes + total_len.to_bytes(2, 'big') + bytes([cur_type]) + orig_len.to_bytes(3, 'big') + bytes(body_buf)
                            msgs.append((seq, cur_type, record))
                            cur_type = None
                            body_buf.clear()
                            header_needed = 4
                return msgs

            handshake_msgs = assemble_handshakes(chronological)

            # Build timeline in chronological order inserting handshake events at completion sequence
            timeline = []
            clienthello = None
            serverhello = None
            after_ccs = False
            # Map completion_seq to handshake message(s) (multiple could finish on same record)
            hs_by_seq = {}
            for seq, hs_type, record in handshake_msgs:
                hs_by_seq.setdefault(seq, []).append((hs_type, record))

            for seq, d, ctype, rec in chronological:
                if ctype == 0x14:  # CCS
                    timeline.append('ChangeCipherSpec')
                    after_ccs = True
                elif ctype == 0x17:
                    timeline.append('ApplicationData')
                elif ctype == 0x15:
                    timeline.append('Alert')
                # Insert any handshake messages completing at this seq
                if seq in hs_by_seq:
                    for hs_type, full_rec in hs_by_seq[seq]:
                        name = None
                        if hs_type == 0x01 and not clienthello:
                            clienthello = parse_client_hello_details(full_rec) if parse_client_hello_details else None
                            name = 'ClientHello'
                        elif hs_type == 0x02 and not serverhello:
                            serverhello = parse_server_hello_details(full_rec) if parse_server_hello_details else None
                            name = 'ServerHello'
                        elif hs_type == 0x0B:
                            name = 'Certificate'
                        elif hs_type == 0x0C:
                            name = 'ServerKeyExchange'
                        elif hs_type == 0x0E:
                            name = 'ServerHelloDone'
                        elif hs_type == 0x10:
                            name = 'ClientKeyExchange'
                        elif hs_type == 0x14:
                            name = 'Encrypted Finished' if after_ccs else 'Finished'
                        else:
                            name = 'Handshake(other)' if not after_ccs else 'Encrypted Handshake'
                        timeline.append(name)

            # Collapse adjacent duplicate handshake(other) or Encrypted Handshake entries for readability
            cleaned = []
            for ev in timeline:
                if cleaned and cleaned[-1] == ev and ('Handshake' in ev):
                    continue
                cleaned.append(ev)
            timeline = cleaned

            # Inject Encrypted Finished placeholders after each ChangeCipherSpec if missing
            enhanced = []
            for i, ev in enumerate(timeline):
                enhanced.append(ev)
                if ev == 'ChangeCipherSpec':
                    nxt = timeline[i+1] if i + 1 < len(timeline) else None
                    if nxt not in ('Finished', 'Encrypted Finished'):
                        enhanced.append('Encrypted Finished')
            timeline = enhanced

            sim_me_records = [r for _, r in reasm.records.get('SIM->ME', [])]
            me_sim_records = [r for _, r in reasm.records.get('ME->SIM', [])]
            certs = []
            if parse_cert_chain:
                certs.extend(parse_cert_chain(sim_me_records))
                certs.extend(parse_cert_chain(me_sim_records))
            if not certs and scan_der_certificates_from_records:
                certs = scan_der_certificates_from_records(sim_me_records + me_sim_records)
            chosen = serverhello['cipher'] if serverhello else None

            if args.json:
                import json
                out = {
                    'summary': {
                        'sni': clienthello.get('sni') if clienthello else None,
                        'version': clienthello.get('version') if clienthello else serverhello.get('version') if serverhello else None,
                        'chosen_cipher': chosen,
                        'certificates': len(certs),
                        'opened_at': session_data.get('opened_at'),
                        'closed_at': session_data.get('closed_at'),
                    },
                    'timeline': ['OPEN CHANNEL'] + timeline + ['CLOSE CHANNEL'],
                    'clienthello': clienthello,
                    'serverhello': serverhello,
                    'certificates': [cert_summary(c) for c in certs] if cert_summary else [],
                }
                print(json.dumps(out, indent=2))
            else:
                print("Summary")
                print(f"- SNI: {clienthello.get('sni') if clienthello else None}")
                print(f"- Version: {clienthello.get('version') if clienthello else serverhello.get('version') if serverhello else None}")
                print(f"- Chosen Cipher: {chosen}")
                print(f"- Certificates: {len(certs)}")
                print(f"- Opened At: {session_data.get('opened_at')}")
                print(f"- Closed At: {session_data.get('closed_at')}")
                print("\nFull TLS Handshake Reconstruction")
                print("- " + " → ".join(['OPEN CHANNEL'] + timeline + ['CLOSE CHANNEL']))
                print("\nDecoded ClientHello")
                if clienthello:
                    for k in ['version','random','session_id']:
                        print(f"- {k}: {clienthello[k]}")
                    print(f"- cipher_suites: {', '.join(clienthello['cipher_suites'])}")
                    print(f"- compression_methods: {clienthello['compression_methods']}")
                    print(f"- extensions: {', '.join(clienthello['extensions'])}")
                    print(f"- SNI: {clienthello['sni']}")
                    print(f"- supported_groups: {clienthello['groups']}")
                    print(f"- signature_algorithms: {clienthello['signature_algorithms']}")
                    print(f"- alpn: {clienthello['alpn']}")
                    print(f"- ec_point_formats: {clienthello['ec_point_formats']}")
                    print(f"- renegotiation_info: {clienthello['renegotiation_info']}")
                else:
                    print("- ClientHello not fully decoded")
                print("\nDecoded ServerHello")
                if serverhello:
                    for k in ['version','random','session_id','cipher','compression','extensions']:
                        print(f"- {k}: {serverhello[k]}")
                else:
                    print("- ServerHello not fully decoded")
                print("\nPKI Certificate Chain (decoded)")
                if certs and cert_summary:
                    for ci, cert in enumerate(certs, 1):
                        info = cert_summary(cert)
                        print(f"Certificate[{ci}]:")
                        for k, v in info.items():
                            print(f"  - {k}: {v}")
                else:
                    print("- No certificates decoded")
                print("\nCipher Suite Negotiation")
                if chosen:
                    aead = ('GCM' in chosen)
                    ecdhe = ('ECDHE' in chosen)
                    ecdsa = ('ECDSA' in chosen)
                    print(f"- chosen: {chosen}")
                    print(f"- key_exchange: {'ECDHE' if ecdhe else 'RSA'}")
                    print(f"- authentication: {'ECDSA' if ecdsa else 'RSA'}")
                    print(f"- aead: {aead}")
                else:
                    print("- No chosen cipher decoded")
                print("\nSession Timeline")
                for ev in timeline:
                    print(f"- {ev}")
                print("\nSecurity Evaluation")
                if chosen:
                    issues = []
                    if 'CBC' in chosen:
                        issues.append('Uses CBC (legacy, not AEAD)')
                    if 'RSA_WITH_' in chosen and 'ECDHE' not in chosen:
                        issues.append('No forward secrecy (RSA key exchange)')
                    if not issues:
                        print("- OK: Modern AEAD/ECDHE detected")
                    else:
                        for it in issues:
                            print(f"- {it}")
                else:
                    print("- Unable to evaluate without chosen cipher")
        except Exception as e:
            print(f"Full TLS reconstruction failed: {e}")

    print("\n=== Done ===")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
