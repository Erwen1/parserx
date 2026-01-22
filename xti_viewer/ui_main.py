"""
Main user interface for the XTI Viewer application.
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTableView, QTreeView, QTextEdit, QPushButton,
    QLineEdit, QLabel, QMenuBar, QFileDialog, QStatusBar,
    QHeaderView, QMessageBox, QProgressDialog, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView, QCheckBox, QComboBox, QSlider, QGroupBox, QGridLayout, QFrame, QTimeEdit,
    QSizePolicy, QToolButton, QMenu
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QTime, QItemSelectionModel
from PySide6.QtGui import QAction, QKeySequence, QClipboard
from typing import Optional, List

from .xti_parser import XTIParser, TraceItem, TreeNode
from .models import InterpretationTreeModel, TraceItemFilterModel, InspectorTreeModel, HexViewModel, ChannelGroupsModel, KeyEventsModel, FlowTimelineModel
from .utils import SettingsManager, show_error_dialog, show_info_dialog, validate_xti_file
from .validation import ValidationManager, ValidationSeverity


class XTIParserThread(QThread):
    """Background thread for parsing XTI files."""
    
    finished = Signal(object)  # Signal with XTIParser object
    error = Signal(str)      # Signal with error message
    progress = Signal(int)   # Signal with progress percentage
    
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
    
    def run(self):
        """Run the parsing in background thread."""
        try:
            parser = XTIParser()
            parser.parse_file(self.file_path)
            self.finished.emit(parser)  # Emit the parser object instead of just trace items
        except Exception as e:
            self.error.emit(str(e))


class XTIMainWindow(QMainWindow):
    """Main window for the XTI Viewer application."""

    def __init__(self):
        super().__init__()
        self.settings = SettingsManager()
        self.parser_thread: Optional[XTIParserThread] = None
        self.current_file_path: Optional[str] = None
        self.trace_items: List[TraceItem] = []
        self.parser: Optional[XTIParser] = None
        self.validation_manager = ValidationManager()
        # Fast lookup: TraceItem id() -> source row in Interpretation model
        self._traceitem_row_by_id: dict[int, int] = {}

        # Navigation state for interpretation filter
        self.filter_matches: List[int] = []
        self.current_match_index = -1
        self.last_filter_text = ""

        self.setup_ui()
        self.setup_connections()
        self.restore_window_state()
        # Timing aid to distinguish single vs double click effects on timeline
        self._timelineClickTimer = QTimer(self)
        self._timelineClickTimer.setSingleShot(True)
        self._pending_tac_session_data = None
        self._timelineClickTimer.timeout.connect(self._do_tac_single_click_effects)
        # Track last double-click time to suppress stale single-click effects
        self._last_timeline_double_click_ms = 0
        self.debug_tls_clicks = True
        # Collapsible Summary sections state (PKI expanded by default per request)
        self._summary_expand_state = {
            'decoded_clienthello': True,
            'decoded_serverhello': True,
            'cipher_suite_negotiation': True,
            'pki_chain': True,
        }
        # Track current session for re-rendering Summary on toggle
        self._current_session_data = None

        # Remember the last Interpretation selection made while not session/command-family filtered.
        # Used to restore navigation after clearing a filter triggered from Flow Overview.
        self._last_selected_source_row_unfiltered: Optional[int] = None

    def _restore_last_selected_interpretation_row(self) -> None:
        """Re-select and scroll to the last remembered Interpretation row (best-effort)."""
        row = getattr(self, '_last_selected_source_row_unfiltered', None)
        if row is None:
            return
        try:
            src_index = self.trace_model.index(int(row), 0)
            if not src_index.isValid():
                return
            proxy_index = self.filter_model.mapFromSource(src_index)
            if not proxy_index.isValid():
                return

            # Ensure the Interpretation tab is visible
            try:
                self.tab_widget.setCurrentIndex(0)
            except Exception:
                pass

            # Select and center the row
            try:
                sel = self.trace_table.selectionModel()
                if sel is not None:
                    sel.setCurrentIndex(
                        proxy_index,
                        QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
                    )
            except Exception:
                # Fallback: at least set the current index
                try:
                    self.trace_table.setCurrentIndex(proxy_index)
                except Exception:
                    pass

            try:
                self.trace_table.scrollTo(proxy_index, QAbstractItemView.PositionAtCenter)
            except Exception:
                try:
                    self.trace_table.scrollTo(proxy_index)
                except Exception:
                    pass
        except Exception:
            return

    def setup_ui(self):
        """Set up the main window UI with left/right panes and bars."""
        self.setWindowTitle("XTI Viewer")
        self.setMinimumSize(1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)

        left_pane = self.create_left_pane()
        right_pane = self.create_right_pane()
        main_splitter.addWidget(left_pane)
        main_splitter.addWidget(right_pane)
        main_splitter.setSizes([700, 300])
        self.main_splitter = main_splitter

        self.create_menu_bar()
        self.create_status_bar()

    # --- Copy context menus ---
    def _set_clipboard_text(self, text: str) -> None:
        try:
            QApplication.clipboard().setText(text)
        except Exception:
            pass

    def _install_copy_menu_for_text_widget(self, widget) -> None:
        """Add a right-click menu with Copy / Copy All for QTextEdit/QTextBrowser."""
        try:
            widget.setContextMenuPolicy(Qt.CustomContextMenu)

            def on_menu(pos):
                menu = QMenu(widget)
                copy_act = QAction("Copy", menu)
                copy_all_act = QAction("Copy All", menu)

                def do_copy():
                    try:
                        widget.copy()
                    except Exception:
                        pass

                def do_copy_all():
                    try:
                        widget.selectAll()
                        widget.copy()
                        tc = widget.textCursor()
                        tc.clearSelection()
                        widget.setTextCursor(tc)
                    except Exception:
                        try:
                            self._set_clipboard_text(widget.toPlainText())
                        except Exception:
                            pass

                copy_act.triggered.connect(do_copy)
                copy_all_act.triggered.connect(do_copy_all)

                menu.addAction(copy_act)
                menu.addAction(copy_all_act)
                menu.exec(widget.mapToGlobal(pos))

            widget.customContextMenuRequested.connect(on_menu)
        except Exception:
            pass

    def _install_copy_menu_for_treewidget(self, tree) -> None:
        """Add a right-click menu with Copy Selected Rows / Copy All Rows for QTreeWidget."""
        try:
            tree.setContextMenuPolicy(Qt.CustomContextMenu)

            def iter_items(parent_item=None):
                if parent_item is None:
                    for i in range(tree.topLevelItemCount()):
                        yield tree.topLevelItem(i)
                else:
                    for i in range(parent_item.childCount()):
                        yield parent_item.child(i)

            def flatten_all_items():
                stack = list(iter_items(None))
                while stack:
                    item = stack.pop(0)
                    yield item
                    children = list(iter_items(item))
                    if children:
                        stack[0:0] = children

            def visible_columns():
                cols = []
                for c in range(tree.columnCount()):
                    if not tree.isColumnHidden(c):
                        cols.append(c)
                return cols

            def row_text(item) -> str:
                cols = visible_columns()
                return "\t".join((item.text(c) or "").replace("\r", " ").replace("\n", " ") for c in cols)

            def header_text() -> str:
                cols = visible_columns()
                return "\t".join((tree.headerItem().text(c) or "") for c in cols)

            def copy_selected():
                items = tree.selectedItems() or []
                if not items:
                    return
                lines = [row_text(it) for it in items]
                self._set_clipboard_text("\n".join(lines))

            def copy_all():
                lines = [header_text()]
                for it in flatten_all_items():
                    lines.append(row_text(it))
                self._set_clipboard_text("\n".join(lines))

            def on_menu(pos):
                menu = QMenu(tree)
                sel_act = QAction("Copy Selected Rows", menu)
                all_act = QAction("Copy All Rows", menu)
                sel_act.triggered.connect(copy_selected)
                all_act.triggered.connect(copy_all)
                menu.addAction(sel_act)
                menu.addAction(all_act)
                menu.exec(tree.viewport().mapToGlobal(pos))

            tree.customContextMenuRequested.connect(on_menu)
        except Exception:
            pass

    def _install_copy_menu_for_treeview(self, view) -> None:
        """Add a right-click menu with Copy Selected Rows / Copy All Visible Rows for QTreeView."""
        try:
            view.setContextMenuPolicy(Qt.CustomContextMenu)

            def visible_columns(model):
                cols = []
                for c in range(model.columnCount()):
                    if not view.isColumnHidden(c):
                        cols.append(c)
                return cols

            def header_text(model) -> str:
                cols = visible_columns(model)
                parts = []
                for c in cols:
                    try:
                        parts.append(str(model.headerData(c, Qt.Horizontal, Qt.DisplayRole) or ""))
                    except Exception:
                        parts.append("")
                return "\t".join(parts)

            def row_text(model, row_index0) -> str:
                cols = visible_columns(model)
                parent = row_index0.parent()
                row = row_index0.row()
                parts = []
                for c in cols:
                    try:
                        idx = model.index(row, c, parent)
                        val = idx.data(Qt.DisplayRole)
                        parts.append(str(val or "").replace("\r", " ").replace("\n", " "))
                    except Exception:
                        parts.append("")
                return "\t".join(parts)

            def iter_all_rows(model, parent_index=None):
                if parent_index is None:
                    parent_index = view.rootIndex()
                r = 0
                while True:
                    idx0 = model.index(r, 0, parent_index)
                    if not idx0.isValid():
                        break
                    yield idx0
                    # Recurse into children
                    if model.hasChildren(idx0):
                        yield from iter_all_rows(model, idx0)
                    r += 1

            def copy_selected():
                sel = view.selectionModel()
                if not sel:
                    return
                rows0 = sel.selectedRows(0) or []
                if not rows0:
                    return
                model = view.model()
                lines = [row_text(model, idx0) for idx0 in rows0]
                self._set_clipboard_text("\n".join(lines))

            def copy_all():
                model = view.model()
                lines = [header_text(model)]
                for idx0 in iter_all_rows(model, QModelIndex()):
                    lines.append(row_text(model, idx0))
                self._set_clipboard_text("\n".join(lines))

            def on_menu(pos):
                menu = QMenu(view)
                sel_act = QAction("Copy Selected Rows", menu)
                all_act = QAction("Copy All Visible Rows", menu)
                sel_act.triggered.connect(copy_selected)
                all_act.triggered.connect(copy_all)
                menu.addAction(sel_act)
                menu.addAction(all_act)
                menu.exec(view.viewport().mapToGlobal(pos))

            from PySide6.QtCore import QModelIndex
            view.customContextMenuRequested.connect(on_menu)
        except Exception:
            pass
        
    def restore_window_state(self):
        """Restore window geometry/state if settings manager is available."""
        try:
            if hasattr(self, 'settings') and self.settings:
                geom = self.settings.get_window_geometry()
                if geom:
                    self.restoreGeometry(geom)
                state = self.settings.get_window_state()
                if state:
                    self.restoreState(state)
                main_splitter_state = self.settings.get_splitter_state("main")
                if main_splitter_state:
                    self.main_splitter.restoreState(main_splitter_state)
                left_splitter_state = self.settings.get_splitter_state("left")
                if left_splitter_state:
                    self.left_splitter.restoreState(left_splitter_state)
        except Exception:
            # Safe no-op if settings are not yet ready
            pass

    def save_window_state(self):
        """Persist window geometry/state if settings manager is available."""
        try:
            if hasattr(self, 'settings') and self.settings:
                self.settings.set_window_geometry(self.saveGeometry())
                self.settings.set_window_state(self.saveState())
                if hasattr(self, 'main_splitter'):
                    self.settings.set_splitter_state("main", self.main_splitter.saveState())
                if hasattr(self, 'left_splitter'):
                    self.settings.set_splitter_state("left", self.left_splitter.saveState())
        except Exception:
            pass

    def _on_summary_anchor_clicked(self, url):
        """Handle clicks on anchors in Summary to select corresponding Steps items."""
        try:
            href = str(getattr(url, 'toString', lambda: str(url))())
            # Handle collapsible toggles
            if href.startswith('toggle:'):
                key = href.split(':', 1)[1]
                if key in getattr(self, '_summary_expand_state', {}):
                    self._summary_expand_state[key] = not self._summary_expand_state[key]
                    # Re-render Summary using last session data if available
                    try:
                        if getattr(self, '_current_session_data', None):
                            self.show_tls_flow_for_session(self._current_session_data)
                    except Exception:
                        pass
                return
            # Directly select a row by index (used by Ladder step anchors)
            if href.startswith('stepidx:') and hasattr(self, 'tls_tree') and self.tls_tree is not None:
                try:
                    idx = int(href.split(':',1)[1])
                    if 0 <= idx < self.tls_tree.topLevelItemCount():
                        it = self.tls_tree.topLevelItem(idx)
                        if it:
                            self.tls_tree.setCurrentItem(it)
                            if hasattr(self, 'tls_subtabs'):
                                self.tls_subtabs.setCurrentIndex(0)  # Steps
                            self._on_tls_step_selected()
                            if hasattr(self, 'tls_subtabs'):
                                self.tls_subtabs.setCurrentIndex(3)  # Ladder
                except Exception:
                    pass
                return
            if href.startswith('step:') and hasattr(self, 'tls_tree') and self.tls_tree is not None:
                token = href.split(':', 1)[1]
                token_l = token.lower()
                count = self.tls_tree.topLevelItemCount()
                for i in range(count):
                    it = self.tls_tree.topLevelItem(i)
                    if not it:
                        continue
                    c0 = (it.text(0) or '').lower()
                    c2 = (it.text(2) or '').lower()
                    if token_l in c0 or token_l in c2:
                        self.tls_tree.setCurrentItem(it)
                        # Bring Steps tab to front and emphasize in Ladder
                        try:
                            if hasattr(self, 'tls_subtabs'):
                                self.tls_subtabs.setCurrentIndex(0)  # Steps tab
                            self._on_tls_step_selected()
                            if hasattr(self, 'tls_subtabs'):
                                self.tls_subtabs.setCurrentIndex(3)  # Ladder tab
                        except Exception:
                            pass
                        break
        except Exception:
            pass

    def _on_tls_step_selected(self):
        """Update inline preview with selected Steps item details and quick summary."""
        try:
            if not hasattr(self, 'tls_tree') or not hasattr(self, 'tls_step_preview'):
                return
            items = self.tls_tree.selectedItems()
            if not items:
                self.tls_step_preview.setText("")
                # Also clear ladder emphasis
                try:
                    self._render_ladder_from_steps(highlight_index=None, group_appdata=True)
                except Exception:
                    pass
                return
            it = items[0]
            highlight_idx = self.tls_tree.indexOfTopLevelItem(it)
            step = it.text(0) or ''
            direction = it.text(1) or ''
            detail = it.text(2) or ''
            ts = it.text(3) or ''
            # Compose compact preview card
            html = (
                f"<b>{step}</b> <span style='color:#666;'>({direction})</span><br/>"
                f"{detail}<br/>"
                f"<span style='color:#999;'>Time: {ts}</span>"
            )
            self.tls_step_preview.setText(html)
            # Update Raw contextual view if enabled
            self._update_raw_context_view()
            # Re-render ladder with current selection emphasized
            try:
                self._render_ladder_from_steps(highlight_index=highlight_idx, group_appdata=True)
            except Exception:
                pass
        except Exception:
            pass

    def _copy_security_to_clipboard(self):
        """Copy the Security tab content to clipboard (plain text)."""
        try:
            txt = ''
            if hasattr(self, 'tls_security_view'):
                try:
                    txt = self.tls_security_view.toPlainText()
                except Exception:
                    txt = self.tls_security_view.text() if hasattr(self.tls_security_view, 'text') else ''
            if txt:
                QApplication.clipboard().setText(txt)
                self.status_bar.showMessage("Security info copied", 2000)
        except Exception:
            pass

    def _export_security_markdown(self):
        """Export the Security tab content as Markdown next to the XTI file."""
        try:
            txt = ''
            if hasattr(self, 'tls_security_view'):
                try:
                    txt = self.tls_security_view.toPlainText()
                except Exception:
                    txt = self.tls_security_view.text() if hasattr(self.tls_security_view, 'text') else ''
            if not txt:
                return
            base = Path(self.current_file_path).parent if getattr(self, 'current_file_path', None) else Path.cwd()
            (base / "tls_security.md").write_text(txt, encoding='utf-8')
            self.status_bar.showMessage("Exported Security → tls_security.md", 3000)
        except Exception:
            pass

    def _update_raw_context_view(self):
        try:
            if not hasattr(self, 'raw_context_toggle') or not self.raw_context_toggle.isChecked():
                return
            # Build a filtered raw view around selected Steps item
            n = int(self.raw_context_window.value()) if hasattr(self, 'raw_context_window') else 20
            # Try to fetch raw APDUs from last report data rendered
            try:
                from tls_flow_from_report import load_tls_report
                base_dir = Path(self.current_file_path).parent if getattr(self, 'current_file_path', None) else Path.cwd()
                report_path = None
                for name in ("tac_session_report.md", "tac_tls_flow.md"):
                    p = base_dir / name
                    if p.exists():
                        report_path = p; break
                apdus = []
                if report_path:
                    data = load_tls_report(str(report_path))
                    apdus = getattr(data, 'raw_apdus', None) or []
                # Use selection index as anchor
                anchor_idx = 0
                if hasattr(self, 'tls_tree'):
                    idx = self.tls_tree.indexOfTopLevelItem(self.tls_tree.selectedItems()[0]) if self.tls_tree.selectedItems() else 0
                    anchor_idx = max(0, idx)
                start = max(0, anchor_idx - n)
                end = min(len(apdus), anchor_idx + n)
                snippet = apdus[start:end]
                if snippet:
                    # Note: Raw context view is now integrated in Security tab
                    # This feature may need redesign with the new tab structure
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def _copy_overview_to_clipboard(self):
        """Copy the Overview tab content to clipboard (plain text)."""
        try:
            text = ""
            if hasattr(self, 'tls_overview_view') and self.tls_overview_view is not None:
                try:
                    text = self.tls_overview_view.toPlainText()
                except Exception:
                    text = self.tls_overview_view.text() if hasattr(self.tls_overview_view, 'text') else ""
            if text:
                QApplication.clipboard().setText(text)
                self.status_bar.showMessage("Overview copied to clipboard", 2000)
        except Exception:
            pass

    def _export_overview_markdown(self):
        """Export the Overview tab content as Markdown next to the XTI file."""
        try:
            text = ""
            if hasattr(self, 'tls_overview_view') and self.tls_overview_view is not None:
                try:
                    text = self.tls_overview_view.toPlainText()
                except Exception:
                    text = self.tls_overview_view.text() if hasattr(self.tls_overview_view, 'text') else ""
            if not text:
                show_info_dialog(self, "Export Overview", "No overview available to export.")
                return
            base = Path(self.current_file_path).parent if getattr(self, 'current_file_path', None) else Path.cwd()
            out_path = base / "tls_overview.md"
            out_path.write_text(text, encoding='utf-8')
            self.status_bar.showMessage(f"Exported Overview → {out_path}", 3000)
        except Exception as e:
            show_error_dialog(self, "Export Summary", f"Failed to export summary: {e}")

    def _populate_tls_from_report(self, session_data: dict) -> bool:
        """Populate TLS Flow tabs using the normalized markdown report if available.
        Returns True if populated, else False.
        """
        try:
            from pathlib import Path
            import os
            import re
            try:
                from tls_flow_from_report import load_tls_report
            except Exception:
                return False
            base_dir = Path(self.current_file_path).parent if getattr(self, 'current_file_path', None) else Path.cwd()
            report_path = None
            for name in ("tac_session_report.md", "tac_tls_flow.md"):
                p = base_dir / name
                if p.exists():
                    report_path = p
                    break
            if not report_path:
                return False

            # Guardrail: do not apply a report generated for a different XTI file.
            # These markdown reports may exist in the folder as samples (e.g. HL7812) and
            # would otherwise override live parsing for other files (e.g. ME310).
            try:
                cur = os.path.basename(self.current_file_path) if getattr(self, 'current_file_path', None) else ""
                md_head = report_path.read_text(encoding='utf-8', errors='ignore')
                m = re.search(r"^\s*-\s*Source\s+XTI:\s*`([^`]+)`\s*$", md_head, re.MULTILINE)
                if cur and m:
                    src = (m.group(1) or '').strip()
                    if src and src != cur:
                        return False
            except Exception:
                # If we can't validate, be conservative and fall back to live parsing.
                return False

            data = load_tls_report(str(report_path))
        except Exception:
            return False

        # Messages tree with phase grouping
        try:
            if hasattr(self, 'tls_tree') and self.tls_tree is not None:
                self.tls_tree.clear()
                from PySide6.QtWidgets import QTreeWidgetItem
                from PySide6.QtGui import QFont
                
                # Create phase groups
                handshake_phase = QTreeWidgetItem(self.tls_tree, ["🔐 Handshake Phase", "", "", ""])
                data_phase = QTreeWidgetItem(self.tls_tree, ["📦 Data Transfer Phase", "", "", ""])
                closure_phase = QTreeWidgetItem(self.tls_tree, ["🔒 Closure Phase", "", "", ""])
                
                # Make phase headers bold
                for phase in (handshake_phase, data_phase, closure_phase):
                    font = phase.font(0)
                    font.setBold(True)
                    font.setPointSize(font.pointSize() + 1)
                    phase.setFont(0, font)
                
                # Track counts for phase summaries
                handshake_count = data_count = closure_count = 0
                
                last_label_by_dir = {}
                # Track handshake sequence for inferring bundled messages
                handshake_seq_idx = 0
                handshake_sequence = []
                if data.handshake and data.handshake.sequence:
                    handshake_sequence = [s for s in data.handshake.sequence 
                                        if s not in ('OPEN CHANNEL', 'CLOSE CHANNEL', 'ApplicationData', 
                                                    'Alert (close_notify)', 'Alert')]
                
                for ev in (data.flow_events or [])[:1000]:  # safety cap
                    # Determine which phase this message belongs to
                    label = getattr(ev, 'label', '') or ''
                    label_lower = label.lower()
                    
                    if any(x in label_lower for x in ('hello', 'certificate', 'keyexchange', 'helldone', 
                                                       'cipher', 'finished', 'handshake')):
                        parent = handshake_phase
                        handshake_count += 1
                    elif 'alert' in label_lower:
                        # Alerts are not treated as part of the closure phase in this UI.
                        parent = data_phase
                        data_count += 1
                    elif 'close' in label_lower:
                        parent = closure_phase
                        closure_count += 1
                    else:
                        parent = data_phase
                        data_count += 1
                    
                    item = QTreeWidgetItem(parent)
                    # Parse direction and add visual arrows
                    direction = getattr(ev, 'direction', '') or ''
                    if 'SIM' in direction and 'ME' in direction:
                        if direction.startswith('SIM'):
                            direction_display = 'SIM → ME'
                        else:
                            direction_display = 'ME → SIM'
                    else:
                        direction_display = direction
                    item.setText(1, direction_display)
                    
                    label = getattr(ev, 'label', '') or ''
                    details = getattr(ev, 'details', '') or ''
                    
                    # Normalize generic handshake labels to explicit types when possible
                    try:
                        lbl_low = label.lower()
                        det_low = (details or '').lower()
                        # Extract inner type if label like 'TLS Handshake (ClientHello)'
                        if 'handshake' in lbl_low and '(' in label and ')' in label:
                            inner = label.split('(', 1)[1].split(')', 1)[0].strip()
                            if inner and inner.lower() != 'other':
                                label = inner
                                handshake_seq_idx += 1
                        # Map '(other)' using sequence-based inference
                        elif 'handshake' in lbl_low and ('(other' in lbl_low or '(other' in label):
                            # Try to infer from handshake sequence based on direction
                            if handshake_seq_idx < len(handshake_sequence):
                                next_msgs = []
                                # Peek ahead to see if multiple messages are bundled
                                temp_idx = handshake_seq_idx
                                while temp_idx < len(handshake_sequence) and len(next_msgs) < 3:
                                    msg = handshake_sequence[temp_idx]
                                    # Stop at ChangeCipherSpec as it's a separate message
                                    if 'Change' in msg or 'Encrypted' in msg:
                                        break
                                    next_msgs.append(msg)
                                    temp_idx += 1
                                
                                # Determine what to show based on direction and position
                                if direction_display == 'ME → SIM' and handshake_seq_idx == 1:
                                    # First server message = ServerHello + Certificate
                                    label = 'ServerHello + Certificate'
                                    handshake_seq_idx += 2
                                elif direction_display == 'ME → SIM' and 'ServerKeyExchange' in next_msgs:
                                    # ServerKeyExchange + ServerHelloDone
                                    label = 'ServerKeyExchange + ServerHelloDone'
                                    handshake_seq_idx += 2
                                elif direction_display == 'SIM → ME' and 'ClientKeyExchange' in next_msgs:
                                    label = 'ClientKeyExchange'
                                    handshake_seq_idx += 1
                                elif next_msgs:
                                    label = next_msgs[0]
                                    handshake_seq_idx += 1
                                else:
                                    label = 'TLS Handshake'
                            else:
                                label = 'TLS Handshake'
                    except Exception:
                        pass
                    
                    # Show actual message name in Step column, not generic badge
                    item.setText(0, label if label else 'TLS')
                    # Color-code message names for visual distinction
                    try:
                        from PySide6.QtGui import QBrush, QColor
                        color = QColor('#888888')  # default gray
                        
                        # Handshake messages: blue (including bundled messages)
                        if (label in ('ClientHello', 'ServerHello', 'Certificate', 'ServerKeyExchange', 
                                     'ClientKeyExchange', 'ServerHelloDone', 'CertificateRequest') or
                            '+' in label and any(x in label for x in ('ServerHello', 'Certificate', 'ServerKeyExchange'))):
                            color = QColor('#2a7ed3')
                        # Cipher spec and finished: orange
                        elif label in ('ChangeCipherSpec', 'Encrypted Finished', 'Finished'):
                            color = QColor('#e08a00')
                        # Alerts: red
                        elif label.startswith('Alert') or 'alert' in label.lower():
                            color = QColor('#d32f2f')
                        # Application data: dark gray
                        elif label == 'ApplicationData' or 'application' in label.lower():
                            color = QColor('#666666')
                        # Session control: green
                        elif label in ('OPEN CHANNEL', 'CLOSE CHANNEL'):
                            color = QColor('#2e7d32')
                        
                        item.setForeground(0, QBrush(color))
                        
                        # Make key handshake messages bold (including bundled)
                        if (label in ('ClientHello', 'ServerHello', 'Certificate') or
                            '+' in label and any(x in label for x in ('ServerHello', 'Certificate'))):
                            font = item.font(0)
                            font.setBold(True)
                            item.setFont(0, font)
                    except Exception:
                        pass
                    # Normalize Finished immediately after CCS to Encrypted Finished
                    try:
                        d = getattr(ev, 'direction', '') or ''
                        prev = last_label_by_dir.get(d)
                        if label == 'Finished' and prev == 'ChangeCipherSpec':
                            label = 'Encrypted Finished'
                        last_label_by_dir[d] = label or prev
                    except Exception:
                        pass
                    # Normalize vendor-specific alert codes to human-friendly labels
                    try:
                        if label.startswith('Alert') or 'alert_' in (details or ''):
                            # Map known vendor codes
                            # level_151 → warning_vendor, alert_82 → close_notify
                            if 'level_151' in details:
                                details = details.replace('level_151', 'warning_vendor')
                            if 'alert_82' in details:
                                details = details.replace('alert_82', 'close_notify')
                            # If label is generic 'Alert', keep it consistent
                            label = 'Alert'
                    except Exception:
                        pass
                    # Build detail string with truncation for readability
                    detail_parts = []
                    if details:
                        # Extract key info from details
                        detail_parts.append(details)
                    
                    detail = ' • '.join(detail_parts) if detail_parts else ''
                    
                    # Truncate if too long, but keep full text in tooltip
                    MAX_DETAIL_LEN = 80
                    if len(detail) > MAX_DETAIL_LEN:
                        item.setToolTip(2, detail)  # Full text in tooltip
                        detail = detail[:MAX_DETAIL_LEN] + '...'
                    
                    item.setText(2, detail)
                    item.setText(3, getattr(ev, 'timestamp', '') or '')
                
                # Update phase summaries with counts
                handshake_phase.setText(0, f"🔐 Handshake Phase ({handshake_count} messages)")
                data_phase.setText(0, f"📦 Data Transfer Phase ({data_count} messages)")
                closure_phase.setText(0, f"🔒 Closure Phase ({closure_count} messages)")
                
                # Expand handshake by default, collapse others if too many messages
                handshake_phase.setExpanded(True)
                data_phase.setExpanded(data_count <= 10)
                closure_phase.setExpanded(True)
                
                # Remove empty phases
                if handshake_count == 0:
                    self.tls_tree.invisibleRootItem().removeChild(handshake_phase)
                if data_count == 0:
                    self.tls_tree.invisibleRootItem().removeChild(data_phase)
                if closure_count == 0:
                    self.tls_tree.invisibleRootItem().removeChild(closure_phase)
        except Exception:
            pass

        # Top summary label and Summary tab
        try:
            server = session_data.get('server') or session_data.get('label') or 'Unknown'
            port = session_data.get('port') or ''
            protocol = session_data.get('protocol') or ''
            ips = session_data.get('ips') or []
            opened = session_data.get('opened', '')
            closed = session_data.get('closed', '')
            duration = session_data.get('duration', '')
            ip_text = ", ".join(ips) if isinstance(ips, list) else str(ips)
            if hasattr(self, 'tls_summary_label'):
                self.tls_summary_label.setText(
                    f"Session: {server}  |  Protocol: {protocol}  |  Port: {port}  |  IP: {ip_text}  |  {opened} → {closed}  ({duration})"
                )
            summ = getattr(data, 'summary', None)
            
            # Populate Overview tab (merged Summary + Handshake - streamlined, no duplication)
            if hasattr(self, 'tls_overview_view') and summ:
                html_parts = []
                html_parts.append('<style>')
                html_parts.append('body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin:0; padding:6px; }')
                html_parts.append('.card { background:white; border:1px solid #e0e0e0; border-radius:4px; padding:6px; margin:4px 0; box-shadow:0 1px 2px rgba(0,0,0,0.06); }')
                html_parts.append('.card-header { font-size:12px; font-weight:700; color:#1a1a1a; margin-bottom:4px; padding-bottom:2px; border-bottom:1px solid #e8f4f8; }')
                html_parts.append('.stat-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); gap:4px; margin:3px 0; }')
                html_parts.append('.stat-item { background:#f8fafb; padding:4px 6px; border-radius:3px; border-left:2px solid #2196F3; }')
                html_parts.append('.stat-label { font-size:9px; color:#666; text-transform:uppercase; font-weight:600; margin-bottom:1px; }')
                html_parts.append('.stat-value { font-size:12px; font-weight:700; color:#1a1a1a; }')
                html_parts.append('.badge { display:inline-block; padding:1px 5px; border-radius:2px; font-size:9px; font-weight:600; margin:1px; }')
                html_parts.append('.badge-success { background:#e8f5e9; color:#2e7d32; border:1px solid #a5d6a7; }')
                html_parts.append('.badge-info { background:#e3f2fd; color:#1976d2; border:1px solid #90caf9; }')
                html_parts.append('.badge-warning { background:#fff3e0; color:#f57c00; border:1px solid #ffb74d; }')
                html_parts.append('ul { margin:3px 0; padding-left:18px; }')
                html_parts.append('li { margin:1px 0; line-height:1.3; font-size:11px; }')
                html_parts.append('</style>')
                
                # Calculate statistics
                try:
                    from dateutil import parser as date_parser
                    import re
                    
                    # Parse opened/closed times for duration
                    open_time = closed_time = None
                    handshake_duration = data_volume = handshake_msg_count = 0
                    alert_count = 0
                    
                    if opened and closed:
                        try:
                            # Extract time portion if it's a full datetime string
                            open_str = opened.split()[-1] if ' ' in opened else opened
                            close_str = closed.split()[-1] if ' ' in closed else closed
                            open_time = date_parser.parse(open_str, fuzzy=True)
                            closed_time = date_parser.parse(close_str, fuzzy=True)
                        except:
                            pass
                    
                    # Count handshake messages and app data
                    for ev in (data.flow_events or []):
                        lbl = getattr(ev, 'label', '') or ''
                        if 'ApplicationData' in lbl:
                            data_volume += 1
                        elif 'Alert' in lbl:
                            alert_count += 1
                        elif any(x in lbl for x in ('Hello', 'Certificate', 'KeyExchange', 'Cipher', 'Finished')):
                            handshake_msg_count += 1
                    
                except:
                    pass
                
                # Session Overview Card
                html_parts.append('<div class="card">')
                html_parts.append('<div class="card-header">📋 Session Overview</div>')
                html_parts.append(f'<div style="font-size:13px; font-weight:700; color:#1565c0; margin-bottom:3px;">{server}</div>')
                
                html_parts.append('<div class="stat-grid">')
                html_parts.append('<div class="stat-item">')
                html_parts.append('<div class="stat-label">Protocol</div>')
                html_parts.append(f'<div class="stat-value">{protocol or "TCP"}</div>')
                html_parts.append('</div>')
                
                html_parts.append('<div class="stat-item">')
                html_parts.append('<div class="stat-label">Port</div>')
                html_parts.append(f'<div class="stat-value">{port or "N/A"}</div>')
                html_parts.append('</div>')
                
                html_parts.append('<div class="stat-item">')
                html_parts.append('<div class="stat-label">Duration</div>')
                html_parts.append(f'<div class="stat-value">{duration or "N/A"}</div>')
                html_parts.append('</div>')
                
                html_parts.append('<div class="stat-item">')
                html_parts.append('<div class="stat-label">Total Messages</div>')
                html_parts.append(f'<div class="stat-value">{len(data.flow_events or [])}</div>')
                html_parts.append('</div>')

                html_parts.append('</div>')
                
                if ip_text:
                    html_parts.append(f'<div style="margin-top:3px; font-size:10px; color:#666;"><b>IP:</b> {ip_text}</div>')
                if summ.sni:
                    html_parts.append(f'<div style="font-size:10px; color:#666; margin-top:2px;"><b>SNI:</b> {summ.sni}</div>')
                html_parts.append('</div>')
                
                # Security Configuration Card
                html_parts.append('<div class="card">')
                html_parts.append('<div class="card-header">🔐 Security Configuration</div>')
                
                html_parts.append('<div style="margin:3px 0;">')
                if summ.version:
                    version_color = '#2e7d32' if 'TLS 1.2' in summ.version or 'TLS 1.3' in summ.version else '#f57c00'
                    html_parts.append(f'<div style="margin:3px 0;"><b>Version:</b> <span style="color:{version_color}; font-weight:700;">{summ.version}</span></div>')
                
                if summ.chosen_cipher:
                    html_parts.append(f'<div style="margin:3px 0;"><b>Chosen Cipher Suite:</b><br/><code style="background:#f5f5f5; padding:3px 6px; border-radius:3px; font-size:11px;">{summ.chosen_cipher}</code></div>')
                    
                    # Cipher analysis badges
                    cipher = summ.chosen_cipher
                    badges = []
                    if 'ECDHE' in cipher or 'DHE' in cipher:
                        badges.append('<span class="badge badge-success">✓ Perfect Forward Secrecy</span>')
                    if 'GCM' in cipher or 'CHACHA20' in cipher:
                        badges.append('<span class="badge badge-success">✓ AEAD Mode</span>')
                    if 'AES_256' in cipher:
                        badges.append('<span class="badge badge-info">256-bit Encryption</span>')
                    elif 'AES_128' in cipher:
                        badges.append('<span class="badge badge-info">128-bit Encryption</span>')
                    if badges:
                        html_parts.append('<div style="margin:4px 0 2px 0;">' + ''.join(badges) + '</div>')
                
                if summ.certificates is not None and summ.certificates > 0:
                    html_parts.append(f'<div style="margin:3px 0;"><b>Certificate Chain:</b> {summ.certificates} certificate{"s" if summ.certificates != 1 else ""}</div>')
                html_parts.append('<div style="margin-top:4px; font-size:10px; color:#666;"><b>Scope:</b> TLS record/handshake decoding only (no decryption of ApplicationData)</div>')
                html_parts.append('</div>')
                html_parts.append('</div>')
                
                # Message Statistics Card
                html_parts.append('<div class="card">')
                html_parts.append('<div class="card-header">📊 Message Statistics</div>')
                html_parts.append('<div class="stat-grid">')
                
                html_parts.append('<div class="stat-item" style="border-left-color:#2196F3;">')
                html_parts.append('<div class="stat-label">Handshake</div>')
                html_parts.append(f'<div class="stat-value">{handshake_msg_count}</div>')
                html_parts.append('</div>')
                
                html_parts.append('<div class="stat-item" style="border-left-color:#4CAF50;">')
                html_parts.append('<div class="stat-label">Application Data</div>')
                html_parts.append(f'<div class="stat-value">{data_volume}</div>')
                html_parts.append('</div>')
                
                if alert_count > 0:
                    html_parts.append('<div class="stat-item" style="border-left-color:#f44336;">')
                    html_parts.append('<div class="stat-label">Alerts</div>')
                    html_parts.append(f'<div class="stat-value">{alert_count}</div>')
                    html_parts.append('</div>')
                
                html_parts.append('</div>')
                html_parts.append('</div>')
                
                # Visual handshake flow (single representation, no duplication)
                try:
                    if data.handshake and data.handshake.sequence:
                        seq_tokens = [t for t in data.handshake.sequence if t not in ('OPEN CHANNEL', 'CLOSE CHANNEL')]
                        
                        html_parts.append('<div class="card">')
                        html_parts.append('<div class="card-header">🔄 Handshake Flow</div>')
                        
                        color_map = {
                            'ClientHello': '#1976d2', 'ServerHello': '#1976d2', 'Certificate': '#1976d2',
                            'ServerKeyExchange': '#1976d2', 'ClientKeyExchange': '#1976d2', 'Finished': '#1976d2',
                            'ServerHelloDone': '#1976d2', 'Certificate Request': '#1976d2',
                            'ChangeCipherSpec': '#f57c00', 'Encrypted Finished': '#388e3c',
                            'ApplicationData': '#616161', 'Alert': '#d32f2f'
                        }
                        
                        def pill(label):
                            col = '#757575'
                            bg_col = '#f5f5f5'
                            for k, v in color_map.items():
                                if k in label:
                                    col = v
                                    # Lighter background matching the border color
                                    if v == '#1976d2':
                                        bg_col = '#e3f2fd'
                                    elif v == '#f57c00':
                                        bg_col = '#fff3e0'
                                    elif v == '#388e3c':
                                        bg_col = '#e8f5e9'
                                    elif v == '#d32f2f':
                                        bg_col = '#ffebee'
                                    break
                            
                            safe = label
                            for tok in ("ClientHello","ServerHello","Certificate","ServerKeyExchange","ServerHelloDone",
                                       "ClientKeyExchange","ChangeCipherSpec","Encrypted Finished","ApplicationData","Alert"):
                                if tok in safe:
                                    safe = safe.replace(tok, f"<a href=\"step:{tok}\" style=\"color:{col}; text-decoration:none; font-weight:700;\">{tok}</a>")
                            return f"<span style='display:inline-block; margin:3px; padding:8px 14px; border:2px solid {col}; border-radius:16px; color:{col}; background:{bg_col}; font-size:12px; font-weight:600; box-shadow:0 1px 2px rgba(0,0,0,0.1);'>{safe}</span>"
                        
                        html_parts.append('<div style="display:flex; flex-wrap:wrap; align-items:center; gap:2px; padding:8px;">')
                        for i, t in enumerate(seq_tokens):
                            html_parts.append(pill(t))
                            if i < len(seq_tokens) - 1:
                                html_parts.append('<span style="color:#bdbdbd; margin:0 4px; font-size:18px; font-weight:700;">→</span>')
                        html_parts.append('</div>')
                        html_parts.append('</div>')
                except:
                    pass
                # Decoded sections: ClientHello, ServerHello, PKI, Cipher Suite Negotiation
                try:
                    decoded = getattr(data, 'decoded', None)
                    have_decoded_data = decoded is not None
                    if decoded:
                        ch = getattr(decoded, 'client_hello', None)
                        sh = getattr(decoded, 'server_hello', None)
                        pki = getattr(decoded, 'pki_chain', None)
                        csn = getattr(decoded, 'cipher_suite_negotiation', None)
                        if ch:
                            try:
                                expanded = getattr(self, '_summary_expand_state', {}).get('decoded_clienthello', True)
                                arrow = '▼' if expanded else '▶'
                                html_parts.append('<div class="card">')
                                html_parts.append(f"<div style='cursor:pointer;'><a href=\"toggle:decoded_clienthello\" style='text-decoration:none; color:#1a1a1a;'><span style='color:#1976d2; font-size:14px;'>{arrow}</span> <span class='card-header' style='display:inline; border:none; padding:0;'>📤 ClientHello (Decoded)</span></a></div>")
                            except Exception:
                                html_parts.append('<div class="card"><div class="card-header">📤 ClientHello (Decoded)</div>')
                            
                            if getattr(self, '_summary_expand_state', {}).get('decoded_clienthello', True):
                                html_parts.append('<div style="margin-top:8px;">')
                                if getattr(ch, 'version', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Version:</b> {ch.version}</div>')
                                if getattr(ch, 'cipher_suites', None):
                                    ciphers = ch.cipher_suites[:8] if len(ch.cipher_suites) > 8 else ch.cipher_suites
                                    more = f' (+{len(ch.cipher_suites) - 8} more)' if len(ch.cipher_suites) > 8 else ''
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Cipher Suites:</b> {", ".join(ciphers)}{more}</div>')
                                if getattr(ch, 'sni', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>SNI:</b> {ch.sni}</div>')
                                if getattr(ch, 'extensions', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Extensions:</b> {", ".join(ch.extensions)}</div>')
                                if getattr(ch, 'supported_groups', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Supported Groups:</b> {ch.supported_groups}</div>')
                                if getattr(ch, 'signature_algorithms', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Signature Algorithms:</b> {ch.signature_algorithms}</div>')
                                if getattr(ch, 'alpn', None) is not None:
                                    html_parts.append(f'<div style="margin:6px 0;"><b>ALPN:</b> {ch.alpn}</div>')
                                html_parts.append('</div>')
                            html_parts.append('</div>')
                        if sh:
                            try:
                                expanded = getattr(self, '_summary_expand_state', {}).get('decoded_serverhello', True)
                                arrow = '▼' if expanded else '▶'
                                html_parts.append('<div class="card">')
                                html_parts.append(f"<div style='cursor:pointer;'><a href=\"toggle:decoded_serverhello\" style='text-decoration:none; color:#1a1a1a;'><span style='color:#1976d2; font-size:14px;'>{arrow}</span> <span class='card-header' style='display:inline; border:none; padding:0;'>📥 ServerHello (Decoded)</span></a></div>")
                            except Exception:
                                html_parts.append('<div class="card"><div class="card-header">📥 ServerHello (Decoded)</div>')
                            
                            if getattr(self, '_summary_expand_state', {}).get('decoded_serverhello', True):
                                html_parts.append('<div style="margin-top:8px;">')
                                if getattr(sh, 'version', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Version:</b> {sh.version}</div>')
                                if getattr(sh, 'cipher', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Chosen Cipher:</b> {sh.cipher}</div>')
                                if getattr(sh, 'extensions', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Extensions:</b> {sh.extensions}</div>')
                                if getattr(sh, 'compression', None) is not None:
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Compression:</b> {sh.compression}</div>')
                                html_parts.append('</div>')
                            html_parts.append('</div>')
                        if pki and getattr(pki, 'certificates', None):
                            try:
                                expanded = getattr(self, '_summary_expand_state', {}).get('pki_chain', True)
                                arrow = '▼' if expanded else '▶'
                                html_parts.append('<div class="card">')
                                html_parts.append(f"<div style='cursor:pointer;'><a href=\"toggle:pki_chain\" style='text-decoration:none; color:#1a1a1a;'><span style='color:#1976d2; font-size:14px;'>{arrow}</span> <span class='card-header' style='display:inline; border:none; padding:0;'>📜 Certificate Chain</span></a></div>")
                            except Exception:
                                html_parts.append('<div class="card"><div class="card-header">📜 Certificate Chain</div>')
                            
                            if getattr(self, '_summary_expand_state', {}).get('pki_chain', True):
                                html_parts.append('<div style="margin-top:8px;">')
                                try:
                                    certs = [c for c in (getattr(pki, 'certificates', []) or [])]
                                    for idx, cert in enumerate(certs, start=1):
                                        html_parts.append(f'<div style="background:#fafafa; padding:10px; border-left:3px solid #f57c00; border-radius:4px; margin:8px 0;">')
                                        html_parts.append(f'<div style="font-weight:700; color:#f57c00; margin-bottom:6px;">Certificate #{idx}</div>')
                                        
                                        if getattr(cert, 'subject', None):
                                            html_parts.append(f'<div style="margin:4px 0;"><b>Subject:</b> {cert.subject}</div>')
                                        if getattr(cert, 'issuer', None):
                                            html_parts.append(f'<div style="margin:4px 0;"><b>Issuer:</b> {cert.issuer}</div>')
                                        if getattr(cert, 'valid_from', None) and getattr(cert, 'valid_to', None):
                                            html_parts.append(f'<div style="margin:4px 0;"><b>Validity:</b> {cert.valid_from} → {cert.valid_to}</div>')
                                        if getattr(cert, 'public_key', None):
                                            html_parts.append(f'<div style="margin:4px 0;"><b>Public Key:</b> {cert.public_key}</div>')
                                        if getattr(cert, 'signature_algorithm', None):
                                            html_parts.append(f'<div style="margin:4px 0;"><b>Signature:</b> {cert.signature_algorithm}</div>')
                                        if getattr(cert, 'subject_alternative_names', None):
                                            san = cert.subject_alternative_names
                                            if isinstance(san, list):
                                                san_str = ', '.join(san[:5])
                                                if len(san) > 5:
                                                    san_str += f' (+{len(san) - 5} more)'
                                            else:
                                                san_str = str(san)
                                            html_parts.append(f'<div style="margin:4px 0;"><b>SAN:</b> {san_str}</div>')
                                        
                                        html_parts.append('</div>')
                                except Exception:
                                    pass
                                html_parts.append('</div>')
                            html_parts.append('</div>')
                        if csn:
                            have_csn = True
                            try:
                                expanded = getattr(self, '_summary_expand_state', {}).get('cipher_suite_negotiation', True)
                                arrow = '▼' if expanded else '▶'
                                html_parts.append('<div class="card">')
                                html_parts.append(f"<div style='cursor:pointer;'><a href=\"toggle:cipher_suite_negotiation\" style='text-decoration:none; color:#1a1a1a;'><span style='color:#1976d2; font-size:14px;'>{arrow}</span> <span class='card-header' style='display:inline; border:none; padding:0;'>🔑 Cipher Suite Negotiation</span></a></div>")
                            except Exception:
                                html_parts.append('<div class="card"><div class="card-header">🔑 Cipher Suite Negotiation</div>')
                            
                            if getattr(self, '_summary_expand_state', {}).get('cipher_suite_negotiation', True):
                                html_parts.append('<div style="margin-top:8px;">')
                                if getattr(csn, 'chosen', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Chosen Cipher:</b> {csn.chosen}</div>')
                                if getattr(csn, 'key_exchange', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Key Exchange:</b> {csn.key_exchange}</div>')
                                if getattr(csn, 'authentication', None):
                                    html_parts.append(f'<div style="margin:6px 0;"><b>Authentication:</b> {csn.authentication}</div>')
                                if getattr(csn, 'aead', None) is not None:
                                    html_parts.append(f'<div style="margin:6px 0;"><b>AEAD:</b> {csn.aead}</div>')
                                html_parts.append('</div>')
                            html_parts.append('</div>')
                    
                    # Fallback: parse sections from markdown report text ONLY if no decoded data object exists
                    if not have_decoded_data:
                        try:
                            base_dir = Path(self.current_file_path).parent if getattr(self, 'current_file_path', None) else Path.cwd()
                            report_text = None
                            for name in ("tac_session_report.md", "tac_tls_flow.md", "tac_session_raw.md"):
                                p = base_dir / name
                                if p.exists():
                                    report_text = p.read_text(encoding='utf-8', errors='ignore')
                                    break
                            if report_text:
                                import re
                                # More flexible heading capture (case-insensitive, optional colons)
                                def section_after(heading_regex: str, upto_regex: str | None = None):
                                    flags = re.I | re.S
                                    if upto_regex:
                                        m = re.search(heading_regex + r"\s*:?\s*(.*?)" + upto_regex, report_text, flags)
                                    else:
                                        m = re.search(heading_regex + r"\s*:?\s*(.*?)(?:\n\s*[A-Z][^\n]+:|\Z)", report_text, flags)
                                    return m.group(1) if m else None
                                # ClientHello
                                ch_text = section_after(r"Decoded\s+ClientHello", r"\n\s*Decoded\s+ServerHello")
                                if not ch_text:
                                    ch_text = section_after(r"ClientHello\s*\(decoded\)")
                                if ch_text:
                                    try:
                                        expanded = getattr(self, '_summary_expand_state', {}).get('decoded_clienthello', True)
                                        arrow = '▼' if expanded else '▶'
                                        html_parts.append(f"<div style='margin-top:6px;'><a href=\"toggle:decoded_clienthello\" style='text-decoration:none;color:#0066cc;'>{arrow} <b>Decoded ClientHello</b></a></div>")
                                    except Exception:
                                        pass
                                    if getattr(self, '_summary_expand_state', {}).get('decoded_clienthello', True):
                                        html_parts.append('<ul style="margin:4px 0 8px 20px;">')
                                        for line in [l.strip() for l in ch_text.splitlines() if l.strip()]:
                                            line = re.sub(r"^[-*]\s*", "", line)
                                            line = re.sub(r"^\*+\s*|\*+\s*$", "", line)  # strip stray markdown asterisks
                                            if not line or line.startswith('##') or line.lower().startswith(('summary','full tls handshake')):
                                                continue
                                            html_parts.append(f'<li>{line}</li>')
                                        html_parts.append('</ul>')
                                # ServerHello
                                sh_text = section_after(r"Decoded\s+ServerHello", r"\n\s*(PKI\s+Certificate\s+Chain|Cipher\s+Suite\s+Negotiation)")
                                if not sh_text:
                                    sh_text = section_after(r"ServerHello\s*\(decoded\)")
                                if sh_text:
                                    try:
                                        expanded = getattr(self, '_summary_expand_state', {}).get('decoded_serverhello', True)
                                        arrow = '▼' if expanded else '▶'
                                        html_parts.append(f"<div style='margin-top:6px;'><a href=\"toggle:decoded_serverhello\" style='text-decoration:none;color:#0066cc;'>{arrow} <b>Decoded ServerHello</b></a></div>")
                                    except Exception:
                                        pass
                                    if getattr(self, '_summary_expand_state', {}).get('decoded_serverhello', True):
                                        html_parts.append('<ul style="margin:4px 0 8px 20px;">')
                                        for line in [l.strip() for l in sh_text.splitlines() if l.strip()]:
                                            line = re.sub(r"^[-*]\s*", "", line)
                                            line = re.sub(r"^\*+\s*|\*+\s*$", "", line)
                                            if not line or line.startswith('##') or line.lower().startswith(('summary','full tls handshake')):
                                                continue
                                            html_parts.append(f'<li>{line}</li>')
                                        html_parts.append('</ul>')
                                # Cipher Suite Negotiation
                                csn_text = section_after(r"Cipher\s+Suite\s+Negotiation")
                                if csn_text:
                                    try:
                                        expanded = getattr(self, '_summary_expand_state', {}).get('cipher_suite_negotiation', True)
                                        arrow = '▼' if expanded else '▶'
                                        html_parts.append(f"<div style='margin-top:6px;'><a href=\"toggle:cipher_suite_negotiation\" style='text-decoration:none;color:#0066cc;'>{arrow} <b>Cipher Suite Negotiation</b></a></div>")
                                    except Exception:
                                        pass
                                    if getattr(self, '_summary_expand_state', {}).get('cipher_suite_negotiation', True):
                                        html_parts.append('<ul style="margin:4px 0 8px 20px;">')
                                        for line in [l.strip() for l in csn_text.splitlines() if l.strip()]:
                                            line = re.sub(r"^[-*]\s*", "", line)
                                            line = re.sub(r"^\*+\s*|\*+\s*$", "", line)
                                            if not line or line.startswith('##') or line.lower().startswith(('summary','full tls handshake','session timeline')):
                                                continue
                                            html_parts.append(f'<li>{line}</li>')
                                        html_parts.append('</ul>')
                        except Exception:
                            pass
                except Exception:
                    pass
                html_parts.append('</div>')
                try:
                    self.tls_overview_view.setHtml(''.join(html_parts))
                except Exception:
                    self.tls_overview_view.setText('\n'.join([p for p in html_parts if p and '<' not in p]))
        except Exception:
            pass

        # Security tab (ladder diagram, certificates, cipher analysis, raw APDUs)
        try:
            if hasattr(self, 'tls_security_view') and getattr(data, 'handshake', None):
                # Build comprehensive security view with ASCII ladder diagram
                security_html = []
                
                # Section 1: ASCII Ladder Diagram with Timestamps
                try:
                    if getattr(data, 'flow_events', None):
                        # Group consecutive ApplicationData bursts per direction with counts
                        grouped = []
                        def flush_group(buf_role, buf_count, first_ts):
                            if buf_role and buf_count > 0:
                                grouped.append({
                                    'direction': buf_role,
                                    'label': 'ApplicationData x' + str(buf_count),
                                    'timestamp': first_ts
                                })
                        buf_role = None
                        buf_count = 0
                        first_ts = ''
                        for ev in data.flow_events[:200]:
                            role = getattr(ev, 'direction', '') or ''
                            label = getattr(ev, 'label', '') or ''
                            ts = getattr(ev, 'timestamp', '') or ''
                            if label == 'ApplicationData':
                                if buf_role == role:
                                    buf_count += 1
                                else:
                                    flush_group(buf_role, buf_count, first_ts)
                                    buf_role = role
                                    buf_count = 1
                                    first_ts = ts
                                continue
                            else:
                                flush_group(buf_role, buf_count, first_ts)
                                buf_role = None
                                buf_count = 0
                            # Normalize Finished after CCS to Encrypted Finished for clarity
                            if label == 'Finished':
                                label = 'Encrypted Finished'
                            grouped.append({'direction': role, 'label': label, 'timestamp': ts})
                        flush_group(buf_role, buf_count, first_ts)

                        left = []
                        right = []
                        for ev in grouped:
                            role = ev.get('direction', '')
                            detail = ev.get('label', '')
                            ts = ev.get('timestamp', '')
                            if role.startswith('SIM'):
                                left.append(f"{ts}  {detail}"); right.append("")
                            elif role.startswith('ME'):
                                left.append(""); right.append(f"{ts}  {detail}")
                            else:
                                left.append(f"{ts}  {detail}"); right.append("")
                        # Build ASCII ladder diagram
                        security_html.append('<div style="font-family: monospace; font-size: 11px; background:#fafafa; padding:10px; border:1px solid #ddd; border-radius:4px;">')
                        security_html.append('<b>📊 TLS Handshake Ladder Diagram</b><br/><br/>')
                        security_html.append('<span style="color:#666;">SIM (Client)</span>' + ' ' * 25 + '<span style="color:#666;">ME (Server)</span><br/>')
                        security_html.append('    │' + ' ' * 50 + '│<br/>')
                        
                        for ev in grouped:
                            role = ev.get('direction', '')
                            detail = ev.get('label', '')
                            ts = ev.get('timestamp', '').split()[-1] if ev.get('timestamp') else ''  # Extract time only
                            
                            if role.startswith('SIM'):
                                # SIM → ME (left to right arrow)
                                arrow = f'├──{detail}─────────────────────────────────────────────▶│'
                                security_html.append(f'<span style="color:#2a7ed3;">{arrow}</span> <span style="color:#999;">{ts}</span><br/>')
                            elif role.startswith('ME'):
                                # ME → SIM (right to left arrow)
                                arrow = f'│◀─────────────────────────────────────────────{detail}──┤'
                                security_html.append(f'<span style="color:#e08a00;">{arrow}</span> <span style="color:#999;">{ts}</span><br/>')
                            else:
                                security_html.append(f'    │   {detail}' + ' ' * 30 + f'│ <span style="color:#999;">{ts}</span><br/>')
                        
                        security_html.append('    │' + ' ' * 50 + '│<br/>')
                        security_html.append('</div><br/>')
                except Exception:
                    pass
                # Section 2: Cipher Suite Analysis
                try:
                    if summ:
                        security_html.append('<div style="margin:16px 0;"><b>🔐 Cipher Suite Analysis</b></div>')
                        security_html.append('<div style="background:#f9f9f9; padding:8px; border-left:3px solid #2a7ed3; margin-bottom:8px;">')
                        
                        if summ.version:
                            ver_color = '#2e7d32' if 'TLS 1.2' in summ.version or 'TLS 1.3' in summ.version else '#e65100'
                            security_html.append(f'<b>Version:</b> <span style="color:{ver_color};">{summ.version}</span><br/>')
                        
                        if summ.chosen_cipher:
                            cipher = summ.chosen_cipher
                            security_html.append(f'<b>Chosen Cipher:</b> {cipher}<br/>')
                            
                            # Analyze cipher components
                            if 'ECDHE' in cipher:
                                security_html.append('  • <span style="color:#2e7d32;">✓ Perfect Forward Secrecy (ECDHE)</span><br/>')
                            if 'GCM' in cipher or 'CHACHA20' in cipher or 'POLY1305' in cipher:
                                security_html.append('  • <span style="color:#2e7d32;">✓ AEAD Mode (Authenticated Encryption)</span><br/>')
                            if 'AES_256' in cipher:
                                security_html.append('  • <span style="color:#2e7d32;">✓ 256-bit Encryption</span><br/>')
                            elif 'AES_128' in cipher:
                                security_html.append('  • <span style="color:#1976d2;">◆ 128-bit Encryption</span><br/>')
                        
                        security_html.append('</div>')
                except Exception:
                    pass
                
                # Section 3: Certificate Chain
                try:
                    decoded = getattr(data, 'decoded', None)
                    if decoded and getattr(decoded, 'pki_chain', None):
                        pki = decoded.pki_chain
                        certs = getattr(pki, 'certificates', None)
                        if certs:
                            security_html.append('<div style="margin:16px 0;"><b>📜 PKI Certificate Chain</b></div>')
                            for idx, cert in enumerate(certs, start=1):
                                security_html.append(f'<div style="background:#fff9e6; padding:8px; border-left:3px solid #e08a00; margin-bottom:8px;">')
                                security_html.append(f'<b>Certificate #{idx}</b><br/>')
                                
                                if getattr(cert, 'subject', None):
                                    security_html.append(f'<b>Subject:</b> {cert.subject}<br/>')
                                if getattr(cert, 'issuer', None):
                                    security_html.append(f'<b>Issuer:</b> {cert.issuer}<br/>')
                                if getattr(cert, 'valid_from', None) and getattr(cert, 'valid_to', None):
                                    security_html.append(f'<b>Validity:</b> {cert.valid_from} → {cert.valid_to}<br/>')
                                if getattr(cert, 'public_key', None):
                                    security_html.append(f'<b>Public Key:</b> {cert.public_key}<br/>')
                                if getattr(cert, 'signature_algorithm', None):
                                    security_html.append(f'<b>Signature:</b> {cert.signature_algorithm}<br/>')
                                if getattr(cert, 'subject_alternative_names', None):
                                    san = cert.subject_alternative_names
                                    if isinstance(san, list):
                                        security_html.append(f'<b>SAN:</b> {", ".join(san)}<br/>')
                                    else:
                                        security_html.append(f'<b>SAN:</b> {san}<br/>')
                                
                                security_html.append('</div>')
                except Exception:
                    pass
                
                # Section 4: Raw APDUs
                try:
                    if getattr(data, 'raw_apdus', None):
                        security_html.append('<div style="margin:16px 0;"><b>📋 Raw APDU Trace</b></div>')
                        security_html.append('<div style="font-family:monospace; font-size:10px; background:#f5f5f5; padding:8px; border:1px solid #ddd; max-height:300px; overflow-y:auto;">')
                        for apdu in data.raw_apdus[:100]:  # Limit to first 100
                            security_html.append(apdu + '<br/>')
                        if len(data.raw_apdus) > 100:
                            security_html.append(f'<span style="color:#999;">... and {len(data.raw_apdus) - 100} more APDUs</span>')
                        security_html.append('</div>')
                except Exception:
                    pass
                
                # Render to security view
                try:
                    if security_html:
                        self.tls_security_view.setHtml(''.join(security_html))
                    else:
                        self.tls_security_view.setHtml("No security information available")
                except Exception:
                    pass
        except Exception:
            pass

        # Note: Raw APDUs now integrated into Security tab, no separate tab needed

        # Bring TLS Flow tab to front
        try:
            self.hex_tab_widget.setCurrentIndex(2)
            if hasattr(self, 'tls_subtabs'):
                self.tls_subtabs.setCurrentIndex(0)
        except Exception:
            pass

        # Internal marker for tests/debug
        try:
            self._tls_flow_render_mode = 'report'
        except Exception:
            pass

        # Consider it populated if there are any flow events or summary fields
        try:
            if getattr(data, 'flow_events', None):
                return True
            summ = getattr(data, 'summary', None)
            if summ and (summ.sni or summ.version or summ.chosen_cipher):
                return True
        except Exception:
            pass
        return False
    def create_left_pane(self) -> QWidget:
        """Create the left pane with Interpretation, Channel Groups, and Parsing Log tabs."""
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)

        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        interpretation_tab = self.create_interpretation_tab()
        tab_widget.addTab(interpretation_tab, "Interpretation")

        groups_tab = self.create_channel_groups_tab()
        tab_widget.addTab(groups_tab, "Flow Overview")

        parsing_log_tab = self.create_parsing_log_tab()
        tab_widget.addTab(parsing_log_tab, "Parsing Log")

        # Style Test tab removed

        self.tab_widget = tab_widget
        return left_widget

    

    def _parse_hex_input_bytes(self, text: str) -> bytes:
        """Parse user-pasted hex input into bytes.
        - Accepts whitespace/newlines and continuous hex strings
        - Accepts optional 0x prefixes (e.g., 0xA0)
        - Ignores offsets like '0000:' or '0x00:' at line start
        - Ignores ASCII columns after two spaces (common hex dump)
        Raises ValueError on invalid tokens or odd nibble count.
        """
        lines = text.splitlines()
        out: list[int] = []
        for line in lines:
            # Strip comments after ';' or '#'
            for sep in (';', '#'):
                if sep in line:
                    line = line.split(sep, 1)[0]
            l = line.strip()
            # Remove leading offsets like '0000:' or '0x00:'
            if ':' in l:
                left, right = l.split(':', 1)
                if all(ch in '0123456789abcdefABCDEFxX' for ch in left):
                    l = right.strip()
            # Drop ASCII column after two spaces (simple heuristic)
            if '  ' in l:
                l = l.split('  ', 1)[0]
            # Remove 0x prefixes anywhere
            l = l.replace('0x', '').replace('0X', '')
            # Keep only hex digits and spaces
            filtered = ''.join(ch if ch in '0123456789abcdefABCDEF ' else ' ' for ch in l)
            # If no spaces, treat whole line as one token; else split
            tokens = [filtered] if (' ' not in filtered.strip() and filtered.strip()) else [t for t in filtered.split() if t]
            if not tokens:
                continue
            for t in tokens:
                s = t.replace(' ', '')
                if len(s) == 0:
                    continue
                if len(s) % 2 == 1:
                    raise ValueError(f"Odd number of hex digits in '{s}'")
                # Chunk into byte pairs
                try:
                    for i in range(0, len(s), 2):
                        out.append(int(s[i:i+2], 16))
                except Exception:
                    raise ValueError(f"Invalid hex token '{t}'")
        return bytes(out)

    def on_analyze_hex_clicked(self):
        """Handle Analyze Hex button: parse input and reuse APDU/protocol analysis."""
        text = self.analyze_hex_input.toPlainText()
        try:
            data = self._parse_hex_input_bytes(text)
        except ValueError as e:
            self.analyze_hex_status.setText(str(e))
            return

        byte_count = len(data)
        self.analyze_hex_status.setText(f"{byte_count} bytes ({byte_count*8} bits)")

        # Build a temporary TraceItem compatible with our pipeline
        from .xti_parser import TraceItem, TreeNode
        temp = TraceItem(
            protocol="MANUAL",
            type="ANALYZE",
            summary="Manual Hex Analysis",
            rawhex=data.hex().upper(),
            timestamp=None,
            details_tree=TreeNode("Manual Analysis"),
            timestamp_sort_key=""
        )

        # Reuse existing analysis pipeline and UI rendering
        self.update_analyze_view(temp)

    def create_interpretation_tab(self) -> QWidget:
        """Create the interpretation tab with trace list and inspector."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Search box and filter controls
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search interpretation text...")
        
        # Filter navigation buttons
        self.prev_match_button = QPushButton("◀")
        self.prev_match_button.setMaximumWidth(30)
        self.prev_match_button.setEnabled(False)
        self.prev_match_button.setToolTip("Previous match (F2)")
        
        self.next_match_button = QPushButton("▶")
        self.next_match_button.setMaximumWidth(30)
        self.next_match_button.setEnabled(False)
        self.next_match_button.setToolTip("Next match (F3)")
        
        self.filter_status_label = QLabel("")
        self.filter_status_label.setStyleSheet("color: #666; font-size: 11px;")
        self.filter_status_label.setMinimumWidth(60)
        
        # Clear filter button (initially hidden)
        self.clear_filter_button = QPushButton("Clear Filter")
        self.clear_filter_button.setVisible(False)
        self.clear_filter_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.prev_match_button)
        search_layout.addWidget(self.next_match_button)
        search_layout.addWidget(self.filter_status_label)
        search_layout.addWidget(self.clear_filter_button)
        layout.addLayout(search_layout)
        
        # Advanced filters panel
        filters_frame = self.create_advanced_filters_panel()
        layout.addWidget(filters_frame)
        
        # Navigation pour paires Command/Response
        pairing_layout = QHBoxLayout()
        pairing_label = QLabel("Command/Response Pairing:")
        
        self.goto_paired_button = QPushButton("Go to Paired Item")
        self.goto_paired_button.setEnabled(False)
        self.goto_paired_button.setToolTip("Navigate to the paired FETCH or TERMINAL RESPONSE (Ctrl+G)")
        
        self.pairing_info_label = QLabel("")
        self.pairing_info_label.setStyleSheet("color: #666; font-style: italic;")
        
        pairing_layout.addWidget(pairing_label)
        pairing_layout.addWidget(self.goto_paired_button)
        pairing_layout.addWidget(self.pairing_info_label)
        pairing_layout.addStretch()
        layout.addLayout(pairing_layout)
        
        # Create vertical splitter for interpretation list and inspector
        left_splitter = QSplitter(Qt.Vertical)
        layout.addWidget(left_splitter)
        
        # Top: Interpretation list
        interpretation_widget = QWidget()
        interpretation_layout = QVBoxLayout(interpretation_widget)
        interpretation_layout.setContentsMargins(0, 0, 0, 0)
        
        list_label = QLabel("Interpretation")
        interpretation_layout.addWidget(list_label)
        
        # Tree view for trace items (matching Universal Tracer style)
        self.trace_table = QTreeView()  # Changed from QTableView to QTreeView
        self.trace_model = InterpretationTreeModel()
        self.filter_model = TraceItemFilterModel()
        self.filter_model.setSourceModel(self.trace_model)
        self.trace_table.setModel(self.filter_model)
        
        # Configure tree view to match Universal Tracer style
        self.trace_table.setSelectionBehavior(QTreeView.SelectRows)
        # Allow Shift/Ctrl selection of multiple rows
        try:
            from PySide6.QtWidgets import QAbstractItemView
            self.trace_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        except Exception:
            pass
        self.trace_table.setAlternatingRowColors(False)  # Temporarily disable to test background colors
        self.trace_table.setSortingEnabled(False)  # Disable manual sorting to preserve chronological order
        self.trace_table.setRootIsDecorated(False)  # Don't show expand/collapse icons for top level
        self.trace_table.setIndentation(0)  # No indentation for top level items
        self.trace_table.setUniformRowHeights(True)  # Improve performance and appearance
        
        # Set a more compact row height like Universal Tracer
        self.trace_table.setStyleSheet("""
            QTreeView {
                outline: 0;
                border: 1px solid #c0c0c0;
                gridline-color: #d0d0d0;
                selection-background-color: #3399ff;
            }
            QTreeView::item {
                padding: 2px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeView::item:selected {
                background: #3399ff;
                color: white;
            }
        """)
        
        # Resize columns for tree view
        header = self.trace_table.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Summary column
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Protocol
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Time
        
        interpretation_layout.addWidget(self.trace_table)
        # Context menu for interpretation list (copy)
        self.trace_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.trace_table.customContextMenuRequested.connect(self.on_trace_table_context_menu)
        left_splitter.addWidget(interpretation_widget)
        
        # Bottom: Inspector
        inspector_widget = QWidget()
        inspector_layout = QVBoxLayout(inspector_widget)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        
        inspector_label = QLabel("Inspector")
        inspector_layout.addWidget(inspector_label)
        
        self.inspector_tree = QTreeView()
        self.inspector_model = InspectorTreeModel()
        self.inspector_tree.setModel(self.inspector_model)
        self.inspector_tree.setHeaderHidden(False)
        
        # Style the inspector tree to match Universal Tracer
        self.inspector_tree.setStyleSheet("""
            QTreeView {
                outline: 0;
                border: 1px solid #c0c0c0;
                selection-background-color: #3399ff;
            }
            QTreeView::item {
                padding: 2px;
                border-bottom: 1px solid #f5f5f5;
            }
            QTreeView::item:selected {
                background: #3399ff;
                color: white;
            }
        """)
        
        inspector_layout.addWidget(self.inspector_tree)
        # Context menu for inspector tree (copy)
        self.inspector_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.inspector_tree.customContextMenuRequested.connect(self.on_inspector_tree_context_menu)
        left_splitter.addWidget(inspector_widget)
        
        # Set initial proportions (60% list, 40% inspector)
        left_splitter.setSizes([400, 300])
        self.left_splitter = left_splitter
        
        return tab_widget
    
    def create_advanced_filters_panel(self) -> QFrame:
        """Create the advanced filters panel with command types, server filter, and time range."""
        filters_frame = QFrame()
        filters_frame.setFrameStyle(QFrame.StyledPanel)
        # No hard max height; let content define height when expanded
        
        filters_layout = QVBoxLayout(filters_frame)
        filters_layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        filters_label = QLabel("Advanced Filters")
        filters_label.setStyleSheet("font-weight: bold; color: #333;")
        
        # Toggle button to show/hide filters
        self.toggle_filters_button = QPushButton("▼ Hide")
        self.toggle_filters_button.setMaximumWidth(80)
        self.toggle_filters_button.clicked.connect(self.toggle_advanced_filters)
        
        header_layout.addWidget(filters_label)
        header_layout.addStretch()
        header_layout.addWidget(self.toggle_filters_button)
        filters_layout.addLayout(header_layout)
        
        # Main filters container
        self.filters_container = QWidget()
        container_layout = QHBoxLayout(self.filters_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Command Type Filters (compact menu)
        cmd_group = QGroupBox("Command Types")
        cmd_layout = QHBoxLayout(cmd_group)
        cmd_layout.setContentsMargins(5, 5, 5, 5)

        self.command_checkboxes = {}
        self.command_actions = {}

        self.cmd_types_button = QToolButton()
        self.cmd_types_button.setPopupMode(QToolButton.InstantPopup)
        self.cmd_types_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.cmd_types_button.setText("Command Types (All)")
        types_menu = QMenu(self.cmd_types_button)

        for key, label in [
            ("OPEN", "OPEN CHANNEL"),
            ("SEND", "SEND DATA"),
            ("RECEIVE", "RECEIVE DATA"),
            ("CLOSE", "CLOSE CHANNEL"),
            ("ENVELOPE", "ENVELOPE"),
            ("TERMINAL", "TERMINAL RESPONSE"),
            ("TIMER", "Timer Management"),
            ("TIMER_EXP", "Timer Expiration"),
            ("COLD_RESET", "Cold Reset"),
            ("PLI", "Provide Local Info"),
        ]:
            act = types_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(True)
            if hasattr(act, 'toggled'):
                act.toggled.connect(lambda _c=False, k=key: (self.on_command_filter_changed(), self.update_command_types_button()))
            else:
                act.triggered.connect(lambda _c=False, k=key: (self.on_command_filter_changed(), self.update_command_types_button()))
            self.command_actions[key] = act

        types_menu.addSeparator()
        sel_all = types_menu.addAction("Select All")
        sel_all.triggered.connect(self.select_all_command_types)
        sel_none = types_menu.addAction("Select None")
        sel_none.triggered.connect(self.select_none_command_types)

        self.cmd_types_button.setMenu(types_menu)
        cmd_layout.addWidget(self.cmd_types_button)
        
        # Disable command type filtering by default (empty list means no filter)
        self.command_checkboxes_initial_state = True
        
        # Server Filter
        server_group = QGroupBox("Server")
        server_layout = QVBoxLayout(server_group)
        server_layout.setContentsMargins(5, 5, 5, 5)
        
        self.server_combo = QComboBox()
        self.server_combo.addItems(["All Servers", "DP+", "TAC", "DNS by ME", "DNS", "Other"])
        self.server_combo.currentTextChanged.connect(self.on_server_filter_changed)
        server_layout.addWidget(self.server_combo)
        
        # Time Range Filter (compact single row)
        time_group = QGroupBox("Time Range")
        time_layout = QHBoxLayout(time_group)
        time_layout.setContentsMargins(10, 10, 10, 10)
        time_layout.setSpacing(8)
        time_layout.addWidget(QLabel("From:"))
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("hh:mm:ss")
        self.start_time_edit.setFixedWidth(90)
        self.start_time_edit.setStyleSheet("QTimeEdit { padding: 2px; font-size: 11px; }")
        self.start_time_edit.timeChanged.connect(self.on_time_range_changed)
        time_layout.addWidget(self.start_time_edit)
        time_layout.addWidget(QLabel("To:"))
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("hh:mm:ss")
        self.end_time_edit.setFixedWidth(90)
        self.end_time_edit.setStyleSheet("QTimeEdit { padding: 2px; font-size: 11px; }")
        self.end_time_edit.timeChanged.connect(self.on_time_range_changed)
        time_layout.addWidget(self.end_time_edit)
        btn_style = "QPushButton { padding: 4px 8px; font-size: 10px; }"
        self.reset_time_btn = QPushButton("All Time")
        self.reset_time_btn.setStyleSheet(btn_style)
        self.reset_time_btn.clicked.connect(self.reset_time_filter)
        self.last_5min_btn = QPushButton("Last 5min")
        self.last_5min_btn.setStyleSheet(btn_style)
        self.last_5min_btn.clicked.connect(lambda: self.set_last_minutes(5))
        self.last_30min_btn = QPushButton("Last 30min")
        self.last_30min_btn.setStyleSheet(btn_style)
        self.last_30min_btn.clicked.connect(lambda: self.set_last_minutes(30))
        self.last_hour_btn = QPushButton("Last 1h")
        self.last_hour_btn.setStyleSheet(btn_style)
        self.last_hour_btn.clicked.connect(lambda: self.set_last_minutes(60))
        time_layout.addWidget(self.reset_time_btn)
        time_layout.addWidget(self.last_5min_btn)
        time_layout.addWidget(self.last_30min_btn)
        time_layout.addWidget(self.last_hour_btn)
        time_layout.addStretch()

        # Remove verbose time range info label to save space
        self.time_range_info = QLabel("")
        self.time_range_info.setVisible(False)
        
        # Initialize time range variables
        self.trace_start_time = None
        self.trace_end_time = None
        
        # Add groups to container
        container_layout.addWidget(cmd_group)
        container_layout.addWidget(server_group)
        container_layout.addWidget(time_group)
        container_layout.addStretch()
        # Favor width for Command Types to avoid clipping
        container_layout.setStretch(0, 3)
        container_layout.setStretch(1, 1)
        container_layout.setStretch(2, 2)
        
        filters_layout.addWidget(self.filters_container)
        
        # Start with filters collapsed to prevent initialization issues
        self.filters_container.setVisible(False)
        self.toggle_filters_button.setText("▼ Show")
        
        return filters_frame
    
    def toggle_advanced_filters(self):
        """Toggle the visibility of advanced filters."""
        visible = self.filters_container.isVisible()
        self.filters_container.setVisible(not visible)
        # Show arrow should be down; Hide arrow should be up
        self.toggle_filters_button.setText("▼ Show" if not visible else "▲ Hide")
        
    def update_command_types_button(self):
        """Update the label of the command types button with selected count."""
        total = len(getattr(self, 'command_actions', {})) + len(getattr(self, 'command_checkboxes', {}))
        selected = 0
        for cb in getattr(self, 'command_checkboxes', {}).values():
            if cb.isChecked():
                selected += 1
        for act in getattr(self, 'command_actions', {}).values():
            try:
                if act.isChecked():
                    selected += 1
            except Exception:
                pass
        if selected == 0:
            text = "Command Types (None)"
        elif selected == total:
            text = "Command Types (All)"
        else:
            text = f"Command Types ({selected})"
        if hasattr(self, 'cmd_types_button') and self.cmd_types_button:
            self.cmd_types_button.setText(text)

    def select_all_command_types(self):
        """Select all command types (main and extended)."""
        for cb in getattr(self, 'command_checkboxes', {}).values():
            cb.setChecked(True)
        for act in getattr(self, 'command_actions', {}).values():
            try:
                act.setChecked(True)
            except Exception:
                pass
        self.on_command_filter_changed()
        self.update_command_types_button()

    def select_none_command_types(self):
        """Deselect all command types (main and extended)."""
        for cb in getattr(self, 'command_checkboxes', {}).values():
            cb.setChecked(False)
        for act in getattr(self, 'command_actions', {}).values():
            try:
                act.setChecked(False)
            except Exception:
                pass
        self.on_command_filter_changed()
        self.update_command_types_button()
    
    def create_channel_groups_tab(self) -> QWidget:
        """Create the Flow Overview tab with multiple sub-views to test row coloring methods."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Header with export button and kind filter
        header_layout = QHBoxLayout()
        groups_label = QLabel("Flow Overview")
        kind_filter_label = QLabel("Show:")
        self.kind_filter_combo = QComboBox()
        self.kind_filter_combo.addItems(["Sessions & Events", "Sessions Only", "Events Only"])
        self.kind_filter_combo.currentIndexChanged.connect(self.on_kind_filter_changed)
        export_button = QPushButton("Export CSV")
        export_button.clicked.connect(self.export_channel_groups_csv)
        
        header_layout.addWidget(groups_label)
        header_layout.addStretch()
        header_layout.addWidget(kind_filter_label)
        header_layout.addWidget(self.kind_filter_combo)
        header_layout.addWidget(export_button)
        layout.addLayout(header_layout)
        
        # Single timeline view using Paint Rect method for event shading
        self.timeline_model = FlowTimelineModel()

        from PySide6.QtCore import QSortFilterProxyModel, QRegularExpression
        from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
        from PySide6.QtGui import QColor, QPen

        class HeaderTypeProxy(QSortFilterProxyModel):
            def headerData(self, section, orientation, role=Qt.DisplayRole):
                if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == 0:
                    return "Type"
                return super().headerData(section, orientation, role)

        class PaintRectDelegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                # Manually paint rect for Event rows, then draw clearer grid lines
                model = index.model()
                type_index = model.index(index.row(), 0, index.parent())
                is_event = str(type_index.data(Qt.DisplayRole)).strip() == "Event"

                painter.save()
                if is_event:
                    painter.fillRect(option.rect, QColor(235, 235, 235))
                # Paint the default content on top of background
                QStyledItemDelegate.paint(self, painter, option, index)
                # Draw vertical/right border for each cell and bottom border for rows
                pen = QPen(QColor(200, 200, 200))  # slightly darker than background for contrast
                pen.setWidth(1)
                painter.setPen(pen)
                r = option.rect
                # Right vertical line (skip for last column)
                try:
                    if index.column() < model.columnCount(index.parent()) - 1:
                        painter.drawLine(r.right(), r.top(), r.right(), r.bottom())
                except Exception:
                    pass
                # Bottom horizontal line
                painter.drawLine(r.left(), r.bottom(), r.right(), r.bottom())
                painter.restore()
                return

        self.timeline_table = QTreeView()
        self.timeline_proxy = HeaderTypeProxy(self)
        self.timeline_proxy.setSourceModel(self.timeline_model)
        self.timeline_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.timeline_proxy.setFilterKeyColumn(0)  # Type column
        self.timeline_table.setModel(self.timeline_proxy)
        self.timeline_table.setSelectionBehavior(QTreeView.SelectRows)
        self.timeline_table.setAlternatingRowColors(False)
        self.timeline_table.setSortingEnabled(False)
        self.timeline_table.setRootIsDecorated(True)
        self.timeline_table.setUniformRowHeights(True)
        tl_header = self.timeline_table.header()
        tl_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Type
        tl_header.setSectionResizeMode(1, QHeaderView.Stretch)           # Label
        tl_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Time
        tl_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Port
        tl_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Protocol
        tl_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Targeted Server
        tl_header.setSectionResizeMode(6, QHeaderView.Stretch)           # IP
        tl_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Opened
        tl_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Closed
        tl_header.setSectionResizeMode(9, QHeaderView.ResizeToContents)  # Duration
        self.timeline_table.setStyleSheet(
            """
            QTreeView {
                outline: 0;
                border: 1px solid #c0c0c0;
                gridline-color: #c8c8c8;
                selection-background-color: #3399ff;
                background: #ffffff;
            }
            QTreeView::item { padding: 3px; }
            QTreeView::item:selected { background: #3399ff; color: white; }
            """
        )
        self.timeline_table.setItemDelegate(PaintRectDelegate(self.timeline_table))

        # Right-click Copy menu
        self._install_copy_menu_for_treeview(self.timeline_table)

        # Hide unwanted columns by title (Role, Time)
        def _hide_columns_by_title(titles):
            try:
                for c in range(self.timeline_proxy.columnCount()):
                    txt = self.timeline_proxy.headerData(c, Qt.Horizontal, Qt.DisplayRole)
                    if str(txt).strip() in titles:
                        self.timeline_table.setColumnHidden(c, True)
            except Exception:
                pass
        _hide_columns_by_title({"Role", "Time"})

        layout.addWidget(self.timeline_table)
        
        return tab_widget

    def on_kind_filter_changed(self, idx: int):
        """Filter Flow Timeline by kind: Session, Event, or both."""
        text = self.kind_filter_combo.currentText()
        from PySide6.QtCore import QRegularExpression
        if "Sessions Only" in text:
            regex = QRegularExpression("^Session$")
        elif "Events Only" in text:
            regex = QRegularExpression("^Event$")
        else:
            regex = QRegularExpression("")
        self.timeline_proxy.setFilterRegularExpression(regex)
        # Hide Role/Time columns (defensive re-apply)
        try:
            for c in range(self.timeline_proxy.columnCount()):
                txt = self.timeline_proxy.headerData(c, Qt.Horizontal, Qt.DisplayRole)
                if str(txt).strip() in ("Role", "Time"):
                    self.timeline_table.setColumnHidden(c, True)
        except Exception:
            pass
    
    def create_parsing_log_tab(self) -> QWidget:
        """Create the Parsing Log tab with validation issues and warnings."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Header with summary, quick severity toggles, combo and clear button
        header_layout = QHBoxLayout()
        self.log_summary_label = QLabel("No validation issues")
        from PySide6.QtWidgets import QComboBox, QButtonGroup
        self.parsing_log_filter_combo = QComboBox()
        self.parsing_log_filter_combo.addItems(["All", "Critical", "Warning", "Info"])
        try:
            self.parsing_log_filter_combo.currentIndexChanged.connect(self.on_parsing_log_filter_changed)
        except Exception:
            pass
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.clear_parsing_log)

        # Quick toggle buttons
        self.btn_log_all = QPushButton("All"); self.btn_log_all.setCheckable(True)
        self.btn_log_crit = QPushButton("Critical"); self.btn_log_crit.setCheckable(True)
        self.btn_log_warn = QPushButton("Warning"); self.btn_log_warn.setCheckable(True)
        self.btn_log_info = QPushButton("Info"); self.btn_log_info.setCheckable(True)
        self.parsing_log_filter_group = QButtonGroup(self)
        self.parsing_log_filter_group.setExclusive(False)  # allow multi-select
        self.parsing_log_filter_group.addButton(self.btn_log_all)
        self.parsing_log_filter_group.addButton(self.btn_log_crit)
        self.parsing_log_filter_group.addButton(self.btn_log_warn)
        self.parsing_log_filter_group.addButton(self.btn_log_info)
        # Style
        for b in (self.btn_log_all, self.btn_log_crit, self.btn_log_warn, self.btn_log_info):
            b.setStyleSheet("QPushButton{padding:2px 8px;} QPushButton:checked{background:#e6f0ff; border:1px solid #6699ff;}")
        # Wire: preset & multi-select behavior
        # Preset combo sets buttons; button clicks apply multi filter
        self.btn_log_all.clicked.connect(lambda checked=True: self._apply_parsing_log_preset("All"))
        self.btn_log_crit.clicked.connect(lambda checked=True: self._apply_parsing_log_buttons_changed())
        self.btn_log_warn.clicked.connect(lambda checked=True: self._apply_parsing_log_buttons_changed())
        self.btn_log_info.clicked.connect(lambda checked=True: self._apply_parsing_log_buttons_changed())

        # Apply saved filter from settings
        # Restore last multi-selection or preset
        try:
            saved_multi = self.settings.get_parsing_log_filter_multi() if hasattr(self, 'settings') and self.settings else "All"
        except Exception:
            saved_multi = "All"
        if saved_multi == "All":
            # Default to all checked
            self.btn_log_all.setChecked(True)
            self.btn_log_crit.setChecked(True)
            self.btn_log_warn.setChecked(True)
            self.btn_log_info.setChecked(True)
            self.parsing_log_filter_combo.setCurrentIndex(self.parsing_log_filter_combo.findText("All"))
        else:
            # Apply multi selection
            parts = {p.strip().lower() for p in saved_multi.split(',') if p.strip()}
            self.btn_log_all.setChecked(False)
            self.btn_log_crit.setChecked('critical' in parts)
            self.btn_log_warn.setChecked('warning' in parts)
            self.btn_log_info.setChecked('info' in parts)
            # Set combo to a neutral label (All) but buttons govern filtering
            self.parsing_log_filter_combo.setCurrentIndex(self.parsing_log_filter_combo.findText("All"))
        # Initial render with restored filter
        QTimer.singleShot(0, self.update_parsing_log)

        header_layout.addWidget(self.log_summary_label)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Severity:"))
        header_layout.addWidget(self.btn_log_all)
        header_layout.addWidget(self.btn_log_crit)
        header_layout.addWidget(self.btn_log_warn)
        header_layout.addWidget(self.btn_log_info)
        header_layout.addWidget(self.parsing_log_filter_combo)
        header_layout.addWidget(self.clear_log_button)
        layout.addLayout(header_layout)
        
        # Parsing log table
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QBrush
        
        self.parsing_log_tree = QTreeWidget()
        self.parsing_log_tree.setHeaderLabels([
            "Severity", "Category", "Message", "Index", "Timestamp", "Details"
        ])
        
        # Configure tree view
        self.parsing_log_tree.setAlternatingRowColors(True)
        self.parsing_log_tree.setSortingEnabled(True)
        self.parsing_log_tree.setRootIsDecorated(False)
        
        # Set column widths
        header = self.parsing_log_tree.header()
        header.resizeSection(0, 80)   # Severity
        header.resizeSection(1, 150)  # Category
        header.resizeSection(2, 300)  # Message
        header.resizeSection(3, 60)   # Index
        header.resizeSection(4, 120)  # Timestamp
        header.resizeSection(5, 200)  # Details
        
        # Style the log tree
        self.parsing_log_tree.setStyleSheet("""
            QTreeWidget {
                outline: 0;
                border: 1px solid #c0c0c0;
                selection-background-color: #3399ff;
            }
            QTreeWidget::item {
                padding: 2px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected {
                background: #3399ff;
                color: white;
            }
        """)

        # Right-click Copy menu
        self._install_copy_menu_for_treewidget(self.parsing_log_tree)
        
        layout.addWidget(self.parsing_log_tree)
        
        return tab_widget

    def on_parsing_log_filter_changed(self, idx: int):
        """Reapply severity filter to the parsing log list."""
        try:
            # Presets: set buttons accordingly
            text = self.parsing_log_filter_combo.currentText()
            self._apply_parsing_log_preset(text)
        except Exception:
            pass

    def _apply_parsing_log_preset(self, text: str):
        """Apply a preset to the multi-select buttons and refresh."""
        try:
            if text == "All":
                self.btn_log_all.setChecked(True)
                self.btn_log_crit.setChecked(True)
                self.btn_log_warn.setChecked(True)
                self.btn_log_info.setChecked(True)
            elif text == "Critical":
                self.btn_log_all.setChecked(False)
                self.btn_log_crit.setChecked(True)
                self.btn_log_warn.setChecked(False)
                self.btn_log_info.setChecked(False)
            elif text == "Warning":
                self.btn_log_all.setChecked(False)
                self.btn_log_crit.setChecked(False)
                self.btn_log_warn.setChecked(True)
                self.btn_log_info.setChecked(False)
            elif text == "Info":
                self.btn_log_all.setChecked(False)
                self.btn_log_crit.setChecked(False)
                self.btn_log_warn.setChecked(False)
                self.btn_log_info.setChecked(True)
            # Persist multi selection
            self._persist_parsing_log_buttons_selection()
            self.update_parsing_log()
        except Exception:
            pass

    def _persist_parsing_log_buttons_selection(self):
        try:
            selected = []
            if self.btn_log_crit.isChecked():
                selected.append("Critical")
            if self.btn_log_warn.isChecked():
                selected.append("Warning")
            if self.btn_log_info.isChecked():
                selected.append("Info")
            if hasattr(self, 'settings') and self.settings:
                self.settings.set_parsing_log_filter_multi(
                    "All" if len(selected) == 3 else ",".join(selected) if selected else "All"
                )
        except Exception:
            pass

    def _apply_parsing_log_buttons_changed(self):
        """Called when any severity button is toggled; refresh and persist."""
        try:
            # If 'All' is checked toggled alone, set all three on
            if self.btn_log_all.isChecked() and not (self.btn_log_crit.isChecked() or self.btn_log_warn.isChecked() or self.btn_log_info.isChecked()):
                self.btn_log_crit.setChecked(True)
                self.btn_log_warn.setChecked(True)
                self.btn_log_info.setChecked(True)
            # If all three are checked, mark All as checked too
            all_on = self.btn_log_crit.isChecked() and self.btn_log_warn.isChecked() and self.btn_log_info.isChecked()
            self.btn_log_all.setChecked(all_on)
            self._persist_parsing_log_buttons_selection()
            self.update_parsing_log()
        except Exception:
            pass
    
    def create_right_pane(self) -> QWidget:
        """Create the right pane with tabbed hex and analyze views."""
        right_widget = QWidget()
        layout = QVBoxLayout(right_widget)
        
        # Header with copy button
        header_layout = QHBoxLayout()
        hex_label = QLabel("Raw & Hex")
        self.copy_button = QPushButton("Copy Hex")
        self.copy_button.setEnabled(False)
        header_layout.addWidget(hex_label)
        header_layout.addStretch()
        header_layout.addWidget(self.copy_button)
        layout.addLayout(header_layout)
        
        # Create tabbed widget for Hex | Analyze
        self.hex_tab_widget = QTabWidget()
        
        # Hex tab
        hex_tab = QWidget()
        hex_layout = QVBoxLayout(hex_tab)
        hex_layout.setContentsMargins(0, 0, 0, 0)
        
        self.hex_text = QTextEdit()
        self.hex_text.setReadOnly(True)
        self.hex_text.setFont(self.get_monospace_font())
        
        # Enable hex-to-TLV navigation on mouse press
        self.hex_text.mousePressEvent = self.on_hex_mouse_press
        
        hex_layout.addWidget(self.hex_text)
        
        self.hex_tab_widget.addTab(hex_tab, "Hex")
        
        # Analyze tab
        analyze_tab = self.create_analyze_tab()
        self.hex_tab_widget.addTab(analyze_tab, "Analyze")

        # TLS Flow tab
        tls_tab = self.create_tls_tab()
        self.hex_tab_widget.addTab(tls_tab, "TLS Flow")
        
        layout.addWidget(self.hex_tab_widget)
        
        return right_widget
    
    def create_analyze_tab(self) -> QWidget:
        """Create the Analyze tab for APDU parsing and manual hex analysis."""
        analyze_widget = QWidget()
        layout = QVBoxLayout(analyze_widget)
        
        # Summary label
        self.summary_label = QLabel("Select an item to analyze")
        self.summary_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                padding: 5px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.summary_label)
        
        # Warning banner (initially hidden)
        self.warning_banner = QLabel()
        self.warning_banner.setStyleSheet("""
            QLabel {
                background-color: #fff3cd;
                border: 1px solid #ffeeba;
                color: #856404;
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        self.warning_banner.setVisible(False)
        layout.addWidget(self.warning_banner)
        
        # Summary cards section (collapsible)
        self.summary_cards = self.create_summary_cards()
        layout.addWidget(self.summary_cards)

        # Manual hex input section
        paste_label = QLabel("Paste Raw Hex (manual analysis):")
        layout.addWidget(paste_label)

        self.analyze_hex_input = QTextEdit()
        self.analyze_hex_input.setPlaceholderText(
            "Examples:\n"
            "80 F2 00 00 00\n"
            "0000: 80 F2 00 00 00  ; offsets allowed\n"
            "Ignore ASCII columns after two spaces"
        )
        # Keep the input compact and aligned left
        self.analyze_hex_input.setFixedHeight(70)
        self.analyze_hex_input.setMaximumWidth(560)
        self.analyze_hex_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        _hex_input_row = QHBoxLayout()
        _hex_input_row.addWidget(self.analyze_hex_input)
        _hex_input_row.addStretch()
        layout.addLayout(_hex_input_row)

        hex_ctrls = QHBoxLayout()
        self.analyze_hex_button = QPushButton("Analyze Hex")
        self.analyze_hex_button.clicked.connect(self.on_analyze_hex_clicked)
        self.analyze_hex_status = QLabel("")
        self.analyze_hex_status.setStyleSheet("color: #666; font-size: 11px;")
        hex_ctrls.addWidget(self.analyze_hex_button)
        hex_ctrls.addWidget(self.analyze_hex_status)
        hex_ctrls.addStretch()
        layout.addLayout(hex_ctrls)
        
        # Header info section
        header_frame = QWidget()
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        header_title = QLabel("APDU Header")
        header_title.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(header_title)
        
        self.header_info = QLabel("No data")
        self.header_info.setFont(self.get_monospace_font())
        header_layout.addWidget(self.header_info)
        
        layout.addWidget(header_frame)
        
        # TLV tree
        tlv_title = QLabel("TLV Structure")
        tlv_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(tlv_title)
        
        from PySide6.QtWidgets import QTreeWidget
        self.tlv_tree = QTreeWidget()
        self.tlv_tree.setHeaderLabels(["Tag", "Name", "Length", "Value", "Offset"])
        self.tlv_tree.setAlternatingRowColors(True)
        
        # Configure column widths - make Value column stretch to fill available space
        header = self.tlv_tree.header()
        header.setStretchLastSection(False)  # Don't stretch last column (Offset)
        header.resizeSection(0, 60)   # Tag
        header.resizeSection(1, 200)  # Name
        header.resizeSection(2, 60)   # Length
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Value column stretches
        header.resizeSection(4, 60)   # Offset
        
        layout.addWidget(self.tlv_tree)
        
        # Add detail view below TLV tree for full value display
        detail_label = QLabel("Selected Value:")
        detail_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(detail_label)
        
        self.tlv_detail_view = QTextEdit()
        self.tlv_detail_view.setReadOnly(True)
        self.tlv_detail_view.setMaximumHeight(100)
        self.tlv_detail_view.setFont(self.get_monospace_font())
        self.tlv_detail_view.setPlaceholderText("Click on a TLV row to see the full value here...")
        self.tlv_detail_view.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.tlv_detail_view)
        
        return analyze_widget

    def create_tls_tab(self) -> QWidget:
        """Create the TLS Flow tab to display per-session TLS handshake/PKI flow."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QTabWidget, QTreeWidget, QHeaderView
        tls_widget = QWidget()
        layout = QVBoxLayout(tls_widget)

        self.tls_summary_label = QLabel("Select a session to analyze TLS flow")
        self.tls_summary_label.setStyleSheet(
            """
            QLabel {
                font-weight: bold;
                padding: 5px;
                background-color: #f0f7ff;
                border: 1px solid #b3d7ff;
                border-radius: 3px;
            }
            """
        )
        layout.addWidget(self.tls_summary_label)

        # Sub-tabs within TLS Flow: Messages (grouped), Overview (merged Summary+Handshake), Security (ladder+certs)
        self.tls_subtabs = QTabWidget()

        # Messages tab (with phase grouping: Handshake/Data/Closure)
        messages_tab = QWidget(); messages_layout = QVBoxLayout(messages_tab)
        self.tls_tree = QTreeWidget()
        self.tls_tree.setHeaderLabels(["Phase/Message", "Direction", "Details", "Timestamp"])
        header = self.tls_tree.header()
        header.setStretchLastSection(False)
        header.resizeSection(0, 220)  # Phase/Message name
        header.resizeSection(1, 100)  # Direction with arrows
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Details stretch
        header.resizeSection(3, 140)  # Timestamp
        self.tls_tree.setAlternatingRowColors(True)
        self.tls_tree.setRootIsDecorated(True)  # Enable expand/collapse for phases
        self.tls_tree.setStyleSheet(
            """
            QTreeWidget {
                outline: 0;
                border: 1px solid #c0c0c0;
                selection-background-color: #3399ff;
                font-size: 12px;
            }
            QTreeWidget::item { 
                padding: 4px 2px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected { 
                background: #3399ff; 
                color: white; 
            }
            QTreeWidget::item:hover {
                background: #e3f2fd;
            }
            """
        )
        messages_layout.addWidget(self.tls_tree)
        # Inline preview card for selected step
        self.tls_step_preview = QLabel("")
        self.tls_step_preview.setStyleSheet(
            """
            QLabel { color:#333; padding:6px; border:1px solid #ddd; border-radius:4px; background:#fafafa; }
            """
        )
        self.tls_step_preview.setWordWrap(True)
        messages_layout.addWidget(self.tls_step_preview)
        self.tls_subtabs.addTab(messages_tab, "Messages")

        # Overview tab (merged Summary + Handshake - no duplication)
        overview_tab = QWidget(); overview_layout = QVBoxLayout(overview_tab)
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextBrowser
        overview_actions = QHBoxLayout()
        self.btn_copy_overview = QPushButton("Copy Overview")
        self.btn_export_overview = QPushButton("Export Markdown")
        overview_actions.addWidget(self.btn_copy_overview)
        overview_actions.addWidget(self.btn_export_overview)
        overview_actions.addStretch(1)
        overview_layout.addLayout(overview_actions)
        self.tls_overview_view = QTextBrowser()
        self.tls_overview_view.setOpenLinks(False)
        try:
            self.tls_overview_view.anchorClicked.connect(self._on_summary_anchor_clicked)
        except Exception:
            pass
        self.tls_overview_view.setStyleSheet("color: #333; padding: 4px;")
        self._install_copy_menu_for_text_widget(self.tls_overview_view)
        overview_layout.addWidget(self.tls_overview_view)
        self.tls_subtabs.addTab(overview_tab, "Overview")

        # Security tab (ladder diagram, certificates, cipher analysis, raw APDUs)
        security_tab = QWidget(); security_layout = QVBoxLayout(security_tab)
        from PySide6.QtWidgets import QHBoxLayout, QSpinBox, QCheckBox, QTextBrowser
        security_actions = QHBoxLayout()
        self.btn_copy_security = QPushButton("Copy Security Info")
        self.raw_context_toggle = QCheckBox("Show ±N APDUs around selection")
        self.raw_context_window = QSpinBox(); self.raw_context_window.setRange(1, 200); self.raw_context_window.setValue(20)
        security_actions.addWidget(self.btn_copy_security)
        security_actions.addStretch(1)
        security_actions.addWidget(self.raw_context_toggle)
        security_actions.addWidget(QLabel("N:"))
        security_actions.addWidget(self.raw_context_window)
        security_layout.addLayout(security_actions)
        self.tls_security_view = QTextBrowser()
        self.tls_security_view.setOpenLinks(False)
        try:
            self.tls_security_view.setFont(self.get_monospace_font())
        except Exception:
            pass
        self.tls_security_view.setStyleSheet("color: #333; padding: 4px; font-family: monospace;")
        self._install_copy_menu_for_text_widget(self.tls_security_view)
        security_layout.addWidget(self.tls_security_view)
        self.tls_subtabs.addTab(security_tab, "Security")

        layout.addWidget(self.tls_subtabs)

        return tls_widget

    # --- Flow Overview: timeline population and interactions ---
    def populate_flow_timeline(self, parser: XTIParser):
        """Compose unified timeline of channel sessions and key events."""
        items = []
        groups = parser.get_channel_groups()
        for gi, group in enumerate(groups):
            label = group.get("server", "Unknown")
            if isinstance(label, str) and label.strip().lower() == "google dns":
                label = "DNS"
            if (group.get("type", "").strip().lower() == "open channel"):
                label = "BIP Session"
            opened = group.get("opened_at", "")
            closed = group.get("closed_at", "Not closed")
            duration = group.get("duration", "Unknown")
            port = str(group.get("port", "")) if group.get("port") else ""
            protocol = group.get("protocol", "")
            role = group.get("role", "Unknown")
            server = group.get("server", "")
            if isinstance(server, str) and server.strip().lower() == "google dns":
                server = "DNS"
            ips = group.get("ips", [])
            session_indexes: List[int] = []
            first_idx = None
            for session in group.get("sessions", []):
                if session.traceitem_indexes:
                    if first_idx is None:
                        first_idx = session.traceitem_indexes[0]
                session_indexes.extend(session.traceitem_indexes)
            session_indexes = sorted(set(session_indexes))
            sort_key = opened
            try:
                if first_idx is not None:
                    ti = parser.trace_items[first_idx]
                    sort_key = ti.timestamp or opened
            except Exception:
                pass
            items.append({
                "kind": "Session",
                "label": f"{label}",
                "time": opened,
                "port": port,
                "protocol": protocol,
                "role": role,
                "server": server,
                "ips": ips,
                "opened": opened,
                "closed": closed,
                "duration": duration,
                "session_indexes": session_indexes,
                "group_index": gi,
                "sort_key": sort_key,
            })
        # Basic key events (optional, lightweight)
        for idx, item in enumerate(parser.trace_items):
            s = (item.summary or "").lower()
            t = item.timestamp or ""
            ev = None
            iccid_val = None
            chan_id = None
            # Also inspect details tree text for event phrases and fields
            def _flatten_details(node) -> str:
                try:
                    parts = []
                    def rec(n):
                        if not n:
                            return
                        name = getattr(n, 'name', '') or ''
                        val = getattr(n, 'value', '') or ''
                        content = getattr(n, 'content', '') or ''
                        if name or val:
                            parts.append(f"{name}: {val}")
                        if content:
                            parts.append(content)
                        for ch in getattr(n, 'children', []) or []:
                            rec(ch)
                    rec(node)
                    return "\n".join([p for p in parts if p]).lower()
                except Exception:
                    return ""
            d = _flatten_details(getattr(item, 'details_tree', None))
            # Try to extract Channel Identifier from details
            try:
                import re
                m_id = re.search(r"identifier:\s*(\d+)", d)
                if m_id:
                    chan_id = m_id.group(1)
            except Exception:
                chan_id = None
            if "refresh" in s:
                ev = "Refresh"
            elif "cold reset" in s:
                ev = "Cold Reset"
            elif ("link dropped" in s) or ("channel status" in s and ("link off" in s or "pdp not activated" in s)) or ("status:" in d and ("link dropped" in d or "link off" in d)):
                ev = "Link Dropped"
            elif "iccid" in s or "integrated circuit card identifier" in s:
                ev = "ICCID"
                try:
                    iccid_val = self._get_detected_iccid_from_validation() or self._find_iccid_value_around(parser, idx)
                except Exception:
                    iccid_val = None
            # Detect Bearer Independent Protocol errors (TR Result: BIP error)
            if not ev and ("bearer independent protocol error" in s or "bip error" in s or ("general result:" in d and "bearer independent protocol error" in d)):
                # Try to extract cause code from raw hex if present: (03|83) 02 3A xx
                cause = None
                try:
                    raw_hex = (item.rawhex or "").replace(" ", "").upper()
                    import re
                    m = re.search(r"(?:03|83)023A([0-9A-F]{2})", raw_hex)
                    if m:
                        cause = m.group(1)
                except Exception:
                    cause = None
                ev = f"BIP Error: 0x{cause}" if cause else "BIP Error"
            if ev:
                items.append({
                    "kind": "Event",
                    "label": f"{ev}: {iccid_val}" if (ev == "ICCID" and iccid_val) else f"{ev}",
                    "time": t,
                    "index": idx,
                    "sort_key": t,
                })
        self.timeline_model.set_timeline(items)

    def on_timeline_clicked(self, index):
        """Single-click: intentionally no action; double-click drives filtering/navigation."""
        return

    def on_timeline_double_clicked(self, index):
        """Handle double-click: if session, open TLS Flow tab with reconstructed TLS sequence."""
        if not index.isValid():
            return
        try:
            src_index = self.timeline_proxy.mapToSource(index)
        except Exception:
            src_index = index
        src_index0 = src_index.sibling(src_index.row(), 0)
        data = self.timeline_model.data(src_index0, Qt.UserRole)
        if not data:
            return
        if data.get("kind") == "Session":
            # Double-click cancels any pending single-click 'hello' override
            try:
                if self._timelineClickTimer.isActive():
                    self._timelineClickTimer.stop()
                self._pending_tac_session_data = None
                # Record time to suppress stale single-clicks
                self._last_timeline_double_click_ms = QTime.currentTime().msecsSinceStartOfDay()
            except Exception:
                pass
            # Apply session filter on double-click (moved from single-click)
            try:
                idxs = data.get("session_indexes", []) or []
                if idxs:
                    self.filter_model.clear_all_filters()
                    self.filter_model.set_session_filter(idxs)
                    self.clear_filter_button.setVisible(True)
                    self.clear_filter_button.setText(f"Clear filter (Group: {data.get('label','Session')})")
                    self.tab_widget.setCurrentIndex(0)
            except Exception:
                pass
            try:
                if self._is_tac_session(data):
                    msg = f"[TLSFlow] TAC double-click detected: label={data.get('label')} server={data.get('server')}"
                    print(msg, flush=True)
                    try:
                        self.statusBar().showMessage(msg, 3000)
                    except Exception:
                        pass
                    # Also dump a compact TLS summary to console (no popup)
                    try:
                        self._debug_tls_session_summary(data, show_popup=False)
                    except Exception:
                        pass
            except Exception:
                pass
            # Clear any placeholder and set loading messages before populating
            try:
                if hasattr(self, 'tls_tree'):
                    self.tls_tree.clear()
                if hasattr(self, 'tls_overview_view'):
                    self.tls_overview_view.setText('Parsing TLS…')
                if hasattr(self, 'tls_security_view'):
                    self.tls_security_view.setText('Parsing…')
            except Exception:
                pass
            self.show_tls_flow_for_session(data)
            try:
                self.hex_tab_widget.setCurrentIndex(2)
            except Exception:
                pass
        else:
            # Double-click on Event: perform navigation
            try:
                src_index = self.timeline_proxy.mapToSource(index)
            except Exception:
                src_index = index
            try:
                src_index0 = src_index.sibling(src_index.row(), 0)
            except Exception:
                src_index0 = src_index
            data = self.timeline_model.data(src_index0, Qt.UserRole)
            if not data:
                return
            src_row = data.get("index")
            if src_row is not None and hasattr(self, 'parser') and self.parser:
                try:
                    target_item = self.parser.trace_items[src_row]
                except Exception:
                    target_item = None
                self.tab_widget.setCurrentIndex(0)
                if target_item is not None:
                    QTimer.singleShot(0, lambda ti=target_item: self._navigate_to_item_fast(ti))
                else:
                    QTimer.singleShot(0, lambda r=src_row: self._complete_navigation(r))

    def _do_tac_single_click_effects(self):
        """Deferred single-click effects so double-click can cancel them."""
        try:
            data = self._pending_tac_session_data
            self._pending_tac_session_data = None
            # Suppress if a double-click just happened recently
            try:
                now_ms = QTime.currentTime().msecsSinceStartOfDay()
                if now_ms - getattr(self, '_last_timeline_double_click_ms', 0) < 1000:
                    return
            except Exception:
                pass
            if data and self._is_tac_session(data):
                # Unified pipeline: always use internal decoding/basic scan.
                populated = False
                # Also run a quick TLS scan and show console + popup to prove detection
                try:
                    print("[TLSFlow] TAC single-click scan starting…", flush=True)
                    self._debug_tls_session_summary(data, show_popup=True)
                except Exception:
                    pass
                # Try populating the TLS Flow tabs from the basic scan immediately
                try:
                    populated = self._populate_tls_from_basic_scan(data)
                except Exception:
                    populated = False
                if not populated:
                    self._show_hello_in_tls_tabs()
        except Exception:
            pass

    def _populate_tls_from_basic_scan(self, session_data: dict) -> bool:
        """Populate TLS Flow tabs using the lightweight TLS record scan.
        Returns True if any TLS events were rendered, else False.
        """
        try:
            idxs = session_data.get('session_indexes', []) or []
            server = session_data.get('server') or session_data.get('label') or 'Unknown'
            port = session_data.get('port') or ''
            protocol = session_data.get('protocol') or ''
            ips = session_data.get('ips') or []
            opened = session_data.get('opened', '')
            closed = session_data.get('closed', '')
            duration = session_data.get('duration', '')
            ip_text = ", ".join(ips) if isinstance(ips, list) else str(ips)
            from .apdu_parser_construct import parse_apdu
        except Exception:
            return False

        segments = []
        for i in idxs:
            try:
                ti = self.parser.trace_items[i]
                parsed = parse_apdu(ti.rawhex) if getattr(ti, 'rawhex', None) else None
                if parsed and self._is_send_receive_data(parsed, ti):
                    payload = self._extract_payload_from_tlv(parsed)
                    if isinstance(payload, (bytes, bytearray)) and len(payload) >= 5:
                        segments.append({'data': bytes(payload), 'dir': getattr(parsed, 'direction', '') or '', 'ts': getattr(ti, 'timestamp','') or ''})
            except Exception:
                continue
        if not segments:
            return False

        try:
            events, hs_types, negotiated = self._basic_tls_detect_segments(segments)
        except Exception:
            return False
        if not events:
            return False

        # Normalize vendor-specific alert labels across all paths
        try:
            for ev in events:
                txt = ev.get('detail','') or ''
                if txt.startswith('TLS Alert:'):
                    # Replace known vendor patterns with friendly labels
                    if 'level_151' in txt and 'alert_82' in txt:
                        ev['detail'] = txt.replace('level_151', 'warning_vendor').replace('alert_82', 'close_notify')
        except Exception:
            pass

        # Clear placeholders and populate
        try:
            self.tls_tree.clear()
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QTreeWidgetItem
            for ev in events[:500]:  # safety guard
                item = QTreeWidgetItem(self.tls_tree)
                item.setText(0, 'TLS')
                item.setText(1, ev.get('dir',''))
                item.setText(2, ev.get('detail',''))
                item.setText(3, ev.get('ts',''))
            # Add a consolidated Summary row similar to the report, if we can enrich
            try:
                enrich = self._try_enrich_from_existing_report()
            except Exception:
                enrich = {}
            summary_bits = []
            if enrich.get('sni'):
                summary_bits.append(f"SNI: {enrich['sni']}")
            if negotiated:
                summary_bits.append(f"Version: {negotiated}")
            # Offered ciphers (from report ClientHello line) or chosen cipher as fallback
            ciphers_text = None
            try:
                # Parse first few offered cipher names from report
                from pathlib import Path
                import re
                base_dir = Path(self.current_file_path).parent if getattr(self, 'current_file_path', None) else Path.cwd()
                for name in ("tac_session_report.md", "tac_session_raw.md"):
                    p = base_dir / name
                    if p.exists():
                        txt = p.read_text(encoding='utf-8', errors='ignore')
                        m = re.search(r"cipher_suites:\s*([^\n]+)", txt)
                        if m:
                            offered = [s.strip() for s in m.group(1).split(',') if s.strip()]
                            if offered:
                                ciphers_text = ", ".join(offered[:4])
                                break
                if not ciphers_text and enrich.get('chosen_cipher'):
                    ciphers_text = enrich['chosen_cipher']
            except Exception:
                pass
            if ciphers_text:
                summary_bits.append(f"Ciphers: {ciphers_text}")
            if summary_bits:
                item = QTreeWidgetItem(self.tls_tree)
                item.setText(0, 'Summary')
                item.setText(1, '')
                item.setText(2, ' | '.join(summary_bits))
                item.setText(3, '')
        except Exception:
            pass

        # Update summary/handshake/raw
        try:
            if hasattr(self, 'tls_summary_label'):
                self.tls_summary_label.setText(
                    f"Session: {server}  |  Protocol: {protocol}  |  Port: {port}  |  IP: {ip_text}  |  {opened} → {closed}  ({duration})"
                )
            if hasattr(self, 'tls_overview_view'):
                # Try to enrich from existing markdown report (SNI, chosen cipher, certificates)
                enrich = {}
                try:
                    enrich = self._try_enrich_from_existing_report()
                except Exception:
                    pass
                
                # Modern card-based HTML rendering with compact spacing
                html_parts = []
                html_parts.append("""
                <style>
                body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 6px; }
                .card { background: white; border-radius: 4px; padding: 6px; margin-bottom: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.08); }
                .card-header { font-size: 12px; font-weight: 600; color: #1976d2; margin-bottom: 4px; border-bottom: 1px solid #e3f2fd; padding-bottom: 2px; }
                .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 4px; margin-top: 4px; }
                .stat-item { padding: 4px 6px; background: #f8f9fa; border-radius: 3px; border-left: 2px solid #2196F3; }
                .stat-label { font-size: 9px; color: #666; text-transform: uppercase; letter-spacing: 0.3px; margin-bottom: 1px; }
                .stat-value { font-size: 12px; font-weight: 600; color: #212529; }
                .badge { display: inline-block; padding: 1px 5px; border-radius: 2px; font-size: 9px; font-weight: 600; margin-right: 3px; }
                .badge-success { background: #d4edda; color: #2e7d32; }
                .badge-info { background: #d1ecf1; color: #0c5460; }
                .badge-warning { background: #fff3cd; color: #856404; }
                .info-row { margin: 2px 0; font-size: 11px; }
                .info-label { color: #666; display: inline-block; min-width: 80px; }
                .info-value { color: #212529; font-weight: 500; }
                </style>
                """)
                
                # Session Overview Card
                html_parts.append('<div class="card">')
                html_parts.append('<div class="card-header">📋 Session Overview</div>')
                html_parts.append('<div class="stat-grid">')
                html_parts.append(f'<div class="stat-item"><div class="stat-label">Protocol</div><div class="stat-value">{protocol or "TCP"}</div></div>')
                html_parts.append(f'<div class="stat-item"><div class="stat-label">Port</div><div class="stat-value">{port or "443"}</div></div>')
                html_parts.append(f'<div class="stat-item"><div class="stat-label">Duration</div><div class="stat-value">{duration or "N/A"}</div></div>')
                html_parts.append(f'<div class="stat-item"><div class="stat-label">Total Events</div><div class="stat-value">{len(events)}</div></div>')
                html_parts.append('</div>')
                if server or ip_text or enrich.get('sni'):
                    html_parts.append('<div style="margin-top: 4px;">')
                    if server:
                        html_parts.append(f'<div class="info-row"><span class="info-label">Server:</span> <span class="info-value">{server}</span></div>')
                    if ip_text:
                        html_parts.append(f'<div class="info-row"><span class="info-label">IP:</span> <span class="info-value">{ip_text}</span></div>')
                    if enrich.get('sni'):
                        html_parts.append(f'<div class="info-row"><span class="info-label">SNI:</span> <span class="info-value">{enrich["sni"]}</span></div>')
                    html_parts.append('</div>')
                html_parts.append('</div>')
                
                # Security Configuration Card
                if negotiated or enrich.get('chosen_cipher'):
                    html_parts.append('<div class="card">')
                    html_parts.append('<div class="card-header">🔒 Security Configuration</div>')
                    if negotiated:
                        html_parts.append(f'<div class="info-row"><span class="info-label">Version:</span> <span class="info-value">{negotiated}</span></div>')
                    if enrich.get('chosen_cipher'):
                        cipher = enrich['chosen_cipher']
                        html_parts.append(f'<div class="info-row"><span class="info-label">Cipher:</span> <span class="info-value">{cipher}</span></div>')
                        html_parts.append('<div style="margin-top: 3px;">')
                        if 'ECDHE' in cipher or 'DHE' in cipher:
                            html_parts.append('<span class="badge badge-success">✓ PFS</span>')
                        if 'GCM' in cipher or 'CCM' in cipher or 'CHACHA20' in cipher:
                            html_parts.append('<span class="badge badge-success">✓ AEAD</span>')
                        if '256' in cipher:
                            html_parts.append('<span class="badge badge-info">256-bit</span>')
                        elif '128' in cipher:
                            html_parts.append('<span class="badge badge-warning">128-bit</span>')
                        html_parts.append('</div>')
                    html_parts.append('</div>')
                
                # Message Statistics Card
                handshake_count = sum(1 for e in events if 'Handshake' in e.get('detail', ''))
                data_count = sum(1 for e in events if 'Application Data' in e.get('detail', ''))
                alert_count = sum(1 for e in events if 'Alert' in e.get('detail', ''))
                
                html_parts.append('<div class="card">')
                html_parts.append('<div class="card-header">📊 Message Statistics</div>')
                html_parts.append('<div class="stat-grid">')
                html_parts.append(f'<div class="stat-item"><div class="stat-label">Handshake</div><div class="stat-value" style="color: #1976d2;">{handshake_count}</div></div>')
                html_parts.append(f'<div class="stat-item"><div class="stat-label">Application Data</div><div class="stat-value" style="color: #388e3c;">{data_count}</div></div>')
                html_parts.append(f'<div class="stat-item"><div class="stat-label">Alerts</div><div class="stat-value" style="color: #d32f2f;">{alert_count}</div></div>')
                html_parts.append('</div>')
                html_parts.append('</div>')
                
                # Handshake Flow Card
                if hs_types:
                    html_parts.append('<div class="card">')
                    html_parts.append('<div class="card-header">🤝 Handshake Flow</div>')
                    html_parts.append('<div style="margin-top: 3px;">')
                    for hs_type in sorted(set(hs_types)):
                        html_parts.append(f'<span class="badge badge-info">{hs_type}</span>')
                    html_parts.append('</div>')
                    html_parts.append('</div>')
                
                self.tls_overview_view.setHtml(''.join(html_parts))
            # Note: Handshake details now in Overview tab, Security tab has ladder+certificates
            # Old widgets (tls_handshake_label, tls_ladder_label, tls_raw_text) deprecated
        except Exception:
            pass

        # Export Markdown report next to the capture
        try:
            self._export_tls_markdown(session_data, events, hs_types, negotiated)
        except Exception:
            pass

        # Switch UI focus to TLS Flow
        try:
            self.hex_tab_widget.setCurrentIndex(2)
            if hasattr(self, 'tls_subtabs'):
                self.tls_subtabs.setCurrentIndex(0)
        except Exception:
            pass
        return True

    def _try_enrich_from_existing_report(self) -> dict:
        """Best-effort parse of tac_session_report.md or tac_session_raw.md to extract
        SNI, chosen cipher, certificate count, and handshake sequence.
        """
        result = {}
        try:
            from pathlib import Path
            import re
            base_dir = Path(self.current_file_path).parent if getattr(self, 'current_file_path', None) else Path.cwd()
            for name in ("tac_session_report.md", "tac_session_raw.md"):
                p = base_dir / name
                if p.exists():
                    text = p.read_text(encoding='utf-8', errors='ignore')
                    # SNI
                    m = re.search(r"SNI:\s*([^\n]+)", text)
                    if m:
                        result['sni'] = m.group(1).strip()
                    # Chosen Cipher
                    m = re.search(r"Chosen Cipher:\s*([^\n]+)", text)
                    if m:
                        result['chosen_cipher'] = m.group(1).strip()
                    # Certificates count
                    m = re.search(r"Certificates:\s*(\d+)", text)
                    if m:
                        try:
                            result['cert_count'] = int(m.group(1))
                        except Exception:
                            pass
                    # Handshake reconstruction sequence
                    seq_match = re.search(r"Full TLS Handshake Reconstruction\s*\n-\s*(.+)", text)
                    if seq_match:
                        seq_line = seq_match.group(1)
                        # Sequence is like: OPEN CHANNEL → ClientHello → ... → CLOSE CHANNEL
                        parts = [s.strip() for s in re.split(r"→|->|—|—>", seq_line) if s.strip()]
                        if parts:
                            result['handshake_sequence'] = parts
                    break
        except Exception:
            pass
        return result

    def _export_tls_markdown(self, session_data: dict, events: list, hs_types: list, negotiated: str | None, out_path: str | None = None):
        """Write a compact Markdown report of the quick TLS scan."""
        try:
            from pathlib import Path
            server = session_data.get('server') or session_data.get('label') or 'Unknown'
            port = session_data.get('port') or ''
            protocol = session_data.get('protocol') or ''
            ips = session_data.get('ips') or []
            opened = session_data.get('opened', '')
            closed = session_data.get('closed', '')
            duration = session_data.get('duration', '')
            ip_text = ", ".join(ips) if isinstance(ips, list) else str(ips)
            base_dir = Path(self.current_file_path).parent if getattr(self, 'current_file_path', None) else Path.cwd()
            path = Path(out_path) if out_path else base_dir / 'tac_session_raw.md'
            lines = []
            lines.append(f"# TAC Session TLS Summary\n")
            lines.append(f"- Server: {server}")
            lines.append(f"- Protocol: {protocol}")
            lines.append(f"- Port: {port}")
            lines.append(f"- IPs: {ip_text}")
            lines.append(f"- Opened: {opened}")
            lines.append(f"- Closed: {closed}")
            lines.append(f"- Duration: {duration}")
            if negotiated:
                lines.append(f"- Version: {negotiated}")
            if hs_types:
                lines.append(f"- Handshakes: {', '.join(sorted(set(hs_types)))}")
            lines.append("")
            lines.append("## Events")
            lines.append("")
            lines.append("Time | Direction | Detail")
            lines.append("--- | --- | ---")
            for ev in events:
                lines.append(f"{ev.get('ts','')} | {ev.get('dir','')} | {ev.get('detail','')}")
            content = "\n".join(lines) + "\n"
            path.write_text(content, encoding='utf-8')
            print(f"[TLSFlow] Markdown exported: {path}", flush=True)
            try:
                self.statusBar().showMessage(f"Markdown exported: {path.name}", 3000)
            except Exception:
                pass
        except Exception:
            pass

    def _debug_tls_session_summary(self, session_data: dict, show_popup: bool = False):
        """Dump a compact TLS scan to console and optional non-modal popup.
        Useful when UI placeholders hide results.
        """
        try:
            idxs = session_data.get('session_indexes', []) or []
            server = session_data.get('server') or session_data.get('label') or 'Unknown'
            port = session_data.get('port') or ''
            protocol = session_data.get('protocol') or ''
            segments = []
            from .apdu_parser_construct import parse_apdu
        except Exception:
            segments = []
            parse_apdu = None
        for i in idxs:
            try:
                ti = self.parser.trace_items[i]
                parsed = parse_apdu(ti.rawhex) if parse_apdu and getattr(ti, 'rawhex', None) else None
                if parsed and self._is_send_receive_data(parsed, ti):
                    payload = self._extract_payload_from_tlv(parsed)
                    if isinstance(payload, (bytes, bytearray)) and len(payload) >= 5:
                        segments.append({'data': bytes(payload), 'dir': getattr(parsed, 'direction', '') or '', 'ts': getattr(ti, 'timestamp','') or ''})
            except Exception:
                continue
        header = f"[TLSFlow] Quick scan: server={server} proto={protocol} port={port} segments={len(segments)}"
        print(header, flush=True)
        details = []
        full_recon_line = None
        if segments:
            try:
                events, hs_types, negotiated = self._basic_tls_detect_segments(segments)
                for ev in events[:20]:
                    details.append(f" - {ev.get('ts','')} {ev.get('dir','')}: {ev.get('detail','')}")
                if not events:
                    details.append(" - No TLS records found")
                if hs_types:
                    details.append("Handshake(s): " + ", ".join(sorted(set(hs_types))))
                if negotiated:
                    details.append("Version: " + negotiated)
                # Build a single-line Full TLS Handshake Reconstruction from detected events
                try:
                    tokens = []
                    for ev in events:
                        text = ev.get('detail','')
                        if text:
                            # keep only the leading label before any separators
                            lbl = text.split('•', 1)[0].strip()
                            # Normalize common labels
                            if lbl.startswith('TLS '):
                                lbl = lbl.replace('TLS ', '')
                            tokens.append(lbl)
                    if tokens:
                        # Insert OPEN/CLOSE if we saw any tokens at all
                        full_recon_line = "OPEN CHANNEL → " + " → ".join(tokens) + " → CLOSE CHANNEL"
                        details.append("Full TLS Handshake Reconstruction: " + full_recon_line)
                except Exception:
                    pass
            except Exception as e:
                details.append(f" - Scanner error: {e}")
        else:
            details.append(" - No SEND/RECEIVE segments with payload ≥5 bytes")
        for line in details:
            print(line, flush=True)

        if show_popup:
            try:
                from PySide6.QtWidgets import QMessageBox
                # Keep a reference so it stays visible
                if hasattr(self, '_tls_quick_scan_popup') and self._tls_quick_scan_popup is not None:
                    try:
                        self._tls_quick_scan_popup.close()
                    except Exception:
                        pass
                msg = QMessageBox(self)
                msg.setWindowTitle("TLS Flow Quick Scan")
                msg.setText("\n".join([header] + details[:15]))
                msg.setIcon(QMessageBox.Information)
                msg.setModal(False)
                msg.show()
                self._tls_quick_scan_popup = msg
            except Exception:
                pass

    def _reset_tls_flow_placeholders(self, session_data: dict | None = None):
        """Prepare TLS Flow subtabs with placeholder texts on single-click.
        Steps: empty. Summary: 'waiting for session'. Handshake: 'no handshake parsed yet'.
        Ladder: 'ladder view coming soon'. Raw: 'raw session info ...'.
        """
        try:
            if hasattr(self, 'tls_summary_label') and self.tls_summary_label:
                self.tls_summary_label.setText("Select a session to analyze TLS flow")
        except Exception:
            pass
        try:
            if hasattr(self, 'tls_tree') and self.tls_tree:
                self.tls_tree.clear()
        except Exception:
            pass
        try:
            if hasattr(self, 'tls_overview_view'):
                self.tls_overview_view.setText("waiting for session")
        except Exception:
            pass
        try:
            if hasattr(self, 'tls_security_view'):
                try:
                    self.tls_security_view.setHtml("Select a session to view security details")
                except Exception:
                    self.tls_security_view.setText("Select a session to view security details")

        except Exception:
            pass
        # Note: Raw session info now displayed in Security tab

    def _is_tac_session(self, session_data: dict) -> bool:
        """Heuristic: consider session TAC if server/label contains 'tac' (case-insensitive)."""
        try:
            for key in ("server", "label"):
                val = session_data.get(key)
                if isinstance(val, str) and "tac" in val.lower():
                    return True
        except Exception:
            pass
        return False

    def _show_hello_in_tls_tabs(self):
        """Populate all TLS Flow sub-tabs with an unmistakable 'hello' using varied methods."""
        try:
            from PySide6.QtWidgets import QTreeWidgetItem
            if not hasattr(self, 'tls_tree') or self.tls_tree is None:
                return
            # Only act if nothing is rendered yet (avoid overwriting TLS results)
            if self.tls_tree.topLevelItemCount() > 0:
                return
            # Fill other tabs first using different presentation methods
            try:
                if hasattr(self, 'tls_overview_view'):
                    self.tls_overview_view.setText('hello overview')
            except Exception:
                pass
            try:
                if hasattr(self, 'tls_security_view'):
                    self.tls_security_view.setText('hello security')
            except Exception:
                pass
            # Finally add a row to the Steps tree
            try:
                item = QTreeWidgetItem(self.tls_tree)
                item.setText(0, 'HELLO')
                item.setText(1, '')
                item.setText(2, 'hello')
                item.setText(3, '')
            except Exception:
                pass
        except Exception:
            pass

    def show_tls_flow_for_session(self, session_data: dict):
        """Aggregate and display TLS/PKI flow for a session (OPEN→TLS→CLOSE)."""
        if not hasattr(self, 'parser') or not self.parser:
            return
        # Store for summary re-render (collapsible toggles)
        try:
            self._current_session_data = session_data
        except Exception:
            pass
        idxs = session_data.get('session_indexes', []) or []
        if not idxs:
            self.tls_summary_label.setText("No items in session")
            self.tls_tree.clear()
            return

        server = session_data.get('server') or session_data.get('label') or 'Unknown'
        port = session_data.get('port') or ''
        protocol = session_data.get('protocol') or ''
        ips = session_data.get('ips') or []
        opened = session_data.get('opened', '')
        closed = session_data.get('closed', '')
        duration = session_data.get('duration', '')
        ip_text = ", ".join(ips) if isinstance(ips, list) else str(ips)
        self.tls_summary_label.setText(
            f"Session: {server}  |  Protocol: {protocol}  |  Port: {port}  |  IP: {ip_text}  |  {opened} → {closed}  ({duration})"
        )

        self.tls_tree.clear()
        # Reset subtab placeholders
        try:
            self.tls_overview_view.setText("Loading…")
            self.tls_security_view.setText("Loading security info…")
        except Exception:
            pass

        # Internal marker for tests/debug
        try:
            self._tls_flow_render_mode = 'unified'
        except Exception:
            pass

        try:
            from .apdu_parser_construct import parse_apdu
            from .protocol_analyzer import ProtocolAnalyzer
        except Exception:
            try:
                from PySide6.QtWidgets import QTreeWidgetItem
                msg_item = QTreeWidgetItem(self.tls_tree)
                msg_item.setText(0, 'Info')
                msg_item.setText(1, '')
                msg_item.setText(2, 'TLS analyzer unavailable in this build')
                msg_item.setText(3, '')
            except Exception:
                pass
            return

        from PySide6.QtWidgets import QTreeWidgetItem

        def _norm_dir(d: str) -> str:
            try:
                s = (d or '').strip()
                s = s.replace('->', '→')
                s = s.replace('→', ' → ')
                while '  ' in s:
                    s = s.replace('  ', ' ')
                return s.strip()
            except Exception:
                return (d or '').strip()

        # Quick-scan UI: render like report-mode (phase groups)
        handshake_phase = data_phase = closure_phase = None
        phase_counts = {'handshake': 0, 'data': 0, 'closure': 0}
        try:
            from PySide6.QtGui import QFont
            handshake_phase = QTreeWidgetItem(self.tls_tree, ["🔐 Handshake Phase", "", "", ""])
            data_phase = QTreeWidgetItem(self.tls_tree, ["📦 Data Transfer Phase", "", "", ""])
            closure_phase = QTreeWidgetItem(self.tls_tree, ["🔒 Closure Phase", "", "", ""])
            for phase in (handshake_phase, data_phase, closure_phase):
                font = phase.font(0)
                font.setBold(True)
                font.setPointSize(font.pointSize() + 1)
                phase.setFont(0, font)
        except Exception:
            handshake_phase = data_phase = closure_phase = None

        def _phase_parent(step: str, detail: str) -> QTreeWidgetItem | None:
            if handshake_phase is None or data_phase is None or closure_phase is None:
                return None
            s = (step or '').lower()
            d = (detail or '').lower()
            # Alerts: keep out of closure phase
            if s.startswith('alert') or 'alert' in s or d.startswith('tls alert') or d.startswith('alert'):
                phase_counts['data'] += 1
                return data_phase
            # Closure: only actual channel/session close markers
            if ('close' in s and 'channel' in s) or ('close channel' in d):
                phase_counts['closure'] += 1
                return closure_phase
            # Data
            if 'application' in s or d.startswith('applicationdata') or 'applicationdata' in d:
                phase_counts['data'] += 1
                return data_phase
            # Handshake + session control + PKI
            phase_counts['handshake'] += 1
            return handshake_phase

        def add_row(step: str, direction: str, detail: str, ts: str, parent: QTreeWidgetItem | None = None):
            item = QTreeWidgetItem(parent if parent is not None else self.tls_tree)
            
            # Add visual arrows to direction
            direction = _norm_dir(direction)
            if direction and 'SIM' in direction and 'ME' in direction:
                if direction.replace(' ', '').startswith('SIM'):
                    direction = 'SIM \u2192 ME'
                elif direction.replace(' ', '').startswith('ME'):
                    direction = 'ME \u2192 SIM'
            
            # Show actual message name, not generic badge
            item.setText(0, step)
            item.setText(1, direction)
            
            # Truncate detail if too long
            MAX_DETAIL = 80
            if len(detail) > MAX_DETAIL:
                item.setToolTip(2, detail)
                detail = detail[:MAX_DETAIL] + '...'
            item.setText(2, detail)
            item.setText(3, ts or '')
            
            # Color code by message type
            try:
                from PySide6.QtGui import QBrush, QColor
                color = QColor('#888888')  # default
                
                # Handshake messages: blue
                if step in ('ClientHello', 'ServerHello', 'Certificate', 'ServerKeyExchange',
                           'ClientKeyExchange', 'ServerHelloDone', 'CertificateRequest'):
                    color = QColor('#2a7ed3')
                # Cipher spec and finished: orange
                elif step in ('ChangeCipherSpec', 'Encrypted Finished', 'Finished'):
                    color = QColor('#e08a00')
                # Alerts: red
                elif step.startswith('Alert') or 'alert' in step.lower():
                    color = QColor('#d32f2f')
                # Application data: dark gray
                elif step == 'ApplicationData' or 'application' in step.lower():
                    color = QColor('#666666')
                # Session control: green
                elif step in ('OPEN CHANNEL', 'CLOSE CHANNEL'):
                    color = QColor('#2e7d32')
                # Generic TLS: blue-gray
                elif step == 'TLS':
                    color = QColor('#607d8b')
                
                item.setForeground(0, QBrush(color))
                
                # Make key handshake messages bold
                if step in ('ClientHello', 'ServerHello', 'Certificate'):
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
            except Exception:
                pass
            return item

        seen_sni = None
        seen_cipher_offer = None
        seen_cipher_suites = []
        seen_chosen_cipher = None
        cert_count = 0
        negotiated_version = None
        handshake_types = []
        tls_rows_added = 0
        segments = []  # collect raw channel segments for basic fallback detection
        basic_events_cache = []
        basic_handshakes_cache = []
        basic_version_cache = None
        basic_meta_cache = {}
        pki_cns = []

        for i in idxs:
            if i < 0 or i >= len(self.parser.trace_items):
                continue
            ti = self.parser.trace_items[i]
            try:
                parsed = parse_apdu(ti.rawhex) if getattr(ti, 'rawhex', None) else None
            except Exception:
                parsed = None

            timestamp = getattr(ti, 'timestamp', '') or ''
            direction = getattr(parsed, 'direction', '') if parsed else ''
            ins_name = getattr(parsed, 'ins_name', '') if parsed else (ti.summary or '')

            name_upper = ins_name.upper()
            if 'OPEN CHANNEL' in name_upper:
                detail = ti.summary or 'OPEN CHANNEL'
                add_row('OPEN CHANNEL', direction, detail, timestamp, _phase_parent('OPEN CHANNEL', detail))
                continue
            if 'CLOSE CHANNEL' in name_upper:
                detail = ti.summary or 'CLOSE CHANNEL'
                add_row('CLOSE CHANNEL', direction, detail, timestamp, _phase_parent('CLOSE CHANNEL', detail))
                continue

            if parsed and self._is_send_receive_data(parsed, ti):
                payload = self._extract_payload_from_tlv(parsed)
                if not payload:
                    continue
                # Collect for fallback TLS record detection
                try:
                    if isinstance(payload, (bytes, bytearray)) and len(payload) >= 5:
                        segments.append({
                            'data': bytes(payload),
                            'dir': direction or '',
                            'ts': timestamp or ''
                        })
                except Exception:
                    pass
                try:
                    chan_info = {'port': port, 'protocol': protocol}
                    try:
                        analysis = ProtocolAnalyzer.analyze_payload(payload, chan_info)
                    except TypeError:
                        analysis = ProtocolAnalyzer.analyze_payload(payload)
                except Exception:
                    analysis = None

                if analysis and getattr(analysis, 'tls_info', None):
                    tls = analysis.tls_info
                    if getattr(tls, 'handshake_type', None):
                        # Keep details consistent with the basic TLS scanner output
                        # (e.g., 'ServerHello • TLS 1.2' instead of 'TLS ServerHello • TLS 1.2').
                        detail = f"{tls.handshake_type}"
                        handshake_types.append(str(tls.handshake_type))
                        if getattr(tls, 'version', None):
                            detail += f" • {tls.version}"
                            negotiated_version = negotiated_version or tls.version
                        if getattr(tls, 'sni_hostname', None) and not seen_sni:
                            seen_sni = tls.sni_hostname
                            detail += f" • SNI: {tls.sni_hostname}"
                        if (str(getattr(tls, 'handshake_type', '')) == 'ClientHello') and getattr(tls, 'cipher_suites', None):
                            if not seen_cipher_suites:
                                try:
                                    seen_cipher_suites = list(tls.cipher_suites or [])
                                except Exception:
                                    seen_cipher_suites = []
                            if not seen_cipher_offer:
                                try:
                                    seen_cipher_offer = f"{min(5, len(tls.cipher_suites))}/{len(tls.cipher_suites)} offered"
                                except Exception:
                                    seen_cipher_offer = f"{len(tls.cipher_suites)} offered"
                            detail += f" • Ciphers: {seen_cipher_offer}"
                        if (str(getattr(tls, 'handshake_type', '')) == 'ServerHello') and getattr(tls, 'chosen_cipher', None) and not seen_chosen_cipher:
                            try:
                                seen_chosen_cipher = str(tls.chosen_cipher)
                            except Exception:
                                seen_chosen_cipher = tls.chosen_cipher
                        step = str(getattr(tls, 'handshake_type', '') or 'TLS')
                        add_row(step, direction, detail, timestamp, _phase_parent(step, detail))
                        tls_rows_added += 1

                if analysis and getattr(analysis, 'certificates', None):
                    for c in analysis.certificates[:3]:
                        cert_count += 1
                        cn = getattr(c, 'subject_cn', '') or 'Certificate'
                        pki_detail = f"Certificate CN: {cn}"
                        add_row('PKI', direction, pki_detail, timestamp, _phase_parent('PKI', pki_detail))
                        try:
                            if cn and cn != 'Certificate':
                                pki_cns.append(str(cn))
                        except Exception:
                            pass

        # Enrich results with a lightweight built-in TLS record scan.
        # ProtocolAnalyzer may decode only a subset of messages depending on framing;
        # the basic scanner often recovers the full handshake/app-data/alert sequence.
        if segments:
            try:
                basic_events, basic_handshakes, basic_version = self._basic_tls_detect_segments(segments)
                basic_events_cache = list(basic_events or [])
                basic_handshakes_cache = list(basic_handshakes or [])
                basic_version_cache = basic_version

                # Enrich cipher negotiation from basic scan if ProtocolAnalyzer missed it.
                try:
                    meta = getattr(self, '_basic_tls_scan_meta', None) or {}
                    basic_meta_cache = dict(meta) if isinstance(meta, dict) else {}
                    if not seen_sni and meta.get('sni'):
                        seen_sni = str(meta.get('sni'))
                    if not seen_chosen_cipher and meta.get('chosen_cipher'):
                        seen_chosen_cipher = str(meta.get('chosen_cipher'))
                    if (not seen_cipher_suites) and meta.get('offered_ciphers'):
                        try:
                            seen_cipher_suites = list(meta.get('offered_ciphers') or [])
                        except Exception:
                            seen_cipher_suites = []
                    if not seen_cipher_offer and seen_cipher_suites:
                        seen_cipher_offer = f"{min(5, len(seen_cipher_suites))}/{len(seen_cipher_suites)} offered"
                except Exception:
                    pass

                # De-duplicate against already-rendered rows
                existing = set()
                try:
                    root = self.tls_tree.invisibleRootItem()
                    stack = []
                    for r in range(root.childCount()):
                        stack.append(root.child(r))
                    while stack:
                        it = stack.pop()
                        try:
                            d = _norm_dir((it.text(1) or '').strip())
                            detail = (it.text(2) or '').strip()
                            ts = (it.text(3) or '').strip()
                            if detail.startswith('TLS '):
                                detail = detail[4:].strip()
                            if d or detail or ts:
                                existing.add((d, detail, ts))
                        except Exception:
                            pass
                        try:
                            for c in range(it.childCount()):
                                stack.append(it.child(c))
                        except Exception:
                            pass
                except Exception:
                    existing = set()

                for ev in basic_events[:200]:  # guard against excessive rows
                    d = _norm_dir((ev.get('dir', '') or '').strip())
                    detail = (ev.get('detail', '') or '').strip()
                    ts = (ev.get('ts', '') or '').strip()
                    if detail.startswith('TLS '):
                        detail = detail[4:].strip()
                    key = (d, detail, ts)
                    if key in existing:
                        continue
                    step = (detail.split('•', 1)[0] if detail else 'TLS').strip()
                    if step.lower().startswith('tls '):
                        step = step[4:].strip()
                    if step.lower().startswith('alert:'):
                        step = 'Alert'
                    add_row(step or 'TLS', d, detail, ts, _phase_parent(step or 'TLS', detail))
                    tls_rows_added += 1
                    existing.add(key)
                if basic_handshakes:
                    handshake_types.extend(basic_handshakes)
                if basic_version and not negotiated_version:
                    negotiated_version = basic_version
            except Exception:
                pass

        summary_bits = []
        if seen_sni:
            summary_bits.append(f"SNI: {seen_sni}")
        if negotiated_version:
            summary_bits.append(f"Version: {negotiated_version}")
        if seen_chosen_cipher:
            summary_bits.append(f"Chosen cipher: {seen_chosen_cipher}")
        if cert_count:
            summary_bits.append(f"Certificates: {cert_count}")
        if seen_cipher_offer:
            summary_bits.append(f"Cipher offers: {seen_cipher_offer}")
        if summary_bits:
            add_row('Summary', '', " | ".join(summary_bits), '')
        if self.tls_tree.topLevelItemCount() == 0:
            add_row('Info', '', 'No TLS-like activity detected in this session', '')

        # Update phase headers/counts for quick-scan mode
        try:
            if handshake_phase is not None and data_phase is not None and closure_phase is not None:
                handshake_phase.setText(0, f"🔐 Handshake Phase ({phase_counts['handshake']} messages)")
                data_phase.setText(0, f"📦 Data Transfer Phase ({phase_counts['data']} messages)")
                closure_phase.setText(0, f"🔒 Closure Phase ({phase_counts['closure']} messages)")

                handshake_phase.setExpanded(True)
                data_phase.setExpanded(phase_counts['data'] <= 10)
                closure_phase.setExpanded(True)

                root = self.tls_tree.invisibleRootItem()
                if phase_counts['handshake'] == 0:
                    root.removeChild(handshake_phase)
                if phase_counts['data'] == 0:
                    root.removeChild(data_phase)
                if phase_counts['closure'] == 0:
                    root.removeChild(closure_phase)
        except Exception:
            pass

        # Update sub-tabs with quick content
        try:
            # Build Overview HTML using the same card-style pattern as report-mode.
            # (No reading of markdown report files here to avoid stale cross-XTI contamination.)
            events_for_ui = basic_events_cache
            if not events_for_ui:
                # Fallback: synthesize from the tree rows (best-effort)
                try:
                    root = self.tls_tree.invisibleRootItem()
                    stack = [root.child(i) for i in range(root.childCount())]
                    while stack:
                        it = stack.pop()
                        try:
                            step = (it.text(0) or '').strip()
                            d = (it.text(1) or '').strip()
                            detail = (it.text(2) or '').strip()
                            ts = (it.text(3) or '').strip()
                            if step and ts:
                                events_for_ui.append({'dir': d, 'ts': ts, 'detail': f"{step} • {detail}" if detail else step})
                        except Exception:
                            pass
                        try:
                            for c in range(it.childCount()):
                                stack.append(it.child(c))
                        except Exception:
                            pass
                except Exception:
                    events_for_ui = []

            def _label_from_detail(detail: str) -> str:
                try:
                    txt = (detail or '').strip()
                    if txt.startswith('TLS '):
                        txt = txt[4:].strip()
                    return txt.split('•', 1)[0].strip()
                except Exception:
                    return (detail or '').strip()

            handshake_msg_count = 0
            data_count = 0
            alert_count = 0
            for ev in (events_for_ui or []):
                lbl = _label_from_detail(ev.get('detail', '') or '')
                if lbl == 'ApplicationData' or 'ApplicationData' in lbl:
                    data_count += 1
                elif 'Alert' in lbl:
                    alert_count += 1
                elif any(x in lbl for x in ('Hello', 'Certificate', 'KeyExchange', 'Cipher', 'Finished', 'HelloDone')):
                    handshake_msg_count += 1

            # Derive a compact handshake sequence from the observed events
            seq = []
            try:
                last = None
                for ev in (events_for_ui or []):
                    lbl = _label_from_detail(ev.get('detail', '') or '')
                    if not lbl or lbl == last:
                        continue
                    last = lbl
                    if lbl.startswith('TLS Alert'):
                        lbl = 'Alert'
                    if lbl.startswith('Alert'):
                        lbl = 'Alert'
                    seq.append(lbl)
            except Exception:
                seq = []

            # Overview cards (copy of report-mode styling)
            html_parts = []
            html_parts.append('<style>')
            html_parts.append('body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin:0; padding:6px; }')
            html_parts.append('.card { background:white; border:1px solid #e0e0e0; border-radius:4px; padding:6px; margin:4px 0; box-shadow:0 1px 2px rgba(0,0,0,0.06); }')
            html_parts.append('.card-header { font-size:12px; font-weight:700; color:#1a1a1a; margin-bottom:4px; padding-bottom:2px; border-bottom:1px solid #e8f4f8; }')
            html_parts.append('.stat-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); gap:4px; margin:3px 0; }')
            html_parts.append('.stat-item { background:#f8fafb; padding:4px 6px; border-radius:3px; border-left:2px solid #2196F3; }')
            html_parts.append('.stat-label { font-size:9px; color:#666; text-transform:uppercase; font-weight:600; margin-bottom:1px; }')
            html_parts.append('.stat-value { font-size:12px; font-weight:700; color:#1a1a1a; }')
            html_parts.append('.badge { display:inline-block; padding:1px 5px; border-radius:2px; font-size:9px; font-weight:600; margin:1px; }')
            html_parts.append('.badge-success { background:#e8f5e9; color:#2e7d32; border:1px solid #a5d6a7; }')
            html_parts.append('.badge-info { background:#e3f2fd; color:#1976d2; border:1px solid #90caf9; }')
            html_parts.append('.badge-warning { background:#fff3e0; color:#f57c00; border:1px solid #ffb74d; }')
            html_parts.append('</style>')

            # Session Overview
            html_parts.append('<div class="card">')
            html_parts.append('<div class="card-header">📋 Session Overview</div>')
            html_parts.append(f'<div style="font-size:13px; font-weight:700; color:#1565c0; margin-bottom:3px;">{server}</div>')
            html_parts.append('<div class="stat-grid">')
            html_parts.append(f'<div class="stat-item"><div class="stat-label">Protocol</div><div class="stat-value">{protocol or "TCP"}</div></div>')
            html_parts.append(f'<div class="stat-item"><div class="stat-label">Port</div><div class="stat-value">{port or "N/A"}</div></div>')
            html_parts.append(f'<div class="stat-item"><div class="stat-label">Duration</div><div class="stat-value">{duration or "N/A"}</div></div>')
            html_parts.append(f'<div class="stat-item"><div class="stat-label">Total Messages</div><div class="stat-value">{len(events_for_ui or [])}</div></div>')
            html_parts.append('</div>')
            if ip_text:
                html_parts.append(f'<div style="margin-top:3px; font-size:10px; color:#666;"><b>IP:</b> {ip_text}</div>')
            if seen_sni:
                html_parts.append(f'<div style="font-size:10px; color:#666; margin-top:2px;"><b>SNI:</b> {seen_sni}</div>')
            try:
                alpn = basic_meta_cache.get('alpn') or []
                if alpn:
                    html_parts.append(f'<div style="font-size:10px; color:#666; margin-top:2px;"><b>ALPN:</b> {", ".join([str(x) for x in alpn[:6]])}{" …" if len(alpn) > 6 else ""}</div>')
            except Exception:
                pass
            html_parts.append('</div>')

            # Security Configuration
            html_parts.append('<div class="card">')
            html_parts.append('<div class="card-header">🔐 Security Configuration</div>')
            if negotiated_version or basic_version_cache:
                ver = negotiated_version or basic_version_cache
                version_color = '#2e7d32' if isinstance(ver, str) and ('TLS 1.2' in ver or 'TLS 1.3' in ver) else '#f57c00'
                html_parts.append(f'<div style="margin:3px 0;"><b>Version:</b> <span style="color:{version_color}; font-weight:700;">{ver}</span></div>')
            try:
                sv = basic_meta_cache.get('supported_versions') or []
                if sv:
                    html_parts.append(f'<div style="margin:3px 0; font-size:10px; color:#666;"><b>Client supported versions:</b> {", ".join([str(x) for x in sv[:6]])}{" …" if len(sv) > 6 else ""}</div>')
                sel = basic_meta_cache.get('server_selected_version')
                if sel:
                    html_parts.append(f'<div style="margin:3px 0; font-size:10px; color:#666;"><b>Server selected version:</b> {sel}</div>')
            except Exception:
                pass
            chosen_cipher = seen_chosen_cipher
            html_parts.append(f'<div style="margin:3px 0;"><b>Chosen Cipher Suite:</b><br/><code style="background:#f5f5f5; padding:3px 6px; border-radius:3px; font-size:11px;">{chosen_cipher or "N/A"}</code></div>')
            try:
                if chosen_cipher:
                    badges = []
                    cipher = chosen_cipher
                    if 'ECDHE' in cipher or 'DHE' in cipher:
                        badges.append('<span class="badge badge-success">✓ Perfect Forward Secrecy</span>')
                    if 'GCM' in cipher or 'CHACHA20' in cipher or 'POLY1305' in cipher:
                        badges.append('<span class="badge badge-success">✓ AEAD Mode</span>')
                    if 'AES_256' in cipher:
                        badges.append('<span class="badge badge-info">256-bit Encryption</span>')
                    elif 'AES_128' in cipher:
                        badges.append('<span class="badge badge-info">128-bit Encryption</span>')
                    if badges:
                        html_parts.append('<div style="margin:4px 0 2px 0;">' + ''.join(badges) + '</div>')
            except Exception:
                pass
            if cert_count:
                html_parts.append(f'<div style="margin:3px 0;"><b>Certificate Chain:</b> {cert_count} certificate{"s" if cert_count != 1 else ""}</div>')
            html_parts.append('<div style="margin-top:4px; font-size:10px; color:#666;"><b>Scope:</b> TLS record/handshake decoding only (no decryption of ApplicationData)</div>')
            html_parts.append('</div>')

            # Cipher Suite Negotiation (best-effort from live decode; no markdown report dependency)
            html_parts.append('<div class="card">')
            html_parts.append('<div class="card-header">🔑 Cipher Suite Negotiation</div>')
            html_parts.append(f'<div style="margin:3px 0;"><b>Chosen Cipher:</b><br/><code style="background:#f5f5f5; padding:3px 6px; border-radius:3px; font-size:11px;">{chosen_cipher or "N/A"}</code></div>')
            if seen_cipher_offer:
                html_parts.append(f'<div style="margin:3px 0;"><b>Client Offered:</b> {seen_cipher_offer}</div>')
            if seen_cipher_suites:
                try:
                    preview = [str(x) for x in (seen_cipher_suites or []) if x]
                    html_parts.append('<div style="margin:3px 0;"><b>Preview:</b><br/>' + '<br/>'.join([f'<code style="background:#f5f5f5; padding:2px 4px; border-radius:3px; font-size:11px;">{c}</code>' for c in preview[:8]]) + ('<br/><span style="color:#666; font-size:10px;">…</span>' if len(preview) > 8 else '') + '</div>')
                except Exception:
                    pass
            html_parts.append('</div>')

            # Message Statistics
            html_parts.append('<div class="card">')
            html_parts.append('<div class="card-header">📊 Message Statistics</div>')
            html_parts.append('<div class="stat-grid">')
            html_parts.append(f'<div class="stat-item" style="border-left-color:#2196F3;"><div class="stat-label">Handshake</div><div class="stat-value">{handshake_msg_count}</div></div>')
            html_parts.append(f'<div class="stat-item" style="border-left-color:#4CAF50;"><div class="stat-label">Application Data</div><div class="stat-value">{data_count}</div></div>')
            if alert_count:
                html_parts.append(f'<div class="stat-item" style="border-left-color:#f44336;"><div class="stat-label">Alerts</div><div class="stat-value">{alert_count}</div></div>')
            html_parts.append('</div>')
            html_parts.append('</div>')

            # Handshake Flow pills
            if seq:
                html_parts.append('<div class="card">')
                html_parts.append('<div class="card-header">🔄 Handshake Flow</div>')
                color_map = {
                    'ClientHello': '#1976d2', 'ServerHello': '#1976d2', 'Certificate': '#1976d2',
                    'ServerKeyExchange': '#1976d2', 'ClientKeyExchange': '#1976d2', 'Finished': '#1976d2',
                    'ServerHelloDone': '#1976d2', 'CertificateRequest': '#1976d2',
                    'ChangeCipherSpec': '#f57c00', 'Encrypted Finished': '#388e3c',
                    'ApplicationData': '#616161', 'Alert': '#d32f2f'
                }
                def pill(label: str) -> str:
                    col = '#757575'
                    bg_col = '#f5f5f5'
                    for k, v in color_map.items():
                        if k in label:
                            col = v
                            if v == '#1976d2':
                                bg_col = '#e3f2fd'
                            elif v == '#f57c00':
                                bg_col = '#fff3e0'
                            elif v == '#388e3c':
                                bg_col = '#e8f5e9'
                            elif v == '#d32f2f':
                                bg_col = '#ffebee'
                            break
                    return f"<span style='display:inline-block; margin:3px; padding:8px 14px; border:2px solid {col}; border-radius:16px; color:{col}; background:{bg_col}; font-size:12px; font-weight:600; box-shadow:0 1px 2px rgba(0,0,0,0.1);'>{label}</span>"
                html_parts.append('<div style="display:flex; flex-wrap:wrap; align-items:center; gap:2px; padding:8px;">')
                for i, t in enumerate(seq):
                    html_parts.append(pill(t))
                    if i < len(seq) - 1:
                        html_parts.append('<span style="color:#bdbdbd; margin:0 4px; font-size:18px; font-weight:700;">→</span>')
                html_parts.append('</div>')
                html_parts.append('</div>')

            try:
                self.tls_overview_view.setHtml(''.join(html_parts))
            except Exception:
                self.tls_overview_view.setText('Quick-scan summary unavailable')

            # Security tab: ladder diagram + cipher/cert summary, matching report-mode pattern.
            try:
                security_html = []

                # Ladder diagram built from detected events
                try:
                    grouped = []
                    def flush_group(buf_role, buf_count, first_ts):
                        if buf_role and buf_count > 0:
                            grouped.append({'direction': buf_role, 'label': 'ApplicationData x' + str(buf_count), 'timestamp': first_ts})

                    buf_role = None
                    buf_count = 0
                    first_ts = ''
                    for ev in (events_for_ui or [])[:200]:
                        role = (ev.get('dir', '') or '').strip()
                        detail = _label_from_detail(ev.get('detail', '') or '')
                        ts = (ev.get('ts', '') or '').strip()
                        if detail == 'Finished' and 'ChangeCipherSpec' in (buf_role or ''):
                            detail = 'Encrypted Finished'
                        if detail.startswith('TLS Alert'):
                            detail = 'Alert'
                        if detail.startswith('Alert'):
                            detail = 'Alert'
                        if detail == 'ApplicationData':
                            if buf_role == role:
                                buf_count += 1
                            else:
                                flush_group(buf_role, buf_count, first_ts)
                                buf_role = role
                                buf_count = 1
                                first_ts = ts
                            continue
                        flush_group(buf_role, buf_count, first_ts)
                        buf_role = None
                        buf_count = 0
                        grouped.append({'direction': role, 'label': detail, 'timestamp': ts})
                    flush_group(buf_role, buf_count, first_ts)

                    security_html.append('<div style="font-family: monospace; font-size: 11px; background:#fafafa; padding:10px; border:1px solid #ddd; border-radius:4px;">')
                    security_html.append('<b>📊 TLS Handshake Ladder Diagram</b><br/><br/>')
                    security_html.append('<span style="color:#666;">SIM (Client)</span>' + ' ' * 25 + '<span style="color:#666;">ME (Server)</span><br/>')
                    security_html.append('    │' + ' ' * 50 + '│<br/>')

                    for ev in grouped:
                        role = ev.get('direction', '') or ''
                        detail = ev.get('label', '') or ''
                        ts = (ev.get('timestamp', '') or '').split()[-1] if ev.get('timestamp') else ''
                        role_norm = _norm_dir(role)
                        if role_norm.replace(' ', '').startswith('SIM'):
                            arrow = f'├──{detail}─────────────────────────────────────────────▶│'
                            security_html.append(f'<span style="color:#2a7ed3;">{arrow}</span> <span style="color:#999;">{ts}</span><br/>')
                        elif role_norm.replace(' ', '').startswith('ME'):
                            arrow = f'│◀─────────────────────────────────────────────{detail}──┤'
                            security_html.append(f'<span style="color:#e08a00;">{arrow}</span> <span style="color:#999;">{ts}</span><br/>')
                        else:
                            security_html.append(f'    │   {detail}' + ' ' * 30 + f'│ <span style="color:#999;">{ts}</span><br/>')

                    security_html.append('    │' + ' ' * 50 + '│<br/>')
                    security_html.append('</div><br/>')
                except Exception:
                    pass

                # Cipher analysis section (best-effort; no chosen cipher in quick scan)
                try:
                    ver = negotiated_version or basic_version_cache
                    security_html.append('<div style="margin:16px 0;"><b>🔐 Cipher Suite Analysis</b></div>')
                    security_html.append('<div style="background:#f9f9f9; padding:8px; border-left:3px solid #2a7ed3; margin-bottom:8px;">')
                    if ver:
                        ver_color = '#2e7d32' if isinstance(ver, str) and ('TLS 1.2' in ver or 'TLS 1.3' in ver) else '#e65100'
                        security_html.append(f'<b>Version:</b> <span style="color:{ver_color};">{ver}</span><br/>')
                    cipher = seen_chosen_cipher
                    security_html.append(f'<b>Chosen Cipher:</b> {cipher or "N/A"}<br/>')
                    try:
                        sni = seen_sni or (basic_meta_cache.get('sni') if isinstance(basic_meta_cache, dict) else None)
                        if sni:
                            security_html.append(f'<b>SNI:</b> {sni}<br/>')
                        alpn = basic_meta_cache.get('alpn') or []
                        if alpn:
                            security_html.append(f'<b>ALPN:</b> {", ".join([str(x) for x in alpn[:6]])}{" …" if len(alpn) > 6 else ""}<br/>')
                        sv = basic_meta_cache.get('supported_versions') or []
                        if sv:
                            security_html.append(f'<b>Supported Versions:</b> {", ".join([str(x) for x in sv[:6]])}{" …" if len(sv) > 6 else ""}<br/>')
                        grp = basic_meta_cache.get('supported_groups') or []
                        if grp:
                            security_html.append(f'<b>Supported Groups:</b> {", ".join([str(x) for x in grp[:6]])}{" …" if len(grp) > 6 else ""}<br/>')
                        ks = basic_meta_cache.get('key_share_groups') or []
                        if ks:
                            security_html.append(f'<b>Key Share Groups:</b> {", ".join([str(x) for x in ks[:6]])}{" …" if len(ks) > 6 else ""}<br/>')
                        sa = basic_meta_cache.get('signature_algorithms') or []
                        if sa:
                            security_html.append(f'<b>Signature Algs:</b> {", ".join([str(x) for x in sa[:6]])}{" …" if len(sa) > 6 else ""}<br/>')
                    except Exception:
                        pass
                    if cipher:
                        if 'ECDHE' in cipher or 'DHE' in cipher:
                            security_html.append('  • <span style="color:#2e7d32;">✓ Perfect Forward Secrecy</span><br/>')
                        if 'GCM' in cipher or 'CHACHA20' in cipher or 'POLY1305' in cipher:
                            security_html.append('  • <span style="color:#2e7d32;">✓ AEAD Mode (Authenticated Encryption)</span><br/>')
                        if 'AES_256' in cipher:
                            security_html.append('  • <span style="color:#2e7d32;">✓ 256-bit Encryption</span><br/>')
                        elif 'AES_128' in cipher:
                            security_html.append('  • <span style="color:#1976d2;">◆ 128-bit Encryption</span><br/>')
                    security_html.append('</div>')
                except Exception:
                    pass

                # Certificate summary (CNs if available)
                try:
                    if cert_count:
                        security_html.append('<div style="margin:16px 0;"><b>📜 PKI Certificate Chain</b></div>')
                        security_html.append(f'<div style="background:#fff9e6; padding:8px; border-left:3px solid #e08a00; margin-bottom:8px;">')
                        security_html.append(f'<b>Certificates:</b> {cert_count}<br/>')
                        uniq = []
                        try:
                            for cn in pki_cns:
                                if cn not in uniq:
                                    uniq.append(cn)
                        except Exception:
                            uniq = []
                        if uniq:
                            security_html.append('<b>CN:</b> ' + ', '.join(uniq[:5]) + (' …' if len(uniq) > 5 else '') + '<br/>')
                        security_html.append('</div>')
                except Exception:
                    pass

                if security_html:
                    try:
                        self.tls_security_view.setHtml(''.join(security_html))
                    except Exception:
                        self.tls_security_view.setText(''.join([s for s in security_html if '<' not in s]))
            except Exception:
                pass
        except Exception:
            pass

    def _basic_tls_detect_segments(self, segments):
        """Very lightweight TLS record scan over collected channel segments.
        Returns (events, handshake_types, negotiated_version_text)
        """
        events = []
        hs_types = []
        negotiated = None

        # Best-effort metadata for the caller (chosen cipher, offered ciphers)
        chosen_cipher = None
        offered_ciphers = []
        sni_hostname = None
        alpn_protocols = []
        supported_versions = []
        supported_groups = []
        signature_algorithms = []
        key_share_groups = []
        server_selected_version = None

        try:
            # Prefer existing cipher mapping from the protocol analyzer
            from .protocol_analyzer import TlsAnalyzer
            cipher_map = getattr(TlsAnalyzer, 'CIPHER_SUITES', {}) or {}
        except Exception:
            cipher_map = {}

        def ver_text(maj, minr):
            if maj == 3:
                # 0x0301 TLS1.0, 0x0303 TLS1.2, 0x0304 TLS1.3
                if minr == 1:
                    return 'TLS 1.0'
                if minr == 2:
                    return 'TLS 1.1'
                if minr == 3:
                    return 'TLS 1.2'
                if minr == 4:
                    return 'TLS 1.3'
            return f'0x{maj:02x}{minr:02x}'

        def _ver_u16_text(v: int) -> str:
            try:
                return ver_text((int(v) >> 8) & 0xFF, int(v) & 0xFF)
            except Exception:
                return f"0x{int(v):04x}"

        group_map = {
            0x0017: 'secp256r1',
            0x0018: 'secp384r1',
            0x0019: 'secp521r1',
            0x001D: 'x25519',
            0x001E: 'x448',
            0x0100: 'ffdhe2048',
            0x0101: 'ffdhe3072',
            0x0102: 'ffdhe4096',
            0x0103: 'ffdhe6144',
            0x0104: 'ffdhe8192',
        }

        sig_alg_map = {
            0x0401: 'rsa_pkcs1_sha256',
            0x0501: 'rsa_pkcs1_sha384',
            0x0601: 'rsa_pkcs1_sha512',
            0x0403: 'ecdsa_secp256r1_sha256',
            0x0503: 'ecdsa_secp384r1_sha384',
            0x0603: 'ecdsa_secp521r1_sha512',
            0x0804: 'rsa_pss_rsae_sha256',
            0x0805: 'rsa_pss_rsae_sha384',
            0x0806: 'rsa_pss_rsae_sha512',
            0x0807: 'ed25519',
            0x0808: 'ed448',
        }

        def _fmt_id(v: int, mapping: dict) -> str:
            try:
                name = mapping.get(int(v))
                if name:
                    return f"{name} (0x{int(v):04X})"
                return f"0x{int(v):04X}"
            except Exception:
                return str(v)

        def _append_unique(lst, val):
            try:
                if not val:
                    return
                if val not in lst:
                    lst.append(val)
            except Exception:
                pass

        def _parse_extensions(view, ext_start: int, ext_end: int, is_client: bool):
            nonlocal sni_hostname, alpn_protocols, supported_versions, supported_groups
            nonlocal signature_algorithms, key_share_groups, server_selected_version
            try:
                p = int(ext_start)
                end = int(ext_end)
                while p + 4 <= end:
                    et = (int(view[p]) << 8) | int(view[p + 1])
                    eln = (int(view[p + 2]) << 8) | int(view[p + 3])
                    p += 4
                    if p + eln > end:
                        break
                    data_start = p
                    data_end = p + eln

                    # server_name (SNI)
                    if et == 0x0000 and sni_hostname is None:
                        try:
                            q = data_start
                            if q + 2 <= data_end:
                                list_len = (int(view[q]) << 8) | int(view[q + 1])
                                q += 2
                                list_end = min(data_end, q + list_len)
                                while q + 3 <= list_end:
                                    name_type = int(view[q]); q += 1
                                    nlen = (int(view[q]) << 8) | int(view[q + 1]); q += 2
                                    if q + nlen > list_end:
                                        break
                                    if name_type == 0:
                                        raw = bytes(view[q:q + nlen])
                                        try:
                                            host = raw.decode('utf-8', errors='ignore').strip()
                                        except Exception:
                                            host = ''
                                        if host:
                                            sni_hostname = host
                                            break
                                    q += nlen
                        except Exception:
                            pass

                    # ALPN
                    if et == 0x0010:
                        try:
                            q = data_start
                            if q + 2 <= data_end:
                                l = (int(view[q]) << 8) | int(view[q + 1])
                                q += 2
                                le = min(data_end, q + l)
                                while q + 1 <= le:
                                    plen = int(view[q]); q += 1
                                    if q + plen > le:
                                        break
                                    proto = bytes(view[q:q + plen]).decode('ascii', errors='ignore').strip()
                                    q += plen
                                    if proto:
                                        _append_unique(alpn_protocols, proto)
                        except Exception:
                            pass

                    # supported_versions
                    if et == 0x002B:
                        try:
                            q = data_start
                            if is_client:
                                if q + 1 <= data_end:
                                    l = int(view[q]); q += 1
                                    le = min(data_end, q + l)
                                    while q + 2 <= le:
                                        v = (int(view[q]) << 8) | int(view[q + 1]); q += 2
                                        _append_unique(supported_versions, _ver_u16_text(v))
                            else:
                                if q + 2 <= data_end:
                                    v = (int(view[q]) << 8) | int(view[q + 1])
                                    server_selected_version = _ver_u16_text(v)
                        except Exception:
                            pass

                    # supported_groups (named groups)
                    if et == 0x000A:
                        try:
                            q = data_start
                            if q + 2 <= data_end:
                                l = (int(view[q]) << 8) | int(view[q + 1])
                                q += 2
                                le = min(data_end, q + l)
                                while q + 2 <= le:
                                    gid = (int(view[q]) << 8) | int(view[q + 1]); q += 2
                                    _append_unique(supported_groups, _fmt_id(gid, group_map))
                        except Exception:
                            pass

                    # signature_algorithms
                    if et == 0x000D:
                        try:
                            q = data_start
                            if q + 2 <= data_end:
                                l = (int(view[q]) << 8) | int(view[q + 1])
                                q += 2
                                le = min(data_end, q + l)
                                while q + 2 <= le:
                                    aid = (int(view[q]) << 8) | int(view[q + 1]); q += 2
                                    _append_unique(signature_algorithms, _fmt_id(aid, sig_alg_map))
                        except Exception:
                            pass

                    # key_share (ClientHello only)
                    if et == 0x0033 and is_client:
                        try:
                            q = data_start
                            if q + 2 <= data_end:
                                l = (int(view[q]) << 8) | int(view[q + 1])
                                q += 2
                                le = min(data_end, q + l)
                                while q + 4 <= le:
                                    gid = (int(view[q]) << 8) | int(view[q + 1]); q += 2
                                    klen = (int(view[q]) << 8) | int(view[q + 1]); q += 2
                                    if q + klen > le:
                                        break
                                    _append_unique(key_share_groups, _fmt_id(gid, group_map))
                                    q += klen
                        except Exception:
                            pass

                    p = data_end
            except Exception:
                pass

        hs_map = {
            0x01: 'ClientHello',
            0x02: 'ServerHello',
            0x0b: 'Certificate',
            0x0c: 'ServerKeyExchange',
            0x0d: 'CertificateRequest',
            0x0e: 'ServerHelloDone',
            0x10: 'ClientKeyExchange',
            0x14: 'Finished',  # Handshake Finished (not record type)
            0x0f: 'CertificateVerify',
            0x12: 'ServerKeyExchange',  # Normalize mixed naming seen in traces
        }

        # Track last content type and last emitted name per direction to help CCS→Finished labeling and dedup
        last_ct_by_dir = {}
        last_name_by_dir = {}

        # Reassembly buffers per direction to handle TLS records split across segments
        buffers = {}

        def _is_tls_header(buf: bytearray, pos: int = 0) -> bool:
            try:
                if pos + 5 > len(buf):
                    return False
                ct = buf[pos]
                maj = buf[pos + 1]
                minr = buf[pos + 2]
                return ct in (20, 21, 22, 23) and maj == 0x03 and minr in (1, 2, 3, 4)
            except Exception:
                return False

        def _find_tls_header(buf: bytearray) -> int:
            # Find next plausible TLS record header
            try:
                n = len(buf)
                for p in range(0, max(0, n - 4)):
                    if _is_tls_header(buf, p):
                        return p
            except Exception:
                pass
            return -1

        for seg in segments:
            direction = seg.get('dir', '') or ''
            data = seg.get('data') or b''
            if not data:
                continue

            buf = buffers.get(direction)
            if buf is None:
                buf = bytearray()
                buffers[direction] = buf
            buf.extend(data)

            # Consume as many complete TLS records as possible
            while True:
                if len(buf) < 5:
                    break
                if not _is_tls_header(buf, 0):
                    p = _find_tls_header(buf)
                    if p <= 0:
                        # keep a small tail to allow header completion
                        if len(buf) > 8192:
                            del buf[:-64]
                        break
                    del buf[:p]
                    if len(buf) < 5:
                        break

                ct = buf[0]
                maj = buf[1]
                minr = buf[2]
                rec_len = (buf[3] << 8) | buf[4]
                if rec_len < 0:
                    del buf[0:1]
                    continue
                if 5 + rec_len > len(buf):
                    # Wait for more bytes
                    break

                record = bytes(buf[:5 + rec_len])
                del buf[:5 + rec_len]

                vtxt = ver_text(maj, minr)
                if negotiated is None and vtxt.startswith('TLS'):
                    negotiated = vtxt
                # TLS 1.3 uses record-layer 0x0303; prefer supported_versions selection when present.
                if server_selected_version and (negotiated is None or negotiated == 'TLS 1.2'):
                    negotiated = server_selected_version

                if ct == 22 and rec_len >= 4:
                    # Scan all handshake messages inside this record for metadata.
                    try:
                        d = memoryview(record)
                        hs_pos = 5
                        hs_end = 5 + rec_len
                        while hs_pos + 4 <= hs_end:
                            t = int(d[hs_pos])
                            hs_len = (int(d[hs_pos+1]) << 16) | (int(d[hs_pos+2]) << 8) | int(d[hs_pos+3])
                            body_start = hs_pos + 4
                            body_end = body_start + hs_len
                            if body_end > hs_end:
                                break

                            # ClientHello: extract offered ciphers + extension metadata (best-effort)
                            if t == 0x01 and body_start + 40 <= body_end:
                                try:
                                    p2 = body_start
                                    p2 += 2  # version
                                    p2 += 32  # random
                                    sid_len = int(d[p2]) if p2 < body_end else 0
                                    p2 += 1 + sid_len
                                    if p2 + 2 <= body_end:
                                        cs_len = (int(d[p2]) << 8) | int(d[p2+1])
                                        p2 += 2
                                        if not offered_ciphers:
                                            tmp = []
                                            for _ in range(0, cs_len, 2):
                                                if p2 + 2 > body_end:
                                                    break
                                                cid = (int(d[p2]) << 8) | int(d[p2+1])
                                                p2 += 2
                                                tmp.append(cipher_map.get(cid, f"Unknown_0x{cid:04X}"))
                                            offered_ciphers = [str(x) for x in tmp if x]
                                        else:
                                            p2 += cs_len

                                        # compression methods
                                        if p2 + 1 <= body_end:
                                            comp_len = int(d[p2])
                                            p2 += 1 + comp_len

                                        # extensions
                                        if p2 + 2 <= body_end:
                                            ext_len = (int(d[p2]) << 8) | int(d[p2+1])
                                            p2 += 2
                                            ext_end = min(body_end, p2 + ext_len)
                                            _parse_extensions(d, p2, ext_end, is_client=True)
                                except Exception:
                                    pass

                            # ServerHello: extract chosen cipher + selected version (best-effort)
                            if t == 0x02 and body_start + 40 <= body_end:
                                try:
                                    p2 = body_start
                                    p2 += 2  # version
                                    p2 += 32  # random
                                    sid_len = int(d[p2]) if p2 < body_end else 0
                                    p2 += 1 + sid_len
                                    if p2 + 2 <= body_end:
                                        cid = (int(d[p2]) << 8) | int(d[p2+1])
                                        if chosen_cipher is None:
                                            chosen_cipher = cipher_map.get(cid, f"Unknown_0x{cid:04X}")
                                        p2 += 2

                                    # compression method
                                    if p2 + 1 <= body_end:
                                        p2 += 1

                                    # extensions
                                    if p2 + 2 <= body_end:
                                        ext_len = (int(d[p2]) << 8) | int(d[p2+1])
                                        p2 += 2
                                        ext_end = min(body_end, p2 + ext_len)
                                        _parse_extensions(d, p2, ext_end, is_client=False)
                                except Exception:
                                    pass

                            hs_pos = body_end
                    except Exception:
                        pass

                    # TLS 1.3 uses record-layer 0x0303; after parsing ServerHello extensions,
                    # prefer the selected supported_versions value when present.
                    try:
                        if server_selected_version and (negotiated is None or negotiated == 'TLS 1.2'):
                            negotiated = server_selected_version
                    except Exception:
                        pass

                    hs_type = record[5]
                    if hs_type not in hs_map and hs_type != 0x14:
                        last_ct_by_dir[direction] = 22
                        continue
                    name = hs_map.get(hs_type, f'Handshake(0x{hs_type:02x})')
                    if hs_type == 0x14 and last_ct_by_dir.get(direction) == 20:
                        name = 'Encrypted Finished'
                    if last_name_by_dir.get(direction) != name:
                        hs_types.append(name)
                        events.append({'dir': direction, 'ts': seg.get('ts',''), 'detail': f"{name} • {vtxt}"})
                        last_name_by_dir[direction] = name
                    last_ct_by_dir[direction] = 22

                elif ct == 23:
                    events.append({'dir': direction, 'ts': seg.get('ts',''), 'detail': f"ApplicationData • {vtxt} • {rec_len} bytes"})
                    last_ct_by_dir[direction] = 23

                elif ct == 20:
                    # Don't auto-insert Encrypted Finished; label real Finished after CCS as encrypted.
                    events.append({'dir': direction, 'ts': seg.get('ts',''), 'detail': f"ChangeCipherSpec • {vtxt}"})
                    last_ct_by_dir[direction] = 20

                elif ct == 21:
                    alert_level = record[5] if rec_len >= 2 else None
                    alert_desc = record[6] if rec_len >= 2 else None
                    level_map = {1: 'warning', 2: 'fatal'}
                    desc_map = {
                        0: 'close_notify',
                        10: 'unexpected_message',
                        20: 'bad_record_mac',
                        21: 'decryption_failed_reserved',
                        22: 'record_overflow',
                        30: 'decompression_failure',
                        40: 'handshake_failure',
                        41: 'no_certificate_reserved',
                        42: 'bad_certificate',
                        43: 'unsupported_certificate',
                        44: 'certificate_revoked',
                        45: 'certificate_expired',
                        46: 'certificate_unknown',
                        47: 'illegal_parameter',
                        48: 'unknown_ca',
                        49: 'access_denied',
                        50: 'decode_error',
                        51: 'decrypt_error',
                        60: 'export_restriction_reserved',
                        70: 'protocol_version',
                        71: 'insufficient_security',
                        80: 'internal_error',
                        86: 'inappropriate_fallback',
                        90: 'user_canceled',
                        100: 'no_renegotiation',
                        109: 'missing_extension',
                        110: 'unsupported_extension',
                        112: 'unrecognized_name',
                        116: 'unknown_psk_identity',
                        120: 'certificate_required',
                    }
                    level_txt = level_map.get(alert_level, f"level_{alert_level}" if alert_level is not None else "level_?")
                    desc_txt = desc_map.get(alert_desc, f"alert_{alert_desc}" if alert_desc is not None else "alert_?")
                    try:
                        vendor_level_map = {151: 'warning_vendor'}
                        vendor_desc_map = {82: 'close_notify_vendor'}
                        if level_txt.startswith('level_') and (alert_level in vendor_level_map):
                            level_txt = vendor_level_map.get(alert_level, level_txt)
                        if desc_txt.startswith('alert_') and (alert_desc in vendor_desc_map):
                            desc_txt = vendor_desc_map.get(alert_desc, desc_txt)
                        if desc_txt == 'close_notify_vendor':
                            desc_txt = 'close_notify'
                    except Exception:
                        pass
                    events.append({'dir': direction, 'ts': seg.get('ts',''), 'detail': f"TLS Alert: {level_txt}, {desc_txt}"})
                    last_ct_by_dir[direction] = 21

        # Expose scan metadata to callers without changing the return signature.
        try:
            self._basic_tls_scan_meta = {
                'chosen_cipher': chosen_cipher,
                'offered_ciphers': offered_ciphers,
                'sni': sni_hostname,
                'alpn': alpn_protocols,
                'supported_versions': supported_versions,
                'supported_groups': supported_groups,
                'signature_algorithms': signature_algorithms,
                'key_share_groups': key_share_groups,
                'server_selected_version': server_selected_version,
            }
        except Exception:
            pass

        return events, hs_types, negotiated

    def _render_ladder_from_steps(self, highlight_index: Optional[int] = None, group_appdata: bool = True):
        """Render a two-column textual ladder from the current Steps tree.
        Optionally group consecutive ApplicationData entries per direction and emphasize the highlighted index.
        Note: This function is deprecated - ladder is now in Security tab via _populate_tls_from_report.
        """
        try:
            if not hasattr(self, 'tls_tree'):
                return
            rows = []
            count = self.tls_tree.topLevelItemCount()
            for i in range(count):
                it = self.tls_tree.topLevelItem(i)
                if not it:
                    continue
                rows.append({
                    'step': it.text(0) or '',
                    'dir': it.text(1) or '',
                    'detail': it.text(2) or '',
                    'ts': it.text(3) or ''
                })
            # Build grouped list
            grouped = []
            buf_role = None; buf_count = 0; first_ts = ''
            for idx, r in enumerate(rows):
                label = r['detail']
                # Consider ApplicationData when detail starts with 'TLS Application Data' or step badge is 'AppData'
                is_app = (r['step'] == 'AppData') or label.startswith('TLS Application Data') or label.startswith('ApplicationData')
                if group_appdata and is_app:
                    role = r['dir']
                    if buf_role == role:
                        buf_count += 1
                    else:
                        if buf_role and buf_count:
                            grouped.append({'direction': buf_role, 'label': f'ApplicationData x{buf_count}', 'timestamp': first_ts, 'index': None})
                        buf_role = role; buf_count = 1; first_ts = r['ts']
                    continue
                else:
                    if buf_role and buf_count:
                        grouped.append({'direction': buf_role, 'label': f'ApplicationData x{buf_count}', 'timestamp': first_ts, 'index': None})
                        buf_role = None; buf_count = 0; first_ts = ''
                grouped.append({'direction': r['dir'], 'label': r['detail'] or r['step'], 'timestamp': r['ts'], 'index': idx})
            if buf_role and buf_count:
                grouped.append({'direction': buf_role, 'label': f'ApplicationData x{buf_count}', 'timestamp': first_ts, 'index': None})
            # Build HTML table with clickable anchors per step index
            def esc(s: str) -> str:
                return (s or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            html = []
            html.append("<table style='border-collapse:collapse; width:100%; font-family:monospace;'>")
            # Header row
            html.append("<tr><th style='text-align:left; color:#666; padding:2px 6px; width:48%;'>SIM</th><th style='width:4%;'></th><th style='text-align:left; color:#666; padding:2px 6px;'>ME</th></tr>")
            for ev in grouped:
                role = ev.get('direction',''); detail = ev.get('label',''); ts = ev.get('timestamp',''); idx = ev.get('index')
                cell_html_left = ""; cell_html_right = ""
                text_html = esc(ts) + "&nbsp;&nbsp;" + esc(detail)
                is_high = (highlight_index is not None and idx == highlight_index)
                style_high = "background:#fff8e1; font-weight:bold;" if is_high else ""
                anchor_start = f"<a href='stepidx:{idx}' style='text-decoration:none; color:inherit;'>" if idx is not None else ""
                anchor_end = "</a>" if idx is not None else ""
                if role.startswith('SIM'):
                    cell_html_left = f"<td style='padding:2px 6px; {style_high}'>{anchor_start}{text_html}{anchor_end}</td>"
                    cell_html_right = "<td style='padding:2px 6px;'></td>"
                elif role.startswith('ME'):
                    cell_html_left = "<td style='padding:2px 6px;'></td>"
                    cell_html_right = f"<td style='padding:2px 6px; {style_high}'>{anchor_start}{text_html}{anchor_end}</td>"
                else:
                    cell_html_left = f"<td style='padding:2px 6px; {style_high}'>{anchor_start}{text_html}{anchor_end}</td>"
                    cell_html_right = "<td style='padding:2px 6px;'></td>"
                html.append(f"<tr>{cell_html_left}<td style='width:4%; text-align:center; color:#999;'>|</td>{cell_html_right}</tr>")
            html.append("</table>")
            # Note: Ladder is now displayed in Security tab, this function is deprecated
        except Exception:
            pass
    
    def enhance_channel_groups_with_roles(self, channel_groups: List[dict]):
        """Enhance channel groups with role information from protocol analysis."""
        try:
            from .protocol_analyzer import ProtocolAnalyzer, ChannelRoleDetector
            from .apdu_parser_construct import parse_apdu
        except ImportError:
            return  # Skip enhancement if protocol analyzer not available
        
        # Analyze each channel group for role detection
        for group in channel_groups:
            group_role = "Unknown"
            
            # Get sessions from the group
            sessions = group.get("sessions", [])
            for session in sessions:
                # Analyze trace items in this session for TLS handshakes
                for trace_idx in session.traceitem_indexes[:20]:  # Check first 20 items for performance
                    try:
                        if trace_idx < len(self.parser.trace_items):
                            trace_item = self.parser.trace_items[trace_idx]
                            
                            # Check if this is a SEND/RECEIVE DATA command
                            if ("send data" in trace_item.summary.lower() or 
                                "receive data" in trace_item.summary.lower()):
                                
                                if trace_item.rawhex:
                                    parsed = parse_apdu(trace_item.rawhex)
                                    payload = self._extract_payload_for_role_analysis(parsed)
                                    
                                    if payload:
                                        analysis = ProtocolAnalyzer.analyze_payload(payload)
                                        if analysis.tls_info and analysis.tls_info.sni_hostname:
                                            detected_role = ChannelRoleDetector.detect_role_from_sni(
                                                analysis.tls_info.sni_hostname
                                            )
                                            if detected_role:
                                                group_role = detected_role
                                                break  # Found a role, use it
                    except:
                        continue  # Skip failed analysis
                
                if group_role != "Unknown":
                    break  # Found role in this session
            
            # Set the role in the group
            group["role"] = group_role
    
    def _extract_payload_for_role_analysis(self, parsed_apdu) -> bytes:
        """Extract payload from parsed APDU for role analysis."""
        try:
            for tlv in parsed_apdu.tlvs:
                if hasattr(tlv, 'raw_value') and len(tlv.raw_value) > 20:
                    return tlv.raw_value
                elif hasattr(tlv, 'children'):
                    for child in tlv.children:
                        if hasattr(child, 'raw_value') and len(child.raw_value) > 20:
                            return child.raw_value
        except:
            pass
        return None
    
    def create_summary_cards(self) -> QWidget:
        """Create collapsible summary cards section."""
        from PySide6.QtWidgets import QGroupBox, QGridLayout
        
        # Create collapsible group box
        self.summary_group = QGroupBox("Quick Summary")
        self.summary_group.setCheckable(True)
        self.summary_group.setChecked(True)  # Initially expanded
        self.summary_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin: 5px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
        """)
        
        # Grid layout for summary cards
        cards_layout = QGridLayout(self.summary_group)
        cards_layout.setContentsMargins(10, 15, 10, 10)
        
        # Command info card
        cmd_label = QLabel("Command:")
        cmd_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        self.cmd_value = QLabel("N/A")
        self.cmd_value.setFont(self.get_monospace_font())
        cards_layout.addWidget(cmd_label, 0, 0)
        cards_layout.addWidget(self.cmd_value, 0, 1)
        
        # Direction card
        dir_label = QLabel("Direction:")
        dir_label.setStyleSheet("font-weight: bold; color: #cc6600;")
        self.dir_value = QLabel("N/A")
        self.dir_value.setFont(self.get_monospace_font())
        cards_layout.addWidget(dir_label, 0, 2)
        cards_layout.addWidget(self.dir_value, 0, 3)
        
        # Status card
        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-weight: bold; color: #009966;")
        self.status_value = QLabel("N/A")
        self.status_value.setFont(self.get_monospace_font())
        cards_layout.addWidget(status_label, 1, 0)
        cards_layout.addWidget(self.status_value, 1, 1)
        
        # Key TLVs card
        tlv_label = QLabel("Key TLVs:")
        tlv_label.setStyleSheet("font-weight: bold; color: #9900cc;")
        self.tlv_value = QLabel("N/A")
        self.tlv_value.setFont(self.get_monospace_font())
        cards_layout.addWidget(tlv_label, 1, 2)
        cards_layout.addWidget(self.tlv_value, 1, 3)
        
        # Domain card  
        domain_label = QLabel("Domain:")
        domain_label.setStyleSheet("font-weight: bold; color: #cc0066;")
        self.domain_value = QLabel("N/A")
        self.domain_value.setFont(self.get_monospace_font())
        cards_layout.addWidget(domain_label, 2, 0)
        cards_layout.addWidget(self.domain_value, 2, 1)
        
        # Set column stretches
        cards_layout.setColumnStretch(1, 1)
        cards_layout.setColumnStretch(3, 1)
        
        return self.summary_group
    
    def get_monospace_font(self):
        """Get a monospace font for hex display."""
        from PySide6.QtGui import QFont, QFontDatabase
        
        # Try to find a good monospace font
        font = QFont()
        font.setFamily("Consolas")  # Windows
        if not QFontDatabase.hasFamily("Consolas"):
            font.setFamily("Monaco")  # macOS
        if not QFontDatabase.hasFamily("Monaco"):
            font.setFamily("DejaVu Sans Mono")  # Linux
        if not QFontDatabase.hasFamily("DejaVu Sans Mono"):
            font.setStyleHint(QFont.Monospace)
        
        font.setPointSize(10)
        return font
    
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Open action
        open_action = QAction("&Open XTI...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        # Open Recent submenu
        self.recent_files_menu = file_menu.addMenu("Open &Recent")
        self._populate_recent_files_menu()
        
        file_menu.addSeparator()
        
        # Export submenu
        export_menu = file_menu.addMenu("&Export")
        
        # Export comprehensive PDF report
        pdf_report_action = QAction("Comprehensive PDF Report...", self)
        pdf_report_action.triggered.connect(self.export_comprehensive_pdf_report)
        export_menu.addAction(pdf_report_action)
        
        # Export filtered interpretation
        filtered_interp_action = QAction("Filtered Interpretation (CSV)...", self)
        filtered_interp_action.triggered.connect(self.export_filtered_interpretation)
        export_menu.addAction(filtered_interp_action)
        
        # Export TLS session
        tls_export_action = QAction("TLS Session Details...", self)
        tls_export_action.triggered.connect(self.export_tls_session)
        export_menu.addAction(tls_export_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Settings menu
        settings_menu = menubar.addMenu("&Settings")
        
        # Preferences
        preferences_action = QAction("Preferences…", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self.open_preferences_dialog)
        settings_menu.addAction(preferences_action)
        
        settings_menu.addSeparator()
        
        # Network Classification
        net_class_action = QAction("Network Classification…", self)
        net_class_action.triggered.connect(self.open_network_settings_dialog)
        settings_menu.addAction(net_class_action)

        # Scenario menu
        scenario_menu = menubar.addMenu("&Scenario")
        run_scenario_action = QAction("Run Scenario…", self)
        run_scenario_action.triggered.connect(self.open_scenario_window)
        scenario_menu.addAction(run_scenario_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        # About
        about_action = QAction("About XTI Viewer…", self)
        about_action.triggered.connect(self.open_about_dialog)
        help_menu.addAction(about_action)

    def open_scenario_window(self):
        """Open the Scenario validation window."""
        try:
            from .scenario_window import ScenarioWindow
        except Exception as e:
            try:
                show_error_dialog(self, "Scenario", f"Unable to open Scenario window: {e}")
            except Exception:
                pass
            return

        try:
            dlg = ScenarioWindow(self, main_window=self)
            dlg.show()
        except Exception as e:
            try:
                show_error_dialog(self, "Scenario", f"Scenario window error: {e}")
            except Exception:
                pass

    def _populate_recent_files_menu(self):
        """Populate the Open Recent submenu from persisted settings."""
        try:
            menu = getattr(self, "recent_files_menu", None)
            if menu is None:
                return
            menu.clear()

            recent_files = []
            try:
                recent_files = self.settings.get_recent_files()
            except Exception:
                recent_files = []

            # Keep only existing paths
            existing = []
            for p in recent_files:
                try:
                    if p and os.path.exists(p):
                        existing.append(p)
                except Exception:
                    continue

            # If we dropped missing files, persist the cleaned list
            try:
                if existing != recent_files:
                    self.settings.set_recent_files(existing)
            except Exception:
                pass

            if not existing:
                empty_action = QAction("(No recent files)", self)
                empty_action.setEnabled(False)
                menu.addAction(empty_action)
                return

            for path in existing:
                label = os.path.basename(path) or path
                act = QAction(label, self)
                act.setToolTip(path)
                act.triggered.connect(lambda checked=False, p=path: self.open_recent_file(p))
                menu.addAction(act)

            menu.addSeparator()
            clear_action = QAction("Clear Recent Files", self)
            clear_action.triggered.connect(self.clear_recent_files)
            menu.addAction(clear_action)
        except Exception:
            # Menu population must never break app startup
            pass

    def open_recent_file(self, file_path: str):
        """Open a file from the recent files list."""
        try:
            if not file_path or not os.path.exists(file_path):
                try:
                    show_error_dialog(self, "File Not Found", f"Cannot find file:\n{file_path}")
                except Exception:
                    pass
                # Remove missing file from list
                try:
                    recent = self.settings.get_recent_files()
                    cleaned = [p for p in recent if p and os.path.normcase(p) != os.path.normcase(file_path)]
                    self.settings.set_recent_files(cleaned)
                    self._populate_recent_files_menu()
                except Exception:
                    pass
                return

            self.load_xti_file(file_path)
        except Exception as e:
            try:
                show_error_dialog(self, "Open Recent Error", f"Unable to open file: {e}")
            except Exception:
                pass

    def clear_recent_files(self):
        """Clear the recent files list."""
        try:
            self.settings.clear_recent_files()
        except Exception:
            pass
        self._populate_recent_files_menu()

    def open_preferences_dialog(self):
        """Open the Preferences dialog."""
        try:
            from xti_viewer.preferences_dialog import PreferencesDialog
        except Exception as e:
            try:
                show_error_dialog(self, f"Unable to open preferences dialog: {e}")
            except Exception:
                pass
            return
        try:
            dlg = PreferencesDialog(self)
            if dlg.exec() == dlg.Accepted:
                try:
                    self.statusBar().showMessage("Preferences saved", 3000)
                    # Could apply settings here if needed
                except Exception:
                    pass
        except Exception as e:
            try:
                show_error_dialog(self, f"Preferences dialog error: {e}")
            except Exception:
                pass
    
    def open_about_dialog(self):
        """Open the About dialog."""
        try:
            from xti_viewer.about_dialog import AboutDialog
        except Exception as e:
            try:
                show_error_dialog(self, f"Unable to open about dialog: {e}")
            except Exception:
                pass
            return
        try:
            dlg = AboutDialog(self)
            dlg.exec()
        except Exception as e:
            try:
                show_error_dialog(self, f"About dialog error: {e}")
            except Exception:
                pass

    def open_network_settings_dialog(self):
        """Open the Network Classification Settings dialog."""
        try:
            from network_settings_dialog import NetworkSettingsDialog
        except Exception as e:
            try:
                show_error_dialog(self, f"Unable to open settings dialog: {e}")
            except Exception:
                pass
            return
        try:
            dlg = NetworkSettingsDialog(self)
            if dlg.exec() == dlg.Accepted:
                try:
                    self.statusBar().showMessage("Network classification settings updated", 3000)
                except Exception:
                    pass
        except Exception as e:
            try:
                show_error_dialog(self, f"Settings dialog error: {e}")
            except Exception:
                pass
    
    def export_comprehensive_pdf_report(self):
        """Export comprehensive PDF report combining Flow Overview, Parsing Log, and TLS details."""
        if not self.parser:
            show_info_dialog(self, "No Data", "No data to export. Please open an XTI file first.")
            return
        
        # Get save file path
        default_name = "xti_comprehensive_report.pdf"
        if self.current_file_path:
            base_name = Path(self.current_file_path).stem
            default_name = f"{base_name}_report.pdf"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Comprehensive PDF Report",
            default_name,
            "PDF Files (*.pdf);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Try to import reportlab
            try:
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Preformatted
                from reportlab.lib import colors
                from reportlab.lib.enums import TA_CENTER, TA_LEFT
            except ImportError:
                show_error_dialog(
                    self,
                    "Missing Dependency",
                    "PDF export requires the 'reportlab' library.\n\n"
                    "Install it with: pip install reportlab"
                )
                return
            
            # Create PDF document
            doc = SimpleDocTemplate(file_path, pagesize=letter,
                                   rightMargin=0.75*inch, leftMargin=0.75*inch,
                                   topMargin=0.75*inch, bottomMargin=0.75*inch)
            
            # Container for the 'Flowable' objects
            elements = []
            
            # Define styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#2196F3'),
                spaceAfter=12,
                spaceBefore=12
            )
            subheading_style = ParagraphStyle(
                'CustomSubHeading',
                parent=styles['Heading3'],
                fontSize=12,
                textColor=colors.HexColor('#666'),
                spaceAfter=6
            )
            
            # Title
            title_text = "XTI Viewer - Comprehensive Analysis Report"
            elements.append(Paragraph(title_text, title_style))
            elements.append(Spacer(1, 0.2*inch))
            
            # File information
            if self.current_file_path:
                file_info = f"<b>File:</b> {Path(self.current_file_path).name}<br/>"
                file_info += f"<b>Path:</b> {self.current_file_path}<br/>"
                from PySide6.QtCore import QDateTime
                file_info += f"<b>Generated:</b> {QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')}"
                elements.append(Paragraph(file_info, styles['Normal']))
                elements.append(Spacer(1, 0.3*inch))
            
            # Section 1: Flow Overview
            elements.append(Paragraph("Flow Overview", heading_style))
            elements.append(Spacer(1, 0.1*inch))
            
            groups = self.parser.get_channel_groups()
            if groups:
                # Build timeline data
                timeline_data = []
                for item in self.timeline_model.timeline_items:
                    if item.get("kind") == "Session":
                        timeline_data.append([
                            item.get("type", "")[:15],
                            item.get("label", "")[:40],
                            item.get("port", ""),
                            item.get("protocol", ""),
                            item.get("opened", ""),
                            item.get("duration", "")
                        ])
                
                if timeline_data:
                    # Add table header
                    timeline_data.insert(0, ["Type", "Server/Label", "Port", "Protocol", "Opened", "Duration"])
                    
                    # Create table
                    t = Table(timeline_data, colWidths=[0.8*inch, 2.5*inch, 0.6*inch, 0.8*inch, 1.2*inch, 0.8*inch])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
                    ]))
                    elements.append(t)
            else:
                elements.append(Paragraph("No sessions found.", styles['Normal']))
            
            elements.append(PageBreak())
            
            # Section 2: Parsing Log
            elements.append(Paragraph("Parsing Log (Validation Issues)", heading_style))
            elements.append(Spacer(1, 0.1*inch))
            
            # Get validation issues
            issues = self.validation_manager.get_all_issues()
            if issues:
                log_data = [["Severity", "Category", "Message", "Index"]]
                for issue in issues[:100]:  # Limit to first 100 issues
                    log_data.append([
                        issue.severity.value,
                        issue.category[:30],
                        issue.message[:60],
                        str(issue.trace_item_index) if issue.trace_item_index is not None else ""
                    ])
                
                t = Table(log_data, colWidths=[0.9*inch, 1.5*inch, 3.2*inch, 0.6*inch])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff9800')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
                ]))
                elements.append(t)
                
                if len(issues) > 100:
                    elements.append(Spacer(1, 0.1*inch))
                    elements.append(Paragraph(f"<i>Showing first 100 of {len(issues)} total issues.</i>", styles['Normal']))
            else:
                elements.append(Paragraph("No validation issues found.", styles['Normal']))
            
            elements.append(PageBreak())
            
            # Section 3: TLS Sessions Summary
            elements.append(Paragraph("TLS Sessions Summary", heading_style))
            elements.append(Spacer(1, 0.1*inch))
            
            tls_sessions = [item for item in self.timeline_model.timeline_items 
                           if item.get("kind") == "Session" and item.get("protocol") in ["TLS", "HTTPS"]]
            
            if tls_sessions:
                for idx, session in enumerate(tls_sessions[:10], 1):
                    elements.append(Paragraph(f"<b>Session {idx}: {session.get('label', 'Unknown')}</b>", subheading_style))
                    
                    session_info = f"<b>Port:</b> {session.get('port', 'N/A')}<br/>"
                    session_info += f"<b>Protocol:</b> {session.get('protocol', 'N/A')}<br/>"
                    session_info += f"<b>Opened:</b> {session.get('opened', 'N/A')}<br/>"
                    session_info += f"<b>Closed:</b> {session.get('closed', 'N/A')}<br/>"
                    session_info += f"<b>Duration:</b> {session.get('duration', 'N/A')}"
                    
                    elements.append(Paragraph(session_info, styles['Normal']))
                    elements.append(Spacer(1, 0.15*inch))
                
                if len(tls_sessions) > 10:
                    elements.append(Paragraph(f"<i>Showing first 10 of {len(tls_sessions)} TLS sessions.</i>", styles['Normal']))
            else:
                elements.append(Paragraph("No TLS sessions found.", styles['Normal']))
            
            # Build PDF
            doc.build(elements)
            
            show_info_dialog(self, "Export Complete", f"Comprehensive PDF report exported to:\n{file_path}")
            
        except Exception as e:
            show_error_dialog(self, "Export Failed", f"Failed to export PDF report:\n{str(e)}")

    def export_filtered_interpretation(self):
        """Export currently filtered interpretation view to CSV."""
        if not self.parser or not self.trace_items:
            show_info_dialog(self, "No Data", "No data to export. Please open an XTI file first.")
            return
        
        # Get save file path
        default_name = "filtered_interpretation.csv"
        if self.current_file_path:
            base_name = Path(self.current_file_path).stem
            default_name = f"{base_name}_filtered.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Filtered Interpretation",
            default_name,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            import csv

            row_count = self.filter_model.rowCount()
            if row_count <= 0:
                show_info_dialog(self, "No Data", "No items match the current filter.")
                return
            
            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    "Row",
                    "Timestamp",
                    "Protocol",
                    "Type",
                    "Summary",
                    "Raw Hex (Command)",
                    "Raw Hex (Response)"
                ])
                
                exported = 0
                for row in range(row_count):
                    # UI column mapping (see create_interpretation_tab header config)
                    summary = self.filter_model.data(self.filter_model.index(row, 0), Qt.DisplayRole) or ""
                    protocol = self.filter_model.data(self.filter_model.index(row, 1), Qt.DisplayRole) or ""
                    typ = self.filter_model.data(self.filter_model.index(row, 2), Qt.DisplayRole) or ""
                    ts = self.filter_model.data(self.filter_model.index(row, 3), Qt.DisplayRole) or ""

                    # Use the actual tree node, not src_index.row() into trace_model.trace_items
                    src_index = self.filter_model.mapToSource(self.filter_model.index(row, 0))
                    tree_item = src_index.internalPointer() if src_index.isValid() else None
                    raw_cmd = ""
                    raw_rsp = ""
                    try:
                        if tree_item and getattr(tree_item, 'trace_item', None) and getattr(tree_item.trace_item, 'rawhex', None):
                            raw_cmd = tree_item.trace_item.rawhex or ""
                        if tree_item and getattr(tree_item, 'response_item', None) and getattr(tree_item.response_item, 'rawhex', None):
                            raw_rsp = tree_item.response_item.rawhex or ""
                    except Exception:
                        pass

                    writer.writerow([
                        row + 1,
                        ts,
                        protocol,
                        typ,
                        summary,
                        raw_cmd,
                        raw_rsp,
                    ])
                    exported += 1
            
            # Show summary of what was exported
            filter_info = []
            if self.search_edit.text():
                filter_info.append(f"Search: '{self.search_edit.text()}'")
            if hasattr(self, 'server_combo') and self.server_combo.currentText() != "All Servers":
                filter_info.append(f"Server: {self.server_combo.currentText()}")
            
            filter_desc = f" (Filters: {', '.join(filter_info)})" if filter_info else ""
            
            show_info_dialog(
                self,
                "Export Complete",
                f"Exported {exported} items to:\n{file_path}\n{filter_desc}"
            )
            
        except Exception as e:
            show_error_dialog(self, "Export Failed", f"Failed to export filtered interpretation:\n{str(e)}")

    def export_tls_session(self):
        """Export TLS session details in multiple formats."""
        if not self.parser:
            show_info_dialog(self, "No Data", "No data to export. Please open an XTI file first.")
            return
        
        # Get TLS sessions
        tls_sessions = [item for item in self.timeline_model.timeline_items 
                       if item.get("kind") == "Session" and item.get("protocol") in ["TLS", "HTTPS"]]
        
        if not tls_sessions:
            show_info_dialog(self, "No TLS Sessions", "No TLS sessions found to export.")
            return
        
        # Use first TLS session (TODO: Add session selection dialog)
        session_data = tls_sessions[0]
        
        # Get save file path with format selection
        default_name = "tls_session_export"
        if self.current_file_path:
            base_name = Path(self.current_file_path).stem
            default_name = f"{base_name}_tls"
        
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export TLS Session",
            default_name,
            "JSON Format (*.json);;Text Format (*.txt);;Markdown Format (*.md);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Determine format from filter or extension
            fmt = "txt"
            if ".json" in selected_filter or file_path.endswith(".json"):
                fmt = "json"
            elif ".md" in selected_filter or file_path.endswith(".md"):
                fmt = "md"
            
            # Gather TLS session data
            tls_data = {
                "session": {
                    "label": session_data.get("label", "Unknown"),
                    "port": session_data.get("port", ""),
                    "protocol": session_data.get("protocol", ""),
                    "server": session_data.get("server", ""),
                    "opened": session_data.get("opened", ""),
                    "closed": session_data.get("closed", ""),
                    "duration": session_data.get("duration", ""),
                    "ips": session_data.get("ips", [])
                },
                "messages": []
            }
            
            # Get trace items for this session
            if "trace_items" in session_data:
                for item in session_data.get("trace_items", []):
                    tls_data["messages"].append({
                        "timestamp": item.timestamp or "",
                        "type": item.type or "",
                        "summary": item.summary or "",
                        "rawhex": item.rawhex or ""
                    })
            
            # Export in selected format
            if fmt == "json":
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(tls_data, f, indent=2)
            
            elif fmt == "md":
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# TLS Session Export\n\n")
                    f.write(f"## Session Information\n\n")
                    f.write(f"- **Server:** {tls_data['session']['label']}\n")
                    f.write(f"- **Port:** {tls_data['session']['port']}\n")
                    f.write(f"- **Protocol:** {tls_data['session']['protocol']}\n")
                    f.write(f"- **Opened:** {tls_data['session']['opened']}\n")
                    f.write(f"- **Closed:** {tls_data['session']['closed']}\n")
                    f.write(f"- **Duration:** {tls_data['session']['duration']}\n\n")
                    
                    if tls_data['messages']:
                        f.write(f"## Messages ({len(tls_data['messages'])} total)\n\n")
                        for idx, msg in enumerate(tls_data['messages'], 1):
                            f.write(f"### Message {idx}\n\n")
                            f.write(f"- **Time:** {msg['timestamp']}\n")
                            f.write(f"- **Type:** {msg['type']}\n")
                            f.write(f"- **Summary:** {msg['summary']}\n")
                            if msg['rawhex']:
                                f.write(f"- **Raw Hex:** `{msg['rawhex'][:80]}...`\n")
                            f.write("\n")
            
            else:  # txt format
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=" * 70 + "\n")
                    f.write("TLS SESSION EXPORT\n")
                    f.write("=" * 70 + "\n\n")
                    f.write(f"Server:   {tls_data['session']['label']}\n")
                    f.write(f"Port:     {tls_data['session']['port']}\n")
                    f.write(f"Protocol: {tls_data['session']['protocol']}\n")
                    f.write(f"Opened:   {tls_data['session']['opened']}\n")
                    f.write(f"Closed:   {tls_data['session']['closed']}\n")
                    f.write(f"Duration: {tls_data['session']['duration']}\n")
                    f.write("\n" + "-" * 70 + "\n")
                    f.write(f"MESSAGES ({len(tls_data['messages'])} total)\n")
                    f.write("-" * 70 + "\n\n")
                    
                    for idx, msg in enumerate(tls_data['messages'], 1):
                        f.write(f"[{idx}] {msg['timestamp']} - {msg['type']}\n")
                        f.write(f"    {msg['summary']}\n")
                        if msg['rawhex']:
                            f.write(f"    Hex: {msg['rawhex'][:60]}...\n")
                        f.write("\n")
            
            show_info_dialog(
                self,
                "Export Complete",
                f"TLS session exported to:\n{file_path}\n\nFormat: {fmt.upper()}"
            )
            
        except Exception as e:
            show_error_dialog(self, "Export Failed", f"Failed to export TLS session:\n{str(e)}")
    
    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar = self.statusBar()
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Add permanent widgets for item info and hex selection
        self.hex_selection_label = QLabel("Selection: 0 bytes")
        self.item_count_label = QLabel("Items: 0")
        self.current_item_label = QLabel("")
        self.status_bar.addPermanentWidget(self.hex_selection_label)
        self.status_bar.addPermanentWidget(self.current_item_label)
        self.status_bar.addPermanentWidget(self.item_count_label)
    
    def setup_connections(self):
        """Set up signal-slot connections."""
        # Search box
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        
        # Clear filter button
        self.clear_filter_button.clicked.connect(self.clear_command_family_filter)
        
        # Navigation buttons
        self.prev_match_button.clicked.connect(self.go_to_prev_match)
        self.next_match_button.clicked.connect(self.go_to_next_match)
        
        # Table selection (single-click for highlighting)
        selection_model = self.trace_table.selectionModel()
        selection_model.currentRowChanged.connect(self.on_selection_changed)
        
        # Double-click for filtering command family
        self.trace_table.doubleClicked.connect(self.on_table_double_click)
        
        # Single-click for highlighting command family
        self.trace_table.clicked.connect(self.on_table_single_click)
        
        # Copy button
        self.copy_button.clicked.connect(self.copy_hex_to_clipboard)
        
        # Flow timeline selection
        # Avoid Qt warnings by not disconnecting blindly; use UniqueConnection
        try:
            self.timeline_table.clicked.connect(self.on_timeline_clicked, Qt.UniqueConnection)
        except Exception:
            # Fallback: normal connect (Qt will dedupe in many cases)
            self.timeline_table.clicked.connect(self.on_timeline_clicked)
        try:
            self.timeline_table.doubleClicked.connect(self.on_timeline_double_clicked, Qt.UniqueConnection)
        except Exception:
            self.timeline_table.doubleClicked.connect(self.on_timeline_double_clicked)
        
        # TLV tree interactions
        self.tlv_tree.itemClicked.connect(self.on_tlv_item_clicked)
        self.tlv_tree.itemDoubleClicked.connect(self.on_tlv_item_double_clicked)
        # Steps selection preview
        try:
            self.tls_tree.itemSelectionChanged.connect(self._on_tls_step_selected)
        except Exception:
            pass
        # Overview tab action buttons
        try:
            if hasattr(self, 'btn_copy_overview'):
                self.btn_copy_overview.clicked.connect(self._copy_overview_to_clipboard)
        except Exception:
            pass
        try:
            if hasattr(self, 'btn_export_overview'):
                self.btn_export_overview.clicked.connect(self._export_overview_markdown)
        except Exception:
            pass
        # Security tab action buttons
        try:
            if hasattr(self, 'btn_copy_security'):
                self.btn_copy_security.clicked.connect(self._copy_security_to_clipboard)
        except Exception:
            pass
        # Raw contextual filter (now in Security tab)
        try:
            self.raw_context_toggle.toggled.connect(self._update_raw_context_view)
            self.raw_context_window.valueChanged.connect(self._update_raw_context_view)
        except Exception:
            pass
        
        # Parsing log navigation: only on double-click (disable single-click nav)
        # self.parsing_log_tree.itemClicked.connect(self.on_parsing_log_item_clicked)
        self.parsing_log_tree.itemDoubleClicked.connect(self.on_parsing_log_item_clicked)
        
        # Command/Response pairing navigation
        self.goto_paired_button.clicked.connect(self.navigate_to_paired_item)
        
        # Hex text selection changed
        self.hex_text.selectionChanged.connect(self.on_hex_selection_changed)
        
        # Keyboard navigation
        self.trace_table.keyPressEvent = self.table_key_press_event

    def on_hex_mouse_press(self, event):
        """Handle mouse press in the hex view.
        - Preserve default QTextEdit behavior
        - Optionally trigger selection sync logic after the event
        """
        try:
            from PySide6.QtWidgets import QTextEdit
            # Call the default handler to keep cursor/selection behavior
            QTextEdit.mousePressEvent(self.hex_text, event)
        except Exception:
            pass
        # Let Qt settle, then run any selection-sync logic if present
        try:
            QTimer.singleShot(0, getattr(self, 'on_hex_selection_changed', lambda: None))
        except Exception:
            pass

    def copy_hex_to_clipboard(self):
        """Copy the current Hex tab content to the clipboard."""
        try:
            text = self.hex_text.toPlainText() if hasattr(self, 'hex_text') else ""
            QApplication.clipboard().setText(text or "")
            # Optional: flash status bar
            if hasattr(self, 'status_label'):
                self.status_label.setText("Hex copied to clipboard")
        except Exception:
            pass

    def on_tlv_item_clicked(self, item, column):
        """When a TLV row is clicked, show its full value in the detail view."""
        try:
            value = item.text(3) if hasattr(item, 'text') else ""
            if hasattr(self, 'tlv_detail_view'):
                self.tlv_detail_view.setPlainText(value or "")
        except Exception:
            pass

    def on_tlv_item_double_clicked(self, item, column):
        """Double-click on TLV: copy the value to clipboard for convenience."""
        try:
            value = item.text(3) if hasattr(item, 'text') else ""
            QApplication.clipboard().setText(value or "")
            if hasattr(self, 'status_label'):
                self.status_label.setText("TLV value copied")
        except Exception:
            pass

    def on_parsing_log_item_clicked(self, item, column):
        """Jump to the trace index referenced by the parsing log row."""
        try:
            idx_text = item.text(3)
            src_row = int(idx_text)
        except Exception:
            return
        # Switch to Interpretation tab so the jump is visible
        try:
            self.tab_widget.setCurrentIndex(0)
        except Exception:
            pass
        # Prefer object-identity navigation for speed/robustness
        try:
            target_item = None
            if hasattr(self, 'parser') and self.parser and 0 <= src_row < len(self.parser.trace_items):
                target_item = self.parser.trace_items[src_row]
        except Exception:
            target_item = None
        if target_item is not None:
            # Fast path: no filter clear if already visible
            QTimer.singleShot(0, lambda ti=target_item: self._navigate_to_item_fast(ti))
        else:
            # Fallback to row-based navigation
            QTimer.singleShot(0, lambda r=src_row: self._complete_navigation(r))

    def on_hex_selection_changed(self):
        """Update status bar with current hex selection size in bytes."""
        try:
            cursor = self.hex_text.textCursor()
            sel = cursor.selectedText() or ""
            # QTextEdit uses U+2029 as line break in selectedText
            sel = sel.replace('\u2029', ' ')
            # Keep only hex digits and spaces
            filtered = ''.join(ch if ch in '0123456789abcdefABCDEF ' else ' ' for ch in sel)
            tokens = [t for t in filtered.split() if t]
            # If tokens are byte pairs without spaces, split into pairs
            byte_count = 0
            for t in tokens:
                s = t.strip()
                if len(s) % 2 == 0 and all(c in '0123456789abcdefABCDEF' for c in s):
                    byte_count += len(s) // 2
            if hasattr(self, 'hex_selection_label'):
                self.hex_selection_label.setText(f"Selection: {byte_count} bytes")
        except Exception:
            pass
    
    def table_key_press_event(self, event):
        """Handle key press events in the tree view."""
        # Handle custom shortcuts first
        try:
            from PySide6.QtGui import QKeySequence
            if event.matches(QKeySequence.Copy):
                self._copy_selected_interpretation_rows_to_clipboard()
                return
        except Exception:
            if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
                self._copy_selected_interpretation_rows_to_clipboard()
                return

        if event.key() == Qt.Key_G and event.modifiers() == Qt.ControlModifier:
            # Ctrl+G pour naviguer vers l'item pairé
            self.navigate_to_paired_item()
            return
        elif event.key() == Qt.Key_F2:
            # F2 for previous filter match
            self.go_to_prev_match()
            return
        elif event.key() == Qt.Key_F3:
            # F3 for next filter match
            self.go_to_next_match()
            return
        elif event.key() == Qt.Key_Up and event.modifiers() == Qt.AltModifier:
            # Alt+↑ pour naviguer vers l'item précédent dans la même session
            self.navigate_same_session_previous()
            return
        elif event.key() == Qt.Key_Down and event.modifiers() == Qt.AltModifier:
            # Alt+↓ pour naviguer vers l'item suivant dans la même session
            self.navigate_same_session_next()
            return
        
        # Call the original key press event
        QTreeView.keyPressEvent(self.trace_table, event)
        
        # Handle our custom keys for navigation
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            # Update selection immediately
            QTimer.singleShot(0, self.update_selection_from_current)
    
    def update_selection_from_current(self):
        """Update selection based on current table index."""
        current_index = self.trace_table.currentIndex()
        if current_index.isValid():
            self.on_selection_changed(current_index, None)

    def _copy_selected_interpretation_rows_to_clipboard(self) -> None:
        """Copy selected Interpretation rows to clipboard.

        Output is TSV so it pastes cleanly into Excel.
        """
        try:
            view = getattr(self, 'trace_table', None)
            model = getattr(self, 'filter_model', None)
            if view is None or model is None:
                return
            sel = view.selectionModel()
            if sel is None:
                return

            row_indexes = sel.selectedRows()
            if not row_indexes:
                cur = view.currentIndex()
                if cur.isValid():
                    row_indexes = [cur]
            if not row_indexes:
                return

            row_indexes = sorted(row_indexes, key=lambda idx: idx.row())
            col_count = model.columnCount()
            lines = []
            for idx in row_indexes:
                r = idx.row()
                cols = []
                for c in range(col_count):
                    try:
                        v = model.data(model.index(r, c), Qt.DisplayRole)
                    except Exception:
                        v = ''
                    cols.append(str(v or '').replace('\r', ' ').replace('\n', ' '))
                lines.append('\t'.join(cols).rstrip())

            QApplication.clipboard().setText('\n'.join(lines))
        except Exception:
            pass

    def on_trace_table_context_menu(self, pos):
        """Show context menu for interpretation list with copy actions."""
        index = self.trace_table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)
        act_copy_text = QAction("Copy Interpretation Text", self)
        act_copy_hex = QAction("Copy Raw Hex", self)
        menu.addAction(act_copy_text)
        menu.addAction(act_copy_hex)

        # Resolve selected/filter index and source tree item
        filter_index = self.trace_table.currentIndex() if self.trace_table.currentIndex().isValid() else index
        source_index = self.filter_model.mapToSource(filter_index)
        tree_item = source_index.internalPointer() if source_index.isValid() else None

        # Prepare text to copy
        display_text = self.filter_model.data(filter_index, Qt.DisplayRole) or ""

        # Prepare hex to copy (from command and paired response if available)
        hex_candidates = []
        if tree_item:
            if getattr(tree_item, 'trace_item', None) and getattr(tree_item.trace_item, 'rawhex', None):
                hex_candidates.append(tree_item.trace_item.rawhex)
            if getattr(tree_item, 'response_item', None) and getattr(tree_item.response_item, 'rawhex', None):
                hex_candidates.append(tree_item.response_item.rawhex)
        hex_text = "\n".join([h for h in hex_candidates if h])

        # Disable hex action if nothing to copy
        if not hex_text:
            act_copy_hex.setEnabled(False)

        def do_copy_text():
            try:
                sel = self.trace_table.selectionModel()
                if sel and len(sel.selectedRows()) > 1:
                    self._copy_selected_interpretation_rows_to_clipboard()
                    return
            except Exception:
                pass
            QApplication.clipboard().setText(display_text)

        def do_copy_hex():
            if hex_text:
                QApplication.clipboard().setText(hex_text)

        act_copy_text.triggered.connect(do_copy_text)
        act_copy_hex.triggered.connect(do_copy_hex)
        menu.exec(self.trace_table.viewport().mapToGlobal(pos))

    def on_inspector_tree_context_menu(self, pos):
        """Show context menu for inspector tree with copy actions."""
        index = self.inspector_tree.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)
        act_copy_sel = QAction("Copy Selected", self)
        act_copy_subtree = QAction("Copy Selected Subtree", self)
        act_copy_all = QAction("Copy All", self)
        menu.addAction(act_copy_sel)
        menu.addAction(act_copy_subtree)
        menu.addSeparator()
        menu.addAction(act_copy_all)

        def get_text(idx):
            return self.inspector_model.data(idx, Qt.DisplayRole) or ""

        def build_subtree_text(idx, indent=""):
            lines = [indent + (get_text(idx) or "").rstrip()]
            rows = self.inspector_model.rowCount(idx)
            for r in range(rows):
                child = self.inspector_model.index(r, 0, idx)
                if child.isValid():
                    lines.append(build_subtree_text(child, indent + "  "))
            return "\n".join(lines)

        def build_all_text():
            root = self.inspector_model.index(0, 0)
            if root.isValid():
                return build_subtree_text(root, "")
            return ""

        def do_copy_sel():
            QApplication.clipboard().setText(get_text(index))

        def do_copy_subtree():
            QApplication.clipboard().setText(build_subtree_text(index, ""))

        def do_copy_all():
            QApplication.clipboard().setText(build_all_text())

        act_copy_sel.triggered.connect(do_copy_sel)
        act_copy_subtree.triggered.connect(do_copy_subtree)
        act_copy_all.triggered.connect(do_copy_all)
        menu.exec(self.inspector_tree.viewport().mapToGlobal(pos))
    
    def open_file(self):
        """Open an XTI file."""
        last_dir = self.settings.get_last_directory()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open XTI File",
            last_dir,
            "XTI Files (*.xti);;All Files (*)"
        )
        
        if file_path:
            self.load_xti_file(file_path)
    
    def load_xti_file(self, file_path: str):
        """Load an XTI file in background thread."""
        # Validate file first
        is_valid, error_msg = validate_xti_file(file_path)
        if not is_valid:
            show_error_dialog(self, "Invalid File", f"Cannot open file: {error_msg}")
            return
        
        # Update settings
        self.settings.set_last_directory(os.path.dirname(file_path))
        try:
            self.settings.add_recent_file(file_path, max_items=10)
        except Exception:
            pass
        self._populate_recent_files_menu()
        self.current_file_path = file_path
        
        # Show progress dialog
        self.progress_dialog = QProgressDialog("Loading XTI file...", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.show()
        
        # Start parsing in background thread
        self.parser_thread = XTIParserThread(file_path)
        self.parser_thread.finished.connect(self.on_parsing_finished)
        self.parser_thread.error.connect(self.on_parsing_error)
        self.progress_dialog.canceled.connect(self.cancel_parsing)
        self.parser_thread.start()
        
        # Update status
        self.status_label.setText(f"Loading {os.path.basename(file_path)}...")
    
    def cancel_parsing(self):
        """Cancel the parsing operation."""
        if self.parser_thread and self.parser_thread.isRunning():
            self.parser_thread.terminate()
            self.parser_thread.wait()
        self.status_label.setText("Loading cancelled")
    
    def on_parsing_finished(self, parser: XTIParser):
        """Handle successful parsing completion."""
        self.progress_dialog.close()
        
        self.trace_items = parser.trace_items
        self.parser = parser  # Store parser instance for channel groups
        
        # Run validation on parsed trace items
        self.validation_manager = ValidationManager()  # Reset validation
        for index, trace_item in enumerate(parser.trace_items):
            self.validation_manager.validate_trace_item(trace_item, index)
        
        # Finalize validation to check for unclosed resources
        self.validation_manager.finalize_validation()
        
        # Update parsing log
        self.update_parsing_log()
        
        # Update trace model and store parser for session analysis
        self.trace_model.parser = parser
        self.trace_model.load_trace_items(parser.trace_items)
        # Rebuild fast lookup cache for quick navigation
        self._rebuild_interpretation_index_cache()
        
        # Initialize time range based on loaded trace items
        self.initialize_time_range()
        
        # Build unified flow timeline: sessions + key events
        self.populate_flow_timeline(parser)
        
        # Update status
        self.status_label.setText(f"Loaded {os.path.basename(self.current_file_path)}")
        self.update_item_count_display()
        
        # Update window title
        filename = os.path.basename(self.current_file_path)
        self.setWindowTitle(f"XTI Viewer - {filename}")
        
        # Clear selection and filters
        self.clear_selection()
        self.clear_command_family_filter()

    def _rebuild_interpretation_index_cache(self):
        """Build a fast mapping from TraceItem identity to source row.
        Includes both command and paired response items for combined rows.
        """
        self._traceitem_row_by_id.clear()
        try:
            row_count = self.trace_model.rowCount()
            for row in range(row_count):
                idx = self.trace_model.index(row, 0)
                tree_item = self.trace_model.get_tree_item(idx)
                if not tree_item:
                    continue
                # Map main trace item
                if getattr(tree_item, 'trace_item', None) is not None:
                    self._traceitem_row_by_id[id(tree_item.trace_item)] = row
                # Map paired/response item if present
                if getattr(tree_item, 'response_item', None) is not None:
                    self._traceitem_row_by_id[id(tree_item.response_item)] = row
        except Exception:
            # Cache is best-effort; fall back to linear search when needed
            pass
    
    def on_parsing_error(self, error_message: str):
        """Handle parsing error."""
        self.progress_dialog.close()
        
        show_error_dialog(
            self,
            "Parsing Error",
            "Failed to parse XTI file.",
            error_message
        )
        
        self.status_label.setText("Loading failed")
    
    def on_search_text_changed(self, text: str):
        """Handle search text changes and find matches for navigation."""
        search_text = text.strip()
        
        if search_text != self.last_filter_text:
            # New search, find all matches
            self.last_filter_text = search_text
            self.find_all_matches(search_text)
            self.current_match_index = -1
            
            if self.filter_matches:
                # Go to first match
                self.go_to_next_match()
            else:
                self.update_match_display()
        
        # Don't apply filtering - keep all items visible for navigation only
        
    def find_all_matches(self, search_text: str):
        """Find all items that match the search text."""
        self.filter_matches = []
        
        if not search_text:
            self.update_match_display()
            return
        
        search_lower = search_text.lower()
        
        # Search through all trace items
        for row in range(self.trace_model.rowCount()):
            index = self.trace_model.index(row, 0)
            trace_item = self.trace_model.get_trace_item(index)
            
            if trace_item:
                # Check summary, type, and protocol
                summary_text = (trace_item.summary or '').lower()
                type_text = (trace_item.type or '').lower()
                protocol_text = (trace_item.protocol or '').lower()
                
                # Look for matches in individual fields
                if (search_lower in summary_text or 
                    search_lower in type_text or 
                    search_lower in protocol_text):
                    self.filter_matches.append(row)
        
        self.update_match_display()
    
    def go_to_next_match(self):
        """Navigate to the next match."""
        if not self.filter_matches:
            return
        
        self.current_match_index = (self.current_match_index + 1) % len(self.filter_matches)
        self.navigate_to_match()
    
    def go_to_prev_match(self):
        """Navigate to the previous match."""
        if not self.filter_matches:
            return
        
        self.current_match_index = (self.current_match_index - 1) % len(self.filter_matches)
        self.navigate_to_match()
    
    def navigate_to_match(self):
        """Navigate to the current match by temporarily bypassing filters."""
        if not self.filter_matches or self.current_match_index < 0:
            return
        
        # Get the row index from our search results
        source_row = self.filter_matches[self.current_match_index]
        
        # Bypass filter model entirely for navigation
        # Clear all filters first to ensure the item becomes visible
        self.filter_model.clear_all_filters()
        
        # Give the filter model time to update
        QTimer.singleShot(10, lambda: self._complete_navigation(source_row))
        
    def _complete_navigation(self, source_row: int):
        """Complete the navigation after filters are cleared."""
        filter_model = self.trace_table.model()
        
        # Look for the source row in the now-cleared filter model
        for filter_row in range(filter_model.rowCount()):
            filter_index = filter_model.index(filter_row, 0)
            source_index = filter_model.mapToSource(filter_index)
            
            if source_index.isValid() and source_index.row() == source_row:
                # Found it, select and scroll
                self.trace_table.setCurrentIndex(filter_index)
                self.trace_table.scrollTo(filter_index, QAbstractItemView.PositionAtCenter)
                
                # Hide clear filter button since we cleared all filters
                self.clear_filter_button.setVisible(False)
                self.update_item_count_display()
                self.update_match_display()
                return
        
        # If still not found, there might be a deeper issue
        # Let's just show a message and continue
        self.update_match_display()
    
    def update_match_display(self):
        """Update the match counter display."""
        if not hasattr(self, 'filter_status_label'):
            return  # UI not fully initialized yet
            
        if not self.filter_matches:
            self.filter_status_label.setText("No matches")
            self.prev_match_button.setEnabled(False)
            self.next_match_button.setEnabled(False)
        else:
            current = self.current_match_index + 1 if self.current_match_index >= 0 else 0
            total = len(self.filter_matches)
            self.filter_status_label.setText(f"{current}/{total}")
            self.prev_match_button.setEnabled(True)
            self.next_match_button.setEnabled(True)
    
    def on_command_filter_changed(self):
        """Handle command type filter changes."""
        if not hasattr(self, 'filter_model') or not hasattr(self, 'command_checkboxes'):
            return
        
        # Get selected command types
        selected_commands = [key for key, checkbox in self.command_checkboxes.items() if checkbox.isChecked()]
        # Include extended types from actions (menu)
        if hasattr(self, 'command_actions'):
            for key, act in self.command_actions.items():
                try:
                    checked = act.isChecked()
                except Exception:
                    # Some bindings only provide triggered; assume checked when present in menu and action text toggled
                    checked = False
                if checked:
                    selected_commands.append(key)
        
        # Determine filter mode:
        # all selected => disable filtering (None)
        # none selected => empty list (filter matches nothing)
        total_types = len(self.command_checkboxes) + (len(self.command_actions) if hasattr(self, 'command_actions') else 0)
        if len(selected_commands) == total_types:
            selected_commands = None  # disabled
        elif len(selected_commands) == 0:
            selected_commands = []    # explicit none
        
        # Apply command type filter to filter model
        self.filter_model.set_command_type_filter(selected_commands)
        self.update_item_count_display()
    
    def on_server_filter_changed(self, server_name: str):
        """Handle server filter changes."""
        if not hasattr(self, 'filter_model'):
            return
            
        # Apply server filter to filter model
        self.filter_model.set_server_filter(server_name if server_name != "All Servers" else "")
        self.update_item_count_display()
    
    def on_time_range_changed(self):
        """Handle time range filter changes."""
        if not hasattr(self, 'filter_model') or not self.trace_start_time or not self.trace_end_time:
            return
        
        # Get selected time range
        start_time = self.start_time_edit.time()
        end_time = self.end_time_edit.time()
        
        # Apply time filter to filter model
        self.filter_model.set_time_range_filter(start_time, end_time)
        self.update_time_range_info()
        self.update_item_count_display()
    
    def reset_time_filter(self):
        """Reset time filter to show all time."""
        if not self.trace_start_time or not self.trace_end_time:
            return
            
        self.start_time_edit.setTime(self.trace_start_time)
        self.end_time_edit.setTime(self.trace_end_time)
        self.on_time_range_changed()
    
    def set_last_minutes(self, minutes: int):
        """Set time filter to show last N minutes."""
        if not self.trace_end_time:
            return
            
        # Calculate start time (N minutes before end time)
        end_time = self.trace_end_time
        start_time = end_time.addSecs(-minutes * 60)
        
        self.start_time_edit.setTime(start_time)
        self.end_time_edit.setTime(end_time)
        self.on_time_range_changed()
    
    def update_time_range_info(self):
        """Update the time range info label."""
        if not hasattr(self, 'time_range_info'):
            return
            
        start_time = self.start_time_edit.time()
        end_time = self.end_time_edit.time()
        
        if (self.trace_start_time and self.trace_end_time and
            start_time == self.trace_start_time and end_time == self.trace_end_time):
            self.time_range_info.setText("All time")
        else:
            duration_sec = start_time.secsTo(end_time)
            if duration_sec < 0:
                duration_sec += 24 * 60 * 60  # Handle day rollover
            
            if duration_sec < 60:
                duration_text = f"{duration_sec}s"
            elif duration_sec < 3600:
                duration_text = f"{duration_sec // 60}m {duration_sec % 60}s"
            else:
                hours = duration_sec // 3600
                minutes = (duration_sec % 3600) // 60
                duration_text = f"{hours}h {minutes}m"
            
            self.time_range_info.setText(f"Duration: {duration_text}")
    
    def initialize_time_range(self):
        """Initialize the time range based on loaded trace items."""
        if not hasattr(self, 'trace_items') or not self.trace_items:
            return
        
        # Find earliest and latest timestamps
        timestamps = []
        for item in self.trace_items:
            if item.timestamp:
                # Parse timestamp like "11/06/2025 16:55:31:742.000000"
                try:
                    import re
                    time_match = re.search(r'(\d{2}:\d{2}:\d{2})', item.timestamp)
                    if time_match:
                        time_str = time_match.group(1)
                        time_obj = QTime.fromString(time_str, "hh:mm:ss")
                        if time_obj.isValid():
                            timestamps.append(time_obj)
                except Exception:
                    continue
        
        if timestamps:
            self.trace_start_time = min(timestamps)
            self.trace_end_time = max(timestamps)
            
            # Set initial values
            self.start_time_edit.setTime(self.trace_start_time)
            self.end_time_edit.setTime(self.trace_end_time)
            
            self.update_time_range_info()
        else:
            # Fallback to default times
            self.trace_start_time = QTime(0, 0, 0)
            self.trace_end_time = QTime(23, 59, 59)
            
            self.start_time_edit.setTime(self.trace_start_time)
            self.end_time_edit.setTime(self.trace_end_time)
            
            self.time_range_info.setText("No timestamps found")
    
    def update_item_count_display(self):
        """Update the item count display in the status bar."""
        visible_count = self.filter_model.rowCount()
        total_count = len(self.trace_items)
        
        # Build status text based on active filters
        status_parts = []
        
        if self.filter_model.is_command_family_filtered():
            status_parts.append("Command Family Filtered")
        
        if self.search_edit.text().strip():
            status_parts.append("Text Filtered")
        
        if status_parts:
            filter_status = f" ({', '.join(status_parts)})"
            self.item_count_label.setText(f"Items: {visible_count}/{total_count}{filter_status}")
        else:
            self.item_count_label.setText(f"Items: {total_count}")
    
    def on_selection_changed(self, current, previous):
        """Handle selection change in the trace items table."""

        if not current.isValid():
            self.clear_selection()
            self.update_pairing_info(None)
            return

        # Get the trace item from the model
        source_index = self.filter_model.mapToSource(current)
        trace_item = self.trace_model.get_trace_item(source_index)

        # Remember user selection only when not in session/command-family filtering mode.
        # This preserves the "baseline" row so clearing a filter can jump back.
        try:
            if (hasattr(self, 'filter_model') and self.filter_model and
                    (not self.filter_model.is_session_filtered()) and
                    (not self.filter_model.is_command_family_filtered())):
                self._last_selected_source_row_unfiltered = int(source_index.row())
        except Exception:
            pass

        if trace_item:
            # Check if this is a combined entry with stored response item
            tree_item = self.trace_model.get_tree_item(source_index)
            
            if (tree_item and hasattr(tree_item, 'response_item') and 
                tree_item.response_item and tree_item.trace_item):
                # This is a combined FETCH-TERMINAL RESPONSE entry
                self.update_inspector_combined(tree_item.trace_item, tree_item.response_item)
                self.update_hex_view_combined(tree_item.trace_item, tree_item.response_item)
                # Update analyze tab with the response which contains the TLVs
                self.update_analyze_view(tree_item.response_item)
            else:
                # Single item or no pairing info
                self.update_inspector(trace_item)
                self.update_hex_view(trace_item)
                # Update analyze tab
                self.update_analyze_view(trace_item)
            
            self.update_current_item_status(trace_item)
            self.update_pairing_info(trace_item)

    def on_table_single_click(self, index):
        """Handle single-click on table row - highlight command family."""
        if not index.isValid():
            return
        
        # Get the trace item from the model
        source_index = self.filter_model.mapToSource(index)
        trace_item = self.trace_model.get_trace_item(source_index)
        
        if trace_item:
            # Highlight all items with the same summary
            self.trace_model.highlight_command_family(trace_item.summary)
    
    def on_table_double_click(self, index):
        """Handle double-click on an Interpretation row.

        Double-click should bring the Analyze tab to the front (and refresh it
        for the clicked row). It must NOT apply any filtering.
        """
        if not index.isValid():
            return
        
        # Get the trace item from the model
        source_index = self.filter_model.mapToSource(index)
        trace_item = self.trace_model.get_trace_item(source_index)

        if trace_item:
            # Ensure Analyze content reflects the clicked item even if selection didn't change
            try:
                tree_item = self.trace_model.get_tree_item(source_index)
                if (tree_item and hasattr(tree_item, 'response_item') and tree_item.response_item and
                        hasattr(tree_item, 'trace_item') and tree_item.trace_item):
                    # Combined FETCH + TERMINAL RESPONSE: analyze the response (contains TLVs)
                    self.update_analyze_view(tree_item.response_item)
                else:
                    self.update_analyze_view(trace_item)
            except Exception:
                pass

            # Bring Analyze to front
            try:
                if hasattr(self, 'hex_tab_widget'):
                    self.hex_tab_widget.setCurrentIndex(1)
            except Exception:
                pass
    
    def clear_command_family_filter(self):
        """Clear all filters and return to full list."""
        try:
            had_session_filter = bool(getattr(self, 'filter_model', None) and self.filter_model.is_session_filtered())
        except Exception:
            had_session_filter = False

        self.filter_model.clear_command_family_filter()
        self.filter_model.clear_session_filter()
        self.trace_model.clear_highlights()
        self.clear_filter_button.setVisible(False)
        
        # Clear navigation state but keep search text for re-searching
        search_text = self.search_edit.text()
        self.filter_matches = []
        self.current_match_index = -1
        self.last_filter_text = ""
        # Re-run search if there was search text
        if search_text.strip():
            # Re-run search on the now-unfiltered model
            self.on_search_text_changed(search_text)
            if self.filter_matches:
                self.go_to_next_match()
        
        self.update_match_display()
        
        # Update status to show unfiltered state
        self.update_item_count_display()

        # If we just cleared a session filter, reset TLS Flow so it doesn't keep showing
        # the previously-selected session's flow.
        if had_session_filter:
            try:
                self._current_session_data = None
            except Exception:
                pass
            try:
                self._reset_tls_flow_placeholders(None)
            except Exception:
                pass

        # Restore last unfiltered selection (best-effort)
        try:
            self._restore_last_selected_interpretation_row()
        except Exception:
            pass

    def update_current_item_status(self, trace_item: TraceItem):
        """Update small UI indicators for the currently selected item."""
        try:
            label = getattr(trace_item, 'summary', '') or ''
            proto = getattr(trace_item, 'protocol', '') or ''
            ts = getattr(trace_item, 'timestamp', '') or ''
            if hasattr(self, 'current_item_label'):
                self.current_item_label.setText(label)
            if hasattr(self, 'status_label') and label:
                self.status_label.setText(f"{proto} • {label} • {ts}")
        except Exception:
            pass
    
    def create_enhanced_inspector_tree(self, trace_item: TraceItem) -> TreeNode:
        """Create an enhanced inspector tree that includes raw data and timing info."""
        # Create the root node without tree symbols
        root = TreeNode(trace_item.summary)
        
        # Add FETCH section with raw data if this is a FETCH command
        if trace_item.summary.startswith("FETCH"):
            fetch_node = TreeNode("FETCH")
            
            # Add raw data info as a child with proper indentation
            raw_data_lines = []
            if trace_item.rawhex:
                raw_data_lines.append(f"Raw Data: 0x{trace_item.rawhex}")
            raw_data_lines.append("Type : ISO7816")
            if trace_item.timestamp:
                # Extract just the time part for display
                import re
                time_match = re.search(r'(\d{2}:\d{2}:\d{2}:\d{3})', trace_item.timestamp)
                if time_match:
                    raw_data_lines.append(f"Time Stamp : {time_match.group(1)}.000000")
                else:
                    raw_data_lines.append(f"Time Stamp : {trace_item.timestamp}")
            raw_data_lines.append("Duration : 113226 ns")
            raw_data_lines.append("Elapsed Time : 991646 ns")
            
            # Create single node with proper formatting
            raw_data_text = "     \\---[:] " + raw_data_lines[0]
            for line in raw_data_lines[1:]:
                raw_data_text += f"\n              {line}"
            
            raw_data_node = TreeNode(raw_data_text)
            fetch_node.add_child(raw_data_node)
            root.add_child(fetch_node)
        
        # Add the main command section
        if trace_item.details_tree and trace_item.details_tree.children:
            # Create the main command section (e.g., "FETCH - OPEN CHANNEL")
            main_command_content = trace_item.summary
            if trace_item.summary.startswith("FETCH - "):
                main_command_content = trace_item.summary[8:]  # Remove "FETCH - " prefix
            
            main_command_node = TreeNode(f"\\---[+] {main_command_content}")
            
            # Copy the original interpretation structure with proper prefixes
            for i, child in enumerate(trace_item.details_tree.children):
                is_last = i == len(trace_item.details_tree.children) - 1
                enhanced_child = self.copy_tree_with_enhancements(child, trace_item, is_last, is_main_level=True)
                main_command_node.add_child(enhanced_child)
            
            # Add SW and Raw Data at the end of the main command
            if trace_item.rawhex:
                # Add raw data as the last item under main command
                raw_response_lines = []
                raw_response_lines.append(f"Raw Data: 0x{trace_item.rawhex}")
                raw_response_lines.append("Type : ISO7816")
                if trace_item.timestamp:
                    import re
                    time_match = re.search(r'(\d{2}:\d{2}:\d{2}:\d{3})', trace_item.timestamp)
                    if time_match:
                        raw_response_lines.append(f"Time Stamp : {time_match.group(1)}.000000")
                    else:
                        raw_response_lines.append(f"Time Stamp : {trace_item.timestamp}")
                raw_response_lines.append("Duration : 824646 ns")
                raw_response_lines.append("Elapsed Time : 767532 ns")
                
                raw_response_text = "     \\---[:] " + raw_response_lines[0]
                for line in raw_response_lines[1:]:
                    raw_response_text += f"\n              {line}"
                
                raw_response_node = TreeNode(raw_response_text)
                main_command_node.add_child(raw_response_node)
            
            root.add_child(main_command_node)
        
        return root
    
    def copy_tree_with_enhancements(self, original_node: TreeNode, trace_item: TraceItem, is_last: bool = False, is_main_level: bool = False, depth: int = 0) -> TreeNode:
        """Copy a tree node and enhance it with clean formatting."""
        content = original_node.content.strip()
        
        # Create clean node without tree symbols, just use indentation
        indent = "  " * depth if depth > 0 else ""
        new_node = TreeNode(f"{indent}{content}")
        
        # Copy all children with appropriate formatting
        for i, child in enumerate(original_node.children):
            is_child_last = i == len(original_node.children) - 1
            new_child = self.copy_tree_with_enhancements(child, trace_item, is_child_last, False, depth + 1)
            new_node.add_child(new_child)
        
        return new_node

    def create_combined_inspector_tree(self, fetch_item: TraceItem, response_item: TraceItem) -> TreeNode:
        """Create a combined inspector tree for FETCH and TERMINAL RESPONSE pair."""
        # Extract command type from response summary (e.g., "TERMINAL RESPONSE - OPEN CHANNEL" -> "OPEN CHANNEL")
        response_summary = response_item.summary
        command_type = "UNKNOWN"
        if " - " in response_summary:
            command_type = response_summary.split(" - ", 1)[1]
        
        # Create the root node with combined format
        root = TreeNode(f"FETCH - FETCH - {command_type}")
        
        # Add FETCH section with raw data
        fetch_node = TreeNode("FETCH")
        
        # Add raw data info for FETCH command
        raw_data_lines = []
        if fetch_item.rawhex:
            raw_data_lines.append(f"Raw Data: 0x{fetch_item.rawhex}")
        raw_data_lines.append("Type : ISO7816")
        if fetch_item.timestamp:
            # Extract just the time part for display
            import re
            time_match = re.search(r'(\d{2}:\d{2}:\d{2}:\d{3})', fetch_item.timestamp)
            if time_match:
                raw_data_lines.append(f"Time Stamp : {time_match.group(1)}.000000")
            else:
                raw_data_lines.append(f"Time Stamp : {fetch_item.timestamp}")
        raw_data_lines.append("Duration : 118570 ns")
        raw_data_lines.append("Elapsed Time : 1348692 ns")
        
        # Create single node with proper formatting
        raw_data_text = "     \\---[:] " + raw_data_lines[0]
        for line in raw_data_lines[1:]:
            raw_data_text += f"\n              {line}"
        
        fetch_raw_node = TreeNode(raw_data_text)
        fetch_node.add_child(fetch_raw_node)
        root.add_child(fetch_node)
        
        # Add the TERMINAL RESPONSE section with all its interpretation details
        response_node = TreeNode(f"\\---[+] FETCH - {command_type}")
        
        # Add interpretation details from the response item's details_tree
        if response_item.details_tree and response_item.details_tree.children:
            # Skip the root and use its children directly (Command Details, Device Identity, etc.)
            for i, child_node in enumerate(response_item.details_tree.children):
                is_last_detail = i == len(response_item.details_tree.children) - 1
                enhanced_child = self.copy_tree_with_inspector_formatting(child_node, is_last_detail, True, 1)
                response_node.add_child(enhanced_child)
        
        # Add SW code if available (look for it in the response or try to extract from summary)
        sw_code = None
        if hasattr(response_item, 'sw_code') and response_item.sw_code:
            sw_code = response_item.sw_code
        else:
            # Try to find SW code in the summary or response data
            import re
            if response_item.rawhex and len(response_item.rawhex) >= 4:
                # Last 4 characters should be the SW code
                sw_code = response_item.rawhex[-4:].upper()
        
        if sw_code:
            sw_description = self.get_sw_description(sw_code)
            sw_text = f"SW: {sw_code}"
            if sw_description:
                sw_text += f" - {sw_description}"
            sw_node = TreeNode(f"    {sw_text}")
            response_node.add_child(sw_node)
        
        # Add raw data for response
        response_raw_lines = []
        if response_item.rawhex:
            response_raw_lines.append(f"Raw Data: 0x{response_item.rawhex}")
        response_raw_lines.append("Type : ISO7816")
        if response_item.timestamp:
            import re
            time_match = re.search(r'(\d{2}:\d{2}:\d{2}:\d{3})', response_item.timestamp)
            if time_match:
                response_raw_lines.append(f"Time Stamp : {time_match.group(1)}.000000")
            else:
                response_raw_lines.append(f"Time Stamp : {response_item.timestamp}")
        response_raw_lines.append("Duration : 1018032 ns")
        response_raw_lines.append("Elapsed Time : 768200 ns")
        
        response_raw_text = "\\---[:] " + response_raw_lines[0]
        for line in response_raw_lines[1:]:
            response_raw_text += f"\n              {line}"
        
        response_raw_node = TreeNode(response_raw_text)
        response_node.add_child(response_raw_node)
        
        root.add_child(response_node)
        
        return root
        
    def copy_tree_with_inspector_formatting(self, original_node: TreeNode, is_last: bool = False, is_main_level: bool = False, depth: int = 0) -> TreeNode:
        """Copy a tree node with proper inspector formatting for combined entries."""
        content = original_node.content.strip()
        
        # Use simple indentation based on depth
        indent = "    " * depth
        
        new_node = TreeNode(f"{indent}{content}")
        
        # Copy all children with appropriate formatting
        for i, child in enumerate(original_node.children):
            is_child_last = i == len(original_node.children) - 1
            new_child = self.copy_tree_with_inspector_formatting(child, is_child_last, False, depth + 1)
            new_node.add_child(new_child)
        
        return new_node
        
    def get_sw_description(self, sw_code: str) -> str:
        """Get description for SW code."""
        sw_descriptions = {
            "9000": "Normal processing. Command correctly executed, and no response data",
            "9110": "Command correctly executed, and 16 byte(s) Proactive Command is available",
            "9120": "Command correctly executed, and 32 byte(s) Proactive Command is available", 
            "9143": "Command correctly executed, and 67 byte(s) Proactive Command is available",
            "910F": "Command correctly executed, and 15 byte(s) Proactive Command is available",
            "910D": "Command correctly executed, and 13 byte(s) Proactive Command is available",
        }
        return sw_descriptions.get(sw_code, "")

    def update_inspector(self, trace_item: TraceItem):
        """Update the inspector tree with trace item details including raw data."""
        enhanced_tree = self.create_enhanced_inspector_tree(trace_item)
        self.inspector_model.load_tree(enhanced_tree)
        # Expand all levels by default to show full hierarchy like Universal Tracer
        self.inspector_tree.expandAll()
        
    def update_inspector_combined(self, fetch_item: TraceItem, response_item: TraceItem):
        """Update the inspector tree with combined FETCH and TERMINAL RESPONSE details."""
        enhanced_tree = self.create_combined_inspector_tree(fetch_item, response_item)
        self.inspector_model.load_tree(enhanced_tree)
        # Expand all levels by default to show full hierarchy like Universal Tracer
        self.inspector_tree.expandAll()
    
    def update_hex_view(self, trace_item: TraceItem):
        """Update the hex view and analyze tab with trace item data."""
        # Update hex tab
        formatted_hex = HexViewModel.format_hex_data(trace_item.rawhex)
        self.hex_text.setPlainText(formatted_hex)
        self.copy_button.setEnabled(bool(trace_item.rawhex))
        
        # Update analyze tab
        self.update_analyze_view(trace_item)
        
    def update_hex_view_combined(self, fetch_item: TraceItem, response_item: TraceItem):
        """Update the hex view with both FETCH command and response data."""
        combined_hex = ""
        
        # Add FETCH command (outgoing → )
        if fetch_item.rawhex:
            combined_hex += "→ \n"
            fetch_hex = HexViewModel.format_hex_data(fetch_item.rawhex)
            combined_hex += fetch_hex
        
        # Add response (incoming ← )
        if response_item.rawhex:
            combined_hex += "\n\n← \n"
            response_hex = HexViewModel.format_hex_data(response_item.rawhex)
            combined_hex += response_hex
        
        self.hex_text.setPlainText(combined_hex)
        self.copy_button.setEnabled(bool(fetch_item.rawhex or response_item.rawhex))
        
        # Update analyze tab with the fetch item (primary command)
        self.update_analyze_view(fetch_item)
    
    def update_analyze_view(self, trace_item: TraceItem):
        """Update the analyze tab with parsed APDU data and protocol analysis."""
        if not trace_item.rawhex:
            self.summary_label.setText("No raw data to analyze")
            self.header_info.setText("No data")
            self.tlv_tree.clear()
            self.warning_banner.setVisible(False)
            
            # Clear summary cards
            self.cmd_value.setText("N/A")
            self.dir_value.setText("N/A")  
            self.status_value.setText("N/A")
            self.tlv_value.setText("N/A")
            self.domain_value.setText("N/A")
            return

        try:
            # Import the APDU parser and protocol analyzer
            from .apdu_parser_construct import parse_apdu
            from .protocol_analyzer import ProtocolAnalyzer, PayloadType
            
            parsed = parse_apdu(trace_item.rawhex)
            
            # Get channel info for protocol analysis
            channel_info = self._get_channel_info(trace_item)
            
            # Perform protocol analysis on SEND/RECEIVE DATA payloads
            protocol_analysis = None
            if self._is_send_receive_data(parsed, trace_item):
                payload = self._extract_payload_from_tlv(parsed)
                if payload:
                    protocol_analysis = ProtocolAnalyzer.analyze_payload(payload, channel_info)
            
            # Update summary with protocol information
            summary_text = parsed.summary
            if protocol_analysis:
                # Add detailed protocol information to summary
                if protocol_analysis.tls_info:
                    tls = protocol_analysis.tls_info
                    summary_text += f" | TLS {tls.handshake_type} ({tls.version})"
                    if tls.sni_hostname:
                        summary_text += f" | SNI: {tls.sni_hostname}"
                elif protocol_analysis.dns_info:
                    dns = protocol_analysis.dns_info
                    qtype = "Query" if dns.is_query else "Response"
                    summary_text += f" | DNS {qtype}"
                    if dns.questions:
                        summary_text += f" | {dns.questions[0]['name']}"
                elif protocol_analysis.json_content:
                    summary_text += f" | JSON Message"
                    if 'function' in protocol_analysis.json_content:
                        summary_text += f" | {protocol_analysis.json_content['function']}"
                elif protocol_analysis.asn1_structure:
                    summary_text += f" | ASN.1/BER Structure"
                else:
                    summary_text += f" | {protocol_analysis.raw_classification}"
                
                if protocol_analysis.channel_role:
                    summary_text += f" | Role: {protocol_analysis.channel_role}"
            
            self.summary_label.setText(summary_text)
            
            # Update summary cards
            self.update_summary_cards(parsed, protocol_analysis)
            
            # Update header info
            header_text = f"CLA: {parsed.cla:02X}  INS: {parsed.ins:02X} ({parsed.ins_name})  P1: {parsed.p1:02X}  P2: {parsed.p2:02X}"
            if parsed.lc is not None:
                header_text += f"  Lc: {parsed.lc:02X} ({parsed.lc})"
            if parsed.le is not None:
                header_text += f"  Le: {parsed.le:02X}"
            if parsed.sw is not None:
                header_text += f"  SW: {parsed.sw:04X}"
            
            # Add direction and command type information
            header_text += f"  |  Direction: {parsed.direction}  |  Type: {parsed.command_type}"
            
            # Add protocol analysis info to header if available
            if protocol_analysis and protocol_analysis.media_type:
                header_text += f"  |  Media: {protocol_analysis.media_type}"
            
            self.header_info.setText(header_text)
            
            # Update warnings
            warnings = parsed.warnings[:]
            if protocol_analysis and protocol_analysis.tls_info and not protocol_analysis.tls_info.compliance_ok:
                warnings.extend([f"TLS: {issue}" for issue in protocol_analysis.tls_info.compliance_issues])
            
            if warnings:
                warning_text = "⚠️ " + "; ".join(warnings)
                self.warning_banner.setText(warning_text)
                self.warning_banner.setVisible(True)
            else:
                self.warning_banner.setVisible(False)
            
            # Update TLV tree with protocol analysis sections
            self.tlv_tree.clear()
            for tlv in parsed.tlvs:
                self.add_tlv_to_tree(tlv, None)
            
            # Add protocol analysis sections
            if protocol_analysis:
                self.add_protocol_analysis_to_tree(protocol_analysis)
            
            # Expand all items
            self.tlv_tree.expandAll()
            
        except Exception as e:
            self.summary_label.setText(f"Parse error: {str(e)}")
            self.header_info.setText("Parse failed")
            self.tlv_tree.clear()
            self.warning_banner.setText(f"⚠️ Parse error: {str(e)}")
            self.warning_banner.setVisible(True)
            
            # Clear summary cards
            self.cmd_value.setText("Parse Error")
            self.dir_value.setText("Unknown")
            self.status_value.setText("Error")
            self.tlv_value.setText("N/A")
            self.domain_value.setText("Error")
    
    def _get_channel_info(self, trace_item: TraceItem) -> dict:
        """Extract channel information for protocol analysis."""
        channel_info = {}
        
        # Try to get channel info from the trace model
        if hasattr(self, 'trace_model') and self.trace_model:
            # Get session info from the filter proxy model
            if hasattr(self.trace_model, 'session_navigator'):
                sessions = getattr(self.trace_model.session_navigator, 'channel_sessions', {})
                for channel_id, session in sessions.items():
                    if trace_item in session.get('items', []):
                        if 'ip' in session:
                            channel_info['ip'] = session['ip']
                        if 'port' in session:
                            channel_info['port'] = session['port']
                        if 'protocol' in session:
                            channel_info['protocol'] = session['protocol']
                        break
        
        return channel_info
    
    def _is_send_receive_data(self, parsed_apdu, trace_item: TraceItem) -> bool:
        """Check if this is a SEND DATA or RECEIVE DATA command."""
        return ("SEND DATA" in parsed_apdu.ins_name or 
                "RECEIVE DATA" in parsed_apdu.ins_name or
                "send data" in trace_item.summary.lower() or
                "receive data" in trace_item.summary.lower())
    
    def _extract_payload_from_tlv(self, parsed_apdu) -> bytes:
        """Extract the payload bytes from TLV data - searches recursively through TLV structure."""
        def search_tlv_recursively(tlvs, depth=0):
            """Recursively search for payload data in TLV structure."""
            if depth > 3 or not tlvs:
                return None
            
            for tlv in tlvs:
                # Try raw_value attribute first
                if hasattr(tlv, 'raw_value') and tlv.raw_value and len(tlv.raw_value) > 5:
                    return tlv.raw_value
                
                # Try value_hex attribute
                if hasattr(tlv, 'value_hex') and tlv.value_hex:
                    try:
                        raw_data = bytes.fromhex(tlv.value_hex.replace(' ', ''))
                        if len(raw_data) > 5:
                            return raw_data
                    except:
                        pass
                
                # Try decoded_value attribute
                if hasattr(tlv, 'decoded_value') and tlv.decoded_value:
                    if isinstance(tlv.decoded_value, str):
                        hex_clean = tlv.decoded_value.replace(' ', '').replace('\n', '').replace('\r', '')
                        if len(hex_clean) > 10 and all(c in '0123456789ABCDEFabcdef' for c in hex_clean):
                            try:
                                raw_data = bytes.fromhex(hex_clean)
                                if len(raw_data) > 5:
                                    return raw_data
                            except:
                                pass
                
                # Search in children recursively
                if hasattr(tlv, 'children') and tlv.children:
                    result = search_tlv_recursively(tlv.children, depth + 1)
                    if result:
                        return result
            
            return None
        
        try:
            return search_tlv_recursively(parsed_apdu.tlvs)
        except Exception as e:
            return None
    
    def add_protocol_analysis_to_tree(self, analysis):
        """Add enhanced protocol analysis sections to the TLV tree with detailed formatting."""
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QFont, QColor
        from PySide6.QtCore import Qt
        
        # Create main protocol analysis section with visual separation
        protocol_root = QTreeWidgetItem(self.tlv_tree)
        protocol_root.setText(0, "═══════════")
        protocol_root.setText(1, "═══ PROTOCOL ANALYSIS ═══")
        protocol_root.setText(2, "")
        protocol_root.setText(3, analysis.raw_classification)
        protocol_root.setText(4, "")
        
        # Make header bold
        font = QFont()
        font.setBold(True)
        protocol_root.setFont(1, font)
        protocol_root.setForeground(1, QColor(0, 102, 204))  # Blue color
        
        # TLS Handshake section with enhanced display
        if analysis.tls_info:
            tls = analysis.tls_info
            tls_item = QTreeWidgetItem(protocol_root)
            tls_item.setText(0, "🔒")
            tls_item.setText(1, f"TLS {tls.handshake_type}")
            tls_item.setText(2, "")
            tls_item.setText(3, f"Version: {tls.version}")
            tls_item.setText(4, "")
            tls_item.setForeground(1, QColor(139, 0, 139))  # Purple for TLS
            
            # Version compliance check
            version_ok = "1.2" in tls.version or "1.3" in tls.version
            version_item = QTreeWidgetItem(tls_item)
            version_item.setText(0, "✓" if version_ok else "⚠")
            version_item.setText(1, "TLS Version")
            version_item.setText(2, "")
            version_item.setText(3, f"{tls.version} {'(OK ≥1.2)' if version_ok else '(WARNING: Use ≥1.2)'}")
            version_item.setText(4, "")
            version_item.setForeground(3, QColor(0, 128, 0) if version_ok else QColor(255, 140, 0))
            
            if tls.sni_hostname:
                sni_item = QTreeWidgetItem(tls_item)
                sni_item.setText(0, "🌐")
                sni_item.setText(1, "SNI (Server Name)")
                sni_item.setText(2, "")
                sni_item.setText(3, tls.sni_hostname)
                sni_item.setText(4, "")
            
            if tls.cipher_suites:
                cipher_item = QTreeWidgetItem(tls_item)
                cipher_item.setText(0, "🔐")
                cipher_item.setText(1, "Cipher Suites")
                cipher_item.setText(2, str(len(tls.cipher_suites)))
                cipher_item.setText(3, f"{len(tls.cipher_suites)} offered")
                cipher_item.setText(4, "")
                
                # Show first 5 cipher suites
                for i, cipher in enumerate(tls.cipher_suites[:5]):
                    suite_item = QTreeWidgetItem(cipher_item)
                    suite_item.setText(0, f"  {i+1}")
                    suite_item.setText(1, cipher)
                    suite_item.setText(2, "")
                    suite_item.setText(3, "")
                    suite_item.setText(4, "")
            
            if tls.extensions:
                ext_item = QTreeWidgetItem(tls_item)
                ext_item.setText(0, "📋")
                ext_item.setText(1, "Extensions")
                ext_item.setText(2, str(len(tls.extensions)))
                ext_item.setText(3, ", ".join(tls.extensions[:5]))
                ext_item.setText(4, "")
        
        # DNS section with enhanced display
        if analysis.dns_info:
            dns = analysis.dns_info
            dns_item = QTreeWidgetItem(protocol_root)
            dns_item.setText(0, "🌐")
            dns_item.setText(1, f"DNS {'Query' if dns.is_query else 'Response'}")
            dns_item.setText(2, "")
            dns_item.setText(3, f"Transaction ID: 0x{dns.transaction_id:04X}")
            dns_item.setText(4, "")
            dns_item.setForeground(1, QColor(0, 128, 128))  # Teal for DNS
            
            # Questions section
            if dns.questions:
                for question in dns.questions:
                    q_item = QTreeWidgetItem(dns_item)
                    q_item.setText(0, "❓")
                    q_item.setText(1, "QNAME")
                    q_item.setText(2, "")
                    q_item.setText(3, question['name'])
                    q_item.setText(4, "")
                    
                    # Query details
                    type_item = QTreeWidgetItem(q_item)
                    type_item.setText(0, "  ")
                    qtype = question['type']
                    qtype_desc = "(IPv6)" if qtype == "AAAA" else "(IPv4)" if qtype == "A" else ""
                    type_item.setText(1, f"Type: {qtype} {qtype_desc}")
                    type_item.setText(2, "")
                    type_item.setText(3, "")
                    type_item.setText(4, "")
                    
                    class_item = QTreeWidgetItem(q_item)
                    class_item.setText(0, "  ")
                    class_item.setText(1, f"Class: IN")
                    class_item.setText(2, "")
                    class_item.setText(3, "")
                    class_item.setText(4, "")
            
            # Answers section
            if dns.answers:
                answers_header = QTreeWidgetItem(dns_item)
                answers_header.setText(0, "✅")
                answers_header.setText(1, f"Answers ({len(dns.answers)})")
                answers_header.setText(2, "")
                answers_header.setText(3, "")
                answers_header.setText(4, "")
                
                for i, answer in enumerate(dns.answers[:5]):
                    a_item = QTreeWidgetItem(answers_header)
                    a_item.setText(0, f"  {i+1}")
                    a_item.setText(1, f"{answer['type']} Record")
                    a_item.setText(2, f"TTL: {answer['ttl']}s")
                    
                    # Truncate long data
                    data_str = str(answer['data'])
                    if len(data_str) > 50:
                        data_str = data_str[:47] + "..."
                    a_item.setText(3, data_str)
                    a_item.setText(4, "")
        
        # JSON section
        if analysis.json_content:
            json_item = QTreeWidgetItem(protocol_root)
            json_item.setText(0, "JSON")
            json_item.setText(1, "JSON Message")
            json_item.setText(2, str(len(analysis.json_content)))
            
            # Show key fields
            key_fields = []
            for key in ['function', 'transactionId', 'resultCode', 'notificationType']:
                if key in analysis.json_content:
                    key_fields.append(f"{key}: {analysis.json_content[key]}")
            
            json_item.setText(3, ", ".join(key_fields) if key_fields else "JSON data")
            json_item.setText(4, "")
        
        # ASN.1 section
        if analysis.asn1_structure:
            asn1_item = QTreeWidgetItem(protocol_root)
            asn1_item.setText(0, "ASN1")
            asn1_item.setText(1, "ASN.1/BER Structure")
            asn1_item.setText(2, str(len(analysis.asn1_structure)))
            asn1_item.setText(3, ", ".join(analysis.asn1_structure[:3]))
            asn1_item.setText(4, "")
        
        # Certificate chain section
        if analysis.certificates:
            cert_item = QTreeWidgetItem(protocol_root)
            cert_item.setText(0, "CERT")
            cert_item.setText(1, "Certificate Chain")
            cert_item.setText(2, str(len(analysis.certificates)))
            cert_item.setText(3, f"{len(analysis.certificates)} certificate(s)")
            cert_item.setText(4, "")
            
            for i, cert in enumerate(analysis.certificates):
                c_item = QTreeWidgetItem(cert_item)
                c_item.setText(0, f"C{i}")
                c_item.setText(1, f"Certificate {i+1}")
                c_item.setText(2, "")
                c_item.setText(3, f"CN: {cert.subject_cn}")
                c_item.setText(4, "")
        
        # Channel Role section with visual indicator
        if analysis.channel_role:
            role_item = QTreeWidgetItem(protocol_root)
            role_item.setText(0, "📍")
            role_item.setText(1, "Channel Role")
            role_item.setText(2, "")
            role_item.setText(3, analysis.channel_role)
            role_item.setText(4, "")
            
            # Color code by role
            role_colors = {
                "eIM": QColor(0, 153, 76),      # Green
                "SM-DP+": QColor(255, 102, 0),   # Orange
                "TAC": QColor(153, 51, 255),     # Purple
                "LPA": QColor(0, 102, 204)       # Blue
            }
            role_color = role_colors.get(analysis.channel_role, QColor(128, 128, 128))
            role_item.setForeground(3, role_color)
            
            font_bold = QFont()
            font_bold.setBold(True)
            role_item.setFont(3, font_bold)
    
    def add_tlv_to_tree(self, tlv, parent_item=None):
        """Add a TLV item to the analyze tree widget."""
        from PySide6.QtWidgets import QTreeWidgetItem
        
        # Create the tree item
        if parent_item is None:
            item = QTreeWidgetItem(self.tlv_tree)
        else:
            item = QTreeWidgetItem(parent_item)
        
        # Format the tag column
        tag_text = f"{tlv.tag:02X}"
        
        # Set the column values
        item.setText(0, tag_text)  # Tag
        item.setText(1, tlv.name)  # Name
        item.setText(2, str(tlv.length))  # Length
        item.setText(3, tlv.decoded_value[:100] + "..." if len(tlv.decoded_value) > 100 else tlv.decoded_value)  # Value (truncated)
        item.setText(4, f"0x{tlv.byte_offset:04X}")  # Offset
        
        # Add children if they exist
        if hasattr(tlv, 'children') and tlv.children:
            for child_tlv in tlv.children:
                self.add_tlv_to_tree(child_tlv, item)
    
    def update_summary_cards(self, parsed_apdu, protocol_analysis=None):
        """Update the summary cards with key information."""
        # Command info with command number if available
        cmd_text = f"{parsed_apdu.ins_name} (0x{parsed_apdu.ins:02X})"
        
        # Try to extract command number from TLVs
        cmd_number = None
        for tlv in parsed_apdu.tlvs:
            if tlv.tag in [0x01, 0x81]:  # Command Details
                try:
                    if len(tlv.value_hex) >= 2:
                        cmd_number = int(tlv.value_hex[0:2], 16)
                        break
                except:
                    pass
        
        if cmd_number is not None:
            cmd_text += f" • Cmd#{cmd_number}"
        
        # Add detailed protocol info to command
        if protocol_analysis:
            if protocol_analysis.tls_info:
                tls = protocol_analysis.tls_info
                cmd_text += f" • {tls.handshake_type} ({tls.version})"
                if tls.cipher_suites:
                    cmd_text += f" • {len(tls.cipher_suites)} cipher suites"
            elif protocol_analysis.dns_info:
                dns = protocol_analysis.dns_info
                qtype = "DNS Query" if dns.is_query else "DNS Response"
                cmd_text += f" • {qtype}"
                if dns.questions:
                    cmd_text += f" • {len(dns.questions)} question(s)"
                if dns.answers:
                    cmd_text += f" • {len(dns.answers)} answer(s)"
            elif protocol_analysis.json_content:
                cmd_text += f" • JSON Message"
            elif protocol_analysis.payload_type:
                cmd_text += f" • {protocol_analysis.payload_type.value}"
        
        self.cmd_value.setText(cmd_text)
        
        # Direction with arrow and role
        direction_text = parsed_apdu.direction
        if "ME->SIM" in direction_text:
            direction_text = "ME → SIM"
        elif "SIM->ME" in direction_text:
            direction_text = "SIM → ME"
        
        if protocol_analysis and protocol_analysis.channel_role:
            direction_text += f" ({protocol_analysis.channel_role})"
        
        self.dir_value.setText(direction_text)
        
        # Enhanced status with result details
        if parsed_apdu.sw is not None:
            if parsed_apdu.sw == 0x9000:
                status_text = "✓ Success"
                self.status_value.setStyleSheet("color: green; font-weight: bold;")
            elif parsed_apdu.sw >> 8 == 0x90:
                status_text = "⚠ Warning"  
                self.status_value.setStyleSheet("color: orange; font-weight: bold;")
            else:
                status_text = "✗ Error"
                self.status_value.setStyleSheet("color: red; font-weight: bold;")
            status_text += f" (0x{parsed_apdu.sw:04X})"
            
            # Try to add result details from TLVs
            for tlv in parsed_apdu.tlvs:
                if tlv.tag in [0x03, 0x83]:  # Result TLV
                    if "successfully" in tlv.decoded_value.lower():
                        status_text = "✓ " + tlv.decoded_value.split('(')[0].strip()
                    elif "error" in tlv.decoded_value.lower() or "unable" in tlv.decoded_value.lower():
                        status_text = "✗ " + tlv.decoded_value.split('(')[0].strip()
                    break
        else:
            status_text = "No Status"
            self.status_value.setStyleSheet("color: gray;")
        self.status_value.setText(status_text)
        
        # Enhanced Key TLVs with channel info and duration
        key_info = []
        channel_id = None
        duration = None
        
        for tlv in parsed_apdu.tlvs:
            # Extract channel information
            if tlv.tag in [0x30, 0xB7] and "Channel" in tlv.decoded_value:
                try:
                    if "Channel " in tlv.decoded_value:
                        channel_part = tlv.decoded_value.split("Channel ")[1].split(":")[0]
                        channel_id = channel_part.strip()
                except:
                    pass
            
            # Extract duration information  
            elif tlv.tag == 0x04 and ":" in tlv.decoded_value:
                try:
                    duration = tlv.decoded_value.split("(")[0].strip()
                except:
                    pass
            
            # Key TLVs for display
            elif tlv.tag in [0x01, 0x81, 0x02, 0x82, 0x03, 0x83, 0x36]:  # Important tags
                if len(key_info) < 2:  # Limit display
                    key_info.append(f"{tlv.name}")
        
        # Build enhanced summary text with protocol details
        tlv_parts = []
        
        # Add protocol-specific information first
        if protocol_analysis:
            if protocol_analysis.tls_info and protocol_analysis.tls_info.sni_hostname:
                tlv_parts.append(f"SNI: {protocol_analysis.tls_info.sni_hostname}")
            elif protocol_analysis.dns_info:
                dns = protocol_analysis.dns_info
                if dns.questions:
                    qname = dns.questions[0]['name']
                    if len(qname) > 30:
                        qname = qname[:27] + "..."
                    tlv_parts.append(f"QNAME: {qname}")
                if dns.answers and not dns.is_query:
                    tlv_parts.append(f"{len(dns.answers)} answer(s)")
        
        if channel_id:
            tlv_parts.append(f"Channel: {channel_id}")
        if duration:
            tlv_parts.append(f"Duration: {duration}")
        if key_info and len(tlv_parts) < 3:
            tlv_parts.extend(key_info[:3-len(tlv_parts)])
        
        if tlv_parts:
            tlv_text = " • ".join(tlv_parts)
        else:
            tlv_text = f"{len(parsed_apdu.tlvs)} TLVs" if parsed_apdu.tlvs else "No TLVs"
        
        self.tlv_value.setText(tlv_text)
        
        # Domain with enhanced formatting
        domain_text = parsed_apdu.domain
        if "Bearer Independent Protocol" in domain_text:
            domain_text = "BIP"
        elif "SIM Toolkit" in domain_text:
            domain_text = "STK" 
        elif "Short Message Service" in domain_text:
            domain_text = "SMS"
        self.domain_value.setText(domain_text)

    def add_tlv_to_tree(self, tlv, parent_item):
        """Add a TLV to the tree widget."""
        from .apdu_parser_construct import TLVInfo
        
        # Create tree item
        if parent_item is None:
            item = QTreeWidgetItem(self.tlv_tree)
        else:
            item = QTreeWidgetItem(parent_item)
        
        # Set data
        item.setText(0, tlv.tag_hex)
        item.setText(1, tlv.name)
        item.setText(2, str(tlv.length))
        item.setText(3, str(tlv.decoded_value))
        item.setText(4, f"{tlv.byte_offset:04X}")
        
        # Store TLV data for highlighting
        item.setData(0, Qt.UserRole, tlv)
        
        # Set tooltip with hex data
        tooltip = f"Tag: {tlv.tag_hex}\nOffset: {tlv.byte_offset:04X}\nLength: {tlv.length}\nHex: {tlv.value_hex}"
        for col in range(5):
            item.setToolTip(col, tooltip)
        
        # Add children if any
        if tlv.children:
            for child_tlv in tlv.children:
                self.add_tlv_to_tree(child_tlv, item)
        
        return item
    
    def update_summary_cards(self, parsed_apdu, protocol_analysis=None):
        """Update the summary cards with key information."""
        # Command info with command number if available
        cmd_text = f"{parsed_apdu.ins_name} (0x{parsed_apdu.ins:02X})"
        
        # Try to extract command number from TLVs
        cmd_number = None
        for tlv in parsed_apdu.tlvs:
            if tlv.tag in [0x01, 0x81]:  # Command Details
                try:
                    if len(tlv.value_hex) >= 2:
                        cmd_number = int(tlv.value_hex[0:2], 16)
                        break
                except:
                    pass
        
        if cmd_number is not None:
            cmd_text += f" • Cmd#{cmd_number}"
        
        # Add detailed protocol info to command
        if protocol_analysis:
            if protocol_analysis.tls_info:
                tls = protocol_analysis.tls_info
                cmd_text += f" • {tls.handshake_type} ({tls.version})"
                if tls.cipher_suites:
                    cmd_text += f" • {len(tls.cipher_suites)} cipher suites"
            elif protocol_analysis.dns_info:
                dns = protocol_analysis.dns_info
                qtype = "DNS Query" if dns.is_query else "DNS Response"
                cmd_text += f" • {qtype}"
                if dns.questions:
                    cmd_text += f" • {len(dns.questions)} question(s)"
                if dns.answers:
                    cmd_text += f" • {len(dns.answers)} answer(s)"
            elif protocol_analysis.json_content:
                cmd_text += f" • JSON Message"
            elif protocol_analysis.payload_type:
                cmd_text += f" • {protocol_analysis.payload_type.value}"
        
        self.cmd_value.setText(cmd_text)
        
        # Direction with arrow and role
        direction_text = parsed_apdu.direction
        if "ME->SIM" in direction_text:
            direction_text = "ME → SIM"
        elif "SIM->ME" in direction_text:
            direction_text = "SIM → ME"
        
        if protocol_analysis and protocol_analysis.channel_role:
            direction_text += f" ({protocol_analysis.channel_role})"
        
        self.dir_value.setText(direction_text)
        
        # Enhanced status with result details
        if parsed_apdu.sw is not None:
            if parsed_apdu.sw == 0x9000:
                status_text = "✓ Success"
                self.status_value.setStyleSheet("color: green; font-weight: bold;")
            elif parsed_apdu.sw >> 8 == 0x90:
                status_text = "⚠ Warning"  
                self.status_value.setStyleSheet("color: orange; font-weight: bold;")
            else:
                status_text = "✗ Error"
                self.status_value.setStyleSheet("color: red; font-weight: bold;")
            status_text += f" (0x{parsed_apdu.sw:04X})"
            
            # Try to add result details from TLVs
            for tlv in parsed_apdu.tlvs:
                if tlv.tag in [0x03, 0x83]:  # Result TLV
                    if "successfully" in tlv.decoded_value.lower():
                        status_text = "✓ " + tlv.decoded_value.split('(')[0].strip()
                    elif "error" in tlv.decoded_value.lower() or "unable" in tlv.decoded_value.lower():
                        status_text = "✗ " + tlv.decoded_value.split('(')[0].strip()
                    break
        else:
            status_text = "No Status"
            self.status_value.setStyleSheet("color: gray;")
        self.status_value.setText(status_text)
        
        # Enhanced Key TLVs with channel info and duration
        key_info = []
        channel_id = None
        duration = None
        
        for tlv in parsed_apdu.tlvs:
            # Extract channel information
            if tlv.tag in [0x30, 0xB7] and "Channel" in tlv.decoded_value:
                try:
                    if "Channel " in tlv.decoded_value:
                        channel_part = tlv.decoded_value.split("Channel ")[1].split(":")[0]
                        channel_id = channel_part.strip()
                except:
                    pass
            
            # Extract duration information  
            elif tlv.tag == 0x04 and ":" in tlv.decoded_value:
                try:
                    duration = tlv.decoded_value.split("(")[0].strip()
                except:
                    pass
            
            # Key TLVs for display
            elif tlv.tag in [0x01, 0x81, 0x02, 0x82, 0x03, 0x83, 0x36]:  # Important tags
                if len(key_info) < 2:  # Limit display
                    key_info.append(f"{tlv.name}")
        
        # Build enhanced summary text with protocol details
        tlv_parts = []
        
        # Add protocol-specific information first
        if protocol_analysis:
            if protocol_analysis.tls_info and protocol_analysis.tls_info.sni_hostname:
                tlv_parts.append(f"SNI: {protocol_analysis.tls_info.sni_hostname}")
            elif protocol_analysis.dns_info:
                dns = protocol_analysis.dns_info
                if dns.questions:
                    qname = dns.questions[0]['name']
                    if len(qname) > 30:
                        qname = qname[:27] + "..."
                    tlv_parts.append(f"QNAME: {qname}")
                if dns.answers and not dns.is_query:
                    tlv_parts.append(f"{len(dns.answers)} answer(s)")
        
        if channel_id:
            tlv_parts.append(f"Channel: {channel_id}")
        if duration:
            tlv_parts.append(f"Duration: {duration}")
        if key_info and len(tlv_parts) < 3:
            tlv_parts.extend(key_info[:3-len(tlv_parts)])
        
        if tlv_parts:
            tlv_text = " • ".join(tlv_parts)
        else:
            tlv_text = f"{len(parsed_apdu.tlvs)} TLVs" if parsed_apdu.tlvs else "No TLVs"
        
        self.tlv_value.setText(tlv_text)
        
        # Domain with enhanced formatting
        domain_text = parsed_apdu.domain
        if "Bearer Independent Protocol" in domain_text:
            domain_text = "BIP"
        elif "SIM Toolkit" in domain_text:
            domain_text = "STK" 
        elif "Short Message Service" in domain_text:
            domain_text = "SMS"
        self.domain_value.setText(domain_text)

    def export_channel_groups_csv(self):
        """Export channel groups to CSV file."""
        if not self.parser or not self.parser.channel_sessions:
            show_info_dialog(self, "No Data", "No channel groups to export.")
            return
        
        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Channel Groups",
            "channel_groups.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            import csv
            
            # Get channel groups data
            groups = self.parser.get_channel_groups()
            
            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(["Type de Channel", "Port", "Protocol", "Serveur utilisé", "IP"])
                
                # Write data rows
                for group in groups:
                    writer.writerow([
                        group.get("type", ""),
                        group.get("port", ""),
                        group.get("protocol", ""), 
                        group.get("server", ""),
                        ", ".join(group.get("ips", []))
                    ])
            
            show_info_dialog(self, "Export Complete", f"Channel groups exported to {file_path}")
            
        except Exception as e:
            show_error_dialog(self, "Export Failed", f"Failed to export CSV: {str(e)}")

    def _navigate_to_item(self, target_item: TraceItem):
        """Helper pour naviguer vers un item spécifique."""
        # Try cache first for O(1) lookup
        target_index = None
        row = self._traceitem_row_by_id.get(id(target_item))
        if row is not None:
            target_index = self.trace_model.index(row, 0)
            print(f"[FlowOverview] Found target in Interpretation at source row {row} (cached)")
        else:
            # Fallback linear search (rare)
            for r in range(self.trace_model.rowCount()):
                model_index = self.trace_model.index(r, 0)
                item = self.trace_model.get_trace_item(model_index)
                if item is target_item:
                    print(f"[FlowOverview] Found target in Interpretation at source row {r} (fallback)")
                    target_index = model_index
                    break
        
        if target_index:
            # Mapper vers le modèle filtré et sélectionner
            filtered_index = self.filter_model.mapFromSource(target_index)
            if filtered_index.isValid():
                from PySide6.QtWidgets import QAbstractItemView
                # Verify we actually hit the row containing the target identity
                def row_contains_target(f_index, target):
                    try:
                        s_idx = self.filter_model.mapToSource(f_index)
                        tree_item = self.trace_model.get_tree_item(s_idx)
                        if not tree_item:
                            return False
                        if getattr(tree_item, 'trace_item', None) is target:
                            return True
                        if getattr(tree_item, 'response_item', None) is target:
                            return True
                    except Exception:
                        return False
                    return False

                best_index = filtered_index
                if not row_contains_target(filtered_index, target_item):
                    # Scan a small window around to locate the exact combined row
                    try:
                        start = max(0, filtered_index.row() - 4)
                        end = min(self.filter_model.rowCount(), filtered_index.row() + 5)
                        for r in range(start, end):
                            probe = self.filter_model.index(r, 0)
                            if row_contains_target(probe, target_item):
                                best_index = probe
                                break
                    except Exception:
                        pass

                # Minimize overhead: scroll first, then select
                self.trace_table.scrollTo(best_index, QAbstractItemView.PositionAtCenter)
                self.trace_table.setCurrentIndex(best_index)
                
                # Animation visuelle pour indiquer le saut
                self.flash_selection()
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Item Filtered Out", 
                    "The target item is currently filtered out. Clear filters to navigate to it."
                )

    def _navigate_to_item_fast(self, target_item: TraceItem):
        """Fast path: select immediately if visible; otherwise clear filters and navigate."""
        try:
            row = self._traceitem_row_by_id.get(id(target_item))
            if row is not None:
                src_idx = self.trace_model.index(row, 0)
                f_idx = self.filter_model.mapFromSource(src_idx)
                if f_idx.isValid():
                    from PySide6.QtWidgets import QAbstractItemView
                    # Verify/adjust selection to ensure exact target row
                    def row_contains_target(f_index, target):
                        try:
                            s_idx = self.filter_model.mapToSource(f_index)
                            tree_item = self.trace_model.get_tree_item(s_idx)
                            if not tree_item:
                                return False
                            if getattr(tree_item, 'trace_item', None) is target:
                                return True
                            if getattr(tree_item, 'response_item', None) is target:
                                return True
                        except Exception:
                            return False
                        return False

                    best_index = f_idx
                    if not row_contains_target(f_idx, target_item):
                        try:
                            start = max(0, f_idx.row() - 4)
                            end = min(self.filter_model.rowCount(), f_idx.row() + 5)
                            for r in range(start, end):
                                probe = self.filter_model.index(r, 0)
                                if row_contains_target(probe, target_item):
                                    best_index = probe
                                    break
                        except Exception:
                            pass
                    self.trace_table.scrollTo(best_index, QAbstractItemView.PositionAtCenter)
                    self.trace_table.setCurrentIndex(best_index)
                    self.flash_selection()
                    return
        except Exception:
            pass
        # Not visible: clear filters then use identity-based navigation
        try:
            self.filter_model.clear_all_filters()
        except Exception:
            pass
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda ti=target_item: self._navigate_to_item(ti))
    
    def flash_selection(self):
        """Animation visuelle pour indiquer un saut de navigation."""
        # Simple flash effect - pourrait être amélioré avec des animations Qt
        current_style = self.trace_table.styleSheet()
        flash_style = current_style + """
            QTreeView::item:selected {
                background-color: #FFD700;
                border: 2px solid #FFA500;
            }
        """
        self.trace_table.setStyleSheet(flash_style)
        
        # Restaurer le style normal après 200ms
        QTimer.singleShot(200, lambda: self.trace_table.setStyleSheet(current_style))

    def _find_iccid_value_around(self, parser: XTIParser, pivot_index: int) -> Optional[str]:
        """Heuristically extract ICCID value from nearby interpretation items.
        - Scans a window around the pivot for any text matching ICCID and digits
        - Falls back to decoding BCD from APDU READ BINARY responses (SW=9000)
        Returns a normalized decimal ICCID string when possible.
        """
        import re

        def decode_bcd_iccid(hex_data: str) -> Optional[str]:
            """Decode BCD ICCID with swapped nibbles (same as ValidationManager)."""
            try:
                hex_data = (hex_data or "").replace(" ", "").upper()
                if len(hex_data) < 20:
                    return None
                hex_data = hex_data[:20]  # 10 bytes
                out = []
                for i in range(0, len(hex_data), 2):
                    byte = hex_data[i:i+2]
                    out.append(byte[1])
                    out.append(byte[0])
                iccid = "".join(out).rstrip('F')
                if len(iccid) >= 18 and iccid.startswith('89'):
                    return iccid
                return None
            except Exception:
                return None

        def flatten_text(node: Optional[TreeNode]) -> str:
            if not node:
                return ""
            parts = [node.content or ""]
            for ch in getattr(node, 'children', []) or []:
                parts.append(flatten_text(ch))
            return "\n".join([p for p in parts if p])

        # 1) Look for explicit ICCID decimal in summaries or details within ±5 items
        start = max(0, pivot_index - 5)
        end = min(len(parser.trace_items), pivot_index + 6)
        iccid_re = re.compile(r"ICCID[^0-9]*([0-9]{18,22})", re.IGNORECASE)
        for i in range(start, end):
            ti = parser.trace_items[i]
            for text in [ti.summary or "", flatten_text(getattr(ti, 'details_tree', None))]:
                m = iccid_re.search(text)
                if m:
                    return m.group(1)

        # 2) Try to decode BCD-encoded ICCID from rawhex of nearby APDU responses
        for i in range(start, end):
            ti = parser.trace_items[i]
            try:
                trace_type = (getattr(ti, 'type', '') or '').lower()
                if trace_type != 'apduresponse':
                    continue
                clean_hex = (getattr(ti, 'rawhex', '') or '').replace(' ', '').upper()
                if clean_hex.endswith('9000') and len(clean_hex) >= 24:
                    data_hex = clean_hex[:-4]
                    val = decode_bcd_iccid(data_hex)
                    if val:
                        return val
            except Exception:
                continue

        return None

    def _get_detected_iccid_from_validation(self) -> Optional[str]:
        """Return ICCID detected by ValidationManager, if any."""
        import re

        vm = getattr(self, 'validation_manager', None)
        if not vm:
            return None
        try:
            issues = vm.get_all_issues() if hasattr(vm, 'get_all_issues') else getattr(vm, 'issues', [])
            candidates = []
            for iss in issues or []:
                if getattr(iss, 'category', '') == 'ICCID Detection':
                    msg = getattr(iss, 'message', '') or ''
                    m = re.search(r'([0-9]{18,22})', msg)
                    if m:
                        candidates.append(m.group(1))
            return candidates[-1] if candidates else None
        except Exception:
            return None

    def clear_parsing_log(self):
        """Clear the parsing log and reset validation manager."""
        self.validation_manager = ValidationManager()
        self.parsing_log_tree.clear()
        self.log_summary_label.setText("No validation issues")
    
    def update_parsing_log(self):
        """Update the parsing log with current validation issues."""
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QBrush
        
        # Clear current items
        self.parsing_log_tree.clear()
        
        # Apply severity filter
        desired = None
        try:
            if hasattr(self, 'parsing_log_filter_combo'):
                sel = (self.parsing_log_filter_combo.currentText() or 'All').lower()
                if sel != 'all':
                    desired = sel  # 'critical' | 'warning' | 'info'
        except Exception:
            desired = None

        # Determine multi-selected severities from buttons
        multi_selected = None
        try:
            severities = set()
            if getattr(self, 'btn_log_crit', None) and self.btn_log_crit.isChecked():
                severities.add('critical')
            if getattr(self, 'btn_log_warn', None) and self.btn_log_warn.isChecked():
                severities.add('warning')
            if getattr(self, 'btn_log_info', None) and self.btn_log_info.isChecked():
                severities.add('info')
            if severities:
                multi_selected = severities
        except Exception:
            multi_selected = None

        # Add issues to tree
        for issue in self.validation_manager.issues:
            sev_l = issue.severity.value.lower()
            if desired is not None and sev_l != desired:
                continue
            if multi_selected is not None and sev_l not in multi_selected:
                continue
            item = QTreeWidgetItem([
                issue.severity.value,
                issue.category,
                issue.message,
                str(issue.trace_index),
                issue.timestamp or "",
                issue.command_details or ""
            ])
            
            # Color code by severity
            if issue.severity == ValidationSeverity.CRITICAL:
                # Red for critical
                item.setBackground(0, QBrush(QColor(255, 200, 200)))
                item.setForeground(0, QBrush(QColor(139, 0, 0)))
            elif issue.severity == ValidationSeverity.WARNING:
                # Orange for warnings
                item.setBackground(0, QBrush(QColor(255, 235, 200)))
                item.setForeground(0, QBrush(QColor(204, 102, 0)))
            else:
                # Blue for info
                item.setBackground(0, QBrush(QColor(200, 220, 255)))
                item.setForeground(0, QBrush(QColor(0, 0, 139)))
            
            self.parsing_log_tree.addTopLevelItem(item)
        
        # Update summary
        summary = self.validation_manager.get_summary()
        self.log_summary_label.setText(summary)
        
        # Sort by timestamp (chronological order)
        self.parsing_log_tree.sortItems(4, Qt.AscendingOrder)

    def update_pairing_info(self, trace_item: TraceItem):
        """Met à jour les informations de pairing pour l'item sélectionné."""
        if not trace_item:
            self.goto_paired_button.setEnabled(False)
            self.pairing_info_label.setText("")
            return
        
        # Obtenir les infos de pairing depuis le modèle
        pair = self.trace_model.get_pair_info_for_item(trace_item)
        
        if pair:
            self.goto_paired_button.setEnabled(True)
            
            # Créer le texte d'info selon le type d'item
            if pair.fetch_item == trace_item:
                # Item sélectionné = FETCH command
                if pair.is_complete:
                    info_text = f"Cmd#{pair.command_number} → {pair.get_status()} ({pair.get_duration_display()})"
                else:
                    info_text = f"Cmd#{pair.command_number} → ⏳ Waiting for response"
                self.goto_paired_button.setText("Go to Response →")
            else:
                # Item sélectionné = TERMINAL RESPONSE
                info_text = f"← Response to Cmd#{pair.command_number} ({pair.get_duration_display()})"
                self.goto_paired_button.setText("Go to Command ←")
            
            self.pairing_info_label.setText(info_text)
        else:
            self.goto_paired_button.setEnabled(False)
            self.pairing_info_label.setText("No pairing available")
    
    def navigate_to_paired_item(self):
        """Navigue vers l'item pairé (FETCH ↔ TERMINAL RESPONSE)."""
        current_index = self.trace_table.currentIndex()
        if not current_index.isValid():
            return
        
        # Obtenir l'item actuel
        source_index = self.filter_model.mapToSource(current_index)
        current_item = self.trace_model.get_trace_item(source_index)
        
        if not current_item:
            return
        
        # Trouver l'item pairé
        paired_item = self.trace_model.get_paired_item(current_item)
        
        if not paired_item:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, 
                "No Paired Item", 
                "No paired FETCH/TERMINAL RESPONSE found for this item."
            )
            return
        
        # Trouver l'index de l'item pairé dans le modèle via cache
        paired_index = None
        cached_row = self._traceitem_row_by_id.get(id(paired_item))
        if cached_row is not None:
            paired_index = self.trace_model.index(cached_row, 0)
        else:
            # Fallback linear search
            for r in range(self.trace_model.rowCount()):
                model_index = self.trace_model.index(r, 0)
                item = self.trace_model.get_trace_item(model_index)
                if item is paired_item:
                    paired_index = model_index
                    break
        
        if paired_index:
            # Mapper vers le modèle filtré et sélectionner
            filtered_index = self.filter_model.mapFromSource(paired_index)
            if filtered_index.isValid():
                self.trace_table.scrollTo(filtered_index, self.trace_table.PositionAtCenter)
                self.trace_table.setCurrentIndex(filtered_index)
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, 
                    "Item Filtered Out", 
                    "The paired item is currently filtered out. Clear filters to navigate to it."
                )

    def navigate_same_session_next(self):
        """Navigue vers l'item suivant dans la même session (Alt+↓)."""
        current_index = self.trace_table.currentIndex()
        if not current_index.isValid():
            return
        
        # Obtenir l'item actuel
        source_index = self.filter_model.mapToSource(current_index)
        current_item = self.trace_model.get_trace_item(source_index)
        
        if not current_item:
            return
        
        # Trouver l'item suivant dans la même session
        next_item = self.trace_model.get_next_in_same_session(current_item)
        
        if not next_item:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "End of Session",
                "No more items in this session (protocol/channel context)."
            )
            return
        
        # Naviguer vers l'item trouvé
        self._navigate_to_item(next_item)

    def navigate_same_session_previous(self):
        """Navigue vers l'item précédent dans la même session (Alt+↑)."""
        current_index = self.trace_table.currentIndex()
        if not current_index.isValid():
            return
        
        # Obtenir l'item actuel
        source_index = self.filter_model.mapToSource(current_index)
        current_item = self.trace_model.get_trace_item(source_index)
        
        if not current_item:
            return
        
        # Trouver l'item précédent dans la même session
        previous_item = self.trace_model.get_previous_in_same_session(current_item)
        
        if not previous_item:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Start of Session", 
                "No previous items in this session (protocol/channel context)."
            )
            return
        
        # Naviguer vers l'item trouvé
        self._navigate_to_item(previous_item)

    def clear_selection(self):
        """Clear current selection and any session filter UI affordances."""
        try:
            self.trace_table.clearSelection()
        except Exception:
            pass
        try:
            self.clear_filter_button.setVisible(False)
        except Exception:
            pass

    def closeEvent(self, event):
        """Handle window close event."""
        # Cancel any running parsing
        if self.parser_thread and self.parser_thread.isRunning():
            self.parser_thread.terminate()
            self.parser_thread.wait()
        
        # Save window state
        self.save_window_state()
        
        event.accept()


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    app.setApplicationName("XTI Viewer")
    app.setApplicationVersion("1.0.1")
    app.setOrganizationName("XTIViewer")

    # App/window icon (shows in title bar + taskbar on Windows)
    try:
        from PySide6.QtGui import QIcon
        from xti_viewer.resources import resource_path

        icon_path = resource_path("Logo.png")
        app_icon = QIcon(icon_path)
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)
    except Exception:
        pass
    
    window = XTIMainWindow()
    try:
        if 'app_icon' in locals() and app_icon and not app_icon.isNull():
            window.setWindowIcon(app_icon)
    except Exception:
        pass
    window.show()
    
    # Open file if provided as command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            QTimer.singleShot(100, lambda: window.load_xti_file(file_path))
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()