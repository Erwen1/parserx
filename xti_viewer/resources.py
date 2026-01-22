from __future__ import annotations

from pathlib import Path
import os
import sys


def resource_path(relative_path: str) -> str:
    """Return an absolute path to a bundled resource.

    Works both in development and in PyInstaller onefile mode.
    """
    rel = relative_path.replace("/", os.sep).replace("\\", os.sep)

    # PyInstaller onefile extracts to a temp dir exposed as sys._MEIPASS
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = Path(base) / rel
        if candidate.exists():
            return str(candidate)

    # Dev / source tree: xti_viewer/.. is repo root
    repo_root = Path(__file__).resolve().parent.parent
    candidate = repo_root / rel
    if candidate.exists():
        return str(candidate)

    # Fallback: relative to current working directory
    return str((Path.cwd() / rel).resolve())
