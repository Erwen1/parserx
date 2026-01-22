import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class TLSFlowEvent:
    direction: str  # "SIM->ME" or "ME->SIM" or ""
    timestamp: str  # e.g., "11/06/2025 16:55:33:739.000000"
    label: str      # e.g., "TLS Handshake (ClientHello)"
    details: str    # extra info like version/SNI/ciphers


@dataclass
class TLSSummary:
    sni: Optional[str]
    version: Optional[str]
    offered_ciphers: List[str]
    chosen_cipher: Optional[str]
    certificates: Optional[int]


@dataclass
class TLSHandshake:
    sequence: List[str]


@dataclass
class TLSReportData:
    raw_apdus: List[str]
    flow_events: List[TLSFlowEvent]
    summary: TLSSummary
    handshake: TLSHandshake


_TLS_FLOW_SECTION_RE = re.compile(r"^## TLS Flow.*?$", re.MULTILINE)
_RAW_APDUS_SECTION_RE = re.compile(r"^## RAW APDUs.*?$", re.MULTILINE)
_FULL_ANALYSIS_SECTION_RE = re.compile(r"^## Full TLS Analysis.*?$", re.MULTILINE)


def _extract_code_block(md: str, heading: str) -> List[str]:
    """Return lines inside the first fenced code block under the given heading."""
    # Find heading position
    idx = md.find(heading)
    if idx == -1:
        return []
    # Find first fenced block after heading
    fence_start = md.find("```", idx)
    if fence_start == -1:
        return []
    fence_end = md.find("```", fence_start + 3)
    if fence_end == -1:
        return []
    block = md[fence_start + 3 : fence_end]
    # Normalize and split; drop optional language header like "text"
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    if lines and lines[0].lower() in {"text", "json", "yaml", "md"}:
        lines = lines[1:]
    return lines


def _parse_tls_flow_lines(lines: List[str]) -> List[TLSFlowEvent]:
    events: List[TLSFlowEvent] = []
    # Example line:
    # [TLS] TLS          | SIM->ME   | 11/06/2025 16:55:33:739.000000 | TLS Handshake (ClientHello) • TLS 1.2 • SNI: ...
    pattern = re.compile(
        r"^\[TLS\]\s+([^|]+)\|\s*([^|]*)\|\s*([^|]*)\|\s*(.*)$"
    )
    for ln in lines:
        # Skip the aggregated Summary row, handled separately
        if ln.startswith("[TLS] Summary"):
            continue
        m = pattern.match(ln.strip())
        if not m:
            continue
        _category, _direction, _ts, _rest = [x.strip() for x in m.groups()]
        # Split rest at first '•' for label and details
        if "•" in _rest:
            label, details = _rest.split("•", 1)
            label = label.strip()
            details = details.strip()
        else:
            label, details = _rest, ""
        events.append(TLSFlowEvent(direction=_direction, timestamp=_ts, label=label, details=details))
    return events


def _parse_summary(md: str) -> TLSSummary:
    # Parse the concise Summary line inside TLS Flow as offered ciphers
    tls_flow_lines = _extract_code_block(md, "## TLS Flow")
    offered: List[str] = []
    sni = None
    version = None
    for ln in tls_flow_lines:
        if ln.startswith("[TLS] Summary"):
            # Extract SNI and Version
            sni_m = re.search(r"SNI:\s([^|]+)", ln)
            ver_m = re.search(r"Version:\s([^|]+)", ln)
            c_m = re.search(r"Ciphers:\s(.+)$", ln)
            if sni_m:
                sni = sni_m.group(1).strip()
            if ver_m:
                version = ver_m.group(1).strip()
            if c_m:
                offered = [c.strip() for c in c_m.group(1).split(',')]
            break

    # Parse chosen cipher and certificates from Full TLS Analysis Summary
    chosen = None
    certs = None
    # pick first Full TLS Analysis block
    fa_idx = md.find("## Full TLS Analysis")
    if fa_idx != -1:
        # Search within next ~1000 chars to avoid scanning entire file
        window = md[fa_idx : fa_idx + 3000]
        cm = re.search(r"Chosen Cipher:\s(.+)", window)
        if cm:
            chosen = cm.group(1).strip()
        ctm = re.search(r"Certificates:\s(\d+)", window)
        if ctm:
            certs = int(ctm.group(1))

    return TLSSummary(sni=sni, version=version, offered_ciphers=offered, chosen_cipher=chosen, certificates=certs)


def _parse_handshake(md: str) -> TLSHandshake:
    # Find Full TLS Handshake Reconstruction bullet list
    fa_idx = md.find("## Full TLS Analysis")
    sequence: List[str] = []
    if fa_idx != -1:
        window = md[fa_idx : fa_idx + 3000]
        hm = re.search(r"\*\*Full TLS Handshake Reconstruction\*\*\n-\s(.+)", window)
        if hm:
            seq = hm.group(1).strip()
            # Split by arrow →
            sequence = [x.strip() for x in seq.split("→")]
    return TLSHandshake(sequence=sequence)


def parse_tls_report(md_text: str) -> TLSReportData:
    raw_lines = _extract_code_block(md_text, "## RAW APDUs")
    flow_lines = _extract_code_block(md_text, "## TLS Flow")
    flow_events = _parse_tls_flow_lines(flow_lines)
    summary = _parse_summary(md_text)
    handshake = _parse_handshake(md_text)
    return TLSReportData(
        raw_apdus=raw_lines,
        flow_events=flow_events,
        summary=summary,
        handshake=handshake,
    )


def load_tls_report(path: str) -> TLSReportData:
    with open(path, "r", encoding="utf-8") as f:
        md = f.read()
    return parse_tls_report(md)


def to_dict(data: TLSReportData) -> Dict[str, Any]:
    return {
        "raw_apdus": data.raw_apdus,
        "flow_events": [
            {
                "direction": e.direction,
                "timestamp": e.timestamp,
                "label": e.label,
                "details": e.details,
            }
            for e in data.flow_events
        ],
        "summary": {
            "sni": data.summary.sni,
            "version": data.summary.version,
            "offered_ciphers": data.summary.offered_ciphers,
            "chosen_cipher": data.summary.chosen_cipher,
            "certificates": data.summary.certificates,
        },
        "handshake": {
            "sequence": data.handshake.sequence,
        },
    }
