"""PhotoChop 7.0 Professional -- the application window.

Layout follows Photoshop 7 exactly: menu bar, then the context-sensitive
options bar, then toolbox / document workspace / palette dock, then the
status bar with the document size, zoom, and the current tool's hint.

The window class itself only wires things together; the commands live in
the mixin modules next to this one, one per menu / concern.
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, QTimer
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout

from ....window_manager import XPWindow
from .. import tools as tool_defs
from ..canvas import Canvas
from ..model import Document
from ..splash import SerialActivationDialog, SplashScreen
from .menus import MenuMixin
from .chrome import ChromeMixin
from .tool_options import ToolOptionsMixin
from .state import StateMixin
from .file_ops import FileMixin
from .edit_ops import EditMixin
from .adjust_ops import AdjustMixin
from .image_ops import ImageMixin
from .layer_ops import LayerMixin
from .selection_ops import SelectionMixin
from .filter_ops import FilterMixin
from .view_ops import ViewMixin
from .type_ops import TypeMixin
from .help_ops import HelpMixin


_activated_this_session = False


class PhotoChopWindow(MenuMixin, ChromeMixin, ToolOptionsMixin, StateMixin, FileMixin, EditMixin, AdjustMixin, ImageMixin, LayerMixin, SelectionMixin, FilterMixin, ViewMixin, TypeMixin, HelpMixin, XPWindow):
    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Adobo PhotoChop", icon_key="photochop",
                         size=QSize(1040, 720))
        global _activated_this_session
        self.node_id = node_id

        if not _activated_this_session:
            SplashScreen(self).exec()
            SerialActivationDialog(self).exec()
            _activated_this_session = True

        self.doc = Document(560, 380, name="Untitled-1")
        self.options = tool_defs.default_options()
        self.current_tool = "marquee_rect"
        self.fg_color = QColor("black")
        self.bg_color = QColor("white")
        self.last_filter: tuple | None = None
        self.screen_mode = "standard"
        self._tool_buttons = []
        self._option_widgets = {}
        self._clipboard: QImage | None = None
        self._type_editor: QLineEdit | None = None
        self._preview_backup: QImage | None = None

        self.canvas = Canvas(self)
        self.canvas.position_changed.connect(self._on_position)
        self.canvas.zoom_changed.connect(lambda _: self._sync_status())
        self.canvas.status_message.connect(self._set_hint)
        self.canvas.document_changed.connect(self.refresh_all)
        self.canvas.color_sampled.connect(self._on_color_changed)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setMenuBar(self._build_menu())
        root.addWidget(self._build_options_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_toolbox())
        body.addWidget(self._build_workspace(), 1)
        body.addWidget(self._build_palette_dock())
        root.addLayout(body, 1)
        root.addWidget(self._build_status_bar())
        self.set_content_layout(root)

        self.select_tool("marquee_rect")
        if node_id:
            self._load_node(node_id)
        QTimer.singleShot(0, self.canvas.fit_on_screen)
        self.refresh_all()
