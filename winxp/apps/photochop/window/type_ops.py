"""Type tool editing -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QLineEdit

from .. import imageops as ops
from ..model import Layer


class TypeMixin:
    """Type tool editing."""

    def begin_type(self, pos, vertical=False, mask=False):
        if self._type_editor is not None:
            self.commit_type()
        editor = QLineEdit(self.canvas)
        editor.setFrame(False)
        view = self.canvas.view_pos(pos)
        font = self.options.get("font", {})
        editor.move(int(view.x()), int(view.y() - font.get("size", 24) * self.canvas.zoom))
        editor.resize(260, int(font.get("size", 24) * self.canvas.zoom * 1.5) + 6)
        editor.setStyleSheet("background: rgba(255,255,255,40); border: 1px dotted #333;")
        editor.returnPressed.connect(self.commit_type)
        editor.show()
        editor.setFocus()
        self._type_editor = editor
        self._type_pos = pos
        self._type_vertical = vertical
        self._type_mask = mask
        self._apply_type_font()
        self._set_hint("Type, then press Enter to commit or Esc to cancel.")

    def _apply_type_font(self):
        if self._type_editor is None:
            return
        spec = self.options.get("font", {})
        font = QFont(spec.get("family", "Tahoma"),
                     max(1, int(spec.get("size", 24) * self.canvas.zoom)))
        style = spec.get("style", "Regular")
        font.setBold("Bold" in style)
        font.setItalic("Italic" in style)
        self._type_editor.setFont(font)

    def commit_type(self):
        if self._type_editor is None:
            return
        text = self._type_editor.text()
        self._type_editor.deleteLater()
        self._type_editor = None
        if not text:
            return
        spec = self.options.get("font", {})
        font = QFont(spec.get("family", "Tahoma"), int(spec.get("size", 24)))
        style = spec.get("style", "Regular")
        font.setBold("Bold" in style)
        font.setItalic("Italic" in style)
        rendered = self.doc.blank_image()
        p = QPainter(rendered)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing,
                        spec.get("antialias", "Crisp") != "None")
        p.setFont(font)
        p.setPen(QColor(spec.get("color", "#000000")))
        if self._type_vertical:
            x, y = self._type_pos.x(), self._type_pos.y()
            metrics = p.fontMetrics()
            for ch in text:
                p.drawText(QPointF(x, y), ch)
                y += metrics.height()
        else:
            p.drawText(self._type_pos, text)
        p.end()
        if self._type_mask:
            from .model import Selection
            grey = ops.desaturate(rendered)
            sel = self.doc.ensure_selection()
            buf, w, h = ops.to_buf(rendered)
            alpha = ops.plane(buf, ops.A)
            mask_buf = bytearray(w * h * 4)
            mask_buf[0::4] = alpha
            mask_buf[1::4] = alpha
            mask_buf[2::4] = alpha
            mask_buf[3::4] = b"\xff" * (w * h)
            sel.set_mask(ops.from_buf(mask_buf, w, h), "replace")
            self.doc.history.record("Type Mask")
        else:
            layer = Layer(text[:24], rendered, kind="type")
            layer.text = dict(spec, string=text)
            self.doc.add_layer(layer)
            self.doc.history.record("Type Layer")
        self.refresh_all()
