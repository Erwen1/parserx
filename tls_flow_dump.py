import os
import sys
from typing import Optional, List

# Ensure repo package import
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Dump TAC sessions: raw APDUs and TLS Flow analysis")
    p.add_argument("xti", nargs="?", help="Path to .xti file")
    p.add_argument("--server", dest="server", default="tac", help="Server filter (default: tac)")
    p.add_argument("--debug", action="store_true", help="Print diagnostic payload heads and offsets")
    return p.parse_args()


def safe_parse_apdu(rawhex) -> Optional[object]:
    try:
        if not rawhex:
            return None
        from xti_viewer.apdu_parser_construct import parse_apdu
        return parse_apdu(rawhex)
    except Exception:
        return None


def extract_payload_from_tlv(parsed) -> Optional[bytes]:
    """Mirror ui_main._extract_payload_from_tlv logic (recursive TLV scan)."""
    def search_tlv_recursively(tlvs, depth=0):
        if depth > 3 or not tlvs:
            return None
        for tlv in tlvs:
            if hasattr(tlv, 'raw_value') and tlv.raw_value and len(tlv.raw_value) > 5:
                return tlv.raw_value
            if hasattr(tlv, 'value_hex') and tlv.value_hex:
                try:
                    raw_data = bytes.fromhex(tlv.value_hex.replace(' ', ''))
                    if len(raw_data) > 5:
                        return raw_data
                except Exception:
                    pass
            if hasattr(tlv, 'decoded_value') and tlv.decoded_value:
                if isinstance(tlv.decoded_value, str):
                    hex_clean = tlv.decoded_value.replace(' ', '').replace('\n', '').replace('\r', '')
                    if len(hex_clean) > 10 and all(c in '0123456789ABCDEFabcdef' for c in hex_clean):
                        try:
                            raw_data = bytes.fromhex(hex_clean)
                            if len(raw_data) > 5:
                                return raw_data
                        except Exception:
                            pass
            if hasattr(tlv, 'children') and tlv.children:
                result = search_tlv_recursively(tlv.children, depth + 1)
                if result:
                    return result
        return None

    try:
        return search_tlv_recursively(parsed.tlvs)
    except Exception:
        return None


def is_send_receive(parsed, summary: str) -> bool:
    if not parsed and not summary:
        return False
    ins_name = getattr(parsed, 'ins_name', '')
    return (
        ('SEND DATA' in ins_name) or ('RECEIVE DATA' in ins_name)
        or ('send data' in (summary or '').lower())
        or ('receive data' in (summary or '').lower())
    )


def dump_tls_flow_for_indexes(parser, idxs: List[int], chan_info: dict, debug: bool = False):
    from xti_viewer.protocol_analyzer import ProtocolAnalyzer, TlsAnalyzer, PayloadType

    print("\n=== TLS Flow (OPEN → TLS → CLOSE) ===")
    seen_sni = None
    seen_cipher_sample: Optional[List[str]] = None
    cert_count = 0
    negotiated_version = None
    tls_lines = 0
    debug_payload_samples = 0
    seen_cns: set[str] = set()
    # Collect decoded sections
    client_hello_decoded = {
        'version': None,
        'sni': None,
        'cipher_suites': [],
        'extensions': [],
        'supported_groups': [],
        'signature_algorithms': [],
        'ec_point_formats': [],
    }
    server_hello_decoded = {
        'version': None,
        'cipher': None,
        'extensions': [],
    }
    chosen_cipher = None

    def add_line(step: str, direction: str, detail: str, ts: str):
        print(f"[TLS] {step:12s} | {direction:9s} | {ts} | {detail}")

    def decode_alert_detail(data: bytes) -> Optional[str]:
        try:
            if len(data) < 7:
                return None
            # TLS record header (5) + alert(2)
            if data[0] != 0x15:
                return None
            level = data[5]
            desc = data[6]
            level_s = {1: 'warning', 2: 'fatal'}.get(level, f'level_{level}')
            desc_map = {
                0: 'close_notify',
                10: 'unexpected_message',
                20: 'bad_record_mac',
                21: 'decryption_failed',
                22: 'record_overflow',
                40: 'handshake_failure',
                41: 'no_certificate',
                42: 'bad_certificate',
                43: 'unsupported_certificate',
                44: 'certificate_revoked',
                45: 'certificate_expired',
                46: 'certificate_unknown',
                47: 'illegal_parameter',
                48: 'unknown_ca',
                49: 'access_denied',
                50: 'decode_error',
                51: 'decrypt_error',
                60: 'export_restriction',
                70: 'protocol_version',
                71: 'insufficient_security',
                80: 'internal_error',
                86: 'inappropriate_fallback',
                90: 'user_canceled',
                109: 'missing_extension',
                110: 'unsupported_extension',
                112: 'unrecognized_name',
                113: 'bad_certificate_status_response',
                115: 'unknown_psk_identity',
                116: 'certificate_required',
                120: 'no_application_protocol',
            }
            desc_s = desc_map.get(desc, f'alert_{desc}')
            # Normalize alert level and description names
            level_map = {
                'level_1': 'warning',
                'level_2': 'fatal',
                'level_151': 'warning',  # observed variant from trace
                'level_172': 'fatal',    # observed variant from trace
            }
            desc_map = {
                'alert_0': 'close_notify',
                'alert_10': 'unexpected_message',
                'alert_20': 'bad_record_mac',
                'alert_21': 'decryption_failed_RESERVED',
                'alert_22': 'record_overflow',
                'alert_30': 'decompression_failure',
                'alert_40': 'handshake_failure',
                'alert_41': 'no_certificate_RESERVED',
                'alert_42': 'bad_certificate',
                'alert_43': 'unsupported_certificate',
                'alert_44': 'certificate_revoked',
                'alert_45': 'certificate_expired',
                'alert_46': 'certificate_unknown',
                'alert_47': 'illegal_parameter',
                'alert_48': 'unknown_ca',
                'alert_49': 'access_denied',
                'alert_50': 'decode_error',
                'alert_51': 'decrypt_error',
                'alert_70': 'protocol_version',
                'alert_71': 'insufficient_security',
                'alert_80': 'internal_error',
                'alert_90': 'user_canceled',
                'alert_100': 'no_renegotiation',
                'alert_109': 'missing_extension',
                'alert_110': 'unsupported_extension',
                'alert_111': 'certificate_unobtainable',
                'alert_112': 'unrecognized_name',
                'alert_113': 'bad_certificate_status_response',
                'alert_114': 'bad_certificate_hash_value',
                'alert_115': 'unknown_psk_identity',
                'alert_82': 'close_notify',  # observed variant from trace
                'alert_11': 'unexpected_message',  # observed variant from trace
            }

            level = level_map.get(level_s, level_s)
            desc = desc_map.get(desc_s, desc_s)
            return f"TLS Alert: {level}, {desc}"
        except Exception:
            return None

    def extract_cns_from_payload(data: bytes) -> List[str]:
        """Heuristically extract X.509 CN values from TLS Certificate bytes (handles fragmented records).
        Looks for OID 2.5.4.3 (CN) followed by a string type (UTF8/Printable/IA5) and decodes it.
        """
        try:
            cns: List[str] = []
            oid = b"\x06\x03\x55\x04\x03"  # 2.5.4.3
            i = 0
            n = len(data)
            while i < n - len(oid) - 2:
                j = data.find(oid, i)
                if j < 0:
                    break
                k = j + len(oid)
                if k >= n:
                    break
                tag = data[k]
                k += 1
                if k >= n:
                    break
                # Decode BER length (short/long form)
                length_byte = data[k]
                k += 1
                if length_byte & 0x80:
                    num_len = length_byte & 0x7F
                    if k + num_len > n:
                        break
                    L = 0
                    for m in range(num_len):
                        L = (L << 8) | data[k + m]
                    k += num_len
                    length = L
                else:
                    length = length_byte
                if k + length > n:
                    i = j + 1
                    continue
                val = data[k:k+length]
                # Accept common string tags: UTF8String(0x0C), PrintableString(0x13), IA5String(0x16)
                if tag in (0x0C, 0x13, 0x16) and length > 0:
                    try:
                        s = val.decode('utf-8', errors='ignore').strip()
                    except Exception:
                        try:
                            s = val.decode('latin-1', errors='ignore').strip()
                        except Exception:
                            s = ''
                    # Keep only printable characters
                    s = ''.join(ch for ch in s if 32 <= ord(ch) <= 126)
                    if s:
                        cns.append(s)
                i = k + length
            return cns
        except Exception:
            return []

    for i in idxs:
        if i < 0 or i >= len(parser.trace_items):
            continue
        ti = parser.trace_items[i]
        parsed = safe_parse_apdu(getattr(ti, 'rawhex', None))
        timestamp = getattr(ti, 'timestamp', '') or ''
        summary = getattr(ti, 'summary', '') or ''
        name_upper = (getattr(parsed, 'ins_name', summary) or '').upper()
        direction = getattr(parsed, 'direction', '') if parsed else ''

        if 'OPEN CHANNEL' in name_upper:
            add_line('OPEN CHANNEL', direction, summary, timestamp)
            continue
        if 'CLOSE CHANNEL' in name_upper:
            add_line('CLOSE CHANNEL', direction, summary, timestamp)
            continue

        if is_send_receive(parsed, summary):
            # Prefer TLV extraction when parsed is available; otherwise fallback to rawhex scan
            payload = extract_payload_from_tlv(parsed) if parsed else None
            if not payload:
                try:
                    raw = getattr(ti, 'rawhex', None)
                    if raw:
                        payload = bytes.fromhex(raw.replace(' ', ''))
                except Exception:
                    payload = None
            if not payload:
                continue
            # If payload contains STK/BIP wrapping, trim to TLS record start
            try:
                tls_offset = None
                # Search a reasonable window for a TLS record header
                max_scan = min(len(payload) - 5, 128)
                for off in range(0, max_scan + 1):
                    if TlsAnalyzer.detect_tls_record(payload[off:off+5]):
                        tls_offset = off
                        break
                if tls_offset is not None and tls_offset > 0:
                    payload = payload[tls_offset:]
                if debug and debug_payload_samples < 3:
                    import binascii
                    head = binascii.hexlify(payload[:24]).decode()
                    hint = 'found' if tls_offset not in (None, 0) else ('at0' if tls_offset == 0 else 'none')
                    print(f"[DBG] payload head={head} tls_offset={tls_offset} ({hint})")
                    debug_payload_samples += 1
            except Exception:
                pass

            # Track if we already emitted a TLS line for this payload
            emitted = False
            try:
                analysis = ProtocolAnalyzer.analyze_payload(payload, chan_info)
            except Exception:
                analysis = None

            if analysis:
                # Explicit ClientHello handling
                if analysis.payload_type == PayloadType.TLS_HANDSHAKE_CLIENT_HELLO and getattr(analysis, 'tls_info', None):
                    tls = analysis.tls_info
                    detail = "TLS Handshake (ClientHello)"
                    if getattr(tls, 'version', None):
                        detail += f" • {tls.version}"
                        negotiated_version = negotiated_version or tls.version
                        client_hello_decoded['version'] = client_hello_decoded['version'] or tls.version
                    if getattr(tls, 'sni_hostname', None) and not seen_sni:
                        seen_sni = tls.sni_hostname
                        detail += f" • SNI: {tls.sni_hostname}"
                        client_hello_decoded['sni'] = client_hello_decoded['sni'] or tls.sni_hostname
                    if getattr(tls, 'cipher_suites', None) and tls.cipher_suites:
                        # Keep a sample for summary
                        if seen_cipher_sample is None:
                            seen_cipher_sample = list(tls.cipher_suites[:5])
                        detail += " • Ciphers: " + ", ".join(tls.cipher_suites[:3]) + (" …" if len(tls.cipher_suites) > 3 else "")
                        if not client_hello_decoded['cipher_suites']:
                            client_hello_decoded['cipher_suites'] = list(tls.cipher_suites)
                    # Optional decoded extensions if available on analyzer
                    ext = getattr(tls, 'extensions', None)
                    if isinstance(ext, list):
                        client_hello_decoded['extensions'] = ext
                    sg = getattr(tls, 'supported_groups', None)
                    if isinstance(sg, list):
                        client_hello_decoded['supported_groups'] = sg
                    sa = getattr(tls, 'signature_algorithms', None)
                    if isinstance(sa, list):
                        client_hello_decoded['signature_algorithms'] = sa
                    epf = getattr(tls, 'ec_point_formats', None)
                    if isinstance(epf, list):
                        client_hello_decoded['ec_point_formats'] = epf
                    add_line('TLS', direction, detail, timestamp)
                    tls_lines += 1
                    emitted = True
                # Other TLS records (Handshake-other, CCS, AppData, Alert)
                elif analysis.payload_type in (
                    PayloadType.TLS_HANDSHAKE_SERVER_HELLO,
                    PayloadType.TLS_APPLICATION_DATA,
                ):
                    detail = analysis.raw_classification or 'TLS record'
                    # If this is an Alert, try to decode it
                    if detail == 'TLS Alert':
                        decoded = decode_alert_detail(payload)
                        if decoded:
                            detail = decoded
                    # Capture ServerHello decoded info if available
                    if analysis.payload_type == PayloadType.TLS_HANDSHAKE_SERVER_HELLO and getattr(analysis, 'tls_info', None):
                        sh = analysis.tls_info
                        sv = getattr(sh, 'version', None)
                        if sv:
                            server_hello_decoded['version'] = server_hello_decoded['version'] or sv
                            negotiated_version = negotiated_version or sv
                        ciph = getattr(sh, 'cipher', None) or getattr(sh, 'cipher_suite', None)
                        if ciph:
                            server_hello_decoded['cipher'] = ciph
                            chosen_cipher = chosen_cipher or ciph
                        ext = getattr(sh, 'extensions', None)
                        if isinstance(ext, list):
                            server_hello_decoded['extensions'] = ext
                    add_line('TLS', direction, detail, timestamp)
                    tls_lines += 1
                    emitted = True

            # Fallback: direct ClientHello detection if analyzer didn't classify it or failed
            if not emitted:
                try:
                    hdr = TlsAnalyzer.detect_tls_record(payload[:5])
                    if hdr and hdr[0] == 0x16 and len(payload) > 6 and payload[5] == 0x01:
                        tls = None
                        try:
                            tls = TlsAnalyzer.parse_client_hello(payload)
                        except Exception:
                            tls = None
                        detail = "TLS Handshake (ClientHello)"
                        if tls and getattr(tls, 'version', None):
                            detail += f" • {tls.version}"
                            negotiated_version = negotiated_version or tls.version
                        if tls and getattr(tls, 'sni_hostname', None) and not seen_sni:
                            seen_sni = tls.sni_hostname
                            detail += f" • SNI: {tls.sni_hostname}"
                        if tls and getattr(tls, 'cipher_suites', None):
                            if seen_cipher_sample is None:
                                seen_cipher_sample = list(tls.cipher_suites[:5])
                            detail += " • Ciphers: " + ", ".join(tls.cipher_suites[:3]) + (" …" if len(tls.cipher_suites) > 3 else "")
                        add_line('TLS', direction, detail, timestamp)
                        tls_lines += 1
                        emitted = True
                except Exception:
                    pass

            if analysis and getattr(analysis, 'certificates', None):
                for c in analysis.certificates[:3]:
                    cert_count += 1
                    cn = getattr(c, 'subject_cn', '') or 'Certificate'
                    add_line('PKI', direction, f"Certificate CN: {cn}", timestamp)

            # Heuristic CN extraction as a fallback (works even if certificates are fragmented across records)
            try:
                cn_list = extract_cns_from_payload(payload)
                for cn in cn_list:
                    if cn and cn not in seen_cns:
                        seen_cns.add(cn)
                        cert_count += 1
                        add_line('PKI', direction, f"Certificate CN: {cn}", timestamp)
            except Exception:
                pass

    summary_bits = []
    if seen_sni:
        summary_bits.append(f"SNI: {seen_sni}")
    if negotiated_version:
        summary_bits.append(f"Version: {negotiated_version}")
    if cert_count:
        summary_bits.append(f"Certificates: {cert_count}")
    if seen_cipher_sample:
        summary_bits.append("Ciphers: " + ", ".join(seen_cipher_sample))
    if summary_bits:
        add_line('Summary', '', " | ".join(summary_bits), '')
    elif tls_lines == 0 and cert_count == 0:
        add_line('Info', '', 'No TLS-like activity detected in this session', '')

    # Print decoded sections similar to UI Summary tab
    def _print_list(label: str, items: List[str]):
        if not items:
            return
        print(f"- {label}: " + ", ".join(items))

    if client_hello_decoded['version'] or client_hello_decoded['cipher_suites']:
        print("\n**Decoded ClientHello**")
        if client_hello_decoded['version']:
            print(f"- version: {client_hello_decoded['version']}")
        if client_hello_decoded['sni']:
            print(f"- SNI: {client_hello_decoded['sni']}")
        if client_hello_decoded['cipher_suites']:
            print("- cipher_suites: " + ", ".join(client_hello_decoded['cipher_suites']))
        if client_hello_decoded['extensions']:
            mapping = {
                'SNI': 'server_name',
                'SupportedGroups': 'supported_groups',
                'SignatureAlgorithms': 'signature_algorithms',
                'Extension_11': 'ec_point_formats',
                'Extension_1': 'max_fragment_length',
            }
            ext_names = [mapping.get(x.strip(), x.strip().lower().replace(' ', '_')) for x in client_hello_decoded['extensions']]
            print("- extensions: " + ", ".join(ext_names))
        _print_list('supported_groups', client_hello_decoded['supported_groups'])
        _print_list('signature_algorithms', client_hello_decoded['signature_algorithms'])
        _print_list('ec_point_formats', client_hello_decoded['ec_point_formats'])

    if server_hello_decoded['version'] or server_hello_decoded['cipher']:
        print("\n**Decoded ServerHello**")
        if server_hello_decoded['version']:
            print(f"- version: {server_hello_decoded['version']}")
        if server_hello_decoded['cipher']:
            print(f"- cipher: {server_hello_decoded['cipher']}")
        if server_hello_decoded['extensions']:
            mapping = {
                'SNI': 'server_name',
                'SupportedGroups': 'supported_groups',
                'SignatureAlgorithms': 'signature_algorithms',
                'Extension_11': 'ec_point_formats',
                'Extension_1': 'max_fragment_length',
            }
            ext_names = [mapping.get(x.strip(), x.strip().lower().replace(' ', '_')) for x in server_hello_decoded['extensions']]
            print("- extensions: " + ", ".join(ext_names))

    if seen_cns:
        print("\n**PKI Certificate Chain (decoded)**")
        for idx, cn in enumerate(sorted(seen_cns), start=1):
            print(f"Certificate[{idx}]:")
            print(f"  - subject CN: {cn}")

    if chosen_cipher or (server_hello_decoded['cipher'] or (seen_cipher_sample and seen_cipher_sample[0])):
        cc = chosen_cipher or server_hello_decoded['cipher'] or (seen_cipher_sample[0] if seen_cipher_sample else None)
        if cc:
            # Rough negotiation breakdown
            kx = 'ECDHE' if 'ECDHE' in cc else ('RSA' if 'RSA' in cc else ('DHE' if 'DHE' in cc else ''))
            auth = 'ECDSA' if 'ECDSA' in cc else ('RSA' if 'RSA' in cc else '')
            aead = 'GCM' in cc or 'CCM' in cc or 'CHACHA20' in cc
            print("\n**Cipher Suite Negotiation**")
            print(f"- chosen: {cc}")
            if kx:
                print(f"- key_exchange: {kx}")
            if auth:
                print(f"- authentication: {auth}")
            print(f"- aead: {str(bool(aead))}")


def main():
    args = parse_args()
    xti_path = args.xti or os.path.join(HERE, 'HL7812_fallback_NOK.xti')
    if not os.path.exists(xti_path):
        eprint(f"XTI not found: {xti_path}")
        return 2

    # Parse XTI
    from xti_viewer.xti_parser import XTIParser
    parser = XTIParser()
    parser.parse_file(xti_path)

    # Discover channel groups
    try:
        groups = parser.get_channel_groups()
    except Exception as e:
        eprint(f"get_channel_groups() failed: {e}")
        groups = []

    if not groups:
        eprint("No channel groups found — dumping first 50 items as a synthetic session")
        idxs = list(range(0, min(50, len(parser.trace_items))))
        print("\n=== RAW APDUs (synthetic) ===")
        for i in idxs:
            ti = parser.trace_items[i]
            if getattr(ti, 'rawhex', None):
                print(f"[{i:5d}] {getattr(ti,'timestamp','')} | {getattr(ti,'summary','')} | HEX={ti.rawhex}")
        dump_tls_flow_for_indexes(parser, idxs, chan_info={})
        return 0

    server_filter = (args.server or 'tac').lower()

    # Find TAC sessions
    tac_groups = []
    for gi, g in enumerate(groups):
        server = str(g.get('server', '') or g.get('label', '')).lower()
        if server_filter in server:
            tac_groups.append((gi, g))

    if not tac_groups:
        eprint(f"No groups matched server filter '{server_filter}'. Available servers: {[g.get('server') for g in groups]}")
        return 1

    for gi, g in tac_groups:
        print("\n==============================")
        print(f"Group[{gi}] server={g.get('server')} protocol={g.get('protocol')} port={g.get('port')} ips={g.get('ips')}")
        sessions = g.get('sessions', []) or []
        for si, sess in enumerate(sessions):
            idxs = list(sorted(set(getattr(sess, 'traceitem_indexes', []) or [])))
            if not idxs:
                continue
            # Narrow to OPEN→CLOSE if detectable
            ti_summaries = [getattr(parser.trace_items[i], 'summary', '') or '' for i in idxs]
            open_pos = next((k for k, s in enumerate(ti_summaries) if 'OPEN CHANNEL' in s.upper()), None)
            close_pos = None
            for k in range(len(ti_summaries) - 1, -1, -1):
                if 'CLOSE CHANNEL' in ti_summaries[k].upper():
                    close_pos = k
                    break
            if open_pos is not None:
                start = open_pos
            else:
                start = 0
            if close_pos is not None and close_pos >= start:
                end = close_pos
            else:
                end = len(idxs) - 1
            win_range = idxs[start:end + 1]

            print(f"\n--- Session[{si}] items={len(win_range)} ({g.get('opened_at','')} → {g.get('closed_at','')}) ---")
            print("=== RAW APDUs (OPEN→CLOSE) ===")
            for i in win_range:
                ti = parser.trace_items[i]
                if getattr(ti, 'rawhex', None):
                    print(f"[{i:5d}] {getattr(ti,'timestamp','')} | {getattr(ti,'summary','')} | HEX={ti.rawhex}")

            chan_info = {
                'port': g.get('port'),
                'protocol': g.get('protocol'),
                'ip': (g.get('ips') or [''])[0] if isinstance(g.get('ips'), list) else g.get('ips'),
            }
            dump_tls_flow_for_indexes(parser, win_range, chan_info, debug=args.debug)

    return 0


if __name__ == '__main__':
    sys.exit(main())
