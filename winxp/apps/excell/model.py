"""Workbook, sheets and cells; what typing into a cell turns into; how a value
is displayed; recalculation; and the on-disk format."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal, InvalidOperation

from . import formulas as fx
from .formulas import XLError

SETTINGS_PATH = os.path.join(os.path.expanduser("~/.winxp_sim"), "excell.json")

DEFAULT_COL_WIDTH = 64
DEFAULT_ROW_HEIGHT = 17

DEFAULT_FORMAT = {
    "num": "General", "dec": 2, "date": "d-mmm", "thousands": False,
    "bold": False, "italic": False, "underline": False,
    "align": "", "fill": "", "color": "", "border": False,
}


@dataclass
class Cell:
    raw: str = ""
    value: object = None
    fmt: dict = field(default_factory=dict)
    ast: object = None
    error: str = ""

    @property
    def is_formula(self):
        return self.raw.startswith("=")

    def style(self, key):
        return self.fmt.get(key, DEFAULT_FORMAT[key])


class Sheet:
    def __init__(self, name: str):
        self.name = name
        self.cells: dict[tuple[int, int], Cell] = {}
        self.col_widths: dict[int, int] = {}

    def get(self, r, c) -> Cell | None:
        return self.cells.get((r, c))

    def ensure(self, r, c) -> Cell:
        cell = self.cells.get((r, c))
        if cell is None:
            cell = self.cells[(r, c)] = Cell()
        return cell

    def prune(self, r, c):
        cell = self.cells.get((r, c))
        if cell and not cell.raw and not cell.fmt:
            del self.cells[(r, c)]

    def used_bounds(self):
        if not self.cells:
            return 0, 0
        return (max(r for r, _ in self.cells) + 1, max(c for _, c in self.cells) + 1)


# ------------------------------------------------------------ data entry

_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]
_MONTH_RE = ("(january|february|march|april|may|june|july|august|september|october|"
             "november|december|sept|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)")


def _month(token: str) -> int:
    token = token.lower()
    for i, name in enumerate(_MONTHS):
        if name.startswith(token[:3]):
            return i + 1
    return 0


def _date_or_none(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date(text: str):
    """The famous one. Returns (serial, date format) or None. Anything that
    could conceivably be a date, is one: 3-4, 1/2, MARCH1, SEPT2."""
    t = text.strip()
    year = date.today().year

    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})", t)
    if m:
        y = int(m.group(3))
        y += 2000 if y < 30 else (1900 if y < 100 else 0)
        d = _date_or_none(y, int(m.group(1)), int(m.group(2)))
        return (fx.date_to_serial(d), "m/d/yyyy") if d else None

    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,4})", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        d = _date_or_none(year, a, b) if b <= 31 else _date_or_none(b, a, 1)
        if d:
            return fx.date_to_serial(d), ("d-mmm" if b <= 31 else "mmm-yy")
        return None

    m = re.fullmatch(r"(\d{1,2})[ /-]?" + _MONTH_RE + r"[a-z]*\.?", t, re.I)
    if m:
        d = _date_or_none(year, _month(m.group(2)), int(m.group(1)))
        return (fx.date_to_serial(d), "d-mmm") if d else None

    m = re.fullmatch(_MONTH_RE + r"[a-z]*\.?[ /-]?(\d{1,4})", t, re.I)
    if m:
        n = int(m.group(2))
        if n <= 31:
            d = _date_or_none(year, _month(m.group(1)), n)
            return (fx.date_to_serial(d), "d-mmm") if d else None
        n += 2000 if n < 30 else (1900 if n < 100 else 0)
        d = _date_or_none(n, _month(m.group(1)), 1)
        return (fx.date_to_serial(d), "mmm-yy") if d else None
    return None


def parse_time(text: str):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([ap]m)?", text.strip(), re.I)
    if not m:
        return None
    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if m.group(4):
        h = h % 12 + (12 if m.group(4).lower() == "pm" else 0)
    if h > 23 or mi > 59 or s > 59:
        return None
    return (h * 3600 + mi * 60 + s) / 86400.0


def fifteen_digits(digits: str) -> float:
    """Excel keeps 15 significant digits and quietly zeroes the rest, which is
    why everyone's credit card numbers end in 0."""
    try:
        d = Decimal(digits)
    except InvalidOperation:
        return float("nan")
    if d == 0:
        return 0.0
    shift = d.adjusted() - 14
    if shift > 0:
        d = d.scaleb(-shift).to_integral_value(ROUND_DOWN).scaleb(shift)
    return float(d)


_NUMBER_RE = re.compile(r"([+-]?)(\$?)([\d,]*\.?\d+(?:[eE][+-]?\d+)?)(%?)")


def parse_entry(text: str, current_fmt: str = "General"):
    """What a typed entry becomes: (value, format changes to apply)."""
    if text == "":
        return None, {}
    if text.startswith("'"):
        return text[1:], {}
    if current_fmt == "Text":
        return text, {}
    upper = text.strip().upper()
    if upper in ("TRUE", "FALSE"):
        return upper == "TRUE", {}
    if upper in fx.ERRORS:
        return fx.ERRORS[upper], {}

    m = _NUMBER_RE.fullmatch(text.strip())
    if m and ("," not in m.group(3) or re.fullmatch(r"\d{1,3}(,\d{3})*(\.\d+)?", m.group(3))):
        sign, dollar, digits, pct = m.groups()
        value = fifteen_digits(digits.replace(",", ""))
        if sign == "-":
            value = -value
        if current_fmt != "General":
            return value / 100.0 if pct else value, {}
        if pct:
            return value / 100.0, {"num": "Percent", "dec": 2 if "." in digits else 0}
        if dollar:
            return value, {"num": "Currency", "dec": 2 if "." in digits else 0}
        if "," in digits:
            return value, {"num": "Number", "thousands": True, "dec": 2 if "." in digits else 0}
        return value, {}

    if current_fmt in ("General", "Date"):
        parsed = parse_date(text)
        if parsed:
            serial, pattern = parsed
            return serial, {"num": "Date", "date": pattern}
        t = parse_time(text)
        if t is not None:
            return t, {"num": "Time"}
    return text, {}


# ---------------------------------------------------------------- display

def to_hex(value: float, places: int | None = None) -> str:
    """Hexcel: the default number display. Fractions get hexadecimal places."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole = int(value)
    frac = value - whole
    digits = []
    limit = 4 if places is None else places
    for _ in range(limit):
        frac *= 16
        digit = int(frac)
        digits.append("0123456789ABCDEF"[digit])
        frac -= digit
    text = "".join(digits)
    if places is None:
        text = text.rstrip("0")
    return f"{sign}0x{whole:X}" + (f".{text}" if text else "")


def _general(value: float) -> str:
    if value == int(value) and abs(value) < 1e11:
        return str(int(value))
    if abs(value) >= 1e11 or abs(value) < 1e-9:
        return f"{value:.5E}".replace("E+0", "E+").replace("E-0", "E-")
    return f"{value:.10g}"


def _fixed(value: float, dec: int, thousands: bool) -> str:
    d = Decimal(f"{value:.15g}")
    return format(d, f"{',' if thousands else ''}.{dec}f")


def _date_text(serial: float, pattern: str) -> str:
    if serial < 0 or serial > 2958465:
        return "#" * 8
    dt = fx.serial_to_date(serial)
    if pattern == "m/d/yyyy":
        return f"{dt.month}/{dt.day}/{dt.year}"
    if pattern == "mmm-yy":
        return f"{dt:%b}-{dt:%y}"
    if pattern == "d-mmm-yy":
        return f"{dt.day}-{dt:%b}-{dt:%y}"
    if pattern == "mmmm d, yyyy":
        return f"{dt:%B} {dt.day}, {dt.year}"
    return f"{dt.day}-{dt:%b}"


def format_value(value, cell: Cell | None, hexcel: bool) -> str:
    if value is None:
        return ""
    if isinstance(value, XLError):
        return str(value)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return value
    style = cell.style if cell else (lambda k: DEFAULT_FORMAT[k])
    num, dec = style("num"), int(style("dec"))
    if num == "Date":
        return _date_text(value, style("date"))
    if num == "Time":
        secs = round((value % 1) * 86400)
        return f"{secs // 3600}:{secs // 60 % 60:02d}"
    if num == "Percent":
        return (to_hex(value * 100, dec) if hexcel else _fixed(value * 100, dec, False)) + "%"
    if num == "Currency":
        body = to_hex(abs(value), dec) if hexcel else _fixed(abs(value), dec, True)
        return ("-$" if value < 0 else "$") + body
    if num == "Number":
        return to_hex(value, dec) if hexcel else _fixed(value, dec, bool(style("thousands")))
    if num == "Scientific":
        return f"{value:.{dec}E}"
    return to_hex(value) if hexcel else _general(value)


# --------------------------------------------------------------- settings

class ExCellSettings:
    def __init__(self):
        self.options = {"hexcel": True, "assistant_enabled": True,
                        "gridlines": True, "formula_bar": True, "status_bar": True}
        self.last_closed: dict | None = None
        self.load()

    def load(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        self.options.update(data.get("options", {}))
        self.last_closed = data.get("last_closed")

    def save(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
                json.dump({"options": self.options, "last_closed": self.last_closed},
                          fh, indent=1)
        except OSError:
            pass


settings = ExCellSettings()


# --------------------------------------------------------------- workbook

class Workbook:
    FORMAT_TAG = "ex-cell/1"

    def __init__(self, sheet_count=3):
        self.sheets = [Sheet(f"Sheet{i + 1}") for i in range(sheet_count)]
        self.active = 0
        self.circular: list[tuple[str, int, int]] = []
        self._undo: list[tuple[str, list]] = []
        self._redo: list[tuple[str, list]] = []
        self._pending: list | None = None
        self._computing: set = set()
        self._done: set = set()
        # dependency index, keyed by (id(sheet), r, c)
        self._precedents: dict[tuple, tuple[list, list]] = {}
        self._single_deps: dict[tuple, set] = {}
        self._range_deps: dict[tuple, list] = {}
        self._volatile: set = set()
        self._changed: set = set()

    @property
    def sheet(self) -> Sheet:
        return self.sheets[self.active]

    def sheet_named(self, name: str) -> Sheet | None:
        for sheet in self.sheets:
            if sheet.name.lower() == name.lower():
                return sheet
        return None

    def unique_sheet_name(self, base="Sheet"):
        n = len(self.sheets) + 1
        while self.sheet_named(f"{base}{n}"):
            n += 1
        return f"{base}{n}"

    # -- undo -------------------------------------------------------------

    def begin(self, label: str):
        self._pending = []
        self._pending_label = label

    def _remember(self, sheet: Sheet, r, c):
        if self._pending is None:
            return
        if any(s is sheet and (rr, cc) == (r, c) for s, rr, cc, *_ in self._pending):
            return
        cell = sheet.get(r, c)
        self._pending.append((sheet, r, c, cell.raw if cell else "",
                              dict(cell.fmt) if cell else {}))

    def commit(self):
        if self._pending:
            self._undo.append((self._pending_label, self._pending))
            del self._undo[:-100]
            self._redo.clear()
        self._pending = None

    def snapshot(self, label: str):
        """Structural edits undo by restoring the whole workbook."""
        self._undo.append((label, ("snapshot", self._state())))
        del self._undo[:-100]
        self._redo.clear()

    def _state(self):
        return [(sheet.name, dict(sheet.col_widths),
                 {pos: (cell.raw, dict(cell.fmt)) for pos, cell in sheet.cells.items()})
                for sheet in self.sheets], self.active

    def _restore(self, state):
        sheets, active = state
        self.sheets = []
        for name, widths, cells in sheets:
            sheet = Sheet(name)
            sheet.col_widths = dict(widths)
            self.sheets.append(sheet)
            for (r, c), (raw, fmt) in cells.items():
                sheet.ensure(r, c).fmt = dict(fmt)
                self._store(sheet, r, c, raw)
        self.active = min(active, len(self.sheets) - 1)
        self.reindex()

    def _swap(self, entries):
        if isinstance(entries, tuple) and entries[0] == "snapshot":
            current = ("snapshot", self._state())
            self._restore(entries[1])
            return current
        inverse = []
        for sheet, r, c, raw, fmt in entries:
            cell = sheet.get(r, c)
            inverse.append((sheet, r, c, cell.raw if cell else "",
                            dict(cell.fmt) if cell else {}))
            target = sheet.ensure(r, c)
            target.fmt = dict(fmt)
            self._store(sheet, r, c, raw)
            sheet.prune(r, c)
        return inverse

    def undo(self) -> str | None:
        if not self._undo:
            return None
        label, entries = self._undo.pop()
        self._redo.append((label, self._swap(entries)))
        self.recalc_changed()
        return label

    def redo(self) -> str | None:
        if not self._redo:
            return None
        label, entries = self._redo.pop()
        self._undo.append((label, self._swap(entries)))
        self.recalc_changed()
        return label

    @property
    def undo_label(self):
        return self._undo[-1][0] if self._undo else None

    # -- editing ----------------------------------------------------------

    def _store(self, sheet: Sheet, r, c, raw: str):
        cell = sheet.ensure(r, c)
        cell.raw = raw
        cell.ast = None
        cell.error = ""
        self._unindex((id(sheet), r, c))
        self._changed.add((id(sheet), r, c))
        if raw.startswith("=") and len(raw) > 1:
            try:
                cell.ast = fx.parse(raw[1:])
            except fx.FormulaError as exc:
                cell.error = str(exc)
                cell.value = fx.NAME
                return
            self._index(sheet, r, c, cell.ast)
            return
        value, changes = parse_entry(raw, cell.style("num"))
        cell.value = value
        cell.fmt.update(changes)

    def set_entry(self, sheet: Sheet, r, c, raw: str):
        self._remember(sheet, r, c)
        self._store(sheet, r, c, raw)
        sheet.prune(r, c)

    def set_format(self, sheet: Sheet, r, c, **changes):
        self._remember(sheet, r, c)
        cell = sheet.ensure(r, c)
        for key, value in changes.items():
            if value == DEFAULT_FORMAT[key]:
                cell.fmt.pop(key, None)
            else:
                cell.fmt[key] = value
        sheet.prune(r, c)

    def clear(self, sheet: Sheet, r, c, contents=True, formats=False):
        if not sheet.get(r, c):
            return
        self._remember(sheet, r, c)
        cell = sheet.get(r, c)
        if formats:
            cell.fmt = {}
        if contents:
            self._store(sheet, r, c, "")
        sheet.prune(r, c)

    # -- recalculation ----------------------------------------------------

    def _index(self, sheet: Sheet, r, c, ast):
        key = (id(sheet), r, c)
        singles, ranges = [], []
        for ref in fx.references(ast):
            target = sheet if ref.sheet is None else self.sheet_named(ref.sheet)
            if target is None:
                continue
            if ref.is_range:
                ranges.append((id(target), ref.r1, ref.c1, ref.r2, ref.c2))
            else:
                singles.append((id(target), ref.r1, ref.c1))
        for precedent in singles:
            self._single_deps.setdefault(precedent, set()).add(key)
        if ranges:
            self._range_deps[key] = ranges
        self._precedents[key] = (singles, ranges)
        if _is_volatile(ast):
            self._volatile.add(key)

    def _unindex(self, key):
        entry = self._precedents.pop(key, None)
        if entry:
            for precedent in entry[0]:
                deps = self._single_deps.get(precedent)
                if deps:
                    deps.discard(key)
                    if not deps:
                        del self._single_deps[precedent]
        self._range_deps.pop(key, None)
        self._volatile.discard(key)

    def reindex(self):
        """After sheets are renamed, added or removed: names in formulas may
        now point somewhere else."""
        self._precedents.clear()
        self._single_deps.clear()
        self._range_deps.clear()
        self._volatile.clear()
        for sheet in self.sheets:
            for (r, c), cell in sheet.cells.items():
                if cell.raw.startswith("=") and len(cell.raw) > 1:
                    self._store(sheet, r, c, cell.raw)
        self.recalc()

    def _dependents(self, seeds) -> set:
        dirty, stack = set(), list(seeds)
        while stack:
            key = stack.pop()
            found = set(self._single_deps.get(key, ()))
            sid, r, c = key
            for dependent, rects in self._range_deps.items():
                for rs, r1, c1, r2, c2 in rects:
                    if rs == sid and r1 <= r <= r2 and c1 <= c <= c2:
                        found.add(dependent)
                        break
            for dependent in found - dirty:
                dirty.add(dependent)
                stack.append(dependent)
        return dirty

    def _order(self, dirty: set) -> list:
        """Dirty cells, precedents first, via an iterative DFS so a chain
        65,536 cells long never recurses more than one level deep."""
        def precedents(key):
            singles, ranges = self._precedents.get(key, ((), ()))
            found = [p for p in singles if p in dirty]
            for sid, r1, c1, r2, c2 in ranges:
                if (r2 - r1 + 1) * (c2 - c1 + 1) < len(dirty):
                    found.extend(k for k in ((sid, r, c) for r in range(r1, r2 + 1)
                                             for c in range(c1, c2 + 1)) if k in dirty)
                else:
                    found.extend(k for k in dirty
                                 if k[0] == sid and r1 <= k[1] <= r2 and c1 <= k[2] <= c2)
            return found

        order, state = [], {}
        for root in sorted(dirty):
            if root in state:
                continue
            state[root] = 1
            stack = [(root, iter(precedents(root)))]
            while stack:
                key, children = stack[-1]
                child = next(children, None)
                if child is None:
                    stack.pop()
                    state[key] = 2
                    order.append(key)
                elif child not in state:
                    state[child] = 1
                    stack.append((child, iter(precedents(child))))
        return order

    def _evaluate(self, dirty: set):
        sheets = {id(sheet): sheet for sheet in self.sheets}
        self._computing = set()
        self._done = {key for key in self._precedents if key not in dirty}
        self.circular = []
        for key in self._order(dirty):
            sheet = sheets.get(key[0])
            if sheet is not None:
                self._value_of(sheet, key[1], key[2])

    def recalc(self):
        """Everything, from scratch."""
        self._changed.clear()
        self._evaluate(set(self._precedents))

    def recalc_changed(self, extra=()) -> set:
        """Only what the edits since the last recalc can have touched, plus
        anything volatile. Returns the keys that were recomputed."""
        seeds = self._changed | set(extra) | self._volatile
        self._changed = set()
        dirty = self._dependents(seeds) | {k for k in seeds if k in self._precedents}
        self._evaluate(dirty)
        return dirty

    def iterate_circular(self) -> set:
        """One more lap round every loop."""
        sheets = {sheet.name: sheet for sheet in self.sheets}
        keys = {(id(sheets[name]), r, c) for name, r, c in self.circular if name in sheets}
        return self.recalc_changed(keys)

    def _value_of(self, sheet: Sheet, r, c):
        cell = sheet.get(r, c)
        if cell is None:
            return None
        if cell.ast is None:
            return cell.value
        key = (id(sheet), r, c)
        if key in self._done:
            return cell.value
        if key in self._computing:
            # A circular reference. Excel warns and gives up; Ex-Cell takes
            # last pass's value and carries on, so every recalc goes round
            # the loop once more.
            entry = (sheet.name, r, c)
            if entry not in self.circular:
                self.circular.append(entry)
            return cell.value
        self._computing.add(key)
        result = fx.Evaluator(_Context(self, sheet)).eval(cell.ast)
        if isinstance(result, fx.Range):
            result = result.rows[0][0] if result.height == result.width == 1 else fx.VALUE
        if result is None:
            result = 0.0
        if isinstance(result, float) and (result != result or result in (float("inf"), float("-inf"))):
            result = fx.NUM
        cell.value = result
        self._computing.discard(key)
        self._done.add(key)
        return result

    def value(self, sheet: Sheet, r, c):
        cell = sheet.get(r, c)
        return cell.value if cell else None

    # -- copy / paste -----------------------------------------------------

    def shift_cells(self, sheet: Sheet, axis: str, at: int, count: int):
        """Insert (count > 0) or delete (count < 0) rows or columns."""
        self.snapshot(("Insert " if count > 0 else "Delete ") +
                      ("Rows" if axis == "row" else "Columns"))
        moved = {}
        for (r, c), cell in sheet.cells.items():
            i = r if axis == "row" else c
            if count < 0 and at <= i < at - count:
                continue
            if i >= at:
                i += count
            if not 0 <= i < (fx.MAX_ROWS if axis == "row" else fx.MAX_COLS):
                continue
            moved[(i, c) if axis == "row" else (r, i)] = cell
        sheet.cells = moved
        if axis == "col":
            sheet.col_widths = {(c + count if c >= at else c): w
                                for c, w in sheet.col_widths.items()
                                if not (count < 0 and at <= c < at - count)}
        for other in self.sheets:
            for cell in other.cells.values():
                if cell.raw.startswith("=") and len(cell.raw) > 1:
                    try:
                        cell.raw = "=" + fx.adjust_for_insert(
                            cell.raw[1:], other.name, sheet.name, axis, at, count)
                    except fx.FormulaError:
                        pass
        self.reindex()

    def rename_sheet(self, sheet: Sheet, name: str):
        self.snapshot("Rename Sheet")
        old = sheet.name
        for other in self.sheets:
            for cell in other.cells.values():
                if cell.raw.startswith("=") and "!" in cell.raw:
                    cell.raw = re.sub(
                        r"(?<![A-Za-z0-9_.])(" + re.escape(old) + r"|'" +
                        re.escape(old.replace("'", "''")) + r"')!",
                        lambda _m: (f"'{name}'!" if re.search(r"[^A-Za-z0-9_.]", name)
                                    else f"{name}!"),
                        cell.raw, flags=re.I)
        sheet.name = name
        self.reindex()

    def copy_block(self, sheet: Sheet, r1, c1, r2, c2):
        block = []
        for r in range(r1, r2 + 1):
            row = []
            for c in range(c1, c2 + 1):
                cell = sheet.get(r, c)
                row.append((cell.raw, dict(cell.fmt)) if cell else ("", {}))
            block.append(row)
        return {"origin": (r1, c1), "cells": block}

    def paste_block(self, sheet: Sheet, r0, c0, clip):
        orow, ocol = clip["origin"]
        dr, dc = r0 - orow, c0 - ocol
        for i, row in enumerate(clip["cells"]):
            for j, (raw, fmt) in enumerate(row):
                r, c = r0 + i, c0 + j
                if r >= fx.MAX_ROWS or c >= fx.MAX_COLS:
                    continue
                if raw.startswith("="):
                    try:
                        raw = "=" + fx.shift_formula(raw[1:], dr, dc)
                    except fx.FormulaError:
                        pass
                self._remember(sheet, r, c)
                cell = sheet.ensure(r, c)
                cell.fmt = dict(fmt)
                self._store(sheet, r, c, raw)
                sheet.prune(r, c)

    def fill(self, sheet: Sheet, r1, c1, r2, c2, direction: str):
        """Ctrl+D / Ctrl+R: copy the first row (or column) across the rest."""
        if direction == "down":
            for c in range(c1, c2 + 1):
                clip = self.copy_block(sheet, r1, c, r1, c)
                for r in range(r1 + 1, r2 + 1):
                    self.paste_block(sheet, r, c, clip)
        else:
            for r in range(r1, r2 + 1):
                clip = self.copy_block(sheet, r, c1, r, c1)
                for c in range(c1 + 1, c2 + 1):
                    self.paste_block(sheet, r, c, clip)

    def fill_series(self, sheet: Sheet, src, dst):
        """The fill handle. Two or more numbers extend as a series; a lone
        date or "Item 1" counts up; formulas shift; anything else repeats."""
        sr1, sc1, sr2, sc2 = src
        dr1, dc1, dr2, dc2 = dst
        vertical = dr1 != sr1 or dr2 != sr2
        if vertical:
            lines = [[(r, c) for r in range(sr1, sr2 + 1)] for c in range(sc1, sc2 + 1)]
            targets = [r for r in range(dr1, dr2 + 1) if not sr1 <= r <= sr2]
            start = sr1
        else:
            lines = [[(r, c) for c in range(sc1, sc2 + 1)] for r in range(sr1, sr2 + 1)]
            targets = [c for c in range(dc1, dc2 + 1) if not sc1 <= c <= sc2]
            start = sc1
        for line in lines:
            cells = [sheet.get(r, c) for r, c in line]
            n = len(cells)
            constants = [cell.value for cell in cells
                         if cell and not cell.is_formula and isinstance(cell.value, float)
                         and not isinstance(cell.value, bool)]
            series = len(constants) == n and n >= 2
            step = (constants[-1] - constants[0]) / (n - 1) if series else 0.0
            lone = cells[0] if n == 1 else None
            for t in targets:
                offset = t - start
                k = offset % n
                source = cells[k]
                pos = (t, line[0][1]) if vertical else (line[0][0], t)
                src_pos = line[k]
                raw = source.raw if source else ""
                if series:
                    raw = f"{constants[0] + step * offset:.15g}"
                elif lone is not None and not lone.is_formula and lone.raw:
                    if lone.style("num") == "Date" and isinstance(lone.value, float):
                        raw = f"{lone.value + offset:.15g}"
                    else:
                        m = re.fullmatch(r"(.*?)(\d+)(\D*)", lone.raw)
                        if m and not isinstance(lone.value, float):
                            raw = f"{m.group(1)}{int(m.group(2)) + offset}{m.group(3)}"
                elif raw.startswith("="):
                    try:
                        raw = "=" + fx.shift_formula(raw[1:], pos[0] - src_pos[0],
                                                     pos[1] - src_pos[1])
                    except fx.FormulaError:
                        pass
                self._remember(sheet, *pos)
                cell = sheet.ensure(*pos)
                cell.fmt = dict(source.fmt) if source else {}
                self._store(sheet, pos[0], pos[1], raw)
                sheet.prune(*pos)

    def sort_rows(self, sheet: Sheet, r1, c1, r2, c2, key_col: int, descending=False):
        rows = []
        for r in range(r1, r2 + 1):
            rows.append([sheet.get(r, c) for c in range(c1, c2 + 1)])

        def sort_key(row):
            cell = row[key_col - c1]
            v = cell.value if cell else None
            if v is None:
                return (3, 0)
            if isinstance(v, float):
                return (0, v)
            if isinstance(v, bool):
                return (2, v)
            return (1, str(v).lower())

        blanks = [row for row in rows if sort_key(row)[0] == 3]
        filled = sorted((row for row in rows if sort_key(row)[0] != 3),
                        key=sort_key, reverse=descending)
        snapshot = [[(cell.raw, dict(cell.fmt)) if cell else ("", {}) for cell in row]
                    for row in filled + blanks]
        for i, row in enumerate(snapshot):
            for j, (raw, fmt) in enumerate(row):
                r, c = r1 + i, c1 + j
                self._remember(sheet, r, c)
                cell = sheet.ensure(r, c)
                cell.fmt = dict(fmt)
                self._store(sheet, r, c, raw)
                sheet.prune(r, c)

    # -- persistence ------------------------------------------------------

    def to_json(self) -> str:
        return json.dumps({
            "format": self.FORMAT_TAG,
            "active": self.active,
            "sheets": [{
                "name": sheet.name,
                "widths": {str(c): w for c, w in sheet.col_widths.items()},
                "cells": {fx.cell_name(r, c): ({"v": cell.raw, "f": cell.fmt}
                                              if cell.fmt else {"v": cell.raw})
                          for (r, c), cell in sorted(sheet.cells.items())},
            } for sheet in self.sheets],
        }, indent=1)

    @classmethod
    def from_text(cls, text: str) -> "Workbook":
        try:
            data = json.loads(text) if text.strip() else None
        except ValueError:
            data = None
        if not isinstance(data, dict) or data.get("format") != cls.FORMAT_TAG:
            return cls._import_delimited(text)
        book = cls(sheet_count=0)
        for entry in data.get("sheets", []):
            sheet = Sheet(entry.get("name", book.unique_sheet_name()))
            sheet.col_widths = {int(c): int(w) for c, w in entry.get("widths", {}).items()}
            book.sheets.append(sheet)
            for name, spec in entry.get("cells", {}).items():
                pos = fx.parse_cell(name)
                if pos is None:
                    continue
                cell = sheet.ensure(*pos)
                cell.fmt = dict(spec.get("f", {}))
                book._store(sheet, pos[0], pos[1], spec.get("v", ""))
        if not book.sheets:
            book.sheets.append(Sheet("Sheet1"))
        book.active = min(int(data.get("active", 0)), len(book.sheets) - 1)
        book.reindex()
        return book

    @classmethod
    def _import_delimited(cls, text: str) -> "Workbook":
        """A file that isn't a workbook gets the Text Import treatment, dates
        and all."""
        book = cls()
        sep = "\t" if "\t" in text else ","
        for r, line in enumerate(text.splitlines()[:fx.MAX_ROWS]):
            for c, value in enumerate(line.split(sep)[:fx.MAX_COLS]):
                if value.strip():
                    book._store(book.sheet, r, c, value.strip())
        book.recalc()
        return book


VOLATILE = {"RAND", "RANDBETWEEN", "NOW", "TODAY"}


def _is_volatile(node) -> bool:
    if node[0] == "call":
        return node[1] in VOLATILE or any(_is_volatile(a) for a in node[2])
    if node[0] == "bin":
        return _is_volatile(node[2]) or _is_volatile(node[3])
    if node[0] in ("neg", "pct"):
        return _is_volatile(node[1])
    return False


class _Context:
    def __init__(self, book: Workbook, sheet: Sheet):
        self.book = book
        self.sheet = sheet

    def resolve(self, ref: fx.Ref):
        sheet = self.sheet
        if ref.sheet is not None:
            sheet = self.book.sheet_named(ref.sheet)
            if sheet is None:
                return fx.REF
        if not ref.is_range:
            return self.book._value_of(sheet, ref.r1, ref.c1)
        height, width = ref.r2 - ref.r1 + 1, ref.c2 - ref.c1 + 1
        rows = [[None] * width for _ in range(height)]
        if height * width > len(sheet.cells):
            positions = [(r, c) for (r, c) in list(sheet.cells)
                         if ref.r1 <= r <= ref.r2 and ref.c1 <= c <= ref.c2]
        else:
            positions = [(r, c) for r in range(ref.r1, ref.r2 + 1)
                         for c in range(ref.c1, ref.c2 + 1) if (r, c) in sheet.cells]
        for r, c in positions:
            rows[r - ref.r1][c - ref.c1] = self.book._value_of(sheet, r, c)
        return fx.Range(rows)
