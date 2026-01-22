"""About Dialog for XTI Viewer."""
from __future__ import annotations

from datetime import datetime
import os
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QTextBrowser
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QDesktopServices, QPixmap, QIcon
import platform

from xti_viewer.resources import resource_path


class AboutDialog(QDialog):
    """Dialog showing application information."""
    
    VERSION = "1.0.1"
    AUTHOR = "Marwane Kaddam"
    EMAIL = "marwane.kaddam@thalesgroup.com"
    ORGANIZATION = "Thales Group"
    DESCRIPTION = "A desktop application for browsing and exploring Gemalto/Thales Universal Tracer .xti files"

    @staticmethod
    def _build_date_text() -> str:
        """Best-effort build date.

        Priority:
        1) `XTI_VIEWER_BUILD_DATE` env var (string)
        2) Timestamp of the running executable when frozen
        3) Timestamp of this source file
        """
        try:
            env = (os.environ.get("XTI_VIEWER_BUILD_DATE") or "").strip()
            if env:
                return env

            if getattr(sys, "frozen", False):
                path = sys.executable
            else:
                path = __file__
            ts = os.path.getmtime(path)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Unknown"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About XTI Viewer")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        try:
            self.setWindowIcon(QIcon(resource_path("Logo.png")))
        except Exception:
            pass
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Logo
        try:
            logo = QPixmap(resource_path("Logo.png"))
            if not logo.isNull():
                logo_label = QLabel()
                logo_label.setAlignment(Qt.AlignCenter)
                logo_label.setPixmap(logo.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                layout.addWidget(logo_label)
        except Exception:
            pass
        
        # Application title
        title_label = QLabel("XTI Viewer")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel(f"Version {self.VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        # Build date
        build_label = QLabel(f"Build {self._build_date_text()}")
        build_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(build_label)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Description
        desc_label = QLabel(self.DESCRIPTION)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        
        layout.addSpacing(10)
        
        # Features section
        features_browser = QTextBrowser()
        features_browser.setMaximumHeight(150)
        features_browser.setOpenExternalLinks(False)
        features_html = """
        <h3>Key Features</h3>
        <ul>
            <li><b>Protocol Analysis:</b> ISO7816, AT commands, Network protocols</li>
            <li><b>TLS Session Analysis:</b> Complete TLS handshake and data flow visualization</li>
            <li><b>Advanced Filtering:</b> Filter by command type, server, time range</li>
            <li><b>TLV Decoder:</b> Automatic BER-TLV parsing and interpretation</li>
            <li><b>Network Classification:</b> TAC, DP+, DNS server detection</li>
            <li><b>Export Functions:</b> CSV, multi-format, channel groups</li>
        </ul>
        """
        features_browser.setHtml(features_html)
        layout.addWidget(features_browser)
        
        layout.addSpacing(10)
        
        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line2)
        
        # Contact information
        contact_layout = QVBoxLayout()
        
        author_label = QLabel(f"<b>Author:</b> {self.AUTHOR}")
        contact_layout.addWidget(author_label)
        
        email_label = QLabel(f'<b>Contact:</b> <a href="mailto:{self.EMAIL}">{self.EMAIL}</a>')
        email_label.setOpenExternalLinks(True)
        contact_layout.addWidget(email_label)
        
        org_label = QLabel(f"<b>Organization:</b> {self.ORGANIZATION}")
        contact_layout.addWidget(org_label)
        
        layout.addLayout(contact_layout)
        
        layout.addSpacing(10)
        
        # System information
        sys_info_label = QLabel(
            f"<small><i>Python {platform.python_version()} | "
            f"{platform.system()} {platform.release()}</i></small>"
        )
        sys_info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(sys_info_label)
        
        layout.addStretch()
        
        # Separator
        line3 = QFrame()
        line3.setFrameShape(QFrame.HLine)
        line3.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line3)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
