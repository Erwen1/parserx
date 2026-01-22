import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any


def hex_to_bytes(hex_str: str) -> bytes:
    s = hex_str.strip().replace(" ", "")
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    if len(s) % 2:
        raise ValueError(f"Odd number of hex nibbles in '{hex_str[:40]}...'")
    return bytes.fromhex(s)


@dataclass
class TraceItem:
    protocol: str
    type: str
    rawhex: bytes
    group_id: Optional[str] = None
    timestamp: Optional[str] = None


def read_xti(path: str) -> List[TraceItem]:
    tree = ET.parse(path)
    root = tree.getroot()
    items: List[TraceItem] = []
    for ti in root.iterfind(".//traceitem"):
        protocol = ti.get("protocol") or ""
        ttype = ti.get("type") or ""
        data = ti.find("data")
        rawhex_attr = data.get("rawhex") if data is not None else None
        if rawhex_attr is None:
            continue
        group = data.get("group") or ti.get("group") or None
        group_id = None
        if group is None:
            g = ti.find("group")
            if g is not None:
                group_id = g.get("id")
        else:
            group_id = group
        ts = ti.find("timestamp/formatted")
        formatted = ts.text if ts is not None else None
        try:
            b = hex_to_bytes(rawhex_attr)
        except Exception:
            # Skip malformed entries
            continue
        items.append(TraceItem(protocol=protocol, type=ttype, rawhex=b, group_id=group_id, timestamp=formatted))
    return items


# ---------------- APDU parsing ----------------


@dataclass
class ApduCommand:
    cla: int
    ins: int
    p1: int
    p2: int
    lc: Optional[int]
    data: bytes
    le: Optional[int]


@dataclass
class ApduResponse:
    data: bytes
    sw1: int
    sw2: int


def parse_apdu_command(b: bytes) -> ApduCommand:
    if len(b) < 4:
        raise ValueError("APDU command too short")
    cla, ins, p1, p2 = b[0], b[1], b[2], b[3]
    idx = 4
    lc: Optional[int] = None
    le: Optional[int] = None
    data = b""

    if len(b) == 4:
        return ApduCommand(cla, ins, p1, p2, None, b"", None)

    # If first length byte is 0x00, extended length
    if idx < len(b) and b[idx] == 0x00:
        # Extended Case 2/3/4
        if len(b) < idx + 3:
            raise ValueError("Extended length header incomplete")
        ext_len = (b[idx + 1] << 8) | b[idx + 2]
        idx += 3
        if len(b) == idx:  # Case 2E (Le only, 2 bytes ‘ext_len’ being actually Le)
            le = ext_len if ext_len != 0 else 65536
            return ApduCommand(cla, ins, p1, p2, None, b"", le)
        # Case 3E or 4E
        lc = ext_len
        if len(b) < idx + lc:
            raise ValueError("APDU data shorter than Lc (extended)")
        data = b[idx:idx + lc]
        idx += lc
        if len(b) == idx:
            return ApduCommand(cla, ins, p1, p2, lc, data, None)
        # Le (2 bytes if nonzero length remains is 2, else 1 per some variants)
        rem = len(b) - idx
        if rem == 1:
            le = b[idx] if b[idx] != 0 else 256
        elif rem == 2:
            le_val = (b[idx] << 8) | b[idx + 1]
            le = le_val if le_val != 0 else 65536
        else:
            raise ValueError("Unexpected trailing bytes after APDU data (extended)")
        return ApduCommand(cla, ins, p1, p2, lc, data, le)

    # Short cases
    # If remaining length is 1 => Case 2S (Le only)
    if len(b) == idx + 1:
        le = b[idx] if b[idx] != 0 else 256
        return ApduCommand(cla, ins, p1, p2, None, b"", le)

    # Otherwise first is Lc
    lc = b[idx]
    idx += 1
    if len(b) < idx + lc:
        raise ValueError("APDU data shorter than Lc (short)")
    data = b[idx:idx + lc]
    idx += lc
    if len(b) == idx:
        return ApduCommand(cla, ins, p1, p2, lc, data, None)
    if len(b) == idx + 1:
        le = b[idx] if b[idx] != 0 else 256
        return ApduCommand(cla, ins, p1, p2, lc, data, le)
    raise ValueError("Unexpected trailing bytes after APDU data (short)")


def parse_apdu_response(b: bytes) -> ApduResponse:
    if len(b) < 2:
        raise ValueError("APDU response too short")
    data = b[:-2]
    sw1, sw2 = b[-2], b[-1]
    return ApduResponse(data=data, sw1=sw1, sw2=sw2)


SW_MEANINGS: Dict[Tuple[int, int], str] = {
    (0x90, 0x00): "Success",
    (0x6C, None): "Wrong length (correct length in SW2)",
}


def decode_sw(sw1: int, sw2: int) -> str:
    if (sw1, sw2) in SW_MEANINGS:
        return SW_MEANINGS[(sw1, sw2)]
    if sw1 == 0x6C:
        return f"Wrong length; expected {sw2}"
    return f"SW1=0x{sw1:02X}, SW2=0x{sw2:02X}"


# ---------------- BER‑TLV parsing ----------------


@dataclass
class TlvNode:
    tag_bytes: bytes
    length: int
    value: bytes
    children: Optional[List["TlvNode"]] = None

    @property
    def tag(self) -> int:
        t = 0
        for b in self.tag_bytes:
            t = (t << 8) | b
        return t

    def is_constructed(self) -> bool:
        return (self.tag_bytes[0] & 0x20) != 0


CONTAINER_TAGS_FORCE = {0xD0, 0xA0}


def parse_ber_tlv(b: bytes, start: int = 0, end: Optional[int] = None) -> Tuple[List[TlvNode], int]:
    if end is None:
        end = len(b)
    nodes: List[TlvNode] = []
    i = start
    while i < end:
        # Tag
        if i >= end:
            break
        first = b[i]
        i += 1
        tag_bytes = bytes([first])
        if (first & 0x1F) == 0x1F:
            # long-form tag
            while i < end:
                tag_bytes += bytes([b[i]])
                cont = (b[i] & 0x80) != 0
                i += 1
                if not cont:
                    break
        if i >= end:
            break
        # Length
        lbyte = b[i]
        i += 1
        if lbyte < 0x80:
            length = lbyte
        else:
            nlen = lbyte & 0x7F
            if i + nlen > end:
                raise ValueError("TLV length bytes exceed buffer")
            length = 0
            for k in range(nlen):
                length = (length << 8) | b[i + k]
            i += nlen
        if i + length > end:
            raise ValueError("TLV value exceeds buffer")
        value = b[i:i + length]
        i += length
        node = TlvNode(tag_bytes=tag_bytes, length=length, value=value)
        tag_int = node.tag
        if node.is_constructed() or tag_int in CONTAINER_TAGS_FORCE:
            children, _ = parse_ber_tlv(value, 0, len(value))
            node.children = children
        nodes.append(node)
    return nodes, i


# Common STK/USIM TLV names (mask out CR bit 0x80 when applicable)
STK_TLV_NAMES: Dict[int, str] = {
    0x1E: "Image Descriptor",
    0x1F: "URL",
    0x25: "Browser Identity",
    0x26: "Bearer",
    0x2B: "USSD String",
    0x2C: "SMS TPDU",
    0x2D: "Cell Broadcast Page",
    0x35: "Response Length",
    0x36: "File List",
    0x39: "Service Search",
    0x3A: "Network Search",
    0x3B: "EFRAT Parameters",
    0x3C: "Text Attribute",
    0x3D: "Item Icon Identifier",
    0x81: "Command Details",
    0x82: "Device Identity",
    0x83: "Result",
    0x84: "AID",
    0x85: "Alpha Identifier",
    0x86: "BIP Transport Level",
    0x87: "Timer Identifier",
    0x88: "Timer Value",
    0x8A: "USIM Response",
    0x8B: "Text String",
    0x8C: "Item",
    0x8D: "Item Identifier",
    0x8E: "Response Length",
    0x90: "Help Request",
    0xA0: "Command Container",
    0xA3: "Channel Status",
    0xD0: "Proactive Command",
    0x62: "FCP Template",
    0x6F: "FCI Proprietary Template",
    0xA5: "FCI Template",
}


def tag_display_name(tag_bytes: bytes) -> str:
    tag = 0
    for b in tag_bytes:
        tag = (tag << 8) | b
    # For single-byte comprehension TLVs, mask CR bit when mapping
    base_tag = tag_bytes[0] & 0x7F if len(tag_bytes) == 1 else tag
    name = STK_TLV_NAMES.get(base_tag)
    if name:
        return f"{name} (0x{tag:02X})"
    return f"Tag 0x{tag:02X}"


def format_tlv_tree(nodes: List[TlvNode], indent: int = 0) -> List[str]:
    lines: List[str] = []
    pad = "  " * indent
    for n in nodes:
        title = tag_display_name(n.tag_bytes)
        if n.children is not None:
            lines.append(f"{pad}{title}: [{n.length} bytes]")
            lines.extend(format_tlv_tree(n.children, indent + 1))
        else:
            val_preview = n.value.hex().upper()
            # Attempt ASCII preview
            ascii_preview = None
            try:
                txt = n.value.decode("ascii")
                if any(c.isalpha() for c in txt):
                    ascii_preview = txt
            except Exception:
                pass
            if ascii_preview:
                lines.append(f"{pad}{title}: {val_preview} | '{ascii_preview}'")
            else:
                lines.append(f"{pad}{title}: {val_preview}")
    return lines


DOMAIN_RE = re.compile(rb"([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")


def find_domain_like(data: bytes) -> List[str]:
    return sorted({m.group(0).decode("ascii", errors="ignore") for m in DOMAIN_RE.finditer(data)})


def analyze_item(ti: TraceItem) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "protocol": ti.protocol,
        "type": ti.type,
        "timestamp": ti.timestamp,
        "group": ti.group_id,
        "rawlen": len(ti.rawhex),
        "issues": [],
    }
    b = ti.rawhex
    if ti.protocol == "ISO7816" and ti.type == "apducommand":
        try:
            cmd = parse_apdu_command(b)
            out["apdu"] = {
                "cla": f"0x{cmd.cla:02X}",
                "ins": f"0x{cmd.ins:02X}",
                "p1": f"0x{cmd.p1:02X}",
                "p2": f"0x{cmd.p2:02X}",
                "lc": cmd.lc,
                "le": cmd.le,
                "data_len": len(cmd.data),
            }
            if cmd.lc is not None and cmd.lc != len(cmd.data):
                out["issues"].append(f"Lc {cmd.lc} != data length {len(cmd.data)}")
            # If data appears TLV (starts with constructed 0xD0/0x62/0x6F/A5), decode
            if cmd.data[:1] in (b"\xD0", b"\x62", b"\x6F", b"\xA5"):
                tlvs, _ = parse_ber_tlv(cmd.data)
                out["tlv"] = format_tlv_tree(tlvs)
        except Exception as e:
            out["issues"].append(f"APDU command parse error: {e}")
    elif ti.protocol == "ISO7816" and ti.type == "apduresponse":
        try:
            rsp = parse_apdu_response(b)
            out["apdu"] = {
                "data_len": len(rsp.data),
                "sw1": f"0x{rsp.sw1:02X}",
                "sw2": f"0x{rsp.sw2:02X}",
                "status": decode_sw(rsp.sw1, rsp.sw2),
            }
            # If response data looks TLV or Proactive Command, decode
            if rsp.data[:1] in (b"\xD0", b"\x62", b"\x6F", b"\xA5") and len(rsp.data) > 2:
                try:
                    tlvs, _ = parse_ber_tlv(rsp.data)
                    out["tlv"] = format_tlv_tree(tlvs)
                except Exception as e:
                    out["issues"].append(f"TLV parse error: {e}")
            # DNS-like strings hunt
            doms = find_domain_like(rsp.data)
            if doms:
                out["domains"] = doms
        except Exception as e:
            out["issues"].append(f"APDU response parse error: {e}")
    else:
        # Non-APDU items: still search for TLV and domains
        if len(b) > 2 and b[:1] in (b"\xD0", b"\x62", b"\x6F", b"\xA5"):
            try:
                tlvs, _ = parse_ber_tlv(b)
                out["tlv"] = format_tlv_tree(tlvs)
            except Exception:
                pass
        doms = find_domain_like(b)
        if doms:
            out["domains"] = doms
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Validate XTI APDU/TLV analysis against expectations.")
    p.add_argument("xti", help="Path to .xti file")
    p.add_argument("--only-protocol", choices=["ISO7816", "MSC_EVENT", "ALL"], default="ALL")
    p.add_argument("--only-type", help="Filter by traceitem type (e.g., apducommand, apduresponse)")
    p.add_argument("--aid-prefix", help="Filter responses containing AID TLV (0x84) with this hex prefix")
    p.add_argument("--has-tag", help="Filter items containing given TLV tag hex (e.g., 0xD0,0x39)")
    p.add_argument("--dns", action="store_true", help="Show only items with domain-like ASCII strings")
    p.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = p.parse_args()

    items = read_xti(args.xti)
    results: List[Dict[str, Any]] = []
    tag_filter_ints: Optional[List[int]] = None
    if args.has_tag:
        tag_filter_ints = []
        for t in args.has_tag.split(','):
            t = t.strip()
            if t.lower().startswith('0x'):
                tag_filter_ints.append(int(t, 16))
            else:
                tag_filter_ints.append(int(t))

    for ti in items:
        if args.only_protocol != "ALL" and ti.protocol != args.only_protocol:
            continue
        if args.only_type and ti.type != args.only_type:
            continue
        res = analyze_item(ti)
        # AID filter
        if args.aid_prefix:
            aid_match = False
            tlv_lines = res.get("tlv") or []
            pref = args.aid_prefix.upper().replace(" ", "")
            for line in tlv_lines:
                if line.strip().startswith("AID") and pref in line:
                    aid_match = True
                    break
            if not aid_match:
                continue
        # Tag filter
        if tag_filter_ints is not None:
            has_any = False
            tlv_lines = res.get("tlv") or []
            for line in tlv_lines:
                for t in tag_filter_ints:
                    if f"0x{t:02X}" in line:
                        has_any = True
                        break
                if has_any:
                    break
            if not has_any:
                continue
        # DNS-only filter
        if args.dns and not res.get("domains"):
            continue
        results.append(res)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    # Pretty text output
    total = len(results)
    print(f"Analyzed items: {total}")
    for i, r in enumerate(results, 1):
        print("-" * 80)
        hdr = f"[{i}/{total}] {r.get('protocol')}/{r.get('type')} time={r.get('timestamp')} group={r.get('group')} len={r.get('rawlen')}"
        print(hdr)
        apdu = r.get("apdu")
        if apdu:
            if "ins" in apdu:
                print(f"  APDU-C: CLA={apdu['cla']} INS={apdu['ins']} P1={apdu['p1']} P2={apdu['p2']} Lc={apdu['lc']} Le={apdu['le']} data_len={apdu['data_len']}")
            else:
                print(f"  APDU-R: data_len={apdu['data_len']} SW1={apdu['sw1']} SW2={apdu['sw2']} ({apdu['status']})")
        tlv_lines = r.get("tlv")
        if tlv_lines:
            print("  TLV:")
            for line in tlv_lines:
                print("    " + line)
        if r.get("domains"):
            print("  Domains:", ", ".join(r["domains"]))
        if r.get("issues"):
            print("  Issues:")
            for iss in r["issues"]:
                print("    - " + iss)
    return 0


if __name__ == "__main__":
    sys.exit(main())
