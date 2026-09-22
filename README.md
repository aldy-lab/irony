# Irony vs. Satyr

Bottle shop, Soukenicka 1756, Nove Mesto, Prague. A **catalogue** of what is on
the shelf — nothing is sold through the site. Static, no framework, no build
tooling beyond Python 3.

Light ground: the brand deck carries both halves, gold and pink type on dark and
dark green type on light, and this site takes the light one. The dark half
survives in the footer, in the occasional inverted section, and after hours.

**Live:** https://aldy-lab.github.io/irony

---

## Running it

```sh
python3 build.py          # regenerate every page
python3 -m http.server 8731   # then open http://127.0.0.1:8731
```

`build.py` writes `index.html` (the catalogue itself), `about.html`,
`visit.html`, `404.html`, one page per bottle under `shop/`, plus
`sitemap.xml` and `robots.txt`. `shop.html` is written too, as a redirect: the
catalogue used to live there before it moved to the front page, and a link
shared in between should not land on a 404. **Do not edit those files by hand** — they are
overwritten on every build. Edit `templates/` and `data/` instead.

The sitemap is generated from the same page list the pages are, which is the
only way it stays free of 404s.

---

## The one file you edit

`data/site.json` holds every pending go-live value: email, phone, maps link,
Instagram, analytics.

**Fill a value in and the element switches on. Leave it `""` and the element is
removed from the page entirely**, along with any container it would have left
empty. There is no `href="#"` fallback anywhere in this repo, so the worst case
is a missing link, never a dead one.

`data/catalogue.json` holds the categories and the bottles.

---

## What is still blocked

`build.py` prints these on every build, so they cannot be forgotten:

- **All 20 products are placeholders.** They are deliberately generic — no real
  distillery is named anywhere, because listing a brand is claiming to stock it.
  Replace them with the real list (name, producer, volume, ABV, price, a line of
  copy) and delete the `"placeholder": true` line from each.
- **No product photography.** Cards are designed to work without it and fall
  back to the brand mark. Add `"image": "assets/products/x.webp"` to a product
  and its card grows a photo; leave it out and the card stays typographic.
- **No contact details.** The footer shows a holding line until `email`,
  `phone` or a social URL is filled in, and product pages show no enquiry
  button at all rather than one that goes nowhere.

---

## The front page is the catalogue

`index.html` opens on a short masthead — mark, one line, the satyr — and then
the filters and the full grid. The masthead is capped in height rather than
sized to the viewport the way a hero would be, and on a phone it drops the
figure and the flute entirely, because a brand block that fills the screen
hides the thing it is introducing. The filter bar is above the fold at every
size that was measured, down to a 664px-tall phone.

The header is the dark half of the brand, gold on green, and carries its own
colour tokens so it stays that way over a light page, an inverted section, or
the after-hours colourway.

## Filtering

Filters sit in a **left sidebar** rather than a bar across the top, so the grid
starts directly under the masthead instead of below 400px of controls, and the
filters stay in view while the list scrolls. On a phone the same panel
collapses behind one button carrying a count of how many filters are active,
which puts bottles on the first screen at every size measured.

The grid is rendered **statically at build time**, so it is crawlable and the
full list is readable with JavaScript off. The filters only narrow what is
already on the page:

- **Category** list with per-category counts, **search** (name, producer,
  category and tasting note), **price** band, **strength** band, **bottle
  size**, and **sort** beside the result count.
- Category counts come from the same data the grid does, so they cannot
  disagree with it.
- Bottle sizes are read from the data, so adding a 1 litre bottle adds its own
  filter option without the template being touched.
- Search text is lowercased once at build time into `data-search`, so filtering
  stays a substring test rather than work repeated on every keystroke.
- Every filter is written to the URL, so a narrowed view can be sent to someone
  and survives a reload.

Nothing is buyable anywhere: no cart, no checkout, no prices that imply a
transaction. A product page's only action is asking about the bottle, and that
button appears **only** when an email or phone is configured.

Selling alcohol means checking ID at the counter. The age gate here is a first
gate and `catalogue.availability_note` is the line that says so; it appears on
every product page and on Visit, and it is a statement of how the shop works
rather than decoration.

## Weight

Every mark is defined **once per page as an SVG sprite** and referenced with
`<use>`. Before that the motif was inlined twenty-two times on the catalogue
page — 40 KB of identical path data each — which made the front page 1.13 MB
and the twenty product pages 6.6 MB between them. They are now 188 KB and
3.4 MB.

What remains is the sprite itself, 163 KB raw and 66 KB gzipped, of which the
satyr is 114 KB. It cannot be moved to an external file without losing
`currentColor`, which is what lets one mark be gold on the header and muted on
a card. Moving these to CSS `mask-image` would cache them across pages and cut
the HTML to a few KB — worth doing if the page weight ever matters more than
the simplicity.

## Brand assets

`assets/brand/*.svg` are extracted from `pres_Irony_vs_Satyr.ai` by
`tools/extract_brand.py`. They are real vector outlines from the source file —
not traced, not redrawn — each written as a single path with
`fill="currentColor"`, so CSS recolours them gold, pink or green without
shipping a second file.

```sh
python3 tools/extract_brand.py   # re-extract if the .ai changes
python3 tools/make_icons.py      # favicon, touch icon, share card
```

The wordmark ships as outlines, so it is typographically exact regardless of
which fonts are licensed.

## Fonts

**Expo (Parachute) and Arno Pro (Adobe) are not licensed for web use here**, so
the site ships self-hosted substitutes:

| Role | Brand font | Shipped |
|---|---|---|
| Display | Expo Regular | Cormorant Garamond |
| Body / italic | Arno Pro Italic | EB Garamond |

EB Garamond is a Garamond revival, which is the family Arno descends from, so
it is a genuine relative rather than a lookalike.

The display face was chosen by setting the candidates beside the outlined
wordmark and looking. **Italiana** matches Expo's proportions best — narrow,
high contrast, flared stems — but it has no lining figures, and `lnum` cannot
conjure them: it renders "10 Years" as "Io Years", which a catalogue full of
ages, strengths and volumes cannot carry. **Bodoni Moda**, shipped first, has
sound figures but is far wider and rounder than the wordmark. **Cormorant
Garamond** is narrower and sharper than the Bodoni, has proper figures, and
being a Garamond it is of a piece with the text face. Headings and prices are
set at weight 500, since Cormorant's 400 is light enough to look anaemic.

Figures are pinned to `lining-nums` on `body`, and `lining-nums tabular-nums`
on prices, so a swapped face can never quietly turn a price into old-style. Both are OFL and self-hosted
(`tools/fetch_fonts.py`), which also keeps the Google Fonts IP disclosure out
of the privacy story.

Swapping in a licensed Expo webfont is two lines: drop the files into
`assets/fonts/`, add the `@font-face` rules, and change `--display` in
`css/main.css`.

## Analytics

Off. `analytics.plausible_domain` is blank, so no third-party request is made,
there is no cookie banner and there is nothing to disclose. Switching it on
requires a privacy policy — which this site does not yet have.

---

## Checks

```sh
python3 build.py && python3 tools/check.py
```

`tools/check.py` starts its own server, drives a real browser and exits
non-zero on failure: every filter and combination, a filtered URL surviving a
reload, five phone sizes (two-column grid, filters above the fold, 44px tap
targets, 16px inputs, page height), horizontal overflow over 85 width/page
combinations, and no grid left with a partly-filled last row.

Three habits it encodes, each from a bug that shipped here:

- **Assert pixels, not properties.** `hidden` is outranked by any element with
  its own `display`, so a filter reported "4 bottles" while all twenty stayed
  on screen.
- **Source order decides between equal specificity.** A `@media` block placed
  above the rules it overrides is inert and still looks right in the diff —
  that happened three times in one sitting, to the mobile card, the filter bar
  and the chip/select swap. The check asserts computed values for that reason.
- **Emulate the device.** macOS Chrome clamps a headless window to 500px, so a
  390px screenshot is silently fake.

## Easter egg

Type `satyr` on any page — the site flips to the dark half of the brand.
