"""The wizard itself. Deliberately has zero dependency on the winxp package
-- this runs *before* that package necessarily exists on disk. Only
PyQt6, installer.actions and installer.components (stdlib-only) are required.

The flow follows real Setup rather than a generic installer: a text-mode
phase, then licence, product key, setup type, and -- for a Custom install --
Select Components. During the copy phase the sidebar becomes the five-stage
checklist with the famously optimistic time estimate.
"""
from __future__ import annotations

import os
import random
import sys
import time

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPalette
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QListWidget,
    QProgressBar, QPushButton, QRadioButton, QStackedWidget, QVBoxLayout, QWidget,
)

import actions
import components as comps
import pages
from style import (
    ACCENT_BLUE, BODY_BG, BUTTON_STYLE, PROGRESSBAR_STYLE, RULE_COLOR,
    SIDEBAR_BLUE_BOTTOM, SIDEBAR_BLUE_TOP, SUBTEXT_COLOR, TEXT_COLOR,
    UI_FONT_FAMILY,
)

# Re-exported because the old module defined them here and something else may
# still be importing them from this path.
__all__ = ["Wizard", "main", "UI_FONT_FAMILY", "BODY_BG", "TEXT_COLOR"]

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

# The five stages down the left of real Setup.
STAGES = ["Collecting information", "Dynamic Update", "Preparing installation",
          "Installing Windows", "Finalizing installation"]


class Sidebar(QWidget):
    """Blue panel. Shows the product name normally, and the stage checklist
    plus time estimate once Setup is actually doing something."""

    def __init__(self):
        super().__init__()
        self.setFixedWidth(178)
        self.stage_index = -1        # -1 = not in the copy phase
        self.minutes_left = 39

    def set_stage(self, index):
        self.stage_index = index
        self.update()

    def set_minutes(self, minutes):
        self.minutes_left = minutes
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(SIDEBAR_BLUE_TOP))
        g.setColorAt(1, QColor(SIDEBAR_BLUE_BOTTOM))
        p.fillRect(self.rect(), g)

        p.setPen(QColor("white"))
        p.setFont(QFont(UI_FONT_FAMILY, 15, QFont.Weight.Bold))
        p.drawText(16, 34, 146, 90, Qt.TextFlag.TextWordWrap,
                   "Windows XP\nSetup Wizard")

        if self.stage_index >= 0:
            self._paint_stages(p)
        else:
            p.setFont(QFont(UI_FONT_FAMILY, 8))
            p.setPen(QColor(255, 255, 255, 200))
            p.drawText(16, self.height() - 70, 146, 60, Qt.TextFlag.TextWordWrap,
                       "Earth1283/WinXP\ngithub.com")
        p.end()

    def _paint_stages(self, p):
        y = 132
        for i, stage in enumerate(STAGES):
            done = i < self.stage_index
            current = i == self.stage_index
            if current:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 46))
                p.drawRect(6, y - 12, self.width() - 12, 20)
            p.setPen(QColor("white") if current or done
                     else QColor(255, 255, 255, 120))
            p.setFont(QFont(UI_FONT_FAMILY, 8,
                            QFont.Weight.Bold if current else QFont.Weight.Normal))
            marker = "✓" if done else ("►" if current else "")
            p.drawText(12, y, 14, 14, Qt.AlignmentFlag.AlignLeft, marker)
            p.drawText(28, y - 11, 142, 18, Qt.TextFlag.TextWordWrap, stage)
            y += 24

        p.setPen(QColor(255, 255, 255, 210))
        p.setFont(QFont(UI_FONT_FAMILY, 8))
        p.drawText(14, self.height() - 62, 150, 56, Qt.TextFlag.TextWordWrap,
                   "Setup will complete in\napproximately:\n\n"
                   f"{self.minutes_left} minutes")


class ActionWorker(QThread):
    progress = pyqtSignal(int)
    phase = pyqtSignal(str)
    stage = pyqtSignal(int)
    file_copied = pyqtSignal(str)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, action, selection=None):
        super().__init__()
        self.action = action
        self.selection = selection

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
            self.stage.emit(0)
            self._fake_ramp(0, 8, "Setup is collecting information...")
            self.stage.emit(1)
            self._fake_ramp(8, 14, "Setup is checking for updates...")
            self.stage.emit(2)

            result = None
            download = lambda p: self.progress.emit(14 + int(p * 0.46))
            copied = lambda name: self.file_copied.emit(name)

            if self.action in ("install", "reinstall"):
                self.phase.emit("Downloading Windows XP...")
                fn = actions.install if self.action == "install" else actions.reinstall
                self.stage.emit(3)
                result = fn(self.selection, on_progress=download, on_file=copied)
            elif self.action == "repair":
                self.phase.emit("Downloading Windows XP...")
                self.stage.emit(3)
                result = actions.repair(self.selection, on_progress=download,
                                        on_file=copied)
            elif self.action == "wipe":
                self.stage.emit(3)
                self._fake_ramp(14, 78, "Removing files...")
                actions.wipe()

            self.progress.emit(88)
            self.stage.emit(4)
            self._fake_ramp(88, 100, "Setup is finalizing your installation...")
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class Wizard(QWidget):
    # page indices inside the stack
    TEXTMODE, WELCOME, LICENSE, PRODUCT_KEY, SETUP_TYPE, COMPONENTS, \
        CONFIRM, PROGRESS, FINISH = range(9)

    def __init__(self):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Windows XP Setup Wizard")
        self.setFixedSize(660, 486)
        self.selected_action = "install"
        self.worker = None
        self._launch_offered = True
        self._flow = []
        self._flow_pos = 0
        self._selection = comps.default_selection()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {BODY_BG};")
        self.textmode_page = pages.TextModePage()
        self.textmode_page.done.connect(self._leave_text_mode)
        # Built before the welcome page: picking an action there recomputes the
        # flow, which asks the setup-type page what it is set to.
        self.license_page = pages.LicensePage()
        self.license_page.accepted_changed.connect(self._update_nav)
        self.key_page = pages.ProductKeyPage()
        self.key_page.key_changed.connect(self._update_nav)
        self.type_page = pages.SetupTypePage()
        self.type_page.type_changed.connect(self._on_type_changed)
        self.components_page = pages.ComponentsPage()
        self.components_page.selection_changed.connect(self._update_nav)
        self.welcome_page = self._build_welcome()
        self.confirm_page = self._build_confirm()
        self.progress_page = self._build_progress()
        self.finish_page = self._build_finish()
        for pg in (self.textmode_page, self.welcome_page, self.license_page,
                   self.key_page, self.type_page, self.components_page,
                   self.confirm_page, self.progress_page, self.finish_page):
            self.stack.addWidget(pg)
        right.addWidget(self.stack, 1)

        self.nav = self._build_nav()
        right.addWidget(self.nav)
        root.addLayout(right, 1)

        self._minutes_timer = QTimer(self)
        self._minutes_timer.timeout.connect(self._tick_minutes)

        self._enter_text_mode()

    # -- text mode -------------------------------------------------------

    def _enter_text_mode(self):
        self.stack.setCurrentIndex(self.TEXTMODE)
        self.sidebar.hide()
        self.nav.hide()
        self.textmode_page.setFocus()
        self.textmode_page.start()

    def _leave_text_mode(self):
        self.sidebar.show()
        self.nav.show()
        self._flow = [self.WELCOME]
        self._flow_pos = 0
        self.stack.setCurrentIndex(self.WELCOME)
        self._update_nav()

    # -- page builders ---------------------------------------------------

    def _build_welcome(self):
        w, l = pages.titled_page("What would you like to do?")
        l.addWidget(pages.body_label(self._detect_status_text(), muted=True))

        self.action_group = QButtonGroup(w)
        for key, title, desc in ACTIONS:
            radio = QRadioButton(title)
            radio.setStyleSheet(
                f"font-weight: bold; color: {TEXT_COLOR}; border: none; padding: 2px 0;")
            radio.toggled.connect(lambda checked, k=key: self._on_action_picked(k, checked))
            if key == "install":
                radio.setChecked(True)
            self.action_group.addButton(radio)
            l.addWidget(radio)
            sub = pages.body_label(desc, muted=True)
            sub.setStyleSheet(
                f"color: {SUBTEXT_COLOR}; margin-left: 20px; border: none;")
            l.addWidget(sub)
        l.addStretch(1)
        return w

    def _build_confirm(self):
        w, l = pages.titled_page("Confirm")
        self.confirm_label = pages.body_label("")
        l.addWidget(self.confirm_label)
        self.summary_label = pages.body_label("", muted=True)
        l.addWidget(self.summary_label)
        l.addStretch(1)
        self.confirm_checkbox = QCheckBox("I understand this will erase my data.")
        self.confirm_checkbox.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        self.confirm_checkbox.toggled.connect(self._update_nav)
        l.addWidget(self.confirm_checkbox)
        return w

    def _build_progress(self):
        w, l = pages.titled_page("Installing Windows XP")
        self.progress_status = pages.body_label("")
        l.addWidget(self.progress_status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet(PROGRESSBAR_STYLE)
        l.addWidget(self.progress_bar)

        l.addWidget(pages.body_label("Files installed:", muted=True))
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(
            "QListWidget { background: #ffffff; border: 1px solid #7f9db9;"
            " color: #303030; }"
            "QListWidget::item { padding: 0 2px; }")
        self.file_list.setFont(QFont(UI_FONT_FAMILY, 8))
        self.file_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        l.addWidget(self.file_list, 1)
        return w

    def _build_finish(self):
        w, l = pages.titled_page("Setup Complete")
        self.finish_label = pages.body_label("")
        l.addWidget(self.finish_label)
        self.finish_detail = QListWidget()
        self.finish_detail.setStyleSheet(
            "QListWidget { background: #ffffff; border: 1px solid #7f9db9;"
            " color: #303030; }")
        self.finish_detail.setFont(QFont(UI_FONT_FAMILY, 8))
        self.finish_detail.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.finish_detail.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        l.addWidget(self.finish_detail, 1)
        self.launch_checkbox = QCheckBox("Launch Windows XP now")
        self.launch_checkbox.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        self.launch_checkbox.setChecked(True)
        l.addWidget(self.launch_checkbox)
        return w

    def _build_nav(self):
        bar = QWidget()
        bar.setStyleSheet(f"background: {BODY_BG}; border-top: 1px solid {RULE_COLOR};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(8)
        row.addStretch(1)
        self.back_btn = QPushButton("< Back")
        self.next_btn = QPushButton("Next >")
        self.cancel_btn = QPushButton("Cancel")
        for btn in (self.back_btn, self.next_btn, self.cancel_btn):
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setMinimumWidth(84)
        self.next_btn.setDefault(True)
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn.clicked.connect(self._go_next)
        self.cancel_btn.clicked.connect(self.close)
        row.addWidget(self.back_btn)
        row.addWidget(self.next_btn)
        row.addWidget(self.cancel_btn)
        return bar

    # -- flow ------------------------------------------------------------

    def _build_flow(self):
        """Which pages this action visits, in order."""
        if self.selected_action in ("install", "reinstall"):
            flow = [self.WELCOME, self.LICENSE, self.PRODUCT_KEY, self.SETUP_TYPE]
            if self.type_page.value() == "custom":
                flow.append(self.COMPONENTS)
            flow += [self.CONFIRM, self.PROGRESS, self.FINISH]
        else:
            flow = [self.WELCOME, self.CONFIRM, self.PROGRESS, self.FINISH]
        return flow

    def _on_type_changed(self):
        if self.type_page.value() == "complete":
            self._selection = comps.complete_selection()
        elif self.type_page.value() == "typical":
            self._selection = comps.typical_selection()
        self.components_page.set_selection(self._selection)
        self._flow = self._build_flow()
        self._update_nav()

    def _current_page(self):
        return self.stack.currentIndex()

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
            self._flow = self._build_flow()

    def _update_nav(self):
        page = self._current_page()
        self.back_btn.setEnabled(self._flow_pos > 0 and page not in
                                 (self.PROGRESS, self.FINISH, self.TEXTMODE))
        self.cancel_btn.setEnabled(page != self.PROGRESS)

        if page == self.FINISH:
            self.next_btn.setText("Finish")
            self.next_btn.setEnabled(True)
            return
        self.next_btn.setText("Next >")
        if page == self.PROGRESS:
            self.next_btn.setEnabled(False)
        elif page == self.LICENSE:
            self.next_btn.setEnabled(self.license_page.is_accepted())
        elif page == self.PRODUCT_KEY:
            self.next_btn.setEnabled(self.key_page.is_complete())
        elif page == self.COMPONENTS:
            self.next_btn.setEnabled(self.components_page.has_enough_space())
        elif page == self.CONFIRM:
            needs_check = self.selected_action in DESTRUCTIVE
            self.next_btn.setEnabled(
                not needs_check or self.confirm_checkbox.isChecked())
        else:
            self.next_btn.setEnabled(True)

    def _go_back(self):
        if self._flow_pos == 0:
            return
        self._flow_pos -= 1
        self.stack.setCurrentIndex(self._flow[self._flow_pos])
        self._update_nav()

    def _go_next(self):
        page = self._current_page()

        if page == self.FINISH:
            if self.launch_checkbox.isChecked() and self._launch_offered:
                self._launch_app()
            self.close()
            return

        if page == self.WELCOME:
            self._flow = self._build_flow()

        if page == self.COMPONENTS:
            self._selection = self.components_page.selection()

        if page == self.CONFIRM:
            self._start_action()
            return

        self._flow_pos = min(self._flow_pos + 1, len(self._flow) - 1)
        target = self._flow[self._flow_pos]

        if target == self.CONFIRM:
            self._prepare_confirm()
        if target == self.COMPONENTS:
            self.components_page.set_selection(self._selection)

        self.stack.setCurrentIndex(target)
        self._update_nav()

    def _prepare_confirm(self):
        self.confirm_label.setText(
            CONFIRM_TEXT[self.selected_action].format(dir=actions.INSTALL_DIR))
        self.confirm_checkbox.setChecked(False)
        self.confirm_checkbox.setVisible(self.selected_action in DESTRUCTIVE)
        if self.selected_action in ("install", "reinstall"):
            chosen = self._selection
            names = [comps.BY_ID[c].label for c in chosen
                     if not comps.BY_ID[c].children and not comps.BY_ID[c].required]
            size = comps.selected_size_mb(chosen)
            self.summary_label.setText(
                f"Setup type: {self.type_page.value().title()}\n"
                f"Components: {len(chosen)} selected, {size:,} MB required\n"
                f"Product Key: {self.key_page.key()}")
            self.summary_label.setVisible(True)
        else:
            self.summary_label.setVisible(False)

    # -- running ---------------------------------------------------------

    def _start_action(self):
        self._flow_pos = self._flow.index(self.PROGRESS)
        self.stack.setCurrentIndex(self.PROGRESS)
        self._update_nav()
        self.progress_bar.setValue(0)
        self.file_list.clear()
        self.progress_status.setText(PROGRESS_LABEL[self.selected_action])
        self.sidebar.set_stage(0)
        self.sidebar.set_minutes(39)
        self._minutes_timer.start(1400)

        selection = (self._selection
                     if self.selected_action in ("install", "reinstall") else None)
        self.worker = ActionWorker(self.selected_action, selection)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.phase.connect(self.progress_status.setText)
        self.worker.stage.connect(self.sidebar.set_stage)
        self.worker.file_copied.connect(self._on_file_copied)
        self.worker.finished_ok.connect(self._on_action_done)
        self.worker.failed.connect(self._on_action_failed)
        self.worker.start()

    def _tick_minutes(self):
        """The estimate that famously sat at 34 minutes for half an hour, then
        finished in one. Non-linear on purpose."""
        pct = self.progress_bar.value() / 100.0
        remaining = max(1, int(39 * (1 - pct) ** 0.55))
        self.sidebar.set_minutes(remaining)

    def _on_file_copied(self, name):
        self.file_list.addItem(name)
        if self.file_list.count() > 400:
            self.file_list.takeItem(0)
        self.file_list.scrollToBottom()

    def _on_action_done(self, result):
        self._minutes_timer.stop()
        self.sidebar.set_stage(-1)
        self.finish_detail.clear()
        if self.selected_action == "wipe":
            text = f"Windows XP has been removed from:\n\n{actions.INSTALL_DIR}"
            self._launch_offered = False
        elif self.selected_action == "repair":
            items = result or []
            text = ("Repair complete. Fixed:" if items
                    else "Repair complete. Nothing needed fixing.")
            self.finish_detail.addItems(items)
            self._launch_offered = True
        else:
            text = f"Windows XP is ready to use.\n\nInstalled at:\n{actions.INSTALL_DIR}"
            self.finish_detail.addItems(result or [])
            if not (result or []):
                self.finish_detail.addItem("All selected components installed.")
            self._launch_offered = True
        self.finish_detail.setVisible(self.finish_detail.count() > 0)
        self.launch_checkbox.setVisible(self._launch_offered)
        self.finish_label.setText(text)
        self._flow_pos = self._flow.index(self.FINISH)
        self.stack.setCurrentIndex(self.FINISH)
        self._update_nav()

    def _on_action_failed(self, message):
        self._minutes_timer.stop()
        self.sidebar.set_stage(-1)
        self._launch_offered = False
        self.launch_checkbox.setVisible(False)
        self.finish_detail.clear()
        self.finish_detail.setVisible(False)
        self.finish_label.setText(
            f"Setup could not complete:\n\n{message}\n\n"
            "Check your internet connection and try again."
        )
        self._flow_pos = self._flow.index(self.FINISH)
        self.stack.setCurrentIndex(self.FINISH)
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
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,
                 QColor("#8a8a8a"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#8a8a8a"))
    return pal


def main():
    # Runs unmodified on Windows, Linux, and macOS -- PyQt6, and the stdlib
    # calls in actions.py, are all cross-platform already. The only OS
    # dependence is cosmetic (UI_FONT_FAMILY in style.py, picked from
    # platform.system()).
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(_light_palette())
    app.setFont(QFont(UI_FONT_FAMILY, 9))
    w = Wizard()
    w.show()
    sys.exit(app.exec())
