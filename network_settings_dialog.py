from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

import json

from app_config import load_config, save_config, reset_defaults, validate_ip_list


def _join_lines(items: List[str]) -> str:
    return "\n".join(items)


def _split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


class NetworkSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Classification Settings")
        self.resize(640, 520)

        self.tac_edit = QPlainTextEdit(self)
        self.dp_edit = QPlainTextEdit(self)
        self.dns_edit = QPlainTextEdit(self)
        for ed in (self.tac_edit, self.dp_edit, self.dns_edit):
            ed.setPlaceholderText("One IP per line (IPv4/IPv6 supported)")

        v = QVBoxLayout(self)
        v.addWidget(QLabel("TAC IPs"))
        v.addWidget(self.tac_edit, 1)
        v.addWidget(QLabel("DP+ IPs"))
        v.addWidget(self.dp_edit, 1)
        v.addWidget(QLabel("DNS IPs"))
        v.addWidget(self.dns_edit, 1)

        # Buttons row
        btns = QHBoxLayout()
        self.btn_validate = QPushButton("Validate", self)
        self.btn_import = QPushButton("Import…", self)
        self.btn_export = QPushButton("Export…", self)
        self.btn_reset = QPushButton("Reset to Defaults", self)
        btns.addWidget(self.btn_validate)
        btns.addStretch(1)
        btns.addWidget(self.btn_import)
        btns.addWidget(self.btn_export)
        btns.addWidget(self.btn_reset)
        v.addLayout(btns)

        # Save/Cancel row
        sc = QHBoxLayout()
        sc.addStretch(1)
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_save = QPushButton("Save", self)
        sc.addWidget(self.btn_cancel)
        sc.addWidget(self.btn_save)
        v.addLayout(sc)

        # Wire
        self.btn_validate.clicked.connect(self.on_validate)
        self.btn_import.clicked.connect(self.on_import)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.on_save)

        self._load_into_fields()

    def _load_into_fields(self):
        cfg = load_config()
        cl = cfg.get("classification", {})
        self.tac_edit.setPlainText(_join_lines(cl.get("tac_ips", [])))
        self.dp_edit.setPlainText(_join_lines(cl.get("dp_plus_ips", [])))
        self.dns_edit.setPlainText(_join_lines(cl.get("dns_ips", [])))

    def _collect_lists(self):
        tac = _split_lines(self.tac_edit.toPlainText())
        dp = _split_lines(self.dp_edit.toPlainText())
        dns = _split_lines(self.dns_edit.toPlainText())
        return tac, dp, dns

    def on_validate(self):
        tac, dp, dns = self._collect_lists()
        invalid = {
            "TAC": validate_ip_list(tac),
            "DP+": validate_ip_list(dp),
            "DNS": validate_ip_list(dns),
        }
        problems = [f"{k}: {', '.join(v)}" for k, v in invalid.items() if v]
        if problems:
            QMessageBox.warning(self, "Invalid IPs", "\n".join(problems))
        else:
            QMessageBox.information(self, "Validation", "All IPs look valid.")

    def on_reset(self):
        reset_defaults()
        self._load_into_fields()
        QMessageBox.information(self, "Defaults", "Restored default IP lists.")

    def on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Settings", str(Path.cwd()), "JSON Files (*.json);;All Files (*.*)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as ex:
            QMessageBox.critical(self, "Import Error", f"Failed to read JSON: {ex}")
            return
        # Shallow merge + ensure shape
        try:
            save_config(data)
        except Exception as ex:
            QMessageBox.critical(self, "Import Error", f"Failed to save imported config: {ex}")
            return
        self._load_into_fields()
        QMessageBox.information(self, "Import", "Settings imported.")

    def on_export(self):
        # Export current in-memory fields (not disk config)
        tac, dp, dns = self._collect_lists()
        export_obj = {
            "classification": {
                "tac_ips": tac,
                "dp_plus_ips": dp,
                "dns_ips": dns,
            }
        }
        path, _ = QFileDialog.getSaveFileName(self, "Export Settings", str(Path.cwd() / "config.export.json"), "JSON Files (*.json);;All Files (*.*)")
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(export_obj, indent=2), encoding="utf-8")
        except Exception as ex:
            QMessageBox.critical(self, "Export Error", f"Failed to write JSON: {ex}")
            return
        QMessageBox.information(self, "Export", "Settings exported.")

    def on_save(self):
        tac, dp, dns = self._collect_lists()
        problems = {
            "TAC": validate_ip_list(tac),
            "DP+": validate_ip_list(dp),
            "DNS": validate_ip_list(dns),
        }
        bad = [f"{k}: {', '.join(v)}" for k, v in problems.items() if v]
        if bad:
            QMessageBox.warning(self, "Invalid IPs", "\n".join(bad))
            return
        cfg = load_config()
        cfg["classification"]["tac_ips"] = sorted(set(tac))
        cfg["classification"]["dp_plus_ips"] = sorted(set(dp))
        cfg["classification"]["dns_ips"] = sorted(set(dns))
        save_config(cfg)
        self.accept()
