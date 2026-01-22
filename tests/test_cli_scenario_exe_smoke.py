import os
import json
import subprocess
import sys
import pytest


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cli_scenario_exe_smoke():
    repo_root = _repo_root()
    exe_path = os.path.join(repo_root, "dist", "XTIViewerCLI.exe")
    if not os.path.exists(exe_path):
        pytest.skip("dist/XTIViewerCLI.exe not found")

    xti_path = os.path.join(repo_root, "test.xti")
    if not os.path.exists(xti_path):
        pytest.skip("test.xti not found")

    # List scenarios (JSON)
    p = subprocess.run(
        [exe_path, "Scenario", "-l", "--format", "json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert p.returncode == 0, p.stderr

    payload = json.loads(p.stdout)
    names = payload.get("scenarios")
    assert isinstance(names, list) and names, "Expected at least one scenario"

    scenario_name = "Default" if "Default" in names else str(names[0])

    # Run scenario (JSON)
    p2 = subprocess.run(
        [exe_path, "Scenario", scenario_name, xti_path, "--format", "json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert p2.returncode == 0, p2.stderr

    out = json.loads(p2.stdout)
    assert out.get("file") == xti_path
    assert out.get("scenario") == scenario_name
    assert "overall_status" in out
    assert isinstance(out.get("results"), list)
