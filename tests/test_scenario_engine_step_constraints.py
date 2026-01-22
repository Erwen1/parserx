from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from xti_viewer import scenario_engine as se
from xti_viewer.scenario_engine import (
    ScenarioStep,
    ScenarioStepPresence,
    ScenarioStepScope,
    ScenarioStepType,
    run_scenario,
)


class _TI:
    def __init__(self, summary: str = "", rawhex: str = "00"):
        self.summary = summary
        self.rawhex = rawhex


class _Session:
    def __init__(self, idx: int, ips: set[str], opened_at: datetime | None = None):
        self.traceitem_indexes = [idx]
        self.ips = ips
        self.opened_at = opened_at


class _Parser:
    def __init__(self, sessions: list[_Session]):
        self.channel_sessions = sessions
        # Provide enough trace items so _traceitem_bytes works.
        max_idx = max((max(s.traceitem_indexes) for s in sessions), default=0)
        self.trace_items = [_TI() for _ in range(max_idx + 1)]


@pytest.fixture(autouse=True)
def _fake_server_tagger(monkeypatch):
    def fake_tag_server_from_ips(ips: set[str]) -> str:
        if not ips:
            return "ME"
        if "1.1.1.1" in ips:
            return "TAC"
        if "2.2.2.2" in ips:
            return "DP+"
        if "3.3.3.3" in ips:
            return "DNS"
        return "Unknown"

    monkeypatch.setattr(se, "tag_server_from_ips", fake_tag_server_from_ips)


def test_optional_step_missing_is_ok():
    t0 = datetime(2026, 1, 16, 12, 0, 0)
    parser = _Parser(
        [
            _Session(0, set(), opened_at=t0),
            _Session(2, {"1.1.1.1"}, opened_at=t0 + timedelta(seconds=2)),
        ]
    )

    steps = [
        ScenarioStep(step_type=ScenarioStepType.DNS_BY_ME),
        ScenarioStep(step_type=ScenarioStepType.DP_PLUS, presence=ScenarioStepPresence.OPTIONAL),
        ScenarioStep(step_type=ScenarioStepType.TAC),
    ]

    res = run_scenario(parser, issues=None, steps=steps)
    assert res.overall_status == "OK"

    assert res.results[1].step.step_type == ScenarioStepType.DP_PLUS
    assert res.results[1].status == "OK"
    assert "Optional step not found" in (res.results[1].message or "")


def test_forbidden_step_present_warns():
    parser = _Parser(
        [
            _Session(0, set()),
            _Session(1, {"3.3.3.3"}),
            _Session(2, {"1.1.1.1"}),
        ]
    )

    steps = [
        ScenarioStep(step_type=ScenarioStepType.DNS_BY_ME),
        ScenarioStep(step_type=ScenarioStepType.DNS, presence=ScenarioStepPresence.FORBIDDEN),
        ScenarioStep(step_type=ScenarioStepType.TAC),
    ]

    res = run_scenario(parser, issues=None, steps=steps)
    assert res.overall_status == "WARN"
    assert res.results[1].status == "WARN"
    assert "Forbidden step present" in (res.results[1].message or "")


def test_required_step_min_count_allows_multiple():
    parser = _Parser(
        [
            _Session(0, set()),
            _Session(2, {"1.1.1.1"}),
            _Session(3, {"1.1.1.1"}),
        ]
    )

    steps = [
        ScenarioStep(step_type=ScenarioStepType.DNS_BY_ME),
        ScenarioStep(
            step_type=ScenarioStepType.TAC,
            presence=ScenarioStepPresence.REQUIRED,
            min_count=2,
            max_count=3,
        ),
    ]

    res = run_scenario(parser, issues=None, steps=steps)
    assert res.overall_status == "OK"
    assert res.results[1].status == "OK"
    assert res.results[1].evidence is not None
    assert int(res.results[1].evidence.count) == 2


def test_any_of_matches_either_type_and_reports_warn_on_forbidden_global():
    # Has both DNSbyME (ME) and DNS sessions.
    parser = _Parser(
        [
            _Session(0, set()),
            _Session(1, {"3.3.3.3"}),
            _Session(2, {"1.1.1.1"}),
        ]
    )

    steps = [
        ScenarioStep(step_type=ScenarioStepType.DNS_BY_ME),
        ScenarioStep(
            step_type=ScenarioStepType.DNS_BY_ME,
            any_of=[ScenarioStepType.DNS_BY_ME, ScenarioStepType.DNS],
            presence=ScenarioStepPresence.OPTIONAL,
            label="DNS either",
        ),
        ScenarioStep(
            step_type=ScenarioStepType.DNS,
            presence=ScenarioStepPresence.FORBIDDEN,
            scope=ScenarioStepScope.GLOBAL,
            on_too_many="WARN",
        ),
        ScenarioStep(step_type=ScenarioStepType.TAC),
    ]

    res = run_scenario(parser, issues=None, steps=steps)
    assert res.overall_status == "WARN"

    # any_of step should be OK and have evidence
    assert res.results[1].status in ("OK", "WARN")
    assert res.results[1].evidence is not None
    assert int(res.results[1].evidence.count) >= 1

    # global forbidden DNS should warn because DNS exists anywhere
    assert res.results[2].status == "WARN"
    assert "Forbidden step present" in (res.results[2].message or "")
