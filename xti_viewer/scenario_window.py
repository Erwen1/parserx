from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QInputDialog,
    QMessageBox,
)

from .scenario_engine import (
    ScenarioStep,
    ScenarioStepPresence,
    ScenarioStepScope,
    ScenarioStepType,
    run_scenario,
)


class ScenarioWindow(QDialog):
    """Window that lets the user define a step sequence and run scenario validation."""

    def __init__(self, parent=None, *, main_window=None):
        super().__init__(parent)
        self.setWindowTitle("Scenario Results")
        self.setModal(False)

        self._main_window = main_window

        root = QVBoxLayout(self)

        # Header: scenario management
        header = QHBoxLayout()
        header.addWidget(QLabel("Scenario:"))

        self.scenario_combo = QComboBox()
        self.scenario_combo.currentIndexChanged.connect(self._on_select_scenario)
        header.addWidget(self.scenario_combo, 1)

        self.new_btn = QPushButton("New")
        self.new_btn.clicked.connect(self._new_scenario)
        header.addWidget(self.new_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_current_scenario)
        header.addWidget(self.save_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_current_scenario)
        header.addWidget(self.delete_btn)

        self.overall_label = QLabel("Overall: N/A")
        self.overall_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.overall_label)

        root.addLayout(header)

        self.summary_label = QLabel("Sequence summary: N/A")
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.summary_label)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        # Left: sequence editor
        seq_group = QGroupBox("Sequence")
        seq_layout = QVBoxLayout(seq_group)

        self.steps_list = QListWidget()
        self.steps_list.setSelectionMode(QListWidget.SingleSelection)
        self.steps_list.currentRowChanged.connect(self._on_select_step)
        seq_layout.addWidget(self.steps_list, 1)

        add_row = QHBoxLayout()
        self.step_type_combo = QComboBox()
        # Populate from enum so new step types automatically appear.
        for t in ScenarioStepType:
            self.step_type_combo.addItem(t.value)
        add_row.addWidget(self.step_type_combo, 1)

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._add_step)
        add_row.addWidget(self.add_btn)
        seq_layout.addLayout(add_row)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_step)
        btn_row.addWidget(self.remove_btn)

        self.up_btn = QPushButton("Up")
        self.up_btn.clicked.connect(self._move_up)
        btn_row.addWidget(self.up_btn)

        self.down_btn = QPushButton("Down")
        self.down_btn.clicked.connect(self._move_down)
        btn_row.addWidget(self.down_btn)

        seq_layout.addLayout(btn_row)

        # Step options
        step_group = QGroupBox("Step options")
        step_layout = QVBoxLayout(step_group)

        r = QHBoxLayout()
        r.addWidget(QLabel("Presence:"))
        self.step_presence = QComboBox()
        self.step_presence.addItems(["required", "optional", "forbidden"])
        self.step_presence.currentIndexChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_presence, 1)
        step_layout.addLayout(r)

        r = QHBoxLayout()
        r.addWidget(QLabel("Scope:"))
        self.step_scope = QComboBox()
        self.step_scope.addItems(["segment", "global"])
        self.step_scope.currentIndexChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_scope, 1)
        step_layout.addLayout(r)

        r = QHBoxLayout()
        self.step_use_any_of = QCheckBox("Use any_of")
        self.step_use_any_of.stateChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_use_any_of)
        step_layout.addLayout(r)

        r = QHBoxLayout()
        r.addWidget(QLabel("any_of:"))
        self.step_any_of = QLineEdit()
        self.step_any_of.setPlaceholderText("Comma-separated step types, e.g. DNSbyME,DNS")
        self.step_any_of.textChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_any_of, 1)
        step_layout.addLayout(r)

        r = QHBoxLayout()
        r.addWidget(QLabel("Label:"))
        self.step_label = QLineEdit()
        self.step_label.setPlaceholderText("Optional display label")
        self.step_label.textChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_label, 1)
        step_layout.addLayout(r)

        r = QHBoxLayout()
        self.step_use_min = QCheckBox("Min")
        self.step_use_min.stateChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_use_min)
        self.step_min = QSpinBox()
        self.step_min.setRange(0, 999)
        self.step_min.valueChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_min)
        self.step_use_max = QCheckBox("Max")
        self.step_use_max.stateChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_use_max)
        self.step_max = QSpinBox()
        self.step_max.setRange(0, 999)
        self.step_max.valueChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_max)
        step_layout.addLayout(r)

        r = QHBoxLayout()
        r.addWidget(QLabel("Too few:"))
        self.step_too_few = QComboBox()
        self.step_too_few.addItems(["(default)", "ok", "warn", "fail"])
        self.step_too_few.currentIndexChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_too_few, 1)
        step_layout.addLayout(r)

        r = QHBoxLayout()
        r.addWidget(QLabel("Too many:"))
        self.step_too_many = QComboBox()
        self.step_too_many.addItems(["(default)", "ok", "warn", "fail"])
        self.step_too_many.currentIndexChanged.connect(self._on_step_options_changed)
        r.addWidget(self.step_too_many, 1)
        step_layout.addLayout(r)

        seq_layout.addWidget(step_group)

        # Constraints (Approach 2 starter)
        cons_group = QGroupBox("Constraints")
        cons_layout = QVBoxLayout(cons_group)

        row = QHBoxLayout()
        self.max_gap_enabled = QCheckBox("Enforce max gap between steps")
        row.addWidget(self.max_gap_enabled, 1)
        row.addWidget(QLabel("Seconds:"))
        self.max_gap_seconds = QSpinBox()
        self.max_gap_seconds.setRange(0, 24 * 3600)
        self.max_gap_seconds.setValue(30)
        row.addWidget(self.max_gap_seconds)
        cons_layout.addLayout(row)
        seq_layout.addWidget(cons_group)

        body.addWidget(seq_group, 1)

        # Right: results (expandable)
        res_group = QGroupBox("Results")
        res_layout = QVBoxLayout(res_group)

        self.results_tree = QTreeWidget()
        self.results_tree.setColumnCount(3)
        self.results_tree.setHeaderLabels(["Step", "Status", "Summary"])
        self.results_tree.setUniformRowHeights(True)
        self.results_tree.setAlternatingRowColors(True)
        res_layout.addWidget(self.results_tree, 1)

        body.addWidget(res_group, 2)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch(1)

        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self._run)
        footer.addWidget(self.run_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        footer.addWidget(self.close_btn)

        root.addLayout(footer)

        self._load_scenarios_from_settings()

    def _format_step_payload(self, payload: dict) -> str:
        try:
            label = str(payload.get('label') or '').strip()
            if label:
                return label

            any_of = payload.get('any_of')
            if isinstance(any_of, list) and any_of:
                parts = [str(x).strip() for x in any_of if str(x).strip()]
                if parts:
                    return "AnyOf(" + "|".join(parts) + ")"
        except Exception:
            pass

        try:
            t = str(payload.get('type') or '').strip()
            return t if t else '(step)'
        except Exception:
            return '(step)'

    def _item_payload(self, item: Optional[QListWidgetItem]) -> dict:
        if item is None:
            return {}
        try:
            d = item.data(Qt.UserRole)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _set_item_payload(self, item: Optional[QListWidgetItem], payload: dict) -> None:
        if item is None:
            return
        try:
            item.setData(Qt.UserRole, payload)
            item.setText(self._format_step_payload(payload))
        except Exception:
            pass

    def _selected_item(self) -> Optional[QListWidgetItem]:
        try:
            return self.steps_list.currentItem()
        except Exception:
            return None

    def _on_select_step(self, _row: int):
        item = self._selected_item()
        payload = self._item_payload(item)

        self._block_step_option_signals(True)
        try:
            presence = str(payload.get('presence') or 'required').strip().lower()
            scope = str(payload.get('scope') or 'segment').strip().lower()
            label = str(payload.get('label') or '').strip()

            any_of = payload.get('any_of')
            any_of_list = any_of if isinstance(any_of, list) else []
            any_of_txt = ','.join([str(x).strip() for x in any_of_list if str(x).strip()])

            min_v = payload.get('min')
            if min_v is None:
                min_v = payload.get('min_count')
            max_v = payload.get('max')
            if max_v is None:
                max_v = payload.get('max_count')

            too_few = payload.get('too_few')
            if too_few is None:
                too_few = payload.get('on_too_few')
            too_many = payload.get('too_many')
            if too_many is None:
                too_many = payload.get('on_too_many')

            self.step_presence.setCurrentText(presence if presence in ('required', 'optional', 'forbidden') else 'required')
            self.step_scope.setCurrentText(scope if scope in ('segment', 'global') else 'segment')

            self.step_use_any_of.setChecked(bool(any_of_txt))
            self.step_any_of.setText(any_of_txt)
            self.step_label.setText(label)

            self.step_use_min.setChecked(min_v is not None)
            self.step_min.setValue(int(min_v) if min_v is not None else 0)
            self.step_use_max.setChecked(max_v is not None)
            self.step_max.setValue(int(max_v) if max_v is not None else 0)

            def _set_combo_default(combo: QComboBox, val) -> None:
                s = str(val or '').strip().lower()
                if not s:
                    combo.setCurrentIndex(0)
                elif s in ('ok', 'warn', 'fail'):
                    combo.setCurrentText(s)
                else:
                    combo.setCurrentIndex(0)

            _set_combo_default(self.step_too_few, too_few)
            _set_combo_default(self.step_too_many, too_many)

            self.step_any_of.setEnabled(self.step_use_any_of.isChecked())
        finally:
            self._block_step_option_signals(False)

    def _block_step_option_signals(self, block: bool) -> None:
        for w in (
            self.step_presence,
            self.step_scope,
            self.step_use_any_of,
            self.step_any_of,
            self.step_label,
            self.step_use_min,
            self.step_min,
            self.step_use_max,
            self.step_max,
            self.step_too_few,
            self.step_too_many,
        ):
            try:
                w.blockSignals(block)
            except Exception:
                pass

    def _on_step_options_changed(self, *_args):
        item = self._selected_item()
        if item is None:
            return

        payload = dict(self._item_payload(item) or {})

        presence = str(self.step_presence.currentText() or 'required').strip().lower()
        scope = str(self.step_scope.currentText() or 'segment').strip().lower()
        payload['presence'] = presence
        payload['scope'] = scope

        label = str(self.step_label.text() or '').strip()
        if label:
            payload['label'] = label
        else:
            payload.pop('label', None)

        use_any_of = bool(self.step_use_any_of.isChecked())
        self.step_any_of.setEnabled(use_any_of)
        if use_any_of:
            raw = str(self.step_any_of.text() or '')
            parts = [p.strip() for p in raw.replace(';', ',').split(',') if p.strip()]
            if parts:
                payload['any_of'] = parts
            else:
                payload.pop('any_of', None)
        else:
            payload.pop('any_of', None)

        if self.step_use_min.isChecked():
            payload['min'] = int(self.step_min.value())
        else:
            payload.pop('min', None)
            payload.pop('min_count', None)

        if self.step_use_max.isChecked():
            payload['max'] = int(self.step_max.value())
        else:
            payload.pop('max', None)
            payload.pop('max_count', None)

        tf = str(self.step_too_few.currentText() or '').strip().lower()
        if tf and tf != '(default)':
            payload['too_few'] = tf
        else:
            payload.pop('too_few', None)
            payload.pop('on_too_few', None)

        tm = str(self.step_too_many.currentText() or '').strip().lower()
        if tm and tm != '(default)':
            payload['too_many'] = tm
        else:
            payload.pop('too_many', None)
            payload.pop('on_too_many', None)

        self._set_item_payload(item, payload)

    def _settings(self):
        mw = self._main_window
        return getattr(mw, 'settings', None) if mw is not None else None

    def _load_scenarios_from_settings(self):
        settings = self._settings()
        scenarios = {"Default": {"sequence": ["DNSbyME", "DNS", "DP+", "TAC"], "constraints": {"max_gap_enabled": False, "max_gap_seconds": 30}}}
        selected = "Default"
        if settings is not None and hasattr(settings, 'get_scenarios'):
            try:
                scenarios = settings.get_scenarios() or scenarios
                selected = settings.get_selected_scenario_name() if hasattr(settings, 'get_selected_scenario_name') else selected
            except Exception:
                pass

        self._scenarios_cache = scenarios
        names = sorted(list(scenarios.keys()))
        if not names:
            names = ["Default"]
            self._scenarios_cache = {"Default": scenarios.get("Default") or {"sequence": ["DNSbyME", "DNS", "DP+", "TAC"], "constraints": {"max_gap_enabled": False, "max_gap_seconds": 30}}}

        self.scenario_combo.blockSignals(True)
        self.scenario_combo.clear()
        for n in names:
            self.scenario_combo.addItem(n)
        self.scenario_combo.blockSignals(False)

        idx = self.scenario_combo.findText(selected)
        if idx < 0:
            idx = 0
        self.scenario_combo.setCurrentIndex(idx)
        self._load_scenario_into_editor(self.scenario_combo.currentText())

    def _load_scenario_into_editor(self, name: str):
        payload = (getattr(self, '_scenarios_cache', {}) or {}).get(name) or {}
        seq = payload.get('sequence')
        if not isinstance(seq, list) or not seq:
            seq = [ScenarioStepType.DNS_BY_ME.value, ScenarioStepType.DNS.value, ScenarioStepType.DP_PLUS.value, ScenarioStepType.TAC.value]

        cons = payload.get('constraints')
        if not isinstance(cons, dict):
            cons = {}

        self.steps_list.clear()
        for s in seq:
            payload = {}
            if isinstance(s, dict):
                payload = dict(s)
                st = payload.get('type') or payload.get('step_type') or payload.get('step')
                if st is not None:
                    payload['type'] = str(st).strip()
            else:
                payload = {'type': str(s).strip()}

            if not str(payload.get('type') or '').strip() and not (isinstance(payload.get('any_of'), list) and payload.get('any_of')):
                continue

            it = QListWidgetItem(self._format_step_payload(payload))
            it.setData(Qt.UserRole, payload)
            self.steps_list.addItem(it)
        if self.steps_list.count() > 0:
            self.steps_list.setCurrentRow(0)

        try:
            self.max_gap_enabled.setChecked(bool(cons.get('max_gap_enabled', False)))
        except Exception:
            self.max_gap_enabled.setChecked(False)
        try:
            self.max_gap_seconds.setValue(int(cons.get('max_gap_seconds', 30) or 30))
        except Exception:
            self.max_gap_seconds.setValue(30)

        # Persist selected scenario
        settings = self._settings()
        if settings is not None and hasattr(settings, 'set_selected_scenario_name'):
            try:
                settings.set_selected_scenario_name(name)
            except Exception:
                pass

    def _on_select_scenario(self):
        name = str(self.scenario_combo.currentText() or '').strip()
        if not name:
            return
        self._load_scenario_into_editor(name)

    def _new_scenario(self):
        name, ok = QInputDialog.getText(self, 'New Scenario', 'Scenario name:')
        if not ok:
            return
        name = str(name or '').strip()
        if not name:
            return

        scenarios = dict(getattr(self, '_scenarios_cache', {}) or {})
        if name in scenarios:
            QMessageBox.information(self, 'Scenario', 'Scenario already exists.')
            return

        scenarios[name] = {
            'sequence': [ScenarioStepType.DNS_BY_ME.value, ScenarioStepType.DNS.value, ScenarioStepType.DP_PLUS.value, ScenarioStepType.TAC.value],
            'constraints': {'max_gap_enabled': False, 'max_gap_seconds': 30},
        }
        self._persist_scenarios(scenarios, select=name)

    def _delete_current_scenario(self):
        name = str(self.scenario_combo.currentText() or '').strip()
        if not name:
            return
        if name == 'Default':
            QMessageBox.information(self, 'Scenario', 'Default scenario cannot be deleted.')
            return

        scenarios = dict(getattr(self, '_scenarios_cache', {}) or {})
        if name not in scenarios:
            return
        scenarios.pop(name, None)
        self._persist_scenarios(scenarios, select='Default')

    def _persist_scenarios(self, scenarios: dict, select: str):
        self._scenarios_cache = scenarios
        settings = self._settings()
        if settings is not None and hasattr(settings, 'save_scenarios'):
            try:
                settings.save_scenarios(scenarios)
            except Exception:
                pass
        if settings is not None and hasattr(settings, 'set_selected_scenario_name'):
            try:
                settings.set_selected_scenario_name(select)
            except Exception:
                pass
        self._load_scenarios_from_settings()
        # Force selection
        idx = self.scenario_combo.findText(select)
        if idx >= 0:
            self.scenario_combo.setCurrentIndex(idx)

    def _save_current_scenario(self):
        name = str(self.scenario_combo.currentText() or '').strip()
        if not name:
            return

        scenarios = dict(getattr(self, '_scenarios_cache', {}) or {})
        scenarios[name] = {
            'sequence': self._current_steps_payloads(),
            'constraints': {
                'max_gap_enabled': bool(self.max_gap_enabled.isChecked()),
                'max_gap_seconds': int(self.max_gap_seconds.value()),
            },
        }
        self._persist_scenarios(scenarios, select=name)

    def _current_steps_payloads(self) -> list[object]:
        out: list[object] = []
        for i in range(self.steps_list.count()):
            item = self.steps_list.item(i)
            if item is None:
                continue
            payload = self._item_payload(item)
            if not payload:
                continue
            t = str(payload.get('type') or '').strip()

            def _has_non_default_fields(p: dict) -> bool:
                if str(p.get('label') or '').strip():
                    return True
                ao = p.get('any_of')
                if isinstance(ao, list) and any(str(x).strip() for x in ao):
                    return True
                if str(p.get('presence') or '').strip().lower() not in ('', 'required'):
                    return True
                if str(p.get('scope') or '').strip().lower() not in ('', 'segment'):
                    return True
                for k in ('min', 'max', 'min_count', 'max_count', 'too_few', 'too_many', 'on_too_few', 'on_too_many'):
                    if p.get(k) is not None and str(p.get(k) or '').strip() != '':
                        return True
                return False

            if t and not _has_non_default_fields(payload) and not (isinstance(payload.get('any_of'), list) and payload.get('any_of')):
                out.append(t)
            else:
                # Keep a compact schema
                obj: dict = {}
                if t:
                    obj['type'] = t
                if isinstance(payload.get('any_of'), list) and payload.get('any_of'):
                    obj['any_of'] = [str(x).strip() for x in payload.get('any_of') if str(x).strip()]
                if str(payload.get('label') or '').strip():
                    obj['label'] = str(payload.get('label') or '').strip()
                pres = str(payload.get('presence') or '').strip().lower()
                if pres and pres != 'required':
                    obj['presence'] = pres
                sc = str(payload.get('scope') or '').strip().lower()
                if sc and sc != 'segment':
                    obj['scope'] = sc
                if payload.get('min') is not None:
                    obj['min'] = payload.get('min')
                if payload.get('max') is not None:
                    obj['max'] = payload.get('max')
                if payload.get('too_few') is not None:
                    obj['too_few'] = payload.get('too_few')
                if payload.get('too_many') is not None:
                    obj['too_many'] = payload.get('too_many')
                out.append(obj)
        return out

    # Backward-compatible alias (not used by UI anymore)
    def _save_sequence(self):
        self._save_current_scenario()

    def _add_step(self):
        val = str(self.step_type_combo.currentText() or '').strip()
        if not val:
            return
        payload = {'type': val, 'presence': 'required', 'scope': 'segment'}
        it = QListWidgetItem(self._format_step_payload(payload))
        it.setData(Qt.UserRole, payload)
        self.steps_list.addItem(it)
        self.steps_list.setCurrentRow(self.steps_list.count() - 1)

    def _remove_step(self):
        r = self.steps_list.currentRow()
        if r < 0:
            return
        self.steps_list.takeItem(r)
        if self.steps_list.count() > 0:
            self.steps_list.setCurrentRow(min(r, self.steps_list.count() - 1))

    def _move_up(self):
        r = self.steps_list.currentRow()
        if r <= 0:
            return
        item = self.steps_list.takeItem(r)
        self.steps_list.insertItem(r - 1, item)
        self.steps_list.setCurrentRow(r - 1)

    def _move_down(self):
        r = self.steps_list.currentRow()
        if r < 0 or r >= self.steps_list.count() - 1:
            return
        item = self.steps_list.takeItem(r)
        self.steps_list.insertItem(r + 1, item)
        self.steps_list.setCurrentRow(r + 1)

    def _build_step_defs(self) -> list[ScenarioStep]:
        steps: list[ScenarioStep] = []

        for obj in self._current_steps_payloads():
            if isinstance(obj, str):
                try:
                    steps.append(ScenarioStep(step_type=ScenarioStepType(obj)))
                except Exception:
                    continue
                continue

            if not isinstance(obj, dict):
                continue

            t = str(obj.get('type') or '').strip()
            any_of_raw = obj.get('any_of')
            any_of: list[ScenarioStepType] = []
            if isinstance(any_of_raw, list):
                for x in any_of_raw:
                    sx = str(x or '').strip()
                    if not sx:
                        continue
                    try:
                        any_of.append(ScenarioStepType(sx))
                    except Exception:
                        continue

            if t:
                try:
                    st = ScenarioStepType(t)
                except Exception:
                    continue
            elif any_of:
                st = any_of[0]
            else:
                continue

            presence_raw = str(obj.get('presence') or 'required').strip().lower()
            presence = ScenarioStepPresence.REQUIRED
            if presence_raw == 'optional':
                presence = ScenarioStepPresence.OPTIONAL
            elif presence_raw == 'forbidden':
                presence = ScenarioStepPresence.FORBIDDEN

            scope_raw = str(obj.get('scope') or 'segment').strip().lower()
            scope = ScenarioStepScope.SEGMENT
            if scope_raw == 'global':
                scope = ScenarioStepScope.GLOBAL

            def _int_or_none(v) -> Optional[int]:
                try:
                    if v is None or v == '':
                        return None
                    return int(v)
                except Exception:
                    return None

            min_count = _int_or_none(obj.get('min', obj.get('min_count')))
            max_count = _int_or_none(obj.get('max', obj.get('max_count')))
            too_few = obj.get('too_few', obj.get('on_too_few'))
            too_many = obj.get('too_many', obj.get('on_too_many'))
            label = str(obj.get('label') or '').strip() or None

            steps.append(
                ScenarioStep(
                    step_type=st,
                    any_of=any_of or None,
                    scope=scope,
                    label=label,
                    presence=presence,
                    min_count=min_count,
                    max_count=max_count,
                    on_too_few=str(too_few) if too_few is not None else None,
                    on_too_many=str(too_many) if too_many is not None else None,
                )
            )
        return steps

    def _run(self):
        mw = self._main_window
        parser = getattr(mw, 'parser', None) if mw is not None else None
        if parser is None:
            QMessageBox.information(self, "Scenario", "Open an XTI file first.")
            return

        vm = getattr(mw, 'validation_manager', None) if mw is not None else None
        issues = getattr(vm, 'issues', None) if vm is not None else None

        steps = self._build_step_defs()
        if not steps:
            QMessageBox.information(self, "Scenario", "Add at least one step.")
            return

        result = run_scenario(
            parser,
            issues,
            steps,
            max_gap_enabled=bool(self.max_gap_enabled.isChecked()),
            max_gap_seconds=int(self.max_gap_seconds.value()),
        )
        self.overall_label.setText(f"Overall: {result.overall_status}")
        self.summary_label.setText(f"Sequence summary: {getattr(result, 'steps_summary', '') or 'N/A'}")

        self.results_tree.clear()

        for sr in result.results:
            step_name = getattr(sr.step, 'label', None) or sr.step.step_type.value
            top = QTreeWidgetItem([str(step_name), sr.status, sr.message])
            top.setFirstColumnSpanned(False)
            self.results_tree.addTopLevelItem(top)

            if sr.evidence is not None:
                ev = sr.evidence
                ip_txt = ', '.join(ev.ips) if ev.ips else '(none)'
                srv_txt = ', '.join(getattr(ev, 'servers', []) or []) or '(n/a)'
                QTreeWidgetItem(top, ["Evidence", "", f"Count: {getattr(ev, 'count', 0)}   Bytes: {getattr(ev, 'bytes_total', 0)}"])
                QTreeWidgetItem(top, ["", "", f"Servers: {srv_txt}  IPs: {ip_txt}"])
                QTreeWidgetItem(top, ["", "", f"Issues summary: {ev.issues_summary}"])

            # Expandable parsing log details
            issues_list = sr.issues or []
            if issues_list:
                issues_node = QTreeWidgetItem(top, ["Issues", "", f"{len(issues_list)} issue(s)"])
                for iss in issues_list[:200]:
                    try:
                        sev = getattr(iss.severity, 'value', str(iss.severity))
                    except Exception:
                        sev = str(getattr(iss, 'severity', ''))
                    cat = str(getattr(iss, 'category', '') or '')
                    msg = str(getattr(iss, 'message', '') or '')
                    idx = getattr(iss, 'trace_index', None)
                    tail = f"{cat}: {msg}"
                    if idx is not None:
                        tail = f"[{idx}] {tail}"
                    QTreeWidgetItem(issues_node, ["", str(sev), tail])

            # Default expand failures/warns
            if sr.status in ('FAIL', 'WARN'):
                top.setExpanded(True)

        self.results_tree.expandToDepth(0)
