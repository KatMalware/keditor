"""
Advanced Notepad v2.0
A feature-rich text editor built with Python and Tkinter.

New in v2.0:
- Line numbers panel
- Recent files menu (persisted to disk)
- Auto-save (configurable interval)
- Zoom in / out (Ctrl+= / Ctrl+-)
- Find & Replace dialog with "Replace All" and match count
- Case-insensitive / whole-word search options
- Go to line (Ctrl+G)
- Duplicate line, delete line shortcuts
- Insert date/time
- Word wrap toggle
- Multiple themes (Light, Dark, Solarized, Monokai)
- Print support (via system print dialog where available)
- Unsaved-changes tracking with title asterisk and confirm-on-exit/new/open
- Drag-and-drop friendly "Open Recent"
- Status bar: line, column, total lines, word count, char count, modified state
- Tab/Indent settings, auto-indent on Enter
- Export to PDF (best-effort, requires reportlab; falls back gracefully)
"""

from tkinter import *
from tkinter import filedialog as fd
from tkinter import messagebox, simpledialog, font, colorchooser
import os
import re
import json
import time
import datetime

# ----------------------------------------------------------------------------
# Paths / persisted settings
# ----------------------------------------------------------------------------
APP_DIR = os.path.join(os.path.expanduser("~"), ".advanced_notepad")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
os.makedirs(APP_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "recent_files": [],
    "theme": "Light",
    "font_family": "Consolas",
    "font_size": 12,
    "word_wrap": True,
    "auto_save": False,
    "auto_save_interval_sec": 60,
    "tab_size": 4,
    "show_line_numbers": True,
}

THEMES = {
    "Light":     {"bg": "#ffffff", "fg": "#000000", "insert": "#000000", "select": "#cce6ff",
                  "ln_bg": "#f0f0f0", "ln_fg": "#555555"},
    "Dark":      {"bg": "#1e1e1e", "fg": "#e0e0e0", "insert": "#ffffff", "select": "#3a3d41",
                  "ln_bg": "#252526", "ln_fg": "#858585"},
    "Solarized": {"bg": "#fdf6e3", "fg": "#657b83", "insert": "#657b83", "select": "#eee8d5",
                  "ln_bg": "#eee8d5", "ln_fg": "#93a1a1"},
    "Monokai":   {"bg": "#272822", "fg": "#f8f8f2", "insert": "#f8f8f0", "select": "#49483e",
                  "ln_bg": "#2d2e27", "ln_fg": "#75715e"},
}

MAX_RECENT = 8


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Application
# ----------------------------------------------------------------------------
class AdvancedNotepad:
    def __init__(self, root):
        self.root = root
        self.root.title("Untitled - Advanced Notepad")
        self.root.geometry("1000x700")

        self.config_data = load_config()
        self.current_file = None
        self.text_modified = False
        self.auto_save_job = None
        self.zoom_level = 0  # relative to base font size

        self._build_menu()
        self._build_layout()
        self._apply_theme(self.config_data.get("theme", "Light"))
        self._apply_font()
        self._bind_shortcuts()
        self._update_recent_menu()
        self._schedule_autosave()

        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self):
        # Main frame holds line numbers + text area side by side
        self.main_frame = Frame(self.root)
        self.main_frame.pack(expand=True, fill=BOTH)

        self.line_numbers = Text(self.main_frame, width=5, padx=4, takefocus=0,
                                  border=0, state="disabled", wrap="none")
        self.line_numbers.pack(side=LEFT, fill=Y)

        self.text_area = Text(self.main_frame, wrap="word" if self.config_data["word_wrap"] else "none",
                               undo=True)
        self.text_area.pack(side=LEFT, expand=True, fill=BOTH)

        scrollbar = Scrollbar(self.main_frame, command=self._on_scroll)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.text_area.config(yscrollcommand=scrollbar.set)

        # Status bar
        self.status_bar = Label(self.root, text="", anchor=E)
        self.status_bar.pack(side=BOTTOM, fill=X)

        # Events
        self.text_area.bind("<KeyRelease>", self._on_text_event)
        self.text_area.bind("<ButtonRelease>", self._on_text_event)
        self.text_area.bind("<<Modified>>", self._on_modified)
        self.text_area.bind("<Return>", self._auto_indent)
        self.text_area.bind("<MouseWheel>", self._on_mousewheel_zoom)   # Windows/Mac
        self.text_area.bind("<Control-Button-4>", lambda e: self._zoom(1))   # Linux scroll up
        self.text_area.bind("<Control-Button-5>", lambda e: self._zoom(-1))  # Linux scroll down

        self._update_line_numbers()
        self._update_status()

    def _on_scroll(self, *args):
        self.text_area.yview(*args)
        self.line_numbers.yview(*args)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _build_menu(self):
        self.menubar = Menu(self.root)

        # File menu
        self.filemenu = Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        self.filemenu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        self.recent_menu = Menu(self.filemenu, tearoff=0)
        self.filemenu.add_cascade(label="Open Recent", menu=self.recent_menu)
        self.filemenu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        self.filemenu.add_command(label="Save As...", command=self.save_as_file, accelerator="Ctrl+Shift+S")
        self.filemenu.add_separator()
        self.filemenu.add_command(label="Print...", command=self.print_file, accelerator="Ctrl+P")
        self.filemenu.add_command(label="Export as PDF...", command=self.export_pdf)
        self.filemenu.add_separator()
        self.filemenu.add_checkbutton(label="Auto-Save", command=self.toggle_autosave,
                                       variable=BooleanVar(value=self.config_data["auto_save"]))
        self.filemenu.add_separator()
        self.filemenu.add_command(label="Exit", command=self.on_exit)
        self.menubar.add_cascade(label="File", menu=self.filemenu)

        # Edit menu
        editmenu = Menu(self.menubar, tearoff=0)
        editmenu.add_command(label="Undo", command=self.undo_action, accelerator="Ctrl+Z")
        editmenu.add_command(label="Redo", command=self.redo_action, accelerator="Ctrl+Y")
        editmenu.add_separator()
        editmenu.add_command(label="Cut", command=self.cut_text, accelerator="Ctrl+X")
        editmenu.add_command(label="Copy", command=self.copy_text, accelerator="Ctrl+C")
        editmenu.add_command(label="Paste", command=self.paste_text, accelerator="Ctrl+V")
        editmenu.add_separator()
        editmenu.add_command(label="Find...", command=self.open_find_dialog, accelerator="Ctrl+F")
        editmenu.add_command(label="Replace...", command=self.open_find_dialog, accelerator="Ctrl+H")
        editmenu.add_command(label="Go to Line...", command=self.go_to_line, accelerator="Ctrl+G")
        editmenu.add_separator()
        editmenu.add_command(label="Duplicate Line", command=self.duplicate_line, accelerator="Ctrl+D")
        editmenu.add_command(label="Delete Line", command=self.delete_line, accelerator="Ctrl+Shift+K")
        editmenu.add_separator()
        editmenu.add_command(label="Insert Date/Time", command=self.insert_datetime, accelerator="F5")
        editmenu.add_command(label="Word Count", command=self.word_count)
        editmenu.add_command(label="Select All", command=self.select_all, accelerator="Ctrl+A")
        self.menubar.add_cascade(label="Edit", menu=editmenu)

        # Format menu
        formatmenu = Menu(self.menubar, tearoff=0)
        formatmenu.add_command(label="Font...", command=self.change_font)
        formatmenu.add_checkbutton(label="Word Wrap", command=self.toggle_wordwrap,
                                    variable=BooleanVar(value=self.config_data["word_wrap"]))
        tabsize_menu = Menu(formatmenu, tearoff=0)
        for size in (2, 4, 8):
            tabsize_menu.add_command(label=f"{size} spaces",
                                      command=lambda s=size: self.set_tab_size(s))
        formatmenu.add_cascade(label="Tab Size", menu=tabsize_menu)
        self.menubar.add_cascade(label="Format", menu=formatmenu)

        # View menu
        viewmenu = Menu(self.menubar, tearoff=0)
        theme_menu = Menu(viewmenu, tearoff=0)
        for theme_name in THEMES:
            theme_menu.add_command(label=theme_name, command=lambda t=theme_name: self._apply_theme(t))
        viewmenu.add_cascade(label="Theme", menu=theme_menu)
        viewmenu.add_checkbutton(label="Show Line Numbers", command=self.toggle_line_numbers,
                                  variable=BooleanVar(value=self.config_data["show_line_numbers"]))
        viewmenu.add_separator()
        viewmenu.add_command(label="Zoom In", command=lambda: self._zoom(1), accelerator="Ctrl++")
        viewmenu.add_command(label="Zoom Out", command=lambda: self._zoom(-1), accelerator="Ctrl+-")
        viewmenu.add_command(label="Reset Zoom", command=lambda: self._zoom(0, reset=True), accelerator="Ctrl+0")
        self.menubar.add_cascade(label="View", menu=viewmenu)

        # Help menu
        helpmenu = Menu(self.menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        self.menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=self.menubar)

    # ------------------------------------------------------------------
    # Shortcuts
    # ------------------------------------------------------------------
    def _bind_shortcuts(self):
        b = self.root.bind
        b("<Control-n>", lambda e: self.new_file())
        b("<Control-o>", lambda e: self.open_file())
        b("<Control-s>", lambda e: self.save_file())
        b("<Control-S>", lambda e: self.save_as_file())
        b("<Control-Shift-S>", lambda e: self.save_as_file())
        b("<Control-p>", lambda e: self.print_file())
        b("<Control-f>", lambda e: self.open_find_dialog())
        b("<Control-h>", lambda e: self.open_find_dialog())
        b("<Control-g>", lambda e: self.go_to_line())
        b("<Control-z>", lambda e: self.undo_action())
        b("<Control-y>", lambda e: self.redo_action())
        b("<Control-d>", lambda e: self.duplicate_line())
        b("<Control-D>", lambda e: self.duplicate_line())
        b("<Control-Shift-K>", lambda e: self.delete_line())
        b("<Control-a>", lambda e: self.select_all())
        b("<F5>", lambda e: self.insert_datetime())
        b("<Control-equal>", lambda e: self._zoom(1))
        b("<Control-plus>", lambda e: self._zoom(1))
        b("<Control-minus>", lambda e: self._zoom(-1))
        b("<Control-0>", lambda e: self._zoom(0, reset=True))

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def _confirm_discard_changes(self):
        """Return True if it's OK to proceed (saved, discarded, or no changes)."""
        if not self.text_modified:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved Changes",
            "You have unsaved changes. Do you want to save them first?"
        )
        if answer is None:
            return False
        if answer:
            self.save_file()
            return not self.text_modified  # only proceed if save succeeded
        return True

    def new_file(self):
        if not self._confirm_discard_changes():
            return
        self.current_file = None
        self.text_area.delete(1.0, END)
        self.text_modified = False
        self.text_area.edit_modified(False)
        self.root.title("Untitled - Advanced Notepad")
        self._update_line_numbers()
        self._update_status()

    def open_file(self, path=None):
        if not self._confirm_discard_changes():
            return
        file_path = path or fd.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("Python Files", "*.py"),
                       ("Markdown", "*.md"), ("All Files", "*.*")])
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                content = file.read()
        except Exception as e:
            messagebox.showerror("Open File", f"Could not open file:\n{e}")
            return
        self.current_file = file_path
        self.text_area.delete(1.0, END)
        self.text_area.insert(1.0, content)
        self.root.title(f"{os.path.basename(file_path)} - Advanced Notepad")
        self.text_modified = False
        self.text_area.edit_modified(False)
        self._add_recent_file(file_path)
        self._update_line_numbers()
        self._update_status()

    def save_file(self):
        if not self.current_file:
            self.save_as_file()
            return
        try:
            with open(self.current_file, "w", encoding="utf-8") as file:
                file.write(self.text_area.get(1.0, "end-1c"))
            self.text_modified = False
            self.text_area.edit_modified(False)
            self.root.title(f"{os.path.basename(self.current_file)} - Advanced Notepad")
            self._update_status(flash="Saved")
        except Exception as e:
            messagebox.showerror("Save File", f"Could not save file:\n{e}")

    def save_as_file(self):
        file_path = fd.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("Python Files", "*.py"),
                       ("Markdown", "*.md"), ("All Files", "*.*")])
        if not file_path:
            return
        self.current_file = file_path
        self.save_file()
        self._add_recent_file(file_path)

    def on_exit(self):
        if self._confirm_discard_changes():
            save_config(self.config_data)
            self.root.destroy()

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------
    def _add_recent_file(self, path):
        recents = self.config_data.get("recent_files", [])
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        self.config_data["recent_files"] = recents[:MAX_RECENT]
        save_config(self.config_data)
        self._update_recent_menu()

    def _update_recent_menu(self):
        self.recent_menu.delete(0, END)
        recents = self.config_data.get("recent_files", [])
        if not recents:
            self.recent_menu.add_command(label="(No recent files)", state="disabled")
            return
        for path in recents:
            label = path if len(path) < 60 else "..." + path[-57:]
            self.recent_menu.add_command(
                label=label, command=lambda p=path: self.open_file(p))
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="Clear Recent Files", command=self._clear_recent)

    def _clear_recent(self):
        self.config_data["recent_files"] = []
        save_config(self.config_data)
        self._update_recent_menu()

    # ------------------------------------------------------------------
    # Edit basics
    # ------------------------------------------------------------------
    def cut_text(self):
        self.text_area.event_generate("<<Cut>>")

    def copy_text(self):
        self.text_area.event_generate("<<Copy>>")

    def paste_text(self):
        self.text_area.event_generate("<<Paste>>")

    def undo_action(self):
        try:
            self.text_area.edit_undo()
        except TclError:
            pass

    def redo_action(self):
        try:
            self.text_area.edit_redo()
        except TclError:
            pass

    def select_all(self):
        self.text_area.tag_add(SEL, "1.0", END)
        return "break"

    def duplicate_line(self):
        line_idx = self.text_area.index(INSERT).split(".")[0]
        line_text = self.text_area.get(f"{line_idx}.0", f"{line_idx}.end")
        self.text_area.insert(f"{line_idx}.end", "\n" + line_text)
        return "break"

    def delete_line(self):
        line_idx = self.text_area.index(INSERT).split(".")[0]
        self.text_area.delete(f"{line_idx}.0", f"{int(line_idx)+1}.0")
        return "break"

    def insert_datetime(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.text_area.insert(INSERT, now)

    def go_to_line(self):
        total_lines = int(self.text_area.index("end-1c").split(".")[0])
        line_no = simpledialog.askinteger(
            "Go to Line", f"Enter line number (1-{total_lines}):",
            minvalue=1, maxvalue=total_lines)
        if line_no:
            self.text_area.mark_set(INSERT, f"{line_no}.0")
            self.text_area.see(f"{line_no}.0")
            self.text_area.focus_set()
            self._update_status()

    def _auto_indent(self, event):
        line_idx = self.text_area.index(INSERT).split(".")[0]
        current_line = self.text_area.get(f"{line_idx}.0", f"{line_idx}.end")
        indent = re.match(r"[ \t]*", current_line).group()
        self.text_area.insert(INSERT, "\n" + indent)
        return "break"

    # ------------------------------------------------------------------
    # Find / Replace
    # ------------------------------------------------------------------
    def open_find_dialog(self):
        if hasattr(self, "_find_win") and self._find_win.winfo_exists():
            self._find_win.lift()
            return

        win = Toplevel(self.root)
        win.title("Find & Replace")
        win.resizable(False, False)
        self._find_win = win

        Label(win, text="Find:").grid(row=0, column=0, sticky=W, padx=6, pady=4)
        find_entry = Entry(win, width=35)
        find_entry.grid(row=0, column=1, columnspan=2, padx=6, pady=4)

        Label(win, text="Replace with:").grid(row=1, column=0, sticky=W, padx=6, pady=4)
        replace_entry = Entry(win, width=35)
        replace_entry.grid(row=1, column=1, columnspan=2, padx=6, pady=4)

        case_var = BooleanVar(value=False)
        word_var = BooleanVar(value=False)
        Checkbutton(win, text="Case sensitive", variable=case_var).grid(row=2, column=0, sticky=W, padx=6)
        Checkbutton(win, text="Whole word", variable=word_var).grid(row=2, column=1, sticky=W)

        result_label = Label(win, text="", fg="gray")
        result_label.grid(row=3, column=0, columnspan=3, sticky=W, padx=6)

        def clear_highlights():
            self.text_area.tag_remove("highlight", "1.0", END)

        def find_next():
            clear_highlights()
            term = find_entry.get()
            if not term:
                return
            flags_count = "1" if not case_var.get() else "0"
            start = self.text_area.index(INSERT)
            idx = self.text_area.search(term, start, END, nocase=(not case_var.get()))
            if not idx:
                idx = self.text_area.search(term, "1.0", END, nocase=(not case_var.get()))
            if idx:
                end_idx = f"{idx}+{len(term)}c"
                self.text_area.tag_add("highlight", idx, end_idx)
                self.text_area.tag_config("highlight", background="yellow", foreground="black")
                self.text_area.mark_set(INSERT, end_idx)
                self.text_area.see(idx)
                result_label.config(text="Match found")
            else:
                result_label.config(text="No matches found")

        def replace_one():
            term = find_entry.get()
            repl = replace_entry.get()
            if not term:
                return
            sel_ranges = self.text_area.tag_ranges("highlight")
            if sel_ranges:
                self.text_area.delete(sel_ranges[0], sel_ranges[1])
                self.text_area.insert(sel_ranges[0], repl)
            find_next()

        def replace_all():
            term = find_entry.get()
            repl = replace_entry.get()
            if not term:
                return
            content = self.text_area.get("1.0", "end-1c")
            if word_var.get():
                pattern = r"\b" + re.escape(term) + r"\b"
            else:
                pattern = re.escape(term)
            count_flags = 0 if case_var.get() else re.IGNORECASE
            new_content, n = re.subn(pattern, repl, content, flags=count_flags)
            self.text_area.delete("1.0", END)
            self.text_area.insert("1.0", new_content)
            result_label.config(text=f"Replaced {n} occurrence(s)")
            self._update_status()

        btn_frame = Frame(win)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=6)
        Button(btn_frame, text="Find Next", command=find_next, width=12).grid(row=0, column=0, padx=4)
        Button(btn_frame, text="Replace", command=replace_one, width=12).grid(row=0, column=1, padx=4)
        Button(btn_frame, text="Replace All", command=replace_all, width=12).grid(row=0, column=2, padx=4)

        find_entry.focus_set()
        win.bind("<Return>", lambda e: find_next())

    def word_count(self):
        content = self.text_area.get(1.0, "end-1c")
        words = len(content.split())
        chars = len(content)
        chars_no_space = len(content.replace(" ", "").replace("\n", ""))
        lines = int(self.text_area.index("end-1c").split(".")[0])
        messagebox.showinfo(
            "Word Count",
            f"Words: {words}\nCharacters: {chars}\n"
            f"Characters (no spaces): {chars_no_space}\nLines: {lines}"
        )

    # ------------------------------------------------------------------
    # Format / View
    # ------------------------------------------------------------------
    def change_font(self):
        family = simpledialog.askstring(
            "Font", "Enter font family (e.g., Consolas, Arial):",
            initialvalue=self.config_data["font_family"])
        size = simpledialog.askinteger(
            "Font Size", "Enter font size:",
            initialvalue=self.config_data["font_size"], minvalue=6, maxvalue=72)
        if family and size:
            self.config_data["font_family"] = family
            self.config_data["font_size"] = size
            self.zoom_level = 0
            self._apply_font()
            save_config(self.config_data)

    def _apply_font(self):
        size = self.config_data["font_size"] + self.zoom_level
        size = max(6, size)
        f = font.Font(family=self.config_data["font_family"], size=size)
        self.text_area.config(font=f)
        self.line_numbers.config(font=f)

    def _zoom(self, delta, reset=False):
        if reset:
            self.zoom_level = 0
        else:
            self.zoom_level += delta
            self.zoom_level = max(-6, min(20, self.zoom_level))
        self._apply_font()
        self._update_line_numbers()

    def _on_mousewheel_zoom(self, event):
        # Only zoom if Ctrl is held (state bit 4 = Control on Windows)
        if event.state & 0x4:
            self._zoom(1 if event.delta > 0 else -1)
            return "break"

    def toggle_wordwrap(self):
        self.config_data["word_wrap"] = not self.config_data["word_wrap"]
        self.text_area.config(wrap="word" if self.config_data["word_wrap"] else "none")
        save_config(self.config_data)

    def set_tab_size(self, size):
        self.config_data["tab_size"] = size
        f = font.Font(font=self.text_area["font"])
        tab_width = f.measure(" " * size)
        self.text_area.config(tabs=tab_width)
        save_config(self.config_data)

    def toggle_line_numbers(self):
        self.config_data["show_line_numbers"] = not self.config_data["show_line_numbers"]
        if self.config_data["show_line_numbers"]:
            self.line_numbers.pack(side=LEFT, fill=Y, before=self.text_area)
        else:
            self.line_numbers.pack_forget()
        save_config(self.config_data)

    def _apply_theme(self, theme_name):
        theme = THEMES.get(theme_name, THEMES["Light"])
        self.text_area.config(bg=theme["bg"], fg=theme["fg"],
                               insertbackground=theme["insert"],
                               selectbackground=theme["select"])
        self.line_numbers.config(bg=theme["ln_bg"], fg=theme["ln_fg"])
        self.config_data["theme"] = theme_name
        save_config(self.config_data)

    # ------------------------------------------------------------------
    # Line numbers / status bar
    # ------------------------------------------------------------------
    def _on_text_event(self, event=None):
        self._update_line_numbers()
        self._update_status()

    def _on_modified(self, event=None):
        if self.text_area.edit_modified():
            if not self.text_modified:
                self.text_modified = True
                title = self.root.title()
                if not title.startswith("*"):
                    self.root.title("*" + title)
            self._update_line_numbers()
            self._update_status()

    def _update_line_numbers(self):
        if not self.config_data.get("show_line_numbers", True):
            return
        total_lines = int(self.text_area.index("end-1c").split(".")[0])
        line_str = "\n".join(str(i) for i in range(1, total_lines + 1))
        self.line_numbers.config(state="normal")
        self.line_numbers.delete("1.0", END)
        self.line_numbers.insert("1.0", line_str)
        self.line_numbers.config(state="disabled")

    def _update_status(self, flash=None):
        row, col = self.text_area.index(INSERT).split(".")
        total_lines = int(self.text_area.index("end-1c").split(".")[0])
        content = self.text_area.get(1.0, "end-1c")
        words = len(content.split())
        chars = len(content)
        modified = "Modified" if self.text_modified else "Saved"
        msg = f"Line {row}, Col {int(col)+1}  |  {total_lines} lines  |  {words} words  |  {chars} chars  |  {modified}"
        if flash:
            msg = f"{flash}  |  " + msg
        self.status_bar.config(text=msg)

    # ------------------------------------------------------------------
    # Auto-save
    # ------------------------------------------------------------------
    def toggle_autosave(self):
        self.config_data["auto_save"] = not self.config_data["auto_save"]
        save_config(self.config_data)
        self._schedule_autosave()

    def _schedule_autosave(self):
        if self.auto_save_job:
            self.root.after_cancel(self.auto_save_job)
            self.auto_save_job = None
        if self.config_data.get("auto_save"):
            interval_ms = int(self.config_data.get("auto_save_interval_sec", 60)) * 1000
            self.auto_save_job = self.root.after(interval_ms, self._do_autosave)

    def _do_autosave(self):
        if self.current_file and self.text_modified:
            try:
                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(self.text_area.get(1.0, "end-1c"))
                self.text_modified = False
                self.text_area.edit_modified(False)
                title = self.root.title().lstrip("*")
                self.root.title(title)
                self._update_status(flash=f"Auto-saved at {time.strftime('%H:%M:%S')}")
            except Exception:
                pass
        self._schedule_autosave()

    # ------------------------------------------------------------------
    # Print / Export
    # ------------------------------------------------------------------
    def print_file(self):
        content = self.text_area.get(1.0, "end-1c")
        tmp_path = os.path.join(APP_DIR, "_print_temp.txt")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            messagebox.showerror("Print", f"Could not prepare file for printing:\n{e}")
            return

        try:
            if os.name == "nt":
                os.startfile(tmp_path, "print")
            elif os.uname().sysname == "Darwin":
                os.system(f"lpr '{tmp_path}'")
            else:
                os.system(f"lpr '{tmp_path}' 2>/dev/null")
            messagebox.showinfo("Print", "Sent to system print dialog/queue (if a printer is configured).")
        except Exception as e:
            messagebox.showwarning(
                "Print",
                f"Could not invoke system print automatically ({e}).\n"
                f"The file was saved to:\n{tmp_path}\nYou can print it manually."
            )

    def export_pdf(self):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except ImportError:
            messagebox.showwarning(
                "Export as PDF",
                "PDF export requires the 'reportlab' package, which isn't installed.\n"
                "Install it with: pip install reportlab"
            )
            return

        file_path = fd.asksaveasfilename(defaultextension=".pdf",
                                          filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return

        content = self.text_area.get(1.0, "end-1c")
        c = canvas.Canvas(file_path, pagesize=letter)
        width, height = letter
        margin = 50
        y = height - margin
        line_height = 14
        c.setFont("Courier", 10)
        for line in content.split("\n"):
            if y < margin:
                c.showPage()
                c.setFont("Courier", 10)
                y = height - margin
            # Wrap very long lines crudely
            max_chars = 95
            while len(line) > max_chars:
                c.drawString(margin, y, line[:max_chars])
                line = line[max_chars:]
                y -= line_height
                if y < margin:
                    c.showPage()
                    c.setFont("Courier", 10)
                    y = height - margin
            c.drawString(margin, y, line)
            y -= line_height
        c.save()
        messagebox.showinfo("Export as PDF", f"Exported to:\n{file_path}")

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------
    def show_about(self):
        messagebox.showinfo(
            "About Advanced Notepad",
            "Advanced Notepad v2.0\n\n"
            "A feature-rich text editor built with Python and Tkinter.\n"
            "Features: line numbers, themes, find & replace, auto-save,\n"
            "recent files, zoom, PDF export, printing, and more."
        )


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------
def main():
    root = Tk()
    app = AdvancedNotepad(root)
    root.mainloop()


if __name__ == "__main__":
    main()
