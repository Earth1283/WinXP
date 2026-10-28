"""Options bar, toolbox, workspace, palette dock and status bar -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget,
)

from .... import theme
from .. import pc_icons, tools as tool_defs
from ..palettes import (
    ActionsPalette, BrushesPalette, ChannelsPalette, CharacterPalette, ColorPalette,
    HistoryPalette, InfoPalette, LayersPalette, NavigatorPalette, PaletteGroup,
    ParagraphPalette, PathsPalette, StylesPalette, SwatchesPalette, ToolPresetsPalette,
)
from .constants import OPTIONS_QSS, TOOLBOX_QSS
from .widgets import ColorSwatchWidget, PaletteScrollArea, Ruler, ToolButton


class ChromeMixin:
    """Options bar, toolbox, workspace, palette dock and status bar."""

    def _build_options_bar(self):
        bar = QWidget()
        bar.setObjectName("optionsBar")
        bar.setStyleSheet(OPTIONS_QSS)
        bar.setFixedHeight(30)
        self._options_layout = QHBoxLayout(bar)
        self._options_layout.setContentsMargins(4, 2, 6, 2)
        self._options_layout.setSpacing(5)
        self._tool_icon_label = QLabel()
        self._tool_icon_label.setFixedSize(24, 24)
        self._options_layout.addWidget(self._tool_icon_label)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #b0b0a0;")
        self._options_layout.addWidget(sep)
        self._options_host = QWidget()
        self._options_host.setObjectName("optHolder")
        self._options_host_layout = QHBoxLayout(self._options_host)
        self._options_host_layout.setContentsMargins(0, 0, 0, 0)
        self._options_host_layout.setSpacing(6)
        self._options_layout.addWidget(self._options_host, 1)
        return bar

    def _build_toolbox(self):
        panel = QWidget()
        panel.setFixedWidth(62)
        panel.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; "
                            f"border-right: 1px solid #9a9a8a; {TOOLBOX_QSS}")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(3, 3, 3, 4)
        layout.setSpacing(2)

        grid = QGridLayout()
        grid.setSpacing(1)
        for i, group in enumerate(tool_defs.TOOL_GROUPS):
            btn = ToolButton(self, group, i)
            self._tool_buttons.append(btn)
            grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addSpacing(4)

        self.swatch_widget = ColorSwatchWidget(self)
        layout.addWidget(self.swatch_widget, 0, Qt.AlignmentFlag.AlignHCenter)

        mask_row = QHBoxLayout()
        mask_row.setSpacing(1)
        self.quick_mask_buttons = []
        for i, name in enumerate(("quick_mask_off", "quick_mask_on")):
            b = QToolButton()
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setIcon(pc_icons.icon(name, 18))
            b.setIconSize(QSize(18, 18))
            b.setFixedSize(24, 22)
            b.setToolTip("Edit in Standard Mode (Q)" if i == 0 else "Edit in Quick Mask Mode (Q)")
            b.clicked.connect(lambda _, want=bool(i): self.set_quick_mask(want))
            self.quick_mask_buttons.append(b)
            mask_row.addWidget(b)
        layout.addLayout(mask_row)

        screen_row = QHBoxLayout()
        screen_row.setSpacing(1)
        self.screen_buttons = []
        for i, name in enumerate(("screen_standard", "screen_full_menu", "screen_full")):
            b = QToolButton()
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setIcon(pc_icons.icon(name, 16))
            b.setIconSize(QSize(16, 16))
            b.setFixedSize(17, 20)
            b.clicked.connect(lambda _, idx=i: self.set_screen_mode(idx))
            self.screen_buttons.append(b)
            screen_row.addWidget(b)
        layout.addLayout(screen_row)

        ir = QToolButton()
        ir.setIcon(pc_icons.icon("imageready", 20))
        ir.setIconSize(QSize(20, 20))
        ir.setFixedSize(28, 26)
        ir.setToolTip("Jump to ImageReady")
        ir.clicked.connect(self.jump_to_imageready)
        layout.addWidget(ir, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        return panel

    def _build_workspace(self):
        wrap = QWidget()
        wrap.setStyleSheet("background: #6e6e6e;")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.doc_title = QLabel()
        self.doc_title.setFixedHeight(18)
        self.doc_title.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #0a58f2, stop:1 #0058e6); color: white; font-size: 11px;"
            "padding-left: 6px;")
        layout.addWidget(self.doc_title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self.corner = QWidget()
        self.corner.setFixedSize(18, 18)
        self.corner.setStyleSheet("background: #ece9d8; border: 1px solid #9a9a8a;")
        self.ruler_h = Ruler(self, horizontal=True)
        self.ruler_v = Ruler(self, horizontal=False)
        grid.addWidget(self.corner, 0, 0)
        grid.addWidget(self.ruler_h, 0, 1)
        grid.addWidget(self.ruler_v, 1, 0)
        grid.addWidget(self.canvas, 1, 1)
        layout.addLayout(grid, 1)
        return wrap

    def _build_palette_dock(self):
        dock = QWidget()
        dock.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; "
                           f"border-left: 1px solid #9a9a8a;")
        layout = QVBoxLayout(dock)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)

        self.navigator = NavigatorPalette(self)
        self.info = InfoPalette(self)
        self.color_palette = ColorPalette(self)
        self.swatches = SwatchesPalette(self)
        self.styles = StylesPalette(self)
        self.history = HistoryPalette(self)
        self.actions_palette = ActionsPalette(self)
        self.tool_presets = ToolPresetsPalette(self)
        self.layers = LayersPalette(self)
        self.channels = ChannelsPalette(self)
        self.paths = PathsPalette(self)
        self.brushes_palette = BrushesPalette(self)
        self.character = CharacterPalette(self)
        self.paragraph = ParagraphPalette(self)

        self.groups = [
            PaletteGroup([("Navigator", self.navigator), ("Info", self.info)]),
            PaletteGroup([("Color", self.color_palette), ("Swatches", self.swatches),
                          ("Styles", self.styles), ("Brushes", self.brushes_palette),
                          ("Character", self.character), ("Paragraph", self.paragraph)]),
            PaletteGroup([("History", self.history), ("Actions", self.actions_palette),
                          ("Tool Presets", self.tool_presets)]),
            PaletteGroup([("Layers", self.layers), ("Channels", self.channels),
                          ("Paths", self.paths)]),
        ]
        for group, stretch in zip(self.groups, (0, 0, 3, 4)):
            layout.addWidget(group, stretch)
        self.groups[0].setFixedHeight(128)
        self.groups[1].setFixedHeight(130)
        dock.setMinimumWidth(max(group.sizeHint().width() for group in self.groups) + 6)

        scroll = PaletteScrollArea()
        scroll.setObjectName("paletteScroll")
        scroll.setFixedWidth(226)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(dock)
        bar = scroll.horizontalScrollBar()
        bar.setFixedHeight(9)
        bar.setSingleStep(24)
        bar.setStyleSheet("""
            QScrollBar:horizontal {
                height: 9px; margin: 0; border: 1px solid #9a9a8a;
                background: #d4d0c8;
            }
            QScrollBar::handle:horizontal {
                min-width: 18px; background: #ece9d8;
                border: 1px solid #808080;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0; border: none; background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: #d4d0c8;
            }
        """)
        self.palette_scroll = scroll
        return scroll

    def _build_status_bar(self):
        bar = QWidget()
        bar.setFixedHeight(20)
        bar.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; border-top: 1px solid #9a9a8a;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(6)
        self.status_zoom = QLabel("100%")
        self.status_zoom.setFixedWidth(56)
        self.status_zoom.setStyleSheet("background: white; border: 1px solid #9a9a8a;"
                                       "font-size: 11px; padding-left: 3px;")
        self.status_doc = QLabel("Doc: 623K/623K")
        self.status_doc.setFixedWidth(150)
        self.status_hint = QLabel("")
        for w in (self.status_doc, self.status_hint):
            w.setStyleSheet("background: transparent; font-size: 11px;")
        row.addWidget(self.status_zoom)
        row.addWidget(self.status_doc)
        row.addWidget(self.status_hint, 1)
        return bar
