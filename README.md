# Irony vs. Satyr

Bottle shop, Soukenicka 1756, Nove Mesto, Prague. Static site, no framework,
no build tooling beyond Python 3.

**Live:** https://aldy-lab.github.io/irony

---

## Running it

```sh
python3 build.py          # regenerate every page
python3 -m http.server 8731   # then open http://127.0.0.1:8731
```

`build.py` writes `index.html`, `shop.html`, `cart.html`, `about.html`,
`visit.html`, `404.html`, one page per product under `shop/`, plus
`sitemap.xml` and `robots.txt`. **Do not edit those files by hand** — they are
overwritten on every build. Edit `templates/` and `data/` instead.

The sitemap is generated from the same page list the pages are, which is the
only way it stays free of 404s.

---

## The one file you edit

`data/site.json` holds every pending go-live value: email, phone, maps link,
Instagram, the order form endpoint, analytics.

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
  `phone` or a social URL is filled in.
- **No order form endpoint.** The cart works, but checkout cannot submit. Add a
  Formspree-style endpoint to `commerce.order_form_endpoint` and the checkout
  form appears. Until then the cart page says how to order instead of showing a
  button that does nothing.

---

## How the shop works without a server

GitHub Pages is static, so there is no backend to take a card payment.

- The cart lives in `localStorage` and works entirely client-side.
- Checkout posts the order to the configured form endpoint as an **order
  request**. Payment and ID check happen at handover.
- A product may carry `"stripe_buy_button": "<Stripe Payment Link>"`, which adds
  a *Buy now with card* button to that product's page. Stripe hosts the payment
  page, so it still needs no backend. Without a link, the product is still
  orderable through the cart.

Selling alcohol in Czechia means verifying age at handover, not only on the
site. The age gate here is a first gate; `commerce.delivery_note` is the policy
line that appears at checkout and on every product page, and it is a legal
statement rather than decoration.

---

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
| Display | Expo Regular | Bodoni Moda |
| Body / italic | Arno Pro Italic | EB Garamond |

EB Garamond is a Garamond revival, which is the family Arno descends from, so
it is a genuine relative rather than a lookalike. Both are OFL and self-hosted
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
python3 build.py    # fails loudly on an unknown template token
```

Before shipping a change, the things worth re-checking are horizontal overflow
across the width range (not just at 1440), that the cart badge, filter, sort and
age gate still work, and that prices render identically in the HTML and in the
cart — `money()` exists in both `build.py` and `js/main.js` and they must agree.

## Easter egg

Type `satyr` on any page.
