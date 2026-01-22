"""
Centralized styling for XTI Viewer.
Defines color palettes and QSS (Qt Style Sheets) for a modern look.
"""

class ModernTheme:
    """Modern Slate & Indigo Theme Palette."""
    
    # Colors
    BG_APP = "#f8fafc"       # Slate-50
    BG_PANEL = "#ffffff"     # White
    BG_HEADER = "#f1f5f9"    # Slate-100
    BG_HOVER = "#f1f5f9"     # Slate-100
    BG_SELECTED = "#e0e7ff"  # Indigo-100
    
    BORDER_SUBTLE = "#e2e8f0" # Slate-200
    BORDER_FOCUS = "#6366f1"  # Indigo-500
    
    TEXT_MAIN = "#0f172a"    # Slate-900
    TEXT_MUTED = "#64748b"   # Slate-500
    TEXT_INVERSE = "#ffffff"
    
    PRIMARY = "#4f46e5"      # Indigo-600
    PRIMARY_HOVER = "#4338ca" # Indigo-700
    
    # Status Colors
    SUCCESS_BG = "#dcfce7"   # Emerald-100
    SUCCESS_TEXT = "#166534" # Emerald-800
    WARN_BG = "#ffedd5"      # Orange-100
    WARN_TEXT = "#9a3412"    # Orange-800
    ERROR_BG = "#fee2e2"     # Red-100
    ERROR_TEXT = "#991b1b"   # Red-800

    @staticmethod
    def get_stylesheet() -> str:
        """Returns the global QSS for the application."""
        return f"""
        QMainWindow, QDialog {{
            background-color: {ModernTheme.BG_APP};
            color: {ModernTheme.TEXT_MAIN};
        }}
        
        QWidget {{
            font-family: 'Segoe UI', 'Inter', sans-serif;
            font-size: 13px;
            color: {ModernTheme.TEXT_MAIN};
        }}
        
        /* Splitters */
        QSplitter::handle {{
            background-color: {ModernTheme.BORDER_SUBTLE};
            width: 1px;
            height: 1px;
        }}
        
        /* Tab Widget */
        QTabWidget::pane {{
            border: 1px solid {ModernTheme.BORDER_SUBTLE};
            background: {ModernTheme.BG_PANEL};
            border-radius: 4px;
        }}
        
        QTabBar::tab {{
            background: {ModernTheme.BG_HEADER};
            border: 1px solid {ModernTheme.BORDER_SUBTLE};
            padding: 6px 12px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            color: {ModernTheme.TEXT_MUTED};
        }}
        
        QTabBar::tab:selected {{
            background: {ModernTheme.BG_PANEL};
            color: {ModernTheme.PRIMARY};
            border-bottom-color: {ModernTheme.BG_PANEL};
            font-weight: bold;
        }}
        
        QTabBar::tab:hover {{
            background: {ModernTheme.BG_HOVER};
        }}
        
        /* Tree/Table Views */
        QTreeView, QTableView, QListWidget {{
            background-color: {ModernTheme.BG_PANEL};
            border: 1px solid {ModernTheme.BORDER_SUBTLE};
            border-radius: 4px;
            outline: none;
            selection-background-color: {ModernTheme.BG_SELECTED};
            selection-color: {ModernTheme.TEXT_MAIN};
            gridline-color: {ModernTheme.BORDER_SUBTLE};
        }}
        
        QTreeView::item, QTableView::item {{
            padding: 4px;
            border-bottom: 1px solid {ModernTheme.BG_APP};
        }}
        
        QTreeView::item:selected, QTableView::item:selected {{
            background-color: {ModernTheme.BG_SELECTED};
            color: {ModernTheme.PRIMARY};
            border-left: 3px solid {ModernTheme.PRIMARY};
        }}
        
        QTreeView::item:hover, QTableView::item:hover {{
            background-color: {ModernTheme.BG_HOVER};
        }}
        
        QHeaderView::section {{
            background-color: {ModernTheme.BG_HEADER};
            color: {ModernTheme.TEXT_MUTED};
            padding: 6px;
            border: none;
            border-bottom: 1px solid {ModernTheme.BORDER_SUBTLE};
            border-right: 1px solid {ModernTheme.BORDER_SUBTLE};
            font-weight: bold;
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: {ModernTheme.BG_PANEL};
            border: 1px solid {ModernTheme.BORDER_SUBTLE};
            border-radius: 4px;
            padding: 6px 12px;
            color: {ModernTheme.TEXT_MAIN};
        }}
        
        QPushButton:hover {{
            background-color: {ModernTheme.BG_HOVER};
            border-color: {ModernTheme.TEXT_MUTED};
        }}
        
        QPushButton:pressed {{
            background-color: {ModernTheme.BG_SELECTED};
        }}
        
        QPushButton:disabled {{
            background-color: {ModernTheme.BG_APP};
            color: {ModernTheme.TEXT_MUTED};
            border-color: {ModernTheme.BORDER_SUBTLE};
        }}
        
        /* Inputs */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {ModernTheme.BG_PANEL};
            border: 1px solid {ModernTheme.BORDER_SUBTLE};
            border-radius: 4px;
            padding: 4px;
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 1px solid {ModernTheme.PRIMARY};
        }}
        
        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: {ModernTheme.BG_APP};
            width: 10px;
            margin: 0;
        }}
        
        QScrollBar::handle:vertical {{
            background: {ModernTheme.BORDER_SUBTLE};
            min-height: 20px;
            border-radius: 5px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background: {ModernTheme.TEXT_MUTED};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        /* GroupBox */
        QGroupBox {{
            border: 1px solid {ModernTheme.BORDER_SUBTLE};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            font-weight: bold;
            color: {ModernTheme.TEXT_MUTED};
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            left: 10px;
        }}
        
        /* Status Bar */
        QStatusBar {{
            background: {ModernTheme.BG_HEADER};
            border-top: 1px solid {ModernTheme.BORDER_SUBTLE};
            color: {ModernTheme.TEXT_MUTED};
        }}
        """
