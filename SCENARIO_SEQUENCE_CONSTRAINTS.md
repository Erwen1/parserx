# Scenario Sequences & Constraints (XTIViewer)

This document explains how **Scenarios** work in XTIViewer:

- `sequence`: ordered step definitions (strings or objects)
- `constraints`: scenario-level rules (currently max-gap timing)

It also includes practical suggestions for writing robust scenarios.

---

## 1) What is a Scenario?

A **Scenario** is an *expected pattern* in a trace:

- you define a **sequence** of steps (DNSbyME → DNS → DP+ → TAC …)
- the scenario engine scans reconstructed sessions/events and checks if the pattern matches
- you get a per-step result (`OK`, `WARN`, `FAIL`) plus an overall status

Where it’s stored:
- GUI + CLI share the same data via `config.json` under `scenarios`

---

## 2) Scenario file shape (`config.json`)

Minimal example:

```json
{
  "scenarios": {
    "Default": {
      "sequence": ["DNSbyME", "DNS", "DP+", "TAC"],
      "constraints": {
        "max_gap_enabled": false,
        "max_gap_seconds": 30
      }
    }
  },
  "selected_scenario": "Default"
}
```

Notes:
- `sequence` supports **string steps** (legacy/simple) and **object steps** (advanced)
- if you only use strings, behavior matches the old implementation (required exactly once)

---

## 3) Sequence steps

### 3.1 Step types you can use

Typical session-based types:
- `DNSbyME`
- `DNS`
- `DP+`
- `TAC`

Event-based types (also supported):
- `Refresh`
- `ICCID`
- `Location Status (Limited Service)`

---

## 4) Step formats

### 4.1 String step (simple)

```json
"DNS"
```

Meaning:
- step is **required**
- expected **exactly once**

This is the best choice when you don’t need extra constraints.

### 4.2 Object step (advanced)

```json
{ "type": "TAC", "presence": "required", "min": 1, "max": 2, "too_many": "warn" }
```

Object steps allow: optional/forbidden, min/max counts, either/or matches, and global rules.

---

## 5) Step constraint fields (object step)

### 5.1 `type`

The primary step type, e.g.:

```json
{ "type": "TAC" }
```

### 5.2 `presence`

Controls whether this step is expected:

- `required` (default): must be present
- `optional`: allowed to be missing
- `forbidden`: should not occur

Examples:

```json
{ "type": "Refresh", "presence": "optional" }
{ "type": "DNS", "presence": "forbidden" }
```

### 5.3 `min` / `max` (or `min_count` / `max_count`)

Controls occurrence counts for the step (within its matching `scope`).

Defaults (important):
- `required`: min=1, max=1
- `optional`: min=0, max=1
- `forbidden`: max=0

Examples:

```json
{ "type": "TAC", "min": 2 }
{ "type": "TAC", "max": 3, "too_many": "warn" }
```

### 5.4 `too_few` / `too_many` (or `on_too_few` / `on_too_many`)

When min/max rules are violated, what status should the engine emit:

- `ok`
- `warn`
- `fail`

Examples:

```json
{ "type": "TAC", "min": 1, "too_few": "fail" }
{ "type": "TAC", "max": 1, "too_many": "warn" }

{ "type": "DNS", "presence": "forbidden", "scope": "global", "too_many": "fail" }
```

Practical meaning:
- **Too few** usually means *missing required step* (often `fail`)
- **Too many** is often an anomaly (frequently `warn`)

### 5.5 `scope`

Where to search for this step:

- `segment` (default): only inside the current “segment”
- `global`: the whole trace

What is a **segment**?
- the engine advances step-by-step
- a step’s segment is effectively:
  - after the previous consumed step
  - up to (but not beyond) the next **required** step

Why this matters:
- optional/forbidden checks in `segment` are local (“shouldn’t happen *here*”)
- `global` is for rules like “must never happen anywhere”

Examples:

```json
{ "type": "DNS", "presence": "forbidden", "scope": "segment", "too_many": "warn" }
{ "type": "DNS", "presence": "forbidden", "scope": "global", "too_many": "warn" }
```

### 5.6 `any_of` (either/or)

Match *any of multiple types*:

```json
{ "label": "DNS (either)", "any_of": ["DNSbyME", "DNS"], "presence": "optional" }
```

Behavior:
- occurrences of any listed type count toward this step
- the step’s evidence can include which types matched

### 5.7 `label`

Human-friendly name shown in GUI/CLI output:

```json
{ "label": "Connectivity established", "type": "TAC", "min": 1 }
```

---

## 6) Scenario-level constraints (`constraints`)

### 6.1 `max_gap_enabled` / `max_gap_seconds`

If enabled, checks the time gap between consecutive *consumed* steps.

```json
{
  "max_gap_enabled": true,
  "max_gap_seconds": 30
}
```

### 6.2 `max_gap_on_unknown` / `max_gap_on_violation`

Controls severity when timing check cannot be computed or is violated:

- `max_gap_on_unknown`: what if timestamps are missing (default `WARN`)
- `max_gap_on_violation`: what if gap exceeds limit (default `FAIL`)

```json
{
  "max_gap_enabled": true,
  "max_gap_seconds": 30,
  "max_gap_on_unknown": "warn",
  "max_gap_on_violation": "fail"
}
```

Notes:
- max-gap is not applied to `scope: "global"` steps (global rules aren’t tied to a specific point in time)
- forbidden steps do not “advance” the cursor

---

## 7) How results are computed (important behaviors)

### 7.1 Status levels

- `OK`: step satisfied
- `WARN`: suspicious but not a hard failure
- `FAIL`: scenario expectation broken

### 7.2 Validation issues can bump severity

If a step matches and the underlying trace range contains **CRITICAL validation issues**, the step is upgraded to at least `WARN` (unless already `FAIL`).

This is independent of min/max rules.

---

## 8) Recommended patterns (suggestions)

### Pattern A: Strict “happy path”
Use strings only:

```json
"sequence": ["DNSbyME", "DNS", "DP+", "TAC"]
```

Good when:
- you want a simple, stable baseline

### Pattern B: Optional noise step

```json
{
  "type": "Refresh",
  "presence": "optional"
}
```

Good when:
- refresh may or may not happen
- you don’t want missing refresh to fail the scenario

### Pattern C: Local forbidden (“shouldn’t happen here”)

```json
{ "type": "DNS", "presence": "forbidden", "scope": "segment", "too_many": "warn" }
```

Good when:
- DNS is okay globally but not expected in a particular phase

### Pattern D: Global forbidden (“must never happen”)

```json
{ "type": "DNS", "presence": "forbidden", "scope": "global", "too_many": "fail" }
```

Good when:
- you’re enforcing a policy (e.g., no DNS at all)

### Pattern E: Either/or step

```json
{ "label": "DNS (either)", "any_of": ["DNSbyME", "DNS"], "presence": "required" }
```

Good when:
- devices/firmware variants produce different but equivalent steps

### Pattern F: Expected repetition, but bounded

```json
{ "type": "TAC", "min": 1, "max": 2, "too_many": "warn" }
```

Good when:
- retries can happen, but too many retries is suspicious

### Pattern G: Timing SLA (max gap)

```json
"constraints": {
  "max_gap_enabled": true,
  "max_gap_seconds": 30,
  "max_gap_on_unknown": "warn",
  "max_gap_on_violation": "fail"
}
```

Good when:
- you’re validating performance/latency expectations

---

## 9) Common mistakes to avoid

- **Using `global` scope for a step that you want to be sequential.**
  - `global` is mainly intended for forbidden/policy checks.

- **Forgetting that default max for required/optional is 1.**
  - If a step can legitimately repeat, set `max` explicitly.

- **Mixing GUI editing with advanced object steps without saving.**
  - The GUI can edit these now, but if you have legacy scenarios, ensure you hit Save.

---

## 10) Example: full scenario

```json
{
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
```

---

## 11) Next ideas (if you want more power)

High-value extensions you might add next:

1. **Group rules** ("at least one of these steps must occur") without forcing a specific `any_of` step in the sequence.
2. **Not-before / not-after** constraints (e.g. "TAC must not occur before DNS").
3. **Windowed global rules** (forbidden only within the first N seconds / first M trace items).
4. **Custom message** per violation for friendlier reporting.

If you tell me your top 2–3 real-world scenarios, I can recommend the smallest, cleanest schema to cover them.
