"""Small, procedurally drawn Internet Explorer 6 toolbar icons.

IE6 used the colourful Windows XP shell icon set rather than glyph-only
buttons.  Keeping these as vectors makes the browser chrome crisp at every
simulator scale without shipping copied Microsoft artwork.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen,
    QPixmap, QPolygonF,
)


_CACHE: dict[tuple[str, int], QIcon] = {}


def icon(name: str, size: int = 24) -> QIcon:
    key = (name, size)
    if key not in _CACHE:
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _draw(painter, name, float(size))
        painter.end()
        _CACHE[key] = QIcon(pm)
    return _CACHE[key]


def _gradient(rect: QRectF, top: str, bottom: str) -> QBrush:
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    grad.setColorAt(0, QColor(top))
    grad.setColorAt(1, QColor(bottom))
    return QBrush(grad)


def _arrow(p: QPainter, s: float, right: bool, enabled: bool = True):
    green1, green2 = ("#8dd93a", "#268b19") if enabled else ("#d9d8cc", "#8e8d84")
    r = QRectF(s * .06, s * .08, s * .84, s * .84)
    p.setPen(QPen(QColor("#39780f" if enabled else "#77766d"), max(1.0, s * .045)))
    p.setBrush(_gradient(r, green1, green2))
    if right:
        points = [(s*.25, s*.20), (s*.78, s*.50), (s*.25, s*.80),
                  (s*.25, s*.63), (s*.05, s*.63), (s*.05, s*.37), (s*.25, s*.37)]
    else:
        points = [(s*.75, s*.20), (s*.22, s*.50), (s*.75, s*.80),
                  (s*.75, s*.63), (s*.95, s*.63), (s*.95, s*.37), (s*.75, s*.37)]
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
    p.setPen(QPen(QColor(255, 255, 255, 150), max(1.0, s * .035)))
    p.drawLine(QPointF(s*.30 if right else s*.70, s*.27),
               QPointF(s*.67 if right else s*.33, s*.50))


def _globe(p: QPainter, s: float):
    r = QRectF(s*.10, s*.10, s*.80, s*.80)
    p.setPen(QPen(QColor("#174a9b"), max(1.0, s*.04)))
    p.setBrush(_gradient(r, "#78d9ff", "#1763bd"))
    p.drawEllipse(r)
    p.setPen(QPen(QColor(255, 255, 255, 175), max(1.0, s*.035)))
    p.drawEllipse(QRectF(s*.30, s*.11, s*.40, s*.78))
    p.drawLine(QPointF(s*.11, s*.50), QPointF(s*.89, s*.50))
    p.drawArc(QRectF(s*.12, s*.26, s*.76, s*.47), 0, 180*16)


def _ie(p: QPainter, s: float):
    # The familiar blue lower-case e with a gold orbital swoosh.
    f = p.font()
    f.setFamily("Arial")
    f.setBold(True)
    f.setItalic(True)
    f.setPixelSize(max(9, int(s*.90)))
    p.setFont(f)
    p.setPen(QColor("#0875d1"))
    p.drawText(QRectF(s*.10, -s*.12, s*.82, s*1.06), Qt.AlignmentFlag.AlignCenter, "e")
    p.setPen(QPen(QColor("#e7a20a"), max(1.1, s*.09), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.drawArc(QRectF(s*.03, s*.27, s*.94, s*.46), 205*16, 248*16)
    p.setPen(QPen(QColor("#ffd861"), max(1.0, s*.028)))
    p.drawArc(QRectF(s*.06, s*.30, s*.88, s*.40), 205*16, 248*16)


def _draw(p: QPainter, name: str, s: float):
    if name == "back":
        _arrow(p, s, False)
    elif name == "forward":
        _arrow(p, s, True, enabled=False)
    elif name == "forward_active":
        _arrow(p, s, True)
    elif name == "stop":
        r = QRectF(s*.13, s*.13, s*.74, s*.74)
        p.setPen(QPen(QColor("#a20d0d"), max(1.0, s*.04)))
        p.setBrush(_gradient(r, "#ff6d65", "#d30d0d"))
        p.drawEllipse(r)
        p.setPen(QPen(QColor("white"), max(2.0, s*.15), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(s*.34, s*.34), QPointF(s*.66, s*.66))
        p.drawLine(QPointF(s*.66, s*.34), QPointF(s*.34, s*.66))
    elif name == "refresh":
        p.setPen(QPen(QColor("#167415"), max(2.0, s*.14), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(s*.17, s*.18, s*.66, s*.66), 35*16, 275*16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2fa523"))
        p.drawPolygon(QPolygonF([QPointF(s*.70,s*.08), QPointF(s*.91,s*.31),
                                 QPointF(s*.61,s*.34)]))
    elif name == "home":
        p.setPen(QPen(QColor("#6c5325"), max(1.0, s*.04)))
        p.setBrush(_gradient(QRectF(s*.22,s*.37,s*.58,s*.53), "#fff8d0", "#e8c46d"))
        p.drawRect(QRectF(s*.22,s*.39,s*.58,s*.48))
        p.setBrush(_gradient(QRectF(s*.09,s*.08,s*.82,s*.48), "#ef776b", "#aa1d15"))
        p.drawPolygon(QPolygonF([QPointF(s*.08,s*.45), QPointF(s*.50,s*.09),
                                 QPointF(s*.92,s*.45), QPointF(s*.82,s*.54),
                                 QPointF(s*.50,s*.27), QPointF(s*.18,s*.54)]))
        p.setBrush(QColor("#58a6e5")); p.drawRect(QRectF(s*.32,s*.52,s*.15,s*.17))
        p.setBrush(QColor("#865b2c")); p.drawRect(QRectF(s*.57,s*.54,s*.14,s*.33))
    elif name == "search":
        _globe(p, s*.68)
        p.setPen(QPen(QColor("#56564f"), max(2.0, s*.11), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.setBrush(QColor(220, 245, 255, 80))
        p.drawEllipse(QRectF(s*.45,s*.36,s*.35,s*.35))
        p.drawLine(QPointF(s*.72,s*.66), QPointF(s*.93,s*.89))
    elif name == "favorites":
        p.setPen(QPen(QColor("#b37b00"), max(1.0, s*.035)))
        p.setBrush(_gradient(QRectF(0,0,s,s), "#fff58a", "#f2b500"))
        pts=[]
        for i in range(10):
            import math
            a = -math.pi/2 + i*math.pi/5
            rad = s*(.44 if i%2 == 0 else .19)
            pts.append(QPointF(s*.5 + math.cos(a)*rad, s*.51 + math.sin(a)*rad))
        p.drawPolygon(QPolygonF(pts))
    elif name == "media":
        _globe(p, s)
        p.setPen(QPen(QColor("white"), max(1.0,s*.04)))
        p.setBrush(QColor("#f15b2a"))
        p.drawEllipse(QRectF(s*.46,s*.45,s*.45,s*.45))
        p.setBrush(QColor("white")); p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([QPointF(s*.61,s*.55), QPointF(s*.61,s*.80), QPointF(s*.80,s*.68)]))
    elif name == "history":
        p.setPen(QPen(QColor("#886711"), max(1.0,s*.04)))
        p.setBrush(_gradient(QRectF(s*.08,s*.08,s*.78,s*.78), "#fffbd8", "#e8c65f"))
        p.drawEllipse(QRectF(s*.08,s*.08,s*.78,s*.78))
        p.setPen(QPen(QColor("#52524a"), max(1.3,s*.07), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(s*.47,s*.24), QPointF(s*.47,s*.51))
        p.drawLine(QPointF(s*.47,s*.51), QPointF(s*.68,s*.61))
        p.setPen(QPen(QColor("#368bd0"), max(1.0,s*.05)))
        p.drawArc(QRectF(s*.02,s*.30,s*.52,s*.64), 105*16, 150*16)
    elif name == "mail":
        r=QRectF(s*.06,s*.23,s*.88,s*.60)
        p.setPen(QPen(QColor("#56687c"), max(1.0,s*.04)))
        p.setBrush(_gradient(r,"#ffffff","#b8d4ee")); p.drawRect(r)
        p.drawLine(r.topLeft(), QPointF(s*.50,s*.58)); p.drawLine(r.topRight(), QPointF(s*.50,s*.58))
    elif name == "print":
        p.setPen(QPen(QColor("#55555a"), max(1.0,s*.04)))
        p.setBrush(QColor("white")); p.drawRect(QRectF(s*.25,s*.04,s*.50,s*.38))
        p.setBrush(_gradient(QRectF(s*.08,s*.28,s*.84,s*.43),"#dae4ee","#7b8b9e"))
        p.drawRoundedRect(QRectF(s*.08,s*.28,s*.84,s*.43),s*.06,s*.06)
        p.setBrush(QColor("white")); p.drawRect(QRectF(s*.22,s*.52,s*.56,s*.40))
        p.setPen(QColor("#7290b0"));
        for y in (.63,.73,.83): p.drawLine(QPointF(s*.30,s*y),QPointF(s*.70,s*y))
    elif name == "edit":
        p.setPen(QPen(QColor("#63718b"), max(1.0,s*.04))); p.setBrush(QColor("white"))
        p.drawRect(QRectF(s*.10,s*.06,s*.59,s*.82))
        p.setPen(QColor("#9ab0c9"))
        for y in (.25,.39,.53,.67): p.drawLine(QPointF(s*.19,s*y),QPointF(s*.58,s*y))
        p.setPen(QPen(QColor("#785b10"), max(1.0,s*.05)))
        p.setBrush(QColor("#ffd64f"))
        p.drawPolygon(QPolygonF([QPointF(s*.34,s*.82),QPointF(s*.78,s*.29),
                                 QPointF(s*.91,s*.41),QPointF(s*.47,s*.91)]))
    elif name == "go":
        p.setPen(QPen(QColor("#24700c"), max(1.0,s*.04)))
        p.setBrush(_gradient(QRectF(s*.06,s*.06,s*.88,s*.88),"#b8ec55","#3b9f16"))
        p.drawEllipse(QRectF(s*.06,s*.06,s*.88,s*.88))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("white"))
        p.drawPolygon(QPolygonF([QPointF(s*.28,s*.39),QPointF(s*.59,s*.39),
                                 QPointF(s*.59,s*.25),QPointF(s*.83,s*.50),
                                 QPointF(s*.59,s*.75),QPointF(s*.59,s*.61),QPointF(s*.28,s*.61)]))
    elif name == "ie_small":
        _ie(p, s)
    elif name == "globe":
        _globe(p, s)
    elif name == "branding":
        # IE6's top-right animated Windows flag panel.
        p.fillRect(QRectF(0,0,s,s), _gradient(QRectF(0,0,s,s),"#163b76","#071b45"))
        wave = QPainterPath(); wave.moveTo(s*.16,s*.22); wave.cubicTo(s*.38,s*.10,s*.48,s*.26,s*.58,s*.19)
        wave.lineTo(s*.58,s*.47); wave.cubicTo(s*.45,s*.54,s*.34,s*.37,s*.16,s*.50); wave.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#ef3d32")); p.drawPath(wave)
        p.save(); p.translate(s*.44,0)
        wave2=QPainterPath(); wave2.moveTo(s*.16,s*.19); wave2.cubicTo(s*.30,s*.14,s*.37,s*.23,s*.44,s*.20)
        wave2.lineTo(s*.44,s*.47); wave2.cubicTo(s*.35,s*.50,s*.28,s*.42,s*.16,s*.47); wave2.closeSubpath()
        p.setBrush(QColor("#69bd45")); p.drawPath(wave2); p.restore()
        p.save(); p.translate(0,s*.34); p.setBrush(QColor("#29a9eb")); p.drawPath(wave); p.restore()
        p.save(); p.translate(s*.44,s*.34); p.setBrush(QColor("#ffd43b")); p.drawPath(wave2); p.restore()
    else:
        _ie(p, s)
