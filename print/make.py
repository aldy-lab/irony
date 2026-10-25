#!/usr/bin/env python3
"""The printed pieces: a card, a coaster, a business card, a table sticker.

    python3 print/make.py            # everything, into print/out/
    python3 print/make.py card       # one of them, while working on it

Each comes out as a press-ready PDF with 3 mm of bleed and crop marks, and a
PNG beside it to look at. Vector throughout, in the site's own ink and paper,
set in the fonts the site is set in.

The codes are stylised — round modules, the brand's own corner marks, the
satyr knocked out of the middle — and stylising a code is how a code stops
scanning. So every one of them is rendered at the size it will be printed,
photographed back at 300 dpi and decoded. A piece whose code does not read
is not written out at all.
"""

from __future__ import annotations

import io
import math
import json
import sys
from functools import lru_cache
from pathlib import Path

import fitz
import segno
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"
FONTS = Path(__file__).resolve().parent / ".fonts"

# ---------------------------------------------------------------------------
# What the codes point at
# ---------------------------------------------------------------------------

_site = json.loads((ROOT / "data" / "site.json").read_text())
_base = _site["url"].rstrip("/")

MENU_URL = f"{_base}/menu/"

# The review code points at /r/ on the site, which redirects to Google. Going
# straight at Google needs 79 characters and a 49-module code; this needs 35
# and 33. It is also the only version that can be corrected after printing:
# the place id was derived from the bar's Maps link and never confirmed in a
# browser, and a coaster cannot be edited. build.py builds /r/ from the same
# line of config, or says loudly that it did not.
REVIEW_URL = f"{_base}/r/"
if not _site.get("google_review", "").strip():
    raise SystemExit(
        "site.json has no google_review, so /r/ is not built. A printed code "
        "pointing at a page that does not exist is worse than no code.")

# ---------------------------------------------------------------------------
# Ink and paper
# ---------------------------------------------------------------------------

def _hex(code: str):
    return tuple(int(code[i:i + 2], 16) / 255 for i in (0, 2, 4))


INK = _hex("16210b")          # the brand's dark green, and the ground here
PAPER = _hex("fbfaf7")
MUTED = _hex("656e5b")

# Two golds, because they do different jobs. GOLD is for type and hairlines
# on the green, where it only has to be legible. GILT is a shade lighter and
# carries the codes: a code's modules are read by their contrast with the
# field behind them, and that field has to be the light one.
GOLD = _hex("b08d2e")
GILT = _hex("c3a24a")

# Why the plate is gold and the modules are green, and not the other way
# round: a code is specified as dark modules on a light field. Reversed, it
# is a different thing that some readers happen to tolerate. Tested here
# across five shades of gold, every one of them read as green-on-gold and
# every one failed as gold-on-green, at 300 through 900 dpi. Green on brass
# measures 6.8:1, well clear of what print needs after dot gain.

MM = 2.834645669

BLEED = 3 * MM
SAFE = 4 * MM


def mm(value: float) -> float:
    return value * MM


# ---------------------------------------------------------------------------
# A stylised code
# ---------------------------------------------------------------------------

def code_matrix(data: str, error: str = "q"):
    """The code's modules.

    Q carries twenty-five percent, which is the usual choice for something
    printed that will be wiped, splashed and set a wet glass on. H was only
    needed while a mark sat in the middle of the code; without it, H just
    adds rows of dots for nothing.
    """
    qr = segno.make(data, error=error, boost_error=False)
    return [list(row) for row in qr.matrix]


def finder_cells(size: int) -> set:
    """The three corner squares, which get drawn as shapes rather than dots."""
    cells = set()
    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        for y in range(top, top + 7):
            for x in range(left, left + 7):
                cells.add((y, x))
    return cells


# Every code drawn in the current piece: page, where on it, and what it
# should say. The check reads these one at a time. Asking a detector to
# sweep a whole page instead lets a second code on the same piece go
# unverified while the run still reports success — the coaster carries two.
DRAWN = []

# Every line of type, and the region of its page that type may occupy. These
# exist so that "does the address run under the code?" is a question the run
# answers rather than one somebody has to notice in a preview. It was not
# noticed in a preview: two lines were sitting under a gold plate.
TEXTS = []
SAFE = []


def draw_code(shape, data: str, x: float, y: float, side: float,
              ink=INK, field=GILT, corner: float = 0.0):
    """Draw a code of `side` points with its top-left at (x, y).

    Round modules and squared corner marks: the corners are what a phone
    locks onto, so they stay solid and square while the data goes to dots.
    The code sits on its own plate of `field`, which is both the quiet zone
    the specification demands and the thing that makes it an object on the
    page rather than a sticker dropped onto one.
    """
    matrix = code_matrix(data)
    size = len(matrix)
    quiet = 4                      # modules, and not negotiable in print
    unit = side / (size + quiet * 2)

    plate = fitz.Rect(x, y, x + side, y + side)
    # radius is a fraction of the shorter side, not a length.
    shape.draw_rect(plate, radius=(corner / side) if corner else None)
    shape.finish(color=None, fill=field, width=0)

    origin_x = x + quiet * unit
    origin_y = y + quiet * unit
    finders = finder_cells(size)

    radius = unit * 0.5     # touching, not floating: see the note on the plate
    for row in range(size):
        for col in range(size):
            if not matrix[row][col] or (row, col) in finders:
                continue
            shape.draw_circle(
                fitz.Point(origin_x + (col + 0.5) * unit,
                           origin_y + (row + 0.5) * unit), radius)
    shape.finish(color=None, fill=ink, width=0)

    # Corner marks: a square ring with a square eye, in the brand's manner.
    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        ox = origin_x + left * unit
        oy = origin_y + top * unit
        for inset, colour in ((0, ink), (1, field), (2, ink)):
            box = fitz.Rect(ox + inset * unit, oy + inset * unit,
                            ox + (7 - inset) * unit, oy + (7 - inset) * unit)
            shape.draw_rect(box)
            shape.finish(color=None, fill=colour, width=0)

    DRAWN.append({"page": shape.page.number, "rect": plate,
                  "data": data, "mm": side / 72 * 25.4})
    return {"unit": unit, "size": size, "plate": plate}


# ---------------------------------------------------------------------------

def mark_svg(name: str) -> str:
    return (ROOT / "assets" / "brand" / f"{name}.svg").read_text()


def place_mark(page, name: str, rect: fitz.Rect, colour=INK):
    """Drop one of the brand's drawings into a box, in one colour."""
    svg = mark_svg(name)
    paint = "#%02x%02x%02x" % tuple(round(c * 255) for c in colour)
    svg = svg.replace("currentColor", paint)
    if "fill=" not in svg.split(">")[0]:
        svg = svg.replace("<svg", f'<svg fill="{paint}"', 1)
    doc = fitz.open("svg", svg.encode())
    pdf = fitz.open("pdf", doc.convert_to_pdf())
    page.show_pdf_page(rect, pdf, 0)
    # A drawing can run off the edge exactly as a line of type can, so it is
    # registered the same way. The wordmark was crossing the coaster's ring.
    TEXTS.append({"page": page.number, "text": f"<{name}>", "rect": rect})


def ready_fonts():
    """Unpack the site's own webfonts into something a PDF can embed.

    The print pieces and the site must not drift apart, so these are the
    same files the pages load, not a second copy fetched by hand. An earlier
    version read them from a scratch folder that only existed on the machine
    they were first made on.
    """
    FONTS.mkdir(exist_ok=True)
    for source in sorted((ROOT / "assets" / "fonts").glob("*.woff2")):
        target = FONTS / (source.stem + ".ttf")
        if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
            continue
        font = TTFont(source)
        font.flavor = None
        font.save(target)


# Characters no font file could set. They print as empty boxes, so a
# non-empty set here is a defect, not a warning.
MISSING = set()


@lru_cache(maxsize=None)
def _covers(path: str) -> frozenset:
    return frozenset(TTFont(path).getBestCmap())


def font_file(which: str, text: str = "") -> str:
    """The subset that carries this text, or the one that carries most of it."""
    return runs(which, text)[0][1] if text else _subsets(which)[0]


def _subsets(which: str) -> list:
    base = {
        "display": "cormorant-garamond-normal-500",
        "body": "eb-garamond-normal-400800",
        "italic": "eb-garamond-italic-400800",
    }[which]
    return [str(FONTS / f"{base}-{part}.ttf")
            for part in ("latin", "ext", "cyrillic")]


def runs(which: str, text: str) -> list:
    """Split a line into stretches each of which one font file can set.

    The families arrive from the site already split by script, so no single
    file holds "Napojovy listek · Меню": the Czech accents live in the
    extended subset and the Cyrillic in its own. Set the line from one file
    and the characters it lacks print as empty boxes, silently — which is
    what the first proof of the card did.
    """
    files = _subsets(which)
    out = []
    for ch in text:
        for path in files:
            if ord(ch) in _covers(path):
                break
        else:
            path = files[0]
            MISSING.add(ch)
        if out and out[-1][1] == path:
            out[-1][0] += ch
        else:
            out.append([ch, path])
    return out or [["", files[0]]]


def _name(which: str, path: str) -> str:
    """A page keeps one font per name, so the name has to change with the
    file. Reusing "F1" for a second file hands back the first one."""
    tail = path.rsplit("-", 1)[1].split(".")[0]
    return {"display": "F0", "body": "F1", "italic": "F2"}[which] + tail[0]


def write(page, text: str, x: float, y: float, size: float, which="body",
          colour=INK, align=0, width=None, tracking=0.0):
    """One line, with optional letterspacing, since the brand sets small
    capitals wide and a PDF will not do it on its own."""
    pieces = runs(which, text)
    fonts = {path: fitz.Font(fontfile=path) for _chars, path in pieces}

    def advance(chars, path):
        font = fonts[path]
        return sum(font.text_length(ch, size) + tracking for ch in chars)

    total = sum(advance(chars, path) for chars, path in pieces)
    if tracking:
        total -= tracking
    start = x - total / 2 if align == 1 else (x - total if align == 2 else x)

    TEXTS.append({
        "page": page.number, "text": text,
        "rect": fitz.Rect(start, y - size * 0.82, start + total, y + size * 0.26),
    })

    for chars, path in pieces:
        name = _name(which, path)
        if not tracking:
            page.insert_text(fitz.Point(start, y), chars, fontname=name,
                             fontfile=path, fontsize=size, color=colour)
            start += advance(chars, path)
            continue
        for ch in chars:
            page.insert_text(fitz.Point(start, y), ch, fontname=name,
                             fontfile=path, fontsize=size, color=colour)
            start += fonts[path].text_length(ch, size) + tracking


def centred(page, text: str, cx: float, y: float, size: float, which="body",
            colour=INK, tracking=0.0):
    """Centred on cx. Goes through write() so a line that needs more than one
    font file is set from all of them rather than from the first."""
    write(page, text, cx, y, size, which, colour, align=1, tracking=tracking)


# Room outside the bleed for the cut marks themselves. Without it the marks
# are drawn on top of the artwork, where a guillotine operator cannot use
# them, and the earlier version put them 0.5 mm past the edge of the page.
MARGIN = mm(5)


def crop_marks(page, trim: fitz.Rect):
    """Where to cut: outside the bleed, on bare paper, as a printer expects."""
    arm = mm(3.5)
    gap = BLEED + mm(1.0)
    shape = page.new_shape()
    for x, dx in ((trim.x0, -1), (trim.x1, 1)):
        for y, dy in ((trim.y0, -1), (trim.y1, 1)):
            shape.draw_line(fitz.Point(x + dx * gap, y),
                            fitz.Point(x + dx * (gap + arm), y))
            shape.draw_line(fitz.Point(x, y + dy * gap),
                            fitz.Point(x, y + dy * (gap + arm)))
    shape.finish(color=(0, 0, 0), width=0.25)
    shape.commit()


# ---------------------------------------------------------------------------
# The pieces
#
# One language across all four: the brand's dark green as the ground, gold for
# the type and the hairlines, and every code on a gold plate with the modules
# in green. See the note on the palette for why the plate is the light one.
# ---------------------------------------------------------------------------

def new_page(doc, w_mm: float, h_mm: float, ground=INK):
    """A page with bleed, cut marks outside it, and the trim box between.

    The ground is painted over the whole bleed box, not just the trim. An
    earlier version filled the trim only, so every rectangular piece went out
    with a 3 mm white border where its bleed was supposed to be — and the
    preview looked correct, because a preview shows the page, not the cut.
    """
    pad = BLEED + MARGIN
    page = doc.new_page(width=mm(w_mm) + 2 * pad, height=mm(h_mm) + 2 * pad)
    page.draw_rect(page.rect, color=None, fill=PAPER)
    trim = fitz.Rect(pad, pad, pad + mm(w_mm), pad + mm(h_mm))
    page.draw_rect(trim + (-BLEED, -BLEED, BLEED, BLEED), color=None, fill=ground)
    SAFE.append({"page": page.number, "kind": "rect",
                 "rect": trim + (mm(4), mm(4), -mm(4), -mm(4))})
    return page, trim


def hairline(page, rect: fitz.Rect, colour=GOLD, width=0.6):
    """The thin rule that holds a small piece together."""
    page.draw_rect(rect, color=colour, fill=None, width=width)


def plate(page, data: str, cx: float, top: float, side: float):
    """A code on its gold plate, centred on cx."""
    shape = page.new_shape()
    spec = draw_code(shape, data, cx - side / 2, top, side, corner=mm(2.2))
    shape.commit()
    return spec


def wordmark(page, cx: float, top: float, w: float, colour=GOLD):
    """Both lines of the wordmark, centred, scaled from the first line's width."""
    place_mark(page, "wordmark-line1",
               fitz.Rect(cx - w / 2, top, cx + w / 2, top + w * 0.133),
               colour=colour)
    second = w * 0.645
    place_mark(page, "wordmark-line2",
               fitz.Rect(cx - second / 2, top + w * 0.145,
                         cx + second / 2, top + w * 0.145 + second * 0.188),
               colour=colour)


# --- the plastic card ------------------------------------------------------

def card_side(page, trim, title, sub, data, foot=""):
    """One face of a landscape card: words on the left, the code on the right.

    Landscape is the shape of the piece, so the code goes beside the words
    rather than under them — stacked, a 54 mm card leaves the code 22 mm and
    the type nowhere to breathe. The sizes below are measured against the
    32.6 mm the left column actually has; the first set were not, and two
    lines ran under the plate.
    """
    hairline(page, trim + (mm(3), mm(3), -mm(3), -mm(3)))
    left = trim.x0 + mm(8)

    side = mm(31)
    plate(page, data, trim.x1 - mm(8) - side / 2,
          trim.y0 + (trim.y1 - trim.y0 - side) / 2, side)

    write(page, title, left, trim.y0 + mm(24), 6.2, "display", GOLD,
          tracking=1.5)
    write(page, sub, left, trim.y0 + mm(31), 6.4, "italic", PAPER)
    if foot:
        write(page, foot, left, trim.y0 + mm(39), 5.0, "display", GOLD,
              tracking=1.4)
    crop_marks(page, trim)


def make_card(doc):
    """CR80, the size of a bank card, for the table."""
    page, trim = new_page(doc, 85.6, 54)
    wordmark(page, trim.x0 + mm(23), trim.y0 + mm(8), mm(28))
    card_side(page, trim, "THE MENU", "Jídelní lístek  ·  Меню", MENU_URL)

    page, trim = new_page(doc, 85.6, 54)
    wordmark(page, trim.x0 + mm(23), trim.y0 + mm(8), mm(28))
    card_side(page, trim, "WAS IT ANY GOOD?", "Tell Google. It takes a minute.",
              REVIEW_URL, foot="NOVÉ MĚSTO  ·  PRAHA")


# --- the business card -----------------------------------------------------

def make_business_card(doc):
    """For the hand: who the bar is on the front, the menu on the back."""
    page, trim = new_page(doc, 85, 55)
    hairline(page, trim + (mm(3), mm(3), -mm(3), -mm(3)))
    place_mark(page, "satyr",
               fitz.Rect(trim.x0 + mm(8), trim.y0 + mm(10),
                         trim.x0 + mm(24), trim.y1 - mm(10)), colour=GOLD)
    left = trim.x0 + mm(30)
    place_mark(page, "wordmark-line1",
               fitz.Rect(left, trim.y0 + mm(12), left + mm(40), trim.y0 + mm(17.3)),
               colour=GOLD)
    place_mark(page, "wordmark-line2",
               fitz.Rect(left, trim.y0 + mm(17.8), left + mm(25.5), trim.y0 + mm(22.6)),
               colour=GOLD)
    write(page, "COCKTAIL BAR", left, trim.y0 + mm(28), 5.6, "display", GOLD,
          tracking=2.0)
    write(page, "Soukenická 1756, Nové Město", left, trim.y0 + mm(35), 6.8,
          "body", PAPER)
    write(page, "110 00 Praha", left, trim.y0 + mm(39.5), 6.8, "body", PAPER)
    write(page, "Daily from 12:00", left, trim.y0 + mm(45.5), 6.6, "italic",
          GOLD)
    crop_marks(page, trim)

    # The back is the menu, and only the menu.
    page, trim = new_page(doc, 85, 55)
    hairline(page, trim + (mm(3), mm(3), -mm(3), -mm(3)))
    cx = (trim.x0 + trim.x1) / 2
    side = mm(30)
    plate(page, MENU_URL, cx, trim.y0 + mm(9), side)
    centred(page, "THE MENU", cx, trim.y1 - mm(13), 7.4, "display", GOLD,
            tracking=2.8)
    centred(page, "Jídelní lístek  ·  Меню  ·  Menu", cx, trim.y1 - mm(7),
            6.2, "italic", PAPER)
    crop_marks(page, trim)


# --- the coaster -----------------------------------------------------------

def coaster_face(doc, size_mm: float):
    """A round face with bleed past the cut, and the cut drawn for the die."""
    pad = BLEED + MARGIN
    page = doc.new_page(width=mm(size_mm) + 2 * pad, height=mm(size_mm) + 2 * pad)
    page.draw_rect(page.rect, color=None, fill=PAPER)
    cx = cy = (mm(size_mm) + 2 * pad) / 2
    r = mm(size_mm) / 2
    # Bleed past the cut, because a round die never lands exactly.
    page.draw_circle(fitz.Point(cx, cy), r + BLEED, color=None, fill=INK)
    page.draw_circle(fitz.Point(cx, cy), r - mm(4.5), color=GOLD, fill=None,
                     width=0.6)
    SAFE.append({"page": page.number, "kind": "circle",
                 "centre": (cx, cy), "r": r - mm(6.5)})
    return page, cx, cy, r


def close_coaster(page, cx, cy, r):
    """Magenta is the die line: a cutter reads it as the cut, not as art."""
    page.draw_circle(fitz.Point(cx, cy), r, color=(1, 0, 1), fill=None, width=0.5)


def make_coaster(doc):
    """Round, under the glass. One code a side, so each gets the whole face."""
    size = 95

    page, cx, cy, r = coaster_face(doc, size)
    wordmark(page, cx, cy - mm(33), mm(38))
    plate(page, MENU_URL, cx, cy - mm(20), mm(42))
    centred(page, "THE MENU", cx, cy + mm(29), 8.4, "display", GOLD, tracking=3.2)
    centred(page, "Jídelní lístek  ·  Меню", cx, cy + mm(35.5), 6.6, "italic",
            PAPER)
    close_coaster(page, cx, cy, r)

    page, cx, cy, r = coaster_face(doc, size)
    centred(page, "WAS IT ANY GOOD?", cx, cy - mm(31), 8.4, "display", GOLD,
            tracking=3.2)
    plate(page, REVIEW_URL, cx, cy - mm(24), mm(42))
    centred(page, "Tell Google. It takes a minute.", cx, cy + mm(27), 7.6,
            "italic", PAPER)
    centred(page, "NOVÉ MĚSTO  ·  PRAHA", cx, cy + mm(35), 5.8,
            "display", GOLD, tracking=2.2)
    close_coaster(page, cx, cy, r)


# --- the table sticker -----------------------------------------------------

def make_sticker(doc):
    """For the table itself: one code, read from standing height."""
    page, trim = new_page(doc, 90, 60)
    hairline(page, trim + (mm(3.5), mm(3.5), -mm(3.5), -mm(3.5)))
    middle = trim.y0 + (trim.y1 - trim.y0) / 2

    side = mm(38)
    plate(page, MENU_URL, trim.x0 + mm(10) + side / 2, middle - side / 2, side)

    left = trim.x0 + mm(52)
    place_mark(page, "wordmark-line1",
               fitz.Rect(left, trim.y0 + mm(15), left + mm(30), trim.y0 + mm(19)),
               colour=GOLD)
    place_mark(page, "wordmark-line2",
               fitz.Rect(left, trim.y0 + mm(19.5), left + mm(19.4), trim.y0 + mm(23.1)),
               colour=GOLD)
    write(page, "SCAN FOR", left, trim.y0 + mm(31), 6.6, "display", GOLD,
          tracking=2.2)
    write(page, "THE MENU", left, trim.y0 + mm(36), 6.6, "display", GOLD,
          tracking=2.2)
    write(page, "Jídelní lístek", left, trim.y0 + mm(43), 6.2, "italic", PAPER)
    write(page, "Меню  ·  Menu", left, trim.y0 + mm(47.5), 6.2, "italic", PAPER)
    crop_marks(page, trim)


PIECES = {
    "card": ("card", make_card),
    "coaster": ("coaster", make_coaster),
    "business-card": ("business-card", make_business_card),
    "sticker": ("table-sticker", make_sticker),
}


# ---------------------------------------------------------------------------
# Does it actually scan?
# ---------------------------------------------------------------------------

# How finely the page is sampled before the codes are read back. A phone
# camera held over a card resolves better than the lowest of these; the
# lowest that still reads is reported, because a code that only decodes at
# 600 is a code that is too small on paper.
def check_layout() -> list:
    """Nothing may sit under a code, or outside the area the piece allows."""
    trouble = []
    regions = {r["page"]: r for r in SAFE}

    for item in TEXTS:
        for code in DRAWN:
            if code["page"] != item["page"]:
                continue
            if item["rect"].intersects(code["rect"]):
                trouble.append(f"page {item['page'] + 1}: "
                               f"{item['text'][:34]!r} runs under a code")
        region = regions.get(item["page"])
        if not region:
            continue
        box = item["rect"]
        if region["kind"] == "rect":
            if box not in region["rect"]:
                trouble.append(f"page {item['page'] + 1}: "
                               f"{item['text'][:34]!r} leaves the safe area")
        else:
            cx, cy, r = region["centre"][0], region["centre"][1], region["r"]
            corners = ((box.x0, box.y0), (box.x1, box.y0),
                       (box.x0, box.y1), (box.x1, box.y1))
            if any(math.hypot(x - cx, y - cy) > r for x, y in corners):
                trouble.append(f"page {item['page'] + 1}: "
                               f"{item['text'][:34]!r} crosses the ring")
    return trouble


SAMPLES = (300, 450, 600, 900)


def read_codes(pdf: Path, drawn: list) -> list:
    """Photograph each code where it was drawn and read it back.

    A stylised code that does not decode is a thousand printed cards nobody
    can use. This is the only part of the file that is not about looks.
    """
    import cv2
    import numpy as np

    detector = cv2.QRCodeDetector()
    doc = fitz.open(pdf)
    results = []
    for code in drawn:
        page = doc[code["page"]]
        got, read_at = None, None
        for dpi in SAMPLES:
            scale = dpi / 72
            # A little paper around the code, the way a phone frames one.
            box = code["rect"] + (-9, -9, 9, 9)
            pix = page.get_pixmap(dpi=dpi, clip=box)
            array = np.array(
                Image.open(io.BytesIO(pix.tobytes("png"))).convert("L"))
            said = detector.detectAndDecode(array)[0]
            if said:
                got, read_at = said, dpi
                break
        results.append({**code, "read": got, "dpi": read_at})
    doc.close()
    return results

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ready_fonts()
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")]
    problems = []
    worst = 0

    for key, (name, draw) in PIECES.items():
        if wanted and key not in wanted:
            continue
        doc = fitz.open()
        DRAWN.clear()
        TEXTS.clear()
        SAFE.clear()
        draw(doc)
        for note in check_layout():
            problems.append(f"{name}: {note}")
        drawn = list(DRAWN)
        doc_pages = range(len(doc))
        path = OUT / f"{name}.pdf"
        doc.save(str(path), deflate=True)
        doc.close()

        read = read_codes(path, drawn)
        print(f"  {name:16} {len(doc_pages)} "
              f"{'page' if len(doc_pages) == 1 else 'pages'}, "
              f"{len(read)} code{'' if len(read) == 1 else 's'}, "
              f"{path.stat().st_size // 1024} KB")
        for code in read:
            where = f"page {code['page'] + 1}, {code['mm']:.0f} mm"
            if code["read"] is None:
                print(f"      {where}: NOT READ at any of {SAMPLES}")
                problems.append(f"{name}: a code on page {code['page'] + 1} "
                                "could not be read")
            elif code["read"] != code["data"]:
                print(f"      {where}: READ THE WRONG THING")
                problems.append(f"{name}: a code reads {code['read'][:60]!r}, "
                                f"not what it was given")
            else:
                print(f"      {where}: {code['dpi']} dpi — "
                      + code["read"].replace("https://", "")[:44])
                worst = max(worst, code["dpi"])
            if code["mm"] < 15:
                problems.append(f"{name}: a code is only {code['mm']:.0f} mm "
                                "across; under 15 mm is unreliable in a bar")

        # Something to look at without opening a PDF.
        doc = fitz.open(path)
        for number, page in enumerate(doc, 1):
            pix = page.get_pixmap(dpi=200)
            suffix = "" if len(doc) == 1 else f"-{number}"
            pix.save(str(OUT / f"{name}{suffix}.png"))
        doc.close()

    if MISSING:
        problems.append("no glyph for " + " ".join(
            f"{ch!r} (U+{ord(ch):04X})" for ch in sorted(MISSING)))

    if problems:
        print("\n" + "\n".join("  ! " + p for p in problems))
        return 1
    print(f"\n  every code on every piece read back, "
          f"the worst needing {worst} dpi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
