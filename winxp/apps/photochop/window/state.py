"""Refreshing UI state, foreground/background colours and keyboard handling -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ....color_dialog import XPColorDialog
from .. import dialogs as dlg, tools as tool_defs


class StateMixin:
    """Refreshing UI state, foreground/background colours and keyboard handling."""

    def refresh_all(self):
        self.doc.invalidate()
        for depth, action in self._bit_depth_actions.items():
            action.setChecked(depth == self.doc.bits_per_channel)
        self.canvas.update()
        self.layers.refresh()
        self.channels.refresh()
        self.paths.refresh()
        self.history.refresh()
        self.navigator.refresh()
        self.color_palette.refresh()
        self.brushes_palette.refresh()
        self.info.set_dimensions(self.doc.width, self.doc.height)
        self._sync_status()
        self._sync_title()

    def refresh_canvas(self):
        self.canvas.update()
        self.navigator.refresh()

    def _sync_title(self):
        zoom = self.canvas.zoom * 100
        layer = self.doc.active
        mode = "RGB" if self.doc.mode == "RGB Color" else self.doc.mode
        self.doc_title.setText(f"  {self.doc.name} @ {zoom:.1f}% ({layer.name}, {mode})")
        self.setWindowTitle(f"{self.doc.name} - Adobo PhotoChop")

    def _sync_status(self):
        zoom = self.canvas.zoom * 100
        self.status_zoom.setText(f"{zoom:.2f}%".rstrip("0").rstrip(".") + "%"
                                 if zoom % 1 else f"{zoom:.0f}%")
        flat = self.doc.width * self.doc.height * 3 / 1024
        layered = self.doc.memory_size() / 1024
        self.status_doc.setText(f"Doc: {dlg._size_text(flat)}/{dlg._size_text(layered)}")
        self.navigator.refresh()
        self.ruler_h.update()
        self.ruler_v.update()
        self._sync_title()

    def _set_hint(self, text):
        self.status_hint.setText(text)
        self.info.set_hint(text)

    def _on_position(self, pos):
        if pos is None:
            self.info.set_pixel(None, None)
        else:
            self.info.set_pixel(pos, self.doc.composite().pixelColor(pos))
        self.ruler_h.cursor_pos = pos
        self.ruler_v.cursor_pos = pos
        self.ruler_h.update()
        self.ruler_v.update()

    def _on_color_changed(self):
        self.swatch_widget.update()
        self.color_palette.refresh()

    def update_samplers(self, points):
        self.info.set_samplers(points)

    def update_measure(self, line):
        length = line.length()
        angle = line.angle()
        self._set_hint(f"A: {angle:.1f}°   D: {length:.2f}   "
                       f"W: {abs(line.dx()):.0f}   H: {abs(line.dy()):.0f}")

    # ========================================================== colours ====

    def set_fg_color(self, colour):
        self.fg_color = QColor(colour)
        self._on_color_changed()

    def set_bg_color(self, colour):
        self.bg_color = QColor(colour)
        self._on_color_changed()

    def pick_fg_color(self):
        c = XPColorDialog.get_color(self, self.fg_color)
        if c:
            self.set_fg_color(c)

    def pick_bg_color(self):
        c = XPColorDialog.get_color(self, self.bg_color)
        if c:
            self.set_bg_color(c)

    def swap_colors(self):
        self.fg_color, self.bg_color = self.bg_color, self.fg_color
        self._on_color_changed()

    def reset_colors(self):
        self.fg_color = QColor("black")
        self.bg_color = QColor("white")
        self._on_color_changed()

    # ========================================================= keyboard ====

    def keyPressEvent(self, ev):
        key = ev.text().upper()
        mods = ev.modifiers()
        if not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            if key == "D":
                self.reset_colors()
                return
            if key == "X":
                self.swap_colors()
                return
            if key == "Q":
                self.set_quick_mask(not self.doc.quick_mask)
                return
            if key == "F":
                self.set_screen_mode((["standard", "full_menu", "full"].index(
                    self.screen_mode) + 1) % 3)
                return
            if key in tool_defs.SHORTCUT_GROUPS:
                group = tool_defs.SHORTCUT_GROUPS[key]
                if self.current_tool in group:
                    idx = (group.index(self.current_tool) + 1) % len(group)
                    self.select_tool(group[idx])
                else:
                    self.select_tool(group[0])
                return
            if ev.key() == Qt.Key.Key_BracketLeft:
                self._nudge_brush(-2)
                return
            if ev.key() == Qt.Key.Key_BracketRight:
                self._nudge_brush(2)
                return
        super().keyPressEvent(ev)

    def _nudge_brush(self, delta):
        brush = dict(self.options.get("brush", {}))
        brush["size"] = max(1, min(300, brush.get("size", 13) + delta))
        self.options["brush"] = brush
        self.brushes_palette.refresh()
        self._set_hint(f"Brush diameter: {brush['size']} px")
