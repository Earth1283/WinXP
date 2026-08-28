from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygon
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QSlider, QToolButton,
    QVBoxLayout, QWidget,
)


NAV_QSS = """
QToolButton {
    color: #dcecff; background: transparent; border: 0; border-left: 4px solid transparent;
    font-size: 11px; font-weight: bold; padding: 7px 8px; text-align: left;
}
QToolButton:hover { background: #153b61; border-left-color: #e99124; }
QToolButton:checked { background: #28577f; border-left-color: #ffb334; color: white; }
"""

SLIDER_QSS = """
QSlider::groove:horizontal { height: 4px; background: #5d6e7f; border: 1px solid #17283a; }
QSlider::sub-page:horizontal { background: #75a9d7; }
QSlider::handle:horizontal {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:0.45 #dce5ed,stop:1 #7f96aa);
    border: 1px solid #263a4d; width: 11px; margin: -5px 0; border-radius: 2px;
}
"""


class NavButton(QToolButton):
    def __init__(self, text, key):
        super().__init__()
        self.key = key
        self.setText(text)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self.setMinimumHeight(34)
        self.setStyleSheet(NAV_QSS)


class SectionHeader(QWidget):
    def __init__(self, title, subtitle=""):
        super().__init__()
        self.setObjectName("sectionHeader")
        self.setStyleSheet("""
            QWidget#sectionHeader { background: #dfeaf3; border-bottom: 1px solid #8ca2b5; }
            QLabel { background: transparent; color: #183a59; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(0)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)
        if subtitle:
            note = QLabel(subtitle)
            note.setStyleSheet("font-size: 10px; color: #526b80;")
            layout.addWidget(note)


class Visualizer(QWidget):
    modeChanged = pyqtSignal(str)

    MODES = ("Bars", "Scope", "Ambience")

    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 180)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playing = False
        self.mode = "Bars"
        self.phase = 0.0
        self.bars = [4] * 32
        self.particles = [(random.random(), random.random(), random.random()) for _ in range(32)]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(75)

    def set_playing(self, playing):
        self.playing = playing

    def set_mode(self, mode):
        if mode in self.MODES:
            self.mode = mode
            self.modeChanged.emit(mode)
            self.update()

    def cycle_mode(self):
        index = (self.MODES.index(self.mode) + 1) % len(self.MODES)
        self.set_mode(self.MODES[index])

    def mouseDoubleClickEvent(self, event):
        self.cycle_mode()

    def tick(self):
        speed = 0.22 if self.playing else 0.045
        self.phase += speed
        if self.playing:
            self.bars = [max(4, min(100, value + random.randint(-26, 30))) for value in self.bars]
        else:
            self.bars = [max(3, value - 6) for value in self.bars]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#06182c"))
        gradient.setColorAt(1, QColor("#00060d"))
        painter.fillRect(self.rect(), gradient)
        if self.mode == "Bars":
            self.paint_bars(painter)
        elif self.mode == "Scope":
            self.paint_scope(painter)
        else:
            self.paint_ambience(painter)
        painter.setPen(QColor("#8ca4ba"))
        painter.drawText(9, 17, self.mode)
        painter.setPen(QColor("#263e52"))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def paint_bars(self, painter):
        width = self.width() / len(self.bars)
        for index, value in enumerate(self.bars):
            height = int((self.height() - 24) * value / 100)
            x = int(index * width) + 2
            for y in range(0, height, 4):
                ratio = y / max(1, height)
                color = QColor("#65d7ff" if ratio > .65 else "#2184c7" if ratio > .28 else "#174a87")
                painter.fillRect(x, self.height() - y - 5, max(1, int(width) - 3), 2, color)

    def paint_scope(self, painter):
        path = QPainterPath()
        middle = self.height() / 2
        amplitude = self.height() * (.30 if self.playing else .04)
        path.moveTo(0, middle)
        for x in range(self.width()):
            wave = math.sin(x * .045 + self.phase) + .45 * math.sin(x * .12 - self.phase * 1.7)
            path.lineTo(x, middle + wave * amplitude * .55)
        painter.setPen(QPen(QColor("#58d4ff"), 2))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(30, 110, 170, 90), 1))
        painter.drawLine(0, int(middle), self.width(), int(middle))

    def paint_ambience(self, painter):
        center = QPointF(self.width() / 2, self.height() / 2)
        base = min(self.width(), self.height())
        for index in range(9, 0, -1):
            pulse = math.sin(self.phase + index * .6) * 7 if self.playing else 0
            radius = base * index / 20 + pulse
            color = QColor(20, 100 + index * 8, 175 + index * 6, 28 + index * 8)
            painter.setPen(QPen(color, 2))
            painter.drawEllipse(center, radius, radius * .58)
        for x, y, seed in self.particles:
            brightness = int(80 + 170 * abs(math.sin(self.phase * seed + seed * 8)))
            painter.setBrush(QColor(80, 190, 255, brightness))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(x * self.width(), y * self.height()), 2, 2)


class TransportButton(QToolButton):
    def __init__(self, glyph, diameter=30):
        super().__init__()
        self.glyph = glyph
        self.setFixedSize(diameter, diameter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(glyph.title())

    def sizeHint(self):
        return QSize(self.width(), self.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        top = QColor("#f8fbfd") if not self.isDown() else QColor("#9eb3c6")
        bottom = QColor("#768fa6") if not self.isDown() else QColor("#526d84")
        gradient = QLinearGradient(
            float(rect.left()), float(rect.top()),
            float(rect.left()), float(rect.bottom()),
        )
        gradient.setColorAt(0, top)
        gradient.setColorAt(1, bottom)
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#14283a"), 1))
        painter.drawEllipse(rect)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#10263a"))
        center_x, center_y = rect.center().x(), rect.center().y()
        if self.glyph == "play":
            painter.drawPolygon(QPolygon([QPoint(center_x - 4, center_y - 7),
                                          QPoint(center_x - 4, center_y + 7),
                                          QPoint(center_x + 7, center_y)]))
        elif self.glyph == "pause":
            painter.drawRect(center_x - 6, center_y - 7, 4, 14)
            painter.drawRect(center_x + 2, center_y - 7, 4, 14)
        elif self.glyph == "stop":
            painter.drawRect(center_x - 5, center_y - 5, 10, 10)
        elif self.glyph == "prev":
            painter.drawRect(center_x - 7, center_y - 6, 2, 12)
            painter.drawPolygon(QPolygon([QPoint(center_x + 6, center_y - 6),
                                          QPoint(center_x + 6, center_y + 6),
                                          QPoint(center_x - 5, center_y)]))
        elif self.glyph == "next":
            painter.drawPolygon(QPolygon([QPoint(center_x - 6, center_y - 6),
                                          QPoint(center_x - 6, center_y + 6),
                                          QPoint(center_x + 5, center_y)]))
            painter.drawRect(center_x + 5, center_y - 6, 2, 12)


class PlaybackDisplay(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(43)
        self.title = "No media selected"
        self.status = "Ready"
        self.time = "0:00"

    def set_values(self, title=None, status=None, time=None):
        if title is not None:
            self.title = title
        if status is not None:
            self.status = status
        if time is not None:
            self.time = time
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#07131e"))
        painter.setPen(QPen(QColor("#375166"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.setPen(QColor("#b8d88c"))
        font = painter.font()
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(8, 16, self.title[:52])
        font.setPixelSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#789c79"))
        painter.drawText(8, 33, self.status)
        painter.setPen(QColor("#c8e699"))
        painter.drawText(self.rect().adjusted(0, 0, -8, -7),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, self.time)


class EqualizerPanel(QWidget):
    enabledChanged = pyqtSignal(bool)

    FREQUENCIES = ("31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k")
    PRESETS = {
        "Default": [0] * 10,
        "Rock": [4, 3, 1, -1, -2, 0, 2, 4, 5, 5],
        "Pop": [-1, 2, 4, 4, 1, -1, -2, -2, -1, -1],
        "Jazz": [3, 2, 1, 2, -1, -1, 0, 2, 3, 4],
        "Classical": [4, 3, 2, 1, -1, -1, 0, 2, 3, 4],
        "Laptop Speakers": [8, 8, 5, 1, -3, -5, -8, -8, -8, -8],
    }

    def __init__(self):
        super().__init__()
        self.setFixedHeight(150)
        self.setStyleSheet("background:#d8e2ea;border-top:1px solid #8195a7")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 5)
        root.setSpacing(2)
        top = QHBoxLayout()
        enabled = QCheckBox("Turn on")
        enabled.setChecked(True)
        enabled.toggled.connect(self.enabledChanged)
        top.addWidget(enabled)
        top.addWidget(QLabel("Graphic Equalizer"))
        top.addStretch(1)
        self.presets = QComboBox()
        self.presets.addItems(self.PRESETS)
        self.presets.currentTextChanged.connect(self.apply_preset)
        top.addWidget(QLabel("Preset:"))
        top.addWidget(self.presets)
        root.addLayout(top)
        sliders = QHBoxLayout()
        sliders.setSpacing(5)
        self.controls = []
        for frequency in self.FREQUENCIES:
            column = QVBoxLayout()
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-10, 10)
            slider.setValue(0)
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.setStyleSheet("QSlider::groove:vertical{width:3px;background:#6c8294}"
                                 "QSlider::handle:vertical{height:8px;margin:0 -4px;background:#f5f7f8;border:1px solid #40586c}")
            column.addWidget(slider, 1, Qt.AlignmentFlag.AlignHCenter)
            label = QLabel(frequency)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background:transparent;font-size:9px")
            column.addWidget(label)
            sliders.addLayout(column)
            self.controls.append(slider)
        root.addLayout(sliders, 1)

    def apply_preset(self, name):
        for slider, value in zip(self.controls, self.PRESETS[name]):
            slider.setValue(value)
