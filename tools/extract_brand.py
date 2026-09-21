#!/usr/bin/env python3
"""Lift the Irony vs. Satyr marks out of the brand file as tight, recolourable SVGs.

The source is pres_Irony_vs_Satyr.ai — all vector, no rasters. Every mark comes
out as one path with fill="currentColor", so CSS colours it gold, pink or green
without shipping a second file.
"""
import sys
from pathlib import Path

import pymupdf

SRC = Path("/Users/aldy/Downloads/pres_Irony_vs_Satyr.ai")
OUT = Path(__file__).resolve().parent.parent / "assets" / "brand"


def fmt(n):
    """Trim coordinates to 2dp — halves the file with no visible change."""
    s = f"{n:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def path_data(drawing, ox, oy):
    """Serialise one PyMuPDF drawing into SVG path data."""
    out, cur = [], None
    for item in drawing["items"]:
        op = item[0]
        if op == "l":
            p1, p2 = item[1], item[2]
            if cur != (p1.x, p1.y):
                out.append(f"M{fmt(p1.x - ox)} {fmt(p1.y - oy)}")
            out.append(f"L{fmt(p2.x - ox)} {fmt(p2.y - oy)}")
            cur = (p2.x, p2.y)
        elif op == "c":
            p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
            if cur != (p1.x, p1.y):
                out.append(f"M{fmt(p1.x - ox)} {fmt(p1.y - oy)}")
            out.append(
                f"C{fmt(p2.x - ox)} {fmt(p2.y - oy)} {fmt(p3.x - ox)} {fmt(p3.y - oy)} "
                f"{fmt(p4.x - ox)} {fmt(p4.y - oy)}"
            )
            cur = (p4.x, p4.y)
        elif op == "re":
            r = item[1]
            out.append(
                f"M{fmt(r.x0 - ox)} {fmt(r.y0 - oy)}H{fmt(r.x1 - ox)}"
                f"V{fmt(r.y1 - oy)}H{fmt(r.x0 - ox)}Z"
            )
            cur = None
        elif op == "qu":
            q = item[1]
            pts = [q.ul, q.ur, q.lr, q.ll]
            out.append("M" + " L".join(f"{fmt(p.x - ox)} {fmt(p.y - oy)}" for p in pts) + "Z")
            cur = None
    return "".join(out) + "Z"


def build(page, drawings, name, title):
    box = pymupdf.Rect(drawings[0]["rect"])
    for d in drawings:
        box |= d["rect"]
    pad = 1.0
    ox, oy = box.x0 - pad, box.y0 - pad
    w, h = box.width + pad * 2, box.height + pad * 2

    # Split by fill rule so holes in the figures survive the merge.
    buckets = {True: [], False: []}
    for d in drawings:
        buckets[bool(d.get("even_odd"))].append(path_data(d, ox, oy))

    paths = []
    for even_odd, chunks in buckets.items():
        if not chunks:
            continue
        rule = ' fill-rule="evenodd"' if even_odd else ""
        paths.append(f'<path{rule} d="{"".join(chunks)}"/>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" '
        f'fill="currentColor" role="img" aria-label="{title}">'
        f"<title>{title}</title>{''.join(paths)}</svg>"
    )
    dest = OUT / f"{name}.svg"
    dest.write_text(svg)
    print(f"  {name}.svg  {len(svg) / 1024:6.1f} KB  viewBox 0 0 {fmt(w)} {fmt(h)}")
    return box


def inside(drawing, box):
    return pymupdf.Rect(box).contains(drawing["rect"] + (0.5, 0.5, -0.5, -0.5))


def main():
    if not SRC.exists():
        sys.exit(f"brand source not found: {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(SRC)
    print(f"extracting from {SRC.name}")

    p1 = doc[0]
    d1 = p1.get_drawings()
    motif = [d for d in d1 if inside(d, (420, 170, 932, 442))]
    mark = [d for d in d1 if inside(d, (268, 452, 1086, 908))]
    # The stacked mark is two lines: "IRONY VS." over "SATYR".
    split = 690
    line1 = [d for d in mark if d["rect"].y1 <= split]
    line2 = [d for d in mark if d["rect"].y1 > split]

    build(p1, motif, "motif", "Irony vs. Satyr")
    build(p1, mark, "wordmark-stacked", "Irony vs. Satyr")
    build(p1, line1, "wordmark-line1", "Irony vs.")
    build(p1, line2, "wordmark-line2", "Satyr")

    p4 = doc[3]
    satyr = [d for d in p4.get_drawings() if inside(d, (766, 147, 1178, 906))]
    build(p4, satyr, "satyr", "The satyr")

    print(f"wrote {len(list(OUT.glob('*.svg')))} marks to {OUT}")


if __name__ == "__main__":
    main()
