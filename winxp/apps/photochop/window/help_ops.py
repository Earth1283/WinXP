"""Help menu commands -- mixin for PhotoChopWindow."""
from __future__ import annotations

from ....xp_dialog import XPMessageBox
from ..splash import AboutDialog


class HelpMixin:
    """Help menu commands."""

    def show_help(self):
        from .misc_dialogs import HelpDialog
        HelpDialog(self).exec()

    def about(self):
        AboutDialog(self).exec()

    def about_plugin(self):
        XPMessageBox.information(
            self, "About Plug-In",
            "Chrome Filter 1.0\n\nCopyright 1991-2002. All rights probably reserved.")

    def help_wizard(self):
        XPMessageBox.information(
            self, "PhotoChop",
            "This wizard would walk you through five steps that each do one "
            "thing you already know how to do.")

    def system_info(self):
        XPMessageBox.information(
            self, "System Info",
            f"PhotoChop 7.0\nSerial: 1045-1234-5678-9012-3456-7890\n\n"
            f"Physical memory: 256 MB\nMemory available to PhotoChop: 51 MB\n"
            f"Scratch disk: C:\\ (free: not much)\n"
            f"Image cache level: 4\nDocument: {self.doc.width} x {self.doc.height}")

    def support(self):
        XPMessageBox.information(
            self, "PhotoChop",
            "Could not connect to the internet because dial-up is not configured.")

    def register(self):
        XPMessageBox.information(
            self, "Registration",
            "Thank you for registering PhotoChop. Your details have been written "
            "to a floppy disk and mailed to nobody.")

    def deactivate(self):
        XPMessageBox.information(
            self, "Transfer Activation",
            "You have used 1 of 2 activations.\n\nDeactivating will let you activate "
            "PhotoChop on another computer. There is no other computer.")
