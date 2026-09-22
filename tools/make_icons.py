#!/usr/bin/env python3
"""Generate the favicon, touch icon and share card from the brand marks.

Generated rather than drawn so they cannot drift away from the logo. Every page
gets the same 1200x630 card for now; per-page cards come when there is
photography to put on them.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
GREEN, GOLD, PINK, MAROON = "#112103", "#d3bd8d", "#ff95ff", "#260408"


def inner(name):
    """Strip the wrapper so a mark can be nested inside another SVG."""
    svg = (BRAND / f"{name}.svg").read_text()
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    body = re.sub(r"^<svg[^>]*>|</svg>$", "", svg.strip())
    body = re.sub(r"<title>.*?</title>", "", body)
    return box, body


def main():
    # Favicon: the mask from the motif is too fine at 16px, so the icon is the
    # satyr silhouette, which still reads as a shape at that size.
    box, body = inner("satyr")
    x, y, w, h = (float(v) for v in box.split())
    pad = w * 0.12
    (BRAND / "favicon.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x - pad} {y} {w + pad * 2} {h}">'
        f'<rect x="{x - pad}" y="{y}" width="{w + pad * 2}" height="{h}" fill="{GREEN}"/>'
        f'<g fill="{GOLD}">{body}</g></svg>'
    )

    # Share card, 1200x630.
    mbox, mbody = inner("wordmark-stacked")
    mx, my, mw, mh = (float(v) for v in mbox.split())
    scale = 620 / mw
    tx, ty = (1200 - mw * scale) / 2, 300 - mh * scale / 2

    fbox, fbody = inner("motif")
    fx, fy, fw, fh = (float(v) for v in fbox.split())
    fscale = 300 / fw
    ftx, fty = (1200 - fw * fscale) / 2, 96

    share = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" '
        'viewBox="0 0 1200 630">'
        f'<rect width="1200" height="630" fill="{GREEN}"/>'
        f'<g transform="translate({ftx} {fty}) scale({fscale})" fill="{PINK}">{fbody}</g>'
        f'<g transform="translate({tx} {ty + 60}) scale({scale})" fill="{GOLD}">{mbody}</g>'
        f'<text x="600" y="566" text-anchor="middle" fill="{GOLD}" opacity="0.65" '
        'font-family="Georgia, serif" font-style="italic" font-size="30">'
        "Bottle shop &#183; Nove Mesto, Prague</text>"
        "</svg>"
    )
    (BRAND / "share.svg").write_text(share)

    # Rasterise with the browser that is already installed for screenshots.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not available — share.png and apple-touch-icon.png skipped")
        return

    # A lone SVG favicon leaves older browsers, Windows and pinned tabs with
    # nothing, so the raster sizes are generated from the same source.
    jobs = [
        ("share.svg", "share.png", 1200, 630),
        ("favicon.svg", "apple-touch-icon.png", 180, 180),
        ("favicon.svg", "icon-512.png", 512, 512),
        ("favicon.svg", "icon-192.png", 192, 192),
        ("favicon.svg", "favicon-32.png", 32, 32),
        ("favicon.svg", "favicon-16.png", 16, 16),
    ]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for src, dest, w, h in jobs:
            # The SVG is embedded in an HTML shell: loading an .svg directly
            # gives a document with no <head> to style.
            svg = (BRAND / src).read_text()
            svg = re.sub(r"<svg", f'<svg width="{w}" height="{h}"', svg, count=1)
            shell = (
                "<!doctype html><meta charset=utf-8>"
                "<style>html,body{margin:0;padding:0;background:" + GREEN + "}"
                "svg{display:block}</style>" + svg
            )
            page = browser.new_page(viewport={"width": w, "height": h})
            page.set_content(shell)
            page.screenshot(path=str(BRAND / dest))
            page.close()
            print(f"  {dest}  {(BRAND / dest).stat().st_size / 1024:.1f} KB")
        browser.close()

    # A single .ico carrying both small sizes, for anything that still asks.
    try:
        from PIL import Image

        ico = BRAND / "favicon.ico"
        Image.open(BRAND / "favicon-32.png").save(
            ico, sizes=[(16, 16), (32, 32), (48, 48)]
        )
        print(f"  favicon.ico  {ico.stat().st_size / 1024:.1f} KB")
    except ImportError:
        print("Pillow not available — favicon.ico skipped")

    manifest = {
        "name": "Irony vs. Satyr",
        "short_name": "Irony vs. Satyr",
        "description": "A bottle shop in Nove Mesto, Prague.",
        "start_url": "./",
        "display": "minimal-ui",
        "background_color": GREEN,
        "theme_color": GREEN,
        "icons": [
            {"src": "assets/brand/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "assets/brand/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "assets/brand/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }
    (ROOT / "site.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n")
    print("  site.webmanifest")


if __name__ == "__main__":
    main()
