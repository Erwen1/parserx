import os
import sys
from typing import List, Optional, Tuple, Dict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from xti_viewer.xti_parser import XTIParser
from xti_viewer.apdu_parser_construct import parse_apdu
from xti_viewer.protocol_analyzer import TlsAnalyzer

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.x509.oid import NameOID, ExtensionOID, ExtendedKeyUsageOID


def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)


def extract_payload_from_tlv(parsed) -> Optional[bytes]:
    def rec(tlvs, depth=0):
        if depth > 4 or not tlvs:
            return None
        for t in tlvs:
            if hasattr(t, 'raw_value') and t.raw_value and len(t.raw_value) > 5:
                return t.raw_value
            if hasattr(t, 'value_hex') and t.value_hex:
                try:
                    b = bytes.fromhex(t.value_hex.replace(' ', ''))
                    if len(b) > 5:
                        return b
                except Exception:
                    pass
            if hasattr(t, 'decoded_value') and t.decoded_value:
                if isinstance(t.decoded_value, str):
                    hx = t.decoded_value.replace(' ', '').replace('\n', '').replace('\r', '')
                    if len(hx) > 10 and all(c in '0123456789ABCDEFabcdef' for c in hx):
                        try:
                            b = bytes.fromhex(hx)
                            if len(b) > 5:
                                return b
                        except Exception:
                            pass
            if hasattr(t, 'children') and t.children:
                v = rec(t.children, depth+1)
                if v:
                    return v
        return None
    try:
        return rec(parsed.tlvs)
    except Exception:
        return None


def align_tls_start(payload: bytes) -> bytes:
    if not payload or len(payload) < 5:
        return payload
    max_scan = min(len(payload) - 5, 128)
    for off in range(0, max_scan + 1):
        if TlsAnalyzer.detect_tls_record(payload[off:off+5]):
            return payload[off:]
    return payload


class TLSReassembler:
    def __init__(self):
        self.buffers: Dict[str, bytearray] = { 'SIM->ME': bytearray(), 'ME->SIM': bytearray() }
        self.records: Dict[str, List[Tuple[int, bytes]]] = { 'SIM->ME': [], 'ME->SIM': [] }
        self.sequence: int = 0
        self.all_records: List[Tuple[int, str, int, bytes]] = []  # (seq, direction, type, record)

    def _extract_records_from_buffer(self, direction: str):
        buf = self.buffers[direction]
        i = 0
        # Search for TLS headers and extract complete records
        while True:
            # Find header
            start = -1
            scan_limit = max(0, len(buf) - 4)
            for off in range(0, scan_limit):
                if TlsAnalyzer.detect_tls_record(buf[off:off+5]):
                    start = off
                    break
            if start == -1:
                # Keep last 4 bytes to catch split headers
                if len(buf) > 4:
                    del buf[:-4]
                break
            if start > 0:
                del buf[:start]
            if len(buf) < 5:
                break
            length = (buf[3] << 8) | buf[4]
            total = 5 + length
            if len(buf) < total:
                break
            rec = bytes(buf[:total])
            self.records[direction].append((rec[0], rec))
            self.sequence += 1
            self.all_records.append((self.sequence, direction, rec[0], rec))
            del buf[:total]

    def feed_bytes(self, direction: str, data: bytes):
        if not data:
            return
        self.buffers[direction].extend(data)
        self._extract_records_from_buffer(direction)

    def iter_records(self, direction: str):
        for typ, rec in self.records[direction]:
            yield typ, rec


def iter_tls_records(payload: bytes):
    i = 0
    n = len(payload)
    while i + 5 <= n:
        hdr = payload[i:i+5]
        det = TlsAnalyzer.detect_tls_record(hdr)
        if not det:
            i += 1
            continue
        length = (hdr[3] << 8) | hdr[4]
        end = i + 5 + length
        if end > n:
            # incomplete record; stop
            break
        yield payload[i:end]
        i = end


def parse_client_hello_details(rec: bytes) -> Optional[dict]:
    try:
        if rec[0] != 0x16 or rec[5] != 0x01:
            return None
        p = 5 + 4  # HS header
        vmaj, vmin = rec[p], rec[p+1]; p += 2
        rnd = rec[p:p+32]; p += 32
        sid_len = rec[p]; p += 1
        sid = rec[p:p+sid_len]; p += sid_len
        cs_len = (rec[p] << 8) | rec[p+1]; p += 2
        suites = []
        for j in range(0, cs_len, 2):
            cid = (rec[p+j] << 8) | rec[p+j+1]
            suites.append(TlsAnalyzer.CIPHER_SUITES.get(cid, f"Unknown_0x{cid:04X}"))
        p += cs_len
        comp_len = rec[p]; p += 1
        comp = list(rec[p:p+comp_len]); p += comp_len
        exts = []
        sni = None
        groups = []
        sigalgs = []
        alpn = []
        ec_point_formats = []
        reneg_info = None
        if p + 2 <= len(rec):
            ext_total = (rec[p] << 8) | rec[p+1]
            p += 2
            end = p + ext_total
            while p + 4 <= end and end <= len(rec):
                etype = (rec[p] << 8) | rec[p+1]; elen = (rec[p+2] << 8) | rec[p+3]; p += 4
                data = rec[p:p+elen]
                p += elen
                if etype == 0:  # SNI
                    exts.append('SNI')
                    q = 2  # list len
                    if q < len(data) and data[q] == 0 and q+3 <= len(data):
                        hn_len = (data[q+1] << 8) | data[q+2]
                        hn = data[q+3:q+3+hn_len]
                        sni = hn.decode('utf-8','ignore')
                elif etype == 1:  # max_fragment_length
                    exts.append('max_fragment_length')
                elif etype == 10:  # supported_groups
                    exts.append('supported_groups')
                    if len(data) >= 2:
                        glen = (data[0] << 8) | data[1]
                        for k in range(0, glen, 2):
                            if 2+k <= len(data)-2:
                                gid = (data[2+k] << 8) | data[2+k+1]
                                groups.append(gid)
                elif etype == 13:  # signature_algorithms
                    exts.append('signature_algorithms')
                    if len(data) >= 2:
                        slen = (data[0] << 8) | data[1]
                        for k in range(0, slen, 2):
                            if 2+k <= len(data)-2:
                                sigalgs.append((data[2+k], data[2+k+1]))
                elif etype == 16:  # ALPN
                    exts.append('ALPN')
                    if len(data) >= 2:
                        list_len = (data[0] << 8) | data[1]
                        q = 2
                        while q < 2+list_len and q < len(data):
                            l = data[q]; q += 1
                            alpn.append(data[q:q+l].decode('utf-8','ignore'))
                            q += l
                elif etype == 11:  # ec_point_formats
                    exts.append('ECPointFormats')
                    if len(data) >= 1:
                        flen = data[0]
                        ec_point_formats = list(data[1:1+flen])
                elif etype == 23:  # extended_master_secret
                    exts.append('extended_master_secret')
                elif etype == 65281:  # renegotiation_info (0xff01)
                    exts.append('RenegotiationInfo')
                    reneg_info = data.hex()
                else:
                    exts.append(f"Extension_{etype}")
        return {
            'version': TlsAnalyzer.TLS_VERSIONS.get((vmaj, vmin), f"Unknown {vmaj}.{vmin}"),
            'random': rnd.hex(),
            'session_id': sid.hex(),
            'cipher_suites': suites,
            'compression_methods': comp,
            'extensions': exts,
            'sni': sni,
            'groups': groups,
            'signature_algorithms': sigalgs,
            'alpn': alpn,
            'ec_point_formats': ec_point_formats,
            'renegotiation_info': reneg_info,
        }
    except Exception:
        return None


def parse_server_hello_details(rec: bytes) -> Optional[dict]:
    try:
        if rec[0] != 0x16 or rec[5] != 0x02:
            return None
        p = 5 + 4  # HS header
        vmaj, vmin = rec[p], rec[p+1]; p += 2
        rnd = rec[p:p+32]; p += 32
        sid_len = rec[p]; p += 1
        sid = rec[p:p+sid_len]; p += sid_len
        cs = (rec[p] << 8) | rec[p+1]; p += 2
        comp = rec[p]; p += 1
        exts = []
        if p + 2 <= len(rec):
            ext_total = (rec[p] << 8) | rec[p+1]
            p += 2
            end = p + ext_total
            while p + 4 <= end and end <= len(rec):
                etype = (rec[p] << 8) | rec[p+1]; elen = (rec[p+2] << 8) | rec[p+3]; p += 4
                _ = rec[p:p+elen]
                p += elen
                # Map common server extensions to readable names
                if etype == 0:
                    exts.append('SNI')
                elif etype == 1:
                    exts.append('max_fragment_length')
                elif etype == 11:
                    exts.append('ECPointFormats')
                elif etype == 23:
                    exts.append('extended_master_secret')
                elif etype == 35:
                    exts.append('SessionTicket')
                elif etype == 65281:
                    exts.append('RenegotiationInfo')
                else:
                    exts.append(f'Extension_{etype}')
        return {
            'version': TlsAnalyzer.TLS_VERSIONS.get((vmaj, vmin), f"Unknown {vmaj}.{vmin}"),
            'random': rnd.hex(),
            'session_id': sid.hex(),
            'cipher': TlsAnalyzer.CIPHER_SUITES.get(cs, f"Unknown_0x{cs:04X}"),
            'compression': comp,
            'extensions': exts,
        }
    except Exception:
        return None


def parse_cert_chain(records: List[bytes]) -> List[x509.Certificate]:
    """
    Assemble Certificate handshake messages across TLS records and decode the chain.
    This handles record-layer fragmentation where a single handshake message spans
    multiple records without repeating the handshake header.
    """
    certs: List[x509.Certificate] = []

    def assemble_handshakes(recs: List[bytes]) -> List[Tuple[int, bytes]]:
        msgs: List[Tuple[int, bytes]] = []
        cur_type: Optional[int] = None
        needed: int = 0
        buf = bytearray()
        header_buf = bytearray()
        header_needed = 4
        for rec in recs:
            if not rec or rec[0] != 0x16:
                continue
            frag = rec[5:5 + ((rec[3] << 8) | rec[4])]
            j = 0
            m = len(frag)
            while j < m:
                # If we're not currently building a handshake body, ensure header is complete
                if cur_type is None and header_needed > 0:
                    take_h = min(header_needed, m - j)
                    if take_h > 0:
                        header_buf.extend(frag[j:j+take_h])
                        j += take_h
                        header_needed -= take_h
                    if header_needed > 0:
                        # Need more header bytes from next record
                        continue
                    # Parse full header
                    cur_type = header_buf[0]
                    needed = (header_buf[1] << 16) | (header_buf[2] << 8) | header_buf[3]
                    header_buf.clear()
                # Now cur_type is set and we have a body to read
                take = min(needed, m - j)
                if take > 0:
                    buf.extend(frag[j:j+take])
                    j += take
                    needed -= take
                if needed == 0 and cur_type is not None:
                    msgs.append((cur_type, bytes(buf)))
                    cur_type = None
                    buf.clear()
                    header_needed = 4
            # proceed to next record (possibly carrying header/body continuation)
        return msgs

    # Assemble messages separately per direction to preserve intra-direction order
    # Extract per-direction lists from provided records when available, else treat as single stream
    # Here, records may already be mixed; we still can assemble within this list.
    msgs = assemble_handshakes(records)

    for hs_type, body in msgs:
        if hs_type != 0x0B or not body:
            continue
        if len(body) < 3:
            continue
        chain_len = (body[0] << 16) | (body[1] << 8) | body[2]
        pos = 3
        end = min(len(body), 3 + chain_len)
        while pos + 3 <= end:
            clen = (body[pos] << 16) | (body[pos+1] << 8) | body[pos+2]
            pos += 3
            if pos + clen > end:
                break
            der = bytes(body[pos:pos+clen])
            pos += clen
            try:
                certs.append(x509.load_der_x509_certificate(der))
            except Exception:
                # ignore bad chunks; continue scanning
                pass
    return certs


def scan_der_certificates_from_records(all_records: List[bytes]) -> List[x509.Certificate]:
    data = b"".join(all_records)
    certs: List[x509.Certificate] = []
    seen = set()
    i = 0
    n = len(data)
    while i + 4 < n:
        if data[i] != 0x30:  # SEQUENCE
            i += 1
            continue
        # Parse DER length
        j = i + 1
        if j >= n:
            break
        first = data[j]
        if first & 0x80 == 0:
            length = first
            j += 1
        else:
            num = first & 0x7F
            j += 1
            if j + num > n or num == 0 or num > 4:
                i += 1
                continue
            length = 0
            for k in range(num):
                length = (length << 8) | data[j + k]
            j += num
        end = j + length
        if end > n or length < 256:  # filter tiny sequences
            i += 1
            continue
        der = data[i:end]
        try:
            cert = x509.load_der_x509_certificate(der)
            fp = cert.fingerprint(cert.signature_hash_algorithm).hex() if cert.signature_hash_algorithm else der[:16].hex()
            if fp not in seen:
                seen.add(fp)
                certs.append(cert)
            i = end
            continue
        except Exception:
            i += 1
            continue
    return certs


def cert_summary(cert: x509.Certificate) -> dict:
    def get_name(nm):
        return ", ".join([f"{attr.oid._name}={attr.value}" for attr in nm])
    subj = get_name(cert.subject)
    iss = get_name(cert.issuer)
    pub = cert.public_key()
    if isinstance(pub, rsa.RSAPublicKey):
        pk = f"RSA {pub.key_size}"
    elif isinstance(pub, ec.EllipticCurvePublicKey):
        pk = f"EC {pub.curve.name}"
    else:
        pk = pub.__class__.__name__
    def try_get(oid):
        try:
            return cert.extensions.get_extension_for_oid(oid).value
        except Exception:
            return None
    ku = try_get(ExtensionOID.KEY_USAGE)
    eku_val = try_get(ExtensionOID.EXTENDED_KEY_USAGE)
    eku = [oid._name for oid in (eku_val or [])] if eku_val else []
    try:
        san = try_get(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        sans = san.get_values_for_type(x509.DNSName) if san else []
    except Exception:
        sans = []
    try:
        aki = try_get(ExtensionOID.AUTHORITY_KEY_IDENTIFIER)
        aki_id = aki.key_identifier.hex() if (aki and aki.key_identifier) else None
    except Exception:
        aki_id = None
    try:
        crl_dp = try_get(ExtensionOID.CRL_DISTRIBUTION_POINTS)
        crls = []
        if crl_dp:
            for dp in crl_dp:
                for gn in dp.full_name or []:
                    if isinstance(gn, x509.UniformResourceIdentifier):
                        crls.append(gn.value)
    except Exception:
        crls = []
    return {
        'subject': subj,
        'issuer': iss,
        'valid_from': cert.not_valid_before.isoformat(),
        'valid_to': cert.not_valid_after.isoformat(),
        'public_key': pk,
        'key_usage': str(ku) if ku else None,
        'extended_key_usages': eku,
        'signature_algorithm': cert.signature_hash_algorithm.name if cert.signature_hash_algorithm else None,
        'subject_alternative_names': sans,
        'authority_key_identifier': aki_id,
        'crl_distribution_points': crls,
    }


def main():
    xti = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'HL7812_fallback_NOK.xti')
    parser = XTIParser(); parser.parse_file(xti)
    groups = parser.get_channel_groups()
    # Pick TAC over TCP:443
    targets = [(gi, g) for gi, g in enumerate(groups) if str(g.get('server','')).lower().find('tac') >= 0 and g.get('port') == 443]
    if not targets:
        eprint('No TAC/TCP:443 groups found')
        return 1
    for gi, g in targets:
        print(f"\n== Group[{gi}] {g.get('server')} TCP:{g.get('port')} ==")
        for si, sess in enumerate(g.get('sessions', []) or []):
            idxs = sorted(set(getattr(sess, 'traceitem_indexes', []) or []))
            print(f"\n--- Session[{si}] ---")
            reasm = TLSReassembler()
            # Feed TLS records in chronological order
            for i in idxs:
                ti = parser.trace_items[i]
                parsed = parse_apdu(getattr(ti, 'rawhex', '')) if getattr(ti, 'rawhex', None) else None
                if not parsed:
                    continue
                name = (parsed.ins_name or '').upper()
                summ = (getattr(ti, 'summary', '') or '').upper()
                if all(x not in name for x in ('SEND DATA','RECEIVE DATA')) and all(x not in summ for x in ('SEND DATA','RECEIVE DATA')):
                    continue
                payload = extract_payload_from_tlv(parsed)
                if not payload:
                    try:
                        payload = bytes.fromhex(ti.rawhex.replace(' ', '')) if ti.rawhex else None
                    except Exception:
                        payload = None
                if not payload:
                    continue
                direction = getattr(parsed, 'direction', '')
                # feed bytes into stream and let reassembler cut records across APDUs
                reasm.feed_bytes(direction, payload)
            # Reconstruction summary & detailed decode
            timeline: List[str] = []
            clienthello = None
            serverhello = None
            certificates: List[x509.Certificate] = []
            # Walk in order of appearance regardless of direction for timeline
            chronological: List[Tuple[str, int, bytes]] = []
            # Use global sequence captured during reassembly to preserve true interleaving
            for _, dirn, typ, rec in sorted(reasm.all_records, key=lambda t: t[0]):
                chronological.append((dirn, typ, rec))
            # simple pass to classify events and pick first occurrences for Client/ServerHello
            for dirn, typ, rec in chronological:
                if typ == 0x16:
                    hs_type = rec[5]
                    if hs_type == 0x01 and not clienthello:
                        clienthello = parse_client_hello_details(rec)
                        timeline.append('ClientHello')
                    elif hs_type == 0x02 and not serverhello:
                        serverhello = parse_server_hello_details(rec)
                        timeline.append('ServerHello')
                    elif hs_type == 0x0B:
                        timeline.append('Certificate')
                    elif hs_type == 0x0E:
                        timeline.append('ServerHelloDone')
                    elif hs_type == 0x10:
                        timeline.append('ClientKeyExchange')
                    elif hs_type == 0x14:
                        timeline.append('Finished')
                    else:
                        timeline.append('Handshake(other)')
                elif typ == 0x14:
                    timeline.append('ChangeCipherSpec')
                elif typ == 0x17:
                    timeline.append('ApplicationData')
                elif typ == 0x15:
                    timeline.append('Alert')
            # Certificates: try handshake-based per direction, then fallback to DER scan across all records
            sim_me_records = [rec for _, rec in reasm.records.get('SIM->ME', [])]
            me_sim_records = [rec for _, rec in reasm.records.get('ME->SIM', [])]
            certificates = []
            certificates.extend(parse_cert_chain(sim_me_records))
            certificates.extend(parse_cert_chain(me_sim_records))
            if not certificates:
                rec_bytes_all = sim_me_records + me_sim_records
                certificates = scan_der_certificates_from_records(rec_bytes_all)
            # Output sections
            print("\nSummary")
            chosen = serverhello['cipher'] if serverhello else None
            print(f"- SNI: {clienthello.get('sni') if clienthello else None}")
            print(f"- Version: {clienthello.get('version') if clienthello else serverhello.get('version') if serverhello else None}")
            print(f"- Chosen Cipher: {chosen}")
            print(f"- Certificates: {len(certificates)}")

            print("\nFull TLS Handshake Reconstruction")
            print(" -> ".join(['OPEN CHANNEL'] + timeline + ['CLOSE CHANNEL']))

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
                print(f"- ALPN: {clienthello['alpn']}")
                print(f"- ec_point_formats: {clienthello['ec_point_formats']}")
                print(f"- renegotiation_info: {clienthello['renegotiation_info']}")
            else:
                print("- ClientHello not fully decoded from provided fragments")

            print("\nDecoded ServerHello")
            if serverhello:
                for k in ['version','random','session_id','cipher','compression','extensions']:
                    v = serverhello[k]
                    print(f"- {k}: {v}")
            else:
                print("- ServerHello not fully decoded from provided fragments")

            print("\nPKI Certificate Chain (decoded)")
            if certificates:
                for idx, cert in enumerate(certificates, 1):
                    info = cert_summary(cert)
                    print(f"Certificate[{idx}]:")
                    for k, v in info.items():
                        print(f"  - {k}: {v}")
            else:
                print("- No certificates decoded from provided records")

            print("\nCipher Suite Negotiation")
            if chosen:
                print(f"- chosen: {chosen}")
                aead = ('GCM' in chosen)
                ecdhe = ('ECDHE' in chosen)
                ecdsa = ('ECDSA' in chosen)
                rsa = ('RSA_' in chosen or chosen.startswith('TLS_RSA_'))
                print(f"- key_exchange: {'ECDHE' if ecdhe else 'RSA'}")
                print(f"- authentication: {'ECDSA' if ecdsa else 'RSA'}")
                print(f"- aead: {aead}")
            else:
                print("- No chosen cipher decoded")

            print("\nSession Timeline")
            for ev in timeline:
                print(f"- {ev}")

            print("\nSecurity Evaluation")
            issues = []
            if chosen:
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

            # Append to tac_session_raw.md as Markdown
            try:
                md_path = os.path.join(HERE, 'tac_session_raw.md')
                with open(md_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n## Full TLS Analysis — Group[{gi}] Session[{si}]\n")
                    f.write("\n**Summary**\n")
                    f.write(f"- SNI: {clienthello.get('sni') if clienthello else None}\n")
                    f.write(f"- Version: {clienthello.get('version') if clienthello else serverhello.get('version') if serverhello else None}\n")
                    f.write(f"- Chosen Cipher: {chosen}\n")
                    f.write(f"- Certificates: {len(certificates)}\n")
                    f.write("\n**Full TLS Handshake Reconstruction**\n")
                    f.write("- " + " → ".join(['OPEN CHANNEL'] + timeline + ['CLOSE CHANNEL']) + "\n")
                    f.write("\n**Decoded ClientHello**\n")
                    if clienthello:
                        f.write(f"- version: {clienthello['version']}\n")
                        f.write(f"- random: {clienthello['random']}\n")
                        f.write(f"- session_id: {clienthello['session_id']}\n")
                        f.write(f"- cipher_suites: {', '.join(clienthello['cipher_suites'])}\n")
                        f.write(f"- compression_methods: {clienthello['compression_methods']}\n")
                        f.write(f"- extensions: {', '.join(clienthello['extensions'])}\n")
                        f.write(f"- SNI: {clienthello['sni']}\n")
                        f.write(f"- supported_groups: {clienthello['groups']}\n")
                        f.write(f"- signature_algorithms: {clienthello['signature_algorithms']}\n")
                        f.write(f"- ALPN: {clienthello['alpn']}\n")
                        f.write(f"- ec_point_formats: {clienthello['ec_point_formats']}\n")
                        f.write(f"- renegotiation_info: {clienthello['renegotiation_info']}\n")
                    else:
                        f.write("- ClientHello not fully decoded from provided fragments\n")
                    f.write("\n**Decoded ServerHello**\n")
                    if serverhello:
                        f.write(f"- version: {serverhello['version']}\n")
                        f.write(f"- random: {serverhello['random']}\n")
                        f.write(f"- session_id: {serverhello['session_id']}\n")
                        f.write(f"- cipher: {serverhello['cipher']}\n")
                        f.write(f"- compression: {serverhello['compression']}\n")
                        f.write(f"- extensions: {serverhello['extensions']}\n")
                    else:
                        f.write("- ServerHello not fully decoded from provided fragments\n")
                    f.write("\n**PKI Certificate Chain (decoded)**\n")
                    if certificates:
                        for idx, cert in enumerate(certificates, 1):
                            info = cert_summary(cert)
                            f.write(f"Certificate[{idx}]:\n")
                            for k, v in info.items():
                                f.write(f"  - {k}: {v}\n")
                    else:
                        f.write("- No certificates decoded from provided records\n")
                    f.write("\n**Cipher Suite Negotiation**\n")
                    if chosen:
                        f.write(f"- chosen: {chosen}\n")
                        aead = ('GCM' in chosen)
                        ecdhe = ('ECDHE' in chosen)
                        ecdsa = ('ECDSA' in chosen)
                        rsa = ('RSA_' in chosen or str(chosen).startswith('TLS_RSA_'))
                        f.write(f"- key_exchange: {'ECDHE' if ecdhe else 'RSA'}\n")
                        f.write(f"- authentication: {'ECDSA' if ecdsa else 'RSA'}\n")
                        f.write(f"- aead: {aead}\n")
                    else:
                        f.write("- No chosen cipher decoded\n")
                    f.write("\n**Session Timeline**\n")
                    for ev in timeline:
                        f.write(f"- {ev}\n")
                    f.write("\n**Security Evaluation**\n")
                    if chosen:
                        issues = []
                        if 'CBC' in chosen:
                            issues.append('Uses CBC (legacy, not AEAD)')
                        if 'RSA_WITH_' in chosen and 'ECDHE' not in chosen:
                            issues.append('No forward secrecy (RSA key exchange)')
                        if not issues:
                            f.write("- OK: Modern AEAD/ECDHE detected\n")
                        else:
                            for it in issues:
                                f.write(f"- {it}\n")
                    else:
                        f.write("- Unable to evaluate without chosen cipher\n")
            except Exception:
                pass


if __name__ == '__main__':
    sys.exit(main())
