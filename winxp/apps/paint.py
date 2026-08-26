from __future__ import annotations

from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..window_manager import XPWindow

PALETTE = [
    "#000000", "#7f7f7f", "#880015", "#ed1c24", "#ff7f27", "#fff200",
    "#22b14c", "#00a2e8", "#3f48cc", "#a349a4",
    "#ffffff", "#c3c3c3", "#b97a57", "#ffaec9", "#ffc90e", "#efe4b0",
    "#b5e61d", "#99d9ea", "#7092be", "#c8bfe7",
]


class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(560, 380)
        self.pixmap = QPixmap(self.size())
        self.pixmap.fill(Qt.GlobalColor.white)
        self.pen_color = QColor("black")
        self.pen_width = 3
        self._last = None

    def set_color(self, color):
        self.pen_color = QColor(color)

    def set_width(self, width):
        self.pen_width = width

    def clear(self):
        self.pixmap.fill(Qt.GlobalColor.white)
        self.update()

    def mousePressEvent(self, ev):
        self._last = ev.position().toPoint()

    def mouseMoveEvent(self, ev):
        if self._last is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            pos = ev.position().toPoint()
            painter = QPainter(self.pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine,
                                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(self._last, pos)
            painter.end()
            self._last = pos
            self.update()

    def mouseReleaseEvent(self, ev):
        self._last = None

    def paintEvent(self, ev):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.pixmap)


class ColorSwatch(QPushButton):
    def __init__(self, color, on_pick):
        super().__init__()
        self.setFixedSize(18, 18)
        self.setStyleSheet(f"background: {color}; border: 1px solid #555;")
        self.clicked.connect(lambda: on_pick(color))


class PaintWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="untitled - Paint", icon_key="paint", size=QSize(680, 500))

        self.canvas = Canvas()

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setMenuBar(self._build_menu())

        body = QHBoxLayout()
        body.setContentsMargins(6, 6, 6, 6)
        body.addWidget(self._build_tools())
        body.addWidget(self.canvas, 1)
        root.addLayout(body)
        root.addWidget(self._build_palette())

        self.set_content_layout(root)

    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar
        bar = QMenuBar()
        file_menu = bar.addMenu("&File")
        new_act = file_menu.addAction("&New")
        new_act.triggered.connect(self.canvas.clear)
        bar.addMenu("&Edit")
        bar.addMenu("&View")
        bar.addMenu("&Image")
        bar.addMenu("&Colors")
        bar.addMenu("&Help")
        return bar

    def _build_tools(self):
        panel = QWidget()
        panel.setFixedWidth(50)
        panel.setStyleSheet("background: #ece9d8; border: 1px solid #aca998;")
        layout = QVBoxLayout(panel)
        for width, label in [(2, "Thin"), (4, "Med"), (8, "Thick"), (14, "Fat")]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, w=width: self.canvas.set_width(w))
            layout.addWidget(btn)
        layout.addStretch(1)
        return panel

    def _build_palette(self):
        panel = QWidget()
        panel.setFixedHeight(40)
        panel.setStyleSheet("background: #ece9d8; border-top: 1px solid #aca998;")
        grid = QGridLayout(panel)
        grid.setContentsMargins(6, 4, 6, 4)
        grid.setSpacing(3)
        for i, color in enumerate(PALETTE):
            swatch = ColorSwatch(color, self.canvas.set_color)
            grid.addWidget(swatch, i // 10, i % 10)
        return panel
