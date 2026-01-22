# Flow Overview and Parsing Log: Criteria and Coverage

This document explains exactly what appears in the Flow Overview (timeline) and Parsing Log tabs, how items are selected, how they are ordered and filtered, and what each severity means.

## Flow Overview

- Data Source: Built from `parser.get_channel_groups()` (sessions) plus a small set of key events scanned directly from `parser.trace_items`.
- Row Types: Two kinds of rows are mixed chronologically:
  - Session: Channel group with metadata (server, port, protocol, role, IPs, opened/closed/duration).
  - Event: Highlight events extracted from trace items (card/service context), kept lightweight.
- Included Events:
  - Refresh: Summary contains "refresh" (case-insensitive).
  - Cold Reset: Summary contains "cold reset".
  - ICCID: Summary or nearby details indicate an ICCID; we attempt to extract and display the decoded ICCID if found.
- Session Label Normalization:
  - Server name "Google DNS" → label shown as "DNS".
  - `Open Channel` groups → label shown as "BIP Session".
- Columns:
  - Session: Kind, Label, Time, Port, Protocol, Role, Targeted Server, IPs, Opened, Closed, Duration.
  - Event: Kind, Label, Time; other columns are empty for events.
  - UI may hide Role/Time to reduce noise; CSV export includes all available columns.
- Sorting:
  - All rows are sorted chronologically. Sessions prefer the timestamp of the first trace item in the session; otherwise, session "Opened" time is used. Events are sorted by their item timestamp.
- Filters & Shading:
  - Show: Sessions & Events | Sessions Only | Events Only (filter toggles the Kind column via regex).
  - Event rows render with a light background for quick visual scanning.
- Interactions:
  - Double-click Session: Applies a session filter in the main trace, switches to TLS Flow, and reconstructs the TLS sequence for that session. Also sets the right-pane tabs (Summary, Handshake, Ladder, Raw) accordingly.
  - Double-click Event: Navigates directly to that trace index in the main trace view (centered selection).
- Export:
  - Header button "Export CSV" exports the currently built timeline data.

### Coverage Notes
- Events are intentionally minimal to keep signal high: Refresh, Cold Reset, ICCID. They offer quick anchors for typical device/session context.
- Additional events can be added later (e.g., power off/on nuances) but are currently out of scope to maintain clarity.

## Parsing Log

- Source: `ValidationManager` scans every `trace_item` once and emits `ValidationIssue` entries. The UI renders these in a sortable QTreeWidget.
- Severities:
  - Info (blue): Informational context, not indicative of failure.
  - Warning (orange): Potential issues that may affect behavior.
  - Critical (red): Serious problems or protocol violations.
- Severity Mapping (not exhaustive; most common cases):
  - Location Status:
    - Normal Service → Info
    - Limited Service → Warning
    - No Service → Warning (downgraded from Critical)
  - Card Events:
    - Card Powered Off Event (MSC 1900) → Info
    - Cold Reset / Power On / Refresh → Info
  - Channel Analysis:
    - OPEN CHANNEL without IP (likely DNS Opened by ME) → Info
  - Channel Status:
    - Link Dropped / Link Off (Event Download: Channel Status) → Critical
  - State Machine Violations:
    - CLOSE CHANNEL without preceding OPEN → Critical
    - Multiple OPENs on same channel → Critical; also adds a Resource Leak on the previous open
    - Unclosed channel at end of trace → Critical (Resource Leak)
  - Status Words / Errors:
    - SW 5023 (Technical problem) → Critical
    - BIP Error (Result TLV 03 02 3A xx) → Critical, includes cause when available
  - Trace Analysis:
    - Explicitly marked "unexpected" Terminal Response → Info (conservative to avoid false positives)
  - ICCID Detection:
    - Successfully decoded ICCID after SELECT EF_ICCID + READ BINARY → Info (message is the ICCID)
- Ordering:
  - The grid sorts by the Timestamp column ascending (chronological).
- Filters & Persistence:
  - Preset combo: All, Critical, Warning, Info.
  - Quick multi-select buttons for Critical/Warning/Info (non-exclusive). The tool persists the last multi-selection (e.g., "Critical,Warning") or "All".
  - The header shows a live summary (counts per severity) from the validation manager.

## Parity & Intent
- Flow Overview aims for XTI-style clarity: sessions are the backbone, with only the most helpful events mixed in.
- Parsing Log prioritizes operator-friendly phrasing and conservative severity for non-failures.
- TLS Flow tabs (Summary/Handshake/Ladder/Raw) are driven by the same session selection, with normalized labels and human-readable decoding for parity between report- and quick-scan-based paths.

## Appendix: Detection Details
- Event detection (Flow Overview):
  - Refresh: `"refresh" in item.summary.lower()`
  - Cold Reset: `"cold reset" in item.summary.lower()`
  - ICCID: `"iccid" in item.summary.lower()` or decoded from nearby READ BINARY data (BCD), or found in details; the docstring for `_find_iccid_value_around` explains the heuristic.
- Location Status matching (Parsing Log):
  - Pattern in raw hex (stripped spaces, uppercased):
    - `1B0100` → Normal Services (Info)
    - `1B0101` → Limited Services (Warning)
    - `1B0102` → No Services (Warning)
- DNS Open Channel heuristic:
  - Missing IP in OPEN CHANNEL is considered Info, consistent with DNS channels opened by ME.
