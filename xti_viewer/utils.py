"""
Utility functions for the XTI Viewer application.
"""
import os
import json
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox, QWidget
from typing import Optional


class SettingsManager:
    """Manages application settings like last opened directory."""
    
    def __init__(self):
        self.settings = QSettings("XTIViewer", "XTIViewer")
    
    def get_last_directory(self) -> str:
        """Get the last opened directory, defaulting to user's home."""
        return self.settings.value("lastDirectory", os.path.expanduser("~"))
    
    def set_last_directory(self, directory: str):
        """Set the last opened directory."""
        self.settings.setValue("lastDirectory", directory)
    
    def get_window_geometry(self):
        """Get saved window geometry."""
        return self.settings.value("geometry")
    
    def set_window_geometry(self, geometry):
        """Save window geometry."""
        self.settings.setValue("geometry", geometry)
    
    def get_window_state(self):
        """Get saved window state."""
        return self.settings.value("windowState")
    
    def set_window_state(self, state):
        """Save window state."""
        self.settings.setValue("windowState", state)
    
    def get_splitter_state(self, name: str):
        """Get saved splitter state."""
        return self.settings.value(f"splitter_{name}")
    
    def set_splitter_state(self, name: str, state):
        """Save splitter state."""
        self.settings.setValue(f"splitter_{name}", state)

    # Recent files
    def get_recent_files(self) -> list[str]:
        """Return list of recently opened XTI files (most recent first)."""
        try:
            val = self.settings.value("recentFiles", [])
            if val is None:
                return []
            if isinstance(val, list):
                return [str(p) for p in val if p]
            # Sometimes QSettings returns a single string
            if isinstance(val, str):
                return [val] if val else []
            return [str(val)]
        except Exception:
            return []

    def set_recent_files(self, files: list[str]):
        """Persist list of recent files."""
        try:
            normalized = [str(p) for p in (files or []) if p]
            self.settings.setValue("recentFiles", normalized)
        except Exception:
            pass

    def add_recent_file(self, file_path: str, max_items: int = 10):
        """Add a file to the recent files list, keeping most recent first."""
        if not file_path:
            return
        try:
            current = self.get_recent_files()
            file_path = str(file_path)
            # De-dup, preserve order
            current = [p for p in current if p and os.path.normcase(p) != os.path.normcase(file_path)]
            current.insert(0, file_path)
            self.set_recent_files(current[: max(1, int(max_items))])
        except Exception:
            pass

    def clear_recent_files(self):
        """Clear recent files list."""
        try:
            self.settings.setValue("recentFiles", [])
        except Exception:
            pass

    # Generic helpers for feature-level preferences
    def get_parsing_log_filter(self) -> str:
        """Return last-selected parsing log severity filter (default 'All')."""
        try:
            val = self.settings.value("parsingLogFilter", "All")
            return str(val)
        except Exception:
            return "All"

    def set_parsing_log_filter(self, value: str):
        """Persist parsing log severity filter."""
        try:
            self.settings.setValue("parsingLogFilter", value)
        except Exception:
            pass

    def get_parsing_log_filter_multi(self) -> str:
        """Return last-selected multi-severity filter as comma-separated string.
        Example: 'Critical,Warning' or 'All'. Default is 'All'."""
        try:
            val = self.settings.value("parsingLogFilterMulti", "All")
            return str(val)
        except Exception:
            return "All"

    def set_parsing_log_filter_multi(self, value: str):
        """Persist multi-severity filter string."""
        try:
            self.settings.setValue("parsingLogFilterMulti", value)
        except Exception:
            pass

    # Scenario (sequence) helpers
    def get_scenario_sequence(self) -> list[str]:
        """Return saved scenario step sequence.

        Stored as a string list, e.g. ['DNSbyME', 'DNS', 'DP+', 'TAC'].
        """
        try:
            val = self.settings.value("scenarioSequence", ["DNSbyME", "DNS", "DP+", "TAC"])
            if val is None:
                return ["DNSbyME", "DNS", "DP+", "TAC"]
            if isinstance(val, list):
                out = [str(x) for x in val if x]
                return out or ["DNSbyME", "DNS", "DP+", "TAC"]
            if isinstance(val, str):
                # Allow comma-separated fallback
                parts = [p.strip() for p in val.split(',') if p.strip()]
                return parts or ["DNSbyME", "DNS", "DP+", "TAC"]
            return [str(val)]
        except Exception:
            return ["DNSbyME", "DNS", "DP+", "TAC"]

    def set_scenario_sequence(self, steps: list[str]):
        """Persist scenario step sequence."""
        try:
            normalized = [str(s) for s in (steps or []) if str(s).strip()]
            if not normalized:
                normalized = ["DNSbyME", "DNS", "DP+", "TAC"]
            self.settings.setValue("scenarioSequence", normalized)
        except Exception:
            pass

    # Scenario (named) management
    def _default_scenario_dict(self) -> dict:
        return {
            "sequence": ["DNSbyME", "DNS", "DP+", "TAC"],
            "constraints": {
                "max_gap_enabled": False,
                "max_gap_seconds": 30,
            },
        }

    def get_scenarios(self) -> dict:
        """Return mapping: scenario_name -> {sequence: [...], constraints: {...}}."""
        # Preferred storage: config.json (shared with CLI)
        try:
            from app_config import load_config, save_config

            cfg = load_config() or {}
            scenarios = cfg.get("scenarios")
            if isinstance(scenarios, dict) and scenarios:
                return scenarios

            # Migration from old QSettings JSON if present
            raw = self.settings.value("scenariosJson", "")
            if isinstance(raw, str) and raw.strip():
                data = json.loads(raw)
                if isinstance(data, dict) and data:
                    cfg["scenarios"] = data
                    if "selected_scenario" not in cfg:
                        cfg["selected_scenario"] = "Default"
                    save_config(cfg)
                    return data
        except Exception:
            pass

        # Final fallback: synthesize
        seq = self.get_scenario_sequence()
        d = self._default_scenario_dict()
        d["sequence"] = seq or d["sequence"]
        return {"Default": d}

    def save_scenarios(self, scenarios: dict):
        """Persist scenarios mapping to QSettings."""
        try:
            # Keep only JSON-safe primitives
            safe = {}
            for name, payload in (scenarios or {}).items():
                if not isinstance(name, str) or not name.strip():
                    continue
                if not isinstance(payload, dict):
                    continue
                seq = payload.get("sequence")
                if not isinstance(seq, list):
                    seq = []
                normalized_seq = []
                for item in seq:
                    if isinstance(item, str):
                        s = str(item).strip()
                        if s:
                            normalized_seq.append(s)
                        continue
                    if isinstance(item, dict):
                        st = item.get("type") or item.get("step_type") or item.get("step")
                        st = str(st or "").strip()
                        any_of = item.get("any_of")
                        if any_of is not None and not isinstance(any_of, list):
                            any_of = None

                        if not st and not any_of:
                            continue

                        obj = {}
                        if st:
                            obj["type"] = st
                        if isinstance(any_of, list) and any_of:
                            obj["any_of"] = [str(x).strip() for x in any_of if str(x).strip()]
                        # Optional knobs (keep small whitelist for stability)
                        for k in (
                            "label",
                            "scope",
                            "presence",
                            "min",
                            "max",
                            "min_count",
                            "max_count",
                            "too_few",
                            "too_many",
                            "on_too_few",
                            "on_too_many",
                        ):
                            if k in item:
                                obj[k] = item.get(k)
                        normalized_seq.append(obj)
                        continue
                cons = payload.get("constraints")
                if not isinstance(cons, dict):
                    cons = {}
                safe[name] = {
                    "sequence": normalized_seq,
                    "constraints": {
                        "max_gap_enabled": bool(cons.get("max_gap_enabled", False)),
                        "max_gap_seconds": int(cons.get("max_gap_seconds", 30) or 30),
                        "max_gap_on_unknown": str(cons.get("max_gap_on_unknown", "WARN") or "WARN"),
                        "max_gap_on_violation": str(cons.get("max_gap_on_violation", "FAIL") or "FAIL"),
                    },
                }
            if not safe:
                safe = {"Default": self._default_scenario_dict()}
            # Write to config.json for CLI compatibility
            try:
                from app_config import load_config, save_config

                cfg = load_config() or {}
                cfg["scenarios"] = safe
                # keep selected scenario if still present
                sel = cfg.get("selected_scenario")
                if not isinstance(sel, str) or sel not in safe:
                    cfg["selected_scenario"] = sorted(safe.keys())[0]
                save_config(cfg)
            except Exception:
                pass

            # Also keep a QSettings cache (non-critical)
            self.settings.setValue("scenariosJson", json.dumps(safe, ensure_ascii=False))
        except Exception:
            pass

    def get_selected_scenario_name(self) -> str:
        # Prefer config.json
        try:
            from app_config import load_config

            cfg = load_config() or {}
            sel = cfg.get("selected_scenario")
            if isinstance(sel, str) and sel:
                return sel
        except Exception:
            pass

        try:
            val = self.settings.value("selectedScenario", "Default")
            return str(val) if val else "Default"
        except Exception:
            return "Default"

    def set_selected_scenario_name(self, name: str):
        # Write to config.json
        try:
            from app_config import load_config, save_config

            cfg = load_config() or {}
            scenarios = cfg.get("scenarios")
            n = str(name or "Default")
            if isinstance(scenarios, dict) and scenarios and n in scenarios:
                cfg["selected_scenario"] = n
            else:
                cfg["selected_scenario"] = "Default"
            save_config(cfg)
        except Exception:
            pass

        # Also keep QSettings cache
        try:
            self.settings.setValue("selectedScenario", str(name or "Default"))
        except Exception:
            pass


def show_error_dialog(parent: Optional[QWidget], title: str, message: str, details: str = ""):
    """
    Show an error dialog with optional details.
    
    Args:
        parent: Parent widget
        title: Dialog title
        message: Main error message
        details: Optional detailed error information
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    
    if details:
        msg_box.setDetailedText(details)
    
    msg_box.exec()


def show_info_dialog(parent: Optional[QWidget], title: str, message: str):
    """
    Show an information dialog.
    
    Args:
        parent: Parent widget
        title: Dialog title
        message: Information message
    """
    QMessageBox.information(parent, title, message)


def validate_xti_file(file_path: str) -> tuple[bool, str]:
    """
    Validate if a file appears to be a valid XTI file.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    if not os.path.isfile(file_path):
        return False, "Path is not a file"
    
    # Check file extension
    if not file_path.lower().endswith('.xti'):
        return False, "File does not have .xti extension"
    
    # Check file size (basic sanity check)
    try:
        size = os.path.getsize(file_path)
        if size == 0:
            return False, "File is empty"
        if size > 100 * 1024 * 1024:  # 100MB limit
            return False, "File is too large (>100MB)"
    except OSError as e:
        return False, f"Cannot access file: {e}"
    
    # Try to read the first few bytes to check if it looks like XML
    try:
        with open(file_path, 'rb') as f:
            header = f.read(1024).decode('utf-8', errors='ignore')
            if not header.strip().startswith('<?xml') and '<tracedata' not in header:
                return False, "File does not appear to be a valid XML/XTI file"
    except Exception as e:
        return False, f"Cannot read file: {e}"
    
    return True, ""


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def safe_filename(filename: str) -> str:
    """
    Create a safe filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    invalid_chars = '<>:"/\\|?*'
    safe_name = ''.join(c for c in filename if c not in invalid_chars)
    return safe_name.strip()