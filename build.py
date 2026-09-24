#!/usr/bin/env python3
"""Build the Irony vs. Satyr shop.

Every page is generated from templates/ plus data/, so the header, footer and
brand marks cannot drift apart across pages. sitemap.xml comes from the same
page list the pages do, which is the only way it stays honest.

    python3 build.py

Config lives in data/site.json. A blank value there removes the element that
would have used it rather than shipping a dead link.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TPL = ROOT / "templates"
DATA = ROOT / "data"
BRAND = ROOT / "assets" / "brand"
SHOP_DIR = ROOT / "shop"
STAMPS = DATA / "lastmod.json"

warnings: list[str] = []

# Placeholder markers are for whoever is building the site, not for a customer.
# `python3 build.py --preview` labels them; a plain build ships none.
PREVIEW = "--preview" in sys.argv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def template(name: str) -> str:
    return (TPL / name).read_text()


def fill(text: str, values: dict) -> str:
    """Replace {{key}} tokens. An unknown token is a build error, not a blank."""
    def sub(match):
        key = match.group(1).strip()
        if key not in values:
            raise KeyError(f"template token {{{{{key}}}}} has no value")
        return str(values[key])

    return re.sub(r"\{\{([a-z0-9_]+)\}\}", sub, text)


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def mark(name: str) -> str:
    """Inline a brand SVG. Inlined so CSS can recolour it with currentColor."""
    path = BRAND / f"{name}.svg"
    if not path.exists():
        raise SystemExit(f"missing brand mark: {path} — run tools/extract_brand.py")
    return path.read_text().strip()


# sprite id -> the mark it comes from, so a <use> can be given the viewBox its
# source has. Without one the outer <svg> has no intrinsic proportions and
# width:auto falls back to the SVG default of 300px, which tore the two
# wordmark lines apart with a gap between them.
MARKS = {
    "m-motif": "motif",
    "m-satyr": "satyr",
    "m-wordmark": "wordmark-stacked",
    "m-word1": "wordmark-line1",
    "m-word2": "wordmark-line2",
}


def view_box(name: str) -> str:
    return re.search(r'viewBox="([^"]+)"', mark(name)).group(1)


def symbol(name: str, sprite_id: str) -> str:
    """Turn a mark into a <symbol> for the page sprite."""
    svg = mark(name)
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    body = re.sub(r"^<svg[^>]*>|</svg>$", "", svg.strip())
    body = re.sub(r"<title>.*?</title>", "", body)
    # fill="currentColor" lives on the source file's <svg> root, which the line
    # above strips. Without it carried onto the symbol the mark renders black,
    # which on the dark green header means an invisible logo.
    return f'<symbol id="{sprite_id}" viewBox="{box}" fill="currentColor">{body}</symbol>'


def sprite() -> str:
    """Every mark, once per page, instead of once per use.

    The motif was inlined twenty-two times on the catalogue page — 40 KB each,
    which is most of a megabyte of identical path data. Defined once here and
    referenced with <use>, the page drops to a fraction of that.
    """
    return (
        '<svg class="sprite" aria-hidden="true" focusable="false" '
        'style="position:absolute;width:0;height:0;overflow:hidden">'
        + symbol("motif", "m-motif")
        + symbol("satyr", "m-satyr")
        + symbol("wordmark-stacked", "m-wordmark")
        + symbol("wordmark-line1", "m-word1")
        + symbol("wordmark-line2", "m-word2")
        + "</svg>"
    )


def use(sprite_id: str, label: str = "") -> str:
    """Reference a sprite symbol. Decorative unless given a label.

    The viewBox is repeated on the referencing <svg> so it keeps the mark's
    aspect ratio — a <use> has no intrinsic size of its own.
    """
    a = f'role="img" aria-label="{esc(label)}"' if label else 'aria-hidden="true"'
    return (
        f'<svg {a} focusable="false" viewBox="{view_box(MARKS[sprite_id])}">'
        f'<use href="#{sprite_id}"/></svg>'
    )


def money(amount) -> str:
    return f"{int(round(amount)):,}".replace(",", " ")


# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------

NAV = [
    ("Catalogue", "index.html"),
    ("About", "about.html"),
    ("Visit", "visit.html"),
]


def nav_links(base: str, current: str) -> str:
    out = []
    for label, href in NAV:
        aria = ' aria-current="page"' if href == current else ""
        out.append(f'<a class="nav__link" href="{base}{href}"{aria}>{label}</a>')
    return "\n      ".join(out)


def wordmark_inline() -> str:
    """The two outlined lines of the mark, set side by side."""
    return (
        f'<span class="brand__line">{use("m-word1")}</span>'
        f'<span class="brand__line">{use("m-word2")}</span>'
    )


def age_gate(site: dict) -> str:
    age = site["catalogue"]["min_age"]
    return f"""<div class="age-gate" data-age-gate hidden role="dialog"
     aria-modal="true" aria-labelledby="age-gate-title">
  <div class="age-gate__inner">
    <div class="age-gate__satyr">{use("m-satyr")}</div>
    <h1 id="age-gate-title" tabindex="-1">Are you over {age}?</h1>
    <p>This is a catalogue of spirits, so we have to ask. Photo ID is checked
    at the counter too &mdash; this is only the first gate.</p>
    <div class="age-gate__actions">
      <button class="button button--solid" type="button" data-age-yes>
        <span>Yes, I am {age} or over</span>
      </button>
      <button class="button" type="button" data-age-no><span>No</span></button>
    </div>
    <p class="age-gate__deny">Then we cannot sell to you, and we would rather say so
    plainly. Come back when you can.</p>
  </div>
</div>"""


def footer_blocks(site: dict, catalogue: dict, base: str) -> dict:
    cats = "".join(
        f'<li><a href="{base}index.html?c={c["slug"]}">{esc(c["name"])}</a></li>'
        for c in catalogue["categories"]
    )

    a = site["address"]
    # Marked so a screen reader does not read Czech place names with English
    # phonetics.
    address = (
        f"<li lang=\"cs\">{esc(a['street'])}</li>"
        f"<li lang=\"cs\">{esc(a['postal'])} {esc(a['district'])}</li>"
        f"<li><span lang=\"cs\">{esc(a['city'])}</span>, {esc(a['country'])}</li>"
    )
    if site["contact"]["maps_url"]:
        address += f'<li><a href="{esc(site["contact"]["maps_url"])}" target="_blank" rel="noopener">Open in maps</a></li>'

    # Blank config value -> the link is never written at all.
    contact = []
    if site["contact"]["email"]:
        contact.append(
            f'<li><a href="mailto:{esc(site["contact"]["email"])}">{esc(site["contact"]["email"])}</a></li>'
        )
    if site["contact"]["phone"]:
        tel = re.sub(r"[^\d+]", "", site["contact"]["phone"])
        contact.append(f'<li><a href="tel:{esc(tel)}">{esc(site["contact"]["phone"])}</a></li>')
    for network in ("instagram", "facebook"):
        url = site["social"].get(network, "")
        if url:
            contact.append(
                f'<li><a href="{esc(url)}" target="_blank" rel="noopener">{network.title()}</a></li>'
            )
    if not contact:
        contact.append("<li>Contact details to follow.</li>")
        warnings.append("no contact details configured — footer shows a holding line")

    return {
        "footer_categories": cats,
        "footer_address": address,
        "footer_contact": "".join(contact),
    }


# ---------------------------------------------------------------------------
# Product rendering
# ---------------------------------------------------------------------------


IMAGE_WIDTHS = (400, 800, 1200)


def responsive_sources(image: str, base: str, sizes: str) -> str:
    """<source> lines for the formats that exist, best first."""
    stem = Path(image).with_suffix("")
    out = []
    for fmt in ("avif", "webp"):
        widths = [w for w in IMAGE_WIDTHS if (ROOT / f"{stem}-{w}.{fmt}").exists()]
        if not widths:
            continue
        srcset = ", ".join(f"{base}{esc(str(stem))}-{w}.{fmt} {w}w" for w in widths)
        out.append(f'<source type="image/{fmt}" srcset="{srcset}" sizes="{sizes}">')
    return "".join(out)


def responsive(image: str, base: str) -> tuple[str, str]:
    """src and srcset, using whatever variants exist beside the original.

    tools/make_product_images.py writes <slug>-400/800/1200.webp. Without them
    the original is served as-is, so a photograph dropped in works immediately
    and gets smaller once the variants are generated.
    """
    stem = Path(image).with_suffix("")
    found = [w for w in IMAGE_WIDTHS if (ROOT / f"{stem}-{w}.webp").exists()]
    if not found:
        return f"{base}{esc(image)}", ""
    src = f"{base}{esc(str(stem))}-{found[-1]}.webp"
    srcset = ", ".join(f"{base}{esc(str(stem))}-{w}.webp {w}w" for w in found)
    return src, srcset


def media(product: dict, base: str, css_class: str) -> str:
    """A photograph when there is one; the mark holding the slot when not."""
    image = product.get("image", "")
    if image:
        src, srcset = responsive(image, base)
        # The card is roughly a quarter of the shell on a desktop and half a
        # phone, so a phone never downloads the large file.
        sizes = (
            '(max-width: 759px) 45vw, (max-width: 1039px) 30vw, 22vw'
        )
        sources = responsive_sources(image, base, sizes)
        extra = f' srcset="{srcset}" sizes="{sizes}"' if srcset and not sources else ""
        return (
            f'<div class="{css_class}"><picture>{sources}'
            f'<img src="{src}"{extra} alt="{esc(product["name"])}" '
            f'loading="lazy" decoding="async" width="800" height="800"></picture></div>'
        )
    return f'<div class="{css_class} {css_class}--mark">{use("m-motif")}</div>'


def product_media(product: dict) -> str:
    """The product's photograph, frame and all — or nothing.

    An empty frame beside the type was the largest thing on the page and said
    nothing. Without a photograph the page is simply one column of type, which
    is the stronger layout anyway.
    """
    image = product.get("image", "")
    if not image:
        return ""
    sizes = "(max-width: 899px) 92vw, 40vw"
    src, srcset = responsive(image, "../")
    sources = responsive_sources(image, "../", sizes)
    extra = f' srcset="{srcset}" sizes="{sizes}"' if srcset and not sources else ""
    return (
        f'<div class="product__media"><picture>{sources}'
        f'<img src="{src}"{extra} alt="{esc(product["name"])}" '
        'width="800" height="800" decoding="async"></picture></div>'
    )


def fold(text: str) -> str:
    """Lowercase and strip diacritics.

    Half the names in a Prague bottle shop carry hacek and carka. Somebody
    typing "Becherovka" should find "Becherovka", and somebody typing it
    properly should find it too, so both forms are in the haystack.
    """
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    return unicodedata.normalize("NFC", stripped).lower()


def search_text(product: dict, cats: dict) -> str:
    """Everything the search box should match, prepared once at build time."""
    parts = [
        product["name"],
        product.get("producer", ""),
        cats[product["category"]]["name"],
        product.get("notes", ""),
    ]
    joined = " ".join(p for p in parts if p)
    folded = fold(joined)
    lowered = joined.lower()
    return folded if folded == lowered else f"{lowered} {folded}"


NEW_FOR_DAYS = 30


def is_new(product: dict) -> bool:
    added = product.get("added")
    if not added:
        return False
    try:
        when = datetime.strptime(added, "%Y-%m-%d").date()
    except ValueError:
        return False
    return (date.today() - when).days <= NEW_FOR_DAYS


def card(product: dict, cats: dict, base: str, order: int) -> str:
    draft = (
        '<span class="badge">Draft</span>'
        if PREVIEW and product.get("placeholder")
        else ""
    )

    # The frame is always there, so the grid is already the shape it will be
    # once photographs land and nothing has to be re-laid out around them.
    # Empty, it holds the mark quietly rather than a hard grey panel.
    frame = media(product, base, "card__media")

    note = product.get("notes", "")
    note_html = f'<p class="card__note">{esc(note)}</p>' if note else ""

    # Shown only when it tells you something. "In stock" on every one of twenty
    # cards is twenty lines of nothing.
    stock = 0 if product.get("placeholder") else product.get("stock", 0)
    flag = ""
    if not product.get("placeholder"):
        if stock == 0:
            flag = '<span class="card__flag" data-out="true">Currently out</span>'
        elif stock == 1:
            flag = '<span class="card__flag">Last bottle</span>'
        elif stock <= 3:
            flag = f'<span class="card__flag">Only {stock} left</span>'

    new_mark = '<span class="card__new">New</span>' if is_new(product) else ""

    return f"""<li class="card" style="--n:{min(order, 11)}" data-category="{esc(product['category'])}"
    data-price="{product['price']}" data-abv="{product['abv']}"
    data-volume="{product['volume']}" data-name="{esc(product['name'])}"
    data-added="{esc(product.get('added', ''))}"
    data-search="{esc(search_text(product, cats))}" data-order="{order}">
  {draft}{new_mark}
  {frame}
  <p class="card__category">{esc(cats[product['category']]['name'])}</p>
  <h2 class="card__name"><a class="card__link" href="{base}shop/{product['slug']}.html">{esc(product['name'])}</a></h2>
  {note_html}
  <div class="card__foot">
    <span class="price">{money(product['price'])} <small>CZK</small></span>
    <span class="card__spec">{product['volume']} ml &middot; {product['abv']}%</span>
  </div>
  {flag}
</li>"""


def grid(products: list, cats: dict, base: str) -> str:
    return "\n".join(card(p, cats, base, i) for i, p in enumerate(products))


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------


def render_page(
    *,
    site: dict,
    catalogue: dict,
    body: str,
    out: Path,
    title: str,
    description: str,
    slug: str,
    base: str,
    current: str = "",
    og_type: str = "website",
    head_extra: str = "",
    share: str = "",
    share_alt: str = "",
) -> None:
    # Each page can carry its own share card; without one it falls back to the
    # site card rather than to nothing.
    share_image = site["url"].rstrip("/") + "/" + (share or "assets/brand/share.png")
    # The catalogue filters read from data- attributes on the cards, so the
    # page needs no product list of its own.
    ivs = {"base": base, "currency": site["currency"]}

    analytics = ""
    domain = site["analytics"]["plausible_domain"]
    if domain:
        analytics = (
            f'<script defer data-domain="{esc(domain)}" '
            'src="https://plausible.io/js/script.js"></script>'
        )

    canonical = site["url"].rstrip("/") + "/" + slug

    values = {
        "title": esc(title),
        "description": esc(description),
        "canonical": esc(canonical),
        "og_type": og_type,
        "og_title": esc(title),
        "site_name": esc(site["name"]),
        "share_image": esc(share_image),
        "share_alt": esc(share_alt or f"{site['name']} — {site['tagline']}"),
        "base": base,
        "body_attrs": "",
        "head_extra": head_extra,
        "age_gate": age_gate(site),
        "wordmark_inline": wordmark_inline(),
        "sprite": sprite(),
        "wordmark_stacked": use("m-wordmark"),
        "nav_links": nav_links(base, current),
        "main": body,
        "legal": (
            esc(
                "A catalogue of what is on the shelf. Nothing is sold through this "
                "site; we sell alcohol only to adults, and photo ID is checked in "
                "the shop every time."
            )
            + f' <a href="{base}privacy.html">Privacy &amp; imprint</a>.'
        ),
        "year": date.today().year,
        "ivs_data": json.dumps(ivs, separators=(",", ":")),
        "analytics": analytics,
    }
    values.update(footer_blocks(site, catalogue, base))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(fill(template("base.html"), values))


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def opening_hours(site: dict) -> list:
    """Turn "Monday - Thursday, 12:00 - 22:00" into schema.org specifications."""
    out = []
    for days, times in site["hours"]:
        names = [d.strip() for d in days.split("-")]
        if len(names) == 2 and names[0] in DAYS and names[1] in DAYS:
            a, z = DAYS.index(names[0]), DAYS.index(names[1])
            span = DAYS[a : z + 1] if a <= z else DAYS[a:] + DAYS[: z + 1]
        else:
            span = [d for d in names if d in DAYS]
        opens, _, closes = times.partition("-")
        if not span or not closes:
            continue
        out.append({
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": span,
            "opens": opens.strip(),
            "closes": closes.strip(),
        })
    return out


def share_card(name: str) -> str:
    """A page's own share card, or "" so the site card is used instead."""
    path = f"assets/share/{name}.png"
    return path if (ROOT / path).exists() else ""


def price_range() -> str:
    """Derived from the catalogue, never asserted.

    A hardcoded "$$" is a claim about the shop nobody made; this is simply the
    span of the prices actually listed.
    """
    prices = [p["price"] for p in load("catalogue.json")["products"] if p.get("price")]
    if not prices:
        return ""
    return f"{money(min(prices))}–{money(max(prices))} CZK"


def shop_jsonld(site: dict) -> str:
    """The shop itself: a real address and real hours, which is what a bottle
    shop is found by. Empty fields are dropped before serialising — Google
    rejects a block containing null."""
    a = site["address"]
    data = {
        "@context": "https://schema.org",
        "@type": "Store",
        "name": site["name"],
        "description": site["description"],
        "url": site["url"].rstrip("/") + "/",
        "image": site["url"].rstrip("/") + "/assets/brand/share.png",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": a["street"],
            "postalCode": a["postal"],
            "addressLocality": a["city"],
            "addressCountry": a["country_code"],
        },
        "openingHoursSpecification": opening_hours(site),
        "priceRange": price_range(),
        "telephone": site["contact"]["phone"],
        "email": site["contact"]["email"],
        "hasMap": site["contact"]["maps_url"],
        "sameAs": [u for u in site["social"].values() if u],
    }
    data = {k: v for k, v in data.items() if v not in ("", None, [], {})}
    return '<script type="application/ld+json">' + json.dumps(data, separators=(",", ":")) + "</script>"


def hours_list(site: dict) -> str:
    return "".join(
        f"<li><span>{esc(day)}</span><span>{esc(time)}</span></li>"
        for day, time in site["hours"]
    )


def address_block(site: dict) -> str:
    a = site["address"]
    return (
        f'<address style="font-style:italic;line-height:1.7;color:var(--text-bright)">'
        f'{esc(a["street"])}<br>{esc(a["postal"])} {esc(a["district"])}<br>'
        f'{esc(a["city"])}, {esc(a["country"])}</address>'
    )


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def validate(site: dict, catalogue: dict) -> None:
    """Fail on bad data with the offending record named.

    A typo in a category used to surface as KeyError: 'nonexistent' from deep
    inside the renderer, with nothing to say which bottle caused it.
    """
    problems: list[str] = []
    categories = {c["slug"] for c in catalogue["categories"]}

    seen: dict[str, int] = {}
    for i, p in enumerate(catalogue["products"]):
        where = f"product {i + 1} ({p.get('slug', 'no slug')})"
        for field in ("slug", "name", "category", "price", "volume", "abv"):
            if p.get(field) in (None, ""):
                problems.append(f"{where}: missing {field}")
        if p.get("category") and p["category"] not in categories:
            problems.append(
                f"{where}: category '{p['category']}' is not in the categories list "
                f"({', '.join(sorted(categories))})"
            )
        for field in ("price", "volume", "abv"):
            if field in p and not isinstance(p[field], (int, float)):
                problems.append(f"{where}: {field} must be a number, got {p[field]!r}")
        if p.get("added") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p["added"])):
            problems.append(f"{where}: added must be YYYY-MM-DD, got {p['added']!r}")
        if p.get("slug"):
            if p["slug"] in seen:
                problems.append(
                    f"{where}: slug repeats product {seen[p['slug']]} — "
                    "they would overwrite each other's page"
                )
            seen[p["slug"]] = i + 1

    for c in catalogue["categories"]:
        if not c.get("slug") or not c.get("name"):
            problems.append(f"category {c!r}: needs both slug and name")

    if not site.get("url"):
        problems.append("site.json: url is required — canonicals and the sitemap use it")

    if problems:
        print("data problems:\n  " + "\n  ".join(problems), file=sys.stderr)
        raise SystemExit(1)


def build():
    site = load("site.json")
    catalogue = load("catalogue.json")
    validate(site, catalogue)
    cats = {c["slug"]: c for c in catalogue["categories"]}
    products = catalogue["products"]

    drafts = [p["slug"] for p in products if p.get("placeholder")]
    if drafts:
        warnings.append(
            f"{len(drafts)} of {len(products)} products are still placeholders "
            "— replace them in data/catalogue.json before this goes to a customer"
        )
    if not any(p.get("image") for p in products):
        warnings.append("no product photography yet — every card falls back to the brand mark")

    pages = []

    # Home — the catalogue ---------------------------------------------------
    # Bottle sizes come from the data, so adding a 1 litre bottle adds its own
    # filter option rather than needing the template edited.
    sizes = sorted({p["volume"] for p in products})
    size_options = '<option value="any">Any</option>' + "".join(
        f'<option value="{v}">{v} ml</option>' for v in sizes
    )
    # One category control at every size, in the sidebar. Counts come from the
    # same data the grid does, so they cannot disagree with it.
    counts = {c["slug"]: sum(1 for p in products if p["category"] == c["slug"])
              for c in catalogue["categories"]}
    category_list = (
        '<li><button class="facet__option" type="button" data-filter="all" '
        f'aria-pressed="true">All<span>{len(products)}</span></button></li>'
    )
    category_list += "".join(
        f'<li><button class="facet__option" type="button" data-filter="{c["slug"]}" '
        f'aria-pressed="false">{esc(c["name"])}<span>{counts[c["slug"]]}</span></button></li>'
        for c in catalogue["categories"]
    )

    home = fill(
        template("home.html"),
        {
            "site_name": esc(site["name"]),
            "tagline": esc(site["tagline"]),
            "city": esc(site["address"]["city"]),
            "description": esc(site["description"]),
            "motif": use("m-motif"),
            "satyr": use("m-satyr"),
            "wordmark_stacked": use("m-wordmark"),
            "category_list": category_list,
            "size_options": size_options,
            "product_grid": grid(products, cats, ""),
            "product_count": len(products),
            "hours_list": hours_list(site),
            "address_block": address_block(site),
            "street": esc(site["address"]["street"]),
            "district": esc(site["address"]["district"]),
        },
    )
    render_page(
        site=site, catalogue=catalogue, body=home, out=ROOT / "index.html",
        title=f"{site['name']} — {site['tagline']}, {site['address']['city']}",
        description=site["description"], slug="", base="", current="index.html",
        head_extra=shop_jsonld(site), share=share_card("index"),
        share_alt=f"{site['name']}, {site['tagline']} in {site['address']['city']}",
    )
    pages.append(("", "1.0"))

    # shop.html was the catalogue before it moved to the front page. It is kept
    # so a link shared in between does not 404 — as a real page, because a bare
    # meta-refresh stub is what a visitor sees if the refresh is blocked.
    moved = fill(
        template("moved.html"),
        {"base": "", "motif": use("m-motif")},
    )
    render_page(
        site=site, catalogue=catalogue, body=moved, out=ROOT / "shop.html",
        title=f"The catalogue moved — {site['name']}",
        description="The catalogue is now the front page.",
        slug="shop.html", base="", current="index.html",
        head_extra='<meta http-equiv="refresh" content="2; url=index.html">'
                   '<meta name="robots" content="noindex,follow">',
    )

    # Product pages ----------------------------------------------------------
    if SHOP_DIR.exists():
        shutil.rmtree(SHOP_DIR)
    for product in products:
        cat = cats[product["category"]]
        # Always exactly four, or the row is left short. Same category first,
        # then topped up from the rest of the shelf — which is why the heading
        # says "the shelf" rather than naming the category.
        same = [
            p for p in products
            if p["category"] == product["category"] and p["slug"] != product["slug"]
        ]
        others = [
            p for p in products
            if p["category"] != product["category"] and p["slug"] != product["slug"]
        ]
        related = (same + others)[:4]

        # A bottle used to be a dead end: breadcrumbs, and nothing else.
        index = products.index(product)
        prev_p = products[index - 1] if index else products[-1]
        next_p = products[(index + 1) % len(products)]
        neighbours = (
            '<nav class="pager" aria-label="Other bottles">'
            f'<a class="pager__link" rel="prev" href="{prev_p["slug"]}.html">'
            f'<span class="pager__dir">Previous</span>'
            f'<span class="pager__name">{esc(prev_p["name"])}</span></a>'
            f'<a class="pager__link pager__link--next" rel="next" href="{next_p["slug"]}.html">'
            f'<span class="pager__dir">Next</span>'
            f'<span class="pager__name">{esc(next_p["name"])}</span></a>'
            "</nav>"
        )

        # Nothing is sold here, so the only action is asking about a bottle —
        # and only when there is somewhere for that to go.
        enquire = ""
        subject = f"About {product['name']}"
        if site["contact"]["email"]:
            enquire = (
                f'<p><a class="button button--primary" '
                f'href="mailto:{esc(site["contact"]["email"])}?subject={esc(subject)}">'
                "<span>Ask about this bottle</span></a></p>"
            )
        elif site["contact"]["phone"]:
            tel = re.sub(r"[^\d+]", "", site["contact"]["phone"])
            enquire = (
                f'<p><a class="button button--primary" href="tel:{esc(tel)}">'
                "<span>Call about this bottle</span></a></p>"
            )

        producer_row = ""
        if product.get("producer"):
            producer_row = f'<tr><th scope="row">Producer</th><td>{esc(product["producer"])}</td></tr>'

        stock = product.get("stock", 0)
        stock_label = (
            f"{stock} in stock" if stock > 3
            else f"Only {stock} left" if stock > 0
            else "Ask us — currently out"
        )

        body = fill(
            template("product.html"),
            {
                "base": "../",
                "slug": esc(product["slug"]),
                "name": esc(product["name"]),
                "notes": esc(product.get("notes", "")),
                "price": money(product["price"]),
                "currency": esc(site["currency"]),
                "volume": product["volume"],
                "abv": product["abv"],
                "category_name": esc(cat["name"]),
                "category_slug": esc(cat["slug"]),
                "media": product_media(product),
                "producer_row": producer_row,
                "stock_label": esc(stock_label),
                "enquire": enquire,
                "availability_note": esc(site["catalogue"]["availability_note"]),
                "related_grid": grid(related, cats, "../"),
                "neighbours": neighbours,
            },
        )

        jsonld = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product["name"],
            "category": cat["name"],
            "description": product.get("notes", ""),
            "offers": {
                "@type": "Offer",
                "price": product["price"],
                "priceCurrency": site["currency"],
                "availability": ""
                if product.get("placeholder")
                else "https://schema.org/InStoreOnly" if stock
                else "https://schema.org/OutOfStock",
                "url": f"{site['url'].rstrip('/')}/shop/{product['slug']}.html",
            },
        }
        if product.get("producer"):
            jsonld["brand"] = {"@type": "Brand", "name": product["producer"]}
        # Google rejects a block containing null, so empty fields go before serialising.
        jsonld["offers"] = {k: v for k, v in jsonld["offers"].items() if v not in ("", None)}
        jsonld = {k: v for k, v in jsonld.items() if v not in ("", None, [], {})}

        render_page(
            site=site, catalogue=catalogue, body=body,
            out=SHOP_DIR / f"{product['slug']}.html",
            title=f"{product['name']} — {site['name']}",
            description=product.get("notes", "") or f"{product['name']}, {product['volume']} ml.",
            slug=f"shop/{product['slug']}.html", base="../", current="index.html",
            og_type="product",
            share=share_card(f"shop-{product['slug']}"),
            share_alt=f"{product['name']} — {cat['name']}, {product['volume']} ml",
            head_extra='<script type="application/ld+json">'
                       + json.dumps(jsonld, separators=(",", ":")) + "</script>"
                       + '<script type="application/ld+json">'
                       + json.dumps({
                           "@context": "https://schema.org",
                           "@type": "BreadcrumbList",
                           "itemListElement": [
                               {"@type": "ListItem", "position": 1, "name": "Catalogue",
                                "item": site["url"].rstrip("/") + "/"},
                               {"@type": "ListItem", "position": 2, "name": cat["name"],
                                "item": site["url"].rstrip("/") + "/?c=" + cat["slug"]},
                               {"@type": "ListItem", "position": 3, "name": product["name"]},
                           ],
                       }, separators=(",", ":")) + "</script>",
        )
        pages.append((f"shop/{product['slug']}.html", "0.7"))

    # About ------------------------------------------------------------------
    about = fill(
        template("about.html"),
        {
            "heading": "Two ways to hold a drink.",
            "motif": use("m-motif"),
            "satyr": use("m-satyr"),
            "hours_list": hours_list(site),
            "street": esc(site["address"]["street"]),
            "district": esc(site["address"]["district"]),
            "city": esc(site["address"]["city"]),
        },
    )
    render_page(
        site=site, catalogue=catalogue, body=about, out=ROOT / "about.html",
        title=f"About — {site['name']}",
        description="A small bottle shop in Nove Mesto, and why the shelf is short.",
        slug="about.html", base="", current="about.html",
        share=share_card("about"), share_alt="Two ways to hold a drink",
    )
    pages.append(("about.html", "0.6"))

    # Visit ------------------------------------------------------------------
    maps = ""
    if site["contact"]["maps_url"]:
        maps = (
            f'<p style="margin-top:1.2rem"><a class="button" '
            f'href="{esc(site["contact"]["maps_url"])}" target="_blank" rel="noopener">'
            "<span>Open in maps</span></a></p>"
        )

    contact_bits = []
    if site["contact"]["phone"]:
        tel = re.sub(r"[^\d+]", "", site["contact"]["phone"])
        contact_bits.append(f'<p><a href="tel:{esc(tel)}">{esc(site["contact"]["phone"])}</a></p>')
    if site["contact"]["email"]:
        contact_bits.append(
            f'<p><a href="mailto:{esc(site["contact"]["email"])}">{esc(site["contact"]["email"])}</a></p>'
        )
    contact_block = "".join(contact_bits) or (
        '<p class="note">Phone and email to be confirmed.</p>'
    )

    visit = fill(
        template("visit.html"),
        {
            "street": esc(site["address"]["street"]),
            "district": esc(site["address"]["district"]),
            "address_block": address_block(site),
            "maps_link": maps,
            "hours_list": hours_list(site),
            "contact_block": contact_block,
            "availability_note": esc(site["catalogue"]["availability_note"]),
        },
    )
    render_page(
        site=site, catalogue=catalogue, body=visit, out=ROOT / "visit.html",
        title=f"Visit — {site['name']}",
        description=f"{site['address']['street']}, {site['address']['district']}, {site['address']['city']}.",
        slug="visit.html", base="", current="visit.html",
        head_extra=shop_jsonld(site), share=share_card("visit"),
        share_alt=f"{site['address']['street']}, {site['address']['city']}",
    )
    pages.append(("visit.html", "0.6"))

    # Privacy and imprint ----------------------------------------------------
    a = site["address"]
    legal = site.get("legal", {})
    rows = [
        ("Trading name", site["name"]),
        ("Registered name", legal.get("company", "")),
        ("Company number", legal.get("company_id", "")),
        ("VAT number", legal.get("vat_id", "")),
        ("Address", f"{a['street']}, {a['postal']} {a['district']}, {a['city']}, {a['country']}"),
        ("Email", site["contact"]["email"]),
        ("Phone", site["contact"]["phone"]),
    ]
    filled = [(k, v) for k, v in rows if v]
    imprint = (
        '<table class="spec"><tbody>'
        + "".join(f"<tr><th scope=\"row\">{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in filled)
        + "</tbody></table>"
    )
    missing = [k for k, v in rows if not v]
    if missing:
        # Stated on the page rather than silently omitted: an imprint that is
        # quietly incomplete looks finished and is not.
        imprint += (
            '<p class="note">Still to be confirmed by the shop: '
            + esc(", ".join(missing).lower())
            + ". These are required on a Czech business site and this page is "
            "not complete without them.</p>"
        )
        warnings.append(
            f"imprint incomplete — missing {', '.join(missing).lower()}"
        )

    # The page has to describe the site as configured, not as it was written.
    if site["analytics"]["plausible_domain"]:
        analytics_note = (
            "<h3>Analytics</h3><p>We use Plausible, which is cookieless and "
            "collects no personal data — no IP address is stored and nothing "
            "follows you between sites. We also record when a search on this "
            "site finds nothing, together with what was typed, because it "
            "tells us which bottle to order next. Nothing else about your "
            "visit is recorded.</p>"
        )
    else:
        analytics_note = (
            "<h3>Analytics</h3><p>None. No analytics script is loaded, so "
            "there is nothing to opt out of and nothing to disclose.</p>"
        )

    privacy = fill(
        template("privacy.html"),
        {
            "motif": use("m-motif"),
            "min_age": site["catalogue"]["min_age"],
            "imprint": imprint,
            "analytics_note": analytics_note,
        },
    )
    render_page(
        site=site, catalogue=catalogue, body=privacy, out=ROOT / "privacy.html",
        title=f"Privacy & imprint — {site['name']}",
        description="What this site collects, which is nothing, and who runs it.",
        slug="privacy.html", base="",
    )
    pages.append(("privacy.html", "0.3"))

    # 404 --------------------------------------------------------------------
    notfound = fill(template("404.html"), {"base": "", "motif": mark("motif")})
    render_page(
        site=site, catalogue=catalogue, body=notfound, out=ROOT / "404.html",
        title=f"Not found — {site['name']}", description="Page not found.",
        slug="404.html", base="",
    )

    # Arrivals feed ----------------------------------------------------------
    newest = sorted(
        (p for p in products if p.get("added")),
        key=lambda p: p["added"], reverse=True,
    )[:20]
    base_url_feed = site["url"].rstrip("/")
    items = [
        {
            "name": p["name"],
            "category": cats[p["category"]]["name"],
            "volume_ml": p["volume"],
            "abv": p["abv"],
            "price": p["price"],
            "currency": site["currency"],
            "note": p.get("notes", ""),
            "added": p["added"],
            "url": f"{base_url_feed}/shop/{p['slug']}.html",
        }
        for p in newest
    ]
    (ROOT / "arrivals.json").write_text(
        json.dumps(
            {"shop": site["name"], "updated": date.today().isoformat(), "bottles": items},
            indent=2, ensure_ascii=False,
        ) + "\n"
    )

    def rfc822(iso: str) -> str:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%a, %d %b %Y 12:00:00 +0000")

    rss_items = "".join(
        "<item>"
        f"<title>{esc(i['name'])}</title>"
        f"<link>{esc(i['url'])}</link>"
        f"<guid isPermaLink=\"true\">{esc(i['url'])}</guid>"
        f"<pubDate>{rfc822(i['added'])}</pubDate>"
        f"<category>{esc(i['category'])}</category>"
        f"<description>{esc(i['note'] or i['name'])} "
        f"{i['volume_ml']} ml, {i['abv']}%, {money(i['price'])} {esc(i['currency'])}.</description>"
        "</item>"
        for i in items
    )
    (ROOT / "arrivals.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>{esc(site['name'])} — new on the shelf</title>"
        f"<link>{base_url_feed}/</link>"
        f"<description>Bottles as they arrive at {esc(site['address']['street'])}.</description>"
        "<language>en</language>"
        f"{rss_items}</channel></rss>\n"
    )

    # sitemap + robots -------------------------------------------------------
    # Generated from the same list the pages were, so it cannot drift into 404s.
    # lastmod tracks the page's content, not the build: stamping today on every
    # URL each time tells a crawler the whole site changed whenever anything
    # did, and it learns to ignore the field.
    base_url = site["url"].rstrip("/")
    today = date.today().isoformat()
    stamps = json.loads(STAMPS.read_text()) if STAMPS.exists() else {}
    changed = 0
    for path, _ in pages:
        f = ROOT / (path or "index.html")
        if not f.exists():
            continue
        digest = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
        entry = stamps.get(path)
        if not entry or entry.get("hash") != digest:
            stamps[path] = {"hash": digest, "date": today}
            changed += 1
    # Forget pages that no longer exist, so the file cannot grow stale entries.
    stamps = {k: v for k, v in stamps.items() if k in {p for p, _ in pages}}
    STAMPS.write_text(json.dumps(stamps, indent=2, sort_keys=True) + "\n")

    urls = "".join(
        f"<url><loc>{base_url}/{path}</loc>"
        f"<lastmod>{stamps.get(path, {}).get('date', today)}</lastmod>"
        f"<priority>{priority}</priority></url>"
        for path, priority in pages
    )
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>\n"
    )
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"
    )
    (ROOT / ".nojekyll").write_text("")

    print(f"built {len(pages) + 1} pages ({len(products)} products)"
          + (f", {changed} changed since last build" if changed else ", none changed"))
    # Deduplicated: the per-page checks would otherwise repeat once per page.
    for w in dict.fromkeys(warnings):
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
