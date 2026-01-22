import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QWidget,
    QVBoxLayout,
)


def load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_text(encoding="latin-1", errors="ignore")


# Minimal cipher mapping to replace Unknown_0x.... with readable names
CIPHER_MAP = {
    "0xC02B": "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
    "0x008C": "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA",
    "0x00AE": "TLS_DHE_PSK_WITH_AES_256_CBC_SHA",
}


class TLSReport:
    def __init__(self, md: str) -> None:
        self.md = md
        self.raw_apdus = self._extract_code_block("RAW APDUs")
        self.tls_flow_lines = self._extract_tlS_flow()
        self.summary = self._extract_summary()
        self.handshake_sequence = self._extract_handshake_sequence()
        self.chosen_cipher = self._extract_field(r"Chosen Cipher:\s*(.*)")
        self.cert_count = self._extract_field(r"Certificates:\s*(\d+)")

    def _section(self, title_prefix: str) -> str:
        pattern = rf"^##\s+{re.escape(title_prefix)}.*$"
        m = re.search(pattern, self.md, re.MULTILINE)
        if not m:
            return ""
        start = m.end()
        m2 = re.search(r"^##\s+", self.md[start:], re.MULTILINE)
        end = start + (m2.start() if m2 else len(self.md) - start)
        return self.md[start:end]

    def _extract_code_block(self, title_keyword: str) -> str:
        sec = self._section(title_keyword)
        m = re.search(r"```text\n(.*?)\n```", sec, re.DOTALL)
        return m.group(1) if m else ""

    def _extract_tlS_flow(self) -> list[str]:
        sec = self._section("TLS Flow")
        m = re.search(r"```text\n(.*?)\n```", sec, re.DOTALL)
        if not m:
            return []
        lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
        # Map cipher codes inline on Summary row
        mapped = []
        for ln in lines:
            if "Ciphers:" in ln:
                mapped.append(self._map_ciphers_in_line(ln))
            else:
                mapped.append(ln)
        return mapped

    def _map_ciphers_in_line(self, line: str) -> str:
        def repl(match: re.Match[str]) -> str:
            code = match.group(0)
            name = CIPHER_MAP.get(code, code)
            return name

        # Replace Unknown_0xNNNN tokens with names where we can
        line = re.sub(r"Unknown_(0x[0-9A-Fa-f]{4})", lambda m: CIPHER_MAP.get(m.group(1), m.group(0)), line)
        # Also replace bare codes if present
        for k, v in CIPHER_MAP.items():
            line = line.replace(k, v)
        return line

    def _extract_summary(self) -> dict:
        # Pull SNI, Version, Ciphers from the TLS Flow summary row (last line typically)
        sni = version = ciphers = ""
        for ln in self.tls_flow_lines:
            if ln.startswith("[TLS] Summary") and "SNI:" in ln:
                sni_m = re.search(r"SNI:\s*([^|]+)", ln)
                ver_m = re.search(r"Version:\s*([^|]+)", ln)
                ciph_m = re.search(r"Ciphers:\s*(.*)$", ln)
                if sni_m:
                    sni = sni_m.group(1).strip()
                if ver_m:
                    version = ver_m.group(1).strip()
                if ciph_m:
                    ciphers = self._map_ciphers_in_line(ciph_m.group(1).strip())
        return {"sni": sni, "version": version, "ciphers": ciphers}

    def _extract_handshake_sequence(self) -> list[str]:
        # Use the first Full TLS Analysis section
        m = re.search(r"\*\*Full TLS Handshake Reconstruction\*\*\s*\n-\s*(.*)", self.md)
        if not m:
            return []
        seq = m.group(1)
        parts = [p.strip() for p in seq.split("→")]
        return parts

    def _extract_field(self, pattern: str) -> str:
        m = re.search(pattern, self.md)
        return m.group(1).strip() if m else ""


class MainWindow(QMainWindow):
    def __init__(self, md_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("TLS Report Viewer")
        self.resize(1200, 800)

        self.md_path = md_path
        self.report = TLSReport(load_text(md_path))

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Steps tab
        self.steps_table = QTableWidget(0, 4)
        self.steps_table.setHorizontalHeaderLabels(["Step", "Direction", "Detail", "Time"])
        self.tabs.addTab(self.steps_table, "Steps")

        # Summary tab
        self.summary_view = QTextEdit()
        self.summary_view.setReadOnly(True)
        self.tabs.addTab(self.summary_view, "Summary")

        # Handshake tab
        self.handshake_view = QTextEdit()
        self.handshake_view.setReadOnly(True)
        self.tabs.addTab(self.handshake_view, "Handshake")

        # Ladder tab
        self.ladder_view = QTextEdit()
        self.ladder_view.setReadOnly(True)
        self.tabs.addTab(self.ladder_view, "Ladder")

        # Raw tab
        self.raw_view = QPlainTextEdit()
        self.raw_view.setReadOnly(True)
        self.tabs.addTab(self.raw_view, "Raw")

        # Report tab (render markdown)
        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.tabs.addTab(self.report_view, "Report")

        self._build_menu()
        self._populate()

    def _build_menu(self) -> None:
        open_action = QAction("Open Report…", self)
        open_action.triggered.connect(self._open_report)
        save_action = QAction("Save Markdown As…", self)
        save_action.triggered.connect(self._save_as)
        self.toolbar = self.addToolBar("TLS")
        self.toolbar.addAction(open_action)
        self.toolbar.addAction(save_action)

    def _populate(self) -> None:
        # Steps from TLS Flow block
        self.steps_table.setRowCount(0)
        for ln in self.report.tls_flow_lines:
            # Example: [TLS] TLS | SIM->ME | ts | details
            m = re.match(r"\[TLS\]\s+(.*?)\s*\|\s*(.*?)\s*\|\s*([^|]*)\|\s*(.*)$", ln)
            if not m:
                # Summary row without columns
                if ln.startswith("[TLS] Summary"):
                    row = self.steps_table.rowCount()
                    self.steps_table.insertRow(row)
                    self.steps_table.setItem(row, 0, QTableWidgetItem("Summary"))
                    self.steps_table.setItem(row, 1, QTableWidgetItem(""))
                    self.steps_table.setItem(row, 2, QTableWidgetItem(ln.split("|", 1)[-1].strip()))
                    self.steps_table.setItem(row, 3, QTableWidgetItem(""))
                continue
            step, direction, when, detail = [g.strip() for g in m.groups()]
            row = self.steps_table.rowCount()
            self.steps_table.insertRow(row)
            self.steps_table.setItem(row, 0, QTableWidgetItem(step))
            self.steps_table.setItem(row, 1, QTableWidgetItem(direction))
            self.steps_table.setItem(row, 2, QTableWidgetItem(detail))
            self.steps_table.setItem(row, 3, QTableWidgetItem(when))

        # Summary view
        s = self.report.summary
        chosen = self.report.chosen_cipher
        certs = self.report.cert_count
        summary_text = (
            f"SNI: {s.get('sni','')}\n"
            f"Version: {s.get('version','')}\n"
            f"Ciphers (offered): {s.get('ciphers','')}\n"
            f"Chosen Cipher: {chosen}\n"
            f"Certificates: {certs}\n"
        )
        self.summary_view.setPlainText(summary_text)

        # Handshake view
        if self.report.handshake_sequence:
            self.handshake_view.setPlainText(" → ".join(self.report.handshake_sequence))
        else:
            self.handshake_view.setPlainText("")

        # Ladder as simple textual ladder from flow
        ladder_lines = []
        for ln in self.report.tls_flow_lines:
            m = re.match(r"\[TLS\]\s+(.*?)\s*\|\s*(.*?)\s*\|", ln)
            if m:
                step, direction = m.groups()
                ladder_lines.append(f"{direction:8} : {step}")
        self.ladder_view.setPlainText("\n".join(ladder_lines))

        # Raw APDUs
        self.raw_view.setPlainText(self.report.raw_apdus)

        # Markdown rendered in Report tab
        try:
            self.report_view.setMarkdown(self.report.md)
        except Exception:
            # Some older Qt builds may not support full markdown; degrade nicely
            self.report_view.setPlainText(self.report.md)

    def _open_report(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "Open TAC Session Report", str(self.md_path.parent), "Markdown (*.md);;All Files (*.*)")
        if not fn:
            return
        p = Path(fn)
        if not p.exists():
            QMessageBox.warning(self, "Open Report", f"File not found: {fn}")
            return
        self.md_path = p
        self.report = TLSReport(load_text(p))
        self._populate()

    def _save_as(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "Save Markdown As", str(self.md_path.with_name("tac_session_raw.md")), "Markdown (*.md)")
        if not fn:
            return
        try:
            Path(fn).write_text(self.report.md, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Save Markdown", f"Failed to save: {e}")
        else:
            QMessageBox.information(self, "Save Markdown", f"Saved to: {fn}")


def main() -> int:
    app = QApplication(sys.argv)
    # Default to tac_session_report.md in CWD if present
    cwd = Path.cwd()
    default = cwd / "tac_session_report.md"
    if len(sys.argv) > 1:
        md = Path(sys.argv[1])
    else:
        md = default if default.exists() else cwd
    if md.is_dir():
        # Try common filenames in directory
        candidates = [md / "tac_session_report.md", md / "tac_session_raw.md"]
        md = next((p for p in candidates if p.exists()), candidates[0])
    if not md.exists():
        QMessageBox.critical(None, "TLS Report Viewer", f"Markdown report not found: {md}")
        return 2
    win = MainWindow(md)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
