#!/usr/bin/env python3
"""Draw every drink on the menu, so the menu has pictures.

    python3 tools/draw_drinks.py               # all of them
    python3 tools/draw_drinks.py negroni       # one, while working on it
    python3 tools/draw_drinks.py --svg         # keep the SVG beside the WebP

A guest chooses on a phone, and a list of names and prices is a spreadsheet.
Every drink gets a picture: the glass it arrives in, the colour it actually
is, its ice and its garnish. Drawn here as SVG and rendered by the same
headless Chromium that tools/check.py drives, so a new drink is a row in a
table rather than a photo shoot, and all seventy-seven share one light, one
angle and one hand.

They are drawings, not photographs. That is deliberate: the bar's own images
are a bought engraving set, a stock poster in a frame, a phone snap and, for
one drink, the logo — different provenance and different quality on every
card. A drawing can be honest about a drink nobody has photographed yet, and
it costs nothing to redraw when the recipe changes.

Written to assets/drinks/<slug>.webp at 320 and 640. A real photograph
dropped in at the same slug replaces the drawing with no code change.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "drinks"
SIZES = (320, 640)

# Drawn on the paper the site is printed on, in the ink it is set in. The
# first pass drew a pale line for a dark page, which meant every picture had
# to sit on a black panel wherever the page was light — a patch, and the
# patch was the thing you noticed.
#
# The line is thin and even, the liquid a flat tint the paper shows through,
# and there is no highlight: this is a drawing of a glass in the manner of a
# technical drawing, not a rendering of one.
GLASS = "#16210b"          # the ink the site is set in
GLASS_SOFT = "#3d4634"
STROKE = 2.0               # at a 200-unit canvas, about 1px as shown
HAIRLINE = 1.4
TINT = 0.55                # the liquid lets the paper through

# ---------------------------------------------------------------------------
# Glassware. Each returns the outline, and the inside the liquid may fill.
# Coordinates are in a 200x260 box standing on y=236.
# ---------------------------------------------------------------------------

FLOOR = 236.0


def coupe():
    bowl = "M50 100 C50 142 76 162 100 162 C124 162 150 142 150 100 Z"
    return {
        "outline": [bowl, "M100 162 L100 214",
                    "M70 216 C70 207 130 207 130 216 C130 223 70 223 70 216 Z"],
        "fill": bowl, "top": 100.0, "bottom": 162.0,
        "rim": (50.0, 150.0, 100.0), "wide": True,
    }


def martini():
    bowl = "M48 94 L152 94 L100 164 Z"
    return {
        "outline": [bowl, "M100 164 L100 214",
                    "M70 216 C70 207 130 207 130 216 C130 223 70 223 70 216 Z"],
        "fill": bowl, "top": 94.0, "bottom": 164.0,
        "rim": (48.0, 152.0, 94.0), "wide": True,
    }


def flute():
    bowl = "M80 52 C80 134 85 152 100 152 C115 152 120 134 120 52 Z"
    return {
        "outline": [bowl, "M100 152 L100 214",
                    "M74 216 C74 207 126 207 126 216 C126 223 74 223 74 216 Z"],
        "fill": bowl, "top": 52.0, "bottom": 152.0,
        "rim": (80.0, 120.0, 52.0), "wide": False,
    }


def wine():
    bowl = "M64 70 C64 136 80 154 100 154 C120 154 136 136 136 70 Z"
    return {
        "outline": [bowl, "M100 154 L100 214",
                    "M72 216 C72 207 128 207 128 216 C128 223 72 223 72 216 Z"],
        "fill": bowl, "top": 70.0, "bottom": 154.0,
        "rim": (64.0, 136.0, 70.0), "wide": False,
    }


def rocks():
    """Squat and heavy. The first pass drew a tumbler as tall as a highball,
    so a Negroni and a Dark and Stormy arrived in the same glass."""
    body = f"M56 140 L60 {FLOOR} L140 {FLOOR} L144 140 Z"
    return {"outline": [body], "fill": body, "top": 140.0, "bottom": FLOOR,
            "rim": (56.0, 144.0, 140.0), "wide": False}


def highball():
    body = f"M70 48 L75 {FLOOR} L125 {FLOOR} L130 48 Z"
    return {"outline": [body], "fill": body, "top": 48.0, "bottom": FLOOR,
            "rim": (70.0, 130.0, 48.0), "wide": False}


def shot():
    body = f"M76 168 L80 {FLOOR} L120 {FLOOR} L124 168 Z"
    return {"outline": [body], "fill": body, "top": 168.0, "bottom": FLOOR,
            "rim": (76.0, 124.0, 168.0), "wide": False}


def mug():
    body = f"M68 110 L72 {FLOOR} L128 {FLOOR} L132 110 Z"
    handle = "M132 142 C160 142 160 192 132 192"
    return {"outline": [body, handle], "fill": body, "top": 110.0,
            "bottom": FLOOR, "rim": (68.0, 132.0, 110.0), "wide": False}


def beer():
    body = f"M68 52 L78 {FLOOR} L122 {FLOOR} L132 52 Z"
    return {"outline": [body], "fill": body, "top": 52.0, "bottom": FLOOR,
            "rim": (68.0, 132.0, 52.0), "wide": False}


def snifter():
    bowl = "M62 108 C62 152 78 168 100 168 C122 168 138 152 138 108 Z"
    return {
        "outline": [bowl, "M100 168 L100 206",
                    "M74 208 C74 200 126 200 126 208 C126 215 74 215 74 208 Z"],
        "fill": bowl, "top": 108.0, "bottom": 168.0,
        "rim": (62.0, 138.0, 108.0), "wide": True,
    }


GLASSES = {
    "coupe": coupe, "martini": martini, "flute": flute, "wine": wine,
    "rocks": rocks, "highball": highball, "shot": shot, "mug": mug,
    "beer": beer, "snifter": snifter,
}


# ---------------------------------------------------------------------------
# Garnish. Small, because at the size a phone shows this it is a silhouette.
# ---------------------------------------------------------------------------

def wheel(x, y, colour, r=17):
    """A citrus wheel, hung on the rim."""
    spokes = "".join(
        f'<path d="M{x} {y} L{x + r * 0.78 * c:.1f} {y + r * 0.78 * s:.1f}"/>'
        for c, s in ((1, 0), (0.5, 0.87), (-0.5, 0.87), (-1, 0),
                     (-0.5, -0.87), (0.5, -0.87))
    )
    return (f'<g stroke="{colour}" stroke-width="2.4" fill="none">'
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{colour}" '
            f'fill-opacity="0.22"/>{spokes}</g>')


def twist(x, y, colour):
    return (f'<path d="M{x} {y} c14 -6 22 4 14 12 c-8 8 -20 2 -16 -8" '
            f'stroke="{colour}" stroke-width="3" fill="none" '
            f'stroke-linecap="round"/>')


def olive(x, y, colour="#9aa86a"):
    return (f'<g><path d="M{x} {y - 26} L{x} {y}" stroke="{GLASS}" '
            f'stroke-width="2"/><ellipse cx="{x}" cy="{y}" rx="9" ry="11" '
            f'fill="{colour}"/><circle cx="{x}" cy="{y}" r="3.4" '
            f'fill="#c0392b"/></g>')


def cherry(x, y):
    return (f'<g><path d="M{x} {y - 24} q6 12 0 18" stroke="{GLASS}" '
            f'stroke-width="2" fill="none"/>'
            f'<circle cx="{x}" cy="{y}" r="9" fill="#8e2b3f"/></g>')


def leaves(x, y, colour="#7f9a4e"):
    return (f'<g fill="{colour}">'
            f'<path d="M{x} {y} c-16 -4 -22 -18 -8 -24 c12 -4 16 12 8 24 Z"/>'
            f'<path d="M{x + 4} {y + 2} c16 -6 24 6 12 14 c-10 6 -18 -4 -12 -14 Z"/>'
            f'</g>')


def celery(x, y):
    return (f'<path d="M{x} {y} L{x + 6} {y - 62}" stroke="#7f9a4e" '
            f'stroke-width="7" stroke-linecap="round"/>')


def beans(x, y):
    return "".join(
        f'<ellipse cx="{x + i * 13}" cy="{y}" rx="6" ry="4.4" '
        f'fill="#d8c9a8" transform="rotate({-18 + i * 14} {x + i * 13} {y})"/>'
        for i in range(3)
    )


def wedge(x, y, colour):
    return (f'<path d="M{x} {y} a19 19 0 0 1 19 19 Z" fill="{colour}" '
            f'fill-opacity="0.5" stroke="{colour}" stroke-width="2.2"/>')


# Hung on the rim the shape declares, not at coordinates that happen to suit
# one glass: the first pass pinned every garnish at (140, 92), so a lime sat
# in mid-air beside a rocks glass and inside the bowl of a coupe.
GARNISH = {
    "lime": lambda sh: wheel(*rim_point(sh), "#8fae4e"),
    "lemon": lambda sh: wheel(*rim_point(sh), "#ccb44e"),
    "orange": lambda sh: wheel(*rim_point(sh), "#c8854a"),
    "grapefruit": lambda sh: wheel(*rim_point(sh), "#c2706a"),
    "lime-wedge": lambda sh: wedge(*rim_point(sh), "#8fae4e"),
    "lemon-twist": lambda sh: twist(*rim_point(sh), "#ccb44e"),
    "orange-twist": lambda sh: twist(*rim_point(sh), "#c8854a"),
    "olive": lambda sh: olive(100, sh["top"] + (sh["bottom"] - sh["top"]) * 0.45),
    "cherry": lambda sh: cherry(100, sh["top"] + (sh["bottom"] - sh["top"]) * 0.5),
    "mint": lambda sh: leaves(112, sh["rim"][2] - 10),
    "basil": lambda sh: leaves(112, sh["rim"][2] - 8),
    "pineapple": lambda sh: leaves(112, sh["rim"][2] - 12, "#b2a24e"),
    "celery": lambda sh: celery(110, sh["rim"][2] + 14),
    "beans": lambda sh: beans(88, sh["top"] + (sh["bottom"] - sh["top"]) * 0.22),
    "": lambda sh: "",
}


def rim_point(shape):
    """Where a wheel or a twist hangs: just inside the right lip."""
    _, right, y = shape["rim"]
    return right - 8, y + 2


# ---------------------------------------------------------------------------
# What each drink looks like. Only what is knowable: a classic has a settled
# glass and colour. Anything the bar invented and has not described is drawn
# from its category alone, and says so by being plain.
# ---------------------------------------------------------------------------

BY_CATEGORY = {
    "cocktail": ("rocks", "#b9763f", "", 1),
    "new-and-popular": ("rocks", "#b9763f", "", 1),
    "gin": ("rocks", "#dfe3d4", "", 1),
    "vodka": ("shot", "#e8ebe0", "", 0),
    "whiskey": ("rocks", "#b07a35", "", 1),
    "rum": ("rocks", "#9a5f2e", "", 1),
    "brandy": ("snifter", "#9c5a2a", "", 0),
    "tequila-and-mezcal": ("shot", "#e0e4d6", "", 0),
    "liquor": ("snifter", "#8d5a46", "", 0),
    "aperitivo": ("wine", "#b4593f", "", 0),
    "porto": ("wine", "#6d2f3a", "", 0),
    "wine": ("wine", "#d8cf9a", "", 0),
    "beer-and-cider": ("beer", "#c08a2e", "", 0),
    "cold-and-hot-beverage": ("highball", "#c9cdbc", "", 2),
    "non-alcohol-cocktail": ("highball", "#c2a85a", "lime", 3),
}

# glass, liquid, garnish, ice cubes
DRINKS = {
    "kyiv-mule-by-ukrainian-nemiroff-vodka": ("highball", "#c9a757", "lime", 3),
    "gin-basil-smash": ("rocks", "#8fa958", "basil", 2),
    "aviation-cocktail": ("coupe", "#a99ac4", "cherry", 0),
    "espresso-martini": ("martini", "#4a3120", "beans", 0),
    "tajin-margarita-cocktail": ("coupe", "#cfc06a", "lime", 0),
    "satyr-cola": ("highball", "#4a2d22", "", 3),
    "negroni": ("rocks", "#9e3524", "orange", 1),
    "new-york-sour": ("rocks", "#b4703a", "lemon-twist", 1),
    "slava-ukraini-shot": ("shot", "#2f6fb5", "", 0),
    "dark-and-stormy": ("highball", "#8a5330", "lime", 3),
    "bee-s-knees": ("coupe", "#d2ad4e", "lemon-twist", 0),
    "adriatico-amaretto-sweet-and-sour": ("rocks", "#b8803f", "lemon", 2),
    "sidecar-by-martell-cognac": ("coupe", "#c08a42", "orange-twist", 0),
    "skinny-bitch-by-nemiroff-delikat": ("highball", "#dfe4d8", "lime", 3),
    "el-presidente": ("coupe", "#c08159", "orange-twist", 0),
    "bloody-mary": ("highball", "#9c3a2c", "celery", 2),
    "salty-dog-by-nemiroff-delikat": ("highball", "#cf8a6c", "grapefruit", 3),
    "bergamot-dry-martini-by-italicus": ("martini", "#dde2cf", "lemon-twist", 0),
    "pisco-sour": ("coupe", "#e3dcc4", "", 0),
    "yellow-negroni": ("rocks", "#c9a93f", "lemon-twist", 1),
    "caipirinha": ("rocks", "#9cb060", "lime-wedge", 4),
    "bitter-giuseppe": ("rocks", "#8e3a2f", "lemon-twist", 1),
    "paloma": ("highball", "#cf8a6c", "grapefruit", 3),
    "french75": ("flute", "#ddc877", "lemon-twist", 0),
    "dolce-amaro-bittersweet": ("rocks", "#a4512f", "orange-twist", 1),
    "last-word": ("coupe", "#9fb173", "cherry", 0),
    "green-deacon": ("highball", "#89a85a", "mint", 3),
    "breakfast-martini": ("martini", "#c89248", "orange-twist", 0),
    "pinnaple-daiquiri": ("coupe", "#cfc077", "pineapple", 0),
    "mezcalita-vida": ("rocks", "#a8b878", "lime", 1),
    "all-shot": ("shot", "#b98a3f", "", 0),
    "skiny-beatch": ("highball", "#dfe4d8", "lime", 3),
    "pilsner-urquell-0-33l": ("beer", "#c9952e", "", 0),
    "coca-cola": ("highball", "#4a2d22", "", 3),
    "coffe-tea": ("mug", "#6b4a2c", "", 0),
    "tomas-henry-tonic-100ml": ("highball", "#dfe4d8", "", 3),
    "tomas-henry-tonic-botle": ("highball", "#dfe4d8", "", 3),
    "jaume-serra-cava-brut-200-ml-spain": ("flute", "#ddd49a", "", 0),
}


# ---------------------------------------------------------------------------
# Putting one together
# ---------------------------------------------------------------------------

def ice_cubes(shape, count, seed):
    """Cubes floating at the top of the liquid, clipped to the glass."""
    if not count:
        return ""
    top, bottom = shape["top"], shape["bottom"]
    span = max(bottom - top, 1)
    cubes = []
    for i in range(count):
        # Arranged, not random: the same drink has to draw the same twice.
        across = 0.5 + 0.34 * (((i + seed) % 3) - 1)
        down = 0.18 + 0.2 * (i % 3)
        x = 62 + across * 76
        y = top + down * span
        tilt = -20 + 17 * ((i + seed) % 3)
        cubes.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="26" height="26" rx="4" '
            f'fill="none" stroke="{GLASS}" stroke-opacity="0.55" '
            f'stroke-width="{HAIRLINE}" '
            f'transform="rotate({tilt} {x + 13:.1f} {y + 13:.1f})"/>'
        )
    return "".join(cubes)


def readable(colour: str) -> tuple:
    """A tint and a colour that still read on paper.

    A cream sour or a clear tonic at the same transparency as a Negroni came
    out as nothing at all: #e3dcc4 over #f3f3ee is a difference of four
    percent. Pale drinks are drawn stronger and a shade deeper, which is what
    a hand drawing them would do.
    """
    r, g, b = (int(colour[1 + i * 2:3 + i * 2], 16) for i in range(3))
    light = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    if light < 0.72:
        return TINT, colour
    # Pulled towards the ink, by how pale it is.
    pull = min(0.42, (light - 0.72) * 1.6)
    mix = lambda c, ink: int(round(c * (1 - pull) + ink * pull))
    deeper = "#%02x%02x%02x" % (mix(r, 0x16), mix(g, 0x21), mix(b, 0x0b))
    return min(0.82, TINT + (light - 0.72) * 0.9), deeper


def svg_for(slug: str, glass: str, liquid: str, garnish: str, ice: int) -> str:
    shape = GLASSES[glass]()
    top, bottom = shape["top"], shape["bottom"]
    # A shallow bowl is filled nearly to the rim; a tall glass is not.
    level = top + (bottom - top) * (0.14 if shape["wide"] else 0.26)
    clip = f"clip-{slug}"
    tint, liquid = readable(liquid)

    outline = "".join(
        f'<path d="{d}" fill="none" stroke="{GLASS}" stroke-width="{STROKE}" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        for d in shape["outline"]
    )
    seed = sum(ord(c) for c in slug)

    # Cropped to where the glassware actually is. The full 200x260 board left
    # a quarter of every thumbnail empty above a shot glass, which made the
    # rows of the menu tall and airy and the page half as long again. The
    # floor stays put, so every glass still stands on one line.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 38 200 206" width="200" height="206">
  <defs>
    <clipPath id="{clip}"><path d="{shape['fill']}"/></clipPath>
    <linearGradient id="g-{slug}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{liquid}" stop-opacity="{tint:.2f}"/>
      <stop offset="1" stop-color="{liquid}" stop-opacity="{min(0.92, tint + 0.12):.2f}"/>
    </linearGradient>
  </defs>
  <g clip-path="url(#{clip})">
    <rect x="40" y="{level:.1f}" width="120" height="{bottom - level + 4:.1f}"
          fill="url(#g-{slug})"/>
    {ice_cubes(shape, ice, seed)}
  </g>
  <!-- The surface, so the liquid reads as a volume and not a block. -->
  <path d="M{54 if shape['wide'] else 70} {level:.1f} L{146 if shape['wide'] else 130} {level:.1f}"
        stroke="{GLASS}" stroke-opacity="0.5" stroke-width="{HAIRLINE}"
        clip-path="url(#{clip})"/>
  {outline}
  {GARNISH.get(garnish, GARNISH[''])(shape)}
</svg>"""


def recipe(slug: str, category: str):
    if slug in DRINKS:
        return DRINKS[slug]
    return BY_CATEGORY.get(category, ("rocks", "#b9763f", "", 1))


def render(svgs: dict, keep_svg: bool) -> None:
    """One browser, every drink, two sizes each."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is required: pip install playwright && playwright install chromium")
    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    stage = ROOT / ".drink-stage"
    stage.mkdir(exist_ok=True)
    for slug, markup in svgs.items():
        (stage / f"{slug}.svg").write_text(markup)
        if keep_svg:
            (OUT / f"{slug}.svg").write_text(markup)

    port = 8799
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=stage, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1).read(1)
            break
        except Exception:
            time.sleep(0.1)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_context(
                viewport={"width": 200, "height": 206}, device_scale_factor=4
            ).new_page()
            for i, slug in enumerate(svgs, 1):
                page.goto(f"http://127.0.0.1:{port}/{slug}.svg",
                          wait_until="networkidle")
                raw = page.locator("svg").screenshot(
                    type="png", omit_background=True
                )
                master = stage / f"{slug}.png"
                master.write_bytes(raw)
                image = Image.open(master).convert("RGBA")
                for size in SIZES:
                    copy = image.resize((size, round(size * 206 / 200)),
                                        Image.LANCZOS)
                    name = f"{slug}.webp" if size == SIZES[0] else f"{slug}-{size}.webp"
                    copy.save(OUT / name, "WEBP", quality=88, method=6)
                if i % 20 == 0:
                    print(f"  {i}/{len(svgs)}")
            browser.close()
    finally:
        server.terminate()
        server.wait()
        for leftover in stage.iterdir():
            leftover.unlink()
        stage.rmdir()


def main() -> int:
    menu = json.loads((ROOT / "data" / "menu.json").read_text())
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")]
    keep_svg = "--svg" in sys.argv

    svgs, drawn_from_category = {}, []
    for product in menu["products"]:
        slug = product["slug"]
        if wanted and slug not in wanted:
            continue
        glass, liquid, garnish, ice = recipe(slug, product["category"])
        if slug not in DRINKS:
            drawn_from_category.append(slug)
        svgs[slug] = svg_for(slug, glass, liquid, garnish, ice)

    if not svgs:
        sys.exit(f"nothing matched {wanted}")

    print(f"drawing {len(svgs)} drinks")
    render(svgs, keep_svg)
    print(f"  {len(svgs)} written to {OUT.relative_to(ROOT)}")
    if drawn_from_category:
        print(f"  {len(drawn_from_category)} drawn from their category alone, "
              "having no entry of their own")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
