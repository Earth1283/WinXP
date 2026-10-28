"""Edit menu commands and history/actions -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QDialog

from ....xp_dialog import XPMessageBox
from .. import dialogs as dlg, filters as filt, imageops as ops
from ..canvas import _grayscale_color, _grayscale_image
from ..model import Layer
from .helpers import _vignette
from .widgets import FadeDialog


class EditMixin:
    """Edit menu commands and history/actions."""

    def undo(self):
        self.doc.history.undo()
        self.refresh_all()

    def redo(self):
        self.doc.history.redo()
        self.refresh_all()

    def fade(self):
        """Edit > Fade: reblend the last operation against what it replaced."""
        fade = getattr(self, "_fade", None)
        if fade is None:
            XPMessageBox.information(
                self, "PhotoChop",
                "Could not fade because the last operation cannot be faded.")
            return
        before, after, name = fade
        layer = self.doc.active
        if layer.target_image().size() != after.size():
            XPMessageBox.information(
                self, "PhotoChop",
                "Could not fade because the layer has changed since then.")
            return

        def preview(params):
            if params is None:
                layer.set_target_image(after.copy())
            else:
                from .model import blend_layer
                out = before.copy()
                layer.set_target_image(blend_layer(out, after, params["mode"],
                                                    params["opacity"] / 100.0))
            self.doc.invalidate()
            self.canvas.update()

        d = FadeDialog(self, name, preview)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.history.record(f"Fade {name}")
        else:
            layer.set_target_image(after.copy())
        self.doc.invalidate()
        self.refresh_all()

    def cut(self):
        self.copy()
        self.clear_selection_pixels()

    def copy(self):
        target = self.doc.active.target_image()
        if self.doc.has_selection():
            from .model import alpha_multiply
            self._clipboard = alpha_multiply(target, self.doc.selection.mask).copy(
                self.doc.selection.bounds())
        else:
            self._clipboard = target.copy()
        self._set_hint("Copied.")

    def copy_merged(self):
        flat = self.doc.flattened()
        if self.doc.has_selection():
            from .model import alpha_multiply
            self._clipboard = alpha_multiply(flat, self.doc.selection.mask).copy(
                self.doc.selection.bounds())
        else:
            self._clipboard = flat
        self._set_hint("Copied merged.")

    def paste(self):
        if self._clipboard is None:
            XPMessageBox.warning(self, "PhotoChop", "The clipboard is empty.")
            return
        layer = Layer(f"Layer {len(self.doc.layers)}", self.doc.blank_image())
        p = QPainter(layer.image)
        p.drawImage((self.doc.width - self._clipboard.width()) // 2,
                    (self.doc.height - self._clipboard.height()) // 2, self._clipboard)
        p.end()
        self.doc.add_layer(layer)
        self.doc.history.record("Paste")
        self.refresh_all()

    def paste_into(self):
        if self._clipboard is None or not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop",
                                 "Paste Into needs both a selection and a clipboard.")
            return
        layer = Layer(f"Layer {len(self.doc.layers)}", self.doc.blank_image())
        bounds = self.doc.selection.bounds()
        p = QPainter(layer.image)
        p.drawImage(bounds.topLeft(), self._clipboard)
        p.end()
        layer.mask = self.doc.selection.mask.copy()
        self.doc.add_layer(layer)
        self.doc.history.record("Paste Into")
        self.refresh_all()

    def clear_selection_pixels(self):
        layer = self.doc.active
        if layer.locked_all or layer.locked_pixels:
            self._set_hint("Could not clear: the layer is locked.")
            return
        target = layer.target_image()
        if layer.editing_mask():
            # A mask has no alpha to clear to -- Photoshop paints the
            # background colour instead, exactly like erasing one.
            p = QPainter(target)
            if self.doc.has_selection():
                p.setClipPath(self.doc.selection.path or QPainterPath())
            p.fillRect(target.rect(), _grayscale_color(self.bg_color))
            p.end()
        else:
            p = QPainter(target)
            if self.doc.has_selection():
                from .model import mask_to_alpha
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
                p.drawImage(0, 0, mask_to_alpha(self.doc.selection.mask))
            else:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                p.fillRect(target.rect(), Qt.GlobalColor.transparent)
            p.end()
        self.doc.invalidate()
        self.doc.history.record("Clear")
        self.refresh_all()

    def check_spelling(self):
        XPMessageBox.information(self, "Check Spelling",
                                 "Spelling check complete. 0 errors found.\n\n"
                                 "PhotoChop cannot read, so it found nothing wrong.")

    def find_replace(self):
        XPMessageBox.information(self, "Find and Replace Text",
                                 "PhotoChop has searched every type layer and found "
                                 "nothing, which is technically correct.")

    def fill_dialog(self):
        d = dlg.FillDialog(self)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        spec = d.result()
        colour = {"Foreground Color": self.fg_color, "Background Color": self.bg_color,
                  "Black": QColor("black"), "White": QColor("white"),
                  "50% Gray": QColor(128, 128, 128)}.get(spec["use"])
        layer = self.doc.active
        editing_mask = layer.editing_mask()
        target = layer.target_image()
        fill = self.doc.blank_image()
        p = QPainter(fill)
        if spec["use"] == "Pattern":
            from .layer_styles import _pattern_tile
            p.drawTiledPixmap(fill.rect(), QPixmap.fromImage(_pattern_tile(spec["pattern"])))
        else:
            fill_colour = colour or self.fg_color
            p.fillRect(fill.rect(), _grayscale_color(fill_colour) if editing_mask else fill_colour)
        p.end()
        if editing_mask and spec["use"] == "Pattern":
            fill = _grayscale_image(fill)
        if self.doc.has_selection():
            from .model import alpha_multiply
            fill = alpha_multiply(fill, self.doc.selection.mask)
        from .model import _QT_MODES
        p = QPainter(target)
        p.setOpacity(spec["opacity"] / 100.0)
        if (spec["preserve"] or layer.locked_transparency) and not editing_mask:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        else:
            p.setCompositionMode(_QT_MODES.get(spec["mode"], _QT_MODES["Normal"]))
        p.drawImage(0, 0, fill)
        p.end()
        self.doc.invalidate()
        self.doc.history.record("Fill")
        self.refresh_all()

    def stroke_dialog(self):
        if not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop",
                                 "Could not stroke because there is no selection.")
            return
        d = dlg.StrokeDialog(self, self.fg_color)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        spec = d.result()
        sel = self.doc.selection
        width = spec["width"]
        if spec["location"] == "Outside":
            band = ops.combine(ops.maximum(sel.mask, width), sel.mask,
                               lambda a, b: max(0, a - b))
        elif spec["location"] == "Inside":
            band = ops.combine(sel.mask, ops.minimum(sel.mask, width),
                               lambda a, b: max(0, a - b))
        else:
            half = max(1, width // 2)
            band = ops.combine(ops.maximum(sel.mask, half), ops.minimum(sel.mask, half),
                               lambda a, b: max(0, a - b))
        layer = self.doc.active
        editing_mask = layer.editing_mask()
        fill = self.doc.blank_image()
        p = QPainter(fill)
        p.fillRect(fill.rect(), _grayscale_color(spec["color"]) if editing_mask else spec["color"])
        p.end()
        from .model import alpha_multiply
        fill = alpha_multiply(fill, band)
        p = QPainter(layer.target_image())
        p.setOpacity(spec["opacity"] / 100.0)
        p.drawImage(0, 0, fill)
        p.end()
        self.doc.invalidate()
        self.doc.history.record("Stroke")
        self.refresh_all()

    def define_brush(self):
        self._set_hint("Brush defined from the current selection.")
        XPMessageBox.information(self, "Brush Name", "Sampled Brush 1 has been defined.")

    def define_pattern(self):
        XPMessageBox.information(self, "Pattern Name", "Pattern 1 has been defined.")

    def define_shape(self):
        XPMessageBox.information(self, "Shape Name", "Shape 1 has been defined.")

    def purge(self):
        self.doc.history.clear()
        self.doc.history.record("Purge")
        self._clipboard = None
        self.refresh_all()
        XPMessageBox.information(self, "PhotoChop",
                                 "Undo, Clipboard and Histories have been purged. "
                                 "This cannot be undone, obviously.")

    def color_settings(self):
        from .misc_dialogs import ColorSettingsDialog
        ColorSettingsDialog(self).exec()

    def preset_manager(self):
        from .misc_dialogs import PresetManagerDialog
        PresetManagerDialog(self).exec()

    def preferences(self, page="General..."):
        from .misc_dialogs import PreferencesDialog
        PreferencesDialog(self, page.rstrip(".")).exec()

    def new_snapshot(self):
        self.doc.history.take_snapshot()
        self.refresh_all()

    def delete_history_state(self):
        hist = self.doc.history
        if hist.states and hist.index >= 0:
            del hist.states[hist.index]
            hist.index = min(hist.index, len(hist.states) - 1)
            if hist.index >= 0:
                hist.step_to(hist.index)
            self.refresh_all()

    def record_action(self):
        self.actions_palette.recording = True
        XPMessageBox.information(
            self, "PhotoChop",
            "Recording has started. Every step you take is being recorded and "
            "will be played back at the worst possible moment.")

    def play_action(self):
        name = self.actions_palette.current_action()
        if not name:
            XPMessageBox.warning(self, "PhotoChop", "Select an action to play.")
            return
        if name.startswith("Sepia"):
            self._apply_to_target(
                lambda img: ops.gradient_map(ops.desaturate(img),
                                             [(0.0, QColor("#1e1408")),
                                              (0.5, QColor("#a07a4a")),
                                              (1.0, QColor("#f5e6c8"))]), name)
        elif name.startswith("Custom RGB to Grayscale"):
            self._apply_to_target(ops.desaturate, name)
        elif name.startswith("Gradient Map"):
            self._apply_to_target(
                lambda img: ops.gradient_map(img, [(0.0, self.fg_color),
                                                   (1.0, self.bg_color)]), name)
        elif name.startswith("Molten Lead"):
            self._apply_to_target(
                lambda img: ops.chrome(img) if hasattr(ops, "chrome")
                else filt.chrome(img), name)
        elif name.startswith("Vignette"):
            self._apply_to_target(lambda img: _vignette(img), name)
        elif name.startswith("Quadrant Colors"):
            self._apply_to_target(lambda img: ops.posterize(img, 4), name)
        else:
            XPMessageBox.information(
                self, "PhotoChop",
                f"The action '{name}' referenced a file that has been moved, a font "
                f"that is not installed, and a plug-in that never shipped.")
