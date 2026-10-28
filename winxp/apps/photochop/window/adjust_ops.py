"""Image > Adjustments commands -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QDialog

from ....xp_dialog import XPMessageBox
from .. import adjust_dialogs as adj, imageops as ops


class AdjustMixin:
    """Image > Adjustments commands."""

    def _apply_to_target(self, fn, name, force_image=False):
        """Run a pixel operation on the active layer, honouring the selection.

        Targets the layer's mask instead of its pixels when the mask is the
        selected paint target -- filters and adjustments work on a mask's
        greyscale channel exactly as they do on real pixels.
        """
        layer = self.doc.active
        if layer.locked_all or layer.locked_pixels:
            XPMessageBox.warning(self, "PhotoChop", "Could not complete the command "
                                                    "because the layer is locked.")
            return
        source = layer.image if force_image else layer.target_image()
        result = fn(source)
        if result is None:
            return
        if self.doc.has_selection():
            result = self.doc.selection.apply(source, result)
        # keep both sides so Edit > Fade can interpolate between them
        self._fade = (source.copy(), result.copy(), name)
        if force_image:
            layer.image = result
        else:
            layer.set_target_image(result)
        self.doc.invalidate()
        self.doc.history.record(name)
        self.refresh_all()

    def _live_adjust(self, name, fn):
        """Wire an adjustment dialog's preview to the real layer, restoring the
        original whenever the preview is switched off or the dialog cancelled."""
        layer = self.doc.active
        backup = layer.target_image().copy()

        def preview(params):
            if params is None:
                layer.set_target_image(backup.copy())
            else:
                result = fn(backup, params)
                layer.set_target_image(self.doc.selection.apply(backup, result)
                                       if self.doc.has_selection() else result)
            self.doc.invalidate()
            self.canvas.update()

        return backup, preview

    def _finish_adjust(self, dialog, backup, name):
        layer = self.doc.active
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.doc.history.record(name)
        else:
            layer.set_target_image(backup)
        self.doc.invalidate()
        self.refresh_all()

    def levels(self):
        backup, preview = self._live_adjust("Levels", lambda img, p: ops.levels(img, **p))
        d = adj.LevelsDialog(self, backup, preview)
        self._finish_adjust(d, backup, "Levels")

    def curves(self):
        backup, preview = self._live_adjust("Curves", lambda img, p: ops.curves(img, **p))
        d = adj.CurvesDialog(self, backup, preview)
        self._finish_adjust(d, backup, "Curves")

    def auto_levels(self):
        self._apply_to_target(ops.auto_levels, "Auto Levels")

    def auto_contrast(self):
        self._apply_to_target(ops.auto_contrast, "Auto Contrast")

    def auto_color(self):
        self._apply_to_target(ops.auto_color, "Auto Color")

    def color_balance(self):
        backup, preview = self._live_adjust(
            "Color Balance", lambda img, p: ops.color_balance(img, **p))
        d = adj.ColorBalanceDialog(self, preview)
        self._finish_adjust(d, backup, "Color Balance")

    def brightness_contrast(self):
        backup, preview = self._live_adjust(
            "Brightness/Contrast", lambda img, p: ops.brightness_contrast(img, **p))
        d = adj.BrightnessContrastDialog(self, preview)
        self._finish_adjust(d, backup, "Brightness/Contrast")

    def hue_saturation(self):
        backup, preview = self._live_adjust(
            "Hue/Saturation", lambda img, p: ops.hue_saturation(img, **p))
        d = adj.HueSaturationDialog(self, preview)
        self._finish_adjust(d, backup, "Hue/Saturation")

    def desaturate(self):
        self._apply_to_target(ops.desaturate, "Desaturate")

    def replace_color(self):
        backup, preview = self._live_adjust(
            "Replace Color",
            lambda img, p: ops.replace_color(img, QColor(p["sample"]), p["fuzziness"],
                                             p["hue"], p["saturation"], p["lightness"]))
        d = adj.HueSaturationDialog(self, lambda params: preview(
            None if params is None else dict(params, sample=self.fg_color.name(),
                                             fuzziness=40)))
        d.setWindowTitle("Replace Color")
        self._finish_adjust(d, backup, "Replace Color")

    def selective_color(self):
        backup, preview = self._live_adjust(
            "Selective Color", lambda img, p: ops.selective_color(img, **p))
        d = adj.SelectiveColorDialog(self, preview)
        self._finish_adjust(d, backup, "Selective Color")

    def channel_mixer(self):
        backup, preview = self._live_adjust(
            "Channel Mixer", lambda img, p: ops.channel_mixer(img, **p))
        d = adj.ChannelMixerDialog(self, preview)
        self._finish_adjust(d, backup, "Channel Mixer")

    def gradient_map(self):
        backup, preview = self._live_adjust(
            "Gradient Map", lambda img, p: ops.gradient_map(img, **p))
        d = adj.GradientMapDialog(self, preview, self.fg_color, self.bg_color)
        self._finish_adjust(d, backup, "Gradient Map")

    def invert(self):
        self._apply_to_target(ops.invert, "Invert")

    def equalize(self):
        self._apply_to_target(ops.equalize, "Equalize")

    def threshold(self):
        backup, preview = self._live_adjust(
            "Threshold", lambda img, p: ops.threshold(img, **p))
        d = adj.ThresholdDialog(self, backup, preview)
        self._finish_adjust(d, backup, "Threshold")

    def posterize(self):
        backup, preview = self._live_adjust(
            "Posterize", lambda img, p: ops.posterize(img, **p))
        d = adj.PosterizeDialog(self, preview)
        self._finish_adjust(d, backup, "Posterize")

    def variations(self):
        d = adj.VariationsDialog(self, self.doc.active.image)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.active.image = d.result()
            self.doc.invalidate()
            self.doc.history.record("Variations")
            self.refresh_all()
