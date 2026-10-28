"""Select menu commands, channels and paths -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QDialog

from ....xp_dialog import XPMessageBox
from .. import adjust_dialogs as adj, dialogs as dlg
from ..canvas import _grayscale_color


class SelectionMixin:
    """Select menu commands, channels and paths."""

    def select_all(self):
        sel = self.doc.ensure_selection()
        sel.select_all()
        self.doc.history.record("Select All")
        self.refresh_all()

    def deselect(self):
        if self.doc.selection:
            self._last_selection = self.doc.selection.copy()
        self.canvas.deselect()
        self.doc.history.record("Deselect")
        self.refresh_all()

    def reselect(self):
        prior = getattr(self, "_last_selection", None)
        if prior:
            self.doc.selection = prior.copy()
            self.doc.history.record("Reselect")
            self.refresh_all()

    def inverse_selection(self):
        if not self.doc.has_selection():
            self.select_all()
            return
        self.doc.selection.invert()
        self.doc.history.record("Inverse")
        self.refresh_all()

    def color_range(self):
        d = adj.ColorRangeDialog(self, self.doc.composite(), self.fg_color)
        if d.exec() == QDialog.DialogCode.Accepted:
            sel = self.doc.ensure_selection()
            sel.set_mask(d.mask(), "replace")
            self.doc.history.record("Color Range")
            self.refresh_all()

    def feather(self):
        if not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop", "There is no selection to feather.")
            return
        d = dlg.FeatherDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.selection.feather(d.result())
            self.doc.history.record("Feather")
            self.refresh_all()

    def modify_selection(self, kind):
        if not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop", "There is no selection to modify.")
            return
        value = dlg.ValueDialog.get(self, kind + " Selection",
                                    ("Width:" if kind == "Border" else
                                     "Sample Radius:" if kind == "Smooth" else
                                     "Expand By:" if kind == "Expand" else "Contract By:"),
                                    5, 1, 100)
        if value is None:
            return
        sel = self.doc.selection
        {"Border": sel.border, "Smooth": sel.smooth,
         "Expand": sel.expand, "Contract": sel.contract}[kind](value)
        self.doc.history.record(kind)
        self.refresh_all()

    def grow_selection(self):
        if self.doc.has_selection():
            self.doc.selection.expand(4)
            self.doc.history.record("Grow")
            self.refresh_all()

    def similar_selection(self):
        if not self.doc.has_selection():
            return
        from .canvas import magic_wand_mask
        bounds = self.doc.selection.bounds()
        seed = bounds.center()
        mask = magic_wand_mask(self.doc.composite(), seed,
                               self.options.get("tolerance", 32), contiguous=False)
        if mask is not None:
            self.doc.selection.set_mask(mask, "add")
            self.doc.history.record("Similar")
            self.refresh_all()

    def transform_selection(self):
        self.canvas.begin_transform("Free Transform")

    def load_channel_selection(self):
        if not self.doc.alpha_channels:
            XPMessageBox.warning(self, "PhotoChop", "There are no saved selections.")
            return
        name, mask = self.doc.alpha_channels[-1]
        sel = self.doc.ensure_selection()
        sel.set_mask(mask.copy(), "replace")
        self._set_hint(f"Loaded selection from {name}.")
        self.refresh_all()

    def save_selection_channel(self):
        if not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop", "There is no selection to save.")
            return
        name = f"Alpha {len(self.doc.alpha_channels) + 1}"
        self.doc.alpha_channels.append((name, self.doc.selection.mask.copy()))
        self._set_hint(f"Selection saved as {name}.")
        self.refresh_all()

    def new_alpha_channel(self):
        blank = QImage(self.doc.width, self.doc.height,
                       QImage.Format.Format_ARGB32_Premultiplied)
        blank.fill(Qt.GlobalColor.black)
        self.doc.alpha_channels.append((f"Alpha {len(self.doc.alpha_channels) + 1}", blank))
        self.refresh_all()

    def delete_alpha_channel(self):
        if self.doc.alpha_channels:
            self.doc.alpha_channels.pop()
            self.refresh_all()

    def set_quick_mask(self, on):
        if on and not self.doc.has_selection():
            self.select_all()
        self.doc.quick_mask = on
        for i, btn in enumerate(self.quick_mask_buttons):
            btn.setChecked(bool(i) == on)
        self._set_hint("Edit in Quick Mask Mode" if on else "Edit in Standard Mode")
        self.canvas.update()

    # ============================================================ paths ====

    def new_path(self):
        self.doc.paths.append((f"Path {len(self.doc.paths) + 1}", QPainterPath()))
        self.refresh_all()

    def delete_path(self):
        row = self.paths.list.currentRow()
        if 0 <= row < len(self.doc.paths):
            del self.doc.paths[row]
            self.refresh_all()

    def _current_path(self):
        row = self.paths.list.currentRow()
        if 0 <= row < len(self.doc.paths):
            return self.doc.paths[row][1]
        return self.doc.paths[-1][1] if self.doc.paths else None

    def fill_path(self):
        path = self._current_path()
        if path is None:
            return
        layer = self.doc.active
        editing_mask = layer.editing_mask()
        p = QPainter(layer.target_image())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_grayscale_color(self.fg_color) if editing_mask else self.fg_color)
        p.drawPath(path)
        p.end()
        self.doc.invalidate()
        self.doc.history.record("Fill Path")
        self.refresh_all()

    def stroke_path(self):
        path = self._current_path()
        if path is None:
            return
        layer = self.doc.active
        editing_mask = layer.editing_mask()
        brush = self.options.get("brush", {})
        pen_colour = _grayscale_color(self.fg_color) if editing_mask else self.fg_color
        p = QPainter(layer.target_image())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(pen_colour, max(1, brush.get("size", 13) // 3),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()
        self.doc.invalidate()
        self.doc.history.record("Stroke Path")
        self.refresh_all()

    def path_to_selection(self):
        path = self._current_path()
        if path is None:
            return
        sel = self.doc.ensure_selection()
        sel.set_path(path, "replace")
        self.doc.history.record("Make Selection")
        self.refresh_all()

    def selection_to_path(self):
        if not self.doc.has_selection() or self.doc.selection.path is None:
            return
        self.doc.paths.append((f"Work Path", QPainterPath(self.doc.selection.path)))
        self.refresh_all()
