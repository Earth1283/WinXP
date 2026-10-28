"""Image menu commands -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog

from ....xp_dialog import XPMessageBox
from .. import dialogs as dlg, imageops as ops
from .helpers import _content_bounds


class ImageMixin:
    """Image menu commands."""

    def apply_image(self):
        XPMessageBox.information(self, "Apply Image",
                                 "Apply Image needs a second document, and there "
                                 "has only ever been one.")

    def duplicate_document(self):
        XPMessageBox.information(
            self, "Duplicate Image",
            f"{self.doc.name} copy has been created in a window PhotoChop "
            f"forgot to open.")

    def image_size(self):
        d = dlg.ImageSizeDialog(self, self.doc.width, self.doc.height, self.doc.resolution)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        spec = d.result()
        self.doc.resolution = spec["resolution"]
        if spec["resample"]:
            self.doc.resize_image(spec["width"], spec["height"], spec["smooth"])
        self.doc.history.record("Image Size")
        self.canvas.fit_on_screen()
        self.refresh_all()

    def canvas_size(self):
        d = dlg.CanvasSizeDialog(self, self.doc.width, self.doc.height)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        spec = d.result()
        self.doc.resize_canvas(spec["width"], spec["height"], spec["anchor"])
        self.doc.history.record("Canvas Size")
        self.canvas.fit_on_screen()
        self.refresh_all()

    def rotate_canvas(self, degrees):
        self.doc.transform_all(lambda img: ops.rotate(img, degrees))
        self.doc.history.record("Rotate Canvas")
        self.canvas.fit_on_screen()
        self.refresh_all()

    def rotate_arbitrary(self):
        d = dlg.RotateCanvasDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.rotate_canvas(d.result())

    def flip_canvas(self, horizontal):
        self.doc.transform_all(lambda img: ops.flip(img, horizontal))
        self.doc.history.record("Flip Canvas")
        self.refresh_all()

    def crop_to_selection(self):
        if not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop", "There is no selection to crop to.")
            return
        rect = self.doc.selection.bounds()
        for layer in self.doc.layers:
            layer.image = layer.image.copy(rect)
            if layer.mask is not None:
                layer.mask = layer.mask.copy(rect)
        self.doc.width, self.doc.height = rect.width(), rect.height()
        self.doc.selection = None
        self.doc.invalidate()
        self.doc.history.record("Crop")
        self.canvas.fit_on_screen()
        self.refresh_all()

    def trim(self):
        img = self.doc.flattened(white_background=False)
        rect = _content_bounds(img)
        if rect.isEmpty():
            return
        for layer in self.doc.layers:
            layer.image = layer.image.copy(rect)
        self.doc.width, self.doc.height = rect.width(), rect.height()
        self.doc.invalidate()
        self.doc.history.record("Trim")
        self.canvas.fit_on_screen()
        self.refresh_all()

    def reveal_all(self):
        self.doc.resize_canvas(self.doc.width, self.doc.height, "center")
        self.refresh_all()

    def show_histogram(self):
        from .misc_dialogs import HistogramDialog
        HistogramDialog(self, self.doc.flattened()).exec()

    def set_bit_depth(self, depth):
        self.doc.bits_per_channel = depth
        self._set_hint(f"{depth} bits per channel")
        self._sync_title()

    def set_mode(self, name):
        self.doc.mode = name
        if name == "Grayscale":
            self._apply_to_target(ops.desaturate, "Grayscale", force_image=True)
        elif name == "Bitmap":
            self._apply_to_target(lambda img: ops.threshold(img, 128), "Bitmap", force_image=True)
        elif name in ("CMYK Color", "Lab Color", "Duotone", "Multichannel",
                      "Indexed Color"):
            XPMessageBox.information(
                self, "PhotoChop",
                f"Converting to {name} would require a colour engine.\n"
                f"PhotoChop has instead written {name} on the title bar.")
        self._sync_title()
