from __future__ import annotations

import random

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

STOP_CODES = {
    "csrss.exe": "0x000000F4 (0x00000003, 0x8570A020, 0x8570A194, 0x805CFA30)",
    "winlogon.exe": "0x0000006B (0xC0000001, 0x00000000, 0x00000000, 0x00000000)",
    "smss.exe": "0x0000001E (0xC0000005, 0x804E2548, 0x00000000, 0x00000000)",
    "services.exe": "0x00000074 (0x00000004, 0x00000000, 0x00000000, 0x00000000)",
    "lsass.exe": "0xC000021A (0x00000000, 0x00000000, 0x00000000, 0x00000000)",
    "System": "0x0000000A (0x00000008, 0x00000002, 0x00000000, 0x804E2548)",
}
DEFAULT_STOP = "0x0000007E (0xC0000005, 0x00000000, 0x00000000, 0x00000000)"


class BSOD(QWidget):
    """Cursed: killing a critical process in Task Manager lands here."""

    def __init__(self, proc_name, on_reboot):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.on_reboot = on_reboot
        self.setStyleSheet("background: #0000AA;")
        self._pct = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(70, 60, 70, 40)
        layout.setSpacing(14)

        stop_code = STOP_CODES.get(proc_name, DEFAULT_STOP)
        addr = f"0x{random.randint(0x10000000, 0xFFFFFFFF):08X}"

        text = (
            "A problem has been detected and Windows has been shut down to prevent "
            "damage to your computer.\n\n"
            f"KMODE_EXCEPTION_NOT_HANDLED -- {proc_name} terminated unexpectedly\n\n"
            "If this is the first time you've seen this Stop error screen, restart "
            "your computer. If this screen appears again, follow these steps:\n\n"
            "Check to make sure any new hardware or software is properly installed. "
            "If this is a new installation, ask your hardware or software manufacturer "
            "for any Windows updates you might need.\n\n"
            "If problems continue, disable or remove any newly installed hardware or "
            "software. Disable BIOS memory options such as caching or shadowing. If you "
            "need to use Safe Mode to remove or disable components, restart your "
            "computer, press F8 to select Advanced Startup Options, and then select "
            "Safe Mode.\n\n"
            "Technical information:\n\n"
            f"*** STOP: {stop_code}\n"
            f"*** {proc_name} - Address {addr} base at 0x00400000, DateStamp 0x3f7d0037"
        )

        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: white; background: transparent;")
        label.setFont(QFont("Consolas", 12))
        layout.addWidget(label)
        layout.addStretch(1)

        self.progress = QLabel("Beginning dump of physical memory...")
        self.progress.setStyleSheet("color: white; background: transparent;")
        self.progress.setFont(QFont("Consolas", 12))
        layout.addWidget(self.progress)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(120)

    def show_fullscreen_on(self, wm):
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.show()
        self.raise_()
        self.activateWindow()

    def _tick(self):
        self._pct = min(100, self._pct + random.randint(3, 9))
        if self._pct >= 100:
            self.progress.setText(
                "Physical memory dump complete.\n"
                "Contact your system administrator or technical support group for further assistance."
            )
            self._timer.stop()
            QTimer.singleShot(1800, self._reboot)
        else:
            self.progress.setText(
                f"Beginning dump of physical memory...\nPhysical memory dump: {self._pct}% complete."
            )

    def _reboot(self):
        self.close()
        self.on_reboot()


def crash(wm, proc_name):
    """Kill everything and show a BSOD, keyed off wm so callers don't need a ref alive."""
    def reboot():
        for window in list(wm.windows):
            window.close()
        from ..corruption import health
        health.reset()

    b = BSOD(proc_name, reboot)
    b.show_fullscreen_on(wm)
    wm._bsod_ref = b
    return b
