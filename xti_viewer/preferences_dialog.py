"""Application Preferences Dialog."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QWidget, QGroupBox,
    QCheckBox, QSpinBox, QComboBox, QLineEdit,
    QFileDialog, QFormLayout
)
from PySide6.QtCore import Qt
import json
import os


class PreferencesDialog(QDialog):
    """Dialog for application preferences and settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        # Load current settings
        self.config_file = "preferences.json"
        self.settings = self._load_preferences()
        
        self._init_ui()
        self._load_current_values()
    
    def _load_preferences(self):
        """Load preferences from JSON file."""
        default_settings = {
            "appearance": {
                "font_size": 9,
                "theme": "System",
                "show_toolbar": True,
                "compact_mode": False
            },
            "behavior": {
                "auto_expand_details": False,
                "confirm_exit": True,
                "remember_window_state": True,
                "max_recent_files": 10
            },
            "export": {
                "default_export_dir": "",
                "auto_open_after_export": False,
                "export_format": "CSV"
            },
            "debugging": {
                "enable_logging": False,
                "log_level": "INFO",
                "log_to_file": False
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for category in default_settings:
                        if category in loaded:
                            default_settings[category].update(loaded[category])
                    return default_settings
            except Exception:
                pass
        
        return default_settings
    
    def _save_preferences(self):
        """Save preferences to JSON file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            return False
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # Appearance tab
        appearance_tab = self._create_appearance_tab()
        tabs.addTab(appearance_tab, "Appearance")
        
        # Behavior tab
        behavior_tab = self._create_behavior_tab()
        tabs.addTab(behavior_tab, "Behavior")
        
        # Export tab
        export_tab = self._create_export_tab()
        tabs.addTab(export_tab, "Export")
        
        # Debugging tab
        debug_tab = self._create_debug_tab()
        tabs.addTab(debug_tab, "Debugging")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Reset to defaults
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_button)
        
        # Cancel
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        # Save
        save_button = QPushButton("Save")
        save_button.setDefault(True)
        save_button.clicked.connect(self._save_and_close)
        button_layout.addWidget(save_button)
        
        layout.addLayout(button_layout)
    
    def _create_appearance_tab(self):
        """Create appearance settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Display group
        display_group = QGroupBox("Display")
        display_layout = QFormLayout()
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 16)
        self.font_size_spin.setSuffix(" pt")
        display_layout.addRow("Font Size:", self.font_size_spin)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        display_layout.addRow("Theme:", self.theme_combo)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # Layout group
        layout_group = QGroupBox("Layout")
        layout_layout = QVBoxLayout()
        
        self.show_toolbar_check = QCheckBox("Show toolbar")
        layout_layout.addWidget(self.show_toolbar_check)
        
        self.compact_mode_check = QCheckBox("Compact mode (reduce spacing)")
        layout_layout.addWidget(self.compact_mode_check)
        
        layout_group.setLayout(layout_layout)
        layout.addWidget(layout_group)
        
        layout.addStretch()
        return widget
    
    def _create_behavior_tab(self):
        """Create behavior settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # General behavior group
        behavior_group = QGroupBox("General")
        behavior_layout = QVBoxLayout()
        
        self.auto_expand_check = QCheckBox("Auto-expand details when selecting item")
        behavior_layout.addWidget(self.auto_expand_check)
        
        self.confirm_exit_check = QCheckBox("Confirm before exiting")
        behavior_layout.addWidget(self.confirm_exit_check)
        
        self.remember_window_check = QCheckBox("Remember window size and position")
        behavior_layout.addWidget(self.remember_window_check)
        
        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)
        
        # Recent files group
        recent_group = QGroupBox("Recent Files")
        recent_layout = QFormLayout()
        
        self.max_recent_spin = QSpinBox()
        self.max_recent_spin.setRange(5, 20)
        recent_layout.addRow("Maximum recent files:", self.max_recent_spin)
        
        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)
        
        layout.addStretch()
        return widget
    
    def _create_export_tab(self):
        """Create export settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Export options group
        export_group = QGroupBox("Export Options")
        export_layout = QFormLayout()
        
        # Default directory
        dir_layout = QHBoxLayout()
        self.export_dir_edit = QLineEdit()
        dir_layout.addWidget(self.export_dir_edit)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_export_dir)
        dir_layout.addWidget(browse_button)
        export_layout.addRow("Default export directory:", dir_layout)
        
        # Format
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["CSV", "JSON", "XML"])
        export_layout.addRow("Default format:", self.export_format_combo)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # Post-export behavior
        post_export_group = QGroupBox("After Export")
        post_export_layout = QVBoxLayout()
        
        self.auto_open_check = QCheckBox("Automatically open exported file")
        post_export_layout.addWidget(self.auto_open_check)
        
        post_export_group.setLayout(post_export_layout)
        layout.addWidget(post_export_group)
        
        layout.addStretch()
        return widget
    
    def _create_debug_tab(self):
        """Create debugging settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Logging group
        logging_group = QGroupBox("Logging")
        logging_layout = QVBoxLayout()
        
        self.enable_logging_check = QCheckBox("Enable logging")
        self.enable_logging_check.toggled.connect(self._on_logging_toggled)
        logging_layout.addWidget(self.enable_logging_check)
        
        level_layout = QFormLayout()
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        level_layout.addRow("Log level:", self.log_level_combo)
        logging_layout.addLayout(level_layout)
        
        self.log_to_file_check = QCheckBox("Save logs to file (xti_viewer.log)")
        logging_layout.addWidget(self.log_to_file_check)
        
        logging_group.setLayout(logging_layout)
        layout.addWidget(logging_group)
        
        # Note
        note_label = QLabel(
            "<i>Note: Logging helps diagnose issues but may impact performance.</i>"
        )
        note_label.setWordWrap(True)
        layout.addWidget(note_label)
        
        layout.addStretch()
        return widget
    
    def _load_current_values(self):
        """Load current settings values into UI controls."""
        # Appearance
        self.font_size_spin.setValue(self.settings["appearance"]["font_size"])
        self.theme_combo.setCurrentText(self.settings["appearance"]["theme"])
        self.show_toolbar_check.setChecked(self.settings["appearance"]["show_toolbar"])
        self.compact_mode_check.setChecked(self.settings["appearance"]["compact_mode"])
        
        # Behavior
        self.auto_expand_check.setChecked(self.settings["behavior"]["auto_expand_details"])
        self.confirm_exit_check.setChecked(self.settings["behavior"]["confirm_exit"])
        self.remember_window_check.setChecked(self.settings["behavior"]["remember_window_state"])
        self.max_recent_spin.setValue(self.settings["behavior"]["max_recent_files"])
        
        # Export
        self.export_dir_edit.setText(self.settings["export"]["default_export_dir"])
        self.export_format_combo.setCurrentText(self.settings["export"]["export_format"])
        self.auto_open_check.setChecked(self.settings["export"]["auto_open_after_export"])
        
        # Debugging
        self.enable_logging_check.setChecked(self.settings["debugging"]["enable_logging"])
        self.log_level_combo.setCurrentText(self.settings["debugging"]["log_level"])
        self.log_to_file_check.setChecked(self.settings["debugging"]["log_to_file"])
        self._on_logging_toggled(self.settings["debugging"]["enable_logging"])
    
    def _collect_values(self):
        """Collect values from UI controls."""
        self.settings["appearance"]["font_size"] = self.font_size_spin.value()
        self.settings["appearance"]["theme"] = self.theme_combo.currentText()
        self.settings["appearance"]["show_toolbar"] = self.show_toolbar_check.isChecked()
        self.settings["appearance"]["compact_mode"] = self.compact_mode_check.isChecked()
        
        self.settings["behavior"]["auto_expand_details"] = self.auto_expand_check.isChecked()
        self.settings["behavior"]["confirm_exit"] = self.confirm_exit_check.isChecked()
        self.settings["behavior"]["remember_window_state"] = self.remember_window_check.isChecked()
        self.settings["behavior"]["max_recent_files"] = self.max_recent_spin.value()
        
        self.settings["export"]["default_export_dir"] = self.export_dir_edit.text()
        self.settings["export"]["export_format"] = self.export_format_combo.currentText()
        self.settings["export"]["auto_open_after_export"] = self.auto_open_check.isChecked()
        
        self.settings["debugging"]["enable_logging"] = self.enable_logging_check.isChecked()
        self.settings["debugging"]["log_level"] = self.log_level_combo.currentText()
        self.settings["debugging"]["log_to_file"] = self.log_to_file_check.isChecked()
    
    def _browse_export_dir(self):
        """Browse for export directory."""
        current_dir = self.export_dir_edit.text() or ""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Default Export Directory",
            current_dir
        )
        if directory:
            self.export_dir_edit.setText(directory)
    
    def _on_logging_toggled(self, enabled):
        """Handle logging enabled/disabled."""
        self.log_level_combo.setEnabled(enabled)
        self.log_to_file_check.setEnabled(enabled)
    
    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.settings = self._load_preferences()
        # Force reload defaults by removing file
        if os.path.exists(self.config_file):
            try:
                os.remove(self.config_file)
            except:
                pass
        self.settings = self._load_preferences()
        self._load_current_values()
    
    def _save_and_close(self):
        """Save settings and close dialog."""
        self._collect_values()
        if self._save_preferences():
            self.accept()
        else:
            # Could show error message here
            self.reject()
    
    def get_settings(self):
        """Get the current settings dictionary."""
        return self.settings
