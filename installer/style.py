"""Shared look for the Setup wizard.

Lives on its own so the wizard and the extra pages cannot drift apart, and
so neither has to import the other.

GUI-mode Setup ran before the theme service existed, so its dialogs were the
Windows Classic grey of Windows 2000 -- not Luna. The colours below are that
scheme, and the app runs under Qt's "Windows" style, which draws the same
bevelled buttons, sunken fields and dotted focus rectangles.
"""
from __future__ import annotations

import os
import platform

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import QProxyStyle, QStyle, QStyleFactory, QStyleOptionComboBox

_SYSTEM = platform.system()


def _has_font(filename: str) -> bool:
    return any(os.path.exists(os.path.join(d, filename)) for d in (
        "/System/Library/Fonts/Supplemental", "/Library/Fonts",
        os.path.expanduser("~/Library/Fonts"),
        "/usr/share/fonts/truetype/msttcorefonts"))


# Tahoma ships with Windows, and macOS keeps a copy in Supplemental fonts.
# Elsewhere pick something that is actually installed so text doesn't fall
# back to an ugly generic serif.
if _SYSTEM == "Windows" or _has_font("Tahoma.ttf"):
    UI_FONT_FAMILY = "Tahoma"
else:
    UI_FONT_FAMILY = "DejaVu Sans"
# Wizard97 welcome/completion titles are Verdana Bold 12pt.
TITLE_FONT_FAMILY = ("Verdana" if _SYSTEM == "Windows" or _has_font("Verdana.ttf")
                     else UI_FONT_FAMILY)
MONO_FONT_FAMILY = {"Windows": "Lucida Console", "Darwin": "Menlo"}.get(
    _SYSTEM, "DejaVu Sans Mono")
# The logo is Franklin Gothic; Trebuchet is the closest thing a Mac has.
# Only families that exist are listed -- Qt spends half a second building
# its alias table the first time it is asked for one that doesn't.
if _SYSTEM == "Windows":
    LOGO_FONT_FAMILIES = ["Franklin Gothic Medium", "Trebuchet MS"]
elif _has_font("Trebuchet MS.ttf"):
    LOGO_FONT_FAMILIES = ["Trebuchet MS"]
else:
    LOGO_FONT_FAMILIES = [UI_FONT_FAMILY]


def ui_font(px: int = 11, bold: bool = False, family: str | None = None) -> QFont:
    """Fonts are sized in pixels, not points: Tahoma 8pt at 96 dpi is 11px,
    and a point size would come out a third smaller on a 72 dpi Mac."""
    font = QFont(family or UI_FONT_FAMILY)
    font.setPixelSize(px)
    if bold:
        font.setWeight(QFont.Weight.Bold)
    return font


# --- Windows Classic ---------------------------------------------------------
FACE = "#d4d0c8"
HILIGHT = "#ffffff"
SHADOW = "#808080"
DARK_SHADOW = "#404040"
TEXT_COLOR = "#000000"
GRAY_TEXT = "#808080"
SELECTION = "#0a246a"
TITLE_LEFT = "#0a246a"
TITLE_RIGHT = "#a6caf0"
ERROR_RED = "#c00000"

# Kept for anything still importing the old names.
BODY_BG = FACE

# --- the billboard behind the dialogs ----------------------------------------
BAND_BLUE = "#00309c"
BACKDROP_BLUE = "#5a7edc"
BACKDROP_GLOW = "#86a7ec"
BAND_LINE_LIGHT = "#d9e5fb"
BAND_LINE_ORANGE = "#f99736"
STAGE_DIM = "#c3d3f4"

# --- text mode (VGA palette) -------------------------------------------------
VGA_BLUE = "#0000aa"
VGA_GRAY = "#aaaaaa"
VGA_WHITE = "#ffffff"
VGA_YELLOW = "#ffff55"


def classic_palette() -> QPalette:
    """Pinned so the OS theme (dark mode especially) can't leak in -- Setup
    looks the same everywhere, and the Windows style draws its bevels from
    Light/Midlight/Dark/Shadow."""
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: FACE,
        QPalette.ColorRole.WindowText: TEXT_COLOR,
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: FACE,
        QPalette.ColorRole.Text: TEXT_COLOR,
        QPalette.ColorRole.Button: FACE,
        QPalette.ColorRole.ButtonText: TEXT_COLOR,
        QPalette.ColorRole.Light: HILIGHT,
        QPalette.ColorRole.Midlight: FACE,
        QPalette.ColorRole.Mid: SHADOW,
        QPalette.ColorRole.Dark: SHADOW,
        QPalette.ColorRole.Shadow: DARK_SHADOW,
        QPalette.ColorRole.Highlight: SELECTION,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: "#ffffe1",
        QPalette.ColorRole.ToolTipText: TEXT_COLOR,
        QPalette.ColorRole.PlaceholderText: GRAY_TEXT,
        QPalette.ColorRole.Link: "#0000ff",
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(GRAY_TEXT))
    # Inactive windows keep the same selection colour, like Windows 2000 did.
    pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight,
                 QColor(SELECTION))
    pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText,
                 QColor("#ffffff"))
    return pal


class ClassicStyle(QProxyStyle):
    """Qt's "Windows" style with two fixes.

    Its bevels are drawn with one-device-pixel lines, so on a HiDPI screen
    they come out half as thick as they should and the 3D look vanishes.
    Every primitive is therefore drawn at 1x and scaled up without
    smoothing -- chunky, exactly as XP looks on a modern screen. Text is
    drawn separately and stays sharp.

    And a drop-down list gets a white field, as on Windows 2000, rather
    than the grey of a button.
    """

    # Scroll bar parts are drawControl() calls, not primitives.
    _DOUBLED_CONTROLS = {
        QStyle.ControlElement.CE_ScrollBarAddLine, QStyle.ControlElement.CE_ScrollBarSubLine,
        QStyle.ControlElement.CE_ScrollBarAddPage, QStyle.ControlElement.CE_ScrollBarSubPage,
        QStyle.ControlElement.CE_ScrollBarSlider,
    }

    def __init__(self):
        super().__init__(QStyleFactory.create("Windows"))

    @staticmethod
    def _at_1x(painter, rect, draw):
        device = painter.device()
        dpr = device.devicePixelRatioF() if device is not None else 1.0
        # Below 2x (Windows at 125/150%) nearest-neighbour scaling would make
        # some lines one pixel and some two, which looks worse than thin.
        if dpr < 2 or rect.isEmpty():
            draw(painter)
            return
        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        inner = QPainter(pixmap)
        inner.translate(-rect.topLeft())
        draw(inner)
        inner.end()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(rect.topLeft(), pixmap)
        painter.restore()

    def drawPrimitive(self, element, option, painter, widget=None):
        self._at_1x(painter, option.rect, lambda p: super(ClassicStyle, self)
                    .drawPrimitive(element, option, p, widget))

    def drawControl(self, element, option, painter, widget=None):
        if element in self._DOUBLED_CONTROLS:
            self._at_1x(painter, option.rect, lambda p: super(ClassicStyle, self)
                        .drawControl(element, option, p, widget))
        else:
            super().drawControl(element, option, painter, widget)

    def drawComplexControl(self, control, option, painter, widget=None):
        base = super(ClassicStyle, self)
        if control == QStyle.ComplexControl.CC_ComboBox and not option.editable:
            field = QStyleOptionComboBox(option)
            field.palette.setColor(QPalette.ColorRole.Button,
                                   option.palette.color(QPalette.ColorRole.Base))
            field.subControls = (QStyle.SubControl.SC_ComboBoxFrame
                                 | QStyle.SubControl.SC_ComboBoxEditField)
            arrow = QStyleOptionComboBox(option)
            arrow.subControls = QStyle.SubControl.SC_ComboBoxArrow

            def draw(p):
                base.drawComplexControl(control, field, p, widget)
                base.drawComplexControl(control, arrow, p, widget)
            self._at_1x(painter, option.rect, draw)
            return
        self._at_1x(painter, option.rect,
                    lambda p: base.drawComplexControl(control, option, p, widget))
