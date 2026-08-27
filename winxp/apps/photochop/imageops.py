"""Pixel math for PhotoChop.

Everything here takes and returns a QImage and never touches the GUI, so the
filter/adjustment dialogs can preview by calling these directly.

Speed notes -- these run in pure Python over ~200k pixels, so anything
per-pixel has to be pushed down into C:

  * single-image, per-channel curves become a 256-entry table and go through
    ``bytes.translate`` (one C call for the whole plane).
  * two-image byte math (unsharp, emboss, min/max, blends) goes through
    ``_pairwise``: interleave the two planes into 16-bit words and map them
    through a 65536-entry table, which is one C-level ``map`` over the buffer.
  * blurs are handed to Qt's own raster engine rather than convolved here.

Buffers are ARGB32 (non-premultiplied) which is B, G, R, A in memory on every
little-endian machine, i.e. every machine this thing will ever run on.
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QImage, QLinearGradient, QPainter, QPen,
    QRadialGradient, QTransform,
)

B, G, R, A = 0, 1, 2, 3  # byte offsets within one ARGB32 pixel


# ---------------------------------------------------------------- buffers ---

def to_buf(img: QImage) -> tuple[bytearray, int, int]:
    """QImage -> (BGRA bytearray, width, height)."""
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    ptr = img.bits()
    ptr.setsize(img.sizeInBytes())
    return bytearray(ptr.asstring()), img.width(), img.height()


def from_buf(buf: bytearray, w: int, h: int) -> QImage:
    """BGRA bytearray -> QImage. Copies, so the buffer can be thrown away."""
    img = QImage(bytes(buf), w, h, w * 4, QImage.Format.Format_ARGB32)
    return img.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def plane(buf: bytearray, ch: int) -> bytearray:
    return buf[ch::4]


def set_plane(buf: bytearray, ch: int, data) -> None:
    buf[ch::4] = data


def clone(img: QImage) -> QImage:
    return img.copy()


def blank_like(img: QImage) -> QImage:
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    return out


def _clamp(v, lo=0, hi=255):
    return lo if v < lo else (hi if v > hi else v)


# ------------------------------------------------------------------- luts ---

def apply_lut(img: QImage, lut_r, lut_g=None, lut_b=None) -> QImage:
    """Push each colour plane through a 256-entry table. Alpha is untouched."""
    lut_r = bytes(lut_r)
    lut_g = bytes(lut_g) if lut_g is not None else lut_r
    lut_b = bytes(lut_b) if lut_b is not None else lut_r
    buf, w, h = to_buf(img)
    set_plane(buf, R, plane(buf, R).translate(lut_r))
    set_plane(buf, G, plane(buf, G).translate(lut_g))
    set_plane(buf, B, plane(buf, B).translate(lut_b))
    return from_buf(buf, w, h)


def identity_lut():
    return list(range(256))


_PAIR_CACHE: dict = {}


def _pairwise(a: bytearray, b: bytearray, table) -> bytes:
    """Byte-for-byte f(a, b) over two equal-length planes, at C speed.

    ``table`` is indexed ``(b << 8) | a`` -- little-endian word order, so
    interleaving a into the low byte and b into the high byte and casting to
    'H' hands ``map`` the index directly.
    """
    n = len(a)
    pairs = bytearray(n * 2)
    pairs[0::2] = a
    pairs[1::2] = b
    return bytes(map(table.__getitem__, memoryview(pairs).cast("H")))


def pair_table(fn) -> bytes:
    """Build (and cache) the 65536-entry table for a two-byte operation."""
    closure = tuple(c.cell_contents for c in (fn.__closure__ or ()))
    try:
        key = (fn.__code__, closure)
    except TypeError:
        key = (fn.__code__, id(fn))
    cached = _PAIR_CACHE.get(key)
    if cached is not None:
        return cached
    tbl = bytes(_clamp(int(fn(lo, hi))) for hi in range(256) for lo in range(256))
    # ^ index is (hi << 8) | lo, so `hi` has to be the outer loop.
    _PAIR_CACHE[key] = tbl
    return tbl


def combine(img_a: QImage, img_b: QImage, fn) -> QImage:
    """Apply fn(a_byte, b_byte) across the colour planes of two images."""
    table = pair_table(fn)
    a, w, h = to_buf(img_a)
    b, _, _ = to_buf(img_b)
    for ch in (R, G, B):
        set_plane(a, ch, _pairwise(plane(a, ch), plane(b, ch), table))
    return from_buf(a, w, h)


def _offset_image(img: QImage, dx: int, dy: int, wrap=False) -> QImage:
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    if wrap:
        w, h = img.width(), img.height()
        for ox in (-w, 0, w):
            for oy in (-h, 0, h):
                p.drawImage(dx + ox, dy + oy, img)
    else:
        # edge-clamp: lay the original down first so the strip the shift
        # exposes keeps real pixels instead of going transparent
        p.drawImage(0, 0, img)
        p.drawImage(dx, dy, img)
    p.end()
    return out


# ------------------------------------------------------------ adjustments ---

def levels(img: QImage, in_black=0, gamma=1.0, in_white=255,
           out_black=0, out_white=255, channel="RGB") -> QImage:
    lut = []
    span = max(1, in_white - in_black)
    inv_gamma = 1.0 / max(0.01, gamma)
    for i in range(256):
        v = (i - in_black) / span
        v = 0.0 if v < 0 else (1.0 if v > 1 else v)
        v = v ** inv_gamma
        lut.append(_clamp(int(round(out_black + v * (out_white - out_black)))))
    return _channel_lut(img, lut, channel)


def _channel_lut(img: QImage, lut, channel) -> QImage:
    ident = identity_lut()
    if channel == "RGB":
        return apply_lut(img, lut, lut, lut)
    if channel == "Red":
        return apply_lut(img, lut, ident, ident)
    if channel == "Green":
        return apply_lut(img, ident, lut, ident)
    return apply_lut(img, ident, ident, lut)


def histogram(img: QImage) -> tuple[list, list, list, list]:
    """(luminosity, r, g, b) 256-bin counts."""
    buf, _, _ = to_buf(img)
    hr = [0] * 256
    hg = [0] * 256
    hb = [0] * 256
    hl = [0] * 256
    for ch, hist in ((R, hr), (G, hg), (B, hb)):
        p = plane(buf, ch)
        for v in p:
            hist[v] += 1
    # luminosity needs the per-pixel triple, so walk it once
    rp, gp, bp = plane(buf, R), plane(buf, G), plane(buf, B)
    for r, g, b in zip(rp, gp, bp):
        hl[(r * 77 + g * 151 + b * 28) >> 8] += 1
    return hl, hr, hg, hb


def _channel_range(hist, clip_pct=0.005):
    total = sum(hist)
    if not total:
        return 0, 255
    clip = total * clip_pct
    acc = 0
    lo = 0
    for i, c in enumerate(hist):
        acc += c
        if acc > clip:
            lo = i
            break
    acc = 0
    hi = 255
    for i in range(255, -1, -1):
        acc += hist[i]
        if acc > clip:
            hi = i
            break
    if hi <= lo:
        lo, hi = 0, 255
    return lo, hi


def auto_levels(img: QImage) -> QImage:
    """PS's Auto Levels: stretch each channel independently."""
    _, hr, hg, hb = histogram(img)
    luts = []
    for hist in (hr, hg, hb):
        lo, hi = _channel_range(hist)
        span = max(1, hi - lo)
        luts.append([_clamp(int((i - lo) * 255 / span)) for i in range(256)])
    return apply_lut(img, *luts)


def auto_contrast(img: QImage) -> QImage:
    """Auto Contrast: one stretch shared by all channels, so colour is kept."""
    hl, _, _, _ = histogram(img)
    lo, hi = _channel_range(hl)
    span = max(1, hi - lo)
    lut = [_clamp(int((i - lo) * 255 / span)) for i in range(256)]
    return apply_lut(img, lut)


def auto_color(img: QImage) -> QImage:
    """Auto Color: neutralise midtones, then stretch per channel."""
    stretched = auto_levels(img)
    buf, w, h = to_buf(stretched)
    means = [sum(plane(buf, ch)) / max(1, len(plane(buf, ch))) for ch in (R, G, B)]
    target = sum(means) / 3
    luts = []
    for m in means:
        g = math.log(max(1e-3, target / 255.0)) / math.log(max(1e-3, m / 255.0)) if m > 1 else 1.0
        g = max(0.4, min(2.5, g))
        luts.append([_clamp(int(255 * (i / 255.0) ** g)) for i in range(256)])
    return apply_lut(stretched, *luts)


def brightness_contrast(img: QImage, brightness=0, contrast=0) -> QImage:
    """PS 7 legacy behaviour: linear brightness shift, then a contrast pivot."""
    c = (contrast + 100) / 100.0
    c = c * c if contrast > 0 else c
    lut = [_clamp(int(round(((i + brightness) - 128) * c + 128))) for i in range(256)]
    return apply_lut(img, lut)


def invert(img: QImage) -> QImage:
    return apply_lut(img, [255 - i for i in range(256)])


def threshold(img: QImage, level=128) -> QImage:
    buf, w, h = to_buf(img)
    rp, gp, bp = plane(buf, R), plane(buf, G), plane(buf, B)
    out = bytes(255 if (r * 77 + g * 151 + b * 28) >> 8 >= level else 0
                for r, g, b in zip(rp, gp, bp))
    for ch in (R, G, B):
        set_plane(buf, ch, out)
    return from_buf(buf, w, h)


def posterize(img: QImage, levels_count=4) -> QImage:
    n = max(2, levels_count)
    lut = [_clamp(int(round(round(i * (n - 1) / 255.0) * 255.0 / (n - 1)))) for i in range(256)]
    return apply_lut(img, lut)


def desaturate(img: QImage) -> QImage:
    """PS Desaturate uses the HSL lightness (max+min)/2, not a luma weighting."""
    buf, w, h = to_buf(img)
    rp, gp, bp = plane(buf, R), plane(buf, G), plane(buf, B)
    grey = bytes((max(r, g, b) + min(r, g, b)) >> 1 for r, g, b in zip(rp, gp, bp))
    for ch in (R, G, B):
        set_plane(buf, ch, grey)
    return from_buf(buf, w, h)


def equalize(img: QImage) -> QImage:
    hl, _, _, _ = histogram(img)
    total = sum(hl) or 1
    acc = 0
    lut = []
    for c in hl:
        acc += c
        lut.append(_clamp(int(acc * 255 / total)))
    return apply_lut(img, lut)


def curves(img: QImage, points, channel="RGB") -> QImage:
    """points: [(x, y)] control points in 0..255. Monotone cubic between them."""
    return _channel_lut(img, curve_lut(points), channel)


def curve_lut(points):
    pts = sorted(points)
    if len(pts) < 2:
        return identity_lut()
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(pts)
    # Fritsch-Carlson monotone tangents -- keeps the curve from overshooting
    # the way PS's own spline doesn't.
    d = [(ys[i + 1] - ys[i]) / max(1e-6, xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [(d[i - 1] + d[i]) / 2 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0
        else:
            a, b = m[i] / d[i], m[i + 1] / d[i]
            s = a * a + b * b
            if s > 9:
                t = 3.0 / math.sqrt(s)
                m[i] = t * a * d[i]
                m[i + 1] = t * b * d[i]
    lut = []
    seg = 0
    for x in range(256):
        while seg < n - 2 and x > xs[seg + 1]:
            seg += 1
        x0, x1 = xs[seg], xs[seg + 1]
        if x <= x0:
            lut.append(_clamp(int(round(ys[0] if x <= xs[0] else ys[seg]))))
            continue
        if x >= xs[-1]:
            lut.append(_clamp(int(round(ys[-1]))))
            continue
        hh = max(1e-6, x1 - x0)
        t = (x - x0) / hh
        t2, t3 = t * t, t * t * t
        v = ((2 * t3 - 3 * t2 + 1) * ys[seg] + (t3 - 2 * t2 + t) * hh * m[seg]
             + (-2 * t3 + 3 * t2) * ys[seg + 1] + (t3 - t2) * hh * m[seg + 1])
        lut.append(_clamp(int(round(v))))
    return lut


def color_balance(img: QImage, shadows=(0, 0, 0), midtones=(0, 0, 0),
                  highlights=(0, 0, 0), preserve_luminosity=True) -> QImage:
    """Three -100..100 triples (cyan/red, magenta/green, yellow/blue)."""
    luts = []
    for ch in range(3):
        lut = []
        for i in range(256):
            t = i / 255.0
            w_sh = max(0.0, 1.0 - t * 2.0)
            w_hi = max(0.0, t * 2.0 - 1.0)
            w_mid = 1.0 - w_sh - w_hi
            shift = (shadows[ch] * w_sh + midtones[ch] * w_mid + highlights[ch] * w_hi)
            lut.append(_clamp(int(round(i + shift * 0.6))))
        luts.append(lut)
    out = apply_lut(img, *luts)
    if preserve_luminosity:
        out = _match_luminosity(img, out)
    return out


def _match_luminosity(src: QImage, dst: QImage) -> QImage:
    sb, w, h = to_buf(src)
    db, _, _ = to_buf(dst)
    sr, sg, sbl = plane(sb, R), plane(sb, G), plane(sb, B)
    dr, dg, dbl = plane(db, R), plane(db, G), plane(db, B)
    orr, og, ob = bytearray(len(dr)), bytearray(len(dr)), bytearray(len(dr))
    for i in range(len(dr)):
        ls = (sr[i] * 77 + sg[i] * 151 + sbl[i] * 28) >> 8
        ld = (dr[i] * 77 + dg[i] * 151 + dbl[i] * 28) >> 8
        delta = ls - ld
        orr[i] = _clamp(dr[i] + delta)
        og[i] = _clamp(dg[i] + delta)
        ob[i] = _clamp(dbl[i] + delta)
    set_plane(db, R, orr)
    set_plane(db, G, og)
    set_plane(db, B, ob)
    return from_buf(db, w, h)


def _rgb_to_hsl(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 510.0
    if mx == mn:
        return 0.0, 0.0, l
    d = (mx - mn) / 255.0
    s = d / (2.0 - (mx + mn) / 255.0) if l > 0.5 else d / ((mx + mn) / 255.0)
    if mx == r:
        hh = ((g - b) / 255.0 / d) % 6
    elif mx == g:
        hh = (b - r) / 255.0 / d + 2
    else:
        hh = (r - g) / 255.0 / d + 4
    return hh / 6.0, s, l


def _hue_channel(p, q, t):
    t %= 1.0
    if t < 1 / 6:
        return p + (q - p) * 6 * t
    if t < 0.5:
        return q
    if t < 2 / 3:
        return p + (q - p) * (2 / 3 - t) * 6
    return p


def _hsl_to_rgb(h, s, l):
    if s == 0:
        v = int(round(l * 255))
        return v, v, v
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return (_clamp(int(round(_hue_channel(p, q, h + 1 / 3) * 255))),
            _clamp(int(round(_hue_channel(p, q, h) * 255))),
            _clamp(int(round(_hue_channel(p, q, h - 1 / 3) * 255))))


HSL_RANGES = {
    "Master": None,
    "Reds": (315, 45), "Yellows": (15, 105), "Greens": (75, 165),
    "Cyans": (135, 225), "Blues": (195, 285), "Magentas": (255, 345),
}


def hue_saturation(img: QImage, hue=0, saturation=0, lightness=0,
                   colorize=False, range_name="Master") -> QImage:
    """Per-pixel HSL, memoised on the source triple -- flat art collapses to a
    handful of dict hits, photos still finish inside a wait cursor."""
    buf, w, h = to_buf(img)
    rp, gp, bp = plane(buf, R), plane(buf, G), plane(buf, B)
    hue_shift = hue / 360.0
    sat = saturation / 100.0
    light = lightness / 100.0
    band = HSL_RANGES.get(range_name)
    memo: dict = {}
    orr, og, ob = bytearray(len(rp)), bytearray(len(rp)), bytearray(len(rp))
    for i in range(len(rp)):
        key = (rp[i], gp[i], bp[i])
        got = memo.get(key)
        if got is None:
            hh, ss, ll = _rgb_to_hsl(*key)
            if colorize:
                hh = hue_shift % 1.0
                ss = max(0.0, min(1.0, saturation / 100.0))
            else:
                weight = 1.0
                if band is not None:
                    deg = (hh * 360.0) % 360
                    lo, hi = band
                    inside = (lo <= deg <= hi) if lo < hi else (deg >= lo or deg <= hi)
                    weight = 1.0 if inside else 0.0
                if weight:
                    hh = (hh + hue_shift) % 1.0
                    ss = ss * (1 + sat) if sat >= 0 else ss * (1 + sat)
                    ss = max(0.0, min(1.0, ss))
            if light > 0:
                ll = ll + (1 - ll) * light
            elif light < 0:
                ll = ll * (1 + light)
            got = _hsl_to_rgb(hh, max(0.0, min(1.0, ss)), max(0.0, min(1.0, ll)))
            memo[key] = got
        orr[i], og[i], ob[i] = got
    set_plane(buf, R, orr)
    set_plane(buf, G, og)
    set_plane(buf, B, ob)
    return from_buf(buf, w, h)


def channel_mixer(img: QImage, matrix, constants=(0, 0, 0), monochrome=False) -> QImage:
    """matrix: 3x3 of -200..200 percentages, rows = output R, G, B."""
    buf, w, h = to_buf(img)
    rp, gp, bp = plane(buf, R), plane(buf, G), plane(buf, B)
    m = [[v / 100.0 for v in row] for row in matrix]
    c = [v * 2.55 for v in constants]
    orr, og, ob = bytearray(len(rp)), bytearray(len(rp)), bytearray(len(rp))
    for i in range(len(rp)):
        r, g, b = rp[i], gp[i], bp[i]
        nr = _clamp(int(m[0][0] * r + m[0][1] * g + m[0][2] * b + c[0]))
        if monochrome:
            orr[i] = og[i] = ob[i] = nr
        else:
            orr[i] = nr
            og[i] = _clamp(int(m[1][0] * r + m[1][1] * g + m[1][2] * b + c[1]))
            ob[i] = _clamp(int(m[2][0] * r + m[2][1] * g + m[2][2] * b + c[2]))
    set_plane(buf, R, orr)
    set_plane(buf, G, og)
    set_plane(buf, B, ob)
    return from_buf(buf, w, h)


def gradient_map(img: QImage, stops) -> QImage:
    """stops: [(pos 0..1, QColor)] -- remap luminosity through the ramp."""
    ramp = QImage(256, 1, QImage.Format.Format_ARGB32)
    p = QPainter(ramp)
    grad = QLinearGradient(0, 0, 256, 0)
    for pos, col in stops:
        grad.setColorAt(max(0.0, min(1.0, pos)), QColor(col))
    p.fillRect(0, 0, 256, 1, QBrush(grad))
    p.end()
    lut_r = [ramp.pixelColor(i, 0).red() for i in range(256)]
    lut_g = [ramp.pixelColor(i, 0).green() for i in range(256)]
    lut_b = [ramp.pixelColor(i, 0).blue() for i in range(256)]
    buf, w, h = to_buf(img)
    rp, gp, bp = plane(buf, R), plane(buf, G), plane(buf, B)
    lum = bytes((r * 77 + g * 151 + b * 28) >> 8 for r, g, b in zip(rp, gp, bp))
    set_plane(buf, R, bytes(lut_r[v] for v in lum))
    set_plane(buf, G, bytes(lut_g[v] for v in lum))
    set_plane(buf, B, bytes(lut_b[v] for v in lum))
    return from_buf(buf, w, h)


def selective_color(img: QImage, target, cmyk, absolute=False) -> QImage:
    """target: Reds/Yellows/Greens/Cyans/Blues/Magentas/Whites/Neutrals/Blacks.
    cmyk: four -100..100 values."""
    buf, w, h = to_buf(img)
    rp, gp, bp = plane(buf, R), plane(buf, G), plane(buf, B)
    c_adj, m_adj, y_adj, k_adj = [v / 100.0 for v in cmyk]
    memo: dict = {}
    orr, og, ob = bytearray(len(rp)), bytearray(len(rp)), bytearray(len(rp))
    for i in range(len(rp)):
        key = (rp[i], gp[i], bp[i])
        got = memo.get(key)
        if got is None:
            r, g, b = key
            mx, mn = max(r, g, b), min(r, g, b)
            weight = _selective_weight(target, r, g, b, mx, mn)
            if weight <= 0:
                got = key
            else:
                c, m, y = 1 - r / 255, 1 - g / 255, 1 - b / 255
                k = min(c, m, y)
                base = 1.0 if absolute else max(0.0, 1.0 - k)
                c = c + c_adj * weight * base
                m = m + m_adj * weight * base
                y = y + y_adj * weight * base
                kk = k + k_adj * weight * base
                got = (_clamp(int(255 * (1 - min(1.0, max(0.0, c + kk - k))))),
                       _clamp(int(255 * (1 - min(1.0, max(0.0, m + kk - k))))),
                       _clamp(int(255 * (1 - min(1.0, max(0.0, y + kk - k))))))
            memo[key] = got
        orr[i], og[i], ob[i] = got
    set_plane(buf, R, orr)
    set_plane(buf, G, og)
    set_plane(buf, B, ob)
    return from_buf(buf, w, h)


def _selective_weight(target, r, g, b, mx, mn):
    d = (mx - mn) / 255.0
    if target == "Whites":
        return max(0.0, (mn - 128) / 127.0)
    if target == "Blacks":
        return max(0.0, (128 - mx) / 128.0)
    if target == "Neutrals":
        return max(0.0, 1.0 - d * 3)
    if d < 0.02:
        return 0.0
    hh, _, _ = _rgb_to_hsl(r, g, b)
    deg = hh * 360
    centres = {"Reds": 0, "Yellows": 60, "Greens": 120,
               "Cyans": 180, "Blues": 240, "Magentas": 300}
    centre = centres.get(target)
    if centre is None:
        return 0.0
    dist = min(abs(deg - centre), 360 - abs(deg - centre))
    return max(0.0, 1.0 - dist / 60.0) * min(1.0, d * 2)


def replace_color(img: QImage, sample: QColor, fuzziness, hue=0, saturation=0, lightness=0) -> QImage:
    buf, w, h = to_buf(img)
    rp, gp, bp = plane(buf, R), plane(buf, G), plane(buf, B)
    sr, sg, sb = sample.red(), sample.green(), sample.blue()
    tol = max(1, fuzziness) * 2
    mask = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    mask.fill(Qt.GlobalColor.transparent)
    shifted = hue_saturation(img, hue, saturation, lightness)
    mb, _, _ = to_buf(mask)
    ap = bytearray(len(rp))
    for i in range(len(rp)):
        dist = abs(rp[i] - sr) + abs(gp[i] - sg) + abs(bp[i] - sb)
        ap[i] = 255 if dist < tol else 0
    sbuf, _, _ = to_buf(shifted)
    set_plane(sbuf, A, ap)
    masked = from_buf(sbuf, w, h)
    out = img.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.drawImage(0, 0, masked)
    p.end()
    return out


# ------------------------------------------------------------------ blurs ---

def gaussian_blur(img: QImage, radius: float) -> QImage:
    if radius <= 0.05:
        return img.copy()
    from PyQt6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene
    from PyQt6.QtGui import QPixmap
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(img))
    eff = QGraphicsBlurEffect()
    eff.setBlurRadius(radius)
    eff.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(eff)
    scene.addItem(item)
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(p, QRectF(out.rect()), QRectF(img.rect()))
    p.end()
    scene.clear()
    return out


def blur(img: QImage) -> QImage:
    return gaussian_blur(img, 0.9)


def blur_more(img: QImage) -> QImage:
    return gaussian_blur(img, 2.4)


def motion_blur(img: QImage, angle=0.0, distance=10) -> QImage:
    steps = max(2, min(48, int(distance)))
    rad = math.radians(-angle)
    dx, dy = math.cos(rad), math.sin(rad)
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    for i in range(steps):
        t = (i / (steps - 1)) - 0.5
        p.setOpacity(1.0 / (i + 1))
        p.drawImage(QPointF(dx * distance * t, dy * distance * t), img)
    p.end()
    return out


def radial_blur(img: QImage, amount=10, method="spin", centre=None) -> QImage:
    w, h = img.width(), img.height()
    cx, cy = (centre or (w / 2, h / 2))
    steps = max(2, min(32, amount))
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    for i in range(steps):
        t = i / (steps - 1) - 0.5
        p.setOpacity(1.0 / (i + 1))
        tr = QTransform()
        tr.translate(cx, cy)
        if method == "spin":
            tr.rotate(t * amount * 0.6)
        else:
            s = 1.0 + t * amount / 100.0
            tr.scale(s, s)
        tr.translate(-cx, -cy)
        p.setTransform(tr)
        p.drawImage(0, 0, img)
    p.end()
    return out


def smart_blur(img: QImage, radius=5.0, threshold_v=25) -> QImage:
    """Blur, then keep the original wherever the two disagree strongly --
    which is what Smart Blur is doing when it preserves edges."""
    blurred = gaussian_blur(img, radius)
    keep = pair_table(lambda orig, blr: orig if abs(orig - blr) > threshold_v else blr)
    a, w, h = to_buf(img)
    b, _, _ = to_buf(blurred)
    for ch in (R, G, B):
        set_plane(a, ch, _pairwise(plane(a, ch), plane(b, ch), keep))
    return from_buf(a, w, h)


def lens_blur(img: QImage, radius=8.0) -> QImage:
    """A cheap bokeh: blur, then push the highlights back up."""
    out = gaussian_blur(img, radius)
    return apply_lut(out, [_clamp(int(255 * (i / 255.0) ** 0.85)) for i in range(256)])


# --------------------------------------------------------------- sharpens ---

def unsharp_mask(img: QImage, amount=50, radius=1.0, threshold_v=0) -> QImage:
    blurred = gaussian_blur(img, radius)
    k = amount / 100.0
    table = pair_table(
        lambda orig, blr: orig if abs(orig - blr) < threshold_v else orig + k * (orig - blr)
    )
    a, w, h = to_buf(img)
    b, _, _ = to_buf(blurred)
    for ch in (R, G, B):
        set_plane(a, ch, _pairwise(plane(a, ch), plane(b, ch), table))
    return from_buf(a, w, h)


def sharpen(img: QImage) -> QImage:
    return unsharp_mask(img, 60, 1.0, 0)


def sharpen_more(img: QImage) -> QImage:
    return unsharp_mask(img, 140, 1.0, 0)


def sharpen_edges(img: QImage) -> QImage:
    return unsharp_mask(img, 90, 1.6, 12)


def high_pass(img: QImage, radius=10.0) -> QImage:
    blurred = gaussian_blur(img, radius)
    table = pair_table(lambda orig, blr: orig - blr + 128)
    a, w, h = to_buf(img)
    b, _, _ = to_buf(blurred)
    for ch in (R, G, B):
        set_plane(a, ch, _pairwise(plane(a, ch), plane(b, ch), table))
    return from_buf(a, w, h)


# ------------------------------------------------------------------ noise ---

def _gauss_byte_lut(spread):
    """Map a uniform random byte to a gaussian offset via the inverse CDF, so
    noise can be generated with one randbytes() call instead of 200k gauss()."""
    out = []
    for i in range(256):
        u = (i + 0.5) / 256.0
        # Acklam-style approximation is overkill here; erfinv via bisection on
        # the logistic approximation is close enough for film grain.
        z = math.log(u / (1 - u)) / 1.702
        out.append(z * spread)
    return out


def add_noise(img: QImage, amount=12.5, monochromatic=False, gaussian=True) -> QImage:
    buf, w, h = to_buf(img)
    n = w * h
    spread = amount * 2.55
    if gaussian:
        offsets = _gauss_byte_lut(spread / 2)
    else:
        offsets = [(i - 127.5) / 127.5 * spread for i in range(256)]
    table = bytes(_clamp(int(v + offsets[noise]))
                  for noise in range(256) for v in range(256))
    shared = bytearray(random.randbytes(n)) if monochromatic else None
    for ch in (R, G, B):
        noise = shared if shared is not None else bytearray(random.randbytes(n))
        set_plane(buf, ch, _pairwise(plane(buf, ch), noise, table))
    return from_buf(buf, w, h)


def _split_alpha(img: QImage):
    """Force the image opaque and hand back the alpha plane to re-apply after.

    Qt's Darken/Lighten are separable blend modes, so they only reduce to a
    plain per-channel min/max when both operands are opaque.
    """
    buf, w, h = to_buf(img)
    alpha = plane(buf, A)
    set_plane(buf, A, b"\xff" * (w * h))
    return from_buf(buf, w, h), alpha, w, h


def _restore_alpha(img: QImage, alpha, w, h) -> QImage:
    buf, _, _ = to_buf(img)
    set_plane(buf, A, alpha)
    return from_buf(buf, w, h)


def _compose(a: QImage, b: QImage, mode) -> QImage:
    out = a.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.setCompositionMode(mode)
    p.drawImage(0, 0, b)
    p.end()
    return out


def _darken(a: QImage, b: QImage) -> QImage:
    return _compose(a, b, QPainter.CompositionMode.CompositionMode_Darken)


def _lighten(a: QImage, b: QImage) -> QImage:
    return _compose(a, b, QPainter.CompositionMode.CompositionMode_Lighten)


NEIGHBOURS_8 = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def minimum(img: QImage, radius=1) -> QImage:
    opaque, alpha, w, h = _split_alpha(img)
    for _ in range(max(1, int(radius))):
        acc = opaque
        for dx, dy in NEIGHBOURS_8:
            acc = _darken(acc, _offset_image(opaque, dx, dy))
        opaque = acc
    return _restore_alpha(opaque, alpha, w, h)


def maximum(img: QImage, radius=1) -> QImage:
    opaque, alpha, w, h = _split_alpha(img)
    for _ in range(max(1, int(radius))):
        acc = opaque
        for dx, dy in NEIGHBOURS_8:
            acc = _lighten(acc, _offset_image(opaque, dx, dy))
        opaque = acc
    return _restore_alpha(opaque, alpha, w, h)


# Standard 9-input median selection network. Each pair is one Darken plus one
# Lighten, so the whole 3x3 median is ~50 raster composites rather than
# 200,000 Python sorts.
_MEDIAN_NETWORK = (
    (0, 1), (3, 4), (6, 7), (1, 2), (4, 5), (7, 8), (0, 1), (3, 4), (6, 7),
    (0, 3), (3, 6), (0, 3), (1, 4), (4, 7), (1, 4), (2, 5), (5, 8), (2, 5),
    (1, 3), (5, 7), (2, 6), (4, 6), (2, 4), (2, 3), (4, 6),
)


def median(img: QImage, radius=1) -> QImage:
    opaque, alpha, w, h = _split_alpha(img)
    for _ in range(max(1, int(radius))):
        v = [_offset_image(opaque, dx, dy)
             for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        for i, j in _MEDIAN_NETWORK:
            lo = _darken(v[i], v[j])
            hi = _lighten(v[i], v[j])
            v[i], v[j] = lo, hi
        opaque = v[4]
    return _restore_alpha(opaque, alpha, w, h)


def despeckle(img: QImage) -> QImage:
    return median(img, 1)


def dust_and_scratches(img: QImage, radius=2, threshold_v=0) -> QImage:
    med = median(img, max(1, radius))
    if threshold_v <= 0:
        return med
    table = pair_table(lambda orig, m: orig if abs(orig - m) <= threshold_v else m)
    a, w, h = to_buf(img)
    b, _, _ = to_buf(med)
    for ch in (R, G, B):
        set_plane(a, ch, _pairwise(plane(a, ch), plane(b, ch), table))
    return from_buf(a, w, h)


# --------------------------------------------------------------- pixelate ---

def mosaic(img: QImage, cell=8) -> QImage:
    cell = max(2, int(cell))
    small = img.scaled(max(1, img.width() // cell), max(1, img.height() // cell),
                       Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    return small.scaled(img.width(), img.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.FastTransformation)


def crystallize(img: QImage, size=10) -> QImage:
    w, h = img.width(), img.height()
    cell = max(3, int(size))
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setPen(Qt.PenStyle.NoPen)
    rng = random.Random(1234)
    for cy in range(0, h + cell, cell):
        for cx in range(0, w + cell, cell):
            jx = cx + rng.randint(-cell // 2, cell // 2)
            jy = cy + rng.randint(-cell // 2, cell // 2)
            col = img.pixelColor(max(0, min(w - 1, jx)), max(0, min(h - 1, jy)))
            p.setBrush(col)
            pts = []
            for k in range(6):
                ang = math.radians(60 * k + rng.randint(-12, 12))
                rr = cell * 0.72
                pts.append(QPointF(jx + math.cos(ang) * rr, jy + math.sin(ang) * rr))
            from PyQt6.QtGui import QPolygonF
            p.drawPolygon(QPolygonF(pts))
    p.end()
    return out


def pointillize(img: QImage, size=5) -> QImage:
    w, h = img.width(), img.height()
    cell = max(2, int(size))
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.white)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    rng = random.Random(99)
    for cy in range(0, h + cell, cell):
        for cx in range(0, w + cell, cell):
            jx = cx + rng.randint(-cell, cell)
            jy = cy + rng.randint(-cell, cell)
            col = img.pixelColor(max(0, min(w - 1, jx)), max(0, min(h - 1, jy)))
            p.setBrush(col)
            p.drawEllipse(QPointF(jx, jy), cell * 0.62, cell * 0.62)
    p.end()
    return out


def facet(img: QImage) -> QImage:
    return median(mosaic(img, 3), 1)


def fragment(img: QImage) -> QImage:
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    for dx, dy in ((-4, -4), (4, -4), (-4, 4), (4, 4)):
        p.setOpacity(0.25)
        p.drawImage(dx, dy, img)
    p.end()
    return out


def color_halftone(img: QImage, radius=4) -> QImage:
    w, h = img.width(), img.height()
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.white)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
    step = max(3, radius * 2)
    for angle, col, chan in ((15, QColor(0, 255, 255), 0), (75, QColor(255, 0, 255), 1),
                             (0, QColor(255, 255, 0), 2), (45, QColor(0, 0, 0), 3)):
        p.save()
        p.translate(w / 2, h / 2)
        p.rotate(angle)
        p.translate(-w / 2, -h / 2)
        p.setBrush(col)
        span = int(max(w, h) * 1.5)
        for y in range(-span // 2, span, step):
            for x in range(-span // 2, span, step):
                sx = max(0, min(w - 1, x))
                sy = max(0, min(h - 1, y))
                c = img.pixelColor(sx, sy)
                if chan == 0:
                    v = 255 - c.red()
                elif chan == 1:
                    v = 255 - c.green()
                elif chan == 2:
                    v = 255 - c.blue()
                else:
                    v = 255 - max(c.red(), c.green(), c.blue())
                rr = (v / 255.0) * step * 0.62
                if rr > 0.4:
                    p.drawEllipse(QPointF(x, y), rr, rr)
        p.restore()
    p.end()
    return out


# --------------------------------------------------------------- stylize ----

def emboss(img: QImage, angle=135, height=3, amount=100) -> QImage:
    rad = math.radians(-angle)
    dx = int(round(math.cos(rad) * height))
    dy = int(round(math.sin(rad) * height))
    k = amount / 100.0
    table = pair_table(lambda a, b: (a - b) * k + 128)
    a, w, h = to_buf(img)
    b, _, _ = to_buf(_offset_image(img, dx, dy))
    for ch in (R, G, B):
        set_plane(a, ch, _pairwise(plane(a, ch), plane(b, ch), table))
    return from_buf(a, w, h)


def bas_relief(img: QImage) -> QImage:
    return desaturate(emboss(img, 135, 2, 120))


def find_edges(img: QImage) -> QImage:
    """Max of the absolute differences against four neighbours, inverted --
    Difference and Lighten are both raster ops, so this stays off the Python
    side entirely apart from the final table."""
    opaque, alpha, w, h = _split_alpha(img)
    acc = None
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        d = _compose(opaque, _offset_image(opaque, dx, dy),
                     QPainter.CompositionMode.CompositionMode_Difference)
        acc = d if acc is None else _lighten(acc, d)
    acc = apply_lut(acc, [_clamp(255 - i * 4) for i in range(256)])
    return _restore_alpha(acc, alpha, w, h)


def glowing_edges(img: QImage, width_v=2, brightness=6, smoothness=5) -> QImage:
    edges = invert(find_edges(img))
    edges = apply_lut(edges, [_clamp(int(i * brightness / 3)) for i in range(256)])
    if smoothness > 1:
        edges = gaussian_blur(edges, smoothness / 4.0)
    if width_v > 1:
        edges = maximum(edges, width_v - 1)
    return edges


def trace_contour(img: QImage, level=128, upper=True) -> QImage:
    lut = [255] * 256
    for i in range(max(0, level - 6), min(256, level + 6)):
        lut[i] = 0
    return apply_lut(img, lut)


def solarize(img: QImage) -> QImage:
    return apply_lut(img, [i if i < 128 else 255 - i for i in range(256)])


def diffuse(img: QImage, amount=8) -> QImage:
    w, h = img.width(), img.height()
    src, _, _ = to_buf(img)
    dst = bytearray(src)
    rng = random.Random(7)
    for y in range(h):
        row = y * w
        for x in range(w):
            nx = x + rng.randint(-amount, amount)
            ny = y + rng.randint(-amount, amount)
            if 0 <= nx < w and 0 <= ny < h:
                si = ((ny * w) + nx) * 4
                di = (row + x) * 4
                dst[di:di + 4] = src[si:si + 4]
    return from_buf(dst, w, h)


def wind(img: QImage, strength=12, direction="right") -> QImage:
    out = img.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    rng = random.Random(3)
    sign = 1 if direction == "right" else -1
    for y in range(img.height()):
        if rng.random() < 0.55:
            continue
        length = rng.randint(2, strength)
        p.setOpacity(0.55)
        p.drawImage(QRect(0, y, img.width(), 1), img,
                    QRect(-sign * length, y, img.width(), 1))
    p.end()
    return out


def extrude(img: QImage, size=30, depth=30) -> QImage:
    w, h = img.width(), img.height()
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.black)
    p = QPainter(out)
    p.setPen(Qt.PenStyle.NoPen)
    for y in range(0, h, size):
        for x in range(0, w, size):
            col = img.pixelColor(min(w - 1, x + size // 2), min(h - 1, y + size // 2))
            lum = (col.red() + col.green() + col.blue()) / 765.0
            d = depth * lum * 0.35
            p.setBrush(col.darker(140))
            p.drawRect(QRectF(x, y, size, size))
            p.setBrush(col)
            p.drawRect(QRectF(x + d * 0.3, y + d * 0.3, size - d * 0.6, size - d * 0.6))
    p.end()
    return out


def tiles(img: QImage, count=10, offset_pct=10) -> QImage:
    w, h = img.width(), img.height()
    tw, th = max(1, w // count), max(1, h // count)
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.white)
    p = QPainter(out)
    rng = random.Random(11)
    for y in range(0, h, th):
        for x in range(0, w, tw):
            ox = rng.randint(-tw, tw) * offset_pct // 100
            oy = rng.randint(-th, th) * offset_pct // 100
            p.drawImage(QRect(x + ox, y + oy, tw, th), img, QRect(x, y, tw, th))
    p.end()
    return out


# ---------------------------------------------------------------- distort ---

def _remap(img: QImage, fn) -> QImage:
    """fn(x, y) -> (src_x, src_y). Nearest neighbour, one flat byte copy per
    pixel -- the only honest way to do this without numpy."""
    src, w, h = to_buf(img)
    dst = bytearray(len(src))
    for y in range(h):
        base = y * w
        for x in range(w):
            sx, sy = fn(x, y)
            sx = int(sx)
            sy = int(sy)
            if 0 <= sx < w and 0 <= sy < h:
                si = (sy * w + sx) * 4
                di = (base + x) * 4
                dst[di:di + 4] = src[si:si + 4]
    return from_buf(dst, w, h)


def twirl(img: QImage, angle=50) -> QImage:
    w, h = img.width(), img.height()
    cx, cy = w / 2, h / 2
    radius = min(cx, cy)
    strength = math.radians(angle)

    def fn(x, y):
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d >= radius:
            return x, y
        t = (1 - d / radius) ** 2 * strength
        c, s = math.cos(t), math.sin(t)
        return cx + dx * c - dy * s, cy + dx * s + dy * c

    return _remap(img, fn)


def ripple(img: QImage, amount=100, size="Medium") -> QImage:
    wavelength = {"Small": 8, "Medium": 18, "Large": 34}.get(size, 18)
    amp = amount / 100.0 * 6

    def fn(x, y):
        return (x + math.sin(y / wavelength) * amp,
                y + math.cos(x / wavelength) * amp)

    return _remap(img, fn)


def wave(img: QImage, generators=5, wavelength=40, amplitude=12, kind="Sine") -> QImage:
    rng = random.Random(generators)
    phases = [rng.random() * math.tau for _ in range(max(1, generators))]
    w, h = img.width(), img.height()

    def shape(t):
        if kind == "Triangle":
            return 2 * abs(2 * ((t / math.tau) % 1) - 1) - 1
        if kind == "Square":
            return 1.0 if math.sin(t) >= 0 else -1.0
        return math.sin(t)

    # the horizontal offset is a function of y alone and vice versa, so both
    # collapse to a lookup instead of len(phases) sines per pixel
    col_shift = [sum(shape(y / wavelength + ph) for ph in phases) / len(phases) * amplitude
                 for y in range(h)]
    row_shift = [sum(shape(x / wavelength + ph) for ph in phases) / len(phases) * amplitude
                 for x in range(w)]

    def fn(x, y):
        return x + col_shift[y], y + row_shift[x]

    return _remap(img, fn)


def zigzag(img: QImage, amount=30, ridges=5) -> QImage:
    w, h = img.width(), img.height()
    cx, cy = w / 2, h / 2
    radius = min(cx, cy)

    def fn(x, y):
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d < 0.01 or d > radius:
            return x, y
        push = math.sin(d / radius * ridges * math.pi) * amount / 100.0 * 12
        return x + dx / d * push, y + dy / d * push

    return _remap(img, fn)


def spherize(img: QImage, amount=50) -> QImage:
    w, h = img.width(), img.height()
    cx, cy = w / 2, h / 2
    radius = min(cx, cy)
    k = amount / 100.0

    def fn(x, y):
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d >= radius or d == 0:
            return x, y
        t = d / radius
        # bulge maps the flat radius onto a hemisphere; a negative amount
        # pushes it the other way, which is what PS calls a dented sphere.
        bulge = math.asin(min(1.0, t)) / (math.pi / 2)
        nd = radius * (t * (1 - abs(k)) + (bulge if k > 0 else t * t) * abs(k))
        return cx + dx * (nd / d), cy + dy * (nd / d)

    return _remap(img, fn)


def pinch(img: QImage, amount=50) -> QImage:
    w, h = img.width(), img.height()
    cx, cy = w / 2, h / 2
    radius = min(cx, cy)
    k = amount / 100.0

    def fn(x, y):
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d >= radius or d == 0:
            return x, y
        t = d / radius
        nd = d * (t ** k if k > 0 else t ** k)
        return cx + dx * (nd / d) * 1.0, cy + dy * (nd / d) * 1.0

    return _remap(img, fn)


def polar_coordinates(img: QImage, to_polar=True) -> QImage:
    w, h = img.width(), img.height()
    cx, cy = w / 2, h / 2
    maxr = math.hypot(cx, cy)

    if to_polar:
        def fn(x, y):
            dx, dy = x - cx, y - cy
            ang = (math.atan2(dx, -dy) + math.pi) / math.tau
            r = math.hypot(dx, dy) / maxr
            return ang * w, r * h
    else:
        def fn(x, y):
            ang = x / w * math.tau - math.pi
            r = y / h * maxr
            return cx + math.sin(ang) * r, cy - math.cos(ang) * r

    return _remap(img, fn)


def shear(img: QImage, amount=20) -> QImage:
    h = img.height()

    def fn(x, y):
        return x + math.sin(y / h * math.pi) * amount, y

    return _remap(img, fn)


def displace(img: QImage, h_scale=10, v_scale=10, seed=5) -> QImage:
    rng = random.Random(seed)
    noise = [[(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(16)] for _ in range(16)]
    w, h = img.width(), img.height()

    def fn(x, y):
        nx, ny = noise[int(y * 16 / h) % 16][int(x * 16 / w) % 16]
        return x + nx * h_scale, y + ny * v_scale

    return _remap(img, fn)


def offset(img: QImage, dx=0, dy=0, wrap=True) -> QImage:
    return _offset_image(img, dx, dy, wrap=wrap)


def glass(img: QImage, distortion=5, smoothness=3) -> QImage:
    return displace(gaussian_blur(img, smoothness / 3.0), distortion, distortion, seed=17)


# ----------------------------------------------------------------- render ---

def _octave_noise(w, h, cells, seed) -> QImage:
    rng = random.Random(seed)
    small = QImage(max(2, cells), max(2, cells), QImage.Format.Format_ARGB32)
    for y in range(small.height()):
        for x in range(small.width()):
            v = rng.randint(0, 255)
            small.setPixelColor(x, y, QColor(v, v, v))
    return small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


def clouds(img: QImage, fg: QColor, bg: QColor, seed=None) -> QImage:
    w, h = img.width(), img.height()
    seed = random.randint(0, 1 << 30) if seed is None else seed
    acc = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    acc.fill(Qt.GlobalColor.black)
    p = QPainter(acc)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    amp = 0.5
    for octave in range(6):
        p.setOpacity(amp)
        p.drawImage(0, 0, _octave_noise(w, h, 2 << octave, seed + octave))
        amp *= 0.5
    p.end()
    acc = apply_lut(acc, [_clamp(int((i / 255.0) ** 1.15 * 300 - 22)) for i in range(256)])
    return gradient_map(acc, [(0.0, bg), (1.0, fg)])


def difference_clouds(img: QImage, fg: QColor, bg: QColor) -> QImage:
    c = clouds(img, fg, bg)
    return combine(img, c, lambda a, b: abs(a - b))


def fibers(img: QImage, variance=16, strength=4) -> QImage:
    w, h = img.width(), img.height()
    base = clouds(img, QColor("white"), QColor("black"))
    return motion_blur(add_noise(base, variance), 90, strength * 6)


def lens_flare(img: QImage, cx=None, cy=None, brightness=100, lens="50-300mm Zoom") -> QImage:
    w, h = img.width(), img.height()
    cx = w * 0.62 if cx is None else cx
    cy = h * 0.38 if cy is None else cy
    out = img.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    k = brightness / 100.0

    core = QRadialGradient(cx, cy, min(w, h) * 0.30)
    core.setColorAt(0.0, QColor(255, 255, 250, int(235 * k)))
    core.setColorAt(0.18, QColor(255, 240, 200, int(120 * k)))
    core.setColorAt(1.0, QColor(255, 200, 120, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(core))
    p.drawEllipse(QPointF(cx, cy), min(w, h) * 0.30, min(w, h) * 0.30)

    rays = 8 if "Zoom" in lens else 6
    p.save()
    p.translate(cx, cy)
    for i in range(rays):
        p.save()
        p.rotate(180.0 * i / rays + 10)
        g = QLinearGradient(-w, 0, w, 0)
        g.setColorAt(0.0, QColor(255, 230, 190, 0))
        g.setColorAt(0.5, QColor(255, 245, 220, int(90 * k)))
        g.setColorAt(1.0, QColor(255, 230, 190, 0))
        p.setBrush(QBrush(g))
        p.drawRect(QRectF(-w, -1.4, w * 2, 2.8))
        p.restore()
    p.restore()

    dx, dy = w / 2 - cx, h / 2 - cy
    ghosts = [(0.35, 14, QColor(120, 255, 160)), (0.62, 22, QColor(255, 160, 120)),
              (0.95, 11, QColor(140, 180, 255)), (1.35, 26, QColor(255, 220, 120)),
              (1.72, 9, QColor(200, 140, 255))]
    for t, rad, col in ghosts:
        gx, gy = cx + dx * 2 * t, cy + dy * 2 * t
        col = QColor(col)
        col.setAlpha(int(60 * k))
        gg = QRadialGradient(gx, gy, rad)
        gg.setColorAt(0.55, QColor(col.red(), col.green(), col.blue(), 0))
        gg.setColorAt(0.85, col)
        gg.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
        p.setBrush(QBrush(gg))
        p.drawEllipse(QPointF(gx, gy), rad, rad)
    p.end()
    return out


def lighting_effects(img: QImage, style="Default", intensity=35, cx=None, cy=None,
                     radius=None, ambient=20) -> QImage:
    w, h = img.width(), img.height()
    cx = w / 2 if cx is None else cx
    cy = h / 2 if cy is None else cy
    radius = min(w, h) * 0.7 if radius is None else radius
    light = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    amb = _clamp(int(ambient * 2.55))
    light.fill(QColor(amb, amb, amb))
    p = QPainter(light)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    g = QRadialGradient(cx, cy, radius)
    v = _clamp(int(intensity * 5))
    g.setColorAt(0.0, QColor(v, v, v))
    g.setColorAt(1.0, QColor(0, 0, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawRect(0, 0, w, h)
    p.end()
    return combine(img, light, lambda a, b: a * b / 128.0)


def texturizer(img: QImage, texture="Canvas", scale=100, relief=4) -> QImage:
    w, h = img.width(), img.height()
    tex = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    tex.fill(QColor(128, 128, 128))
    p = QPainter(tex)
    step = max(2, int(6 * scale / 100))
    if texture == "Canvas":
        p.setPen(QPen(QColor(150, 150, 150), 1))
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        p.setPen(QPen(QColor(105, 105, 105), 1))
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)
    elif texture == "Brick":
        p.setPen(QPen(QColor(100, 100, 100), 1))
        bh = step * 3
        for i, y in enumerate(range(0, h, bh)):
            p.drawLine(0, y, w, y)
            off = 0 if i % 2 == 0 else step * 3
            for x in range(off, w, step * 6):
                p.drawLine(x, y, x, y + bh)
    elif texture == "Burlap":
        rng = random.Random(4)
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                v = 128 + rng.randint(-30, 30)
                p.fillRect(x, y, 2, 2, QColor(v, v, v))
    else:  # Sandstone
        p.end()
        tex = add_noise(tex, 18, monochromatic=True)
        tex = gaussian_blur(tex, 0.7)
        p = QPainter(tex)
    p.end()
    emb = emboss(tex, 135, max(1, relief // 2), 100)
    return combine(img, emb, lambda a, b: a + (b - 128) * 0.9)


# ------------------------------------------------------------------ misc ----

def apply_to_channel(img: QImage, fn, channel) -> QImage:
    """Run fn over one channel only, keeping the other two."""
    if channel == "RGB":
        return fn(img)
    processed = fn(img)
    src, w, h = to_buf(img)
    new, _, _ = to_buf(processed)
    ch = {"Red": R, "Green": G, "Blue": B}[channel]
    set_plane(src, ch, plane(new, ch))
    return from_buf(src, w, h)


def flip(img: QImage, horizontal=True) -> QImage:
    return img.mirrored(horizontal, not horizontal)


def rotate(img: QImage, degrees: float, expand=True) -> QImage:
    tr = QTransform().rotate(degrees)
    return img.transformed(tr, Qt.TransformationMode.SmoothTransformation)


def note_paper(img: QImage) -> QImage:
    g = desaturate(img)
    g = threshold(g, 128)
    g = add_noise(g, 6, monochromatic=True)
    return gaussian_blur(g, 0.6)


def photocopy(img: QImage, detail=7, darkness=8) -> QImage:
    g = desaturate(img)
    hp = high_pass(g, max(1, 14 - detail))
    return threshold(hp, _clamp(128 + (darkness - 8) * 6))


def chalk_and_charcoal(img: QImage) -> QImage:
    g = desaturate(img)
    e = find_edges(g)
    return combine(g, e, lambda a, b: (a + b) // 2)


def stamp(img: QImage, smoothness=4, light_dark=25) -> QImage:
    g = gaussian_blur(desaturate(img), smoothness)
    return threshold(g, _clamp(int(light_dark * 5.1)))


def sponge(img: QImage) -> QImage:
    return median(add_noise(img, 10), 2)


def watercolor(img: QImage) -> QImage:
    return median(gaussian_blur(posterize(img, 6), 1.2), 2)


def dry_brush(img: QImage) -> QImage:
    return median(posterize(img, 8), 1)


def palette_knife(img: QImage) -> QImage:
    return median(posterize(img, 5), 3)


def plastic_wrap(img: QImage) -> QImage:
    e = invert(find_edges(gaussian_blur(img, 2)))
    return combine(img, e, lambda a, b: min(255, a + b // 2))


def poster_edges(img: QImage, thickness=2, intensity=4, posterization=2) -> QImage:
    base = posterize(img, max(2, 12 - posterization * 2))
    e = find_edges(img)
    if thickness > 1:
        e = minimum(e, thickness - 1)
    return combine(base, e, lambda a, b: a * b // 255)
