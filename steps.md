Build a desktop app to browse .xti traces (Universal Tracer–style)

You are an expert Python developer (PySide6/PyQt5, XML parsing, desktop UX). Build a small GUI application that loads and explores Gemalto/Thales Universal Tracer .xti files (XML).

Goal & behavior

Replicate the layout/behavior from Universal Tracer:

Left pane (top): “Interpretation” list

Show one row per <traceitem> in the XTI.

For each row, display ONLY the first interpreted result string (the topmost content on the first <interpretedresult> inside <interpretation>).

Example: ENVELOPE Event Download - Location Status (do not show every child line here).

Additional columns (if available from the XML): Protocol (traceitem@protocol), Type (traceitem@type), Timestamp (compose from any available date/time fields in the file if present; OK to leave blank if not found).

Allow filter text box above the list for quick search over the first-line text.

Left pane (bottom): “Inspector”

When the user clicks a row in the top list, populate this bottom inspector with the full details of that interpretation:

Render the entire nested hierarchy of all <interpretedresult> nodes under that interpretation as an indented tree.

Each node shows its content attribute.

Preserve order and nesting exactly as in the XML.

Also show any other available sections from that traceitem that are useful (e.g., command details, device identity, etc.) if present in the interpretation tree.

Right pane: “Raw & Hex”

Show the <data> element’s rawhex for the selected traceitem (if present), and a simple bytes view (grouped hex with byte offsets).

Provide a copy button for hex.

File menu

“Open .xti…” to load a file.

Remember the last folder.

Performance

XTI files can be a few MB; parsing must be fast and UI must remain responsive.

Use a background thread or QtConcurrent for parsing, then populate models on the GUI thread.

Use lazy population of the inspector tree (populate on selection).

Quality of life

Keyboard up/down navigates the list.

Double-click row = expand inspector and focus it.

Status bar shows item count and currently selected protocol/type.

Robust error messages if the file is not valid XML.

Tech & structure

Python 3.10+.

Prefer PySide6 (fallback to PyQt5 is fine).

No external heavy deps. Use stdlib xml.etree.ElementTree (or lxml if you think it’s safer).

Package layout:

xti_viewer/
  main.py
  ui_main.py (or inline in main)
  xti_parser.py
  models.py
  utils.py
  README.md


xti_parser.py

Parse the XML root <tracedata>.

For each <traceitem>:

Collect:

protocol (attr)

type (attr)

data.rawhex (child <data @rawhex>, if present)

interpretation → the first <interpretedresult> (this is the summary string for the top list).

The entire interpreted tree (all nested <interpretedresult> descendants) for the inspector.

Optional timestamp: search for attributes like date, month, year, hour, minute, second, millisecond, nanosecond anywhere under the same traceitem; if not per-item, leave blank.

Expose a simple Python dataclass:

@dataclass
class TraceItem:
    protocol: str | None
    type: str | None
    summary: str            # first interpreted result content
    rawhex: str | None
    timestamp: str | None   # formatted if available
    details_tree: TreeNode  # your own class: content:str, children:list[TreeNode]


models.py

QStandardItemModel for the top list with columns: Summary, Protocol, Type, Timestamp.

Selection change signal triggers the inspector population.

Inspector

Use QTreeWidget or QTreeView with a simple model that mirrors details_tree.

Indentation should reflect nesting; tooltips show full text when long.

Right Hex view

A read-only QPlainTextEdit showing grouped hex with offsets. Provide a “Copy” button.

Search

A search box above the top list that filters by the summary string (case-insensitive contains).

Error handling

If the file is not valid XML or <traceitem> is missing, show a modal dialog with a concise error and a suggestion.

Acceptance criteria

Opening the sample EXS82-W_enable-profil_NOTOK.xti:

The top list shows one line per traceitem using only the first interpreted result content.

Clicking any row fills the inspector with the entire nested interpreted tree for that item, line-for-line and level-for-level.

The right pane shows the rawhex of that item (if present).

Filter box narrows the top list by substring in the summary.

App remains responsive during load (no frozen window).

Code is clean, commented, and includes a short README.md with run instructions (pip install PySide6 and python -m xti_viewer.main).

Helpful notes about the XTI structure

The file is XML. Each <traceitem> typically looks like:

<traceitem protocol="ISO7816" type="apducommand">
  <data rawhex="..." type="apducommand" />
  <interpretation>
    <interpretedresult content="(THIS IS THE SUMMARY LINE)">
      <interpretedresult content="Child line 1">
        <interpretedresult content="Child line 1.1" />
      </interpretedresult>
      <interpretedresult content="Child line 2" />
    </interpretedresult>
  </interpretation>
</traceitem>


The summary for the top list is the content of the first <interpretedresult> under <interpretation>.

The inspector should render all descendants (depth-first, in order) as a tree.

Deliverables

A runnable Python project as described, with:

main.py launching the GUI.

Parser and models per spec.

README with setup/run instructions.

Include a minimal unit test for the parser that asserts:

It extracts the first interpreted result.

It builds the full interpreted tree.

It reads rawhex when present.