#!/usr/bin/env python3
"""Generate a 1200x630 share card per page.

One card for a whole site means a link to a particular bottle shows the same
picture as a link to the shop. These are built from the same data the pages
are, in the brand's dark half — which is also what `theme-color` is set to, so
the card and the browser chrome agree.

    python3 tools/make_share_cards.py

Writes assets/share/<slug>.png. Re-run after changing the catalogue.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "assets" / "share"

GREEN, GOLD, PINK = "#112103", "#d3bd8d", "#ff95ff"


def mark_inner(name: str) -> tuple[str, str]:
    """viewBox and body of a brand mark, ready to nest in another SVG."""
    svg = (BRAND / f"{name}.svg").read_text()
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    body = re.sub(r"^<svg[^>]*>|</svg>$", "", svg.strip())
    body = re.sub(r"<title>.*?</title>", "", body)
    return box, body


def inline_mark(name: str, height: int, colour: str) -> str:
    box, body = mark_inner(name)
    w, h = (float(v) for v in box.split()[2:])
    return (
        f'<svg viewBox="{box}" height="{height}" width="{height * w / h:.0f}" '
        f'fill="{colour}">{body}</svg>'
    )


def card_html(eyebrow: str, title: str, meta: str, figure: str) -> str:
    display = (FONTS / "cormorant-garamond-normal-500-latin.woff2").as_uri()
    body_font = (FONTS / "eb-garamond-italic-400800-latin.woff2").as_uri()
    return f"""<!doctype html><meta charset="utf-8"><style>
@font-face {{ font-family: 'D'; src: url('{display}') format('woff2'); font-display: block; }}
@font-face {{ font-family: 'B'; src: url('{body_font}') format('woff2'); font-style: italic; font-display: block; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; width: 1200px; height: 630px; }}
body {{ background: {GREEN}; color: {GOLD}; display: flex; flex-direction: column;
        justify-content: space-between; padding: 64px 72px; overflow: hidden; }}
.top {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 40px; }}
.eyebrow {{ font-family: 'B', serif; font-size: 22px; letter-spacing: .28em;
            text-transform: uppercase; color: #9aa683; }}
h1 {{ font-family: 'D', serif; font-weight: 500; font-size: {"76px" if len(title) > 26 else "104px"};
      line-height: .98; margin: 0; max-width: 15ch; letter-spacing: -.015em; }}
.meta {{ font-family: 'B', serif; font-style: italic; font-size: 30px; color: #c4b58e; margin-top: 22px; }}
.foot {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 40px; }}
.rule {{ flex: 1; height: 1px; background: rgba(211,189,141,.28); margin-bottom: 14px; }}
svg {{ display: block; }}
</style>
<div class="top">
  <div class="eyebrow">{eyebrow}</div>
  {inline_mark("wordmark-stacked", 56, GOLD)}
</div>
<div>
  <h1>{title}</h1>
  <div class="meta">{meta}</div>
</div>
<div class="foot">
  {figure}
  <div class="rule"></div>
  <div class="eyebrow">Nove Mesto, Prague</div>
</div>"""


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is required: pip install playwright")

    site = json.loads((ROOT / "data" / "site.json").read_text())
    cat = json.loads((ROOT / "data" / "catalogue.json").read_text())
    cats = {c["slug"]: c["name"] for c in cat["categories"]}

    motif = inline_mark("motif", 70, GOLD)
    satyr = inline_mark("satyr", 150, GOLD)

    cards = [
        ("index", "Bottle shop", site["name"], site["tagline"] + " · the whole shelf, listed", satyr),
        ("about", "Who we are", "Two ways to hold a drink.", "A bottle shop in Nove Mesto", satyr),
        ("visit", "Find us", site["address"]["street"], f"{site['address']['postal']} {site['address']['district']}, {site['address']['city']}", motif),
    ]
    for p in cat["products"]:
        cards.append((
            f"shop-{p['slug']}",
            cats[p["category"]],
            p["name"],
            f"{p['volume']} ml · {p['abv']}% · {p['price']:,} CZK".replace(",", " "),
            motif,
        ))

    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        for slug, eyebrow, title, meta, figure in cards:
            page.set_content(card_html(eyebrow, title, meta, figure))
            page.wait_for_timeout(120)
            page.screenshot(path=str(OUT / f"{slug}.png"))
        browser.close()

    total = sum(f.stat().st_size for f in OUT.glob("*.png")) / 1024
    print(f"wrote {len(cards)} share cards to {OUT.relative_to(ROOT)} ({total:.0f} KB total)")


if __name__ == "__main__":
    main()
