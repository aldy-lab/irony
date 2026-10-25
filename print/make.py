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

MENU_URL = "https://aldy-lab.github.io/irony/menu/"

# Derived from the bar's own Maps link: the two 64-bit numbers in it, encoded
# the way Google encodes a place id. "ChIJ" is the base64 of the three-byte
# protobuf header, which is how this was checked. Scan it once before any
# print run — that is worth doing for any printed code, derived or not.
PLACE_ID = "ChIJv2EoqCmVC0cRKv96pp_mHTw"
REVIEW_URL = f"https://search.google.com/local/writereview?placeid={PLACE_ID}"

# ---------------------------------------------------------------------------
# Ink and paper
# ---------------------------------------------------------------------------

INK = (0x16 / 255, 0x21 / 255, 0x0b / 255)
PAPER = (0xfb / 255, 0xfa / 255, 0xf7 / 255)
WARM = (0xe9 / 255, 0xe4 / 255, 0xd6 / 255)
GREEN_TINT = (0xe2 / 255, 0xe7 / 255, 0xdc / 255)
MUTED = (0x65 / 255, 0x6e / 255, 0x5b / 255)

MM = 2.834645669

BLEED = 3 * MM
SAFE = 4 * MM


def mm(value: float) -> float:
    return value * MM


# ---------------------------------------------------------------------------
# A stylised code
# ---------------------------------------------------------------------------

def code_matrix(data: str):
    """The code's modules, at the strongest error correction.

    H carries thirty percent, which is what pays for the mark in the middle.
    """
    qr = segno.make(data, error="h", boost_error=False)
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


def draw_code(shape, data: str, x: float, y: float, side: float,
              ink=INK, knockout: float = 0.0):
    """Draw a code of `side` points with its top-left at (x, y).

    Round modules and squared-off corner marks: the corners are what a phone
    locks onto, so they stay solid and square while the data goes to dots.
    """
    matrix = code_matrix(data)
    size = len(matrix)
    quiet = 4                      # modules, and not negotiable in print
    unit = side / (size + quiet * 2)

    # The quiet zone is paper, whatever the piece is tinted. The first proof
    # put a dark-green code straight onto a warm tint and nothing read it:
    # a scanner wants the lightest light it can get next to the darkest dark.
    shape.draw_rect(fitz.Rect(x, y, x + side, y + side))
    shape.finish(color=None, fill=PAPER, width=0)
    origin_x = x + quiet * unit
    origin_y = y + quiet * unit
    finders = finder_cells(size)

    # The middle is cleared for the mark. H can lose thirty percent; this
    # takes about twelve.
    hole = None
    if knockout:
        half = knockout * size / 2
        hole = (size / 2 - half, size / 2 - half, size / 2 + half, size / 2 + half)

    radius = unit * 0.5     # touching, not floating: see the note on the panel
    for row in range(size):
        for col in range(size):
            if not matrix[row][col]:
                continue
            if (row, col) in finders:
                continue
            if hole and hole[0] <= col <= hole[2] and hole[1] <= row <= hole[3]:
                continue
            cx = origin_x + (col + 0.5) * unit
            cy = origin_y + (row + 0.5) * unit
            shape.draw_circle(fitz.Point(cx, cy), radius)
    shape.finish(color=None, fill=ink, width=0)

    # Corner marks: a square ring with a square eye, in the brand's manner.
    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        ox = origin_x + left * unit
        oy = origin_y + top * unit
        outer = fitz.Rect(ox, oy, ox + 7 * unit, oy + 7 * unit)
        inner = fitz.Rect(ox + unit, oy + unit, ox + 6 * unit, oy + 6 * unit)
        eye = fitz.Rect(ox + 2 * unit, oy + 2 * unit,
                        ox + 5 * unit, oy + 5 * unit)
        shape.draw_rect(outer)
        shape.finish(color=None, fill=ink, width=0)
        shape.draw_rect(inner)
        shape.finish(color=None, fill=PAPER, width=0)
        shape.draw_rect(eye)
        shape.finish(color=None, fill=ink, width=0)

    DRAWN.append({"page": shape.page.number,
                  "rect": fitz.Rect(x, y, x + side, y + side),
                  "data": data, "mm": side / 72 * 25.4})

    return {
        "unit": unit, "size": size,
        "hole": fitz.Rect(
            origin_x + hole[0] * unit, origin_y + hole[1] * unit,
            origin_x + hole[2] * unit, origin_y + hole[3] * unit
        ) if hole else None,
    }


# ---------------------------------------------------------------------------
# Marks and type
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


def crop_marks(page, trim: fitz.Rect):
    """Where to cut. Outside the trim, in the bleed, as a printer expects."""
    arm = mm(2.5)
    gap = mm(1.0)
    shape = page.new_shape()
    for x in (trim.x0, trim.x1):
        for y in (trim.y0, trim.y1):
            dx = -1 if x == trim.x0 else 1
            dy = -1 if y == trim.y0 else 1
            shape.draw_line(fitz.Point(x + dx * gap, y),
                            fitz.Point(x + dx * (gap + arm), y))
            shape.draw_line(fitz.Point(x, y + dy * gap),
                            fitz.Point(x, y + dy * (gap + arm)))
    shape.finish(color=(0, 0, 0), width=0.25)
    shape.commit()


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------

def new_page(doc, w_mm: float, h_mm: float):
    """A page with bleed all round, and the trim box it will be cut to."""
    page = doc.new_page(width=mm(w_mm) + 2 * BLEED, height=mm(h_mm) + 2 * BLEED)
    trim = fitz.Rect(BLEED, BLEED, BLEED + mm(w_mm), BLEED + mm(h_mm))
    page.draw_rect(page.rect, color=None, fill=PAPER)
    return page, trim


def side_menu(page, trim, tint=WARM):
    """The side a guest scans to read the list."""
    page.draw_rect(trim, color=None, fill=tint)
    cx = (trim.x0 + trim.x1) / 2

    place_mark(page, "wordmark-line1",
               fitz.Rect(cx - mm(21), trim.y0 + mm(5.5), cx + mm(21), trim.y0 + mm(11)))
    place_mark(page, "wordmark-line2",
               fitz.Rect(cx - mm(13.5), trim.y0 + mm(11.4), cx + mm(13.5), trim.y0 + mm(16.5)))

    side = mm(30)
    shape = page.new_shape()
    spec = draw_code(shape, MENU_URL, cx - side / 2, trim.y0 + mm(18), side,
                     knockout=0.26)
    shape.commit()
    if spec["hole"]:
        place_mark(page, "satyr", spec["hole"] + (mm(1.4), mm(0.2), -mm(1.4), -mm(0.2)))

    centred(page, "THE MENU", cx, trim.y1 - mm(6.4), 6.2, "display", INK, tracking=2.4)
    centred(page, "Jídelní lístek  ·  Меню", cx, trim.y1 - mm(3.1), 5.4, "italic", MUTED)


def side_review(page, trim, tint=GREEN_TINT):
    """The side somebody scans on the way out."""
    page.draw_rect(trim, color=None, fill=tint)
    cx = (trim.x0 + trim.x1) / 2

    centred(page, "WAS IT ANY GOOD?", cx, trim.y0 + mm(8.5), 7.0, "display",
            INK, tracking=2.0)

    side = mm(29)
    shape = page.new_shape()
    spec = draw_code(shape, REVIEW_URL, cx - side / 2, trim.y0 + mm(12), side,
                     knockout=0.24)
    shape.commit()
    if spec["hole"]:
        place_mark(page, "motif", spec["hole"] + (mm(0.6), mm(1.8), -mm(0.6), -mm(1.8)))

    centred(page, "Tell Google. It takes a minute.", cx, trim.y1 - mm(6.2),
            6.0, "italic", INK)
    centred(page, "IRONY VS. SATYR  ·  NOVÉ MĚSTO", cx, trim.y1 - mm(2.8), 4.8,
            "display", MUTED, tracking=1.4)


def make_card(doc):
    """A plastic card, CR80, the size of a bank card."""
    for side in (side_menu, side_review):
        page, trim = new_page(doc, 85.6, 54)
        side(page, trim)
        crop_marks(page, trim)


def make_business_card(doc):
    """For the hand, not the table: who the bar is and where."""
    page, trim = new_page(doc, 85, 55)
    page.draw_rect(trim, color=None, fill=PAPER)
    cx = (trim.x0 + trim.x1) / 2

    place_mark(page, "satyr",
               fitz.Rect(trim.x0 + mm(6), trim.y0 + mm(7),
                         trim.x0 + mm(22), trim.y1 - mm(7)))
    left = trim.x0 + mm(27)
    place_mark(page, "wordmark-line1",
               fitz.Rect(left, trim.y0 + mm(9), left + mm(40), trim.y0 + mm(14.3)))
    place_mark(page, "wordmark-line2",
               fitz.Rect(left, trim.y0 + mm(14.8), left + mm(25.5), trim.y0 + mm(19.6)))
    write(page, "COCKTAIL BAR", left, trim.y0 + mm(24), 5.4, "display", MUTED,
          tracking=1.8)
    write(page, "Soukenická 1756, Nové Město", left, trim.y0 + mm(29.5), 6.6, "body")
    write(page, "110 00 Praha", left, trim.y0 + mm(33.5), 6.6, "body")
    write(page, "Daily from 12:00", left, trim.y0 + mm(39.5), 6.6, "italic", MUTED)

    side = mm(17)
    shape = page.new_shape()
    draw_code(shape, MENU_URL, trim.x1 - side - mm(5), trim.y1 - side - mm(4), side)
    shape.commit()
    crop_marks(page, trim)

    # The back carries the review code, as the plastic card does: a card
    # handed over at the door is the one still in a pocket the next morning.
    page, trim = new_page(doc, 85, 55)
    page.draw_rect(trim, color=None, fill=WARM)
    cx = (trim.x0 + trim.x1) / 2
    centred(page, "The classics, poured properly.", cx, trim.y0 + mm(9),
            8.6, "italic", INK)

    side = mm(23)
    shape = page.new_shape()
    draw_code(shape, REVIEW_URL, cx - side / 2, trim.y0 + mm(13), side)
    shape.commit()
    centred(page, "WAS IT ANY GOOD? TELL GOOGLE.", cx, trim.y1 - mm(5.4), 5.2,
            "display", MUTED, tracking=1.6)
    crop_marks(page, trim)


def make_coaster(doc):
    """Round, under the glass, with both codes on the one face."""
    size = 95
    page = doc.new_page(width=mm(size) + 2 * BLEED, height=mm(size) + 2 * BLEED)
    page.draw_rect(page.rect, color=None, fill=PAPER)
    cx = cy = (mm(size) + 2 * BLEED) / 2
    r = mm(size) / 2

    # Bleed to the edge, because a round cut never lands exactly.
    page.draw_circle(fitz.Point(cx, cy), r + BLEED, color=None, fill=WARM)
    page.draw_circle(fitz.Point(cx, cy), r, color=None, fill=WARM)

    place_mark(page, "wordmark-line1",
               fitz.Rect(cx - mm(21), cy - mm(40), cx + mm(21), cy - mm(34.4)))
    place_mark(page, "wordmark-line2",
               fitz.Rect(cx - mm(13.5), cy - mm(34), cx + mm(13.5), cy - mm(28.9)))

    side = mm(30)
    shape = page.new_shape()
    menu = draw_code(shape, MENU_URL, cx - side - mm(2.5), cy - mm(13), side,
                     knockout=0.26)
    review = draw_code(shape, REVIEW_URL, cx + mm(2.5), cy - mm(13), side,
                       knockout=0.24)
    shape.commit()
    if menu["hole"]:
        place_mark(page, "satyr", menu["hole"] + (mm(1.4), mm(0.2), -mm(1.4), -mm(0.2)))
    if review["hole"]:
        place_mark(page, "motif", review["hole"] + (mm(0.6), mm(1.8), -mm(0.6), -mm(1.8)))

    centred(page, "THE MENU", cx - side / 2 - mm(2.5), cy + mm(21), 6.4,
            "display", INK, tracking=2.2)
    centred(page, "WAS IT GOOD?", cx + side / 2 + mm(2.5), cy + mm(21), 6.4,
            "display", INK, tracking=2.2)
    centred(page, "Soukenická 1756  ·  Nové Město  ·  Praha", cx, cy + mm(33),
            6.0, "italic", MUTED)

    # The cut line, on its own, for the die.
    page.draw_circle(fitz.Point(cx, cy), r, color=(1, 0, 1), fill=None, width=0.5)


def make_sticker(doc):
    """For the table itself: one code, read from standing height."""
    page, trim = new_page(doc, 90, 60)
    page.draw_rect(trim, color=None, fill=GREEN_TINT)
    cx = (trim.x0 + trim.x1) / 2

    side = mm(36)
    shape = page.new_shape()
    spec = draw_code(shape, MENU_URL, trim.x0 + mm(6), (trim.y0 + trim.y1) / 2 - side / 2,
                     side, knockout=0.26)
    shape.commit()
    if spec["hole"]:
        place_mark(page, "satyr", spec["hole"] + (mm(1.6), mm(0.2), -mm(1.6), -mm(0.2)))

    left = trim.x0 + mm(45)
    place_mark(page, "wordmark-line1",
               fitz.Rect(left, trim.y0 + mm(13), left + mm(37), trim.y0 + mm(18)))
    place_mark(page, "wordmark-line2",
               fitz.Rect(left, trim.y0 + mm(18.5), left + mm(23.5), trim.y0 + mm(23)))
    write(page, "SCAN FOR THE MENU", left, trim.y0 + mm(30), 6.2, "display",
          INK, tracking=1.9)
    write(page, "Jídelní lístek · Меню · Menu", left, trim.y0 + mm(35), 6.0,
          "italic", MUTED)
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
        draw(doc)
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
