"""MacroHard WordArt 3D -- a deliberately hideous manual 3D modeling sandbox.

Users place named points (A, B, ... Z, A1, B1, ...), connect them with lines,
and fill panes (polygons) with color. The result gets rasterized and dropped
into the document as an image, same as real WordArt would.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from .. import theme
from ..color_dialog import XPColorDialog
from ..xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def next_point_name(index: int) -> str:
    if index < 26:
        return LETTERS[index]
    cycle, letter_i = divmod(index - 26, 26)
    return f"{LETTERS[letter_i]}{cycle + 1}"


@dataclass
class Pane:
    names: list
    color: QColor


class Scene3D:
    def __init__(self):
        self.points: dict[str, tuple[float, float, float]] = {}
        self.lines: list[tuple[str, str]] = []
        self.panes: list[Pane] = []

    def next_name(self) -> str:
        return next_point_name(len(self.points))

    def add_point(self, name, x, y, z):
        self.points[name] = (x, y, z)

    def remove_point(self, name):
        self.points.pop(name, None)
        self.lines = [l for l in self.lines if name not in l]
        self.panes = [p for p in self.panes if name not in p.names]

    def add_line(self, a, b):
        if a in self.points and b in self.points and a != b:
            self.lines.append((a, b))
            return True
        return False

    def add_pane(self, names, color):
        if len(names) >= 3 and all(n in self.points for n in names):
            self.panes.append(Pane(names, color))
            return True
        return False


class Canvas3D(QWidget):
    zoom_changed = pyqtSignal(float)

    def __init__(self, scene: Scene3D, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.yaw = 35.0
        self.pitch = -20.0
        self.zoom = 1.0
        self._drag_pos = None
        self.setMinimumSize(360, 360)
        self.setStyleSheet("background: #111;")

    def mousePressEvent(self, e):
        self._drag_pos = e.position()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None:
            delta = e.position() - self._drag_pos
            self.yaw += delta.x() * 0.4
            self.pitch = max(-89.0, min(89.0, self.pitch - delta.y() * 0.4))
            self._drag_pos = e.position()
            self.update()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def wheelEvent(self, e):
        self.zoom *= 1.1 if e.angleDelta().y() > 0 else 0.9
        self.zoom = max(0.2, min(5.0, self.zoom))
        self.zoom_changed.emit(self.zoom)
        self.update()

    def _project_all(self):
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        cyaw, syaw = math.cos(yaw), math.sin(yaw)
        cpitch, spitch = math.cos(pitch), math.sin(pitch)
        w, h = self.width(), self.height()
        scale = min(w, h) * 0.28 * self.zoom
        cx, cy = w / 2, h / 2
        dist = 4.0

        projected = {}
        depths = {}
        for name, (x, y, z) in self.scene.points.items():
            x1 = x * cyaw + z * syaw
            z1 = -x * syaw + z * cyaw
            y1 = y * cpitch - z1 * spitch
            z2 = y * spitch + z1 * cpitch
            depth = max(z2 + dist, 0.1)
            f = dist / depth
            projected[name] = QPointF(cx + x1 * scale * f, cy - y1 * scale * f)
            depths[name] = depth
        return projected, depths

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#111"))
        if not self.scene.points:
            p.setPen(QColor("#888"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Add points to begin your masterpiece")
            p.end()
            return

        projected, depths = self._project_all()

        panes_sorted = sorted(
            self.scene.panes,
            key=lambda pane: -sum(depths.get(n, 0) for n in pane.names) / max(len(pane.names), 1),
        )
        for pane in panes_sorted:
            pts = [projected[n] for n in pane.names if n in projected]
            if len(pts) < 3:
                continue
            path = QPainterPath()
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            path.closeSubpath()
            p.setBrush(pane.color)
            p.setPen(QPen(pane.color.darker(150), 1))
            p.drawPath(path)

        p.setPen(QPen(QColor("#7fd0ff"), 2))
        for a, b in self.scene.lines:
            if a in projected and b in projected:
                p.drawLine(projected[a], projected[b])

        p.setPen(QPen(QColor("#ffd23f"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for pt in projected.values():
            p.drawPoint(pt)

        p.setPen(QColor("white"))
        for name, pt in projected.items():
            p.drawText(pt + QPointF(6, -6), name)
        p.end()


class WordArt3DDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.resize(780, 540)
        self.scene = Scene3D()
        self.result_image: QImage | None = None
        self.pane_color = QColor("#3fa129")

        inner = build_dialog_frame(self, "MacroHard WordArt 3D Sandbox")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        inner.addWidget(body)

        root = QHBoxLayout(body)

        controls = QVBoxLayout()

        controls.addWidget(QLabel("<b>Points</b> -- Point &lt;name&gt; (x, y, z)"))
        pt_row = QHBoxLayout()
        self.pt_name_label = QLabel("A")
        self.pt_name_label.setStyleSheet("font-weight:bold; min-width:18px;")
        self.pt_x = self._spin()
        self.pt_y = self._spin()
        self.pt_z = self._spin()
        add_pt_btn = QPushButton("Add Point")
        add_pt_btn.clicked.connect(self._add_point)
        pt_row.addWidget(QLabel("Point"))
        pt_row.addWidget(self.pt_name_label)
        pt_row.addWidget(self.pt_x)
        pt_row.addWidget(self.pt_y)
        pt_row.addWidget(self.pt_z)
        controls.addLayout(pt_row)
        controls.addWidget(add_pt_btn)

        self.points_list = QListWidget()
        self.points_list.setMaximumHeight(90)
        controls.addWidget(self.points_list)
        remove_pt_btn = QPushButton("Remove Selected Point")
        remove_pt_btn.clicked.connect(self._remove_point)
        controls.addWidget(remove_pt_btn)

        controls.addWidget(QLabel("<b>Lines</b> -- [A, B] comma separated"))
        line_row = QHBoxLayout()
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("A, B")
        add_line_btn = QPushButton("Add Line")
        add_line_btn.clicked.connect(self._add_line)
        line_row.addWidget(self.line_edit)
        line_row.addWidget(add_line_btn)
        controls.addLayout(line_row)
        self.lines_list = QListWidget()
        self.lines_list.setMaximumHeight(70)
        controls.addWidget(self.lines_list)

        controls.addWidget(QLabel("<b>Fill Panes with Color</b> -- A, B, C, D"))
        pane_row = QHBoxLayout()
        self.pane_edit = QLineEdit()
        self.pane_edit.setPlaceholderText("A, B, C, D")
        self.pane_color_btn = QPushButton("Color")
        self._style_color_btn()
        self.pane_color_btn.clicked.connect(self._pick_pane_color)
        add_pane_btn = QPushButton("Fill Pane")
        add_pane_btn.clicked.connect(self._add_pane)
        pane_row.addWidget(self.pane_edit)
        pane_row.addWidget(self.pane_color_btn)
        pane_row.addWidget(add_pane_btn)
        controls.addLayout(pane_row)
        self.panes_list = QListWidget()
        self.panes_list.setMaximumHeight(70)
        controls.addWidget(self.panes_list)

        controls.addWidget(QLabel("<b>View</b>"))
        self.auto_rotate_check = QCheckBox("Auto-rotate demo")
        self.auto_rotate_check.toggled.connect(self._set_auto_rotate)
        controls.addWidget(self.auto_rotate_check)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(20, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_slider_zoom)
        zoom_row.addWidget(self.zoom_slider)
        controls.addLayout(zoom_row)

        self._auto_rotate_timer = QTimer(self)
        self._auto_rotate_timer.setInterval(30)
        self._auto_rotate_timer.timeout.connect(self._auto_rotate_tick)

        controls.addStretch(1)
        hint = QLabel("Drag canvas to orbit. Scroll or use the slider to zoom.")
        hint.setStyleSheet("color:#666; font-size:11px;")
        controls.addWidget(hint)

        btn_row = QHBoxLayout()
        insert_btn = QPushButton("Insert into Document")
        insert_btn.clicked.connect(self._insert)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(insert_btn)
        btn_row.addWidget(cancel_btn)
        controls.addLayout(btn_row)

        controls_widget = QWidget()
        controls_widget.setLayout(controls)
        controls_widget.setFixedWidth(320)

        self.canvas = Canvas3D(self.scene)
        self.canvas.zoom_changed.connect(self._on_canvas_zoom)

        root.addWidget(controls_widget)
        root.addWidget(self.canvas, 1)

    def _spin(self):
        box = QDoubleSpinBox()
        box.setRange(-50.0, 50.0)
        box.setDecimals(2)
        return box

    def _set_auto_rotate(self, enabled):
        if enabled:
            self._auto_rotate_timer.start()
        else:
            self._auto_rotate_timer.stop()

    def _auto_rotate_tick(self):
        self.canvas.yaw = (self.canvas.yaw + 1.5) % 360.0
        self.canvas.update()

    def _on_slider_zoom(self, value):
        self.canvas.zoom = value / 100.0
        self.canvas.update()

    def _on_canvas_zoom(self, zoom):
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(int(zoom * 100))
        self.zoom_slider.blockSignals(False)

    def _style_color_btn(self):
        self.pane_color_btn.setStyleSheet(f"background:{self.pane_color.name()};")

    def _pick_pane_color(self):
        color = XPColorDialog.get_color(self, self.pane_color)
        if color is not None:
            self.pane_color = color
            self._style_color_btn()

    def _add_point(self):
        name = self.scene.next_name()
        x, y, z = self.pt_x.value(), self.pt_y.value(), self.pt_z.value()
        self.scene.add_point(name, x, y, z)
        self.points_list.addItem(f"{name} ({x:g}, {y:g}, {z:g})")
        self.pt_x.setValue(0)
        self.pt_y.setValue(0)
        self.pt_z.setValue(0)
        self.pt_name_label.setText(self.scene.next_name())
        self.canvas.update()

    def _remove_point(self):
        row = self.points_list.currentRow()
        if row < 0:
            return
        name = self.points_list.item(row).text().split(" ")[0]
        self.scene.remove_point(name)
        self.points_list.takeItem(row)
        self._rebuild_lines_panes_lists()
        self.pt_name_label.setText(self.scene.next_name())
        self.canvas.update()

    def _rebuild_lines_panes_lists(self):
        self.lines_list.clear()
        for a, b in self.scene.lines:
            self.lines_list.addItem(f"[{a}, {b}]")
        self.panes_list.clear()
        for pane in self.scene.panes:
            self.panes_list.addItem(f"[{', '.join(pane.names)}] {pane.color.name()}")

    def _parse_names(self, text):
        return [t.strip().upper() for t in text.split(",") if t.strip()]

    def _add_line(self):
        names = self._parse_names(self.line_edit.text())
        if len(names) != 2:
            XPMessageBox.warning(self, "MacroHard WordArt", "Enter exactly two point names, e.g. A, B")
            return
        a, b = names
        if not self.scene.add_line(a, b):
            XPMessageBox.warning(self, "MacroHard WordArt", f"Unknown point(s): {a}, {b}")
            return
        self.lines_list.addItem(f"[{a}, {b}]")
        self.line_edit.clear()
        self.canvas.update()

    def _add_pane(self):
        names = self._parse_names(self.pane_edit.text())
        if len(names) < 3:
            XPMessageBox.warning(self, "MacroHard WordArt", "Need at least 3 points to fill a pane.")
            return
        if not self.scene.add_pane(names, QColor(self.pane_color)):
            XPMessageBox.warning(self, "MacroHard WordArt", f"Unknown point(s) in: {', '.join(names)}")
            return
        self.panes_list.addItem(f"[{', '.join(names)}] {self.pane_color.name()}")
        self.pane_edit.clear()
        self.canvas.update()

    def _insert(self):
        if not self.scene.points:
            XPMessageBox.warning(self, "MacroHard WordArt", "Add at least one point first.")
            return
        image = QImage(self.canvas.size(), QImage.Format.Format_ARGB32)
        image.fill(QColor("#111"))
        painter = QPainter(image)
        self.canvas.render(painter)
        painter.end()
        self.result_image = image
        self.accept()
