"""Scenario validation engine.

Goal: Let a user define a SEQUENCE of expected steps (DNSbyME -> DNS -> DP+ -> TAC ...)
Then we validate what happened in the trace based on sessions + parsing log issues.

This stays intentionally lightweight: it uses existing reconstructed channel sessions
and ValidationManager issues; it does not attempt deep protocol semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable, Optional

from .validation import ValidationIssue, ValidationSeverity
from .xti_parser import tag_server_from_ips


class ScenarioStepType(str, Enum):
    DNS_BY_ME = "DNSbyME"
    DNS = "DNS"
    DP_PLUS = "DP+"
    TAC = "TAC"
    REFRESH = "Refresh"
    ICCID = "ICCID"
    LOCATION_LIMITED_SERVICE = "Location Status (Limited Service)"


class ScenarioStepPresence(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    FORBIDDEN = "forbidden"


class ScenarioStepScope(str, Enum):
    SEGMENT = "segment"  # between previous consumed step and next REQUIRED step
    GLOBAL = "global"  # anywhere in the trace


@dataclass(frozen=True)
class ScenarioStep:
    step_type: ScenarioStepType
    any_of: Optional[list[ScenarioStepType]] = None
    scope: ScenarioStepScope = ScenarioStepScope.SEGMENT
    label: Optional[str] = None
    presence: ScenarioStepPresence = ScenarioStepPresence.REQUIRED
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    # What status to emit when constraints are violated.
    # Accepted values (case-insensitive): ok / warn / fail (also: warning / critical)
    on_too_few: Optional[str] = None
    on_too_many: Optional[str] = None


@dataclass
class EvidenceItem:
    title: str
    count: int
    bytes_total: int
    servers: list[str]
    ips: list[str]
    issues_summary: str


@dataclass
class StepResult:
    step: ScenarioStep
    status: str  # OK / WARN / FAIL
    message: str
    evidence: Optional[EvidenceItem] = None
    issues: Optional[list[ValidationIssue]] = None


@dataclass
class ScenarioResult:
    overall_status: str  # OK / WARN / FAIL
    steps_summary: str
    results: list[StepResult]


@dataclass(frozen=True)
class _Occurrence:
    step_type: ScenarioStepType
    start_idx: int
    end_idx: int
    bytes_total: int
    servers: list[str]
    ips: list[str]
    opened_at: Optional[datetime]


def _safe_int(v, default: int = -1) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _normalize_status(val: Optional[str], default: str) -> str:
    s = str(val or "").strip().lower()
    if not s:
        return default
    if s in ("ok", "pass", "info"):
        return "OK"
    if s in ("warn", "warning"):
        return "WARN"
    if s in ("fail", "critical", "error"):
        return "FAIL"
    return default


def _status_worse(a: str, b: str) -> str:
    # FAIL > WARN > OK
    order = {"OK": 0, "WARN": 1, "FAIL": 2}
    return a if order.get(a, 0) >= order.get(b, 0) else b


def _step_types(step: ScenarioStep) -> list[ScenarioStepType]:
    try:
        ao = list(step.any_of or [])
    except Exception:
        ao = []
    ao = [t for t in ao if isinstance(t, ScenarioStepType)]
    return ao if ao else [step.step_type]


def _step_display(step: ScenarioStep) -> str:
    if step.label:
        return str(step.label)
    ts = _step_types(step)
    if len(ts) > 1:
        return "AnyOf(" + "|".join([t.value for t in ts]) + ")"
    return ts[0].value


def _next_required_types(steps: list[ScenarioStep], i: int) -> Optional[list[ScenarioStepType]]:
    for j in range(i + 1, len(steps)):
        if steps[j].presence == ScenarioStepPresence.REQUIRED:
            return _step_types(steps[j])
    return None


def _first_occurrence_after(occ_list: list[_Occurrence], after_end_idx: int) -> Optional[_Occurrence]:
    for o in occ_list or []:
        if o.start_idx > after_end_idx:
            return o
    return None


def _first_occurrence_of_types_after(
    occ: dict[ScenarioStepType, list[_Occurrence]],
    types: list[ScenarioStepType],
    after_end_idx: int,
) -> Optional[_Occurrence]:
    best: Optional[_Occurrence] = None
    for t in types or []:
        o = _first_occurrence_after(list(occ.get(t) or []), after_end_idx)
        if o is None:
            continue
        if best is None or o.start_idx < best.start_idx:
            best = o
    return best


_DNS_LABEL_HINTS = {
    "DNS",
    "Google DNS",
    "Cloudflare DNS",
    "Quad9 DNS",
    "OpenDNS",
    "SIMIN DNS Serveur",
}


def _normalize_label(label: str) -> str:
    return (label or "").strip()


def _is_dns_by_me_session(session) -> bool:
    try:
        return not getattr(session, "ips", None)
    except Exception:
        return False


def _is_dns_session_label(label: str) -> bool:
    lab = _normalize_label(label)
    if not lab:
        return False
    if lab in _DNS_LABEL_HINTS:
        return True
    return "DNS" in lab.upper()


def _match_step(step_type: ScenarioStepType, session, server_label: str) -> bool:
    if step_type == ScenarioStepType.DNS_BY_ME:
        return _is_dns_by_me_session(session) or _normalize_label(server_label) == "ME"
    if step_type == ScenarioStepType.DNS:
        return _is_dns_session_label(server_label)
    if step_type == ScenarioStepType.DP_PLUS:
        return "DP+" in _normalize_label(server_label)
    if step_type == ScenarioStepType.TAC:
        return "TAC" in _normalize_label(server_label)
    return False


def _traceitem_bytes(parser, idx: int) -> int:
    try:
        ti = getattr(parser, "trace_items", [])[idx]
    except Exception:
        return 0

    raw = getattr(ti, "rawhex", None)
    if not raw:
        return 0
    try:
        s = str(raw).replace(" ", "").strip()
        if len(s) % 2 != 0:
            return 0
        return len(s) // 2
    except Exception:
        return 0


def _session_bytes(parser, session) -> int:
    total = 0
    for i in (getattr(session, "traceitem_indexes", []) or []):
        total += _traceitem_bytes(parser, _safe_int(i, -1))
    return total


def _collect_occurrences(parser, issues_list: list[ValidationIssue]) -> dict[ScenarioStepType, list[_Occurrence]]:
    out: dict[ScenarioStepType, list[_Occurrence]] = {t: [] for t in ScenarioStepType}

    # 1) Session-based steps
    sessions = list(getattr(parser, "channel_sessions", []) or [])
    for s in sessions:
        label = tag_server_from_ips(getattr(s, "ips", set()) or set())
        (start_idx, end_idx) = _session_index_range(s)
        if start_idx < 0 or end_idx < 0:
            continue

        bytes_total = _session_bytes(parser, s)
        ips = sorted(list(getattr(s, "ips", set()) or set()))
        servers = [label] if label else []
        opened_at = getattr(s, "opened_at", None)

        for st in (ScenarioStepType.DNS_BY_ME, ScenarioStepType.DNS, ScenarioStepType.DP_PLUS, ScenarioStepType.TAC):
            if _match_step(st, s, label):
                out[st].append(
                    _Occurrence(
                        step_type=st,
                        start_idx=start_idx,
                        end_idx=end_idx,
                        bytes_total=bytes_total,
                        servers=servers,
                        ips=ips,
                        opened_at=opened_at if isinstance(opened_at, datetime) else None,
                    )
                )

    # 2) Event-based steps
    # Refresh: look for summary containing "refresh".
    for idx, ti in enumerate(getattr(parser, "trace_items", []) or []):
        try:
            summary = str(getattr(ti, "summary", "") or "")
        except Exception:
            summary = ""
        if "refresh" in summary.lower():
            out[ScenarioStepType.REFRESH].append(
                _Occurrence(
                    step_type=ScenarioStepType.REFRESH,
                    start_idx=idx,
                    end_idx=idx,
                    bytes_total=_traceitem_bytes(parser, idx),
                    servers=[],
                    ips=[],
                    opened_at=None,
                )
            )

    # ICCID + Location Status are best sourced from ValidationManager issues.
    for iss in issues_list or []:
        cat = str(getattr(iss, "category", "") or "")
        idx = _safe_int(getattr(iss, "trace_index", -1), -1)
        if idx < 0:
            continue

        if cat == "ICCID Detection":
            out[ScenarioStepType.ICCID].append(
                _Occurrence(
                    step_type=ScenarioStepType.ICCID,
                    start_idx=idx,
                    end_idx=idx,
                    bytes_total=_traceitem_bytes(parser, idx),
                    servers=[],
                    ips=[],
                    opened_at=None,
                )
            )

        if cat == "Location Status":
            msg = str(getattr(iss, "message", "") or "")
            if "limited" in msg.lower() and "service" in msg.lower():
                out[ScenarioStepType.LOCATION_LIMITED_SERVICE].append(
                    _Occurrence(
                        step_type=ScenarioStepType.LOCATION_LIMITED_SERVICE,
                        start_idx=idx,
                        end_idx=idx,
                        bytes_total=_traceitem_bytes(parser, idx),
                        servers=[],
                        ips=[],
                        opened_at=None,
                    )
                )

    # Sort occurrences for deterministic behavior
    for k in out.keys():
        out[k] = sorted(out[k], key=lambda o: (o.start_idx, o.end_idx))

    return out


def _format_bytes(n: int) -> str:
    try:
        n = int(n)
    except Exception:
        n = 0
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024.0:.1f} KB"
    return f"{n / (1024.0 * 1024.0):.2f} MB"


def _session_index_range(session) -> tuple[int, int]:
    idxs = list(getattr(session, "traceitem_indexes", []) or [])
    if not idxs:
        return (-1, -1)
    return (min(idxs), max(idxs))


def _issues_for_range(issues: Iterable[ValidationIssue], start: int, end: int) -> list[ValidationIssue]:
    if start < 0 or end < 0:
        return []
    out: list[ValidationIssue] = []
    for i in issues or []:
        try:
            if start <= int(i.trace_index) <= end:
                out.append(i)
        except Exception:
            continue
    return out


def _summarize_issues(issues: list[ValidationIssue]) -> str:
    if not issues:
        return "No issues"
    c = sum(1 for i in issues if i.severity == ValidationSeverity.CRITICAL)
    w = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
    inf = sum(1 for i in issues if i.severity == ValidationSeverity.INFO)
    parts = []
    if c:
        parts.append(f"Critical={c}")
    if w:
        parts.append(f"Warning={w}")
    if inf:
        parts.append(f"Info={inf}")
    return ", ".join(parts) if parts else "No issues"


def run_scenario(
    parser,
    issues: Optional[Iterable[ValidationIssue]],
    steps: list[ScenarioStep],
    *,
    max_gap_enabled: bool = False,
    max_gap_seconds: int = 30,
    max_gap_on_unknown: str = "WARN",
    max_gap_on_violation: str = "FAIL",
) -> ScenarioResult:
    """Run a sequential scenario over reconstructed sessions.

    Matching logic:
    - Uses tag_server_from_ips(session.ips) to decide server label.
    - Each step picks the first matching session AFTER the previous matched session.

    Status rules:
    - FAIL if step not found.
    - WARN if found but session contains CRITICAL issues.
    - OK if found and no CRITICAL issues in that session.
    """
    issues_list = list(issues or [])

    results: list[StepResult] = []
    cursor_end_idx = -1
    prev_time: Optional[datetime] = None

    occ = _collect_occurrences(parser, issues_list)

    for i, step in enumerate(steps):
        step_type = step.step_type
        types = _step_types(step)
        next_required_types = _next_required_types(steps, i)

        presence = step.presence
        scope = step.scope
        # Default min/max behavior keeps old semantics (required exactly once).
        default_min = 1 if presence == ScenarioStepPresence.REQUIRED else 0
        default_max = 0 if presence == ScenarioStepPresence.FORBIDDEN else 1
        min_count = step.min_count if step.min_count is not None else default_min
        max_count = step.max_count if step.max_count is not None else default_max

        on_too_few = _normalize_status(step.on_too_few, "FAIL" if presence == ScenarioStepPresence.REQUIRED else "OK")
        # Old behavior: >1 becomes WARN.
        on_too_many_default = "WARN" if presence != ScenarioStepPresence.FORBIDDEN else "WARN"
        on_too_many = _normalize_status(step.on_too_many, on_too_many_default)

        # Collect occurrences for either a single step type or any_of list.
        if scope == ScenarioStepScope.GLOBAL:
            all_occ = []
            for t in types:
                all_occ.extend(list(occ.get(t) or []))
        else:
            all_occ = []
            for t in types:
                all_occ.extend([o for o in (occ.get(t) or []) if o.start_idx > cursor_end_idx])
        all_occ = sorted(all_occ, key=lambda o: (o.start_idx, o.end_idx))

        # Segment end for OPTIONAL/FORBIDDEN steps is the next REQUIRED step's first occurrence
        # after the current cursor (if any). This keeps optional steps from accidentally
        # "eating" future required steps.
        segment_end = 10**18
        if scope != ScenarioStepScope.GLOBAL and next_required_types is not None:
            nxt = _first_occurrence_of_types_after(occ, next_required_types, cursor_end_idx)
            if nxt is not None:
                segment_end = nxt.start_idx

        step_span: list[_Occurrence] = []
        first: Optional[_Occurrence] = None
        last: Optional[_Occurrence] = None

        if presence == ScenarioStepPresence.FORBIDDEN:
            if scope == ScenarioStepScope.GLOBAL:
                step_span = list(all_occ)
            else:
                step_span = [o for o in all_occ if o.start_idx < segment_end]
            if step_span:
                first, last = step_span[0], step_span[-1]
        elif presence == ScenarioStepPresence.OPTIONAL:
            if scope == ScenarioStepScope.GLOBAL:
                step_span = list(all_occ)
            else:
                step_span = [o for o in all_occ if o.start_idx < segment_end]
            if step_span:
                first, last = step_span[0], step_span[-1]
        else:
            # REQUIRED: find the first occurrence after the cursor anywhere.
            if all_occ:
                first = all_occ[0]
                # Determine boundary based on the next REQUIRED step's first occurrence.
                boundary = 10**18
                if scope != ScenarioStepScope.GLOBAL and next_required_types is not None:
                    nxt = _first_occurrence_of_types_after(occ, next_required_types, first.end_idx)
                    if nxt is not None:
                        boundary = nxt.start_idx
                if scope == ScenarioStepScope.GLOBAL:
                    step_span = list(all_occ)
                else:
                    step_span = [o for o in all_occ if o.start_idx < boundary]
                last = step_span[-1] if step_span else first

        count = len(step_span)
        bytes_total = sum(int(o.bytes_total or 0) for o in step_span)
        servers: list[str] = []
        ips: set[str] = set()
        for o in step_span:
            for s in (o.servers or []):
                if s and s not in servers:
                    servers.append(s)
            for ip in (o.ips or []):
                if ip:
                    ips.add(ip)

        start_idx = first.start_idx if first is not None else -1
        end_idx = last.end_idx if last is not None else -1
        sess_issues = _issues_for_range(issues_list, start_idx, end_idx) if (start_idx >= 0 and end_idx >= 0) else []
        crit = any(i.severity == ValidationSeverity.CRITICAL for i in sess_issues)

        status = "OK"
        msg = ""

        step_name = _step_display(step)

        if presence == ScenarioStepPresence.OPTIONAL and count == 0:
            msg = f"Optional step not found: {step_name}"

        if count < int(min_count or 0):
            status = on_too_few
            if presence == ScenarioStepPresence.OPTIONAL:
                msg = f"Optional step not found: {step_name}"
            else:
                msg = f"Missing step: {step_name}"
        elif max_count is not None and count > int(max_count):
            status = on_too_many
            if presence == ScenarioStepPresence.FORBIDDEN:
                scope_note = " (global)" if scope == ScenarioStepScope.GLOBAL else ""
                msg = f"Forbidden step present{scope_note}: {step_name} (count={count})"
            else:
                msg = f"Too many occurrences for {step_name}: count={count}, max={max_count}"

        # If we did find something (even if it's forbidden), add context.
        if count > 0:
            kind = "session" if step_type in (ScenarioStepType.DNS_BY_ME, ScenarioStepType.DNS, ScenarioStepType.DP_PLUS, ScenarioStepType.TAC) else "event"
            plural = "s" if count != 1 else ""
            details = f"{count} {kind}{plural}, {_format_bytes(bytes_total)} total"
            try:
                matched = sorted({o.step_type.value for o in step_span})
            except Exception:
                matched = []
            if len(matched) > 1:
                details += " (matched: " + ",".join(matched) + ")"
            msg = (msg + "; " + details) if msg else details

        # Session issues can upgrade OK -> WARN, but never override FAIL.
        if crit and status != "FAIL":
            status = _status_worse(status, "WARN")

        # Location Limited Service is inherently a warning condition.
        if step_type == ScenarioStepType.LOCATION_LIMITED_SERVICE and status != "FAIL" and count > 0:
            status = _status_worse(status, "WARN")

        # Optional time constraint between steps (only works when both steps have timestamps).
        if max_gap_enabled and status != "FAIL" and presence != ScenarioStepPresence.FORBIDDEN and count > 0 and scope != ScenarioStepScope.GLOBAL:
            cur_time = first.opened_at if first is not None else None
            if prev_time is None or cur_time is None:
                status = _status_worse(status, _normalize_status(max_gap_on_unknown, "WARN"))
            else:
                try:
                    gap = (cur_time - prev_time).total_seconds()
                    if float(gap) > float(max_gap_seconds):
                        status = _status_worse(status, _normalize_status(max_gap_on_violation, "FAIL"))
                except Exception:
                    status = _status_worse(status, _normalize_status(max_gap_on_unknown, "WARN"))

        evidence = None
        if count > 0:
            evidence = EvidenceItem(
                title=f"{step_type.value}",
                count=count,
                bytes_total=int(bytes_total),
                servers=servers,
                ips=sorted(list(ips)),
                issues_summary=_summarize_issues(sess_issues),
            )

        results.append(
            StepResult(
                step=step,
                status=status,
                message=msg,
                evidence=evidence,
                issues=sess_issues,
            )
        )

        # Only advance cursor for steps that actually consume occurrences.
        if presence != ScenarioStepPresence.FORBIDDEN and count > 0 and last is not None and scope != ScenarioStepScope.GLOBAL:
            cursor_end_idx = last.end_idx
            prev_time = last.opened_at

    if any(r.status == "FAIL" for r in results):
        overall = "FAIL"
    elif any(r.status == "WARN" for r in results):
        overall = "WARN"
    else:
        overall = "OK"

    # Summary line like: DNSbyME(1) -> DNS(1) -> TAC(2!) -> DP+(1)
    parts: list[str] = []
    for r in results:
        c = 0
        if r.evidence is not None:
            try:
                c = int(r.evidence.count)
            except Exception:
                c = 0
        suffix = "" if r.status == "OK" else ("!" if r.status == "WARN" else "x")
        parts.append(f"{_step_display(r.step)}({c}){suffix}")
    steps_summary = " -> ".join(parts)

    return ScenarioResult(overall_status=overall, steps_summary=steps_summary, results=results)
