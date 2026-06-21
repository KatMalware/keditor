# KEditor

A feature-rich text editor built with Python and Tkinter.

## Features

- File operations: New, Open, Save, Save As
- Recent Files menu (persisted across sessions)
- Auto-Save (toggleable, configurable interval)
- Undo / Redo, Cut / Copy / Paste
- Find & Replace with case-sensitive / whole-word options and Replace All
- Go to Line
- Duplicate Line / Delete Line
- Insert Date/Time
- Auto-indent on Enter
- Line numbers panel
- Word count, character count
- Word Wrap toggle
- Configurable tab size
- 4 built-in themes: Light, Dark, Solarized, Monokai
- Zoom in / out / reset (Ctrl + / Ctrl - / Ctrl 0, Ctrl+scroll)
- Unsaved changes tracking (title shows `*`, confirms before discarding)
- Print support (uses system print where available)
- Export as PDF (optional, requires `reportlab`)

## Installation

Clone the repository:

```bash
git clone https://github.com/KatMalware/keditor.git
cd keditor
```

## Requirements

- Python 3.x
- Tkinter (bundled with most Python installs)
- Optional: `reportlab` for PDF export — `pip install reportlab`

## Usage

```bash
python3 keditor.py
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+N | New file |
| Ctrl+O | Open file |
| Ctrl+S | Save file |
| Ctrl+Shift+S | Save As |
| Ctrl+P | Print |
| Ctrl+F | Find |
| Ctrl+H | Replace |
| Ctrl+G | Go to Line |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+X | Cut |
| Ctrl+C | Copy |
| Ctrl+V | Paste |
| Ctrl+A | Select All |
| Ctrl+D | Duplicate Line |
| Ctrl+Shift+K | Delete Line |
| F5 | Insert Date/Time |
| Ctrl++ / Ctrl+- / Ctrl+0 | Zoom In / Out / Reset |

## Configuration

Settings (theme, font, word wrap, tab size, recent files, auto-save) are stored in:

```
~/.keditor/config.json
```

## Contributing

Issues and pull requests are welcome.

## License

MIT
