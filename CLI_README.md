# XTIViewerCLI — Command Line Usage

This document describes the **headless CLI** for extracting information from Universal Tracer `.xti` files **without launching the GUI**.

You can use it either:
- From Python: `python -m xti_viewer.cli ...`
- From the packaged console executable: `XTIViewerCLI.exe ...`

---

## Quick Start

### Option A — Run via Python

```bash
python -m xti_viewer.cli flow-overview path\to\file.xti
python -m xti_viewer.cli parsing-log  path\to\file.xti
```

### Option B — Run via EXE

If you have `XTIViewerCLI.exe` somewhere on disk:

```powershell
C:\path\to\XTIViewerCLI.exe flow-overview C:\path\to\file.xti
C:\path\to\XTIViewerCLI.exe parsing-log  C:\path\to\file.xti
```

---

## Common Options

Most commands support:

- `--format text|json`
  - `text` prints human-readable output (default)
  - `json` prints machine-readable JSON
- `--out <file>`
  - Writes output to a file instead of stdout

Example:

```powershell
C:\path\to\XTIViewerCLI.exe flow-overview C:\path\to\file.xti --format json --out flow.json
```

---

## Commands

### 1) `flow-overview`

**What it does:** Prints a single **chronological timeline** combining:
- **Sessions** (OPEN→CLOSE channel sessions)
- **Key events** (e.g., Refresh, Cold Reset, ICCID, Link Dropped, BIP Error)

**Examples:**

```powershell
C:\path\to\XTIViewerCLI.exe flow-overview C:\path\to\file.xti
C:\path\to\XTIViewerCLI.exe flow-overview C:\path\to\file.xti --format json
```

**JSON output shape (high-level):**

- `file`
- `iccid` (if detected)
- `timeline` (array of timeline items, each with `kind` = `Session` or `Event`)

---

### 2) `flow-sessions`

**What it does:** Prints **sessions only** (no events), in chronological order.

**Examples:**

```powershell
C:\path\to\XTIViewerCLI.exe flow-sessions C:\path\to\file.xti
C:\path\to\XTIViewerCLI.exe flow-sessions C:\path\to\file.xti --format json
```

---

### 3) `flow-events`

**What it does:** Prints **events only** (no sessions), in chronological order.

Events currently include:
- `Refresh`
- `Cold Reset`
- `ICCID` (uses validation-derived ICCID when available)
- `Link Dropped`
- `BIP Error` (with cause code when present)

**Examples:**

```powershell
C:\path\to\XTIViewerCLI.exe flow-events C:\path\to\file.xti
C:\path\to\XTIViewerCLI.exe flow-events C:\path\to\file.xti --format json
```

---

### 4) `parsing-log`

**What it does:** Prints **validation issues** (the same data source used by the GUI Parsing Log).

#### Severity selection

- Default (if you don’t specify anything): **warnings only**
- `--all`: show info + warning + critical
- `--severity <level>`: include a severity (repeatable)
  - allowed: `info`, `warning`, `critical`

Examples:

```powershell
# default: warning
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti

# all severities
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti --all

# only critical
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti --severity critical

# warning + info
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti --severity warning --severity info
```

#### Category filtering

Use `--category` to filter by issue category (substring match, case-insensitive). Repeatable.

```powershell
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti --category "Location Status"
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti --category "Card Event" --category "Location Status"
```

#### Time range filtering (`--since` / `--until`)

Use `--since` and/or `--until` to keep only issues inside a time window.

Accepted formats are flexible (the tool normalizes timestamps using the same logic as the parser). Common examples:
- Universal Tracer-like: `MM/DD/YYYY HH:MM:SS` (milliseconds optional)
- ISO-like: `YYYY-MM-DDTHH:MM:SS`

Examples:

```powershell
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti --all --since "11/06/2025 16:55:42" --until "11/06/2025 16:55:46"
```

#### JSON output

```powershell
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti --all --format json
C:\path\to\XTIViewerCLI.exe parsing-log C:\path\to\file.xti --category "Location Status" --severity warning --format json
```

---

### 5) `iccid`

**What it does:** Prints the detected ICCID (empty output if not found).

**Examples:**

```powershell
C:\path\to\XTIViewerCLI.exe iccid C:\path\to\file.xti
C:\path\to\XTIViewerCLI.exe iccid C:\path\to\file.xti --format json
```

---

### 6) `stats`

**What it does:** Prints counts of validation issues by severity.

**Examples:**

```powershell
C:\path\to\XTIViewerCLI.exe stats C:\path\to\file.xti
C:\path\to\XTIViewerCLI.exe stats C:\path\to\file.xti --format json
```

---

### 7) `scenario`

**What it does:** Runs a saved **Scenario** (sequence + optional constraints) against an `.xti` file and prints results.

Scenarios are shared with the GUI and stored in `config.json`.

#### Advanced step constraints (optional / forbidden / min/max)

By default, each step in `sequence` is **required exactly once** (same as before).

You can also define steps as objects to express constraints:

- `presence`: `required` | `optional` | `forbidden`
- `min` / `max` (or `min_count` / `max_count`): expected occurrence count in the segment
- `too_few` / `too_many` (or `on_too_few` / `on_too_many`): `ok` | `warn` | `fail`

Additional useful fields:

- `any_of`: list of step types to match (either/or)
- `scope`: `segment` (default) or `global` (useful for forbidden steps anywhere)
- `label`: custom name shown in outputs

Example `config.json` snippet:

```json
{
  "scenarios": {
    "MyScenario": {
      "sequence": [
        "DNSbyME",
        {"type": "Refresh", "presence": "optional"},
        {"label": "DNS (either)", "any_of": ["DNSbyME", "DNS"], "presence": "optional"},
        {"type": "DNS", "presence": "forbidden", "scope": "global", "too_many": "warn"},
        {"type": "TAC", "presence": "required", "min": 1, "max": 2, "too_many": "warn"}
      ],
      "constraints": {
        "max_gap_enabled": true,
        "max_gap_seconds": 30,
        "max_gap_on_unknown": "warn",
        "max_gap_on_violation": "fail"
      }
    }
  }
}
```

#### List scenarios

```powershell
C:\path\to\XTIViewerCLI.exe Scenario -l
```

#### Run a scenario

```powershell
# text output
C:\path\to\XTIViewerCLI.exe Scenario Default C:\path\to\file.xti

# json output
C:\path\to\XTIViewerCLI.exe Scenario Default C:\path\to\file.xti --format json
```

---

## Building the CLI EXE

If you build from source using the provided PowerShell script:

```powershell
# If scripts are blocked in your environment (common on corporate machines):
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Build GUI + CLI
./build_exe.ps1 -BuildCli
```

Output:
- `dist\XTIViewer.exe` (GUI)
- `dist\XTIViewerCLI.exe` (console CLI)

---

## Notes

- The CLI is designed to be safe to run headlessly (no Qt imports).
- For automation, prefer `--format json`.
- For large `.xti` files, parsing can take some time; the CLI does a full parse + validation on each run.
