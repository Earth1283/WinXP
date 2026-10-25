"""The wizard itself. Deliberately has zero dependency on the winxp package
-- this runs *before* that package necessarily exists on disk. Only
PyQt6, installer.actions and installer.components (stdlib-only) are required.

The flow follows real Setup rather than a generic installer: a text-mode
phase, then GUI-mode Setup -- the blue billboard with the five stages down
the left, and Windows Classic wizard dialogs on top of it for the licence,
product key, setup type and (for a Custom install) Windows Components.
While files copy the dialog goes away and the billboard shows its own
progress bar, the slides, and the famously optimistic time estimate.
"""
from __future__ import annotations

import os
import random
import sys
import time

from PyQt6.QtCore import QRect, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QListWidget, QPlainTextEdit,
    QPushButton, QStackedLayout, QStackedWidget, QWidget,
)

import actions
import components as comps
import pages
from artwork import WarningIcon
from billboard import STAGES, Billboard, ClassicDialog
from style import (
    BODY_BG, TEXT_COLOR, UI_FONT_FAMILY, ClassicStyle, classic_palette, ui_font,
)

# Re-exported because the old module defined them here and something else may
# still be importing them from this path.
__all__ = ["Wizard", "main", "UI_FONT_FAMILY", "BODY_BG", "TEXT_COLOR"]

ACTIONS = [
    ("install", "New installation",
     "Set up a fresh copy of Windows XP on this computer."),
    ("reinstall", "Reinstall (Advanced)",
     "Replace the current installation with a fresh one. All documents, "
     "settings and programs will be erased."),
    ("repair", "Repair installation",
     "Re-fetch application files and fix missing system files. Your "
     "documents and settings are kept."),
    ("wipe", "Remove Windows XP",
     "Remove Windows XP from this computer entirely. All documents and "
     "settings will be erased."),
]
DESTRUCTIVE = {"reinstall", "wipe"}

CONFIRM_TEXT = {
    "install": (
        "Setup has enough information to start copying the program files. "
        "If you want to review or change any settings, click Back. If you "
        "are satisfied with the settings, click Next to begin copying files."
    ),
    "reinstall": (
        "This will permanently erase the current Windows XP installation and "
        "ALL data -- documents, settings, everything -- and set up a fresh "
        "copy. This cannot be undone."
    ),
    "repair": (
        "Setup will re-fetch application files and repair any missing or "
        "corrupted system files. Your documents and settings will not be "
        "affected."
    ),
    "wipe": (
        "This will permanently remove Windows XP and ALL data from this "
        "computer. Nothing will be reinstalled. This cannot be undone."
    ),
}

CONFIRM_TITLE = {
    "install": "Start Copying Files",
    "reinstall": "Start Copying Files",
    "repair": "Ready to Repair",
    "wipe": "Ready to Remove Windows XP",
}

PROGRESS_LABEL = {
    "install": "Installing Windows XP...",
    "reinstall": "Reinstalling Windows XP...",
    "repair": "Repairing Windows XP...",
    "wipe": "Removing Windows XP...",
}

WINDOW_SIZE = (800, 600)
DIALOG_RECT = QRect(250, 92, 520, 440)


class ActionWorker(QThread):
    progress = pyqtSignal(int)
    phase = pyqtSignal(str)
    stage = pyqtSignal(int)
    file_copied = pyqtSignal(str)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, action, selection=None, source_only=True):
        super().__init__()
        self.action = action
        self.selection = selection
        self.source_only = source_only

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
                result = fn(self.selection, on_progress=download, on_file=copied,
                           source_only=self.source_only)
            elif self.action == "repair":
                self.phase.emit("Downloading Windows XP...")
                self.stage.emit(3)
                result = actions.repair(self.selection, on_progress=download,
                                        on_file=copied, source_only=self.source_only)
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
    # page indices inside the dialog's stack
    WELCOME, LICENSE, PRODUCT_KEY, SETUP_TYPE, COMPONENTS, CONFIRM, FINISH = range(7)

    def __init__(self):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Windows XP Professional Setup")
        self.setFixedSize(*WINDOW_SIZE)
        self.selected_action = "install"
        self.worker = None
        self._launch_offered = True
        self._flow = []
        self._flow_pos = 0
        self._selection = comps.default_selection()

        self.screens = QStackedLayout(self)
        self.textmode_page = pages.TextModePage()
        self.textmode_page.done.connect(self._leave_text_mode)
        self.textmode_page.quit_requested.connect(self.close)
        self.screens.addWidget(self.textmode_page)
        self.billboard = Billboard()
        self.screens.addWidget(self.billboard)

        self.dialog = ClassicDialog("Windows XP Professional Setup", self.billboard)
        self.dialog.setGeometry(DIALOG_RECT)
        self.stack = QStackedWidget()
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
        self.finish_page = self._build_finish()
        for pg in (self.welcome_page, self.license_page, self.key_page,
                   self.type_page, self.components_page, self.confirm_page,
                   self.finish_page):
            self.stack.addWidget(pg)
        self.dialog.body.addWidget(self.stack, 1)
        self.dialog.body.addWidget(pages.Etched())
        self.nav = self._build_nav()
        self.dialog.body.addWidget(self.nav)

        self._minutes_timer = QTimer(self)
        self._minutes_timer.timeout.connect(self._tick_minutes)

        self._enter_text_mode()

    # -- text mode -------------------------------------------------------

    def _enter_text_mode(self):
        self.screens.setCurrentWidget(self.textmode_page)
        self.textmode_page.setFocus()
        self.textmode_page.start()

    def _leave_text_mode(self, choice=""):
        if choice:
            # R at the text-mode Welcome screen means "repair", so arrive at
            # the wizard with that already picked.
            self.action_combo.setCurrentIndex(
                [key for key, _, _ in ACTIONS].index(choice))
        self.screens.setCurrentWidget(self.billboard)
        self.billboard.set_stage(0)
        self._flow = [self.WELCOME]
        self._flow_pos = 0
        self.stack.setCurrentIndex(self.WELCOME)
        self._update_nav()
        self.next_btn.setFocus()

    # -- page builders ---------------------------------------------------

    def _build_welcome(self):
        w, l = pages.exterior_page("Welcome to Windows Setup")
        l.addWidget(pages.body_label(
            "This wizard helps you install, repair, or remove Windows XP."))
        l.addWidget(pages.body_label(self._detect_status_text()))
        l.addSpacing(4)

        type_label = pages.body_label("&Installation Type:", wrap=False)
        l.addWidget(type_label)
        self.action_combo = QComboBox()
        for key, title, _ in ACTIONS:
            self.action_combo.addItem(title, key)
        type_label.setBuddy(self.action_combo)
        l.addWidget(self.action_combo)
        self.action_desc = pages.body_label("")
        self.action_desc.setMinimumHeight(30)
        self.action_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        l.addWidget(self.action_desc)
        self.action_combo.currentIndexChanged.connect(self._on_action_picked)
        self._on_action_picked(0)

        self.binary_checkbox = QCheckBox("Install as a &compiled application")
        self.binary_checkbox.setChecked(False)
        l.addWidget(self.binary_checkbox)
        l.addWidget(pages.body_label(
            "Starts faster and does not require Python or PyQt6. If this box "
            "is not checked, Setup will retrieve the source files from "
            "Microsoft's distribution servers and run Windows XP using the "
            "Python interpreter.", indent=19))

        l.addStretch(1)
        l.addWidget(pages.body_label("To continue, click Next."))
        return w

    def _build_confirm(self):
        w, l = pages.titled_page("Start Copying Files",
                                 "Review the settings before copying files.")
        row = QHBoxLayout()
        row.setSpacing(12)
        self.confirm_icon = WarningIcon()
        row.addWidget(self.confirm_icon, 0, Qt.AlignmentFlag.AlignTop)
        self.confirm_label = pages.body_label("")
        row.addWidget(self.confirm_label, 1)
        l.addLayout(row)

        l.addWidget(pages.body_label("Current settings:", wrap=False))
        self.summary_box = QPlainTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        l.addWidget(self.summary_box, 1)

        self.confirm_checkbox = QCheckBox("I &understand this will erase my data.")
        self.confirm_checkbox.toggled.connect(self._update_nav)
        l.addWidget(self.confirm_checkbox)
        return w

    def _build_finish(self):
        w, l = pages.exterior_page("Completing the Windows XP Setup Wizard")
        self.finish_label = pages.body_label("")
        l.addWidget(self.finish_label)
        self.finish_detail = QListWidget()
        self.finish_detail.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.finish_detail.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        l.addWidget(self.finish_detail, 1)
        self.launch_checkbox = QCheckBox("&Launch Windows XP now")
        self.launch_checkbox.setChecked(True)
        l.addWidget(self.launch_checkbox)
        l.addSpacing(6)
        l.addWidget(pages.body_label("To close this wizard, click Finish."))
        return w

    def _build_nav(self):
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(11, 10, 11, 10)
        row.setSpacing(0)
        row.addStretch(1)
        self.back_btn = QPushButton("< &Back")
        self.next_btn = QPushButton("&Next >")
        self.cancel_btn = QPushButton("Cancel")
        for btn in (self.back_btn, self.next_btn, self.cancel_btn):
            btn.setFixedSize(75, 23)
            btn.setAutoDefault(False)
        self.next_btn.setDefault(True)
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn.clicked.connect(self._go_next)
        self.cancel_btn.clicked.connect(self.close)
        # Back and Next touch; Cancel stands apart -- the Wizard97 layout.
        row.addWidget(self.back_btn)
        row.addWidget(self.next_btn)
        row.addSpacing(8)
        row.addWidget(self.cancel_btn)
        return bar

    # -- flow ------------------------------------------------------------

    def _build_flow(self):
        """Which pages this action visits, in order."""
        if self.selected_action in ("install", "reinstall"):
            flow = [self.WELCOME, self.LICENSE, self.PRODUCT_KEY, self.SETUP_TYPE]
            if self.type_page.value() == "custom":
                flow.append(self.COMPONENTS)
            flow += [self.CONFIRM, self.FINISH]
        else:
            flow = [self.WELCOME, self.CONFIRM, self.FINISH]
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
            return "Setup found an existing installation of Windows XP."
        if has_data:
            # main.py was run straight from a checkout, or the app dir was
            # removed by hand -- vfs.json survived either way.
            return ("Setup found no Windows XP program files, but found "
                    "existing user data in ~/.winxp_sim.")
        if has_app:
            return ("Setup found Windows XP program files, but no user data "
                    "yet. It will be created the first time Windows starts.")
        return "Setup did not find an existing installation of Windows XP."

    def _on_action_picked(self, index):
        key = self.action_combo.itemData(index)
        self.selected_action = key
        self.action_desc.setText(ACTIONS[index][2])
        self._flow = self._build_flow()

    def _update_nav(self):
        page = self._current_page()
        self.back_btn.setEnabled(self._flow_pos > 0 and page != self.FINISH)
        self.cancel_btn.setEnabled(page != self.FINISH)

        if page == self.FINISH:
            self.next_btn.setText("Finish")
            self.next_btn.setEnabled(True)
            return
        self.next_btn.setText("&Next >")
        if page == self.LICENSE:
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
        self._focus_page()

    def _focus_page(self):
        """Wizard97 puts the focus back on Next with each new page -- or, if
        Next isn't available yet, on whatever the page is waiting for."""
        page = self._current_page()
        if page == self.PRODUCT_KEY and not self.key_page.is_complete():
            self.key_page.boxes[0].setFocus()
        elif page == self.LICENSE and not self.license_page.is_accepted():
            self.license_page.text.setFocus()
        elif page == self.CONFIRM and not self.next_btn.isEnabled():
            self.confirm_checkbox.setFocus()
        else:
            self.next_btn.setFocus()

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
        self._focus_page()

    def _prepare_confirm(self):
        action = self.selected_action
        self.confirm_page.heading.setText(CONFIRM_TITLE[action])
        self.confirm_page.subheading.setText(
            "Setup has enough information to begin." if action not in DESTRUCTIVE
            else "Read this carefully before you continue.")
        self.confirm_label.setText(CONFIRM_TEXT[action])
        self.confirm_icon.setVisible(action in DESTRUCTIVE)
        self.confirm_checkbox.setChecked(False)
        self.confirm_checkbox.setVisible(action in DESTRUCTIVE)

        launcher = ("Compiled application" if self.binary_checkbox.isChecked()
                    else "Python source")
        lines = [f"Setup action:\n    {self.action_combo.currentText()}",
                 f"Destination folder:\n    {actions.INSTALL_DIR}"]
        if action in ("install", "reinstall"):
            chosen = self._selection
            size = comps.selected_size_mb(chosen)
            lines += [f"Setup type:\n    {self.type_page.value().title()}",
                      f"Components:\n    {len(chosen)} selected, {size:,} MB required",
                      f"Product Key:\n    {self.key_page.key()}"]
        if action != "wipe":
            lines.append(f"Launcher:\n    {launcher}")
        self.summary_box.setPlainText("\n".join(lines))

    # -- running ---------------------------------------------------------

    def _start_action(self):
        """Real Setup took the dialog away while it copied files and let the
        billboard do the talking."""
        self.dialog.hide()
        self.billboard.set_progress(0)
        self.billboard.set_status(PROGRESS_LABEL[self.selected_action])
        self.billboard.set_detail("")
        self.billboard.set_stage(0)
        self.billboard.set_minutes(39)
        self.billboard.show_slides(True)
        self._minutes_timer.start(1400)

        selection = (self._selection
                     if self.selected_action in ("install", "reinstall") else None)
        source_only = not self.binary_checkbox.isChecked()
        self.worker = ActionWorker(self.selected_action, selection, source_only)
        self.worker.progress.connect(self.billboard.set_progress)
        self.worker.phase.connect(self.billboard.set_status)
        self.worker.stage.connect(self.billboard.set_stage)
        self.worker.file_copied.connect(self.billboard.set_detail)
        self.worker.finished_ok.connect(self._on_action_done)
        self.worker.failed.connect(self._on_action_failed)
        self.worker.start()

    def _tick_minutes(self):
        """The estimate that famously sat at 34 minutes for half an hour, then
        finished in one. Non-linear on purpose."""
        pct = (self.billboard.progress or 0) / 100.0
        remaining = max(1, int(39 * (1 - pct) ** 0.55))
        self.billboard.set_minutes(remaining)

    def _leave_progress(self):
        self._minutes_timer.stop()
        self.billboard.show_slides(False)
        self.billboard.set_progress(None)
        self.billboard.set_detail("")
        self._flow_pos = self._flow.index(self.FINISH)
        self.stack.setCurrentIndex(self.FINISH)
        self._update_nav()
        self.dialog.show()
        self.next_btn.setFocus()

    def _on_action_done(self, result):
        self.billboard.set_minutes(1)
        self.billboard.set_stage(len(STAGES))
        self.finish_page.heading.setText("Completing the Windows XP Setup Wizard")
        self.finish_detail.clear()
        if self.selected_action == "wipe":
            text = f"Windows XP has been removed from:\n{actions.INSTALL_DIR}"
            self._launch_offered = False
        elif self.selected_action == "repair":
            items = result or []
            text = ("Setup repaired the following:" if items
                    else "Setup checked your installation. Nothing needed repairing.")
            self.finish_detail.addItems(items)
            self._launch_offered = True
        else:
            text = ("You have successfully completed the Windows XP Setup "
                    f"Wizard. Windows XP is installed at:\n{actions.INSTALL_DIR}")
            self.finish_detail.addItems(result or [])
            if not (result or []):
                self.finish_detail.addItem("All selected components installed.")
            self._launch_offered = True
        self.finish_detail.setVisible(self.finish_detail.count() > 0)
        self.launch_checkbox.setVisible(self._launch_offered)
        self.finish_label.setText(text)
        self._leave_progress()

    def _on_action_failed(self, message):
        self._launch_offered = False
        self.finish_page.heading.setText("Windows XP Setup Was Not Completed")
        self.launch_checkbox.setVisible(False)
        self.finish_detail.clear()
        self.finish_detail.setVisible(False)
        self.finish_label.setText(
            f"Setup could not complete:\n\n{message}\n\n"
            "Check your internet connection and try again."
        )
        self._leave_progress()

    def _launch_app(self):
        import subprocess
        bin_exe = os.path.join(actions.INSTALL_DIR, actions.BIN_SUBDIR, "WinXP.exe")
        if sys.platform == "win32" and os.path.exists(bin_exe):
            # The prebuilt native binary -- no interpreter needed, and it
            # doesn't inherit sys.executable being *this* frozen installer
            # rather than a real python.exe when run from the shipped .exe.
            subprocess.Popen([bin_exe], cwd=os.path.dirname(bin_exe))
            return
        main_py = os.path.join(actions.INSTALL_DIR, "main.py")
        if os.path.exists(main_py):
            subprocess.Popen([sys.executable, main_py])


def _setup_app(app):
    # Qt's "Windows" style is the Windows 95-2000 classic look -- bevelled
    # buttons, sunken fields, dotted focus rectangles -- and it ships with
    # Qt on every platform, so Setup looks like 2001 on a Mac too. The
    # palette is pinned so the OS theme (dark mode especially) can't leak in.
    app.setStyle(ClassicStyle())
    app.setPalette(classic_palette())
    app.setFont(ui_font(11))


def main():
    # Runs unmodified on Windows, Linux, and macOS -- PyQt6, and the stdlib
    # calls in actions.py, are all cross-platform already. The only OS
    # dependence is cosmetic (font choices in style.py).
    app = QApplication(sys.argv)
    _setup_app(app)
    w = Wizard()
    w.show()
    sys.exit(app.exec())
