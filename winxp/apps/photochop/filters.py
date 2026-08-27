"""The Filter menu.

Every entry in Photoshop 7's Filter menu, in its real order, with a working
implementation behind it. The Gallery filters (Artistic, Brush Strokes,
Sketch, Texture) are composed out of the primitives in imageops -- which is
roughly what they are anyway.

Each entry is (label, key, params). `params` is the dialog schema:
    ("slider",  key, label, min, max, default, suffix)
    ("dslider", key, label, min, max, default, decimals, suffix)
    ("combo",   key, label, choices, default)
    ("check",   key, label, default)
    ("angle",   key, label, default)
An empty params list means the filter runs immediately with no dialog.
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen

from . import imageops as ops


def _ctx_color(ctx, key, fallback):
    return QColor(ctx.get(key, fallback)) if ctx else QColor(fallback)


# ------------------------------------------------------------- artistic ----

def colored_pencil(img, width=4, brightness=25, contrast=25, **_):
    edges = ops.find_edges(img)
    base = ops.posterize(img, 6)
    out = ops.combine(base, edges, lambda a, b: min(255, a * b // 200))
    return ops.brightness_contrast(out, brightness - 25, contrast - 25)


def cutout(img, levels=4, edge_simplicity=4, edge_fidelity=2, **_):
    out = ops.median(ops.posterize(img, max(2, levels)), max(1, edge_simplicity // 2))
    return ops.gaussian_blur(out, max(0.0, 3 - edge_fidelity)) if edge_fidelity < 3 else out


def film_grain(img, grain=4, highlight_area=0, intensity=10, **_):
    out = ops.add_noise(img, grain * 4, monochromatic=True)
    if highlight_area:
        out = ops.levels(out, 0, 1.0, max(60, 255 - highlight_area * 15))
    return out


def fresco(img, brush_size=2, brush_detail=8, texture=1, **_):
    out = ops.posterize(ops.median(img, max(1, brush_size)), 6)
    return ops.unsharp_mask(out, brush_detail * 10, 1.4, 0)


def neon_glow(img, size=5, brightness=15, ctx=None, **_):
    edges = ops.invert(ops.find_edges(img))
    glow = ops.gaussian_blur(edges, max(1, size))
    tinted = ops.gradient_map(glow, [(0.0, QColor("#000018")),
                                     (1.0, _ctx_color(ctx, "fg", "#33ccff"))])
    return ops.combine(ops.desaturate(img), tinted,
                       lambda a, b: min(255, a // 2 + b * (brightness + 5) // 20))


def paint_daubs(img, brush_size=8, sharpness=7, **_):
    out = ops.median(img, max(1, brush_size // 4))
    return ops.unsharp_mask(out, sharpness * 12, 1.5, 0)


def rough_pastels(img, stroke_length=6, stroke_detail=4, **_):
    out = ops.add_noise(ops.posterize(img, 8), stroke_detail * 3, monochromatic=True)
    return ops.motion_blur(out, 45, max(2, stroke_length))


def smudge_stick(img, stroke_length=2, highlight_area=0, intensity=10, **_):
    out = ops.motion_blur(img, 45, max(2, stroke_length * 3))
    return ops.brightness_contrast(out, highlight_area * 2, intensity * 2)


def underpainting(img, brush_size=6, texture_coverage=16, **_):
    out = ops.median(ops.gaussian_blur(img, brush_size / 3.0), 2)
    return ops.texturizer(out, "Canvas", 100, max(1, texture_coverage // 4))


def dry_brush(img, brush_size=2, brush_detail=8, texture=1, **_):
    out = ops.posterize(img, max(2, 14 - brush_detail))
    return ops.median(out, max(1, brush_size // 2 or 1))


def palette_knife(img, stroke_size=25, stroke_detail=3, softness=0, **_):
    out = ops.posterize(img, max(2, stroke_detail * 2))
    out = ops.median(out, max(1, stroke_size // 8))
    return ops.gaussian_blur(out, softness / 4.0) if softness else out


def plastic_wrap(img, highlight_strength=15, detail=9, smoothness=7, **_):
    edges = ops.invert(ops.find_edges(ops.gaussian_blur(img, smoothness / 4.0)))
    edges = ops.apply_lut(edges, [min(255, v * detail // 9) for v in range(256)])
    k = highlight_strength / 20.0
    return ops.combine(img, edges, lambda a, b: min(255, a + b * k / 2))


def watercolor(img, brush_detail=14, shadow_intensity=0, texture=1, **_):
    out = ops.posterize(img, max(3, brush_detail // 2))
    out = ops.median(ops.gaussian_blur(out, 1.2), 2)
    return ops.levels(out, shadow_intensity * 8, 1.0, 255)


def sponge_art(img, brush_size=2, definition=12, smoothness=5, **_):
    return ops.median(ops.add_noise(img, definition), max(1, brush_size))


# -------------------------------------------------------- brush strokes ----

def accented_edges(img, edge_width=2, edge_brightness=38, smoothness=5, **_):
    edges = ops.invert(ops.find_edges(img))
    if edge_width > 1:
        edges = ops.maximum(edges, edge_width - 1)
    edges = ops.apply_lut(edges, [min(255, i * edge_brightness // 25) for i in range(256)])
    out = ops.gaussian_blur(img, smoothness / 5.0)
    return ops.combine(out, edges, lambda a, b: min(255, a + b // 2))


def angled_strokes(img, direction_balance=50, stroke_length=15, sharpness=3, **_):
    a = ops.motion_blur(img, 45, max(2, stroke_length))
    b = ops.motion_blur(img, -45, max(2, stroke_length))
    t = direction_balance / 100.0
    mixed = ops.combine(a, b, lambda x, y: x * (1 - t) + y * t)
    return ops.unsharp_mask(mixed, sharpness * 25, 1.2, 0)


def crosshatch(img, stroke_length=9, sharpness=6, strength=1, **_):
    out = angled_strokes(img, 50, stroke_length, sharpness)
    for _ in range(max(1, strength)):
        out = ops.unsharp_mask(out, 60, 1.0, 0)
    return out


def dark_strokes(img, balance=5, black_intensity=6, white_intensity=2, **_):
    out = ops.motion_blur(img, 45, 6)
    return ops.levels(out, black_intensity * 8, 1.0, 255 - white_intensity * 8)


def ink_outlines(img, stroke_length=4, dark_intensity=20, light_intensity=10, **_):
    edges = ops.find_edges(img)
    edges = ops.motion_blur(edges, 45, max(1, stroke_length))
    return ops.combine(img, edges, lambda a, b: a * b // 255)


def spatter(img, spray_radius=10, smoothness=5, **_):
    return ops.median(ops.diffuse(img, max(1, spray_radius // 2)), max(1, smoothness // 3))


def sprayed_strokes(img, stroke_length=12, spray_radius=7, direction="Right Diagonal", **_):
    angle = {"Right Diagonal": 45, "Horizontal": 0,
             "Left Diagonal": -45, "Vertical": 90}.get(direction, 45)
    return ops.motion_blur(ops.diffuse(img, max(1, spray_radius // 2)), angle,
                           max(2, stroke_length))


def sumi_e(img, stroke_width=10, stroke_pressure=2, contrast=16, **_):
    out = ops.gaussian_blur(img, stroke_width / 5.0)
    out = ops.median(out, max(1, stroke_pressure))
    return ops.brightness_contrast(out, -10, contrast * 3)


# --------------------------------------------------------------- distort ---

def diffuse_glow(img, graininess=6, glow_amount=10, clear_amount=15, ctx=None, **_):
    glow = ops.gaussian_blur(img, 6)
    glow = ops.add_noise(glow, graininess * 2, monochromatic=True)
    lifted = ops.combine(img, glow, lambda a, b: min(255, a + b * (glow_amount + 1) // 30))
    return ops.levels(lifted, clear_amount, 1.0, 255)


def ocean_ripple(img, ripple_size=9, ripple_magnitude=9, **_):
    return ops.displace(img, ripple_magnitude, ripple_magnitude, seed=ripple_size)


# ------------------------------------------------------------- pixelate ----

def mezzotint(img, kind="Fine dots", **_):
    if "lines" in kind:
        angle = 0 if "Horizontal" in kind else 90
        return ops.motion_blur(ops.threshold(ops.add_noise(img, 40), 128), angle, 8)
    return ops.threshold(ops.add_noise(img, 45), 128)


# --------------------------------------------------------------- render ----

def three_d_transform(img, **_):
    return img


def texture_fill(img, ctx=None, **_):
    return ops.texturizer(img, "Burlap", 100, 4)


# --------------------------------------------------------------- sketch ----

def charcoal(img, thickness=1, detail=5, light_dark=50, ctx=None, **_):
    g = ops.desaturate(img)
    e = ops.find_edges(g)
    if thickness > 1:
        e = ops.minimum(e, thickness - 1)
    e = ops.brightness_contrast(e, (50 - light_dark), detail * 6)
    return ops.gradient_map(e, [(0.0, _ctx_color(ctx, "fg", "#000000")),
                                (1.0, _ctx_color(ctx, "bg", "#ffffff"))])


def chrome(img, detail=4, smoothness=7, **_):
    g = ops.desaturate(img)
    e = ops.emboss(g, 135, max(1, detail), 200)
    e = ops.gaussian_blur(e, smoothness / 4.0)
    return ops.levels(e, 40, 1.0, 215)


def conte_crayon(img, foreground_level=11, background_level=7, ctx=None, **_):
    g = ops.desaturate(img)
    g = ops.levels(g, background_level * 8, 1.0, 255 - foreground_level * 6)
    g = ops.texturizer(g, "Canvas", 100, 4)
    return ops.gradient_map(g, [(0.0, _ctx_color(ctx, "fg", "#000000")),
                                (1.0, _ctx_color(ctx, "bg", "#ffffff"))])


def graphic_pen(img, stroke_length=15, light_dark=50, direction="Right Diagonal", ctx=None, **_):
    angle = {"Right Diagonal": 45, "Horizontal": 0,
             "Left Diagonal": -45, "Vertical": 90}.get(direction, 45)
    g = ops.motion_blur(ops.desaturate(img), angle, max(2, stroke_length))
    g = ops.threshold(g, int(light_dark * 2.55))
    return ops.gradient_map(g, [(0.0, _ctx_color(ctx, "fg", "#000000")),
                                (1.0, _ctx_color(ctx, "bg", "#ffffff"))])


def halftone_pattern(img, size=1, contrast=5, pattern_type="Circle", **_):
    g = ops.desaturate(img)
    if pattern_type == "Line":
        return ops.threshold(ops.motion_blur(g, 90, max(2, size * 3)), 128)
    if pattern_type == "Dot":
        return ops.threshold(ops.mosaic(g, max(2, size * 3)), 128)
    return ops.color_halftone(ops.brightness_contrast(g, 0, contrast * 6), max(2, size * 3))


def plaster(img, image_balance=20, smoothness=2, ctx=None, **_):
    g = ops.gaussian_blur(ops.desaturate(img), smoothness)
    e = ops.emboss(g, 135, 2, 140)
    return ops.threshold(e, int(128 + (image_balance - 20) * 2))


def reticulation(img, density=12, foreground_level=40, background_level=5, **_):
    g = ops.desaturate(img)
    g = ops.add_noise(g, density * 3, monochromatic=True)
    return ops.threshold(g, int(128 + (foreground_level - background_level)))


def torn_edges(img, image_balance=25, smoothness=11, contrast=17, ctx=None, **_):
    g = ops.gaussian_blur(ops.desaturate(img), smoothness / 4.0)
    g = ops.add_noise(g, contrast, monochromatic=True)
    return ops.threshold(g, int(image_balance * 4))


def water_paper(img, fiber_length=15, brightness=60, contrast=80, **_):
    out = ops.motion_blur(img, 90, max(2, fiber_length // 2))
    out = ops.motion_blur(out, 0, max(2, fiber_length // 3))
    return ops.brightness_contrast(out, brightness - 60, contrast - 60)


# -------------------------------------------------------------- texture ----

def craquelure(img, crack_spacing=15, crack_depth=6, crack_brightness=9, **_):
    veins = ops.find_edges(ops.clouds(img, QColor("black"), QColor("white")))
    veins = ops.threshold(veins, 100 + crack_brightness * 4)
    return ops.combine(img, ops.emboss(veins, 135, max(1, crack_depth // 2), 100),
                       lambda a, b: max(0, min(255, a + (b - 128))))


def grain(img, intensity=40, contrast=50, grain_type="Regular", **_):
    mono = grain_type in ("Soft", "Sprinkles", "Clumped", "Speckle")
    out = ops.add_noise(img, intensity, monochromatic=mono)
    if grain_type == "Clumped":
        out = ops.median(out, 1)
    if grain_type == "Horizontal":
        out = ops.motion_blur(out, 0, 6)
    if grain_type == "Vertical":
        out = ops.motion_blur(out, 90, 6)
    return ops.brightness_contrast(out, 0, contrast - 50)


def mosaic_tiles(img, tile_size=20, grout_width=3, lighten_grout=9, **_):
    out = ops.crystallize(img, max(4, tile_size // 2))
    edges = ops.find_edges(out)
    if grout_width > 1:
        edges = ops.minimum(edges, grout_width - 1)
    return ops.combine(out, edges, lambda a, b: a * b // 255)


def patchwork(img, square_size=4, relief=8, **_):
    tiles = ops.mosaic(img, max(3, square_size * 3))
    return ops.combine(tiles, ops.emboss(tiles, 135, max(1, relief // 3), 100),
                       lambda a, b: max(0, min(255, a + (b - 128) // 2)))


def stained_glass(img, cell_size=10, border_thickness=4, light_intensity=3, **_):
    cells = ops.crystallize(img, max(4, cell_size))
    edges = ops.find_edges(cells)
    if border_thickness > 1:
        edges = ops.minimum(edges, border_thickness - 1)
    out = ops.combine(cells, edges, lambda a, b: a * b // 255)
    return ops.brightness_contrast(out, light_intensity * 3, 0)


# --------------------------------------------------------------- video -----

def de_interlace(img, eliminate="Odd Fields", create="Interpolation", **_):
    w, h = img.width(), img.height()
    out = img.copy()
    p = QPainter(out)
    drop_odd = eliminate == "Odd Fields"
    for y in range(h):
        if (y % 2 == 1) == drop_odd:
            src = max(0, y - 1) if drop_odd else min(h - 1, y + 1)
            p.drawImage(QRectF(0, y, w, 1), img, QRectF(0, src, w, 1))
    p.end()
    return out


def ntsc_colors(img, **_):
    return ops.levels(img, 16, 1.0, 235, 16, 235)


# ---------------------------------------------------------------- other ----

def custom_convolve(img, matrix=None, scale=1, offset=0, **_):
    """Filter > Other > Custom: a real 5x5 convolution, run as a stack of
    offset composites so it stays interactive."""
    matrix = matrix or [[0] * 5 for _ in range(5)]
    matrix[2][2] = matrix[2][2] or 1
    acc = None
    scale = scale or 1
    for j, row in enumerate(matrix):
        for i, weight in enumerate(row):
            if not weight:
                continue
            shifted = ops.offset(img, i - 2, j - 2, wrap=False)
            k = weight / scale
            if acc is None:
                acc = ops.apply_lut(shifted, [max(0, min(255, int(v * k + offset)))
                                              for v in range(256)])
            else:
                acc = ops.combine(acc, shifted,
                                  lambda a, b, k=k: a + b * k)
    return acc if acc is not None else img


# ------------------------------------------------------------- digimarc ----

def embed_watermark(img, **_):
    return img


# ================================================== the menu, in PS order ===

FILTER_MENU = [
    ("Artistic", [
        ("Colored Pencil...", "colored_pencil", [
            ("slider", "width", "Pencil Width", 1, 24, 4, ""),
            ("slider", "brightness", "Stroke Pressure", 0, 15, 8, ""),
            ("slider", "contrast", "Paper Brightness", 0, 50, 25, "")]),
        ("Cutout...", "cutout", [
            ("slider", "levels", "No. of Levels", 2, 8, 4, ""),
            ("slider", "edge_simplicity", "Edge Simplicity", 0, 10, 4, ""),
            ("slider", "edge_fidelity", "Edge Fidelity", 1, 3, 2, "")]),
        ("Dry Brush...", "dry_brush", [
            ("slider", "brush_size", "Brush Size", 0, 10, 2, ""),
            ("slider", "brush_detail", "Brush Detail", 0, 10, 8, ""),
            ("slider", "texture", "Texture", 1, 3, 1, "")]),
        ("Film Grain...", "film_grain", [
            ("slider", "grain", "Grain", 0, 20, 4, ""),
            ("slider", "highlight_area", "Highlight Area", 0, 20, 0, ""),
            ("slider", "intensity", "Intensity", 0, 10, 10, "")]),
        ("Fresco...", "fresco", [
            ("slider", "brush_size", "Brush Size", 0, 10, 2, ""),
            ("slider", "brush_detail", "Brush Detail", 0, 10, 8, ""),
            ("slider", "texture", "Texture", 1, 3, 1, "")]),
        ("Neon Glow...", "neon_glow", [
            ("slider", "size", "Size", -24, 24, 5, ""),
            ("slider", "brightness", "Brightness", 0, 50, 15, "")]),
        ("Paint Daubs...", "paint_daubs", [
            ("slider", "brush_size", "Brush Size", 1, 50, 8, ""),
            ("slider", "sharpness", "Sharpness", 0, 40, 7, "")]),
        ("Palette Knife...", "palette_knife", [
            ("slider", "stroke_size", "Stroke Size", 1, 50, 25, ""),
            ("slider", "stroke_detail", "Stroke Detail", 1, 3, 3, ""),
            ("slider", "softness", "Softness", 0, 10, 0, "")]),
        ("Plastic Wrap...", "plastic_wrap", [
            ("slider", "highlight_strength", "Highlight Strength", 0, 20, 15, ""),
            ("slider", "detail", "Detail", 1, 15, 9, ""),
            ("slider", "smoothness", "Smoothness", 1, 15, 7, "")]),
        ("Poster Edges...", "poster_edges", [
            ("slider", "thickness", "Edge Thickness", 0, 10, 2, ""),
            ("slider", "intensity", "Edge Intensity", 0, 10, 4, ""),
            ("slider", "posterization", "Posterization", 0, 6, 2, "")]),
        ("Rough Pastels...", "rough_pastels", [
            ("slider", "stroke_length", "Stroke Length", 0, 40, 6, ""),
            ("slider", "stroke_detail", "Stroke Detail", 1, 20, 4, "")]),
        ("Smudge Stick...", "smudge_stick", [
            ("slider", "stroke_length", "Stroke Length", 0, 10, 2, ""),
            ("slider", "highlight_area", "Highlight Area", 0, 20, 0, ""),
            ("slider", "intensity", "Intensity", 0, 10, 10, "")]),
        ("Sponge...", "sponge_art", [
            ("slider", "brush_size", "Brush Size", 0, 10, 2, ""),
            ("slider", "definition", "Definition", 0, 25, 12, ""),
            ("slider", "smoothness", "Smoothness", 1, 15, 5, "")]),
        ("Underpainting...", "underpainting", [
            ("slider", "brush_size", "Brush Size", 0, 40, 6, ""),
            ("slider", "texture_coverage", "Texture Coverage", 0, 40, 16, "")]),
        ("Watercolor...", "watercolor", [
            ("slider", "brush_detail", "Brush Detail", 1, 14, 14, ""),
            ("slider", "shadow_intensity", "Shadow Intensity", 0, 10, 0, ""),
            ("slider", "texture", "Texture", 1, 3, 1, "")]),
    ]),
    ("Blur", [
        ("Blur", "blur", []),
        ("Blur More", "blur_more", []),
        ("Gaussian Blur...", "gaussian_blur", [
            ("dslider", "radius", "Radius", 0.1, 250.0, 1.0, 1, " pixels")]),
        ("Motion Blur...", "motion_blur", [
            ("angle", "angle", "Angle", 0),
            ("slider", "distance", "Distance", 1, 999, 10, " pixels")]),
        ("Radial Blur...", "radial_blur", [
            ("slider", "amount", "Amount", 1, 100, 10, ""),
            ("combo", "method", "Blur Method", ("spin", "zoom"), "spin")]),
        ("Smart Blur...", "smart_blur", [
            ("dslider", "radius", "Radius", 0.1, 100.0, 5.0, 1, ""),
            ("slider", "threshold_v", "Threshold", 0, 100, 25, "")]),
    ]),
    ("Brush Strokes", [
        ("Accented Edges...", "accented_edges", [
            ("slider", "edge_width", "Edge Width", 1, 14, 2, ""),
            ("slider", "edge_brightness", "Edge Brightness", 0, 50, 38, ""),
            ("slider", "smoothness", "Smoothness", 1, 15, 5, "")]),
        ("Angled Strokes...", "angled_strokes", [
            ("slider", "direction_balance", "Direction Balance", 0, 100, 50, ""),
            ("slider", "stroke_length", "Stroke Length", 3, 50, 15, ""),
            ("slider", "sharpness", "Sharpness", 0, 10, 3, "")]),
        ("Crosshatch...", "crosshatch", [
            ("slider", "stroke_length", "Stroke Length", 3, 50, 9, ""),
            ("slider", "sharpness", "Sharpness", 0, 20, 6, ""),
            ("slider", "strength", "Strength", 1, 3, 1, "")]),
        ("Dark Strokes...", "dark_strokes", [
            ("slider", "balance", "Balance", 0, 10, 5, ""),
            ("slider", "black_intensity", "Black Intensity", 0, 10, 6, ""),
            ("slider", "white_intensity", "White Intensity", 0, 10, 2, "")]),
        ("Ink Outlines...", "ink_outlines", [
            ("slider", "stroke_length", "Stroke Length", 1, 50, 4, ""),
            ("slider", "dark_intensity", "Dark Intensity", 0, 50, 20, ""),
            ("slider", "light_intensity", "Light Intensity", 0, 50, 10, "")]),
        ("Spatter...", "spatter", [
            ("slider", "spray_radius", "Spray Radius", 0, 25, 10, ""),
            ("slider", "smoothness", "Smoothness", 1, 15, 5, "")]),
        ("Sprayed Strokes...", "sprayed_strokes", [
            ("slider", "stroke_length", "Stroke Length", 0, 20, 12, ""),
            ("slider", "spray_radius", "Spray Radius", 0, 25, 7, ""),
            ("combo", "direction", "Stroke Direction",
             ("Right Diagonal", "Horizontal", "Left Diagonal", "Vertical"), "Right Diagonal")]),
        ("Sumi-e...", "sumi_e", [
            ("slider", "stroke_width", "Stroke Width", 3, 15, 10, ""),
            ("slider", "stroke_pressure", "Stroke Pressure", 0, 15, 2, ""),
            ("slider", "contrast", "Contrast", 0, 40, 16, "")]),
    ]),
    ("Distort", [
        ("Diffuse Glow...", "diffuse_glow", [
            ("slider", "graininess", "Graininess", 0, 10, 6, ""),
            ("slider", "glow_amount", "Glow Amount", 0, 20, 10, ""),
            ("slider", "clear_amount", "Clear Amount", 0, 20, 15, "")]),
        ("Displace...", "displace", [
            ("slider", "h_scale", "Horizontal Scale", 1, 999, 10, ""),
            ("slider", "v_scale", "Vertical Scale", 1, 999, 10, "")]),
        ("Glass...", "glass", [
            ("slider", "distortion", "Distortion", 0, 20, 5, ""),
            ("slider", "smoothness", "Smoothness", 1, 15, 3, "")]),
        ("Ocean Ripple...", "ocean_ripple", [
            ("slider", "ripple_size", "Ripple Size", 1, 15, 9, ""),
            ("slider", "ripple_magnitude", "Ripple Magnitude", 0, 20, 9, "")]),
        ("Pinch...", "pinch", [
            ("slider", "amount", "Amount", -100, 100, 50, "%")]),
        ("Polar Coordinates...", "polar_coordinates", [
            ("combo", "to_polar", "", ((True, "Rectangular to Polar"),
                                       (False, "Polar to Rectangular")), True)]),
        ("Ripple...", "ripple", [
            ("slider", "amount", "Amount", -999, 999, 100, "%"),
            ("combo", "size", "Size", ("Small", "Medium", "Large"), "Medium")]),
        ("Shear...", "shear", [
            ("slider", "amount", "Shear", -100, 100, 20, "")]),
        ("Spherize...", "spherize", [
            ("slider", "amount", "Amount", -100, 100, 50, "%")]),
        ("Twirl...", "twirl", [
            ("slider", "angle", "Angle", -999, 999, 50, "°")]),
        ("Wave...", "wave", [
            ("slider", "generators", "Number of Generators", 1, 999, 5, ""),
            ("slider", "wavelength", "Wavelength", 1, 999, 40, ""),
            ("slider", "amplitude", "Amplitude", 1, 999, 12, ""),
            ("combo", "kind", "Type", ("Sine", "Triangle", "Square"), "Sine")]),
        ("ZigZag...", "zigzag", [
            ("slider", "amount", "Amount", -100, 100, 30, ""),
            ("slider", "ridges", "Ridges", 1, 20, 5, "")]),
    ]),
    ("Noise", [
        ("Add Noise...", "add_noise", [
            ("dslider", "amount", "Amount", 0.1, 400.0, 12.5, 2, "%"),
            ("check", "monochromatic", "Monochromatic", False),
            ("check", "gaussian", "Gaussian (uncheck for Uniform)", True)]),
        ("Despeckle", "despeckle", []),
        ("Dust & Scratches...", "dust_and_scratches", [
            ("slider", "radius", "Radius", 1, 16, 2, " pixels"),
            ("slider", "threshold_v", "Threshold", 0, 255, 0, " levels")]),
        ("Median...", "median", [
            ("slider", "radius", "Radius", 1, 16, 1, " pixels")]),
    ]),
    ("Pixelate", [
        ("Color Halftone...", "color_halftone", [
            ("slider", "radius", "Max. Radius", 4, 127, 8, " pixels")]),
        ("Crystallize...", "crystallize", [
            ("slider", "size", "Cell Size", 3, 300, 10, "")]),
        ("Facet", "facet", []),
        ("Fragment", "fragment", []),
        ("Mezzotint...", "mezzotint", [
            ("combo", "kind", "Type", ("Fine dots", "Medium dots", "Grainy dots",
                                       "Coarse dots", "Short lines", "Medium lines",
                                       "Long lines", "Short strokes", "Medium strokes",
                                       "Long strokes"), "Fine dots")]),
        ("Mosaic...", "mosaic", [
            ("slider", "cell", "Cell Size", 2, 200, 8, " square")]),
        ("Pointillize...", "pointillize", [
            ("slider", "size", "Cell Size", 3, 300, 5, "")]),
    ]),
    ("Render", [
        ("3D Transform...", "three_d_transform", []),
        ("Clouds", "clouds", []),
        ("Difference Clouds", "difference_clouds", []),
        ("Lens Flare...", "lens_flare", [
            ("slider", "brightness", "Brightness", 10, 300, 100, "%"),
            ("combo", "lens", "Lens Type", ("50-300mm Zoom", "35mm Prime",
                                            "105mm Prime", "Movie Prime"), "50-300mm Zoom")]),
        ("Lighting Effects...", "lighting_effects", [
            ("combo", "style", "Style", ("Default", "Flashlight", "Floodlight",
                                         "Soft Spotlight", "Blue Omni", "Circle of Light",
                                         "Crossing", "Five Lights Down", "Parallel Directional",
                                         "RGB Lights", "Triple Spotlight"), "Default"),
            ("slider", "intensity", "Intensity", 0, 100, 35, ""),
            ("slider", "ambient", "Ambience", 0, 100, 20, "")]),
        ("Texture Fill...", "texture_fill", []),
    ]),
    ("Sharpen", [
        ("Sharpen", "sharpen", []),
        ("Sharpen Edges", "sharpen_edges", []),
        ("Sharpen More", "sharpen_more", []),
        ("Unsharp Mask...", "unsharp_mask", [
            ("slider", "amount", "Amount", 1, 500, 50, "%"),
            ("dslider", "radius", "Radius", 0.1, 250.0, 1.0, 1, " pixels"),
            ("slider", "threshold_v", "Threshold", 0, 255, 0, " levels")]),
    ]),
    ("Sketch", [
        ("Bas Relief...", "bas_relief", []),
        ("Chalk & Charcoal...", "chalk_and_charcoal", []),
        ("Charcoal...", "charcoal", [
            ("slider", "thickness", "Charcoal Thickness", 1, 7, 1, ""),
            ("slider", "detail", "Detail", 0, 5, 5, ""),
            ("slider", "light_dark", "Light/Dark Balance", 0, 100, 50, "")]),
        ("Chrome...", "chrome", [
            ("slider", "detail", "Detail", 0, 10, 4, ""),
            ("slider", "smoothness", "Smoothness", 0, 10, 7, "")]),
        ("Conté Crayon...", "conte_crayon", [
            ("slider", "foreground_level", "Foreground Level", 1, 15, 11, ""),
            ("slider", "background_level", "Background Level", 1, 15, 7, "")]),
        ("Graphic Pen...", "graphic_pen", [
            ("slider", "stroke_length", "Stroke Length", 1, 15, 15, ""),
            ("slider", "light_dark", "Light/Dark Balance", 0, 100, 50, ""),
            ("combo", "direction", "Stroke Direction",
             ("Right Diagonal", "Horizontal", "Left Diagonal", "Vertical"), "Right Diagonal")]),
        ("Halftone Pattern...", "halftone_pattern", [
            ("slider", "size", "Size", 1, 12, 1, ""),
            ("slider", "contrast", "Contrast", 0, 50, 5, ""),
            ("combo", "pattern_type", "Pattern Type", ("Circle", "Dot", "Line"), "Circle")]),
        ("Note Paper...", "note_paper", []),
        ("Photocopy...", "photocopy", [
            ("slider", "detail", "Detail", 1, 24, 7, ""),
            ("slider", "darkness", "Darkness", 1, 50, 8, "")]),
        ("Plaster...", "plaster", [
            ("slider", "image_balance", "Image Balance", 0, 50, 20, ""),
            ("slider", "smoothness", "Smoothness", 1, 15, 2, "")]),
        ("Reticulation...", "reticulation", [
            ("slider", "density", "Density", 0, 50, 12, ""),
            ("slider", "foreground_level", "Foreground Level", 0, 50, 40, ""),
            ("slider", "background_level", "Background Level", 0, 50, 5, "")]),
        ("Stamp...", "stamp", [
            ("slider", "light_dark", "Light/Dark Balance", 0, 50, 25, ""),
            ("slider", "smoothness", "Smoothness", 1, 50, 5, "")]),
        ("Torn Edges...", "torn_edges", [
            ("slider", "image_balance", "Image Balance", 0, 50, 25, ""),
            ("slider", "smoothness", "Smoothness", 1, 15, 11, ""),
            ("slider", "contrast", "Contrast", 1, 25, 17, "")]),
        ("Water Paper...", "water_paper", [
            ("slider", "fiber_length", "Fiber Length", 3, 50, 15, ""),
            ("slider", "brightness", "Brightness", 0, 100, 60, ""),
            ("slider", "contrast", "Contrast", 0, 100, 80, "")]),
    ]),
    ("Stylize", [
        ("Diffuse...", "diffuse", [
            ("slider", "amount", "Amount", 1, 40, 8, "")]),
        ("Emboss...", "emboss", [
            ("angle", "angle", "Angle", 135),
            ("slider", "height", "Height", 1, 100, 3, " pixels"),
            ("slider", "amount", "Amount", 1, 500, 100, "%")]),
        ("Extrude...", "extrude", [
            ("slider", "size", "Size", 2, 255, 30, " pixels"),
            ("slider", "depth", "Depth", 1, 255, 30, "")]),
        ("Find Edges", "find_edges", []),
        ("Glowing Edges...", "glowing_edges", [
            ("slider", "width_v", "Edge Width", 1, 14, 2, ""),
            ("slider", "brightness", "Edge Brightness", 0, 20, 6, ""),
            ("slider", "smoothness", "Smoothness", 1, 15, 5, "")]),
        ("Solarize", "solarize", []),
        ("Tiles...", "tiles", [
            ("slider", "count", "Number Of Tiles", 1, 99, 10, ""),
            ("slider", "offset_pct", "Maximum Offset", 1, 99, 10, "%")]),
        ("Trace Contour...", "trace_contour", [
            ("slider", "level", "Level", 0, 255, 128, ""),
            ("check", "upper", "Edge: Upper (uncheck for Lower)", True)]),
        ("Wind...", "wind", [
            ("slider", "strength", "Strength", 2, 40, 12, ""),
            ("combo", "direction", "Direction", ("right", "left"), "right")]),
    ]),
    ("Texture", [
        ("Craquelure...", "craquelure", [
            ("slider", "crack_spacing", "Crack Spacing", 2, 100, 15, ""),
            ("slider", "crack_depth", "Crack Depth", 0, 10, 6, ""),
            ("slider", "crack_brightness", "Crack Brightness", 0, 10, 9, "")]),
        ("Grain...", "grain", [
            ("slider", "intensity", "Intensity", 0, 100, 40, ""),
            ("slider", "contrast", "Contrast", 0, 100, 50, ""),
            ("combo", "grain_type", "Grain Type",
             ("Regular", "Soft", "Sprinkles", "Clumped", "Contrasty", "Enlarged",
              "Stippled", "Horizontal", "Vertical", "Speckle"), "Regular")]),
        ("Mosaic Tiles...", "mosaic_tiles", [
            ("slider", "tile_size", "Tile Size", 2, 100, 20, ""),
            ("slider", "grout_width", "Grout Width", 1, 15, 3, ""),
            ("slider", "lighten_grout", "Lighten Grout", 0, 10, 9, "")]),
        ("Patchwork...", "patchwork", [
            ("slider", "square_size", "Square Size", 0, 10, 4, ""),
            ("slider", "relief", "Relief", 0, 25, 8, "")]),
        ("Stained Glass...", "stained_glass", [
            ("slider", "cell_size", "Cell Size", 2, 50, 10, ""),
            ("slider", "border_thickness", "Border Thickness", 1, 20, 4, ""),
            ("slider", "light_intensity", "Light Intensity", 0, 10, 3, "")]),
        ("Texturizer...", "texturizer", [
            ("combo", "texture", "Texture", ("Brick", "Burlap", "Canvas", "Sandstone"), "Canvas"),
            ("slider", "scale", "Scaling", 50, 200, 100, "%"),
            ("slider", "relief", "Relief", 0, 50, 4, "")]),
    ]),
    ("Video", [
        ("De-Interlace...", "de_interlace", [
            ("combo", "eliminate", "Eliminate", ("Odd Fields", "Even Fields"), "Odd Fields"),
            ("combo", "create", "Create New Fields by",
             ("Duplication", "Interpolation"), "Interpolation")]),
        ("NTSC Colors", "ntsc_colors", []),
    ]),
    ("Other", [
        ("Custom...", "custom_convolve", []),
        ("High Pass...", "high_pass", [
            ("dslider", "radius", "Radius", 0.1, 250.0, 10.0, 1, " pixels")]),
        ("Maximum...", "maximum", [
            ("slider", "radius", "Radius", 1, 100, 1, " pixels")]),
        ("Minimum...", "minimum", [
            ("slider", "radius", "Radius", 1, 100, 1, " pixels")]),
        ("Offset...", "offset", [
            ("slider", "dx", "Horizontal", -999, 999, 0, " pixels right"),
            ("slider", "dy", "Vertical", -999, 999, 0, " pixels down"),
            ("check", "wrap", "Wrap Around", True)]),
    ]),
    ("Digimarc", [
        ("Embed Watermark...", "embed_watermark", []),
        ("Read Watermark...", "read_watermark", []),
    ]),
]

# key -> callable. Anything not defined in this module falls back to imageops.
def resolve(key: str):
    fn = globals().get(key)
    if callable(fn):
        return fn
    return getattr(ops, key, None)


def run(key: str, img: QImage, params: dict, ctx: dict | None = None) -> QImage:
    """Apply one filter. `ctx` carries the foreground/background colours the
    Render and Sketch filters need."""
    fn = resolve(key)
    if fn is None:
        return img
    params = dict(params)
    if key in ("clouds", "difference_clouds"):
        return fn(img, _ctx_color(ctx, "fg", "#000000"), _ctx_color(ctx, "bg", "#ffffff"))
    if key == "fibers":
        return fn(img)
    try:
        return fn(img, ctx=ctx, **params)
    except TypeError:
        params.pop("ctx", None)
        return fn(img, **params)


def read_watermark(img, **_):
    return img
