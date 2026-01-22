from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit
from PySide6.QtGui import QAction

from network_settings_dialog import NetworkSettingsDialog
from app_config import load_config


class DemoMain(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ParserX Demo — Settings Menu")
        self.resize(900, 600)
        self.editor = QTextEdit(self)
        self.setCentralWidget(self.editor)
        self._build_menu()
        self._refresh_view()

    def _build_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("File")
        settings_menu = mb.addMenu("Settings")

        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        act_net = QAction("Network Classification…", self)
        act_net.triggered.connect(self.open_network_settings)
        settings_menu.addAction(act_net)

    def open_network_settings(self):
        dlg = NetworkSettingsDialog(self)
        if dlg.exec():
            self._refresh_view()

    def _refresh_view(self):
        cfg = load_config()
        cl = cfg.get("classification", {})
        text = [
            "Classification Settings (read-only preview):",
            "",
            f"TAC IPs: {', '.join(cl.get('tac_ips', []))}",
            f"DP+ IPs: {', '.join(cl.get('dp_plus_ips', []))}",
            f"DNS IPs: {', '.join(cl.get('dns_ips', []))}",
        ]
        self.editor.setText("\n".join(text))


def main():
    app = QApplication(sys.argv)
    w = DemoMain()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
