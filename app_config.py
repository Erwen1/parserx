from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from ipaddress import ip_address
from pathlib import Path
from typing import List, Dict, Any


def _get_config_path() -> Path:
    # When packaged (PyInstaller), __file__ points into the temp extraction dir.
    # Use the executable directory so config persists across runs.
    try:
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent / 'config.json'
    except Exception:
        pass
    return Path(__file__).parent / 'config.json'


CONFIG_PATH = _get_config_path()


DEFAULT_CONFIG = {
    "classification": {
        "tac_ips": [
            "13.38.212.83",
            "52.47.40.152",
            "13.39.169.102",
        ],
        "dp_plus_ips": [
            "34.8.202.126",
        ],
        "dns_ips": [
            "8.8.8.8",
            "8.8.4.4",
        ],
    }
    ,
    "scenarios": {
        "Default": {
            "sequence": ["DNSbyME", "DNS", "DP+", "TAC"],
            "constraints": {
                "max_gap_enabled": False,
                "max_gap_seconds": 30,
            },
        }
    },
    "selected_scenario": "Default",
}


def _ensure_config_shape(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = cfg or {}
    if "classification" not in cfg or not isinstance(cfg["classification"], dict):
        cfg["classification"] = {}
    cl = cfg["classification"]
    for key, default in DEFAULT_CONFIG["classification"].items():
        if key not in cl or not isinstance(cl[key], list):
            cl[key] = list(default)

    # Scenarios
    if "scenarios" not in cfg or not isinstance(cfg["scenarios"], dict):
        cfg["scenarios"] = {}
    if not cfg["scenarios"]:
        cfg["scenarios"] = json.loads(json.dumps(DEFAULT_CONFIG["scenarios"]))

    if "selected_scenario" not in cfg or not isinstance(cfg.get("selected_scenario"), str):
        cfg["selected_scenario"] = DEFAULT_CONFIG.get("selected_scenario", "Default")
    if cfg["selected_scenario"] not in cfg["scenarios"]:
        # fall back to any existing scenario, or Default
        try:
            cfg["selected_scenario"] = sorted(cfg["scenarios"].keys())[0]
        except Exception:
            cfg["selected_scenario"] = "Default"
    return cfg


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    return _ensure_config_shape(data)


def save_config(cfg: Dict[str, Any]) -> None:
    cfg = _ensure_config_shape(cfg)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def reset_defaults() -> Dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    save_config(cfg)
    return cfg


def validate_ip_list(ips: List[str]) -> List[str]:
    invalid: List[str] = []
    for s in ips:
        t = s.strip()
        if not t:
            continue
        try:
            ip_address(t)
        except Exception:
            invalid.append(t)
    return invalid


def set_classification_lists(tac_ips: List[str], dp_plus_ips: List[str], dns_ips: List[str]) -> Dict[str, Any]:
    cfg = load_config()
    cfg["classification"]["tac_ips"] = sorted(set([s.strip() for s in tac_ips if s.strip()]))
    cfg["classification"]["dp_plus_ips"] = sorted(set([s.strip() for s in dp_plus_ips if s.strip()]))
    cfg["classification"]["dns_ips"] = sorted(set([s.strip() for s in dns_ips if s.strip()]))
    save_config(cfg)
    return cfg
