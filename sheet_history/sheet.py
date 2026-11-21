"""Grid model: validation, canonicalization and formula evaluation."""

import json
import re
from decimal import Context, Decimal

ROWS = 8
COLS = 6
LETTERS = "ABCDEF"
MAX_CELL_LEN = 200
MAX_TITLE_LEN = 80

CELL_ID_RE = re.compile(r"\A[A-F][1-8]\Z")
NUMBER_RE = re.compile(r"\A-?[0-9]+(\.[0-9]+)?\Z")
FORMULA_RE = re.compile(r"\A=([A-F][1-8])\+([A-F][1-8])\Z")

# Cell ids in canonical (row, column) order: A1,B1,...,F1,A2,...
ALL_CELLS = tuple("%s%d" % (c, r) for r in range(1, ROWS + 1) for c in LETTERS)

# Large precision so long (<=200 digit) operands are summed exactly.
_CTX = Context(prec=600)


class ValidationError(ValueError):
    """Input rejected; the message is safe to show to the client."""


def validate_text(value, max_len, what, allow_empty):
    if not isinstance(value, str):
        raise ValidationError("%s must be a string" % what)
    if not value and not allow_empty:
        raise ValidationError("%s must not be empty" % what)
    if len(value) > max_len:
        raise ValidationError("%s must be at most %d characters" % (what, max_len))
    for ch in value:
        o = ord(ch)
        if o < 0x20 or o == 0x7F or 0xD800 <= o <= 0xDFFF:
            raise ValidationError("%s contains a disallowed character" % what)
    return value


def validate_title(title):
    return validate_text(title, MAX_TITLE_LEN, "title", False)


def canonicalize_cells(cells):
    """Validate a cells mapping; return a dict of non-empty cells in canonical order."""
    if not isinstance(cells, dict):
        raise ValidationError("cells must be an object")
    for key, value in cells.items():
        if not isinstance(key, str) or not CELL_ID_RE.match(key):
            raise ValidationError("unknown cell id")
        validate_text(value, MAX_CELL_LEN, "cell " + key, True)
    return {cid: cells[cid] for cid in ALL_CELLS if cells.get(cid)}


def dumps_grid(grid):
    return json.dumps(grid, ensure_ascii=False, separators=(",", ":"))


def loads_grid(text):
    try:
        return canonicalize_cells(json.loads(text))
    except (ValueError, RecursionError) as exc:
        raise ValidationError("stored grid is invalid") from exc


def _format(d):
    if d == 0:
        return "0"
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def compute(grid):
    """Map formula cell id -> result string. Never evaluates anything but A+B."""
    out = {}
    for cid in ALL_CELLS:
        text = grid.get(cid)
        if not text:
            continue
        m = FORMULA_RE.match(text)
        if not m:
            continue
        operands = [grid.get(m.group(1), ""), grid.get(m.group(2), "")]
        if any(FORMULA_RE.match(o) for o in operands):
            out[cid] = "#NESTED"
            continue
        total = Decimal(0)
        bad = False
        for o in operands:
            if o == "":
                continue
            if NUMBER_RE.match(o):
                total = _CTX.add(total, Decimal(o))
            else:
                bad = True
        out[cid] = "#VALUE!" if bad else _format(total)
    return out
