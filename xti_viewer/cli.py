"""Headless CLI utilities for XTI Viewer.

This module intentionally avoids importing Qt/PySide6 so it can be used in
non-GUI contexts (CI, scripts, console exe).

Usage:
  python -m xti_viewer.cli flow-overview path\\to\\file.xti
  python -m xti_viewer.cli parsing-log path\\to\\file.xti
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable, Optional

from xti_viewer.xti_parser import XTIParser
from xti_viewer.validation import ValidationManager, ValidationSeverity
from xti_viewer.scenario_engine import ScenarioStep, ScenarioStepPresence, ScenarioStepScope, ScenarioStepType, run_scenario


def _load_scenarios_from_config() -> tuple[dict[str, Any], str]:
    """Load scenarios from config.json (shared with GUI), without Qt."""
    try:
        from app_config import load_config

        cfg = load_config() or {}
        scenarios = cfg.get("scenarios")
        if not isinstance(scenarios, dict) or not scenarios:
            scenarios = {
                "Default": {
                    "sequence": ["DNSbyME", "DNS", "DP+", "TAC"],
                    "constraints": {"max_gap_enabled": False, "max_gap_seconds": 30},
                }
            }
        selected = cfg.get("selected_scenario")
        if not isinstance(selected, str) or selected not in scenarios:
            selected = sorted(list(scenarios.keys()))[0]
        return scenarios, selected
    except Exception:
        return (
            {
                "Default": {
                    "sequence": ["DNSbyME", "DNS", "DP+", "TAC"],
                    "constraints": {"max_gap_enabled": False, "max_gap_seconds": 30},
                }
            },
            "Default",
        )


def _normalize_scenario_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    seq = payload.get("sequence")
    if not isinstance(seq, list):
        seq = []

    normalized_seq: list[Any] = []
    for item in seq:
        if isinstance(item, str):
            s = str(item).strip()
            if s:
                normalized_seq.append(s)
            continue
        if isinstance(item, dict):
            step_type = item.get("type") or item.get("step_type") or item.get("step")
            step_type = str(step_type or "").strip()

            any_of = item.get("any_of") or item.get("either") or item.get("one_of")
            if any_of is not None and not isinstance(any_of, list):
                any_of = None

            if not step_type and not any_of:
                continue

            obj: dict[str, Any] = {}
            if step_type:
                obj["type"] = step_type
            if isinstance(any_of, list) and any_of:
                obj["any_of"] = [str(x).strip() for x in any_of if str(x).strip()]
            # Optional fields
            if "presence" in item:
                obj["presence"] = str(item.get("presence") or "").strip()
            if "scope" in item:
                obj["scope"] = str(item.get("scope") or "").strip()
            if "label" in item:
                obj["label"] = str(item.get("label") or "").strip()
            if "min" in item:
                obj["min"] = item.get("min")
            if "max" in item:
                obj["max"] = item.get("max")
            if "min_count" in item:
                obj["min_count"] = item.get("min_count")
            if "max_count" in item:
                obj["max_count"] = item.get("max_count")
            if "too_few" in item:
                obj["too_few"] = item.get("too_few")
            if "too_many" in item:
                obj["too_many"] = item.get("too_many")
            if "on_too_few" in item:
                obj["on_too_few"] = item.get("on_too_few")
            if "on_too_many" in item:
                obj["on_too_many"] = item.get("on_too_many")
            normalized_seq.append(obj)
            continue
        # ignore unknown types
    cons = payload.get("constraints")
    if not isinstance(cons, dict):
        cons = {}
    return {
        "sequence": normalized_seq or ["DNSbyME", "DNS", "DP+", "TAC"],
        "constraints": {
            "max_gap_enabled": bool(cons.get("max_gap_enabled", False)),
            "max_gap_seconds": int(cons.get("max_gap_seconds", 30) or 30),
            "max_gap_on_unknown": str(cons.get("max_gap_on_unknown", "WARN") or "WARN"),
            "max_gap_on_violation": str(cons.get("max_gap_on_violation", "FAIL") or "FAIL"),
        },
    }


def _parse_scenario_steps(seq: list[Any]) -> list[ScenarioStep]:
    out: list[ScenarioStep] = []
    for item in seq or []:
        if isinstance(item, str):
            s = str(item).strip()
            if not s:
                continue
            try:
                out.append(ScenarioStep(step_type=ScenarioStepType(s)))
            except Exception:
                continue
            continue

        if isinstance(item, dict):
            t = str(item.get("type") or item.get("step_type") or "").strip()

            any_of_raw = item.get("any_of")
            any_of: list[ScenarioStepType] = []
            if isinstance(any_of_raw, list):
                for x in any_of_raw:
                    sx = str(x or "").strip()
                    if not sx:
                        continue
                    try:
                        any_of.append(ScenarioStepType(sx))
                    except Exception:
                        continue

            if not t and not any_of:
                continue
            if t:
                try:
                    step_type = ScenarioStepType(t)
                except Exception:
                    continue
            else:
                # any_of only: pick a stable representative for step_type
                step_type = any_of[0]

            presence_raw = str(item.get("presence") or "required").strip().lower()
            presence = ScenarioStepPresence.REQUIRED
            if presence_raw == "optional":
                presence = ScenarioStepPresence.OPTIONAL
            elif presence_raw == "forbidden":
                presence = ScenarioStepPresence.FORBIDDEN

            scope_raw = str(item.get("scope") or "segment").strip().lower()
            scope = ScenarioStepScope.SEGMENT
            if scope_raw == "global":
                scope = ScenarioStepScope.GLOBAL

            def _int_or_none(v: Any) -> Optional[int]:
                try:
                    if v is None or v == "":
                        return None
                    return int(v)
                except Exception:
                    return None

            min_count = _int_or_none(item.get("min_count", item.get("min")))
            max_count = _int_or_none(item.get("max_count", item.get("max")))
            on_too_few = item.get("on_too_few", item.get("too_few"))
            on_too_many = item.get("on_too_many", item.get("too_many"))

            label = str(item.get("label") or "").strip() or None

            out.append(
                ScenarioStep(
                    step_type=step_type,
                    any_of=any_of or None,
                    scope=scope,
                    label=label,
                    presence=presence,
                    min_count=min_count,
                    max_count=max_count,
                    on_too_few=str(on_too_few) if on_too_few is not None else None,
                    on_too_many=str(on_too_many) if on_too_many is not None else None,
                )
            )

    return out


def cmd_scenario(args: argparse.Namespace) -> int:
    scenarios, selected = _load_scenarios_from_config()

    if getattr(args, "list", False):
        names = sorted(list(scenarios.keys()))
        if args.format == "json":
            _write_output(json.dumps({"scenarios": names, "selected": selected}, indent=2, ensure_ascii=False) + "\n", args.out)
            return 0
        lines = ["Scenarios:"]
        for n in names:
            star = "*" if n == selected else " "
            lines.append(f"{star} {n}")
        lines.append("")
        _write_output("\n".join(lines), args.out)
        return 0

    scenario_name = getattr(args, "scenario_name", None)
    xti_file = getattr(args, "xti_file", None)
    if not scenario_name or not xti_file:
        raise ValueError("Usage: scenario -l  OR  scenario <name> <file.xti>")

    # Resolve scenario name (case-insensitive fallback)
    name = str(scenario_name)
    payload = scenarios.get(name)
    if payload is None:
        lowered = {k.lower(): k for k in scenarios.keys()}
        key = lowered.get(name.lower())
        if key is not None:
            name = key
            payload = scenarios.get(key)

    if payload is None:
        raise ValueError(f"Unknown scenario: {scenario_name}. Use: scenario -l")

    payload = _normalize_scenario_payload(payload)
    steps_def = _parse_scenario_steps(payload.get("sequence") or [])
    if not steps_def:
        raise ValueError(f"Scenario '{name}' has no valid steps")

    parser, vm = _load_and_validate(xti_file)

    cons = payload.get("constraints") or {}
    max_gap_enabled = bool(cons.get("max_gap_enabled", False))
    max_gap_seconds = int(cons.get("max_gap_seconds", 30) or 30)
    max_gap_on_unknown = str(cons.get("max_gap_on_unknown", "WARN") or "WARN")
    max_gap_on_violation = str(cons.get("max_gap_on_violation", "FAIL") or "FAIL")

    res = run_scenario(
        parser,
        getattr(vm, "issues", None),
        steps_def,
        max_gap_enabled=max_gap_enabled,
        max_gap_seconds=max_gap_seconds,
        max_gap_on_unknown=max_gap_on_unknown,
        max_gap_on_violation=max_gap_on_violation,
    )

    if args.format == "json":
        def _iss_to_obj(iss: Any) -> dict[str, Any]:
            return {
                "severity": getattr(getattr(iss, "severity", None), "value", str(getattr(iss, "severity", ""))),
                "category": getattr(iss, "category", None),
                "message": getattr(iss, "message", None),
                "trace_index": getattr(iss, "trace_index", None),
                "timestamp": getattr(iss, "timestamp", None),
            }

        results_obj: list[dict[str, Any]] = []
        for r in res.results:
            ev = r.evidence
            issues_list = list(r.issues or [])
            max_issues = 50

            step_display = getattr(r.step, "label", None)
            if not step_display:
                any_of = getattr(r.step, "any_of", None)
                if isinstance(any_of, list) and any_of:
                    try:
                        step_display = "AnyOf(" + "|".join([t.value for t in any_of]) + ")"
                    except Exception:
                        step_display = None
            if not step_display:
                step_display = r.step.step_type.value

            results_obj.append(
                {
                    "step": r.step.step_type.value,
                    "step_display": step_display,
                    "status": r.status,
                    "message": r.message,
                    "evidence": (
                        {
                            "count": getattr(ev, "count", None),
                            "bytes_total": getattr(ev, "bytes_total", None),
                            "servers": getattr(ev, "servers", None),
                            "ips": getattr(ev, "ips", None),
                            "issues_summary": ev.issues_summary,
                        }
                        if ev is not None
                        else None
                    ),
                    "issues": [_iss_to_obj(i) for i in issues_list[:max_issues]],
                    "issues_truncated": max(0, len(issues_list) - max_issues),
                }
            )

        payload_out = {
            "file": xti_file,
            "scenario": name,
            "definition": payload,
            "overall_status": res.overall_status,
            "steps_summary": getattr(res, "steps_summary", None),
            "results": results_obj,
        }
        _write_output(json.dumps(payload_out, indent=2, ensure_ascii=False) + "\n", args.out)
        return 0

    lines: list[str] = []
    lines.append(f"File: {xti_file}")
    lines.append(f"Scenario: {name}")
    if max_gap_enabled:
        lines.append(f"Constraint: max_gap_seconds={max_gap_seconds}")
    lines.append(f"Overall: {res.overall_status}")
    lines.append("")
    for r in res.results:
        step_display = getattr(r.step, "label", None)
        if not step_display:
            any_of = getattr(r.step, "any_of", None)
            if isinstance(any_of, list) and any_of:
                try:
                    step_display = "AnyOf(" + "|".join([t.value for t in any_of]) + ")"
                except Exception:
                    step_display = None
        if not step_display:
            step_display = r.step.step_type.value

        lines.append(f"{step_display} => {r.status}")
        if r.message:
            lines.append(f"  {r.message}")
    lines.append("")
    _write_output("\n".join(lines), args.out)
    return 0


def _write_output(text: str, out_path: Optional[str]) -> None:
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


def _iter_issues(vm: ValidationManager, severities: Optional[set[ValidationSeverity]]) -> Iterable[Any]:
    if not severities:
        return list(vm.issues)
    return [iss for iss in vm.issues if iss.severity in severities]


def _parse_severities(args: argparse.Namespace) -> Optional[set[ValidationSeverity]]:
    if getattr(args, "all", False):
        return None

    mapping = {
        "info": ValidationSeverity.INFO,
        "warning": ValidationSeverity.WARNING,
        "critical": ValidationSeverity.CRITICAL,
    }
    raw = getattr(args, "severity", None) or []
    if not raw:
        raw = ["warning"]
    return {mapping[s] for s in raw}


def _extract_detected_iccid(vm: ValidationManager) -> Optional[str]:
    for iss in reversed(vm.issues):
        if getattr(iss, "category", "") == "ICCID Detection":
            msg = getattr(iss, "message", "") or ""
            # message is already the ICCID in current implementation
            digits = "".join(ch for ch in msg if ch.isdigit())
            if 18 <= len(digits) <= 22:
                return digits
    return None


def _load_and_validate(file_path: str) -> tuple[XTIParser, ValidationManager]:
    parser = XTIParser()
    parser.parse_file(file_path)

    vm = ValidationManager()
    for idx, trace_item in enumerate(parser.trace_items):
        vm.validate_trace_item(trace_item, idx)
    vm.finalize_validation()

    return parser, vm


def _to_sort_key(ts: Optional[str]) -> str:
    """Convert a timestamp string to a comparable sort key."""
    try:
        return XTIParser().get_timestamp_sort_key(ts)
    except Exception:
        return ts or ""


def _filter_issues(
    issues: list[Any],
    severities: Optional[set[ValidationSeverity]],
    since: Optional[str],
    until: Optional[str],
    categories: Optional[list[str]],
) -> list[Any]:
    out = issues

    if severities:
        out = [i for i in out if getattr(i, "severity", None) in severities]

    since_key = _to_sort_key(since) if since else None
    until_key = _to_sort_key(until) if until else None
    if since_key or until_key:
        filtered: list[Any] = []
        for i in out:
            key = _to_sort_key(getattr(i, "timestamp", None))
            if since_key and key < since_key:
                continue
            if until_key and key > until_key:
                continue
            filtered.append(i)
        out = filtered

    if categories:
        needles = [c.strip().lower() for c in categories if c and c.strip()]
        if needles:
            out = [
                i
                for i in out
                if any(n in (getattr(i, "category", "") or "").lower() for n in needles)
            ]

    return out


def _flatten_details_tree(node: Any) -> str:
    try:
        parts: list[str] = []

        def rec(n: Any) -> None:
            if not n:
                return
            name = getattr(n, "name", "") or ""
            val = getattr(n, "value", "") or ""
            content = getattr(n, "content", "") or ""
            if name or val:
                parts.append(f"{name}: {val}")
            if content:
                parts.append(content)
            for ch in getattr(n, "children", []) or []:
                rec(ch)

        rec(node)
        return "\n".join([p for p in parts if p]).lower()
    except Exception:
        return ""


def _build_session_entries(parser: XTIParser) -> list[dict[str, Any]]:
    from xti_viewer.xti_parser import tag_server_from_ips
    from datetime import datetime

    entries: list[dict[str, Any]] = []
    sessions = sorted(parser.channel_sessions, key=lambda s: s.opened_at or s.closed_at or datetime.min)
    for i, s in enumerate(sessions):
        opened = s.opened_at.strftime("%m/%d/%Y %H:%M:%S") if s.opened_at else "Unknown"
        closed = s.closed_at.strftime("%m/%d/%Y %H:%M:%S") if s.closed_at else "Not closed"
        sort_key = (s.opened_at.isoformat(sep=" ") if s.opened_at else "0000-00-00T00:00:00")

        ips = sorted(list(s.ips)) if getattr(s, "ips", None) else []
        if not ips:
            ips_display = ["(DNS by ME)"]
        else:
            ips_display = ips

        server = tag_server_from_ips(s.ips)

        entries.append(
            {
                "kind": "Session",
                "session_number": i + 1,
                "time": opened,
                "sort_key": sort_key,
                "server": server,
                "protocol": s.protocol or "",
                "port": s.port or "",
                "opened_at": opened,
                "closed_at": closed,
                "ips": ips_display,
            }
        )
    return entries


def _build_event_entries(parser: XTIParser, vm: ValidationManager) -> list[dict[str, Any]]:
    import re

    entries: list[dict[str, Any]] = []
    detected_iccid = _extract_detected_iccid(vm)

    for idx, item in enumerate(parser.trace_items):
        s = (item.summary or "").lower()
        t = item.timestamp or ""
        sort_key = getattr(item, "timestamp_sort_key", "") or parser.get_timestamp_sort_key(item.timestamp)
        d = _flatten_details_tree(getattr(item, "details_tree", None))
        ev: Optional[str] = None

        if "refresh" in s:
            ev = "Refresh"
        elif "cold reset" in s:
            ev = "Cold Reset"
        elif (
            ("link dropped" in s)
            or ("channel status" in s and ("link off" in s or "pdp not activated" in s))
            or ("status:" in d and ("link dropped" in d or "link off" in d))
        ):
            ev = "Link Dropped"
        elif "iccid" in s or "integrated circuit card identifier" in s:
            ev = f"ICCID: {detected_iccid}" if detected_iccid else "ICCID"

        if not ev and (
            "bearer independent protocol error" in s
            or "bip error" in s
            or ("general result:" in d and "bearer independent protocol error" in d)
        ):
            cause = None
            try:
                raw_hex = (item.rawhex or "").replace(" ", "").upper()
                m = re.search(r"(?:03|83)023A([0-9A-F]{2})", raw_hex)
                if m:
                    cause = m.group(1)
            except Exception:
                cause = None
            ev = f"BIP Error: 0x{cause}" if cause else "BIP Error"

        if ev:
            entries.append(
                {
                    "kind": "Event",
                    "time": t,
                    "sort_key": sort_key,
                    "index": idx,
                    "label": ev,
                }
            )

    # de-duplicate identical ICCID events if present multiple times
    deduped: list[dict[str, Any]] = []
    seen = set()
    for e in entries:
        key = (e.get("kind"), e.get("label"))
        if key in seen and str(e.get("label", "")).startswith("ICCID"):
            continue
        seen.add(key)
        deduped.append(e)

    return deduped


def _build_flow_timeline(parser: XTIParser, vm: ValidationManager, include_sessions: bool, include_events: bool) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    if include_sessions:
        timeline.extend(_build_session_entries(parser))
    if include_events:
        timeline.extend(_build_event_entries(parser, vm))
    timeline.sort(key=lambda x: (x.get("sort_key") or "", 0 if x.get("kind") == "Session" else 1))
    return timeline


def _render_flow_timeline_text(file_path: str, vm: ValidationManager, timeline: list[dict[str, Any]]) -> str:
    iccid = _extract_detected_iccid(vm)
    lines: list[str] = []
    lines.append(f"File: {file_path}")
    if iccid:
        lines.append(f"ICCID: {iccid}")
    lines.append(f"Timeline items: {len(timeline)}")
    lines.append("")

    for it in timeline:
        if it.get("kind") == "Session":
            proto = (it.get("protocol") or "").strip() or "?"
            port = it.get("port")
            port_s = f":{port}" if port else ""
            lines.append(
                "[{t}] Session #{n} {server} {proto}{port} {opened} -> {closed}".format(
                    t=it.get("time") or "",
                    n=it.get("session_number") or "?",
                    server=it.get("server") or "Unknown",
                    proto=proto,
                    port=port_s,
                    opened=it.get("opened_at") or "Unknown",
                    closed=it.get("closed_at") or "Not closed",
                )
            )
            ips = it.get("ips") or []
            if ips:
                lines.append(f"  IPs: {', '.join(str(x) for x in ips)}")
        else:
            lines.append(f"[{it.get('time') or ''}] Event idx={it.get('index')} {it.get('label')}")

    lines.append("")
    return "\n".join(lines)


def cmd_flow_overview(args: argparse.Namespace) -> int:
    parser, vm = _load_and_validate(args.xti_file)
    timeline = _build_flow_timeline(parser, vm, include_sessions=True, include_events=True)

    if args.format == "json":
        payload = {
            "file": args.xti_file,
            "iccid": _extract_detected_iccid(vm),
            "timeline": timeline,
        }
        _write_output(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", args.out)
        return 0

    _write_output(_render_flow_timeline_text(args.xti_file, vm, timeline), args.out)
    return 0


def cmd_flow_sessions(args: argparse.Namespace) -> int:
    parser, vm = _load_and_validate(args.xti_file)
    timeline = _build_flow_timeline(parser, vm, include_sessions=True, include_events=False)
    if args.format == "json":
        payload = {"file": args.xti_file, "iccid": _extract_detected_iccid(vm), "sessions": timeline}
        _write_output(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", args.out)
        return 0
    _write_output(_render_flow_timeline_text(args.xti_file, vm, timeline), args.out)
    return 0


def cmd_flow_events(args: argparse.Namespace) -> int:
    parser, vm = _load_and_validate(args.xti_file)
    timeline = _build_flow_timeline(parser, vm, include_sessions=False, include_events=True)
    if args.format == "json":
        payload = {"file": args.xti_file, "iccid": _extract_detected_iccid(vm), "events": timeline}
        _write_output(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", args.out)
        return 0
    _write_output(_render_flow_timeline_text(args.xti_file, vm, timeline), args.out)
    return 0


def cmd_parsing_log(args: argparse.Namespace) -> int:
    _parser, vm = _load_and_validate(args.xti_file)

    sevset = _parse_severities(args)
    issues = _filter_issues(
        list(_iter_issues(vm, None)),
        sevset,
        getattr(args, "since", None),
        getattr(args, "until", None),
        getattr(args, "category", None),
    )

    if args.format == "json":
        payload = {
            "file": args.xti_file,
            "severities": sorted([s.value for s in sevset], key=str) if sevset else ["ALL"],
            "since": getattr(args, "since", None),
            "until": getattr(args, "until", None),
            "category": getattr(args, "category", None) or [],
            "issues": [
                {
                    "severity": iss.severity.value,
                    "category": iss.category,
                    "message": iss.message,
                    "trace_index": iss.trace_index,
                    "timestamp": iss.timestamp,
                    "raw_data": iss.raw_data,
                    "channel_id": iss.channel_id,
                    "command_details": iss.command_details,
                }
                for iss in issues
            ],
        }
        _write_output(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", args.out)
        return 0

    lines: list[str] = []
    lines.append(f"File: {args.xti_file}")
    sev_label = ",".join(sorted([s.value for s in sevset], key=str)) if sevset else "ALL"
    lines.append(f"Issues ({sev_label}): {len(issues)}")
    if getattr(args, "since", None) or getattr(args, "until", None):
        lines.append(f"Range: {getattr(args, 'since', None) or '-inf'} .. {getattr(args, 'until', None) or '+inf'}")
    if getattr(args, "category", None):
        lines.append(f"Category filter: {', '.join(getattr(args, 'category'))}")
    lines.append("")

    for iss in issues:
        ts = iss.timestamp or ""
        lines.append(f"[{iss.severity.value}] idx={iss.trace_index} {ts} {iss.category}: {iss.message}")

    lines.append("")
    _write_output("\n".join(lines), args.out)
    return 0


def cmd_iccid(args: argparse.Namespace) -> int:
    _parser, vm = _load_and_validate(args.xti_file)
    iccid = _extract_detected_iccid(vm)
    if args.format == "json":
        _write_output(json.dumps({"file": args.xti_file, "iccid": iccid}, indent=2, ensure_ascii=False) + "\n", args.out)
        return 0
    _write_output((iccid or "") + "\n", args.out)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    _parser, vm = _load_and_validate(args.xti_file)
    counts = {
        "info": sum(1 for i in vm.issues if i.severity == ValidationSeverity.INFO),
        "warning": sum(1 for i in vm.issues if i.severity == ValidationSeverity.WARNING),
        "critical": sum(1 for i in vm.issues if i.severity == ValidationSeverity.CRITICAL),
        "total": len(vm.issues),
    }
    if args.format == "json":
        _write_output(json.dumps({"file": args.xti_file, "issue_counts": counts}, indent=2, ensure_ascii=False) + "\n", args.out)
        return 0

    lines = [f"File: {args.xti_file}", f"Issues: total={counts['total']} info={counts['info']} warning={counts['warning']} critical={counts['critical']}", ""]
    _write_output("\n".join(lines), args.out)
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="xtiviewer",
        description="Headless CLI for XTI Viewer (Flow Overview / Parsing Log)",
    )

    sub = ap.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("xti_file", help="Path to .xti file")
        p.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )
        p.add_argument(
            "--out",
            default=None,
            help="Write output to a file instead of stdout",
        )

    p_flow = sub.add_parser("flow-overview", help="Print Flow Overview (sessions + key events) in chronological order")
    add_common(p_flow)
    p_flow.set_defaults(func=cmd_flow_overview)

    p_flow_sessions = sub.add_parser("flow-sessions", help="Print sessions only")
    add_common(p_flow_sessions)
    p_flow_sessions.set_defaults(func=cmd_flow_sessions)

    p_flow_events = sub.add_parser("flow-events", help="Print key events only")
    add_common(p_flow_events)
    p_flow_events.set_defaults(func=cmd_flow_events)

    p_log = sub.add_parser("parsing-log", help="Print Parsing Log (validation issues)")
    add_common(p_log)
    p_log.add_argument(
        "--severity",
        action="append",
        choices=["info", "warning", "critical"],
        default=[],
        help="Include a severity (repeatable). Default: warning",
    )
    p_log.add_argument(
        "--all",
        action="store_true",
        help="Show all severities (info+warning+critical)",
    )
    p_log.add_argument(
        "--since",
        default=None,
        help="Only include issues at/after this timestamp (supports UT/ISO/time-only formats)",
    )
    p_log.add_argument(
        "--until",
        default=None,
        help="Only include issues at/before this timestamp (supports UT/ISO/time-only formats)",
    )
    p_log.add_argument(
        "--category",
        action="append",
        default=[],
        help="Only include issues whose category contains this string (repeatable)",
    )
    p_log.set_defaults(func=cmd_parsing_log)

    p_iccid = sub.add_parser("iccid", help="Print detected ICCID")
    add_common(p_iccid)
    p_iccid.set_defaults(func=cmd_iccid)

    p_stats = sub.add_parser("stats", help="Print validation stats")
    add_common(p_stats)
    p_stats.set_defaults(func=cmd_stats)

    # Scenario
    p_scn = sub.add_parser(
        "scenario",
        aliases=["Scenario"],
        help="Run a saved Scenario against an XTI file (or list scenarios)",
    )
    p_scn.add_argument(
        "scenario_name",
        nargs="?",
        help="Scenario name (use -l to list)",
    )
    p_scn.add_argument(
        "xti_file",
        nargs="?",
        help="Path to .xti file",
    )
    p_scn.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all scenario names",
    )
    p_scn.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    p_scn.add_argument(
        "--out",
        default=None,
        help="Write output to a file instead of stdout",
    )
    p_scn.set_defaults(func=cmd_scenario)

    return ap


def main(argv: Optional[list[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        # e.g. piping to `head`/`more` and downstream closes
        return 0
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
