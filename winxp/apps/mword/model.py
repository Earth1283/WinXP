"""Document model: page geometry, the built-in style gallery, AutoCorrect's
replacement table, document properties, and the per-user settings blob.

Word measures everything in twips (1/1440 in) and renders at the screen's
logical DPI. Qt's rich text engine works in device-independent pixels, so a
single conversion constant -- 96 px to the inch, which is what Windows XP
reported at 100% -- keeps the ruler, the page, and Page Setup agreeing with
each other.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from PyQt6.QtCore import Qt

DPI = 96.0


def inches(value: float) -> float:
    return value * DPI


def to_inches(px: float) -> float:
    return px / DPI


def cm(value: float) -> float:
    return value * DPI / 2.54


def to_cm(px: float) -> float:
    return px * 2.54 / DPI


# Word's own default unit is inches on a US install; the Options dialog can
# flip it and every measurement box in the app follows.
UNITS = {
    "Inches": (inches, to_inches, '"'),
    "Centimeters": (cm, to_cm, " cm"),
    "Points": (lambda v: v * DPI / 72.0, lambda px: px * 72.0 / DPI, " pt"),
}


def fmt_measure(px: float, unit: str = "Inches") -> str:
    _, back, suffix = UNITS.get(unit, UNITS["Inches"])
    return f"{back(px):.2f}{suffix}"


def parse_measure(text: str, unit: str = "Inches", default: float = 0.0) -> float:
    fwd, _, _ = UNITS.get(unit, UNITS["Inches"])
    cleaned = text.strip().rstrip('"').replace("cm", "").replace("pt", "").strip()
    try:
        return fwd(float(cleaned))
    except ValueError:
        return default


# ------------------------------------------------------------- page setup ---

PAPER_SIZES = {
    "Letter (8.5 x 11 in)": (8.5, 11.0),
    "Legal (8.5 x 14 in)": (8.5, 14.0),
    "Executive (7.25 x 10.5 in)": (7.25, 10.5),
    "A4 (210 x 297 mm)": (8.27, 11.69),
    "A5 (148 x 210 mm)": (5.83, 8.27),
    "B5 (182 x 257 mm)": (7.17, 10.12),
    "Envelope #10 (4.12 x 9.5 in)": (4.12, 9.5),
}


@dataclass
class PageSetup:
    """Word's Page Setup, in pixels, with its US-default one-inch top and
    bottom and the 1.25" left/right that shipped in the Normal template."""
    paper: str = "Letter (8.5 x 11 in)"
    landscape: bool = False
    top: float = inches(1.0)
    bottom: float = inches(1.0)
    left: float = inches(1.25)
    right: float = inches(1.25)
    gutter: float = 0.0
    header_from_edge: float = inches(0.5)
    footer_from_edge: float = inches(0.5)

    @property
    def paper_size(self) -> tuple[float, float]:
        w_in, h_in = PAPER_SIZES.get(self.paper, PAPER_SIZES["Letter (8.5 x 11 in)"])
        if self.landscape:
            w_in, h_in = h_in, w_in
        return inches(w_in), inches(h_in)

    @property
    def page_width(self) -> float:
        return self.paper_size[0]

    @property
    def page_height(self) -> float:
        return self.paper_size[1]

    @property
    def text_width(self) -> float:
        return max(inches(0.5), self.page_width - self.left - self.right - self.gutter)

    @property
    def text_height(self) -> float:
        return max(inches(0.5), self.page_height - self.top - self.bottom)


# ----------------------------------------------------------------- styles ---

@dataclass
class Style:
    """One entry in the style gallery. `next_style` is what you land in after
    pressing Enter -- the reason a Heading 1 doesn't beget another Heading 1."""
    name: str
    family: str = "Times New Roman"
    size: float = 12.0
    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    align: int = int(Qt.AlignmentFlag.AlignLeft)
    space_before: float = 0.0        # px
    space_after: float = 0.0         # px
    line_height: float = 100.0       # percent
    outline_level: int = 9           # 0-8 = heading levels, 9 = body text
    next_style: str = ""
    kind: str = "paragraph"

    def next(self) -> str:
        return self.next_style or self.name


BUILTIN_STYLES: list[Style] = [
    Style("Normal", "Times New Roman", 12.0, next_style="Normal"),
    Style("Heading 1", "Arial", 16.0, bold=True, color="#1f3864",
          space_before=inches(0.17), space_after=inches(0.04),
          outline_level=0, next_style="Normal"),
    Style("Heading 2", "Arial", 14.0, bold=True, italic=True, color="#1f3864",
          space_before=inches(0.14), space_after=inches(0.04),
          outline_level=1, next_style="Normal"),
    Style("Heading 3", "Arial", 13.0, bold=True, color="#1f3864",
          space_before=inches(0.14), space_after=inches(0.04),
          outline_level=2, next_style="Normal"),
    Style("Heading 4", "Times New Roman", 12.0, bold=True, color="#1f3864",
          space_before=inches(0.14), space_after=inches(0.04),
          outline_level=3, next_style="Normal"),
    Style("Title", "Arial", 26.0, bold=True, align=int(Qt.AlignmentFlag.AlignHCenter),
          space_after=inches(0.14), outline_level=0, next_style="Subtitle"),
    Style("Subtitle", "Arial", 14.0, italic=True, color="#4a4a4a",
          align=int(Qt.AlignmentFlag.AlignHCenter),
          space_after=inches(0.14), next_style="Normal"),
    Style("Body Text", "Times New Roman", 12.0, space_after=inches(0.08),
          next_style="Body Text"),
    Style("Quote", "Times New Roman", 12.0, italic=True, color="#3a3a3a",
          space_before=inches(0.08), space_after=inches(0.08), next_style="Normal"),
    Style("Caption", "Arial", 9.0, bold=True, color="#4a4a4a",
          space_after=inches(0.08), next_style="Normal"),
    Style("List Paragraph", "Times New Roman", 12.0, next_style="List Paragraph"),
    Style("Header", "Times New Roman", 12.0, next_style="Header"),
    Style("Footer", "Times New Roman", 12.0, next_style="Footer"),
    Style("Plain Text", "Courier New", 10.5, next_style="Plain Text"),
]

STYLES_BY_NAME = {s.name: s for s in BUILTIN_STYLES}

#: Property id Word-style paragraph tagging is stashed under, so the Style box
#: can read back which style a paragraph was formatted with. Qt reserves
#: everything below UserProperty for its own use.
STYLE_PROPERTY = 0x1000 + 41


# ------------------------------------------------------------ autocorrect ---

#: A trimmed cut of the real Word 2003 AutoCorrect table -- the same entries,
#: in the same "replace this, with that" shape the Tools dialog edits.
DEFAULT_AUTOCORRECT = {
    "teh": "the", "adn": "and", "recieve": "receive", "seperate": "separate",
    "definately": "definitely", "occured": "occurred", "wierd": "weird",
    "thier": "their", "alot": "a lot", "wich": "which", "abbout": "about",
    "acheive": "achieve", "accross": "across", "aparent": "apparent",
    "basicly": "basically", "beleive": "believe", "becuase": "because",
    "calender": "calendar", "cant": "can't", "commited": "committed",
    "dont": "don't", "embarass": "embarrass", "enviroment": "environment",
    "existance": "existence", "familar": "familiar", "goverment": "government",
    "grammer": "grammar", "hte": "the", "independant": "independent",
    "isnt": "isn't", "knowlege": "knowledge", "liason": "liaison",
    "maintainance": "maintenance", "neccessary": "necessary", "noticable": "noticeable",
    "occassion": "occasion", "persistant": "persistent", "posession": "possession",
    "priviledge": "privilege", "publically": "publicly", "reccomend": "recommend",
    "refered": "referred", "relevent": "relevant", "rythm": "rhythm",
    "sucessful": "successful", "supercede": "supersede", "tommorrow": "tomorrow",
    "truely": "truly", "untill": "until", "usefull": "useful", "wont": "won't",
    "youre": "you're", "yuo": "you", "ot eh": "of the",
    "(c)": "©", "(r)": "®", "(tm)": "™", "...": "…",
    ":)": "☺", ":(": "☹", "<-": "←", "->": "→",
    "<--": "←", "-->": "→", "<=": "≤", ">=": "≥",
    "1/2": "½", "1/4": "¼", "3/4": "¾",
}


@dataclass
class AutoCorrectOptions:
    """Every checkbox on the AutoCorrect and AutoFormat As You Type tabs that
    this build actually honours."""
    replace_text: bool = True
    two_initial_caps: bool = True
    capitalize_sentences: bool = True
    capitalize_days: bool = True
    correct_caps_lock: bool = True
    smart_quotes: bool = True
    ordinals_superscript: bool = True
    fractions: bool = True
    symbol_dashes: bool = True
    auto_bullets: bool = True
    auto_numbers: bool = True
    internet_hyperlinks: bool = True


# --------------------------------------------------------- doc properties ---

@dataclass
class DocumentProperties:
    """File > Properties. Word stamps these into the file and shows them in
    Explorer's Summary tab; here they ride along in the saved HTML head."""
    title: str = ""
    subject: str = ""
    author: str = ""
    manager: str = ""
    company: str = "MacroHard Corporation"
    category: str = ""
    keywords: str = ""
    comments: str = ""
    created: str = ""
    modified: str = ""
    last_printed: str = ""
    revision: int = 1
    editing_minutes: int = 0
    template: str = "Normal.dot"


# --------------------------------------------------------------- settings ---

SETTINGS_PATH = os.path.join(os.path.expanduser("~/.winxp_sim"), "mword.json")

DEFAULT_OPTIONS = {
    "units": "Inches",
    "show_ruler": True,
    "show_status_bar": True,
    "show_task_pane": True,
    "show_formatting_marks": False,
    "check_spelling": True,
    "check_grammar": True,
    "autosave_minutes": 10,
    "smart_cut_paste": True,
    "typing_replaces_selection": True,
    "drag_and_drop": True,
    "recently_used_count": 4,
    "background_repagination": True,
    "assistant_enabled": True,
    "view_mode": "print",
    "zoom": 100,
    "standard_toolbar": True,
    "formatting_toolbar": True,
    "drawing_toolbar": False,
}


class WordSettings:
    """Options, the custom dictionary and the MRU list, persisted next to the
    rest of the simulated machine's state."""

    def __init__(self):
        self.options = dict(DEFAULT_OPTIONS)
        self.custom_dictionary: set[str] = set()
        self.autocorrect = dict(DEFAULT_AUTOCORRECT)
        self.autocorrect_options = AutoCorrectOptions()
        self.recent_files: list[dict] = []
        self.load()

    def load(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        self.options.update(data.get("options", {}))
        self.custom_dictionary = set(data.get("custom_dictionary", []))
        self.autocorrect.update(data.get("autocorrect", {}))
        for key in data.get("autocorrect_removed", []):
            self.autocorrect.pop(key, None)
        opts = data.get("autocorrect_options", {})
        for key, value in opts.items():
            if hasattr(self.autocorrect_options, key):
                setattr(self.autocorrect_options, key, bool(value))
        self.recent_files = data.get("recent_files", [])[:9]

    def save(self):
        removed = [k for k in DEFAULT_AUTOCORRECT if k not in self.autocorrect]
        payload = {
            "options": self.options,
            "custom_dictionary": sorted(self.custom_dictionary),
            "autocorrect": {k: v for k, v in self.autocorrect.items()
                            if DEFAULT_AUTOCORRECT.get(k) != v},
            "autocorrect_removed": removed,
            "autocorrect_options": asdict(self.autocorrect_options),
            "recent_files": self.recent_files[:9],
        }
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=1)
        except OSError:
            pass

    # -- MRU ------------------------------------------------------------

    def push_recent(self, node_id: str, name: str):
        self.recent_files = [r for r in self.recent_files if r.get("id") != node_id]
        self.recent_files.insert(0, {"id": node_id, "name": name})
        del self.recent_files[9:]
        self.save()

    def recent(self) -> list[dict]:
        return self.recent_files[: int(self.options.get("recently_used_count", 4))]

    # -- dictionary -----------------------------------------------------

    def add_word(self, word: str):
        self.custom_dictionary.add(word.lower())
        self.save()


settings = WordSettings()
