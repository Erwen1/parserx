# XTI Viewer

A desktop application for browsing and exploring Gemalto/Thales Universal Tracer .xti files (XML). This application replicates the layout and behavior of Universal Tracer with a clean, responsive interface.

## Features

- **Interpretation List**: Browse trace items with summary, protocol, type, and timestamp information
- **Real-time Search**: Filter trace items by interpretation text
- **Detailed Inspector**: View complete interpretation hierarchy in tree format
- **Hex Viewer**: Display raw hex data with formatted output and copy functionality
- **Keyboard Navigation**: Navigate with arrow keys and double-click to expand details
- **Background Parsing**: Responsive UI with background file loading
- **Settings Persistence**: Remembers window layout and last opened directory

## Screenshots

The application provides a two-pane layout:
- **Left Pane**: Interpretation list (top) and detailed inspector (bottom)
- **Right Pane**: Hex viewer with formatted display and copy button

## Installation

### Requirements

- Python 3.10 or higher
- PySide6 (Qt for Python)

# TLS Report Viewer (standalone)
### Setup


3. Run the application:

```bash
python -m xti_viewer.main
```

Or from the project directory:

```bash
python -m xti_viewer.main [optional_xti_file.xti]
```

## Usage

## Headless CLI (no GUI)

You can extract key outputs without launching the GUI:

```bash
python -m xti_viewer.cli flow-overview path/to/file.xti
python -m xti_viewer.cli flow-sessions path/to/file.xti
python -m xti_viewer.cli flow-events path/to/file.xti
python -m xti_viewer.cli parsing-log path/to/file.xti
```

Useful options:

```bash
python -m xti_viewer.cli flow-overview path/to/file.xti --format json
python -m xti_viewer.cli parsing-log path/to/file.xti               # default: warnings
python -m xti_viewer.cli parsing-log path/to/file.xti --all         # info+warning+critical
python -m xti_viewer.cli parsing-log path/to/file.xti --severity critical
python -m xti_viewer.cli parsing-log path/to/file.xti --severity warning --severity info
python -m xti_viewer.cli parsing-log path/to/file.xti --category "Location Status"
python -m xti_viewer.cli parsing-log path/to/file.xti --since "11/06/2025 16:55:40" --until "11/06/2025 17:00:00"
python -m xti_viewer.cli parsing-log path/to/file.xti --out parsing_log.txt
```

If you want a console executable, build it with:

```powershell
./build_exe.ps1 -BuildCli
```

This produces `dist\XTIViewerCLI.exe` in addition to the GUI `dist\XTIViewer.exe`.

### Opening Files

3. Select your .xti file

You can also pass a file path as a command-line argument:

```bash
python -m xti_viewer.main path/to/your/file.xti
```

### Navigation

- **Search**: Type in the filter box to search interpretation text
- **Selection**: Click any row to view details in the inspector and hex viewer
- **Keyboard**: Use **Up/Down** arrows to navigate the list
- **Expand**: Double-click a row to expand the inspector and focus it
- **Copy Hex**: Click the "Copy Hex" button to copy raw hex data to clipboard

### Interface Layout

#### Interpretation List (Top Left)
- Shows one row per `<traceitem>` from the XTI file
- Displays the first interpreted result string as the summary
- Additional columns show Protocol, Type, and Timestamp (when available)
- Sortable by clicking column headers

#### Inspector (Bottom Left)
- Shows the complete interpretation hierarchy when a row is selected
- Displays all nested `<interpretedresult>` nodes as an indented tree
- Preserves exact order and nesting from the XML
- Tooltips show full content for long text

#### Hex Viewer (Right Pane)
- Displays the `<data rawhex>` content for the selected item
- Formatted with byte offsets, hex grouping, and ASCII representation
- Copy button provides clean hex text for clipboard

## File Format

The application expects XTI files with the following XML structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<tracedata>
    <traceitem protocol="ISO7816" type="apducommand">
        <data rawhex="00A4040007A0000001510000" type="apducommand" />
        <interpretation>
            <interpretedresult content="ENVELOPE Event Download - Location Status">
                <interpretedresult content="Command Details">
                    <interpretedresult content="CLA = 00 (ISO/IEC 7816)" />
                    <interpretedresult content="INS = A4 (SELECT FILE)" />
                </interpretedresult>
            </interpretedresult>
        </interpretation>
    </traceitem>
</tracedata>
```

### Required Elements

- Root `<tracedata>` element
- One or more `<traceitem>` elements
- Each traceitem must have an `<interpretation>` element
- First `<interpretedresult>` under interpretation provides the summary text

### Optional Elements

- `protocol` and `type` attributes on `<traceitem>`
- `<data rawhex="...">` element for hex display
- Timestamp attributes (various formats supported)

## Development

### Project Structure

```
xti_viewer/
├── __init__.py
├── main.py          # Entry point
├── ui_main.py       # Main GUI implementation
├── xti_parser.py    # XML parsing logic
├── models.py        # Qt data models
└── utils.py         # Utility functions
```

### Running Tests

The project includes unit tests for the parser functionality:

```bash
python -m pytest test_xti_parser.py -v
```

Or run directly:

```bash
python test_xti_parser.py
```

### Key Classes

- **`XTIParser`**: Handles XML parsing and data extraction
- **`TraceItem`**: Data class representing a single trace item
- **`TreeNode`**: Represents interpretation hierarchy
- **`XTIMainWindow`**: Main GUI application window
- **`TraceItemsModel`**: Qt model for the interpretation list
- **`InspectorTreeModel`**: Qt model for the inspector tree

## Error Handling

The application provides robust error handling for:

- **Invalid XML**: Clear error messages for malformed files
- **Missing Elements**: Graceful handling of incomplete trace items
- **File Access**: Proper error reporting for file system issues
- **Large Files**: Background parsing with progress indication

## Performance

- **Background Parsing**: Files are parsed in separate threads to keep UI responsive
- **Lazy Loading**: Inspector tree is populated only when items are selected
- **Efficient Filtering**: Real-time search with optimized string matching
- **Memory Management**: Proper cleanup of resources and threading

## Troubleshooting

### Common Issues

1. **"Invalid XML" Error**: Ensure your file is a valid XTI file with proper XML structure
2. **No Items Displayed**: Check that your file contains `<traceitem>` elements with `<interpretation>`
3. **Missing Hex Data**: Not all trace items have hex data; this is normal
4. **Performance Issues**: Very large files (>100MB) may take time to load

### System Requirements

- Windows 10/11, macOS 10.14+, or Linux
- 4GB RAM minimum (8GB recommended for large files)
- 100MB disk space for installation

## License

This project is provided as-is for educational and development purposes.

## Support

For issues or questions:

1. Check that your XTI file follows the expected format
2. Verify all dependencies are correctly installed
3. Run the unit tests to ensure the parser is working correctly

## Version History

- **v1.0**: Initial release with core functionality
  - XTI file parsing and display
  - Two-pane interface layout
  - Search and filtering
  - Hex viewer with copy functionality
  - Background file loading