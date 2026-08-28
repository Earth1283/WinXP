"""PhotoChop 7.0 Professional -- the application window.

Layout follows Photoshop 7 exactly: menu bar, then the context-sensitive
options bar, then toolbox / document workspace / palette dock, then the
status bar with the document size, zoom, and the current tool's hint.
"""
from __future__ import annotations

import math
import os

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction, QActionGroup, QColor, QFont, QIcon, QImage, QKeySequence, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QMenuBar, QPushButton, QSizePolicy, QSpinBox, QToolButton, QVBoxLayout,
    QWidget,
)

from ... import image_codec, theme, vfs as vfs_mod
from ...vfs_dialog import VfsFileDialog
from ...window_manager import XPWindow
from ...xp_dialog import XPMessageBox
from ...color_dialog import XPColorDialog
from . import adjust_dialogs as adj, brushes, dialogs as dlg, filters as filt
from . import imageops as ops, pc_icons, tools as tool_defs
from .canvas import (
    Canvas, CUSTOM_SHAPES, GRADIENT_PRESETS, ZOOM_LEVELS, _grayscale_color, _grayscale_image,
)
from .model import BLEND_MODES, Document, Layer, Selection, default_style
from .palettes import (
    ActionsPalette, BrushesPalette, ChannelsPalette, CharacterPalette, ColorPalette,
    HistoryPalette, InfoPalette, LayersPalette, NavigatorPalette, PaletteGroup,
    ParagraphPalette, PathsPalette, StylesPalette, SwatchesPalette, ToolPresetsPalette,
)
from .splash import AboutDialog, SerialActivationDialog, SplashScreen

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets")

TOOLBOX_QSS = """
QToolButton { border: 1px solid transparent; background: transparent; }
QToolButton:hover { border: 1px solid #a0a090; background: #f6f5ee; }
QToolButton:checked { border: 1px solid #6a6a5a; background: #d4d0c0;
                      border-top-color: #8a8a7a; border-left-color: #8a8a7a; }
"""

OPTIONS_QSS = """
QWidget#optionsBar { background: #ece9d8; border-bottom: 1px solid #9a9a8a; }
QWidget#optHolder { background: transparent; }
QLabel { background: transparent; font-size: 11px; }
QCheckBox { background: transparent; font-size: 11px; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { font-size: 11px; }
"""

_activated_this_session = False


class ToolButton(QToolButton):
    """Toolbox button. Right-click (or press-and-hold) opens the flyout, and
    the little corner triangle marks slots that have one."""

    def __init__(self, win, group, index):
        super().__init__()
        self.win = win
        self.group_tools = group
        self.slot_index = index
        self.current = group[0]
        self.setCheckable(True)
        self.setFixedSize(26, 26)
        self.setIconSize(QSize(20, 20))
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self.show_flyout)
        self.refresh()

    def refresh(self):
        self.setIcon(pc_icons.icon(self.current.icon, 20))
        shortcut = f" ({self.current.shortcut})" if self.current.shortcut else ""
        self.setToolTip(f"{self.current.name}{shortcut}")

    def set_current(self, tool):
        self.current = tool
        self.refresh()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if len(self.group_tools) > 1:
            p = QPainter(self)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#303030"))
            w, h = self.width(), self.height()
            p.drawPolygon(QPoint(w - 3, h - 3), QPoint(w - 7, h - 3), QPoint(w - 3, h - 7))
            p.end()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            self.show_flyout()
            return
        self._hold.start(420)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._hold.stop()
        super().mouseReleaseEvent(ev)
        if ev.button() == Qt.MouseButton.LeftButton:
            self.win.select_tool(self.current.id)

    def show_flyout(self):
        self._hold.stop()
        if len(self.group_tools) < 2:
            return
        menu = QMenu(self)
        theme.style_menu(menu) if hasattr(theme, "style_menu") else None
        for tool in self.group_tools:
            act = QAction(pc_icons.icon(tool.icon, 16), tool.name
                          + (f"     {tool.shortcut}" if tool.shortcut else ""), menu)
            act.triggered.connect(lambda _, t=tool: self.win.select_tool(t.id))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(QPoint(self.width(), 0)))


class ColorSwatchWidget(QWidget):
    """Foreground/background swatches with the reset and swap glyphs."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(56, 52)
        self.setToolTip("Set foreground / background color (D resets, X swaps)")

    def paintEvent(self, ev):
        p = QPainter(self)
        p.drawPixmap(0, 0, pc_icons.pixmap("default_colors", 14))
        p.drawPixmap(40, 0, pc_icons.pixmap("swap_colors", 14))
        p.setPen(QPen(QColor("#606060"), 1))
        p.setBrush(self.win.bg_color)
        p.drawRect(20, 20, 28, 28)
        p.setBrush(self.win.fg_color)
        p.drawRect(6, 14, 28, 28)
        p.end()

    def mousePressEvent(self, ev):
        x, y = ev.position().x(), ev.position().y()
        if x < 15 and y < 15:
            self.win.reset_colors()
        elif x > 38 and y < 15:
            self.win.swap_colors()
        elif x > 32 and y > 30:
            self.win.pick_bg_color()
        else:
            self.win.pick_fg_color()


class PhotoChopWindow(XPWindow):
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

    # ================================================================ menus

    def _act(self, menu, text, slot=None, shortcut=None, checkable=False, checked=False,
             enabled=True):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.setEnabled(enabled)
        if slot:
            action.triggered.connect(slot)
        else:
            action.triggered.connect(lambda: self._not_implemented(text))
        menu.addAction(action)
        self.addAction(action)
        return action

    def _not_implemented(self, label):
        clean = label.replace("&", "").rstrip(".")
        XPMessageBox.information(
            self, "PhotoChop",
            f"Could not complete the {clean} command because "
            f"of a program error.")

    def _build_menu(self):
        bar = QMenuBar()
        theme.style_menubar(bar)

        # ---- File
        m = bar.addMenu("&File")
        self._act(m, "&New...", self.new_file, "Ctrl+N")
        self._act(m, "&Open...", self.open_file, "Ctrl+O")
        self._act(m, "&Browse...", self.open_file_browser, "Ctrl+Shift+O")
        recent = m.addMenu("Open &Recent")
        self._act(recent, "Untitled-1.psd")
        self._act(recent, "final_FINAL_v3.psd")
        self._act(recent, "final_FINAL_v3 (use this one).psd")
        m.addSeparator()
        self._act(m, "&Close", self.close, "Ctrl+W")
        self._act(m, "&Save", self.save_file, "Ctrl+S")
        self._act(m, "Save &As...", self.save_file_as, "Ctrl+Shift+S")
        self._act(m, "Save for &Web...", self.save_for_web, "Ctrl+Alt+Shift+S")
        self._act(m, "Re&vert", self.revert, "F12")
        m.addSeparator()
        place = m.addMenu("&Place")
        self._act(place, "Place Image...", self.place_image)
        imp = m.addMenu("&Import")
        self._act(imp, "PDF Image...")
        self._act(imp, "Annotations...")
        self._act(imp, "WIA Support...")
        exp = m.addMenu("&Export")
        self._act(exp, "Paths to Illustrator...")
        self._act(exp, "ZoomView...")
        m.addSeparator()
        auto = m.addMenu("&Automate")
        self._act(auto, "Batch...", self.batch_dialog)
        self._act(auto, "Create Droplet...")
        self._act(auto, "Conditional Mode Change...")
        self._act(auto, "Contact Sheet II...")
        self._act(auto, "Fit Image...", self.fit_image)
        self._act(auto, "Multi-Page PDF to PSD...")
        self._act(auto, "Picture Package...")
        self._act(auto, "Web Photo Gallery...")
        m.addSeparator()
        self._act(m, "File &Info...", self.file_info)
        m.addSeparator()
        self._act(m, "Page Set&up...", self.page_setup, "Ctrl+Shift+P")
        self._act(m, "&Print with Preview...", self.print_preview, "Ctrl+P")
        self._act(m, "Print One Copy", self.print_one, "Ctrl+Alt+Shift+P")
        m.addSeparator()
        self._act(m, "Jump to ImageReady", self.jump_to_imageready, "Ctrl+Shift+M")
        m.addSeparator()
        self._act(m, "E&xit", self.close, "Ctrl+Q")

        # ---- Edit
        m = bar.addMenu("&Edit")
        self.undo_action = self._act(m, "&Undo", self.undo, "Ctrl+Z")
        self._act(m, "Step For&ward", self.redo, "Ctrl+Shift+Z")
        self._act(m, "Step &Backward", self.undo, "Ctrl+Alt+Z")
        m.addSeparator()
        self._act(m, "Fa&de...", self.fade, "Ctrl+Shift+F")
        m.addSeparator()
        self._act(m, "Cu&t", self.cut, "Ctrl+X")
        self._act(m, "&Copy", self.copy, "Ctrl+C")
        self._act(m, "Copy &Merged", self.copy_merged, "Ctrl+Shift+C")
        self._act(m, "&Paste", self.paste, "Ctrl+V")
        self._act(m, "Paste &Into", self.paste_into, "Ctrl+Shift+V")
        self._act(m, "Cle&ar", self.clear_selection_pixels)
        m.addSeparator()
        self._act(m, "Chec&k Spelling...", self.check_spelling)
        self._act(m, "Find and Replace Text...", self.find_replace)
        m.addSeparator()
        self._act(m, "&Fill...", self.fill_dialog, "Shift+F5")
        self._act(m, "&Stroke...", self.stroke_dialog)
        m.addSeparator()
        self._act(m, "Free Trans&form", lambda: self.canvas.begin_transform(), "Ctrl+T")
        tr = m.addMenu("&Transform")
        for label in ("Again", "Scale", "Rotate", "Skew", "Distort", "Perspective"):
            self._act(tr, label, lambda _=None, l=label: self.canvas.begin_transform(l))
        tr.addSeparator()
        self._act(tr, "Rotate 180°", lambda: self.canvas.transform_numeric(
            lambda i: ops.rotate(i, 180)))
        self._act(tr, "Rotate 90° CW", lambda: self.canvas.transform_numeric(
            lambda i: ops.rotate(i, 90)))
        self._act(tr, "Rotate 90° CCW", lambda: self.canvas.transform_numeric(
            lambda i: ops.rotate(i, -90)))
        self._act(tr, "Flip Horizontal", lambda: self.canvas.transform_numeric(
            lambda i: ops.flip(i, True)))
        self._act(tr, "Flip Vertical", lambda: self.canvas.transform_numeric(
            lambda i: ops.flip(i, False)))
        m.addSeparator()
        self._act(m, "Define Brush...", self.define_brush)
        self._act(m, "Define Pattern...", self.define_pattern)
        self._act(m, "Define Custom Shape...", self.define_shape)
        m.addSeparator()
        self._act(m, "Purge", self.purge)
        m.addSeparator()
        self._act(m, "Color Settings...", self.color_settings, "Ctrl+Shift+K")
        self._act(m, "Preset Manager...", self.preset_manager)
        prefs = m.addMenu("Pre&ferences")
        for page in ("General...", "File Handling...", "Display & Cursors...",
                     "Transparency & Gamut...", "Units & Rulers...",
                     "Guides, Grid & Slices...", "Plug-Ins & Scratch Disks...",
                     "Memory & Image Cache..."):
            self._act(prefs, page, lambda _=None, pg=page: self.preferences(pg))

        # ---- Image
        m = bar.addMenu("&Image")
        mode = m.addMenu("&Mode")
        self._mode_group = QActionGroup(self)
        for name in ("Bitmap", "Grayscale", "Duotone", "Indexed Color", "RGB Color",
                     "CMYK Color", "Lab Color", "Multichannel"):
            act = self._act(mode, name, lambda _=None, n=name: self.set_mode(n),
                            checkable=True, checked=(name == "RGB Color"))
            self._mode_group.addAction(act)
        mode.addSeparator()
        self._act(mode, "8 Bits/Channel", checkable=True, checked=True)
        self._act(mode, "16 Bits/Channel", checkable=True)
        mode.addSeparator()
        self._act(mode, "Color Table...")
        self._act(mode, "Assign Profile...")
        self._act(mode, "Convert to Profile...")

        adjust = m.addMenu("Ad&justments")
        self._act(adjust, "&Levels...", self.levels, "Ctrl+L")
        self._act(adjust, "Auto Levels", self.auto_levels, "Ctrl+Shift+L")
        self._act(adjust, "Auto Contrast", self.auto_contrast, "Ctrl+Alt+Shift+L")
        self._act(adjust, "Auto Color", self.auto_color, "Ctrl+Shift+B")
        self._act(adjust, "&Curves...", self.curves, "Ctrl+M")
        self._act(adjust, "Color &Balance...", self.color_balance, "Ctrl+B")
        self._act(adjust, "Brightness/Contrast...", self.brightness_contrast)
        adjust.addSeparator()
        self._act(adjust, "&Hue/Saturation...", self.hue_saturation, "Ctrl+U")
        self._act(adjust, "&Desaturate", self.desaturate, "Ctrl+Shift+U")
        self._act(adjust, "Replace Color...", self.replace_color)
        self._act(adjust, "Selective Color...", self.selective_color)
        self._act(adjust, "Channel Mixer...", self.channel_mixer)
        self._act(adjust, "Gradient Map...", self.gradient_map)
        adjust.addSeparator()
        self._act(adjust, "&Invert", self.invert, "Ctrl+I")
        self._act(adjust, "Equalize", self.equalize)
        self._act(adjust, "Threshold...", self.threshold)
        self._act(adjust, "Posterize...", self.posterize)
        adjust.addSeparator()
        self._act(adjust, "Variations...", self.variations)

        m.addSeparator()
        self._act(m, "&Duplicate...", self.duplicate_document)
        self._act(m, "Apply Image...", self.apply_image)
        self._act(m, "Calculations...")
        m.addSeparator()
        self._act(m, "&Image Size...", self.image_size, "Ctrl+Alt+I")
        self._act(m, "&Canvas Size...", self.canvas_size, "Ctrl+Alt+C")
        rot = m.addMenu("&Rotate Canvas")
        self._act(rot, "180°", lambda: self.rotate_canvas(180))
        self._act(rot, "90° CW", lambda: self.rotate_canvas(90))
        self._act(rot, "90° CCW", lambda: self.rotate_canvas(-90))
        self._act(rot, "Arbitrary...", self.rotate_arbitrary)
        rot.addSeparator()
        self._act(rot, "Flip Horizontal", lambda: self.flip_canvas(True))
        self._act(rot, "Flip Vertical", lambda: self.flip_canvas(False))
        self._act(m, "Cro&p", self.crop_to_selection)
        self._act(m, "Trim...", self.trim)
        self._act(m, "Reveal All", self.reveal_all)
        m.addSeparator()
        self._act(m, "Histogram...", self.show_histogram)
        self._act(m, "Trap...")

        # ---- Layer
        m = bar.addMenu("&Layer")
        new = m.addMenu("&New")
        self._act(new, "Layer...", self.new_layer_dialog, "Ctrl+Shift+N")
        self._act(new, "Layer From Background", self.layer_from_background)
        self._act(new, "Layer Set...", self.new_layer_set)
        self._act(new, "Layer Set From Linked...")
        self._act(new, "Layer via Copy", self.layer_via_copy, "Ctrl+J")
        self._act(new, "Layer via Cut", self.layer_via_cut, "Ctrl+Shift+J")
        self._act(m, "&Duplicate Layer...", self.duplicate_layer)
        self._act(m, "De&lete Layer", self.delete_layer)
        m.addSeparator()
        self._act(m, "Layer &Properties...", self.layer_properties)
        style = m.addMenu("Layer &Style")
        self._act(style, "Blending Options...", self.layer_style)
        style.addSeparator()
        for effect in ("Drop Shadow", "Inner Shadow", "Outer Glow", "Inner Glow",
                       "Bevel and Emboss", "Satin", "Color Overlay", "Gradient Overlay",
                       "Pattern Overlay", "Stroke"):
            self._act(style, effect + "...",
                      lambda _=None, e=effect: self.layer_style(e))
        style.addSeparator()
        self._act(style, "Copy Layer Style", self.copy_layer_style)
        self._act(style, "Paste Layer Style", self.paste_layer_style)
        self._act(style, "Clear Layer Style", self.clear_layer_style)
        self._act(style, "Global Light...")
        self._act(style, "Create Layers", self.style_to_layers)
        self._act(style, "Hide All Effects", self.hide_effects)

        fill_new = m.addMenu("New &Fill Layer")
        for kind in ("Solid Color...", "Gradient...", "Pattern..."):
            self._act(fill_new, kind, lambda _=None, k=kind: self.new_fill_layer(k))
        adj_new = m.addMenu("New Ad&justment Layer")
        for kind in ("Levels...", "Curves...", "Color Balance...",
                     "Brightness/Contrast...", "Hue/Saturation...", "Selective Color...",
                     "Channel Mixer...", "Gradient Map...", "Invert", "Threshold...",
                     "Posterize..."):
            self._act(adj_new, kind,
                      lambda _=None, k=kind: self.new_adjustment_layer(k.rstrip(".")))
        self._act(m, "Change Layer Content")
        self._act(m, "Layer Content Options...")

        mask = m.addMenu("Add Layer &Mask")
        self._act(mask, "Reveal All", lambda: self.add_layer_mask("reveal"))
        self._act(mask, "Hide All", lambda: self.add_layer_mask("hide"))
        self._act(mask, "Reveal Selection", lambda: self.add_layer_mask("selection"))
        self._act(mask, "Hide Selection", lambda: self.add_layer_mask("hide-selection"))
        remove_mask = m.addMenu("&Remove Layer Mask")
        self._act(remove_mask, "Apply", lambda: self.remove_layer_mask(True))
        self._act(remove_mask, "Discard", lambda: self.remove_layer_mask(False))
        self._act(m, "Enable Layer Mask", self.toggle_layer_mask)
        m.addSeparator()
        self._act(m, "&Group with Previous", self.group_with_previous, "Ctrl+G")
        self._act(m, "&Ungroup", self.ungroup, "Ctrl+Shift+G")
        arrange = m.addMenu("&Arrange")
        self._act(arrange, "Bring to Front", lambda: self.arrange("front"), "Ctrl+Shift+]")
        self._act(arrange, "Bring Forward", lambda: self.arrange("forward"), "Ctrl+]")
        self._act(arrange, "Send Backward", lambda: self.arrange("backward"), "Ctrl+[")
        self._act(arrange, "Send to Back", lambda: self.arrange("back"), "Ctrl+Shift+[")
        align = m.addMenu("Align Linked")
        for label in ("Top Edges", "Vertical Centers", "Bottom Edges", "Left Edges",
                      "Horizontal Centers", "Right Edges"):
            self._act(align, label)
        m.addSeparator()
        self._act(m, "Merge &Down", self.merge_down, "Ctrl+E")
        self._act(m, "Merge &Visible", self.merge_visible, "Ctrl+Shift+E")
        self._act(m, "&Flatten Image", self.flatten_image)
        m.addSeparator()
        self._act(m, "Matting", self.defringe)

        # ---- Select
        m = bar.addMenu("&Select")
        self._act(m, "&All", self.select_all, "Ctrl+A")
        self._act(m, "&Deselect", self.deselect, "Ctrl+D")
        self._act(m, "&Reselect", self.reselect, "Ctrl+Shift+D")
        self._act(m, "&Inverse", self.inverse_selection, "Ctrl+Shift+I")
        m.addSeparator()
        self._act(m, "Color Range...", self.color_range)
        m.addSeparator()
        self._act(m, "&Feather...", self.feather, "Ctrl+Alt+D")
        modify = m.addMenu("&Modify")
        self._act(modify, "Border...", lambda: self.modify_selection("Border"))
        self._act(modify, "Smooth...", lambda: self.modify_selection("Smooth"))
        self._act(modify, "Expand...", lambda: self.modify_selection("Expand"))
        self._act(modify, "Contract...", lambda: self.modify_selection("Contract"))
        m.addSeparator()
        self._act(m, "&Grow", self.grow_selection)
        self._act(m, "Si&milar", self.similar_selection)
        m.addSeparator()
        self._act(m, "Transform Selection", self.transform_selection)
        m.addSeparator()
        self._act(m, "&Load Selection...", self.load_channel_selection)
        self._act(m, "&Save Selection...", self.save_selection_channel)

        # ---- Filter
        m = bar.addMenu("F&ilter")
        self.last_filter_action = self._act(m, "Last Filter", self.repeat_last_filter, "Ctrl+F")
        self.last_filter_action.setEnabled(False)
        m.addSeparator()
        self._act(m, "E&xtract...", self.extract, "Ctrl+Alt+X")
        self._act(m, "Li&quify...", self.liquify, "Ctrl+Shift+X")
        self._act(m, "&Pattern Maker...", self.pattern_maker, "Ctrl+Alt+Shift+X")
        m.addSeparator()
        for category, items in filt.FILTER_MENU:
            sub = m.addMenu(category)
            for label, key, params in items:
                self._act(sub, label,
                          lambda _=None, l=label, k=key, p=params: self.run_filter(l, k, p))

        # ---- View
        m = bar.addMenu("&View")
        proof = m.addMenu("Proof Setup")
        for label in ("Custom...", "Working CMYK", "Working Cyan Plate", "Macintosh RGB",
                      "Windows RGB", "Monitor RGB"):
            self._act(proof, label)
        self._act(m, "Proof Colors", shortcut="Ctrl+Y", checkable=True)
        self._act(m, "Gamut Warning", shortcut="Ctrl+Shift+Y", checkable=True)
        m.addSeparator()
        self._act(m, "Zoom &In", self.canvas_zoom_in, "Ctrl+=")
        self._act(m, "Zoom &Out", self.canvas_zoom_out, "Ctrl+-")
        self._act(m, "&Fit on Screen", self.canvas.fit_on_screen, "Ctrl+0")
        self._act(m, "&Actual Pixels", self.canvas.actual_pixels, "Ctrl+Alt+0")
        self._act(m, "Print Size", self.canvas.actual_pixels)
        m.addSeparator()
        self._act(m, "Show &Extras", self.toggle_extras, "Ctrl+H", checkable=True,
                  checked=True)
        show = m.addMenu("&Show")
        self._act(show, "Selection Edges", self.toggle_extras, checkable=True, checked=True)
        self._act(show, "Grid", self.toggle_grid, "Ctrl+'", checkable=True)
        self._act(show, "Guides", self.toggle_guides, "Ctrl+;", checkable=True, checked=True)
        self._act(show, "Slices", checkable=True)
        self._act(show, "Annotations", checkable=True, checked=True)
        m.addSeparator()
        self._act(m, "&Rulers", self.toggle_rulers, "Ctrl+R", checkable=True, checked=True)
        m.addSeparator()
        self._act(m, "&Snap", None, "Ctrl+Shift+;", checkable=True, checked=True)
        self._act(m, "Lock Guides", None, "Ctrl+Alt+;", checkable=True)
        self._act(m, "Clear Guides", self.clear_guides)
        self._act(m, "New Guide...", self.new_guide)

        # ---- Window
        m = bar.addMenu("&Window")
        arrange_menu = m.addMenu("Arrange")
        self._act(arrange_menu, "Cascade")
        self._act(arrange_menu, "Tile")
        self._act(arrange_menu, "Arrange Icons")
        self._act(m, "Documents")
        m.addSeparator()
        self._act(m, "Workspace")
        m.addSeparator()
        self.palette_actions = {}
        for name in ("Tools", "Options", "File Browser", "Navigator", "Info", "Color",
                     "Swatches", "Styles", "History", "Actions", "Tool Presets",
                     "Layers", "Channels", "Paths", "Brushes", "Character",
                     "Paragraph", "Status Bar"):
            act = self._act(m, name, lambda _=None, n=name: self.toggle_palette(n),
                            checkable=True, checked=name not in ("File Browser",))
            self.palette_actions[name] = act

        # ---- Help
        m = bar.addMenu("&Help")
        self._act(m, "PhotoChop Help...", self.show_help, "F1")
        self._act(m, "About PhotoChop...", self.about)
        self._act(m, "About Plug-In", self.about_plugin)
        m.addSeparator()
        self._act(m, "Export Transparent Image...", self.help_wizard)
        self._act(m, "Resize Image...", self.help_wizard)
        m.addSeparator()
        self._act(m, "System Info...", self.system_info)
        self._act(m, "Updates, Support and more...", self.support)
        m.addSeparator()
        self._act(m, "Register...", self.register)
        self._act(m, "Transfer Activation...", self.deactivate)
        return bar

    # ============================================================ chrome ==

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
        dock.setFixedWidth(226)
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
        return dock

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

    # ======================================================== tool plumbing

    def tool_spec(self, tool_id):
        return tool_defs.ALL_TOOLS.get(tool_id)

    def select_tool(self, tool_id):
        spec = tool_defs.ALL_TOOLS.get(tool_id)
        if spec is None:
            return
        self.current_tool = tool_id
        for btn in self._tool_buttons:
            in_group = any(t.id == tool_id for t in btn.group_tools)
            btn.setChecked(in_group)
            if in_group:
                btn.set_current(spec)
        self._tool_icon_label.setPixmap(pc_icons.pixmap(spec.icon, 22))
        self._rebuild_options(spec)
        self._set_hint(spec.hint)
        self.canvas._update_cursor()
        self.canvas.update()

    def _rebuild_options(self, spec):
        while self._options_host_layout.count():
            item = self._options_host_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_widgets = {}
        for control in spec.options:
            widget = self._build_option(control)
            if widget is not None:
                self._options_host_layout.addWidget(widget)
        self._options_host_layout.addStretch(1)

    def _build_option(self, control):
        kind, key, label, extra = control
        if kind == "sep":
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setStyleSheet("color: #b0b0a0;")
            return line
        if kind == "selops":
            return self._build_selops()
        if kind == "label":
            return QLabel(label)
        holder = QWidget()
        holder.setObjectName("optHolder")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        if label and kind not in ("check",):
            row.addWidget(QLabel(label))
        widget = None
        if kind == "check":
            widget = QCheckBox(label)
            widget.setChecked(bool(self.options.get(key)))
            widget.toggled.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "spin":
            lo, hi, suffix = extra
            widget = QSpinBox()
            widget.setRange(lo, hi)
            widget.setValue(int(self.options.get(key, lo)))
            widget.setSuffix(suffix)
            widget.setFixedWidth(64 if hi < 1000 else 74)
            widget.valueChanged.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "pct":
            widget = QSpinBox()
            widget.setRange(0, 100)
            widget.setValue(int(self.options.get(key, extra or 100)))
            widget.setSuffix("%")
            widget.setFixedWidth(56)
            widget.valueChanged.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "combo":
            widget = QComboBox()
            widget.addItems([str(c) for c in extra])
            current = str(self.options.get(key, extra[0]))
            if current in [str(c) for c in extra]:
                widget.setCurrentText(current)
            widget.currentTextChanged.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "blend":
            widget = QComboBox()
            for mode in BLEND_MODES:
                if mode == "-":
                    widget.insertSeparator(widget.count())
                else:
                    widget.addItem(mode)
            widget.setCurrentText(self.options.get(key, "Normal"))
            widget.setFixedWidth(98)
            widget.currentTextChanged.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "brush":
            widget = BrushPickerButton(self)
        elif kind == "gradient":
            widget = GradientPickerButton(self)
        elif kind == "shape":
            widget = QComboBox()
            widget.addItems(CUSTOM_SHAPES)
            widget.setCurrentText(self.options.get("custom_shape", "Heart"))
            widget.currentTextChanged.connect(lambda v: self._set_option("custom_shape", v))
        elif kind == "color":
            widget = QPushButton()
            widget.setFixedSize(34, 18)
            colour = self.options.get(key, "#f5e04a")
            widget.setStyleSheet(f"background: {colour}; border: 1px solid #555;")
            widget.clicked.connect(lambda _, k=key, b=widget: self._pick_option_color(k, b))
        elif kind == "font":
            return self._build_font_options()
        if widget is None:
            return None
        self._option_widgets[key] = widget
        row.addWidget(widget)
        return holder

    def _build_selops(self):
        holder = QWidget()
        holder.setObjectName("optHolder")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(1)
        self._selop_buttons = {}
        for key, glyph, tip in (("new", "sel_new", "New selection"),
                                ("add", "sel_add", "Add to selection"),
                                ("subtract", "sel_subtract", "Subtract from selection"),
                                ("intersect", "sel_intersect", "Intersect with selection")):
            btn = QToolButton()
            btn.setIcon(pc_icons.icon(glyph, 16))
            btn.setIconSize(QSize(16, 16))
            btn.setCheckable(True)
            btn.setChecked(self.options.get("selop", "new") == key)
            btn.setFixedSize(22, 22)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _, k=key: self._set_selop(k))
            self._selop_buttons[key] = btn
            row.addWidget(btn)
        return holder

    def _build_font_options(self):
        holder = QWidget()
        holder.setObjectName("optHolder")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        font = self.options.get("font", {})
        from PyQt6.QtGui import QFontDatabase
        family = QComboBox()
        family.addItems(QFontDatabase.families()[:80])
        family.setCurrentText(font.get("family", "Tahoma"))
        family.setFixedWidth(120)
        family.currentTextChanged.connect(lambda v: self._set_font("family", v))
        style = QComboBox()
        style.addItems(["Regular", "Italic", "Bold", "Bold Italic"])
        style.setCurrentText(font.get("style", "Regular"))
        style.setFixedWidth(76)
        style.currentTextChanged.connect(lambda v: self._set_font("style", v))
        size = QComboBox()
        size.setEditable(True)
        size.addItems([str(s) for s in (6, 8, 10, 12, 14, 18, 24, 30, 36, 48, 60, 72)])
        size.setCurrentText(str(font.get("size", 24)))
        size.setFixedWidth(58)
        size.currentTextChanged.connect(
            lambda v: self._set_font("size", int(v) if v.isdigit() else 24))
        anti = QComboBox()
        anti.addItems(["None", "Sharp", "Crisp", "Strong", "Smooth"])
        anti.setCurrentText(font.get("antialias", "Crisp"))
        anti.setFixedWidth(66)
        anti.currentTextChanged.connect(lambda v: self._set_font("antialias", v))
        colour = QPushButton()
        colour.setFixedSize(34, 18)
        colour.setStyleSheet(f"background: {font.get('color', '#000000')};"
                             f"border: 1px solid #555;")
        colour.clicked.connect(lambda: self._pick_font_color(colour))
        for w in (family, style, size, anti):
            row.addWidget(w)
        row.addWidget(colour)
        return holder

    def _set_font(self, key, value):
        font = dict(self.options.get("font", {}))
        font[key] = value
        self.options["font"] = font
        if self._type_editor is not None:
            self._apply_type_font()

    def _pick_font_color(self, button):
        font = dict(self.options.get("font", {}))
        c = XPColorDialog.get_color(self, QColor(font.get("color", "#000000")))
        if c:
            font["color"] = c.name()
            self.options["font"] = font
            button.setStyleSheet(f"background: {c.name()}; border: 1px solid #555;")
            if self._type_editor is not None:
                self._apply_type_font()

    def _pick_option_color(self, key, button):
        c = XPColorDialog.get_color(self, QColor(self.options.get(key, "#f5e04a")))
        if c:
            self.options[key] = c.name()
            button.setStyleSheet(f"background: {c.name()}; border: 1px solid #555;")

    def _set_selop(self, key):
        self.options["selop"] = key
        for k, btn in self._selop_buttons.items():
            btn.setChecked(k == key)

    def _set_option(self, key, value):
        self.options[key] = value

    def sync_options_bar(self):
        spec = tool_defs.ALL_TOOLS.get(self.current_tool)
        if spec:
            self._rebuild_options(spec)

    # ====================================================== state refresh ==

    def refresh_all(self):
        self.doc.invalidate()
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

    # ============================================================ file =====

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

    # ============================================================ edit =====

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

    # =========================================================== image =====

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

    # =========================================================== layers ====

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

    # ======================================================== selection ====

    def select_all(self):
        sel = self.doc.ensure_selection()
        sel.select_all()
        self.doc.history.record("Select All")
        self.refresh_all()

    def deselect(self):
        if self.doc.selection:
            self._last_selection = self.doc.selection.copy()
        self.canvas.deselect()
        self.doc.history.record("Deselect")
        self.refresh_all()

    def reselect(self):
        prior = getattr(self, "_last_selection", None)
        if prior:
            self.doc.selection = prior.copy()
            self.doc.history.record("Reselect")
            self.refresh_all()

    def inverse_selection(self):
        if not self.doc.has_selection():
            self.select_all()
            return
        self.doc.selection.invert()
        self.doc.history.record("Inverse")
        self.refresh_all()

    def color_range(self):
        d = adj.ColorRangeDialog(self, self.doc.composite(), self.fg_color)
        if d.exec() == QDialog.DialogCode.Accepted:
            sel = self.doc.ensure_selection()
            sel.set_mask(d.mask(), "replace")
            self.doc.history.record("Color Range")
            self.refresh_all()

    def feather(self):
        if not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop", "There is no selection to feather.")
            return
        d = dlg.FeatherDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.selection.feather(d.result())
            self.doc.history.record("Feather")
            self.refresh_all()

    def modify_selection(self, kind):
        if not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop", "There is no selection to modify.")
            return
        value = dlg.ValueDialog.get(self, kind + " Selection",
                                    ("Width:" if kind == "Border" else
                                     "Sample Radius:" if kind == "Smooth" else
                                     "Expand By:" if kind == "Expand" else "Contract By:"),
                                    5, 1, 100)
        if value is None:
            return
        sel = self.doc.selection
        {"Border": sel.border, "Smooth": sel.smooth,
         "Expand": sel.expand, "Contract": sel.contract}[kind](value)
        self.doc.history.record(kind)
        self.refresh_all()

    def grow_selection(self):
        if self.doc.has_selection():
            self.doc.selection.expand(4)
            self.doc.history.record("Grow")
            self.refresh_all()

    def similar_selection(self):
        if not self.doc.has_selection():
            return
        from .canvas import magic_wand_mask
        bounds = self.doc.selection.bounds()
        seed = bounds.center()
        mask = magic_wand_mask(self.doc.composite(), seed,
                               self.options.get("tolerance", 32), contiguous=False)
        if mask is not None:
            self.doc.selection.set_mask(mask, "add")
            self.doc.history.record("Similar")
            self.refresh_all()

    def transform_selection(self):
        self.canvas.begin_transform("Free Transform")

    def load_channel_selection(self):
        if not self.doc.alpha_channels:
            XPMessageBox.warning(self, "PhotoChop", "There are no saved selections.")
            return
        name, mask = self.doc.alpha_channels[-1]
        sel = self.doc.ensure_selection()
        sel.set_mask(mask.copy(), "replace")
        self._set_hint(f"Loaded selection from {name}.")
        self.refresh_all()

    def save_selection_channel(self):
        if not self.doc.has_selection():
            XPMessageBox.warning(self, "PhotoChop", "There is no selection to save.")
            return
        name = f"Alpha {len(self.doc.alpha_channels) + 1}"
        self.doc.alpha_channels.append((name, self.doc.selection.mask.copy()))
        self._set_hint(f"Selection saved as {name}.")
        self.refresh_all()

    def new_alpha_channel(self):
        blank = QImage(self.doc.width, self.doc.height,
                       QImage.Format.Format_ARGB32_Premultiplied)
        blank.fill(Qt.GlobalColor.black)
        self.doc.alpha_channels.append((f"Alpha {len(self.doc.alpha_channels) + 1}", blank))
        self.refresh_all()

    def delete_alpha_channel(self):
        if self.doc.alpha_channels:
            self.doc.alpha_channels.pop()
            self.refresh_all()

    def set_quick_mask(self, on):
        if on and not self.doc.has_selection():
            self.select_all()
        self.doc.quick_mask = on
        for i, btn in enumerate(self.quick_mask_buttons):
            btn.setChecked(bool(i) == on)
        self._set_hint("Edit in Quick Mask Mode" if on else "Edit in Standard Mode")
        self.canvas.update()

    # ============================================================ paths ====

    def new_path(self):
        self.doc.paths.append((f"Path {len(self.doc.paths) + 1}", QPainterPath()))
        self.refresh_all()

    def delete_path(self):
        row = self.paths.list.currentRow()
        if 0 <= row < len(self.doc.paths):
            del self.doc.paths[row]
            self.refresh_all()

    def _current_path(self):
        row = self.paths.list.currentRow()
        if 0 <= row < len(self.doc.paths):
            return self.doc.paths[row][1]
        return self.doc.paths[-1][1] if self.doc.paths else None

    def fill_path(self):
        path = self._current_path()
        if path is None:
            return
        layer = self.doc.active
        editing_mask = layer.editing_mask()
        p = QPainter(layer.target_image())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_grayscale_color(self.fg_color) if editing_mask else self.fg_color)
        p.drawPath(path)
        p.end()
        self.doc.invalidate()
        self.doc.history.record("Fill Path")
        self.refresh_all()

    def stroke_path(self):
        path = self._current_path()
        if path is None:
            return
        layer = self.doc.active
        editing_mask = layer.editing_mask()
        brush = self.options.get("brush", {})
        pen_colour = _grayscale_color(self.fg_color) if editing_mask else self.fg_color
        p = QPainter(layer.target_image())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(pen_colour, max(1, brush.get("size", 13) // 3),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()
        self.doc.invalidate()
        self.doc.history.record("Stroke Path")
        self.refresh_all()

    def path_to_selection(self):
        path = self._current_path()
        if path is None:
            return
        sel = self.doc.ensure_selection()
        sel.set_path(path, "replace")
        self.doc.history.record("Make Selection")
        self.refresh_all()

    def selection_to_path(self):
        if not self.doc.has_selection() or self.doc.selection.path is None:
            return
        self.doc.paths.append((f"Work Path", QPainterPath(self.doc.selection.path)))
        self.refresh_all()

    # ========================================================== history ====

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

    # =========================================================== filters ===

    def run_filter(self, label, key, params):
        layer = self.doc.active
        if layer.kind == "adjustment":
            XPMessageBox.warning(self, "PhotoChop",
                                 "Could not apply the filter to an adjustment layer.")
            return
        ctx = {"fg": self.fg_color.name(), "bg": self.bg_color.name()}
        if not params:
            self._apply_filter(key, {}, ctx, label)
            return
        source = layer.image
        values = dlg.FilterDialog.run(
            self, label.rstrip("."), params,
            lambda v: filt.run(key, source, v, ctx), source)
        if values is not None:
            self._apply_filter(key, values, ctx, label)

    def _apply_filter(self, key, values, ctx, label):
        self.last_filter = (label, key, values, ctx)
        self.last_filter_action.setEnabled(True)
        self.last_filter_action.setText(label.rstrip("."))
        self._apply_to_target(lambda img: filt.run(key, img, values, ctx),
                              label.rstrip("."))

    def repeat_last_filter(self):
        if not self.last_filter:
            return
        label, key, values, ctx = self.last_filter
        self._apply_to_target(lambda img: filt.run(key, img, values, ctx),
                              label.rstrip("."))

    def extract(self):
        from .workspaces import ExtractDialog
        d = ExtractDialog(self, self.doc.active.image)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.active.image = d.result()
            self.doc.invalidate()
            self.doc.history.record("Extract")
            self.refresh_all()

    def liquify(self):
        from .workspaces import LiquifyDialog
        d = LiquifyDialog(self, self.doc.active.image)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.active.image = d.result()
            self.doc.invalidate()
            self.doc.history.record("Liquify")
            self.refresh_all()

    def pattern_maker(self):
        from .workspaces import PatternMakerDialog
        d = PatternMakerDialog(self, self.doc.active.image)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.doc.active.image = d.result()
            self.doc.invalidate()
            self.doc.history.record("Pattern Maker")
            self.refresh_all()

    # ============================================================= view ====

    def canvas_zoom_in(self):
        self.canvas.zoom_in()

    def canvas_zoom_out(self):
        self.canvas.zoom_out()

    def toggle_extras(self):
        self.canvas.update()

    def toggle_grid(self):
        self.canvas.show_grid = not self.canvas.show_grid
        self.canvas.update()

    def toggle_guides(self):
        self.canvas.show_guides = not self.canvas.show_guides
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
            self.doc.guides_h.append(value)
            self.canvas.update()

    def add_guide(self, horizontal, position):
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

    # ============================================================= type ====

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

    # ============================================================= help ====

    def show_help(self):
        from .misc_dialogs import HelpDialog
        HelpDialog(self).exec()

    def about(self):
        AboutDialog(self).exec()

    def about_plugin(self):
        XPMessageBox.information(
            self, "About Plug-In",
            "Chrome Filter 1.0\n\nCopyright 1991-2002. All rights probably reserved.")

    def help_wizard(self):
        XPMessageBox.information(
            self, "PhotoChop",
            "This wizard would walk you through five steps that each do one "
            "thing you already know how to do.")

    def system_info(self):
        XPMessageBox.information(
            self, "System Info",
            f"PhotoChop 7.0\nSerial: 1045-1234-5678-9012-3456-7890\n\n"
            f"Physical memory: 256 MB\nMemory available to PhotoChop: 51 MB\n"
            f"Scratch disk: C:\\ (free: not much)\n"
            f"Image cache level: 4\nDocument: {self.doc.width} x {self.doc.height}")

    def support(self):
        XPMessageBox.information(
            self, "PhotoChop",
            "Could not connect to the internet because dial-up is not configured.")

    def register(self):
        XPMessageBox.information(
            self, "Registration",
            "Thank you for registering PhotoChop. Your details have been written "
            "to a floppy disk and mailed to nobody.")

    def deactivate(self):
        XPMessageBox.information(
            self, "Transfer Activation",
            "You have used 1 of 2 activations.\n\nDeactivating will let you activate "
            "PhotoChop on another computer. There is no other computer.")


class FadeDialog(dlg.PCDialog):
    def __init__(self, parent, last_name, apply_fn):
        super().__init__(parent, "Fade")
        self.apply_fn = apply_fn
        label = QLabel(f"Fade: {last_name}")
        label.setStyleSheet("background: transparent;")
        self.content.addWidget(label)
        self.opacity = dlg.SliderRow("Opacity:", 0, 100, 100, "%")
        self.opacity.changed.connect(self._refresh)
        self.content.addWidget(self.opacity)
        row = QHBoxLayout()
        row.addWidget(dlg._lbl("Mode:"))
        self.mode = QComboBox()
        for mode in BLEND_MODES:
            if mode == "-":
                self.mode.insertSeparator(self.mode.count())
            else:
                self.mode.addItem(mode)
        self.mode.currentTextChanged.connect(lambda _: self._refresh())
        row.addWidget(self.mode, 1)
        self.content.addLayout(row)
        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()
        self._refresh()

    def values(self):
        return dict(opacity=self.opacity.value(), mode=self.mode.currentText())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class Ruler(QWidget):
    """Ruler with tick marks and the cursor tracker line. Drag one out to
    create a guide, the way PS does."""

    def __init__(self, win, horizontal=True):
        super().__init__()
        self.win = win
        self.horizontal = horizontal
        self.cursor_pos = None
        if horizontal:
            self.setFixedHeight(18)
        else:
            self.setFixedWidth(18)
        self.setStyleSheet("background: #ece9d8;")

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ece9d8"))
        p.setPen(QPen(QColor("#9a9a8a"), 1))
        if self.horizontal:
            p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        canvas = self.win.canvas
        r = canvas.view_rect()
        zoom = canvas.zoom
        step = 50
        while step * zoom < 40:
            step *= 2
        while step * zoom > 160:
            step //= 2
        step = max(1, step)
        p.setFont(QFont(theme.FONT_FAMILY, 6))
        p.setPen(QPen(QColor("#404040"), 1))
        doc_span = self.win.doc.width if self.horizontal else self.win.doc.height
        value = 0
        while value <= doc_span:
            pos = (r.x() + value * zoom) if self.horizontal else (r.y() + value * zoom)
            if self.horizontal:
                p.drawLine(int(pos), 12, int(pos), 17)
                p.drawText(int(pos) + 2, 9, str(value))
                for sub in range(1, 5):
                    sp = pos + step * zoom * sub / 5
                    p.drawLine(int(sp), 14, int(sp), 17)
            else:
                p.drawLine(12, int(pos), 17, int(pos))
                p.save()
                p.translate(9, int(pos) + 2)
                p.rotate(-90)
                p.drawText(0, 0, str(value))
                p.restore()
                for sub in range(1, 5):
                    sp = pos + step * zoom * sub / 5
                    p.drawLine(14, int(sp), 17, int(sp))
            value += step

        if self.cursor_pos is not None:
            p.setPen(QPen(QColor("#202020"), 1))
            if self.horizontal:
                x = r.x() + self.cursor_pos.x() * zoom
                p.drawLine(int(x), 0, int(x), self.height())
            else:
                y = r.y() + self.cursor_pos.y() * zoom
                p.drawLine(0, int(y), self.width(), int(y))
        p.end()

    def mousePressEvent(self, ev):
        self._dragging = True

    def mouseReleaseEvent(self, ev):
        canvas = self.win.canvas
        r = canvas.view_rect()
        if self.horizontal:
            pos = (ev.position().y() - r.y()) / max(0.01, canvas.zoom)
            self.win.add_guide(True, max(0, pos))
        else:
            pos = (ev.position().x() - r.x()) / max(0.01, canvas.zoom)
            self.win.add_guide(False, max(0, pos))


class BrushPickerButton(QPushButton):
    """The brush preview button that drops down the preset picker."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(56, 22)
        self.clicked.connect(self._show_picker)
        self.refresh()

    def refresh(self):
        brush = self.win.options.get("brush", {})
        self.setText(str(brush.get("size", 13)))
        self.setToolTip(brush.get("preset", "Brush"))

    def _show_picker(self):
        menu = QMenu(self)
        for name, size, hardness in brushes.BRUSH_PRESETS:
            act = QAction(f"{name}", menu)
            act.triggered.connect(
                lambda _, n=name, s=size, h=hardness: self._pick(n, s, h))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def _pick(self, name, size, hardness):
        brush = dict(self.win.options.get("brush", {}))
        brush.update(preset=name, size=size, hardness=hardness)
        self.win.options["brush"] = brush
        self.win.brushes_palette.refresh()
        self.refresh()


class GradientPickerButton(QPushButton):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(76, 20)
        self.clicked.connect(self._show_picker)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        from PyQt6.QtGui import QLinearGradient
        p = QPainter(self)
        name = self.win.options.get("gradient", "Foreground to Background")
        stops = GRADIENT_PRESETS.get(name)
        grad = QLinearGradient(3, 0, self.width() - 3, 0)
        if stops:
            for pos, colour in stops:
                grad.setColorAt(pos, QColor(colour))
        else:
            grad.setColorAt(0, self.win.fg_color)
            grad.setColorAt(1, self.win.bg_color)
        p.fillRect(QRect(3, 3, self.width() - 6, self.height() - 6), grad)
        p.setPen(QPen(QColor("#606060"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRect(3, 3, self.width() - 7, self.height() - 7))
        p.end()

    def _show_picker(self):
        menu = QMenu(self)
        for name in GRADIENT_PRESETS:
            act = QAction(name, menu)
            act.triggered.connect(lambda _, n=name: self._pick(n))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def _pick(self, name):
        self.win.options["gradient"] = name
        self.update()


def _content_bounds(img: QImage) -> QRect:
    buf, w, h = ops.to_buf(img)
    alpha = ops.plane(buf, ops.A)
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        row = y * w
        for x in range(w):
            if alpha[row + x] > 8:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < 0:
        return QRect()
    return QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def _vignette(img: QImage) -> QImage:
    from PyQt6.QtGui import QRadialGradient
    overlay = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    overlay.fill(Qt.GlobalColor.transparent)
    p = QPainter(overlay)
    grad = QRadialGradient(img.width() / 2, img.height() / 2,
                           max(img.width(), img.height()) * 0.62)
    grad.setColorAt(0.55, QColor(0, 0, 0, 0))
    grad.setColorAt(1.0, QColor(0, 0, 0, 210))
    p.fillRect(overlay.rect(), grad)
    p.end()
    out = img.copy()
    p = QPainter(out)
    p.drawImage(0, 0, overlay)
    p.end()
    return out
