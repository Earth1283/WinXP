"""Toolbox definition: Photoshop 7's 22 slots, their flyouts, and the
options-bar schema each tool contributes.

The options bar is data-driven -- every tool declares a list of controls and
the bar builds itself, which is the only sane way to cover 45 tools.

Control spec: (kind, key, label, extra). Kinds:
    selops     the four selection-interaction buttons (new/add/subtract/intersect)
    check      checkbox
    spin       integer spin box; extra = (min, max, suffix)
    dspin      float spin box; extra = (min, max, decimals, suffix)
    combo      drop-down; extra = tuple of choices
    blend      blend-mode drop-down
    pct        percentage field with a slider flyout; extra = default
    brush      brush preset picker
    gradient   gradient preset picker
    shape      custom-shape picker
    color      colour swatch button
    font       font family / style / size / anti-aliasing cluster
    label      static text
    sep        vertical separator
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    icon: str
    shortcut: str
    hint: str
    options: tuple = ()
    cursor: str = "cross"


SELOPS = ("selops", "selop", "", None)
SEP = ("sep", "", "", None)


def _paint_opts(extra=()):
    return (("brush", "brush", "Brush:", None), SEP,
            ("blend", "mode", "Mode:", None),
            ("pct", "opacity", "Opacity:", 100)) + extra


MARQUEE_OPTS = (SELOPS, SEP, ("spin", "feather", "Feather:", (0, 250, " px")),
                ("check", "antialias", "Anti-aliased", None), SEP,
                ("combo", "style", "Style:", ("Normal", "Fixed Aspect Ratio", "Fixed Size")),
                ("spin", "fixed_w", "Width:", (1, 4000, "")),
                ("spin", "fixed_h", "Height:", (1, 4000, "")))

TOOL_GROUPS: list[list[Tool]] = [
    [
        Tool("marquee_rect", "Rectangular Marquee Tool", "marquee_rect", "M",
             "Click and drag to select a rectangular area. Use Shift, Alt, and Ctrl for additional options.",
             MARQUEE_OPTS),
        Tool("marquee_ellipse", "Elliptical Marquee Tool", "marquee_ellipse", "M",
             "Click and drag to select an elliptical area. Use Shift, Alt, and Ctrl for additional options.",
             MARQUEE_OPTS),
        Tool("marquee_row", "Single Row Marquee Tool", "marquee_row", "M",
             "Click to select a 1-pixel-high row.", (SELOPS,)),
        Tool("marquee_col", "Single Column Marquee Tool", "marquee_col", "M",
             "Click to select a 1-pixel-wide column.", (SELOPS,)),
    ],
    [
        Tool("move", "Move Tool", "move", "V",
             "Click and drag to move the selection or layer. Use Shift, Alt, and Ctrl for additional options.",
             (("check", "auto_select", "Auto Select Layer", None),
              ("check", "show_bounds", "Show Bounding Box", None)), cursor="move"),
    ],
    [
        Tool("lasso", "Lasso Tool", "lasso", "L",
             "Click and drag to draw a freehand selection.",
             (SELOPS, SEP, ("spin", "feather", "Feather:", (0, 250, " px")),
              ("check", "antialias", "Anti-aliased", None))),
        Tool("poly_lasso", "Polygonal Lasso Tool", "poly_lasso", "L",
             "Click to place points. Double-click or click the first point to close the selection.",
             (SELOPS, SEP, ("spin", "feather", "Feather:", (0, 250, " px")),
              ("check", "antialias", "Anti-aliased", None))),
        Tool("magnetic_lasso", "Magnetic Lasso Tool", "magnetic_lasso", "L",
             "Click and drag along an edge; the selection snaps to it.",
             (SELOPS, SEP, ("spin", "feather", "Feather:", (0, 250, " px")),
              ("check", "antialias", "Anti-aliased", None), SEP,
              ("spin", "width", "Width:", (1, 40, " px")),
              ("spin", "edge_contrast", "Edge Contrast:", (1, 100, "%")),
              ("spin", "frequency", "Frequency:", (0, 100, "")))),
    ],
    [
        Tool("wand", "Magic Wand Tool", "wand", "W",
             "Click to select an area of similar colour.",
             (SELOPS, SEP, ("spin", "tolerance", "Tolerance:", (0, 255, "")),
              ("check", "antialias", "Anti-aliased", None),
              ("check", "contiguous", "Contiguous", None),
              ("check", "sample_merged", "Use All Layers", None))),
    ],
    [
        Tool("crop", "Crop Tool", "crop", "C",
             "Click and drag to crop the image. Press Enter to commit, Esc to cancel.",
             (("spin", "crop_w", "Width:", (0, 8000, " px")),
              ("spin", "crop_h", "Height:", (0, 8000, " px")),
              ("spin", "resolution", "Resolution:", (1, 1200, " pixels/inch")),
              ("check", "shield", "Shield cropped area", None))),
    ],
    [
        Tool("slice", "Slice Tool", "slice", "K",
             "Click and drag to define a slice.",
             (("combo", "slice_style", "Style:", ("Normal", "Fixed Aspect Ratio", "Fixed Size")),)),
        Tool("slice_select", "Slice Select Tool", "slice_select", "K",
             "Click a slice to select it.", ()),
    ],
    [
        Tool("healing", "Healing Brush Tool", "healing", "J",
             "Alt-click to set the source, then paint to blend texture from it.",
             (("brush", "brush", "Brush:", None), SEP,
              ("blend", "mode", "Mode:", None),
              ("combo", "source", "Source:", ("Sampled", "Pattern")),
              ("check", "aligned", "Aligned", None))),
        Tool("patch", "Patch Tool", "patch", "J",
             "Draw a region, then drag it over the area to heal from.",
             (SELOPS, SEP, ("combo", "patch_mode", "Patch:", ("Source", "Destination")),
              ("check", "transparent", "Transparent", None))),
    ],
    [
        Tool("brush", "Brush Tool", "brush", "B",
             "Click and drag to paint a soft-edged stroke.",
             _paint_opts((("pct", "flow", "Flow:", 100),
                          ("check", "airbrush", "Airbrush", None)))),
        Tool("pencil", "Pencil Tool", "pencil", "B",
             "Click and drag to paint a hard-edged stroke.",
             _paint_opts((("check", "auto_erase", "Auto Erase", None),))),
    ],
    [
        Tool("clone_stamp", "Clone Stamp Tool", "clone_stamp", "S",
             "Alt-click to set the source point, then paint to copy from it.",
             _paint_opts((("pct", "flow", "Flow:", 100),
                          ("check", "aligned", "Aligned", None),
                          ("check", "sample_merged", "Use All Layers", None)))),
        Tool("pattern_stamp", "Pattern Stamp Tool", "pattern_stamp", "S",
             "Click and drag to paint with the selected pattern.",
             _paint_opts((("combo", "pattern", "Pattern:",
                           ("Checkerboard", "Diagonal Lines", "Bubbles", "Woven")),
                          ("check", "aligned", "Aligned", None)))),
    ],
    [
        Tool("history_brush", "History Brush Tool", "history_brush", "Y",
             "Paint to restore pixels from the selected history state.",
             _paint_opts()),
        Tool("art_history", "Art History Brush Tool", "art_history", "Y",
             "Paint stylised strokes sourced from the selected history state.",
             _paint_opts((("combo", "art_style", "Style:",
                           ("Tight Short", "Tight Medium", "Loose Medium",
                            "Dab", "Tight Curl", "Loose Curl")),
                          ("spin", "area", "Area:", (1, 500, " px")),
                          ("spin", "art_tolerance", "Tolerance:", (0, 100, "%"))))),
    ],
    [
        Tool("eraser", "Eraser Tool", "eraser", "E",
             "Click and drag to erase to transparency, or to the background colour on a locked layer.",
             (("brush", "brush", "Brush:", None), SEP,
              ("combo", "eraser_mode", "Mode:", ("Brush", "Pencil", "Block")),
              ("pct", "opacity", "Opacity:", 100),
              ("pct", "flow", "Flow:", 100),
              ("check", "erase_to_history", "Erase to History", None))),
        Tool("bg_eraser", "Background Eraser Tool", "bg_eraser", "E",
             "Drag to erase pixels matching the colour under the crosshair.",
             (("brush", "brush", "Brush:", None), SEP,
              ("combo", "limits", "Limits:", ("Discontiguous", "Contiguous", "Find Edges")),
              ("spin", "tolerance", "Tolerance:", (0, 100, "%")),
              ("check", "protect_fg", "Protect Foreground Color", None))),
        Tool("magic_eraser", "Magic Eraser Tool", "magic_eraser", "E",
             "Click to erase an area of similar colour.",
             (("spin", "tolerance", "Tolerance:", (0, 255, "")),
              ("check", "antialias", "Anti-aliased", None),
              ("check", "contiguous", "Contiguous", None),
              ("pct", "opacity", "Opacity:", 100))),
    ],
    [
        Tool("gradient", "Gradient Tool", "gradient", "G",
             "Click and drag to draw a gradient. Shift constrains the angle.",
             (("gradient", "gradient", "", None), SEP,
              ("combo", "gradient_type", "", ("Linear", "Radial", "Angle", "Reflected", "Diamond")),
              ("blend", "mode", "Mode:", None),
              ("pct", "opacity", "Opacity:", 100),
              ("check", "reverse", "Reverse", None),
              ("check", "dither", "Dither", None),
              ("check", "transparency", "Transparency", None))),
        Tool("bucket", "Paint Bucket Tool", "bucket", "G",
             "Click to fill an area of similar colour.",
             (("combo", "fill_source", "Fill:", ("Foreground", "Pattern")),
              ("blend", "mode", "Mode:", None),
              ("pct", "opacity", "Opacity:", 100),
              ("spin", "tolerance", "Tolerance:", (0, 255, "")),
              ("check", "antialias", "Anti-aliased", None),
              ("check", "contiguous", "Contiguous", None),
              ("check", "sample_merged", "All Layers", None))),
    ],
    [
        Tool("blur", "Blur Tool", "blur", "R",
             "Click and drag to blur the pixels you paint over.",
             (("brush", "brush", "Brush:", None), SEP,
              ("blend", "mode", "Mode:", None),
              ("pct", "strength", "Strength:", 50),
              ("check", "sample_merged", "Use All Layers", None))),
        Tool("sharpen", "Sharpen Tool", "sharpen", "R",
             "Click and drag to sharpen the pixels you paint over.",
             (("brush", "brush", "Brush:", None), SEP,
              ("blend", "mode", "Mode:", None),
              ("pct", "strength", "Strength:", 50),
              ("check", "sample_merged", "Use All Layers", None))),
        Tool("smudge", "Smudge Tool", "smudge", "R",
             "Click and drag to smear colour the way a finger would.",
             (("brush", "brush", "Brush:", None), SEP,
              ("blend", "mode", "Mode:", None),
              ("pct", "strength", "Strength:", 50),
              ("check", "finger_painting", "Finger Painting", None))),
    ],
    [
        Tool("dodge", "Dodge Tool", "dodge", "O",
             "Click and drag to lighten. Alt temporarily switches to Burn.",
             (("brush", "brush", "Brush:", None), SEP,
              ("combo", "range", "Range:", ("Shadows", "Midtones", "Highlights")),
              ("pct", "exposure", "Exposure:", 50),
              ("check", "airbrush", "Airbrush", None))),
        Tool("burn", "Burn Tool", "burn", "O",
             "Click and drag to darken. Alt temporarily switches to Dodge.",
             (("brush", "brush", "Brush:", None), SEP,
              ("combo", "range", "Range:", ("Shadows", "Midtones", "Highlights")),
              ("pct", "exposure", "Exposure:", 50),
              ("check", "airbrush", "Airbrush", None))),
        Tool("sponge", "Sponge Tool", "sponge", "O",
             "Click and drag to saturate or desaturate.",
             (("brush", "brush", "Brush:", None), SEP,
              ("combo", "sponge_mode", "Mode:", ("Desaturate", "Saturate")),
              ("pct", "flow", "Flow:", 50),
              ("check", "airbrush", "Airbrush", None))),
    ],
    [
        Tool("path_select", "Path Selection Tool", "path_select", "A",
             "Click a path to select the whole path.",
             (("check", "show_bounds", "Show Bounding Box", None),), cursor="arrow"),
        Tool("direct_select", "Direct Selection Tool", "direct_select", "A",
             "Click an anchor point to select it.", (), cursor="arrow"),
    ],
    [
        Tool("type_h", "Horizontal Type Tool", "type_h", "T",
             "Click to set an insertion point, then type.",
             (("font", "font", "", None),), cursor="ibeam"),
        Tool("type_v", "Vertical Type Tool", "type_v", "T",
             "Click to set an insertion point for vertical type.",
             (("font", "font", "", None),), cursor="ibeam"),
        Tool("type_mask_h", "Horizontal Type Mask Tool", "type_mask_h", "T",
             "Click to create a selection in the shape of the type.",
             (("font", "font", "", None),), cursor="ibeam"),
        Tool("type_mask_v", "Vertical Type Mask Tool", "type_mask_v", "T",
             "Click to create a vertical type selection.",
             (("font", "font", "", None),), cursor="ibeam"),
    ],
    [
        Tool("pen", "Pen Tool", "pen", "P",
             "Click to add anchor points; drag to curve. Close the path on the first point.",
             (("check", "rubber_band", "Rubber Band", None),
              ("check", "auto_add_delete", "Auto Add/Delete", None))),
        Tool("freeform_pen", "Freeform Pen Tool", "freeform_pen", "P",
             "Click and drag to draw a freehand path.",
             (("check", "magnetic", "Magnetic", None),)),
        Tool("add_anchor", "Add Anchor Point Tool", "add_anchor", "",
             "Click a path segment to add an anchor point.", ()),
        Tool("del_anchor", "Delete Anchor Point Tool", "del_anchor", "",
             "Click an anchor point to remove it.", ()),
        Tool("convert_point", "Convert Point Tool", "convert_point", "",
             "Click an anchor point to switch it between corner and smooth.", ()),
    ],
    [
        Tool("shape_rect", "Rectangle Tool", "shape_rect", "U",
             "Click and drag to draw a rectangle.",
             (("combo", "shape_kind", "", ("Shape Layers", "Paths", "Fill Pixels")),
              ("blend", "mode", "Mode:", None),
              ("pct", "opacity", "Opacity:", 100),
              ("check", "antialias", "Anti-aliased", None))),
        Tool("shape_round", "Rounded Rectangle Tool", "shape_round", "U",
             "Click and drag to draw a rounded rectangle.",
             (("combo", "shape_kind", "", ("Shape Layers", "Paths", "Fill Pixels")),
              ("spin", "radius", "Radius:", (0, 200, " px")),
              ("blend", "mode", "Mode:", None),
              ("pct", "opacity", "Opacity:", 100))),
        Tool("shape_ellipse", "Ellipse Tool", "shape_ellipse", "U",
             "Click and drag to draw an ellipse.",
             (("combo", "shape_kind", "", ("Shape Layers", "Paths", "Fill Pixels")),
              ("blend", "mode", "Mode:", None),
              ("pct", "opacity", "Opacity:", 100),
              ("check", "antialias", "Anti-aliased", None))),
        Tool("shape_poly", "Polygon Tool", "shape_poly", "U",
             "Click and drag to draw a polygon.",
             (("combo", "shape_kind", "", ("Shape Layers", "Paths", "Fill Pixels")),
              ("spin", "sides", "Sides:", (3, 100, "")),
              ("blend", "mode", "Mode:", None),
              ("pct", "opacity", "Opacity:", 100))),
        Tool("shape_line", "Line Tool", "shape_line", "U",
             "Click and drag to draw a line.",
             (("combo", "shape_kind", "", ("Shape Layers", "Paths", "Fill Pixels")),
              ("spin", "weight", "Weight:", (1, 100, " px")),
              ("blend", "mode", "Mode:", None),
              ("pct", "opacity", "Opacity:", 100))),
        Tool("shape_custom", "Custom Shape Tool", "shape_custom", "U",
             "Click and drag to draw the selected custom shape.",
             (("combo", "shape_kind", "", ("Shape Layers", "Paths", "Fill Pixels")),
              ("shape", "custom_shape", "Shape:", None),
              ("pct", "opacity", "Opacity:", 100))),
    ],
    [
        Tool("notes", "Notes Tool", "notes", "N",
             "Click to leave an annotation nobody will read.",
             (("combo", "author", "Author:", ("You", "The Client", "Legal")),
              ("color", "note_color", "Color:", None),
              ("combo", "note_size", "Font Size:", ("Small", "Medium", "Large"))),
             cursor="arrow"),
        Tool("audio_note", "Audio Annotation Tool", "audio_note", "N",
             "Click to record an audio annotation.",
             (("combo", "author", "Author:", ("You", "The Client", "Legal")),),
             cursor="arrow"),
    ],
    [
        Tool("eyedropper", "Eyedropper Tool", "eyedropper", "I",
             "Click to sample a colour as the foreground colour.",
             (("combo", "sample_size", "Sample Size:",
               ("Point Sample", "3 by 3 Average", "5 by 5 Average")),)),
        Tool("color_sampler", "Color Sampler Tool", "color_sampler", "I",
             "Click to place a persistent colour readout.",
             (("combo", "sample_size", "Sample Size:",
               ("Point Sample", "3 by 3 Average", "5 by 5 Average")),)),
        Tool("measure", "Measure Tool", "measure", "I",
             "Click and drag to measure a distance and angle.", ()),
    ],
    [
        Tool("hand", "Hand Tool", "hand", "H",
             "Click and drag to scroll the image. Hold Space with any tool.",
             (("check", "fit_screen", "Fit On Screen", None),), cursor="hand"),
    ],
    [
        Tool("zoom", "Zoom Tool", "zoom", "Z",
             "Click to zoom in; Alt-click to zoom out. Drag to zoom to a region.",
             (("check", "resize_windows", "Resize Windows To Fit", None),
              ("check", "ignore_palettes", "Ignore Palettes", None)),
             cursor="zoom"),
    ],
]

ALL_TOOLS = {t.id: t for group in TOOL_GROUPS for t in group}
TOOL_ORDER = [t.id for group in TOOL_GROUPS for t in group]

# Single-key shortcuts cycle through the slot, which is exactly what pressing
# M twice does in the real thing.
SHORTCUT_GROUPS: dict[str, list[str]] = {}
for _group in TOOL_GROUPS:
    for _t in _group:
        if _t.shortcut:
            SHORTCUT_GROUPS.setdefault(_t.shortcut, []).append(_t.id)


def group_of(tool_id: str) -> list[Tool]:
    for group in TOOL_GROUPS:
        if any(t.id == tool_id for t in group):
            return group
    return []


def default_options() -> dict:
    """Every option key any tool can read, with PS 7's own defaults."""
    return dict(
        selop="new", feather=0, antialias=True, style="Normal", fixed_w=64, fixed_h=64,
        auto_select=False, show_bounds=False,
        width=10, edge_contrast=10, frequency=57,
        tolerance=32, contiguous=True, sample_merged=False,
        crop_w=0, crop_h=0, resolution=72, shield=True,
        slice_style="Normal",
        source="Sampled", aligned=True, patch_mode="Source", transparent=False,
        brush=dict(size=13, hardness=100, spacing=25, angle=0, roundness=100, preset="Hard Round 13"),
        mode="Normal", opacity=100, flow=100, airbrush=False, auto_erase=False,
        pattern="Checkerboard",
        art_style="Tight Short", area=50, art_tolerance=0,
        eraser_mode="Brush", erase_to_history=False,
        limits="Contiguous", protect_fg=False,
        gradient="Foreground to Background", gradient_type="Linear",
        reverse=False, dither=True, transparency=True,
        fill_source="Foreground",
        strength=50, finger_painting=False,
        range="Midtones", exposure=50, sponge_mode="Desaturate",
        rubber_band=False, auto_add_delete=True, magnetic=False,
        shape_kind="Fill Pixels", radius=10, sides=5, weight=1,
        custom_shape="Heart",
        author="You", note_color="#f5e04a", note_size="Medium",
        sample_size="Point Sample",
        fit_screen=False, resize_windows=False, ignore_palettes=False,
        font=dict(family="Tahoma", style="Regular", size=24,
                  antialias="Crisp", align="left", color="#000000"),
    )
