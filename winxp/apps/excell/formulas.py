"""Formula language: tokenizer, parser, evaluator and the function library.

Values are float, str, bool, XLError, or None for a blank cell. Ranges
evaluate to a Range object holding a 2-D list of values.
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from datetime import date, datetime

MAX_ROWS = 65536
MAX_COLS = 256


class XLError(str):
    pass


DIV0 = XLError("#DIV/0!")
VALUE = XLError("#VALUE!")
REF = XLError("#REF!")
NAME = XLError("#NAME?")
NA = XLError("#N/A")
NUM = XLError("#NUM!")
NULL = XLError("#NULL!")
ERRORS = {e: e for e in (DIV0, VALUE, REF, NAME, NA, NUM, NULL)}


class FormulaError(Exception):
    """Raised for formulas Ex-Cell refuses to accept at all."""


# --------------------------------------------------------------- references

def col_name(c: int) -> str:
    name = ""
    c += 1
    while c:
        c, rem = divmod(c - 1, 26)
        name = chr(65 + rem) + name
    return name


def col_index(name: str) -> int:
    n = 0
    for ch in name.upper():
        n = n * 26 + ord(ch) - 64
    return n - 1


def cell_name(r: int, c: int) -> str:
    return f"{col_name(c)}{r + 1}"


_CELL_RE = re.compile(r"^\$?([A-Za-z]{1,2})\$?(\d{1,5})$")


def parse_cell(text: str) -> tuple[int, int] | None:
    m = _CELL_RE.match(text.strip())
    if not m:
        return None
    r, c = int(m.group(2)) - 1, col_index(m.group(1))
    if 0 <= r < MAX_ROWS and 0 <= c < MAX_COLS:
        return r, c
    return None


# ----------------------------------------------------------------- tokens

_TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<string>"(?:[^"]|"")*")
  | (?P<error>\#(?:DIV/0!|VALUE!|REF!|NAME\?|N/A|NUM!|NULL!))
  | (?P<ref>(?:(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)?
            \$?[A-Za-z]{1,2}\$?\d{1,5}(?::\$?[A-Za-z]{1,2}\$?\d{1,5})?)(?![A-Za-z0-9_(])
  | (?P<number>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)
  | (?P<func>[A-Za-z_][A-Za-z0-9_.]*(?=\s*\())
  | (?P<name>[A-Za-z_][A-Za-z0-9_.]*)
  | (?P<op><>|<=|>=|[-+*/^&=<>%(),:])
""", re.VERBOSE)


@dataclass
class Token:
    kind: str
    text: str
    pos: int


def tokenize(src: str) -> list[Token]:
    tokens, pos = [], 0
    while pos < len(src):
        m = _TOKEN_RE.match(src, pos)
        if not m:
            raise FormulaError(f"Unexpected character '{src[pos]}'")
        kind = m.lastgroup
        if kind != "ws":
            tokens.append(Token(kind, m.group(), pos))
        pos = m.end()
    return tokens


# -------------------------------------------------------------------- AST

@dataclass
class Ref:
    sheet: str | None
    r1: int
    c1: int
    r2: int
    c2: int

    @property
    def is_range(self):
        return (self.r1, self.c1) != (self.r2, self.c2)


def _split_ref(text: str):
    sheet = None
    if "!" in text:
        sheet, text = text.rsplit("!", 1)
        if sheet.startswith("'"):
            sheet = sheet[1:-1].replace("''", "'")
    parts = text.split(":")
    a = parse_cell(parts[0])
    b = parse_cell(parts[-1])
    if a is None or b is None:
        return None
    (r1, c1), (r2, c2) = a, b
    return Ref(sheet, min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2))


class Parser:
    def __init__(self, src: str):
        self.tokens = tokenize(src)
        self.i = 0

    def peek(self, *texts):
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            if not texts or (tok.kind == "op" and tok.text in texts):
                return tok
        return None

    def take(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, text):
        if not self.peek(text):
            raise FormulaError(f"Expected '{text}'")
        return self.take()

    def parse(self):
        if not self.tokens:
            raise FormulaError("Empty formula")
        node = self.comparison()
        if self.i != len(self.tokens):
            raise FormulaError(f"Unexpected '{self.tokens[self.i].text}'")
        return node

    def _binary(self, ops, sub):
        node = sub()
        while self.peek(*ops):
            op = self.take().text
            node = ("bin", op, node, sub())
        return node

    def comparison(self):
        return self._binary(("=", "<>", "<", ">", "<=", ">="), self.concat)

    def concat(self):
        return self._binary(("&",), self.additive)

    def additive(self):
        return self._binary(("+", "-"), self.term)

    def term(self):
        return self._binary(("*", "/"), self.power)

    def power(self):
        return self._binary(("^",), self.unary)

    def unary(self):
        # Excel binds unary minus tighter than ^, so -2^2 is 4. Faithfully.
        if self.peek("-", "+"):
            op = self.take().text
            return ("neg", self.unary()) if op == "-" else self.unary()
        return self.postfix()

    def postfix(self):
        node = self.primary()
        while self.peek("%"):
            self.take()
            node = ("pct", node)
        return node

    def primary(self):
        if self.i >= len(self.tokens):
            raise FormulaError("Formula ends too soon")
        tok = self.take()
        if tok.kind == "number":
            return ("num", float(tok.text))
        if tok.kind == "string":
            return ("str", tok.text[1:-1].replace('""', '"'))
        if tok.kind == "error":
            return ("err", ERRORS[tok.text])
        if tok.kind == "ref":
            ref = _split_ref(tok.text)
            return ("ref", ref) if ref else ("err", REF)
        if tok.kind == "func":
            name = tok.text.upper()
            self.expect("(")
            args = []
            if not self.peek(")"):
                while True:
                    if self.peek(",", ")"):
                        args.append(("blank",))
                    else:
                        args.append(self.comparison())
                    if self.peek(","):
                        self.take()
                        continue
                    break
            self.expect(")")
            return ("call", name, args)
        if tok.kind == "name":
            upper = tok.text.upper()
            if upper in ("TRUE", "FALSE"):
                return ("bool", upper == "TRUE")
            return ("err", NAME)
        if tok.kind == "op" and tok.text == "(":
            node = self.comparison()
            self.expect(")")
            return node
        raise FormulaError(f"Unexpected '{tok.text}'")


def parse(src: str):
    return Parser(src).parse()


def references(node, out=None) -> list[Ref]:
    out = [] if out is None else out
    if node[0] == "ref":
        out.append(node[1])
    elif node[0] in ("bin",):
        references(node[2], out)
        references(node[3], out)
    elif node[0] in ("neg", "pct"):
        references(node[1], out)
    elif node[0] == "call":
        for arg in node[2]:
            references(arg, out)
    return out


# ------------------------------------------------------- relative shifting

def shift_formula(src: str, dr: int, dc: int) -> str:
    """Move every relative reference by (dr, dc), as copy/paste and fill do.
    References pushed off the sheet become #REF!."""
    out, pos = [], 0
    for tok in tokenize(src):
        out.append(src[pos:tok.pos])
        pos = tok.pos + len(tok.text)
        if tok.kind != "ref":
            out.append(tok.text)
            continue
        prefix, body = "", tok.text
        if "!" in body:
            prefix, body = body.rsplit("!", 1)
            prefix += "!"
        parts = []
        for part in body.split(":"):
            m = re.match(r"(\$?)([A-Za-z]{1,2})(\$?)(\d+)", part)
            col_abs, col, row_abs, row = m.groups()
            c = col_index(col) + (0 if col_abs else dc)
            r = int(row) - 1 + (0 if row_abs else dr)
            if not (0 <= r < MAX_ROWS and 0 <= c < MAX_COLS):
                parts = None
                break
            parts.append(f"{col_abs}{col_name(c)}{row_abs}{r + 1}")
        out.append(prefix + ":".join(parts) if parts else "#REF!")
    out.append(src[pos:])
    return "".join(out)


def adjust_for_insert(src: str, own_sheet: str, target_sheet: str, axis: str,
                      at: int, count: int) -> str:
    """Rewrite references after rows/columns are inserted (count > 0) or
    deleted (count < 0) at index `at` on target_sheet. Unlike copy/paste,
    absolute references move too. Anything pointing into deleted cells is
    #REF!; ranges that lose an edge shrink."""
    out, pos = [], 0
    for tok in tokenize(src):
        out.append(src[pos:tok.pos])
        pos = tok.pos + len(tok.text)
        if tok.kind != "ref":
            out.append(tok.text)
            continue
        prefix, body = "", tok.text
        sheet = own_sheet
        if "!" in body:
            prefix, body = body.rsplit("!", 1)
            sheet = prefix[1:-1].replace("''", "'") if prefix.startswith("'") else prefix
            prefix += "!"
        if sheet.lower() != target_sheet.lower():
            out.append(tok.text)
            continue
        parts = [re.match(r"(\$?)([A-Za-z]{1,2})(\$?)(\d+)", p).groups() for p in body.split(":")]
        idx = [(int(row) - 1 if axis == "row" else col_index(col)) for _, col, _, row in parts]
        lo, hi = min(idx), max(idx)
        if count > 0:
            lo2 = lo + count if lo >= at else lo
            hi2 = hi + count if hi >= at else hi
        else:
            gone_lo, gone_hi = at, at - count - 1
            if gone_lo <= lo and hi <= gone_hi:
                out.append("#REF!")
                continue

            def moved(i, edge):
                if i < gone_lo:
                    return i
                if i > gone_hi:
                    return i + count
                return gone_lo if edge == "lo" else gone_lo - 1
            lo2, hi2 = moved(lo, "lo"), moved(hi, "hi")
        limit = MAX_ROWS if axis == "row" else MAX_COLS
        if hi2 >= limit:
            out.append("#REF!")
            continue
        new_idx = [lo2, hi2] if len(parts) == 2 else [lo2]
        if len(parts) == 2 and idx[0] > idx[1]:
            new_idx.reverse()
        rebuilt = []
        for (ca, col, ra, row), i in zip(parts, new_idx):
            if axis == "row":
                rebuilt.append(f"{ca}{col}{ra}{i + 1}")
            else:
                rebuilt.append(f"{ca}{col_name(i)}{ra}{row}")
        out.append(prefix + ":".join(rebuilt))
    out.append(src[pos:])
    return "".join(out)


def cycle_reference_style(ref_text: str) -> str:
    """F4: A1 -> $A$1 -> A$1 -> $A1 -> A1."""
    m = re.fullmatch(r"(\$?)([A-Za-z]{1,2})(\$?)(\d+)", ref_text)
    if not m:
        return ref_text
    col_abs, col, row_abs, row = m.groups()
    state = {("", ""): ("$", "$"), ("$", "$"): ("", "$"),
             ("", "$"): ("$", ""), ("$", ""): ("", "")}[(col_abs, row_abs)]
    return f"{state[0]}{col}{state[1]}{row}"


# ------------------------------------------------------------- evaluation

class Range:
    def __init__(self, rows: list[list]):
        self.rows = rows

    def values(self):
        for row in self.rows:
            yield from row

    @property
    def height(self):
        return len(self.rows)

    @property
    def width(self):
        return len(self.rows[0]) if self.rows else 0


def to_number(v):
    if isinstance(v, XLError):
        return v
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        try:
            return float(v.replace(",", "").strip()) if v.strip() else VALUE
        except ValueError:
            return VALUE
    return VALUE


def to_text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return f"{v:.15g}"
    return str(v)


def to_bool(v):
    if isinstance(v, XLError):
        return v
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        return v != 0
    upper = str(v).upper()
    if upper in ("TRUE", "FALSE"):
        return upper == "TRUE"
    return VALUE


def _scalar(v):
    """A range used where one value is wanted collapses to its first cell."""
    if isinstance(v, Range):
        return v.rows[0][0] if v.height == 1 and v.width == 1 else VALUE
    return v


def _compare(a, b):
    def rank(v):
        if v is None:
            return 0, 0.0
        if isinstance(v, float):
            return 1, v
        if isinstance(v, str):
            return 2, v.lower()
        return 3, v
    if a is None and isinstance(b, str):
        a = ""
    if b is None and isinstance(a, str):
        b = ""
    if a is None and isinstance(b, float):
        a = 0.0
    if b is None and isinstance(a, float):
        b = 0.0
    ra, rb = rank(a), rank(b)
    return (ra > rb) - (ra < rb)


class Evaluator:
    """ctx must provide resolve(ref) -> value (scalar ref) or Range."""

    def __init__(self, ctx):
        self.ctx = ctx

    def eval(self, node):
        kind = node[0]
        if kind == "num":
            return node[1]
        if kind == "str":
            return node[1]
        if kind == "bool":
            return node[1]
        if kind == "err":
            return node[1]
        if kind == "blank":
            return None
        if kind == "ref":
            return self.ctx.resolve(node[1])
        if kind == "neg":
            v = to_number(_scalar(self.eval(node[1])))
            return v if isinstance(v, XLError) else -v
        if kind == "pct":
            v = to_number(_scalar(self.eval(node[1])))
            return v if isinstance(v, XLError) else v / 100.0
        if kind == "bin":
            return self._binary(node[1], _scalar(self.eval(node[2])),
                                _scalar(self.eval(node[3])))
        if kind == "call":
            fn = FUNCTIONS.get(node[1])
            if fn is None:
                return NAME
            if node[1] in LAZY:
                return fn(self, node[2])
            return fn(*[self.eval(arg) for arg in node[2]])
        return VALUE

    def _binary(self, op, a, b):
        if op == "&":
            for v in (a, b):
                if isinstance(v, XLError):
                    return v
            return to_text(a) + to_text(b)
        if op in ("=", "<>", "<", ">", "<=", ">="):
            for v in (a, b):
                if isinstance(v, XLError):
                    return v
            c = _compare(a, b)
            return {"=": c == 0, "<>": c != 0, "<": c < 0, ">": c > 0,
                    "<=": c <= 0, ">=": c >= 0}[op]
        x, y = to_number(a), to_number(b)
        for v in (x, y):
            if isinstance(v, XLError):
                return v
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            return DIV0 if y == 0 else x / y
        if op == "^":
            try:
                result = x ** y
            except (OverflowError, ZeroDivisionError):
                return NUM
            return NUM if isinstance(result, complex) else float(result)
        return VALUE


# --------------------------------------------------------------- functions

def _flatten(args, numbers_only_from_ranges=True):
    """Yield values the way SUM sees them: text inside ranges is skipped,
    text typed directly as an argument is coerced (and can fail)."""
    for arg in args:
        if isinstance(arg, Range):
            for v in arg.values():
                if isinstance(v, XLError):
                    yield v
                elif isinstance(v, float):
                    yield v
                elif not numbers_only_from_ranges and v is not None:
                    yield v
        elif arg is None:
            continue
        else:
            yield to_number(arg) if numbers_only_from_ranges else arg


def _numbers(args):
    out = []
    for v in _flatten(args):
        if isinstance(v, XLError):
            return v
        out.append(v)
    return out


def _agg(fn, empty=0.0):
    def wrapper(*args):
        nums = _numbers(args)
        if isinstance(nums, XLError):
            return nums
        return fn(nums) if nums else empty
    return wrapper


def _average(nums):
    return sum(nums) / len(nums)


def fn_average(*args):
    nums = _numbers(args)
    if isinstance(nums, XLError):
        return nums
    return _average(nums) if nums else DIV0


def fn_count(*args):
    n = 0
    for arg in args:
        if isinstance(arg, Range):
            n += sum(1 for v in arg.values() if isinstance(v, float))
        elif isinstance(arg, float) or not isinstance(to_number(arg), XLError):
            n += 1
    return float(n)


def fn_counta(*args):
    n = 0
    for arg in args:
        if isinstance(arg, Range):
            n += sum(1 for v in arg.values() if v is not None and v != "")
        elif arg is not None:
            n += 1
    return float(n)


def fn_countblank(rng):
    if not isinstance(rng, Range):
        return VALUE
    return float(sum(1 for v in rng.values() if v is None or v == ""))


def _criterion(crit):
    """COUNTIF-style criteria: 5, ">5", "<>apple", "a*"."""
    if isinstance(crit, float):
        return lambda v: isinstance(v, float) and v == crit
    text = to_text(crit)
    m = re.match(r"^(<=|>=|<>|<|>|=)?(.*)$", text, re.S)
    op, operand = m.group(1) or "=", m.group(2)
    try:
        target = float(operand)
    except ValueError:
        target = operand.lower()
    if isinstance(target, str) and op in ("=", "<>") and ("*" in target or "?" in target):
        pattern = re.compile("^" + re.escape(target).replace(r"\*", ".*").replace(r"\?", ".") + "$")
        match = lambda v: isinstance(v, str) and bool(pattern.match(v.lower()))
        return match if op == "=" else (lambda v: not match(v))

    def test(v):
        if isinstance(target, float):
            if not isinstance(v, float):
                return op == "<>"
            a = v
        else:
            if isinstance(v, float) or v is None:
                return op == "<>" if target else (v is None and op == "=")
            a = str(v).lower()
        return {"=": a == target, "<>": a != target, "<": a < target, ">": a > target,
                "<=": a <= target, ">=": a >= target}[op]
    return test


def fn_countif(rng, crit):
    if not isinstance(rng, Range):
        return VALUE
    test = _criterion(crit)
    return float(sum(1 for v in rng.values() if test(v)))


def fn_sumif(rng, crit, sum_rng=None):
    if not isinstance(rng, Range):
        return VALUE
    target = sum_rng if isinstance(sum_rng, Range) else rng
    test = _criterion(crit)
    total = 0.0
    flat_target = list(target.values())
    for i, v in enumerate(rng.values()):
        if test(v) and i < len(flat_target) and isinstance(flat_target[i], float):
            total += flat_target[i]
    return total


def fn_averageif(rng, crit, avg_rng=None):
    if not isinstance(rng, Range):
        return VALUE
    target = list((avg_rng if isinstance(avg_rng, Range) else rng).values())
    test = _criterion(crit)
    picked = [target[i] for i, v in enumerate(rng.values())
              if test(v) and i < len(target) and isinstance(target[i], float)]
    return sum(picked) / len(picked) if picked else DIV0


def lazy_if(ev, args):
    if not 1 <= len(args) <= 3:
        return VALUE
    cond = to_bool(_scalar(ev.eval(args[0])))
    if isinstance(cond, XLError):
        return cond
    if cond:
        return ev.eval(args[1]) if len(args) > 1 else True
    return ev.eval(args[2]) if len(args) > 2 else False


def fn_and(*args):
    vals = [to_bool(v) for v in _flatten(args, numbers_only_from_ranges=False)]
    for v in vals:
        if isinstance(v, XLError):
            return v
    return all(vals) if vals else VALUE


def fn_or(*args):
    vals = [to_bool(v) for v in _flatten(args, numbers_only_from_ranges=False)]
    for v in vals:
        if isinstance(v, XLError):
            return v
    return any(vals) if vals else VALUE


def fn_not(v):
    b = to_bool(_scalar(v))
    return b if isinstance(b, XLError) else not b


def _num_fn(fn):
    def wrapper(*args):
        nums = [to_number(_scalar(a)) for a in args]
        for n in nums:
            if isinstance(n, XLError):
                return n
        try:
            result = fn(*nums)
        except (ValueError, OverflowError):
            return NUM
        except ZeroDivisionError:
            return DIV0
        return result
    return wrapper


def _excel_round(x, digits=0.0):
    factor = 10 ** int(digits)
    return math.floor(abs(x) * factor + 0.5) / factor * (1 if x >= 0 else -1)


def _mod(a, b):
    if b == 0:
        raise ZeroDivisionError
    return a - b * math.floor(a / b)


def _text_fn(fn):
    def wrapper(*args):
        vals = [_scalar(a) for a in args]
        for v in vals:
            if isinstance(v, XLError):
                return v
        return fn(*vals)
    return wrapper


def fn_left(text, n=1.0):
    n = to_number(n)
    return n if isinstance(n, XLError) else to_text(text)[: int(n)]


def fn_right(text, n=1.0):
    n = to_number(n)
    if isinstance(n, XLError):
        return n
    s = to_text(text)
    return s[len(s) - int(n):] if int(n) else ""


def fn_mid(text, start, n):
    start, n = to_number(start), to_number(n)
    if isinstance(start, XLError) or isinstance(n, XLError):
        return VALUE
    if start < 1:
        return VALUE
    return to_text(text)[int(start) - 1: int(start) - 1 + int(n)]


def fn_find(needle, hay, start=1.0):
    idx = to_text(hay).find(to_text(needle), int(to_number(start)) - 1)
    return VALUE if idx < 0 else float(idx + 1)


def fn_search(needle, hay, start=1.0):
    idx = to_text(hay).lower().find(to_text(needle).lower(), int(to_number(start)) - 1)
    return VALUE if idx < 0 else float(idx + 1)


def fn_substitute(text, old, new):
    return to_text(text).replace(to_text(old), to_text(new))


def fn_rept(text, n):
    n = to_number(n)
    return n if isinstance(n, XLError) else to_text(text) * max(0, int(n))


def fn_value(text):
    return to_number(_scalar(text))


def fn_vlookup(key, table, col, approx=True):
    if not isinstance(table, Range):
        return NA
    col = to_number(col)
    if isinstance(col, XLError) or not 1 <= col <= table.width:
        return REF
    key = _scalar(key)
    approx = to_bool(approx)
    best = None
    for row in table.rows:
        c = _compare(row[0], key)
        if c == 0:
            return row[int(col) - 1]
        if approx and c < 0:
            best = row
        elif approx and c > 0:
            break
    return best[int(col) - 1] if (approx and best) else NA


def fn_hlookup(key, table, row_index, approx=True):
    if not isinstance(table, Range):
        return NA
    transposed = Range([list(col) for col in zip(*table.rows)])
    return fn_vlookup(key, transposed, row_index, approx)


def fn_index(table, row, col=1.0):
    if not isinstance(table, Range):
        return _scalar(table)
    r, c = to_number(row), to_number(col)
    if isinstance(r, XLError) or isinstance(c, XLError):
        return VALUE
    if table.height == 1 and c == 1:
        r, c = 1, r
    if not (1 <= r <= table.height and 1 <= c <= table.width):
        return REF
    return table.rows[int(r) - 1][int(c) - 1]


def fn_match(key, rng, kind=1.0):
    if not isinstance(rng, Range):
        return NA
    key, kind = _scalar(key), to_number(kind)
    values = list(rng.values())
    if kind == 0:
        for i, v in enumerate(values):
            if _compare(v, key) == 0:
                return float(i + 1)
        return NA
    best = None
    for i, v in enumerate(values):
        c = _compare(v, key)
        if (kind > 0 and c <= 0) or (kind < 0 and c >= 0):
            best = i
        else:
            break
    return NA if best is None else float(best + 1)


EPOCH = date(1899, 12, 30)


def date_to_serial(d: date | datetime) -> float:
    if isinstance(d, datetime):
        delta = d - datetime(1899, 12, 30)
        return delta.days + delta.seconds / 86400.0
    return float((d - EPOCH).days)


def serial_to_date(serial: float) -> datetime:
    from datetime import timedelta
    return datetime(1899, 12, 30) + timedelta(days=serial)


def fn_date(y, m, d):
    try:
        y, m, d = int(to_number(y)), int(to_number(m)), int(to_number(d))
        if y < 1900:
            y += 1900
        y += (m - 1) // 12
        m = (m - 1) % 12 + 1
        from datetime import timedelta
        return date_to_serial(date(y, m, 1) + timedelta(days=d - 1))
    except (TypeError, ValueError, OverflowError):
        return NUM


def _date_part(attr):
    def fn(v):
        n = to_number(_scalar(v))
        if isinstance(n, XLError):
            return n
        return float(getattr(serial_to_date(n), attr))
    return fn


def fn_iserror(v):
    return isinstance(_scalar(v), XLError)


def fn_isna(v):
    return _scalar(v) == NA and isinstance(_scalar(v), XLError)


def fn_isblank(v):
    return _scalar(v) is None


def fn_isnumber(v):
    return isinstance(_scalar(v), float)


def fn_istext(v):
    v = _scalar(v)
    return isinstance(v, str) and not isinstance(v, XLError)


def fn_choose(index, *options):
    i = to_number(_scalar(index))
    if isinstance(i, XLError):
        return i
    if not 1 <= int(i) <= len(options):
        return VALUE
    return options[int(i) - 1]


def fn_product(*args):
    nums = _numbers(args)
    if isinstance(nums, XLError):
        return nums
    return math.prod(nums) if nums else 0.0


def fn_large(rng, k):
    nums = sorted(_numbers([rng]), reverse=True) if not isinstance(_numbers([rng]), XLError) else []
    k = int(to_number(k))
    return nums[k - 1] if 1 <= k <= len(nums) else NUM


def fn_small(rng, k):
    nums = sorted(_numbers([rng])) if not isinstance(_numbers([rng]), XLError) else []
    k = int(to_number(k))
    return nums[k - 1] if 1 <= k <= len(nums) else NUM


def fn_median(*args):
    nums = _numbers(args)
    if isinstance(nums, XLError):
        return nums
    if not nums:
        return NUM
    nums.sort()
    mid = len(nums) // 2
    return nums[mid] if len(nums) % 2 else (nums[mid - 1] + nums[mid]) / 2


def fn_stdev(*args):
    nums = _numbers(args)
    if isinstance(nums, XLError):
        return nums
    if len(nums) < 2:
        return DIV0
    mean = _average(nums)
    return math.sqrt(sum((n - mean) ** 2 for n in nums) / (len(nums) - 1))


def fn_iferror(*_args):
    # IFERROR arrived in Excel 2007. This is Ex-Cell 2003.
    return NAME


FUNCTIONS = {
    "SUM": _agg(sum),
    "AVERAGE": fn_average,
    "MIN": _agg(min),
    "MAX": _agg(max),
    "COUNT": fn_count,
    "COUNTA": fn_counta,
    "COUNTBLANK": fn_countblank,
    "COUNTIF": fn_countif,
    "SUMIF": fn_sumif,
    "AVERAGEIF": fn_averageif,
    "PRODUCT": fn_product,
    "MEDIAN": fn_median,
    "STDEV": fn_stdev,
    "LARGE": fn_large,
    "SMALL": fn_small,
    "IF": lazy_if,
    "AND": fn_and,
    "OR": fn_or,
    "NOT": fn_not,
    "TRUE": lambda: True,
    "FALSE": lambda: False,
    "ROUND": _num_fn(_excel_round),
    "ROUNDUP": _num_fn(lambda x, d=0.0: math.ceil(abs(x) * 10 ** int(d)) / 10 ** int(d) * (1 if x >= 0 else -1)),
    "ROUNDDOWN": _num_fn(lambda x, d=0.0: math.floor(abs(x) * 10 ** int(d)) / 10 ** int(d) * (1 if x >= 0 else -1)),
    "INT": _num_fn(lambda x: float(math.floor(x))),
    "ABS": _num_fn(abs),
    "MOD": _num_fn(_mod),
    "POWER": _num_fn(lambda x, y: float(x ** y)),
    "SQRT": _num_fn(math.sqrt),
    "EXP": _num_fn(math.exp),
    "LN": _num_fn(math.log),
    "LOG10": _num_fn(math.log10),
    "LOG": _num_fn(lambda x, b=10.0: math.log(x, b)),
    "PI": lambda: math.pi,
    "SIGN": _num_fn(lambda x: float((x > 0) - (x < 0))),
    "RAND": lambda: random.random(),
    "RANDBETWEEN": _num_fn(lambda a, b: float(random.randint(math.ceil(a), math.floor(b)))),
    "CONCATENATE": _text_fn(lambda *a: "".join(to_text(v) for v in a)),
    "LEFT": _text_fn(fn_left),
    "RIGHT": _text_fn(fn_right),
    "MID": _text_fn(fn_mid),
    "LEN": _text_fn(lambda t: float(len(to_text(t)))),
    "UPPER": _text_fn(lambda t: to_text(t).upper()),
    "LOWER": _text_fn(lambda t: to_text(t).lower()),
    "PROPER": _text_fn(lambda t: to_text(t).title()),
    "TRIM": _text_fn(lambda t: " ".join(to_text(t).split())),
    "FIND": _text_fn(fn_find),
    "SEARCH": _text_fn(fn_search),
    "SUBSTITUTE": _text_fn(fn_substitute),
    "REPT": _text_fn(fn_rept),
    "EXACT": _text_fn(lambda a, b: to_text(a) == to_text(b)),
    "VALUE": fn_value,
    "TEXT": _text_fn(lambda v, _fmt="": to_text(v)),
    "VLOOKUP": fn_vlookup,
    "HLOOKUP": fn_hlookup,
    "INDEX": fn_index,
    "MATCH": fn_match,
    "CHOOSE": fn_choose,
    "ISERROR": fn_iserror,
    "ISNA": fn_isna,
    "ISBLANK": fn_isblank,
    "ISNUMBER": fn_isnumber,
    "ISTEXT": fn_istext,
    "NA": lambda: NA,
    "IFERROR": fn_iferror,
    "NOW": lambda: date_to_serial(datetime.now()),
    "TODAY": lambda: date_to_serial(date.today()),
    "DATE": fn_date,
    "YEAR": _date_part("year"),
    "MONTH": _date_part("month"),
    "DAY": _date_part("day"),
}

LAZY = {"IF"}

# Grouped for the Insert Function dialog.
CATEGORIES = {
    "Most Recently Used": ["SUM", "AVERAGE", "IF", "HYPERLINK", "COUNT", "MAX", "SIN",
                           "SUMIF", "PMT", "STDEV"],
    "Math & Trig": ["ABS", "INT", "MOD", "PI", "POWER", "PRODUCT", "RAND", "RANDBETWEEN",
                    "ROUND", "ROUNDDOWN", "ROUNDUP", "SIGN", "SQRT", "SUM", "SUMIF",
                    "EXP", "LN", "LOG", "LOG10"],
    "Statistical": ["AVERAGE", "AVERAGEIF", "COUNT", "COUNTA", "COUNTBLANK", "COUNTIF",
                    "LARGE", "MAX", "MEDIAN", "MIN", "SMALL", "STDEV"],
    "Lookup & Reference": ["CHOOSE", "HLOOKUP", "INDEX", "MATCH", "VLOOKUP"],
    "Text": ["CONCATENATE", "EXACT", "FIND", "LEFT", "LEN", "LOWER", "MID", "PROPER",
             "REPT", "RIGHT", "SEARCH", "SUBSTITUTE", "TEXT", "TRIM", "UPPER", "VALUE"],
    "Logical": ["AND", "FALSE", "IF", "IFERROR", "NOT", "OR", "TRUE"],
    "Information": ["ISBLANK", "ISERROR", "ISNA", "ISNUMBER", "ISTEXT", "NA"],
    "Date & Time": ["DATE", "DAY", "MONTH", "NOW", "TODAY", "YEAR"],
}
