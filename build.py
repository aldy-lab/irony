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
from datetime import date
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
    return f"""<div class="age-gate" data-age-gate hidden>
  <div class="age-gate__inner">
    <div class="age-gate__satyr">{use("m-satyr")}</div>
    <h1>Are you over {age}?</h1>
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
    address = (
        f"<li>{esc(a['street'])}</li>"
        f"<li>{esc(a['postal'])} {esc(a['district'])}</li>"
        f"<li>{esc(a['city'])}, {esc(a['country'])}</li>"
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


def media(product: dict, base: str, css_class: str) -> str:
    """A photo when there is one; the brand mark when there is not.

    The card is designed to work without photography, so a missing image is a
    deliberate state rather than an empty box.
    """
    image = product.get("image", "")
    if image:
        return (
            f'<div class="{css_class}">'
            f'<img src="{base}{esc(image)}" alt="{esc(product["name"])}" '
            f'loading="lazy" decoding="async" width="600" height="750"></div>'
        )
    return f'<div class="{css_class} {css_class}--mark">{use("m-motif")}</div>'


def product_media(product: dict) -> str:
    """Inner contents of the product page's media frame.

    The frame itself is in the template; this is only what sits inside it, so
    a product with no photograph shows the mark instead of an empty panel.
    """
    image = product.get("image", "")
    if image:
        return (
            f'<img src="../{esc(image)}" alt="{esc(product["name"])}" '
            'width="900" height="1200" decoding="async">'
        )
    return f'<div class="mark">{use("m-motif")}</div>'


def search_text(product: dict, cats: dict) -> str:
    """Everything the search box should match, lowercased once at build time."""
    parts = [
        product["name"],
        product.get("producer", ""),
        cats[product["category"]]["name"],
        product.get("notes", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def card(product: dict, cats: dict, base: str, order: int) -> str:
    draft = (
        '<span class="badge">Draft</span>'
        if PREVIEW and product.get("placeholder")
        else ""
    )
    # A placeholder's stock number is invented, so it is not shown as fact.
    stock = 0 if product.get("placeholder") else product.get("stock", 0)
    stock_label = (
        "Ask in the shop"
        if product.get("placeholder")
        else "In stock" if stock > 3 else f"Only {stock} left" if stock else "Ask us"
    )
    return f"""<li class="card" data-category="{esc(product['category'])}"
    data-price="{product['price']}" data-abv="{product['abv']}"
    data-volume="{product['volume']}" data-name="{esc(product['name'])}"
    data-search="{esc(search_text(product, cats))}" data-order="{order}">
  {draft}
  {media(product, base, "card__media")}
  <p class="card__category">{esc(cats[product['category']]['name'])}</p>
  <h2 class="card__name"><a class="card__link" href="{base}shop/{product['slug']}.html">{esc(product['name'])}</a></h2>
  <p class="card__meta">{product['volume']} ml &middot; {product['abv']}%</p>
  <div class="card__foot">
    <span class="price">{money(product['price'])} <small>CZK</small></span>
    <span class="card__stock" data-out="{'true' if not stock else 'false'}">{esc(stock_label)}</span>
  </div>
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


def build():
    site = load("site.json")
    catalogue = load("catalogue.json")
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

    privacy = fill(
        template("privacy.html"),
        {
            "motif": use("m-motif"),
            "min_age": site["catalogue"]["min_age"],
            "imprint": imprint,
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
