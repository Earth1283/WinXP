"""Visual XP Code — a suspiciously modern dark code editor wearing an XP window frame.

Runs real Python via QProcess (not a gag), plus a deliberately unhelpful
"AI" ghost-text autocomplete (canned suggestions, Tab to accept).
"""
from __future__ import annotations

import os
import sys
import tempfile

from PyQt6.QtCore import QRegularExpression, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction, QColor, QFont, QIcon, QPainter, QPixmap, QPolygon,
    QSyntaxHighlighter, QTextCharFormat, QTextCursor,
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenuBar, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import QPoint, QProcess

from .. import icons as icons_mod
from .. import vfs as vfs_mod
from ..vfs_dialog import VfsFileDialog
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox


def _glyph_icon(painter_fn, size=14, color="#ffffff"):
    """Small flat glyph drawn by hand, not a native emoji — keeps look consistent
    across OSes instead of borrowing whatever color-emoji font is installed."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    painter_fn(p, size)
    p.end()
    return QIcon(pm)


def _run_icon(color="#ffffff"):
    def draw(p, s):
        p.drawPolygon(QPolygon([
            QPoint(int(s * 0.28), int(s * 0.16)),
            QPoint(int(s * 0.28), int(s * 0.84)),
            QPoint(int(s * 0.86), int(s * 0.5)),
        ]))
    return _glyph_icon(draw, color=color)


def _stop_icon(color="#ffffff"):
    def draw(p, s):
        p.drawRect(int(s * 0.22), int(s * 0.22), int(s * 0.56), int(s * 0.56))
    return _glyph_icon(draw, color=color)

DEFAULT_SOURCE = '''"""Visual XP Code — definitely not Windows XP."""

def main():
    print("Welcome to Visual XP Code..")


if __name__ == "__main__":
    main()
'''

# Deliberately dumb "AI" autocomplete: keyed by the text just typed, longest match wins.
GHOST_SUGGESTIONS = {
    "def ": "solve_p_equals_np():",
    "class ": "MyClass:",
    "import ": "antigravity",
    "from ": "__future__ import braces",
    "for ": "i in range(10):",
    "while ": "True:  # what could go wrong",
    "if ": "os.path.exists('C:\\\\System32'):",
    "print(": '"it works on my machine")',
    "return ": "42",
    "# TODO": ": fix this before the demo",
    "raise ": "NotImplementedError('ask Clippy')",
}

KEYWORDS = [
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
]


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self._rules = []

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#569cd6"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        for kw in KEYWORDS:
            self._rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))

        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(QColor("#4ec9b0"))
        for name in ("print", "len", "range", "str", "int", "float", "list",
                     "dict", "set", "tuple", "self", "open"):
            self._rules.append((QRegularExpression(rf"\b{name}\b"), builtin_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#b5cea8"))
        self._rules.append((QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), num_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#ce9178"))
        self._rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_fmt))
        self._rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_fmt))

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#6a9955"))
        self._comment_re = QRegularExpression(r"#[^\n]*")

    def highlightBlock(self, text):
        for regex, fmt in self._rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
        it = self._comment_re.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self._comment_fmt)


class GhostEditor(QPlainTextEdit):
    """QPlainTextEdit with inline grey ghost-text autocomplete, accept with Tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suggestion = ""
        self._ghost = QLabel(self.viewport())
        self._ghost.setStyleSheet("color: #5a5a5a; background: transparent;")
        self._ghost.hide()
        self.textChanged.connect(self._recompute_suggestion)
        self.cursorPositionChanged.connect(self._reposition_ghost)

    def set_editor_font(self, font: QFont):
        self.setFont(font)
        self._ghost.setFont(font)

    def _recompute_suggestion(self):
        cursor = self.textCursor()
        at_end = cursor.position() == len(self.toPlainText())
        if not at_end:
            self._clear_suggestion()
            return
        line = cursor.block().text()[:cursor.positionInBlock()]
        best = ""
        for trigger in sorted(GHOST_SUGGESTIONS, key=len, reverse=True):
            if line.endswith(trigger):
                best = GHOST_SUGGESTIONS[trigger]
                break
        self._suggestion = best
        self._ghost.setText(best)
        self._ghost.adjustSize()
        self._ghost.setVisible(bool(best))
        self._reposition_ghost()

    def _reposition_ghost(self):
        if not self._suggestion:
            self._ghost.hide()
            return
        r = self.cursorRect(self.textCursor())
        self._ghost.move(r.right() + 2, r.top())
        self._ghost.show()

    def _clear_suggestion(self):
        self._suggestion = ""
        self._ghost.hide()

    def keyPressEvent(self, ev):
        if self._suggestion and ev.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            cursor.insertText(self._suggestion)
            self._clear_suggestion()
            return
        if self._suggestion and ev.key() == Qt.Key.Key_Escape:
            self._clear_suggestion()
            return
        super().keyPressEvent(ev)


class VisualXPCodeWindow(XPWindow):
    RUN_TIMEOUT_MS = 20000

    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Untitled-1.py - Visual XP Code",
                          icon_key="vscode", size=QSize(860, 600))
        self.node_id = node_id
        self.dirty = False
        self._proc: QProcess | None = None
        self._tmp_path: str | None = None
        self._kill_timer: QTimer | None = None

        self.content.setStyleSheet("background: #1e1e1e;")

        editor_font = QFont("Consolas", 10)
        editor_font.setStyleHint(QFont.StyleHint.Monospace)

        # sidebar
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(190)
        self.sidebar.setStyleSheet(
            "QListWidget { background:#252526; color:#cccccc; border:none; "
            "border-right:1px solid #1b1b1b; padding-top:6px; font-size:12px; }"
            "QListWidget::item { padding:4px 10px; }"
            "QListWidget::item:selected { background:#37373d; }"
        )
        self._reload_sidebar()
        self.sidebar.itemDoubleClicked.connect(self._open_sidebar_item)

        # editor
        self.editor = GhostEditor()
        self.editor.set_editor_font(editor_font)
        self.editor.setStyleSheet(
            "QPlainTextEdit { background:#1e1e1e; color:#d4d4d4; border:none; "
            "selection-background-color:#264f78; padding:6px; }"
        )
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))
        self.editor.setPlainText(DEFAULT_SOURCE)
        self.highlighter = PythonHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._on_change)

        # terminal
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFixedHeight(160)
        self.terminal.setFont(QFont("Consolas", 9))
        self.terminal.setStyleSheet(
            "QPlainTextEdit { background:#1e1e1e; color:#cccccc; "
            "border-top:1px solid #3c3c3c; padding:6px; }"
        )
        self.terminal.setPlaceholderText("PROBLEMS  OUTPUT  TERMINAL")

        editor_col = QWidget()
        editor_layout = QVBoxLayout(editor_col)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        editor_layout.addWidget(self._build_tabbar())
        editor_layout.addWidget(self.editor, 1)
        editor_layout.addWidget(self._build_terminal_header())
        editor_layout.addWidget(self.terminal)
        editor_layout.addWidget(self._build_statusbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(editor_col)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(1)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.setMenuBar(self._build_menu())
        outer.addWidget(splitter, 1)
        self.set_content_layout(outer)

        if node_id:
            self._load_node(node_id)

    # ---------- chrome ----------

    def _build_menu(self):
        bar = QMenuBar()
        bar.setStyleSheet(
            "QMenuBar { background:#3c3c3c; color:#cccccc; border:none; }"
            "QMenuBar::item:selected { background:#505050; }"
            "QMenu { background:#252526; color:#cccccc; border:1px solid #454545; }"
            "QMenu::item:selected { background:#094771; }"
        )
        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._act("&New File", self.new_file))
        file_menu.addAction(self._act("&Open...", self.open_file))
        file_menu.addAction(self._act("&Save", self.save_file))
        file_menu.addAction(self._act("Save &As...", self.save_file_as))
        file_menu.addSeparator()
        file_menu.addAction(self._act("E&xit", self.close))

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addAction(self._act("&Undo", self.editor.undo))
        edit_menu.addAction(self._act("&Redo", self.editor.redo))
        edit_menu.addSeparator()
        edit_menu.addAction(self._act("Cu&t", self.editor.cut))
        edit_menu.addAction(self._act("&Copy", self.editor.copy))
        edit_menu.addAction(self._act("&Paste", self.editor.paste))

        run_menu = bar.addMenu("&Run")
        run_menu.addAction(self._act("&Run Python File", self.run_code))
        run_menu.addAction(self._act("&Stop", self.stop_code))

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self._act("&About Visual XP Code", self._about))
        return bar

    def _act(self, text, slot):
        act = QAction(text, self)
        act.triggered.connect(slot)
        return act

    def _build_tabbar(self):
        bar = QWidget()
        bar.setFixedHeight(30)
        bar.setStyleSheet("background:#2d2d2d; border-bottom:1px solid #1b1b1b;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 10, 0)
        self.tab_label = QLabel("Untitled-1.py")
        self.tab_label.setStyleSheet(
            "background:#1e1e1e; color:#ffffff; padding:5px 14px; "
            "border-top:2px solid #007acc;"
        )
        lay.addWidget(self.tab_label)
        lay.addStretch(1)
        return bar

    def _build_terminal_header(self):
        bar = QWidget()
        bar.setFixedHeight(28)
        bar.setStyleSheet("background:#252526; border-top:1px solid #1b1b1b;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.addWidget(QLabel("<b style='color:#cccccc'>TERMINAL</b>"))
        lay.addStretch(1)
        self.run_btn = QPushButton(_run_icon(), " Run")
        self.run_btn.setStyleSheet(
            "QPushButton { background:#0e639c; color:white; border:none; "
            "padding:3px 12px; border-radius:2px; }"
            "QPushButton:hover { background:#1177bb; }"
        )
        self.run_btn.clicked.connect(self.run_code)
        self.stop_btn = QPushButton(_stop_icon(), " Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            "QPushButton { background:#5a1d1d; color:white; border:none; "
            "padding:3px 12px; border-radius:2px; }"
            "QPushButton:hover { background:#7a2727; }"
            "QPushButton:disabled { background:#3c3c3c; color:#777; }"
        )
        self.stop_btn.clicked.connect(self.stop_code)
        lay.addWidget(self.run_btn)
        lay.addWidget(self.stop_btn)
        return bar

    def _build_statusbar(self):
        bar = QWidget()
        bar.setFixedHeight(22)
        bar.setStyleSheet(f"background:#007acc;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 10, 0)
        label = QLabel(f"Python {sys.version.split()[0]}  \u00b7  UTF-8  \u00b7  LF  \u00b7  Spaces: 4  \u00b7  Ghost Suggestions: On")
        label.setStyleSheet("color:white; font-size:11px;")
        lay.addWidget(label)
        lay.addStretch(1)
        return bar

    # ---------- sidebar / vfs ----------

    def _reload_sidebar(self):
        self.sidebar.clear()
        header = QListWidgetItem("MY DOCUMENTS")
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        self.sidebar.addItem(header)
        for node in vfs_mod.vfs.children_of(vfs_mod.vfs.my_docs_id):
            if node.kind == vfs_mod.TEXT:
                item = QListWidgetItem(icons_mod.icon("text_file", 16), " " + node.name)
                item.setData(Qt.ItemDataRole.UserRole, node.id)
                self.sidebar.addItem(item)

    def _open_sidebar_item(self, item):
        node_id = item.data(Qt.ItemDataRole.UserRole)
        if node_id:
            self._load_node(node_id)

    def _load_node(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        self.node_id = node_id
        self.editor.setPlainText(vfs_mod.vfs.read_content(node_id))
        self.dirty = False
        self._retitle(node.name)

    # ---------- editing state ----------

    def _on_change(self):
        self.dirty = True
        title = self.windowTitle()
        if not title.startswith("\u25cf "):
            self.setWindowTitle("\u25cf " + title)

    def _retitle(self, name):
        self.setWindowTitle(f"{name} - Visual XP Code")
        self.tab_label.setText(name)

    def new_file(self):
        self.node_id = None
        self.editor.setPlainText("")
        self.dirty = False
        self.setWindowTitle("Untitled-1.py - Visual XP Code")
        self.tab_label.setText("Untitled-1.py")

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.TEXT,), title="Open")
        if node_id:
            self._load_node(node_id)
            self._reload_sidebar()

    def save_file(self):
        if self.node_id:
            vfs_mod.vfs.write_content(self.node_id, self.editor.toPlainText())
            self.dirty = False
            node = vfs_mod.vfs.get(self.node_id)
            self._retitle(node.name)
            self._reload_sidebar()
        else:
            self.save_file_as()

    def save_file_as(self):
        folder_id, name = VfsFileDialog.get_save_target(
            self, kinds=(vfs_mod.TEXT,), title="Save As", default_name="script.py"
        )
        if not folder_id:
            return
        existing = next((c for c in vfs_mod.vfs.children_of(folder_id)
                          if c.name == name and c.kind == vfs_mod.TEXT), None)
        content = self.editor.toPlainText()
        if existing:
            vfs_mod.vfs.write_content(existing.id, content)
            self.node_id = existing.id
        else:
            node = vfs_mod.vfs.create_text_file(folder_id, name, content)
            self.node_id = node.id
        self.dirty = False
        self._retitle(vfs_mod.vfs.get(self.node_id).name)
        self._reload_sidebar()

    # ---------- run ----------

    def run_code(self):
        if self._proc is not None:
            return
        self.terminal.clear()
        self.terminal.appendPlainText(f"> python {self.tab_label.text()}")

        fd, path = tempfile.mkstemp(suffix=".py", prefix="vxc_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        self._tmp_path = path

        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setArguments(["-u", path])
        self._proc.readyReadStandardOutput.connect(self._read_stdout)
        self._proc.readyReadStandardError.connect(self._read_stderr)
        self._proc.finished.connect(self._on_finished)
        self._proc.start()

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._on_timeout)
        self._kill_timer.start(self.RUN_TIMEOUT_MS)

    def stop_code(self):
        if self._proc is not None:
            self._proc.kill()

    def _on_timeout(self):
        if self._proc is not None:
            self.terminal.appendPlainText(
                f"\n[Killed: exceeded {self.RUN_TIMEOUT_MS // 1000}s time limit]")
            self._proc.kill()

    def _read_stdout(self):
        if self._proc is not None:
            self.terminal.appendPlainText(
                bytes(self._proc.readAllStandardOutput()).decode(errors="replace").rstrip("\n"))

    def _read_stderr(self):
        if self._proc is not None:
            self.terminal.appendPlainText(
                bytes(self._proc.readAllStandardError()).decode(errors="replace").rstrip("\n"))

    def _on_finished(self, code, status):
        self.terminal.appendPlainText(f"\n[Process exited with code {code}]")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self._kill_timer:
            self._kill_timer.stop()
            self._kill_timer = None
        self._proc = None
        if self._tmp_path:
            try:
                os.remove(self._tmp_path)
            except OSError:
                pass
            self._tmp_path = None

    def closeEvent(self, ev):
        self.stop_code()
        super().closeEvent(ev)

    # ---------- misc ----------

    def _about(self):
        XPMessageBox.information(
            self, "About Visual XP Code",
            "Visual XP Code\nBuild 2024.99.1 (definitely not Luna)\n\n"
            "Runs real Python. Ghost suggestions are 100% canned and\n"
            "0% intelligent. \u00a9 MacroHard Corporation."
        )
