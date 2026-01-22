import os
import sys
import json
import pytest

# Ensure repo package import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_config
from xti_viewer import cli


def test_cli_scenario_list(monkeypatch, capsys):
    real_load_config = app_config.load_config

    def fake_load_config():
        return {
            "classification": real_load_config().get("classification", {}),
            "scenarios": {
                "Default": {"sequence": ["DNSbyME", "DNS"], "constraints": {"max_gap_enabled": False, "max_gap_seconds": 30}},
                "MyScenario": {"sequence": ["TAC"], "constraints": {"max_gap_enabled": True, "max_gap_seconds": 10}},
            },
            "selected_scenario": "MyScenario",
        }

    monkeypatch.setattr(app_config, "load_config", fake_load_config)

    rc = cli.main(["scenario", "-l"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Scenarios:" in out
    assert "Default" in out
    assert "MyScenario" in out


def test_cli_scenario_run_json(monkeypatch, capsys):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    xti_path = os.path.join(repo_root, "test.xti")
    if not os.path.exists(xti_path):
        pytest.skip("test.xti not found")

    real_load_config = app_config.load_config

    def fake_load_config():
        # Keep classification from real config (so tagging works), but add scenarios.
        cfg = real_load_config()
        cfg["scenarios"] = {
            "Default": {"sequence": ["DNSbyME", "DNS", "TAC"], "constraints": {"max_gap_enabled": False, "max_gap_seconds": 30}}
        }
        cfg["selected_scenario"] = "Default"
        return cfg

    monkeypatch.setattr(app_config, "load_config", fake_load_config)

    rc = cli.main(["Scenario", "Default", xti_path, "--format", "json"])
    assert rc == 0

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["scenario"] == "Default"
    assert payload["file"] == xti_path
    assert "overall_status" in payload
    assert isinstance(payload.get("results"), list)
    assert payload["results"], "Expected at least one step result"
