"""DIY color picker — the Luna-styled replacement for a native QColorDialog."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from . import theme
from .xp_dialog import DIALOG_BUTTON_QSS, build_dialog_frame

# Classic Windows XP "basic colors" 48-swatch palette (6 rows x 8 columns).
BASIC_COLORS = [
    "#000000", "#808080", "#800000", "#808000", "#008000", "#008080", "#000080", "#800080",
    "#808040", "#004040", "#0080ff", "#004080", "#4000ff", "#804000", "#ff0000", "#ff8000",
    "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff", "#804040", "#ff8080", "#ffff80",
    "#80ff80", "#80ffff", "#8080ff", "#ff80ff", "#ffffff", "#c0c0c0", "#a6caf0", "#e0e0e0",
    "#ffcc99", "#f0e68c", "#c3f0a6", "#a6f0e0", "#a6c8f0", "#c8a6f0", "#f0a6d0", "#f0a6a6",
    "#e69138", "#b45f06", "#6aa84f", "#38761d", "#3d85c6", "#1155cc", "#674ea7", "#741b47",
]


class Swatch(QPushButton):
    def __init__(self, color, on_pick, size=16):
        super().__init__()
        self.color = color
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"background: {color}; border: 1px solid #555;")
        self.clicked.connect(lambda: on_pick(color))


class XPColorDialog(QDialog):
    def __init__(self, parent, initial: QColor):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self._color = QColor(initial)
        self._accepted = False

        inner = build_dialog_frame(self, "Edit Colors")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(16)

        left = QVBoxLayout()
        basic_label = QLabel("Basic colors:")
        basic_label.setStyleSheet("background: transparent;")
        left.addWidget(basic_label)
        grid = QGridLayout()
        grid.setSpacing(3)
        for i, c in enumerate(BASIC_COLORS):
            sw = Swatch(c, self._pick, size=16)
            grid.addWidget(sw, i // 8, i % 8)
        left.addLayout(grid)
        top.addLayout(left)

        right = QVBoxLayout()
        preview_label = QLabel("Selected color:")
        preview_label.setStyleSheet("background: transparent;")
        right.addWidget(preview_label)
        self.preview = QLabel()
        self.preview.setFixedSize(90, 60)
        self.preview.setStyleSheet("border: 1px solid #555;")
        right.addWidget(self.preview)

        rgb_grid = QGridLayout()
        rgb_grid.setSpacing(4)
        self.spins = {}
        for row, channel in enumerate(("Red", "Green", "Blue")):
            lbl = QLabel(channel + ":")
            lbl.setStyleSheet("background: transparent;")
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.valueChanged.connect(self._on_spin_changed)
            rgb_grid.addWidget(lbl, row, 0)
            rgb_grid.addWidget(spin, row, 1)
            self.spins[channel] = spin
        right.addLayout(rgb_grid)
        right.addStretch(1)
        top.addLayout(right)

        root.addLayout(top)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("OK")
        ok_btn.setMinimumWidth(75)
        ok_btn.clicked.connect(self._accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(75)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        inner.addWidget(body)
        self._sync_spins()
        self._update_preview()

    def _pick(self, hexcolor):
        self._color = QColor(hexcolor)
        self._sync_spins()
        self._update_preview()

    def _sync_spins(self):
        for spin in self.spins.values():
            spin.blockSignals(True)
        self.spins["Red"].setValue(self._color.red())
        self.spins["Green"].setValue(self._color.green())
        self.spins["Blue"].setValue(self._color.blue())
        for spin in self.spins.values():
            spin.blockSignals(False)

    def _on_spin_changed(self, _value):
        self._color = QColor(
            self.spins["Red"].value(), self.spins["Green"].value(), self.spins["Blue"].value()
        )
        self._update_preview()

    def _update_preview(self):
        self.preview.setStyleSheet(f"background: {self._color.name()}; border: 1px solid #555;")

    def _accept(self):
        self._accepted = True
        self.accept()

    @staticmethod
    def get_color(parent, initial: QColor) -> QColor | None:
        dlg = XPColorDialog(parent, initial)
        dlg.exec()
        return dlg._color if dlg._accepted else None
