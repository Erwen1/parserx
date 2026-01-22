"""
XTI Viewer - A desktop application for browsing Universal Tracer .xti files.

This is the main entry point for the application.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xti_viewer.ui_main import main

if __name__ == "__main__":
    main()