"""Layer menu commands -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QDialog

from ....xp_dialog import XPMessageBox
from .. import dialogs as dlg, imageops as ops
from ..model import Layer, default_style


class LayerMixin:
    """Layer menu commands."""

    def new_layer(self):
        layer = Layer(f"Layer {len(self.doc.layers)}", self.doc.blank_image())
        self.doc.add_layer(layer)
        self.doc.history.record("New Layer")
        self.refresh_all()

    def new_layer_dialog(self):
        d = dlg.NewLayerDialog(self, f"Layer {len(self.doc.layers)}")
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        spec = d.result()
        layer = Layer(spec["name"], self.doc.blank_image(),
                      opacity=spec["opacity"] / 100.0, blend=spec["mode"])
        layer.clipping = spec["clipping"]
        self.doc.add_layer(layer)
        self.doc.history.record("New Layer")
        self.refresh_all()

    def new_layer_set(self):
        layer = Layer(f"Set {len(self.doc.layers)}", self.doc.blank_image(), kind="group")
        self.doc.add_layer(layer)
        self.doc.history.record("New Layer Set")
        self.refresh_all()

    def layer_from_background(self):
        layer = self.doc.layers[0]
        if layer.name != "Background":
            return
        layer.name = "Layer 0"
        layer.locked_all = False
        layer.locked_transparency = False
        self.doc.history.record("Layer From Background")
        self.refresh_all()

    def layer_via_copy(self):
        self.copy()
        if self._clipboard is None:
            return
        layer = Layer(f"Layer {len(self.doc.layers)}", self.doc.blank_image())
        pos = self.doc.selection.bounds().topLeft() if self.doc.has_selection() else QPoint(0, 0)
        p = QPainter(layer.image)
        p.drawImage(pos, self._clipboard)
        p.end()
        self.doc.add_layer(layer)
        self.doc.history.record("Layer via Copy")
        self.refresh_all()

    def layer_via_cut(self):
        self.copy()
        source = self.doc.active
        pos = self.doc.selection.bounds().topLeft() if self.doc.has_selection() else QPoint(0, 0)
        self.clear_selection_pixels()
        layer = Layer(f"Layer {len(self.doc.layers)}", self.doc.blank_image())
        if self._clipboard is not None:
            p = QPainter(layer.image)
            p.drawImage(pos, self._clipboard)
            p.end()
        self.doc.add_layer(layer)
        self.doc.history.record("Layer via Cut")
        self.refresh_all()

    def duplicate_layer(self):
        copy = self.doc.active.copy()
        copy.name += " copy"
        copy.locked_all = False
        self.doc.add_layer(copy)
        self.doc.history.record("Duplicate Layer")
        self.refresh_all()

    def delete_layer(self):
        if not self.doc.remove_active():
            XPMessageBox.warning(self, "PhotoChop",
                                 "Could not delete the layer because it is the only one.")
            return
        self.doc.history.record("Delete Layer")
        self.refresh_all()

    def layer_properties(self):
        d = dlg.LayerPropertiesDialog(self, self.doc.active.name)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.active.name = d.result()
            self.refresh_all()

    def layer_style(self, effect=None):
        from .style_dialog import LayerStyleDialog
        layer = self.doc.active
        d = LayerStyleDialog(self, layer, effect)
        if d.exec() == QDialog.DialogCode.Accepted:
            layer.style = d.result()
            self.doc.invalidate()
            self.doc.history.record("Layer Style")
        self.refresh_all()

    def apply_preset_style(self, style):
        layer = self.doc.active
        merged = default_style()
        for key, cfg in style.items():
            merged[key] = dict(cfg)
        layer.style = merged
        self.doc.invalidate()
        self.doc.history.record("Layer Style")
        self.refresh_all()

    def copy_layer_style(self):
        self._style_clipboard = {k: dict(v) for k, v in self.doc.active.style.items()}
        self._set_hint("Layer style copied.")

    def paste_layer_style(self):
        style = getattr(self, "_style_clipboard", None)
        if style:
            self.doc.active.style = {k: dict(v) for k, v in style.items()}
            self.doc.invalidate()
            self.doc.history.record("Paste Layer Style")
            self.refresh_all()

    def clear_layer_style(self):
        self.doc.active.style = default_style()
        self.doc.invalidate()
        self.doc.history.record("Clear Layer Style")
        self.refresh_all()

    def hide_effects(self):
        for cfg in self.doc.active.style.values():
            cfg["enabled"] = False
        self.doc.invalidate()
        self.refresh_all()

    def style_to_layers(self):
        layer = self.doc.active
        if not layer.has_style():
            return
        rendered = self.doc.rendered_layer(layer)
        new_layer = Layer(layer.name + "'s Effects", rendered)
        layer.style = default_style()
        self.doc.add_layer(new_layer)
        self.doc.history.record("Create Layers")
        self.refresh_all()

    def new_fill_layer(self, kind):
        layer = Layer(kind.rstrip("."), self.doc.blank_image())
        p = QPainter(layer.image)
        if kind.startswith("Gradient"):
            from PyQt6.QtGui import QLinearGradient
            grad = QLinearGradient(0, 0, 0, self.doc.height)
            grad.setColorAt(0, self.fg_color)
            grad.setColorAt(1, self.bg_color)
            p.fillRect(layer.image.rect(), grad)
        elif kind.startswith("Pattern"):
            from .layer_styles import _pattern_tile
            p.drawTiledPixmap(layer.image.rect(),
                              QPixmap.fromImage(_pattern_tile("Checkerboard")))
        else:
            p.fillRect(layer.image.rect(), self.fg_color)
        p.end()
        if self.doc.has_selection():
            layer.mask = self.doc.selection.mask.copy()
        self.doc.add_layer(layer)
        self.doc.history.record("New Fill Layer")
        self.refresh_all()

    def new_adjustment_layer(self, kind="Levels"):
        kind = kind.rstrip(".") if isinstance(kind, str) else "Levels"
        params = {"Levels": dict(in_black=0, gamma=1.0, in_white=255),
                  "Curves": dict(points=[(0, 0), (255, 255)]),
                  "Brightness/Contrast": dict(brightness=0, contrast=0),
                  "Hue/Saturation": dict(hue=0, saturation=0, lightness=0),
                  "Color Balance": dict(),
                  "Threshold": dict(level=128),
                  "Posterize": dict(levels=4)}.get(kind, {})
        layer = Layer(f"{kind} {len(self.doc.layers)}", self.doc.blank_image(),
                      kind="adjustment")
        layer.adjustment = {"kind": kind, "params": params}
        if self.doc.has_selection():
            layer.mask = self.doc.selection.mask.copy()
        self.doc.add_layer(layer)
        self.doc.history.record("New Adjustment Layer")
        self.refresh_all()

    def add_layer_mask(self, kind="reveal"):
        layer = self.doc.active
        mask = QImage(self.doc.width, self.doc.height,
                      QImage.Format.Format_ARGB32_Premultiplied)
        if kind == "hide":
            mask.fill(Qt.GlobalColor.black)
        elif kind in ("selection", "hide-selection") and self.doc.has_selection():
            mask = self.doc.selection.mask.copy()
            if kind == "hide-selection":
                mask = ops.invert(mask)
        else:
            mask.fill(Qt.GlobalColor.white)
        layer.mask = mask
        layer.mask_enabled = True
        layer.mask_active = True
        self.doc.invalidate()
        self.doc.history.record("Add Layer Mask")
        self.refresh_all()

    def remove_layer_mask(self, apply_it):
        layer = self.doc.active
        if layer.mask is None:
            return
        if apply_it:
            from .model import alpha_multiply
            layer.image = alpha_multiply(layer.image, layer.mask)
        layer.mask = None
        layer.mask_active = False
        if self.doc.viewing_mask:
            self.doc.viewing_mask = False
        self.doc.invalidate()
        self.doc.history.record("Remove Layer Mask")
        self.refresh_all()

    def toggle_layer_mask(self):
        layer = self.doc.active
        layer.mask_enabled = not layer.mask_enabled
        self.doc.invalidate()
        self.refresh_all()

    def set_mask_target(self, layer, active: bool):
        """Click a layer row's thumbnail: choose whether tools paint the
        layer's pixels or its mask."""
        self.doc.active_index = self.doc.layers.index(layer)
        layer.mask_active = active and layer.mask is not None
        if not layer.mask_active:
            self.doc.viewing_mask = False
        self.refresh_all()

    def toggle_mask_view(self, layer):
        """Alt-click a mask thumbnail: show the mask alone on the canvas."""
        self.doc.active_index = self.doc.layers.index(layer)
        layer.mask_active = True
        self.doc.viewing_mask = not self.doc.viewing_mask
        self.refresh_all()

    def toggle_mask_enabled(self, layer):
        """Shift-click a mask thumbnail: disable/enable it without selecting it."""
        if layer.mask is None:
            return
        layer.mask_enabled = not layer.mask_enabled
        self.doc.invalidate()
        self.refresh_all()

    def load_mask_as_selection(self, layer, mode="replace"):
        """Ctrl-click a mask thumbnail: the mask's white areas become the
        selection (Ctrl+Shift adds, Ctrl+Alt subtracts, both intersects)."""
        if layer.mask is None:
            return
        sel = self.doc.ensure_selection()
        sel.set_mask(layer.mask.copy(), mode)
        self.doc.history.record("Load Mask as Selection")
        self.refresh_all()

    def move_or_copy_mask(self, src_layer, dst_layer, copy: bool):
        """Drag a mask thumbnail onto another layer's row."""
        if src_layer is dst_layer or src_layer.mask is None:
            return
        dst_layer.mask = src_layer.mask.copy()
        dst_layer.mask_enabled = True
        if not copy:
            src_layer.mask = None
            src_layer.mask_active = False
        self.doc.invalidate()
        self.doc.history.record("Copy Layer Mask" if copy else "Move Layer Mask")
        self.refresh_all()

    def group_with_previous(self):
        if self.doc.active_index > 0:
            self.doc.active.clipping = True
            self.doc.invalidate()
            self.doc.history.record("Group with Previous")
            self.refresh_all()

    def ungroup(self):
        self.doc.active.clipping = False
        self.doc.invalidate()
        self.doc.history.record("Ungroup")
        self.refresh_all()

    def arrange(self, where):
        i = self.doc.active_index
        layers = self.doc.layers
        if where == "front":
            layers.append(layers.pop(i))
            self.doc.active_index = len(layers) - 1
        elif where == "back":
            layers.insert(0, layers.pop(i))
            self.doc.active_index = 0
        elif where == "forward" and i < len(layers) - 1:
            layers[i], layers[i + 1] = layers[i + 1], layers[i]
            self.doc.active_index = i + 1
        elif where == "backward" and i > 0:
            layers[i], layers[i - 1] = layers[i - 1], layers[i]
            self.doc.active_index = i - 1
        self.doc.invalidate()
        self.doc.history.record("Arrange")
        self.refresh_all()

    def merge_down(self):
        if not self.doc.merge_down():
            XPMessageBox.warning(self, "PhotoChop",
                                 "There is no layer below this one to merge into.")
            return
        self.doc.history.record("Merge Down")
        self.refresh_all()

    def merge_visible(self):
        flat = self.doc.flattened(white_background=False)
        keep = [l for l in self.doc.layers if not l.visible]
        merged = Layer("Merged", flat)
        self.doc.layers = keep + [merged]
        self.doc.active_index = len(self.doc.layers) - 1
        self.doc.invalidate()
        self.doc.history.record("Merge Visible")
        self.refresh_all()

    def flatten_image(self):
        hidden = [l for l in self.doc.layers if not l.visible]
        if hidden and XPMessageBox.confirm(
                self, "PhotoChop", "Discard hidden layers?") is False:
            return
        self.doc.flatten()
        self.doc.history.record("Flatten Image")
        self.refresh_all()

    def defringe(self):
        layer = self.doc.active
        layer.image = ops.median(layer.image, 1)
        self.doc.invalidate()
        self.doc.history.record("Defringe")
        self.refresh_all()
