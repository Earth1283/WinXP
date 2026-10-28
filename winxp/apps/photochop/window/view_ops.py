"""View and Window menu commands -- mixin for PhotoChopWindow."""
from __future__ import annotations

from .. import dialogs as dlg


class ViewMixin:
    """View and Window menu commands."""

    def canvas_zoom_in(self):
        self.canvas.zoom_in()

    def canvas_zoom_out(self):
        self.canvas.zoom_out()

    def toggle_extras(self, checked=None):
        self.canvas.show_extras = (not self.canvas.show_extras
                                   if checked is None else bool(checked))
        self.canvas.update()

    def toggle_selection_edges(self, checked=None):
        self.canvas.show_selection_edges = (
            not self.canvas.show_selection_edges if checked is None else bool(checked))
        self.canvas.update()

    def toggle_grid(self, checked=None):
        self.canvas.show_grid = (not self.canvas.show_grid
                                 if checked is None else bool(checked))
        self.canvas.update()

    def toggle_guides(self, checked=None):
        self.canvas.show_guides = (not self.canvas.show_guides
                                   if checked is None else bool(checked))
        self.canvas.update()

    def toggle_slices(self, checked=None):
        self.canvas.show_slices = (not self.canvas.show_slices
                                   if checked is None else bool(checked))
        self.canvas.update()

    def toggle_annotations(self, checked=None):
        self.canvas.show_annotations = (
            not self.canvas.show_annotations if checked is None else bool(checked))
        self.canvas.update()

    def toggle_snap(self, checked=None):
        self.canvas.snap = not self.canvas.snap if checked is None else bool(checked)

    def toggle_guide_lock(self, checked=None):
        self.canvas.guides_locked = (
            not self.canvas.guides_locked if checked is None else bool(checked))
        self.canvas.update()

    def toggle_rulers(self):
        show = not self.ruler_h.isVisible()
        self.ruler_h.setVisible(show)
        self.ruler_v.setVisible(show)
        self.corner.setVisible(show)

    def clear_guides(self):
        self.doc.guides_h.clear()
        self.doc.guides_v.clear()
        self.canvas.update()

    def new_guide(self):
        value = dlg.ValueDialog.get(self, "New Guide", "Position:", 100, 0, 8000, " pixels")
        if value is not None:
            self.add_guide(True, value)

    def add_guide(self, horizontal, position):
        if self.canvas.guides_locked:
            self._set_hint("Could not create guide: guides are locked.")
            return
        (self.doc.guides_h if horizontal else self.doc.guides_v).append(int(position))
        self.canvas.update()

    def set_screen_mode(self, index):
        self.screen_mode = ["standard", "full_menu", "full"][index]
        for i, btn in enumerate(self.screen_buttons):
            btn.setChecked(i == index)
        if self.screen_mode == "standard":
            self.doc_title.show()
        else:
            self.doc_title.hide()
        if self.screen_mode == "full":
            self._set_hint("Press F to cycle back to Standard Screen Mode.")

    def toggle_palette(self, name):
        for group in self.groups:
            if group.show_palette(name):
                return
        if name == "Tools":
            self._set_hint("The toolbox is not going anywhere.")
        elif name == "File Browser":
            self.open_file_browser()
