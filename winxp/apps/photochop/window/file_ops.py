"""File menu commands -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QDialog

from .... import image_codec, vfs as vfs_mod
from ....vfs_dialog import VfsFileDialog
from ....xp_dialog import XPMessageBox
from .. import dialogs as dlg
from ..model import Document, Layer


class FileMixin:
    """File menu commands."""

    def new_file(self):
        d = dlg.NewDocumentDialog(self, f"Untitled-{1}", self.doc.width, self.doc.height)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        spec = d.result()
        background = spec["background"]
        if background == "bg":
            background = self.bg_color.name()
        self.doc = Document(spec["width"], spec["height"], spec["resolution"],
                            spec["mode"], background, spec["name"])
        self.node_id = None
        self.canvas.fit_on_screen()
        self.refresh_all()

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.IMAGE,), title="Open")
        if node_id:
            self._load_node(node_id)

    def open_file_browser(self):
        from .filebrowser import FileBrowserDialog
        node_id = FileBrowserDialog.pick(self)
        if node_id:
            self._load_node(node_id)

    def _load_node(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        pixmap = image_codec.from_bytes(vfs_mod.vfs.read_blob(node_id))
        img = pixmap.toImage()
        if img.isNull():
            return
        img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.doc = Document(img.width(), img.height(), name=node.name)
        self.doc.layers[0].image = img
        self.doc.invalidate()
        self.node_id = node_id
        self.canvas.fit_on_screen()
        self.refresh_all()

    def place_image(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.IMAGE,), title="Place")
        if not node_id:
            return
        img = image_codec.from_bytes(vfs_mod.vfs.read_blob(node_id)).toImage()
        if img.isNull():
            return
        layer = Layer(vfs_mod.vfs.get(node_id).name, self.doc.blank_image())
        scaled = img.scaled(self.doc.width, self.doc.height,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        p = QPainter(layer.image)
        p.drawImage((self.doc.width - scaled.width()) // 2,
                    (self.doc.height - scaled.height()) // 2, scaled)
        p.end()
        self.doc.add_layer(layer)
        self.doc.history.record("Place")
        self.refresh_all()

    def save_file(self):
        if self.node_id:
            vfs_mod.vfs.write_blob(self.node_id,
                                   image_codec.to_bytes(QPixmap.fromImage(self.doc.flattened())))
            self.doc.name = vfs_mod.vfs.get(self.node_id).name
            self._sync_title()
            self._set_hint("Saved. The layers were flattened, because of course they were.")
        else:
            self.save_file_as()

    def save_file_as(self):
        folder_id, name = VfsFileDialog.get_save_target(
            self, kinds=(vfs_mod.IMAGE,), title="Save As",
            default_name=self.doc.name.split(".")[0] + ".png")
        if not folder_id:
            return
        existing = next((c for c in vfs_mod.vfs.children_of(folder_id)
                         if c.name == name and c.kind == vfs_mod.IMAGE), None)
        data = image_codec.to_bytes(QPixmap.fromImage(self.doc.flattened()))
        if existing:
            vfs_mod.vfs.write_blob(existing.id, data)
            self.node_id = existing.id
        else:
            self.node_id = vfs_mod.vfs.create_image_file(folder_id, name, data).id
        self.doc.name = name
        self._sync_title()

    def save_for_web(self):
        from .misc_dialogs import SaveForWebDialog
        SaveForWebDialog(self, self.doc.flattened()).exec()

    def revert(self):
        if self.node_id:
            self._load_node(self.node_id)
        else:
            XPMessageBox.warning(self, "PhotoChop", "This document has never been saved.")

    def print_preview(self):
        from .misc_dialogs import PrintDialog
        PrintDialog(self, self.doc.flattened()).exec()

    def page_setup(self):
        from .misc_dialogs import PageSetupDialog
        PageSetupDialog(self).exec()

    def print_one(self):
        XPMessageBox.critical(
            self, "PhotoChop",
            "Could not print because no printer is installed.\n\n"
            "The document has been printed to a printer that is not installed.")

    def file_info(self):
        from .misc_dialogs import FileInfoDialog
        FileInfoDialog(self, self.doc).exec()

    def jump_to_imageready(self):
        XPMessageBox.information(
            self, "PhotoChop",
            "PhotoChop cannot start ImageReady because ImageReady was never written.\n\n"
            "It is, however, definitely installed.")

    def batch_dialog(self):
        XPMessageBox.information(
            self, "Batch",
            "Batch processing 0 of 0 files.\n\nBatch complete.")

    def fit_image(self):
        value = dlg.ValueDialog.get(self, "Fit Image", "Constrain Width:",
                                    self.doc.width, 1, 8000, " pixels")
        if value:
            ratio = self.doc.height / self.doc.width
            self.doc.resize_image(value, max(1, int(value * ratio)))
            self.doc.history.record("Fit Image")
            self.refresh_all()
