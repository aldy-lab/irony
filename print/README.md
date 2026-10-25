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
| `coaster.pdf` | 95 mm round, 2 faces | menu, review | under the glass |
| `business-card.pdf` | 85 × 55 mm | menu (back) | handed over |
| `table-sticker.pdf` | 90 × 60 mm | menu | stuck to the table |

## The look

One language across all four: the brand's dark green as the ground, gold for
the type and the hairlines, and every code on a gold plate with its modules
in green.

**The plate is the gold one and the modules are the green ones, never the
other way round.** A code is specified as dark modules on a light field;
reversed, it is a different thing that some readers happen to tolerate.
Tested across five shades of gold — every one read as green-on-gold, every
one failed as gold-on-green, at 300 through 900 dpi. Green on this brass
measures 6.8:1, well clear of what print needs after dot gain.

The corner marks stay square. Rounding them cost real reliability: the same
artwork went from reading at 300 dpi to needing 450 and 600. Round modules in
the body of the code cost nothing.

## Press specification

- **Bleed** 3 mm on every edge, with the ground painted into it, and a further
  5 mm of bare paper outside that for the cut marks to live on.
- **Coaster**: the magenta circle is the die line, not artwork. It is drawn at
  the trim, so the cutter takes it as the cut and it does not print.
- **Colour**: built in RGB from the site's own tokens — ink `#16210b`, gold
  `#b08d2e`, plate `#c3a24a`, paper `#fbfaf7`. Ask the printer to convert.
  The gold is specified to print as ink; if it is ever run as a foil, the
  plate under each code must stay a flat, matte light tone, because a mirror
  finish returns the phone's own torch straight down the lens.
- **Stock**: the card is PVC. The coaster asks for 1.2 mm pulpboard, uncoated
  — a gloss coaster throws the bar's light back at the camera and is the one
  surface where that matters.
- **Fonts** are embedded, subset. They are converted at build time from the
  site's own webfonts in `assets/fonts/`, so print and screen cannot drift.

## What the run checks

- **Every code, where it was drawn.** Each is cropped from the finished PDF at
  its own rectangle and decoded alone. Sweeping the page instead let the
  coaster's second code pass unverified for a whole build. The run prints the
  density each one needed and fails anything under 15 mm.
- **Every line of type and every drawing**, against the code plates and
  against the area the piece allows — the trim less 4 mm, or for the coaster
  the inside of its ring. This is not a nicety: two lines on the card were
  running underneath a gold plate and the preview did not make it obvious.
- **Every character**, against the font files that have to set it. A line
  mixing Czech accents with Cyrillic needs three subsets; set from one, the
  rest print as empty boxes and nothing complains.

## The codes

They point at this site, not at Google: `/menu/` and `/r/`. `/r/` redirects.

That indirection is the point. A printed code cannot be edited, and the place
id behind the review link was derived from the bar's own Maps URL and never
confirmed in a browser. Through `/r/`, a wrong id is one line in
`data/site.json` and a rebuild, instead of a reprint. Blank that line and
`/r/` is not built, `build.py` says so, and this script refuses to draw a
review code at all. `tools/check.py` asserts `/r/` still answers and still
redirects where the config says.

It also halves the code: straight at Google is 79 characters and 49 modules;
through `/r/` it is 35 and 33.

**Scan the review code off a printed proof before the full run.** That is
worth doing for any printed code, derived or not — a thousand coasters is the
wrong moment to find out.
