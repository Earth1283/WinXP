"""Image > Adjustments.

The two that carry the whole menu -- Levels and Curves -- get real interactive
widgets: a live histogram with draggable black/gamma/white triangles, and a
curve grid you drag control points around on.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget,
)

from . import imageops as ops
from ...color_dialog import XPColorDialog
from ...xp_dialog import XPMessageBox
from .dialogs import PCDialog, PreviewBox, SliderRow, ZoomRow, _lbl, _spin, group_box


class HistogramView(QWidget):
    def __init__(self, height=100):
        super().__init__()
        self.setFixedHeight(height)
        self.setMinimumWidth(258)
        self.hist = [0] * 256
        self.tint = QColor("#404040")

    def set_hist(self, hist, tint="#404040"):
        self.hist = hist
        self.tint = QColor(tint)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ffffff"))
        peak = max(self.hist) or 1
        w = self.width() - 2
        p.setPen(QPen(self.tint, 1))
        for i, v in enumerate(self.hist):
            x = 1 + i * w / 256
            h = (v / peak) * (self.height() - 2)
            p.drawLine(QPointF(x, self.height() - 1), QPointF(x, self.height() - 1 - h))
        p.setPen(QPen(QColor("#808080"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()


class LevelsSlider(QWidget):
    """Black point / gamma / white point triangles under the histogram."""
    changed = pyqtSignal()

    def __init__(self, output=False):
        super().__init__()
        self.setFixedHeight(26)
        self.setMinimumWidth(258)
        self.output = output
        self.black = 0
        self.white = 255
        self.gamma = 1.0
        self._drag = None

    def _positions(self):
        w = self.width() - 2
        gx = self.black + (self.white - self.black) * (0.5 ** (1 / max(0.01, self.gamma)))
        return (1 + self.black * w / 255, 1 + gx * w / 255, 1 + self.white * w / 255)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bar = QRectF(1, 0, self.width() - 2, 10)
        grad = QLinearGradient(bar.left(), 0, bar.right(), 0)
        grad.setColorAt(0, QColor("black"))
        grad.setColorAt(1, QColor("white"))
        p.fillRect(bar, QBrush(grad))
        p.setPen(QPen(QColor("#808080"), 1))
        p.drawRect(bar)
        bx, gx, wx = self._positions()
        marks = ((bx, "#000000"), (wx, "#ffffff")) if self.output else \
                ((bx, "#000000"), (gx, "#808080"), (wx, "#ffffff"))
        for x, colour in marks:
            p.setBrush(QColor(colour))
            p.setPen(QPen(QColor("#303030"), 1))
            p.drawPolygon(QPolygonF([QPointF(x, 12), QPointF(x - 5, 22), QPointF(x + 5, 22)]))
        p.end()

    def mousePressEvent(self, ev):
        bx, gx, wx = self._positions()
        candidates = [("black", bx), ("white", wx)]
        if not self.output:
            candidates.insert(1, ("gamma", gx))
        self._drag = min(candidates, key=lambda c: abs(c[1] - ev.position().x()))[0]
        self.mouseMoveEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag is None:
            return
        w = self.width() - 2
        v = max(0, min(255, int((ev.position().x() - 1) * 255 / max(1, w))))
        if self._drag == "black":
            self.black = min(v, self.white - 1)
        elif self._drag == "white":
            self.white = max(v, self.black + 1)
        else:
            span = max(1, self.white - self.black)
            t = max(0.02, min(0.98, (v - self.black) / span))
            self.gamma = max(0.10, min(9.99, math.log(0.5) / math.log(t)))
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, ev):
        self._drag = None


class LevelsDialog(PCDialog):
    def __init__(self, parent, source: QImage, apply_fn):
        super().__init__(parent, "Levels")
        self.source = source
        self.apply_fn = apply_fn
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)

        row = QHBoxLayout()
        row.addWidget(_lbl("Channel:"))
        self.channel = QComboBox()
        self.channel.addItems(["RGB", "Red", "Green", "Blue"])
        self.channel.currentTextChanged.connect(self._channel_changed)
        row.addWidget(self.channel, 1)
        self.content.addLayout(row)

        self.hist = HistogramView()
        self.content.addWidget(self.hist)

        self.content.addWidget(_lbl("Input Levels:"))
        self.slider = LevelsSlider()
        self.slider.changed.connect(self._from_slider)
        self.content.addWidget(self.slider)

        in_row = QHBoxLayout()
        self.in_black = _spin(0, 255, 0, "")
        self.gamma_box = QComboBox()
        self.gamma_box.setEditable(True)
        self.gamma_box.addItems(["0.10", "0.50", "1.00", "1.50", "2.20"])
        self.gamma_box.setCurrentText("1.00")
        self.in_white = _spin(0, 255, 255, "")
        for w in (self.in_black, self.gamma_box, self.in_white):
            w.setFixedWidth(64)
            in_row.addWidget(w)
            in_row.addStretch(1)
        self.content.addLayout(in_row)

        self.content.addWidget(_lbl("Output Levels:"))
        self.out_slider = LevelsSlider(output=True)
        self.out_slider.changed.connect(self._from_slider)
        self.content.addWidget(self.out_slider)
        out_row = QHBoxLayout()
        self.out_black = _spin(0, 255, 0, "")
        self.out_white = _spin(0, 255, 255, "")
        for w in (self.out_black, self.out_white):
            w.setFixedWidth(64)
            out_row.addWidget(w)
            out_row.addStretch(1)
        self.content.addLayout(out_row)

        for w in (self.in_black, self.in_white, self.out_black, self.out_white):
            w.valueChanged.connect(self._from_spin)
        self.gamma_box.currentTextChanged.connect(self._from_spin)

        self.add_ok_cancel()
        self.add_button("Load...", lambda: XPMessageBox.information(
            self, "Levels", "Could not load the levels file because it does not exist."))
        self.add_button("Save...", lambda: XPMessageBox.information(
            self, "Levels", "Levels settings saved to a file you will never find again."))
        self.add_button("Auto", self._auto)
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()
        self._channel_changed("RGB")

    def _channel_changed(self, name):
        hl, hr, hg, hb = ops.histogram(self.source)
        hist, tint = {"RGB": (hl, "#404040"), "Red": (hr, "#c02020"),
                      "Green": (hg, "#20a020"), "Blue": (hb, "#2040c0")}[name]
        self.hist.set_hist(hist, tint)
        self._refresh()

    def _auto(self):
        lo, hi = ops._channel_range(self.hist.hist)
        self.in_black.setValue(lo)
        self.in_white.setValue(hi)

    def _from_slider(self):
        self.in_black.blockSignals(True)
        self.in_white.blockSignals(True)
        self.gamma_box.blockSignals(True)
        self.in_black.setValue(self.slider.black)
        self.in_white.setValue(self.slider.white)
        self.gamma_box.setCurrentText(f"{self.slider.gamma:.2f}")
        self.out_black.setValue(self.out_slider.black)
        self.out_white.setValue(self.out_slider.white)
        self.in_black.blockSignals(False)
        self.in_white.blockSignals(False)
        self.gamma_box.blockSignals(False)
        self._timer.start(90)

    def _from_spin(self, *_):
        self.slider.black = self.in_black.value()
        self.slider.white = max(self.in_black.value() + 1, self.in_white.value())
        try:
            self.slider.gamma = float(self.gamma_box.currentText())
        except ValueError:
            self.slider.gamma = 1.0
        self.out_slider.black = self.out_black.value()
        self.out_slider.white = self.out_white.value()
        self.slider.update()
        self.out_slider.update()
        self._timer.start(90)

    def values(self):
        try:
            gamma = float(self.gamma_box.currentText())
        except ValueError:
            gamma = 1.0
        return dict(in_black=self.in_black.value(), gamma=gamma,
                    in_white=self.in_white.value(), out_black=self.out_black.value(),
                    out_white=self.out_white.value(), channel=self.channel.currentText())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class CurveEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, size=228):
        super().__init__()
        self.setFixedSize(size, size)
        self.points = [(0, 0), (255, 255)]
        self._drag = None
        self.inverted = False

    def _to_view(self, x, y):
        s = self.width() - 1
        return QPointF(x * s / 255, s - y * s / 255)

    def _from_view(self, pos):
        s = self.width() - 1
        return (max(0, min(255, int(pos.x() * 255 / s))),
                max(0, min(255, int((s - pos.y()) * 255 / s))))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        s = self.width() - 1
        p.setPen(QPen(QColor("#d0d0d0"), 1))
        for i in range(1, 4):
            p.drawLine(QPointF(i * s / 4, 0), QPointF(i * s / 4, s))
            p.drawLine(QPointF(0, i * s / 4), QPointF(s, i * s / 4))
        p.setPen(QPen(QColor("#c0c0c0"), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(0, s), QPointF(s, 0))

        lut = ops.curve_lut(self.points)
        path = QPainterPath(self._to_view(0, lut[0]))
        for x in range(1, 256):
            path.lineTo(self._to_view(x, lut[x]))
        p.setPen(QPen(QColor("#101010"), 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        p.setPen(QPen(QColor("#101010"), 1))
        for i, (x, y) in enumerate(self.points):
            v = self._to_view(x, y)
            p.setBrush(QColor("#101010") if i != self._drag else QColor("#ffffff"))
            p.drawRect(QRectF(v.x() - 3, v.y() - 3, 6, 6))
        p.setPen(QPen(QColor("#808080"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

    def mousePressEvent(self, ev):
        x, y = self._from_view(ev.position())
        for i, (px, py) in enumerate(self.points):
            v = self._to_view(px, py)
            if abs(v.x() - ev.position().x()) < 6 and abs(v.y() - ev.position().y()) < 6:
                if ev.modifiers() & Qt.KeyboardModifier.ControlModifier and 0 < i < len(self.points) - 1:
                    del self.points[i]
                    self.changed.emit()
                    self.update()
                    return
                self._drag = i
                self.update()
                return
        self.points.append((x, y))
        self.points.sort()
        self._drag = self.points.index((x, y))
        self.changed.emit()
        self.update()

    def mouseMoveEvent(self, ev):
        if self._drag is None:
            return
        x, y = self._from_view(ev.position())
        i = self._drag
        if i == 0:
            x = 0
        elif i == len(self.points) - 1:
            x = 255
        else:
            x = max(self.points[i - 1][0] + 1, min(self.points[i + 1][0] - 1, x))
        self.points[i] = (x, y)
        self.changed.emit()
        self.update()

    def mouseReleaseEvent(self, ev):
        self._drag = None
        self.update()

    def reset(self):
        self.points = [(0, 0), (255, 255)]
        self.changed.emit()
        self.update()


class CurvesDialog(PCDialog):
    def __init__(self, parent, source: QImage, apply_fn):
        super().__init__(parent, "Curves")
        self.apply_fn = apply_fn
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)

        row = QHBoxLayout()
        row.addWidget(_lbl("Channel:"))
        self.channel = QComboBox()
        self.channel.addItems(["RGB", "Red", "Green", "Blue"])
        self.channel.currentTextChanged.connect(lambda _: self._timer.start(60))
        row.addWidget(self.channel, 1)
        self.content.addLayout(row)

        self.editor = CurveEditor()
        self.editor.changed.connect(lambda: self._timer.start(90))
        self.content.addWidget(self.editor, 0, Qt.AlignmentFlag.AlignHCenter)

        hint = QLabel("Click the curve to add a point; Ctrl-click a point to remove it.")
        hint.setStyleSheet("background: transparent; color: #555; font-size: 10px;")
        self.content.addWidget(hint)

        self.add_ok_cancel()
        self.add_button("Smooth", self._smooth)
        self.add_button("Reset", self.editor.reset)
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()
        self._refresh()

    def _smooth(self):
        pts = self.editor.points
        if len(pts) < 3:
            return
        smoothed = [pts[0]]
        for i in range(1, len(pts) - 1):
            x = pts[i][0]
            y = (pts[i - 1][1] + pts[i][1] * 2 + pts[i + 1][1]) // 4
            smoothed.append((x, y))
        smoothed.append(pts[-1])
        self.editor.points = smoothed
        self.editor.update()
        self._refresh()

    def values(self):
        return dict(points=list(self.editor.points), channel=self.channel.currentText())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class HueSaturationDialog(PCDialog):
    def __init__(self, parent, apply_fn):
        super().__init__(parent, "Hue/Saturation")
        self.apply_fn = apply_fn
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)

        row = QHBoxLayout()
        row.addWidget(_lbl("Edit:"))
        self.edit = QComboBox()
        self.edit.addItems(["Master", "Reds", "Yellows", "Greens", "Cyans",
                            "Blues", "Magentas"])
        self.edit.currentTextChanged.connect(lambda _: self._timer.start(60))
        row.addWidget(self.edit, 1)
        self.content.addLayout(row)

        self.hue = SliderRow("Hue:", -180, 180, 0)
        self.sat = SliderRow("Saturation:", -100, 100, 0)
        self.light = SliderRow("Lightness:", -100, 100, 0)
        for w in (self.hue, self.sat, self.light):
            w.changed.connect(lambda: self._timer.start(140))
            self.content.addWidget(w)

        self.content.addWidget(_HueStrip())
        self.colorize = QCheckBox("Colorize")
        self.colorize.setStyleSheet("background: transparent;")
        self.colorize.toggled.connect(lambda _: self._timer.start(60))
        self.content.addWidget(self.colorize)

        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()

    def values(self):
        return dict(hue=self.hue.value(), saturation=self.sat.value(),
                    lightness=self.light.value(), colorize=self.colorize.isChecked(),
                    range_name=self.edit.currentText())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class _HueStrip(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(14)

    def paintEvent(self, ev):
        p = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        for i in range(7):
            grad.setColorAt(i / 6, QColor.fromHsv(int(i * 60) % 360, 255, 255))
        p.fillRect(self.rect(), QBrush(grad))
        p.setPen(QPen(QColor("#808080"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()


class ColorBalanceDialog(PCDialog):
    def __init__(self, parent, apply_fn):
        super().__init__(parent, "Color Balance")
        self.apply_fn = apply_fn
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)
        self.values_by_range = {"Shadows": [0, 0, 0], "Midtones": [0, 0, 0],
                                "Highlights": [0, 0, 0]}

        frame, box = group_box("Color Balance")
        row = QHBoxLayout()
        row.addWidget(_lbl("Color Levels:"))
        self.readout = QLabel("0   0   0")
        self.readout.setStyleSheet("background: transparent;")
        row.addWidget(self.readout)
        row.addStretch(1)
        box.addLayout(row)

        self.sliders = []
        for left, right in (("Cyan", "Red"), ("Magenta", "Green"), ("Yellow", "Blue")):
            holder = QWidget()
            h = QHBoxLayout(holder)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(_lbl(left))
            s = SliderRow("", -100, 100, 0)
            s.label.hide()
            s.changed.connect(self._slider_changed)
            h.addWidget(s, 1)
            h.addWidget(_lbl(right))
            self.sliders.append(s)
            box.addWidget(holder)
        self.content.addWidget(frame)

        frame2, box2 = group_box("Tone Balance")
        self.tone = QButtonGroup(self)
        row2 = QHBoxLayout()
        for i, name in enumerate(("Shadows", "Midtones", "Highlights")):
            rb = QRadioButton(name)
            rb.setStyleSheet("background: transparent;")
            if name == "Midtones":
                rb.setChecked(True)
            self.tone.addButton(rb, i)
            row2.addWidget(rb)
        box2.addLayout(row2)
        self.tone.idToggled.connect(self._tone_changed)
        self.preserve = QCheckBox("Preserve Luminosity")
        self.preserve.setChecked(True)
        self.preserve.setStyleSheet("background: transparent;")
        box2.addWidget(self.preserve)
        self.content.addWidget(frame2)

        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()

    def _current_range(self):
        return ("Shadows", "Midtones", "Highlights")[self.tone.checkedId()]

    def _slider_changed(self):
        vals = [s.value() for s in self.sliders]
        self.values_by_range[self._current_range()] = vals
        self.readout.setText("   ".join(f"{v:+d}" for v in vals))
        self._timer.start(140)

    def _tone_changed(self, _id, checked):
        if not checked:
            return
        vals = self.values_by_range[self._current_range()]
        for s, v in zip(self.sliders, vals):
            s.set_value(v)

    def values(self):
        return dict(shadows=tuple(self.values_by_range["Shadows"]),
                    midtones=tuple(self.values_by_range["Midtones"]),
                    highlights=tuple(self.values_by_range["Highlights"]),
                    preserve_luminosity=self.preserve.isChecked())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class BrightnessContrastDialog(PCDialog):
    def __init__(self, parent, apply_fn):
        super().__init__(parent, "Brightness/Contrast")
        self.apply_fn = apply_fn
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)
        self.brightness = SliderRow("Brightness:", -100, 100, 0)
        self.contrast = SliderRow("Contrast:", -100, 100, 0)
        for w in (self.brightness, self.contrast):
            w.changed.connect(lambda: self._timer.start(120))
            self.content.addWidget(w)
        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()

    def values(self):
        return dict(brightness=self.brightness.value(), contrast=self.contrast.value())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class ThresholdDialog(PCDialog):
    def __init__(self, parent, source, apply_fn):
        super().__init__(parent, "Threshold")
        self.apply_fn = apply_fn
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)
        self.content.addWidget(_lbl("Threshold Level:"))
        self.hist = HistogramView(90)
        self.hist.set_hist(ops.histogram(source)[0])
        self.content.addWidget(self.hist)
        self.level = SliderRow("", 1, 255, 128)
        self.level.label.hide()
        self.level.changed.connect(lambda: self._timer.start(90))
        self.content.addWidget(self.level)
        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()

    def values(self):
        return dict(level=self.level.value())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class PosterizeDialog(PCDialog):
    def __init__(self, parent, apply_fn):
        super().__init__(parent, "Posterize")
        self.apply_fn = apply_fn
        row = QHBoxLayout()
        row.addWidget(_lbl("Levels:"))
        self.levels = _spin(2, 255, 4, "")
        self.levels.valueChanged.connect(lambda _: self._refresh())
        row.addWidget(self.levels)
        row.addStretch(1)
        self.content.addLayout(row)
        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()

    def values(self):
        return dict(levels_count=self.levels.value())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class ChannelMixerDialog(PCDialog):
    def __init__(self, parent, apply_fn):
        super().__init__(parent, "Channel Mixer")
        self.apply_fn = apply_fn
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)
        self.matrix = [[100, 0, 0], [0, 100, 0], [0, 0, 100]]
        self.constants = [0, 0, 0]

        row = QHBoxLayout()
        row.addWidget(_lbl("Output Channel:"))
        self.output = QComboBox()
        self.output.addItems(["Red", "Green", "Blue"])
        self.output.currentIndexChanged.connect(self._output_changed)
        row.addWidget(self.output, 1)
        self.content.addLayout(row)

        frame, box = group_box("Source Channels")
        self.sliders = []
        for name in ("Red:", "Green:", "Blue:"):
            s = SliderRow(name, -200, 200, 0, "%")
            s.changed.connect(self._slider_changed)
            box.addWidget(s)
            self.sliders.append(s)
        self.constant = SliderRow("Constant:", -200, 200, 0, "%")
        self.constant.changed.connect(self._slider_changed)
        box.addWidget(self.constant)
        self.content.addWidget(frame)

        self.mono = QCheckBox("Monochrome")
        self.mono.setStyleSheet("background: transparent;")
        self.mono.toggled.connect(lambda _: self._timer.start(60))
        self.content.addWidget(self.mono)

        self._output_changed(0)
        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()

    def _output_changed(self, idx):
        for s, v in zip(self.sliders, self.matrix[idx]):
            s.set_value(v)
        self.constant.set_value(self.constants[idx])

    def _slider_changed(self):
        idx = self.output.currentIndex()
        self.matrix[idx] = [s.value() for s in self.sliders]
        self.constants[idx] = self.constant.value()
        self._timer.start(140)

    def values(self):
        return dict(matrix=[list(r) for r in self.matrix],
                    constants=tuple(self.constants), monochrome=self.mono.isChecked())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class SelectiveColorDialog(PCDialog):
    def __init__(self, parent, apply_fn):
        super().__init__(parent, "Selective Color")
        self.apply_fn = apply_fn
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)
        row = QHBoxLayout()
        row.addWidget(_lbl("Colors:"))
        self.target = QComboBox()
        self.target.addItems(["Reds", "Yellows", "Greens", "Cyans", "Blues",
                              "Magentas", "Whites", "Neutrals", "Blacks"])
        self.target.currentTextChanged.connect(lambda _: self._timer.start(60))
        row.addWidget(self.target, 1)
        self.content.addLayout(row)

        self.sliders = []
        for name in ("Cyan:", "Magenta:", "Yellow:", "Black:"):
            s = SliderRow(name, -100, 100, 0, "%")
            s.changed.connect(lambda: self._timer.start(140))
            self.content.addWidget(s)
            self.sliders.append(s)

        frame, box = group_box("Method")
        self.method = QButtonGroup(self)
        row2 = QHBoxLayout()
        for i, name in enumerate(("Relative", "Absolute")):
            rb = QRadioButton(name)
            rb.setStyleSheet("background: transparent;")
            if i == 0:
                rb.setChecked(True)
            self.method.addButton(rb, i)
            row2.addWidget(rb)
        box.addLayout(row2)
        self.content.addWidget(frame)

        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()

    def values(self):
        return dict(target=self.target.currentText(),
                    cmyk=tuple(s.value() for s in self.sliders),
                    absolute=self.method.checkedId() == 1)

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class GradientMapDialog(PCDialog):
    def __init__(self, parent, apply_fn, fg=QColor("black"), bg=QColor("white")):
        super().__init__(parent, "Gradient Map")
        self.apply_fn = apply_fn
        self.start = QColor(fg)
        self.end = QColor(bg)
        self.content.addWidget(_lbl("Gradient Used for Grayscale Mapping:"))
        row = QHBoxLayout()
        self.start_btn = QPushButton()
        self.start_btn.setFixedSize(40, 20)
        self.start_btn.clicked.connect(lambda: self._pick("start"))
        self.ramp = _RampPreview(self)
        self.end_btn = QPushButton()
        self.end_btn.setFixedSize(40, 20)
        self.end_btn.clicked.connect(lambda: self._pick("end"))
        row.addWidget(self.start_btn)
        row.addWidget(self.ramp, 1)
        row.addWidget(self.end_btn)
        self.content.addLayout(row)

        self.dither = QCheckBox("Dither")
        self.reverse = QCheckBox("Reverse")
        for w in (self.dither, self.reverse):
            w.setStyleSheet("background: transparent;")
            w.toggled.connect(lambda _: self._refresh())
            self.content.addWidget(w)
        self._paint_buttons()
        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()

    def _pick(self, which):
        current = self.start if which == "start" else self.end
        c = XPColorDialog.get_color(self, current)
        if c:
            setattr(self, which, c)
            self._paint_buttons()
            self._refresh()

    def _paint_buttons(self):
        self.start_btn.setStyleSheet(
            f"background: {self.start.name()}; border: 1px solid #555;")
        self.end_btn.setStyleSheet(f"background: {self.end.name()}; border: 1px solid #555;")
        self.ramp.update()

    def values(self):
        a, b = self.start, self.end
        if self.reverse.isChecked():
            a, b = b, a
        return dict(stops=[(0.0, a), (1.0, b)])

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class _RampPreview(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setFixedHeight(20)

    def paintEvent(self, ev):
        p = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, self.owner.start)
        grad.setColorAt(1, self.owner.end)
        p.fillRect(self.rect(), QBrush(grad))
        p.setPen(QPen(QColor("#808080"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()


class VariationsDialog(PCDialog):
    """The thumbnail ring: click a variation, it becomes the new Current Pick."""

    OFFSETS = {
        "More Green": (0, 20, 0), "More Yellow": (0, 0, -20), "More Cyan": (-20, 0, 0),
        "More Red": (20, 0, 0), "More Blue": (0, 0, 20), "More Magenta": (0, -20, 0),
    }
    RING = [(None, "More Green", None),
            ("More Cyan", "Current Pick", "More Red"),
            (None, "More Blue", None),
            ("More Magenta", None, "More Yellow")]

    def __init__(self, parent, source: QImage):
        super().__init__(parent, "Variations")
        self.original = source
        self.current = source.copy()
        self.applied = [0, 0, 0]
        self.fine_coarse = 2

        top = QHBoxLayout()
        top.addWidget(self._thumb_block("Original", self.original))
        self.pick_label = self._thumb_block("Current Pick", self.current)
        top.addWidget(self.pick_label)
        top.addStretch(1)
        self.content.addLayout(top)

        frame, box = group_box("")
        grid = QGridLayout()
        grid.setSpacing(4)
        self.buttons = {}
        for r, row in enumerate(self.RING):
            for c, name in enumerate(row):
                if name is None:
                    continue
                if name == "Current Pick":
                    widget = self._thumb_block("Current Pick", self.current)
                    self.centre_thumb = widget
                else:
                    widget = self._variation_button(name)
                grid.addWidget(widget, r, c)
        box.addLayout(grid)
        self.content.addWidget(frame)

        row = QHBoxLayout()
        row.addWidget(_lbl("Fine"))
        from PyQt6.QtWidgets import QSlider
        self.amount = QSlider(Qt.Orientation.Horizontal)
        self.amount.setRange(0, 4)
        self.amount.setValue(2)
        self.amount.setFixedWidth(120)
        row.addWidget(self.amount)
        row.addWidget(_lbl("Coarse"))
        row.addStretch(1)
        self.content.addLayout(row)

        self.add_ok_cancel()
        self.add_button("Reset", self._reset)
        self.finish_side()

    def _thumb(self, img):
        label = QLabel()
        label.setPixmap(QPixmap.fromImage(
            img.scaled(74, 56, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)))
        label.setStyleSheet("border: 1px solid #808080; background: transparent;")
        return label

    def _thumb_block(self, title, img):
        holder = QWidget()
        v = QVBoxLayout(holder)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        caption = QLabel(title)
        caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        caption.setStyleSheet("background: transparent; font-size: 10px;")
        v.addWidget(caption)
        thumb = self._thumb(img)
        v.addWidget(thumb)
        holder.thumb = thumb
        return holder

    def _variation_button(self, name):
        holder = self._thumb_block(name, self._variant(name))
        holder.thumb.mousePressEvent = lambda _ev, n=name: self._choose(n)
        holder.thumb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.buttons[name] = holder
        return holder

    def _variant(self, name, base=None):
        base = base if base is not None else self.current
        dr, dg, db = self.OFFSETS[name]
        strength = (self.fine_coarse + 1) / 3.0 if hasattr(self, "fine_coarse") else 1.0
        return ops.color_balance(base, (0, 0, 0),
                                 (dr * strength, dg * strength, db * strength), (0, 0, 0))

    def _choose(self, name):
        self.current = self._variant(name)
        self._refresh_thumbs()

    def _reset(self):
        self.current = self.original.copy()
        self._refresh_thumbs()

    def _refresh_thumbs(self):
        pm = QPixmap.fromImage(self.current.scaled(
            74, 56, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self.pick_label.thumb.setPixmap(pm)
        self.centre_thumb.thumb.setPixmap(pm)
        for name, holder in self.buttons.items():
            holder.thumb.setPixmap(QPixmap.fromImage(self._variant(name).scaled(
                74, 56, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)))

    def result(self):
        return self.current


class ColorRangeDialog(PCDialog):
    def __init__(self, parent, source: QImage, sample=QColor("white")):
        super().__init__(parent, "Color Range")
        self.source = source
        self.sample = QColor(sample)
        row = QHBoxLayout()
        row.addWidget(_lbl("Select:"))
        self.select = QComboBox()
        self.select.addItems(["Sampled Colors", "Reds", "Yellows", "Greens", "Cyans",
                              "Blues", "Magentas", "Highlights", "Midtones", "Shadows"])
        row.addWidget(self.select, 1)
        self.content.addLayout(row)

        self.fuzziness = SliderRow("Fuzziness:", 0, 200, 40)
        self.fuzziness.changed.connect(self._refresh)
        self.content.addWidget(self.fuzziness)

        self.preview = QLabel()
        self.preview.setFixedSize(200, 150)
        self.preview.setStyleSheet("border: 1px solid #808080; background: #000;")
        self.content.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)

        row2 = QHBoxLayout()
        row2.addWidget(_lbl("Selection Preview:"))
        self.preview_mode = QComboBox()
        self.preview_mode.addItems(["None", "Grayscale", "Black Matte", "White Matte",
                                    "Quick Mask"])
        row2.addWidget(self.preview_mode, 1)
        self.content.addLayout(row2)

        pick = QPushButton("Pick Sample Color...")
        pick.clicked.connect(self._pick)
        self.content.addWidget(pick)

        self.invert = QCheckBox("Invert")
        self.invert.setStyleSheet("background: transparent;")
        self.invert.toggled.connect(self._refresh)
        self.content.addWidget(self.invert)

        self.add_ok_cancel()
        self.finish_side()
        self._refresh()

    def _pick(self):
        c = XPColorDialog.get_color(self, self.sample)
        if c:
            self.sample = c
            self._refresh()

    def mask(self) -> QImage:
        buf, w, h = ops.to_buf(self.source)
        rp = ops.plane(buf, ops.R)
        gp = ops.plane(buf, ops.G)
        bp = ops.plane(buf, ops.B)
        sr, sg, sb = self.sample.red(), self.sample.green(), self.sample.blue()
        tol = max(1, self.fuzziness.value()) * 3
        invert = self.invert.isChecked()
        out = bytearray(w * h)
        for i in range(w * h):
            dist = abs(rp[i] - sr) + abs(gp[i] - sg) + abs(bp[i] - sb)
            v = max(0, 255 - int(dist * 255 / tol)) if dist < tol else 0
            out[i] = 255 - v if invert else v
        mask_buf = bytearray(w * h * 4)
        mask_buf[0::4] = out
        mask_buf[1::4] = out
        mask_buf[2::4] = out
        mask_buf[3::4] = b"\xff" * (w * h)
        return ops.from_buf(mask_buf, w, h)

    def _refresh(self):
        self.preview.setPixmap(QPixmap.fromImage(self.mask().scaled(
            200, 150, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)))
