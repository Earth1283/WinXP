"""The wizard itself. Deliberately has zero dependency on the winxp package
-- this runs *before* that package necessarily exists on disk. Only
PyQt6 and installer.actions (stdlib-only) are required.
"""
from __future__ import annotations

import os
import platform
import random
import sys
import time

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPalette
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QStackedWidget, QVBoxLayout, QWidget,
)

import actions

# Tahoma only exists on Windows -- pick a font that's actually installed on
# whatever OS this is running under so text doesn't fall back to an ugly
# generic serif on Linux/mac.
_SYSTEM = platform.system()
UI_FONT_FAMILY = {"Windows": "Tahoma", "Darwin": "Helvetica Neue"}.get(_SYSTEM, "DejaVu Sans")

SIDEBAR_BLUE_TOP = "#1657d6"
SIDEBAR_BLUE_BOTTOM = "#3f8cf6"
BODY_BG = "#ece9d8"
TEXT_COLOR = "#000000"
SUBTEXT_COLOR = "#4a4a4a"
ACCENT_BLUE = "#1657d6"

BUTTON_STYLE = f"""
QPushButton {{
    color: {TEXT_COLOR};
    background: #f5f4ee;
    border: 1px solid #8b8b73;
    border-radius: 3px;
    padding: 5px 16px;
}}
QPushButton:hover {{
    background: #ffffff;
    border-color: {ACCENT_BLUE};
}}
QPushButton:pressed {{
    background: #dcdac8;
}}
QPushButton:disabled {{
    color: #8a8a8a;
    background: #e4e2d6;
    border-color: #c2c0ae;
}}
QPushButton:default {{
    border: 1px solid {ACCENT_BLUE};
}}
"""

PROGRESSBAR_STYLE = f"""
QProgressBar {{
    color: {TEXT_COLOR};
    background: #ffffff;
    border: 1px solid #8b8b73;
    border-radius: 3px;
    text-align: center;
    height: 18px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT_BLUE};
    border-radius: 2px;
}}
"""

ACTIONS = [
    ("install", "Install Windows XP",
     "Set up a fresh copy of Windows XP on this computer."),
    ("reinstall", "Reinstall Windows XP",
     "Replace the current installation with a fresh one. Erases all data."),
    ("repair", "Repair Windows XP Installation",
     "Re-fetch application files and fix missing system files. Keeps your data."),
    ("wipe", "Wipe Windows XP Installation",
     "Remove Windows XP from this computer entirely. Erases all data."),
]
DESTRUCTIVE = {"reinstall", "wipe"}

CONFIRM_TEXT = {
    "install": "Setup will install Windows XP to:\n\n{dir}\n\nClick Next to continue.",
    "reinstall": (
        "This will permanently erase the current Windows XP installation and "
        "ALL data -- documents, settings, everything -- and set up a fresh copy "
        "at:\n\n{dir}\n\nThis cannot be undone."
    ),
    "repair": (
        "Setup will re-fetch application files and repair any missing or "
        "corrupted system files at:\n\n{dir}\n\nYour documents and settings "
        "will not be affected."
    ),
    "wipe": (
        "This will permanently remove Windows XP and ALL data from this "
        "computer:\n\n{dir}\n\nNothing will be reinstalled. This cannot be "
        "undone."
    ),
}

PROGRESS_LABEL = {
    "install": "Installing Windows XP...",
    "reinstall": "Reinstalling Windows XP...",
    "repair": "Repairing Windows XP...",
    "wipe": "Removing Windows XP...",
}


class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(160)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(SIDEBAR_BLUE_TOP))
        g.setColorAt(1, QColor(SIDEBAR_BLUE_BOTTOM))
        p.fillRect(self.rect(), g)

        p.setPen(QColor("white"))
        p.setFont(QFont(UI_FONT_FAMILY, 15, QFont.Weight.Bold))
        p.drawText(16, 60, 130, 90, Qt.TextFlag.TextWordWrap, "Windows XP\nSetup Wizard")

        p.setFont(QFont(UI_FONT_FAMILY, 8))
        p.setPen(QColor(255, 255, 255, 200))
        p.drawText(16, self.height() - 70, 130, 60, Qt.TextFlag.TextWordWrap,
                   "Earth1283/WinXP\ngithub.com")


class ActionWorker(QThread):
    progress = pyqtSignal(int)
    phase = pyqtSignal(str)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, action):
        super().__init__()
        self.action = action

    def _fake_ramp(self, lo, hi, phase_text=None):
        if phase_text:
            self.phase.emit(phase_text)
        pct = lo
        while pct < hi:
            pct = min(hi, pct + random.randint(2, 6))
            self.progress.emit(pct)
            time.sleep(random.uniform(0.02, 0.06))

    def run(self):
        try:
            self._fake_ramp(0, 12, "Preparing installation...")

            result = None
            if self.action == "install":
                self.phase.emit("Downloading Windows XP...")
                actions.install(on_progress=lambda p: self.progress.emit(12 + int(p * 0.73)))
            elif self.action == "reinstall":
                self.phase.emit("Downloading Windows XP...")
                actions.reinstall(on_progress=lambda p: self.progress.emit(12 + int(p * 0.73)))
            elif self.action == "repair":
                self.phase.emit("Downloading Windows XP...")
                result = actions.repair(on_progress=lambda p: self.progress.emit(12 + int(p * 0.73)))
            elif self.action == "wipe":
                self._fake_ramp(12, 85, "Removing files...")
                actions.wipe()

            self._fake_ramp(max(12, 85), 100, "Finishing installation...")
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class Wizard(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Windows XP Setup Wizard")
        self.setFixedSize(580, 400)
        self.selected_action = "install"
        self.worker = None
        self._launch_offered = True

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(Sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {BODY_BG};")
        self.welcome_page = self._build_welcome()
        self.confirm_page = self._build_confirm()
        self.progress_page = self._build_progress()
        self.finish_page = self._build_finish()
        for pg in (self.welcome_page, self.confirm_page, self.progress_page, self.finish_page):
            self.stack.addWidget(pg)
        right.addWidget(self.stack, 1)

        right.addWidget(self._build_nav())
        root.addLayout(right, 1)

        self._update_nav()

    # -- page builders ---------------------------------------------------
    def _page(self, title):
        w = QWidget()
        w.setStyleSheet(f"background: {BODY_BG}; color: {TEXT_COLOR};")
        l = QVBoxLayout(w)
        l.setContentsMargins(28, 22, 28, 20)
        l.setSpacing(12)
        heading = QLabel(title)
        heading.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {TEXT_COLOR}; border: none;")
        l.addWidget(heading)
        rule = QWidget()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background: #aca899;")
        l.addWidget(rule)
        return w, l

    def _build_welcome(self):
        w, l = self._page("What would you like to do?")
        status_label = QLabel(self._detect_status_text())
        status_label.setStyleSheet(f"color: {SUBTEXT_COLOR}; border: none;")
        l.addWidget(status_label)

        self.action_group = QButtonGroup(w)
        for key, title, desc in ACTIONS:
            radio = QRadioButton(title)
            radio.setStyleSheet(f"font-weight: bold; color: {TEXT_COLOR}; border: none; padding: 2px 0;")
            radio.toggled.connect(lambda checked, k=key: self._on_action_picked(k, checked))
            if key == "install":
                radio.setChecked(True)
            self.action_group.addButton(radio)
            l.addWidget(radio)
            sub = QLabel(desc)
            sub.setStyleSheet(f"color: {SUBTEXT_COLOR}; margin-left: 20px; border: none;")
            sub.setWordWrap(True)
            l.addWidget(sub)
        l.addStretch(1)
        return w

    def _build_confirm(self):
        w, l = self._page("Confirm")
        self.confirm_label = QLabel("")
        self.confirm_label.setWordWrap(True)
        self.confirm_label.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        l.addWidget(self.confirm_label)
        l.addStretch(1)
        self.confirm_checkbox = QCheckBox("I understand this will erase my data.")
        self.confirm_checkbox.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        self.confirm_checkbox.toggled.connect(self._update_nav)
        l.addWidget(self.confirm_checkbox)
        return w

    def _build_progress(self):
        w, l = self._page("Please wait")
        self.progress_status = QLabel("")
        self.progress_status.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        l.addWidget(self.progress_status)
        from PyQt6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet(PROGRESSBAR_STYLE)
        l.addWidget(self.progress_bar)
        l.addStretch(1)
        return w

    def _build_finish(self):
        w, l = self._page("Setup Complete")
        self.finish_label = QLabel("")
        self.finish_label.setWordWrap(True)
        self.finish_label.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        l.addWidget(self.finish_label)
        l.addStretch(1)
        self.launch_checkbox = QCheckBox("Launch Windows XP now")
        self.launch_checkbox.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        self.launch_checkbox.setChecked(True)
        l.addWidget(self.launch_checkbox)
        return w

    def _build_nav(self):
        bar = QWidget()
        bar.setStyleSheet(f"background: {BODY_BG}; border-top: 1px solid #aca899;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(8)
        row.addStretch(1)
        self.back_btn = QPushButton("< Back")
        self.next_btn = QPushButton("Next >")
        self.cancel_btn = QPushButton("Cancel")
        for btn in (self.back_btn, self.next_btn, self.cancel_btn):
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setMinimumWidth(80)
        self.next_btn.setDefault(True)
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn.clicked.connect(self._go_next)
        self.cancel_btn.clicked.connect(self.close)
        row.addWidget(self.back_btn)
        row.addWidget(self.next_btn)
        row.addWidget(self.cancel_btn)
        return bar

    # -- behavior ---------------------------------------------------
    def _detect_status_text(self):
        has_app = actions.has_app_files()
        has_data = actions.has_profile_data()
        if has_app and has_data:
            return "Existing installation found."
        if has_data:
            # main.py was run straight from a checkout, or the app dir was
            # removed by hand -- vfs.json survived either way.
            return "No app files found, but existing user data was found at ~/.winxp_sim."
        if has_app:
            return "App files found, but no user data yet (first run will create it)."
        return "No installation found."

    def _on_action_picked(self, key, checked):
        if checked:
            self.selected_action = key

    def _update_nav(self):
        idx = self.stack.currentIndex()
        self.back_btn.setEnabled(idx == 1)
        self.cancel_btn.setEnabled(idx != 2)
        if idx == 3:
            self.next_btn.setText("Finish")
            self.next_btn.setEnabled(True)
        elif idx == 2:
            self.next_btn.setText("Next >")
            self.next_btn.setEnabled(False)
        else:
            self.next_btn.setText("Next >")
            needs_check = idx == 1 and self.selected_action in DESTRUCTIVE
            self.next_btn.setEnabled(not needs_check or self.confirm_checkbox.isChecked())

    def _go_back(self):
        if self.stack.currentIndex() == 1:
            self.stack.setCurrentIndex(0)
        self._update_nav()

    def _go_next(self):
        idx = self.stack.currentIndex()
        if idx == 0:
            self.confirm_label.setText(
                CONFIRM_TEXT[self.selected_action].format(dir=actions.INSTALL_DIR)
            )
            self.confirm_checkbox.setChecked(False)
            self.confirm_checkbox.setVisible(self.selected_action in DESTRUCTIVE)
            self.stack.setCurrentIndex(1)
        elif idx == 1:
            self._start_action()
        elif idx == 3:
            if self.launch_checkbox.isChecked() and self._launch_offered:
                self._launch_app()
            self.close()
            return
        self._update_nav()

    def _start_action(self):
        self.stack.setCurrentIndex(2)
        self._update_nav()
        self.progress_bar.setValue(0)
        self.progress_status.setText(PROGRESS_LABEL[self.selected_action])
        self.worker = ActionWorker(self.selected_action)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.phase.connect(self.progress_status.setText)
        self.worker.finished_ok.connect(self._on_action_done)
        self.worker.failed.connect(self._on_action_failed)
        self.worker.start()

    def _on_action_done(self, result):
        if self.selected_action == "wipe":
            text = f"Windows XP has been removed from:\n\n{actions.INSTALL_DIR}"
            self._launch_offered = False
        elif self.selected_action == "repair":
            items = result or []
            if items:
                bullets = "\n".join(f"  - {name}" for name in items)
                text = f"Repair complete. Fixed:\n\n{bullets}"
            else:
                text = "Repair complete. Nothing needed fixing."
            self._launch_offered = True
        else:
            text = f"Windows XP is ready to use.\n\nInstalled at:\n{actions.INSTALL_DIR}"
            self._launch_offered = True
        self.launch_checkbox.setVisible(self._launch_offered)
        self.finish_label.setText(text)
        self.stack.setCurrentIndex(3)
        self._update_nav()

    def _on_action_failed(self, message):
        self._launch_offered = False
        self.launch_checkbox.setVisible(False)
        self.finish_label.setText(
            f"Setup could not complete:\n\n{message}\n\n"
            "Check your internet connection and try again."
        )
        self.stack.setCurrentIndex(3)
        self._update_nav()

    def _launch_app(self):
        import subprocess
        main_py = os.path.join(actions.INSTALL_DIR, "main.py")
        if os.path.exists(main_py):
            subprocess.Popen([sys.executable, main_py])


def _light_palette():
    # Fusion style otherwise inherits the OS palette, which under dark mode
    # swaps window/text colors and makes our (deliberately unstyled) default
    # text render as light-on-light or invisible. Pin a fixed light palette
    # so the wizard looks the same regardless of the OS theme.
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BODY_BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_COLOR))
    pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT_COLOR))
    pal.setColor(QPalette.ColorRole.Button, QColor("#f5f4ee"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_COLOR))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffe1"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_COLOR))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_BLUE))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(SUBTEXT_COLOR))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#8a8a8a"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#8a8a8a"))
    return pal


def main():
    # Runs unmodified on Windows, Linux, and macOS -- PyQt6, and the stdlib
    # calls in actions.py, are all cross-platform already. The only OS
    # dependence is cosmetic (UI_FONT_FAMILY above, picked from
    # platform.system()).
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(_light_palette())
    app.setFont(QFont(UI_FONT_FAMILY, 9))
    w = Wizard()
    w.show()
    sys.exit(app.exec())
