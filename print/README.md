# Printed pieces

Four things that carry a code into the room. All of them are generated:

```
python3 print/make.py            # all four
python3 print/make.py coaster    # just one
```

The PDFs and preview PNGs land in `print/out/`. Nothing here is drawn by
hand, so a change of address or of the menu URL is one edit and a re-run.

## What each one is

| Piece | Trim | Codes | For |
|---|---|---|---|
| `card.pdf` | 85.6 × 54 mm, CR80 | menu (front), review (back) | plastic card at the table |
| `business-card.pdf` | 85 × 55 mm | menu (front), review (back) | handed over |
| `coaster.pdf` | 95 mm round | menu and review, side by side | under the glass |
| `table-sticker.pdf` | 90 × 60 mm | menu | stuck to the table |

## Press specification

- **Bleed** 3 mm on every edge; the tint runs into it. Crop marks sit outside
  the trim on the rectangular pieces.
- **Coaster**: the magenta circle is the die line, not artwork. It is drawn at
  the trim, so the cutter takes it as the cut and it does not print.
- **Colour**: everything is built in RGB from the site's own tokens. Ask the
  printer to convert; the palette is near-neutral and survives it. Ink is
  `#16210b`, paper `#fbfaf7`.
- **Stock**: the card is PVC. The coaster asks for 1.2 mm pulpboard, uncoated
  — a gloss coaster throws the bar's light straight back at the camera and is
  the one surface where that matters.
- **Fonts** are embedded, subset. They are converted at build time from the
  site's own webfonts in `assets/fonts/`, so print and screen cannot drift.

## The codes

Every code is read back from the finished PDF before the run is called good:
each one is cropped where it was drawn and decoded on its own. Sweeping the
page instead would let the coaster's second code pass unverified. The run
prints the density each code needed and fails on anything under 15 mm.

The review code is built from a place id derived from the bar's own Maps
link. The derivation was checked byte for byte, but Google's consent wall
stopped it being confirmed in a browser.

**Scan the review code off a printed proof before the full run.** That is
worth doing for any printed code, derived or not — a thousand cards is the
wrong moment to find out.
