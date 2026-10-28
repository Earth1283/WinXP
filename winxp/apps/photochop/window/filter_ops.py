"""Filter menu commands -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog

from ....xp_dialog import XPMessageBox
from .. import dialogs as dlg, filters as filt


class FilterMixin:
    """Filter menu commands."""

    def run_filter(self, label, key, params):
        layer = self.doc.active
        if layer.kind == "adjustment":
            XPMessageBox.warning(self, "PhotoChop",
                                 "Could not apply the filter to an adjustment layer.")
            return
        ctx = {"fg": self.fg_color.name(), "bg": self.bg_color.name()}
        if not params:
            self._apply_filter(key, {}, ctx, label)
            return
        source = layer.image
        values = dlg.FilterDialog.run(
            self, label.rstrip("."), params,
            lambda v: filt.run(key, source, v, ctx), source)
        if values is not None:
            self._apply_filter(key, values, ctx, label)

    def _apply_filter(self, key, values, ctx, label):
        self.last_filter = (label, key, values, ctx)
        self.last_filter_action.setEnabled(True)
        self.last_filter_action.setText(label.rstrip("."))
        self._apply_to_target(lambda img: filt.run(key, img, values, ctx),
                              label.rstrip("."))

    def repeat_last_filter(self):
        if not self.last_filter:
            return
        label, key, values, ctx = self.last_filter
        self._apply_to_target(lambda img: filt.run(key, img, values, ctx),
                              label.rstrip("."))

    def extract(self):
        from .workspaces import ExtractDialog
        d = ExtractDialog(self, self.doc.active.image)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.active.image = d.result()
            self.doc.invalidate()
            self.doc.history.record("Extract")
            self.refresh_all()

    def liquify(self):
        from .workspaces import LiquifyDialog
        d = LiquifyDialog(self, self.doc.active.image)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.active.image = d.result()
            self.doc.invalidate()
            self.doc.history.record("Liquify")
            self.refresh_all()

    def pattern_maker(self):
        from .workspaces import PatternMakerDialog
        d = PatternMakerDialog(self, self.doc.active.image)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.active.image = d.result()
            self.doc.invalidate()
            self.doc.history.record("Pattern Maker")
            self.refresh_all()
