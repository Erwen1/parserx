import json
import re
from pathlib import Path

MD = Path(__file__).resolve().parents[1] / 'tac_session_report.md'
OUT = Path(__file__).resolve().parents[1] / 'webui' / 'sessions.from_md.json'


def parse_section(text, group_tag):
    # Extract summary
    def pick(line, key):
        m = re.search(rf"^-\s*{re.escape(key)}:\s*(.*)$", line.strip(), re.I)
        return m.group(1).strip() if m else None

    s = {
        'id': f'{group_tag.lower().replace(" ", "").replace("[", "").replace("]", "").replace("--", "-")}',
        'title': group_tag,
        'type': 'TAC',
        'summary': { 'sni': None, 'version': None, 'chosenCipher': None, 'sessionId': None },
        'handshake': { 'clientHello': {}, 'serverHello': {} },
        'events': [],
        'certificates': [],
        'raw': { 'apdus': '(Raw omitted in extractor)' },
        'issues': []
    }

    # Summary block
    m = re.search(rf"##\s*Full TLS Analysis —\s*{re.escape(group_tag)}.*?\*\*Summary\*\*(.*?)\*\*Full TLS Handshake Reconstruction\*\*", text, re.S)
    if m:
        block = m.group(1)
        for line in block.splitlines():
            sni = pick(line, 'SNI')
            ver = pick(line, 'Version')
            ch = pick(line, 'Chosen Cipher')
            if sni is not None: s['summary']['sni'] = sni
            if ver is not None: s['summary']['version'] = ver
            if ch is not None: s['summary']['chosenCipher'] = ch

    # Handshake reconstruction line → events (order only)
    m = re.search(r"\*\*Full TLS Handshake Reconstruction\*\*\s*-\s*(.*?)\n\n", text, re.S)
    if m:
        chain = m.group(1)
        names = [x.strip() for x in chain.split('→')]
        mapping = {
            'ClientHello': ('Handshake', 'ClientHello'),
            'ServerHello': ('Handshake', 'ServerHello'),
            'Certificate': ('Handshake', 'Certificate'),
            'ServerKeyExchange': ('Handshake', 'ServerKeyExchange'),
            'ServerHelloDone': ('Handshake', 'ServerHelloDone'),
            'ClientKeyExchange': ('Handshake', 'ClientKeyExchange'),
            'ChangeCipherSpec': ('ChangeCipherSpec', None),
            'Finished': ('Handshake', 'Finished'),
            'ApplicationData': ('Application Data', None),
            'Alert': ('Alert', None),
        }
        # naive dir guess: SIM->ME for client side messages pre-CCS; refine as needed
        for n in names:
            if n in ('OPEN CHANNEL', 'CLOSE CHANNEL'): continue
            rec, hs = mapping.get(n, ('Other', None))
            s['events'].append({ 'dir': 'SIM->ME' if 'Client' in (hs or '') else 'ME->SIM', 'recordType': rec, 'handshakeType': hs })

    # ClientHello
    m = re.search(r"\*\*Decoded ClientHello\*\*(.*?)(?:\n\n|\Z)", text, re.S)
    if m:
        cl = {}
        block = m.group(1)
        def pickv(k):
            mm = re.search(rf"-\s*{re.escape(k)}:\s*(.*)", block)
            return mm.group(1).strip() if mm else None
        cl['version'] = pickv('version')
        cl['random'] = pickv('random')
        cl['sessionId'] = pickv('session_id')
        ciphers = pickv('cipher_suites')
        cl['ciphers'] = [x.strip() for x in (ciphers or '').split(',') if x.strip()]
        exts = pickv('extensions')
        cl['extensions'] = [x.strip().strip("[]'") for x in (exts or '').split(',') if x.strip()]
        cl['supportedGroups'] = [x.strip().strip("[]'") for x in (pickv('supported_groups') or '').split(',') if x.strip()]
        cl['signatureAlgorithms'] = [x.strip().strip("[]'") for x in (pickv('signature_algorithms') or '').split(',') if x.strip()]
        cl['ecPointFormats'] = [x.strip().strip("[]'") for x in (pickv('ec_point_formats') or '').split(',') if x.strip()]
        s['handshake']['clientHello'] = cl

    # ServerHello
    m = re.search(r"\*\*Decoded ServerHello\*\*(.*?)(?:\n\n|\Z)", text, re.S)
    if m:
        sh = {}
        block = m.group(1)
        def pickv(k):
            mm = re.search(rf"-\s*{re.escape(k)}:\s*(.*)", block)
            return mm.group(1).strip() if mm else None
        sh['version'] = pickv('version')
        sh['random'] = pickv('random')
        sh['sessionId'] = pickv('session_id')
        sh['cipher'] = pickv('cipher')
        exts = pickv('extensions')
        if exts:
            exts = exts.strip()
            # normalize quoted list like ['a','b'] or [a,b]
            exts = exts.strip('[]')
            sh['extensions'] = [x.strip().strip("'\"") for x in exts.split(',') if x.strip()]
        s['handshake']['serverHello'] = sh
        s['summary']['sessionId'] = sh.get('sessionId')

    # Certificates (subjects only)
    certs = []
    for cert_block in re.finditer(r"Certificate\[\d+\]:(.*?)(?:\n\n|\Z)", text, re.S):
        blk = cert_block.group(1)
        subj = re.search(r"-\s*subject:\s*(.*)", blk)
        iss = re.search(r"-\s*issuer:\s*(.*)", blk)
        vf = re.search(r"-\s*valid_from:\s*(.*)", blk)
        vt = re.search(r"-\s*valid_to:\s*(.*)", blk)
        pk = re.search(r"-\s*public_key:\s*(.*)", blk)
        san = re.search(r"-\s*subject_alternative_names:\s*\[(.*)\]", blk)
        eku = re.search(r"-\s*extended_key_usages:\s*\[(.*)\]", blk)
        certs.append({
            'subject': subj.group(1).strip() if subj else '',
            'issuer': iss.group(1).strip() if iss else '',
            'validFrom': vf.group(1).strip() if vf else '',
            'validTo': vt.group(1).strip() if vt else '',
            'publicKey': pk.group(1).strip() if pk else '',
            'san': [x.strip().strip("'\"") for x in (san.group(1) if san else '').split(',') if x.strip()],
            'eku': [x.strip().strip("'\"") for x in (eku.group(1) if eku else '').split(',') if x.strip()],
        })
    s['certificates'] = certs
    return s


def main():
    text = MD.read_text(encoding='utf-8')
    sessions = []
    for tag in ("Group[2] Session[0]", "Group[5] Session[0]"):
        if tag in text:
            # narrow to that section
            sec = re.search(rf"##\s*Full TLS Analysis —\s*{re.escape(tag)}(.*?)(?=\n##\s*Full TLS Analysis|\Z)", text, re.S)
            if sec:
                sessions.append(parse_section(sec.group(0), tag))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({ 'sessions': sessions }, indent=2), encoding='utf-8')
    print(f"Wrote {OUT}")


if __name__ == '__main__':
    main()
