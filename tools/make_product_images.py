#!/usr/bin/env python3
"""Make responsive variants of the product photographs.

    python3 tools/make_product_images.py

Drop a photograph into assets/products/ named after the product's slug — any
of .jpg, .jpeg, .png or .webp — and this writes <slug>-400.webp, -800.webp and
-1200.webp beside it. build.py picks the variants up automatically and emits a
srcset, so a phone showing a 160px card does not download a 1200px file.

The frame is square and the image is cropped to fill it, so the variants are
cropped square here too rather than being squashed by CSS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "products"
WIDTHS = (400, 800, 1200)
SOURCE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")


def source_for(slug: str) -> Path | None:
    """The original for a slug, ignoring the variants this script writes."""
    for suffix in SOURCE_SUFFIXES:
        candidate = SRC / f"{slug}{suffix}"
        if candidate.exists():
            return candidate
    return None


def square(img):
    """Centre-crop to a square, the shape the frame actually is."""
    w, h = img.size
    if w == h:
        return img
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def main():
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow is required: pip install pillow")

    catalogue = json.loads((ROOT / "data" / "catalogue.json").read_text())
    SRC.mkdir(parents=True, exist_ok=True)

    made, missing = 0, []
    tints_path = SRC / "tints.json"
    tints = json.loads(tints_path.read_text()) if tints_path.exists() else {}
    for product in catalogue["products"]:
        slug = product["slug"]
        source = source_for(slug)
        if not source:
            if product.get("image"):
                missing.append(slug)
            continue

        with Image.open(source) as img:
            img = square(img.convert("RGB"))
            for width in WIDTHS:
                if img.width < width and width != WIDTHS[0]:
                    # Never upscale past the original; the smallest is always
                    # written so there is something for a phone.
                    continue
                resized = img.resize((width, width), Image.LANCZOS)
                resized.save(SRC / f"{slug}-{width}.webp", "WEBP", quality=82, method=6)
                made += 1
                # AVIF where Pillow can write it; the browser falls back to
                # WebP on its own if the file is not there.
                try:
                    resized.save(SRC / f"{slug}-{width}.avif", "AVIF", quality=62)
                    made += 1
                except Exception:
                    pass
            # Average colour, for the frame to hold while the photo decodes.
            small = img.resize((1, 1), Image.LANCZOS)
            tints[slug] = "#%02x%02x%02x" % small.getpixel((0, 0))
        print(f"  {slug}: {source.name} -> variants + tint {tints[slug]}")

    if missing:
        print("\n  ! named in catalogue.json but no file found in assets/products/:")
        for slug in missing:
            print(f"      {slug}")

    if tints:
        tints_path.write_text(json.dumps(tints, indent=2, sort_keys=True) + "\n")

    if not made:
        print("no photographs found in assets/products/ — nothing to do")
        print("name each one after its product slug, e.g. single-malt-10.jpg")
    else:
        print(f"\nwrote {made} variants. Run build.py to pick them up.")


if __name__ == "__main__":
    main()
