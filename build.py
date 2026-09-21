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

warnings: list[str] = []


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


def money(amount) -> str:
    return f"{int(round(amount)):,}".replace(",", " ")


# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------

NAV = [
    ("Shop", "shop.html"),
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
        f'<span class="brand__line">{mark("wordmark-line1")}</span>'
        f'<span class="brand__line">{mark("wordmark-line2")}</span>'
    )


def age_gate(site: dict) -> str:
    age = site["commerce"]["min_age"]
    return f"""<div class="age-gate" data-age-gate hidden>
  <div class="age-gate__inner">
    <div class="age-gate__satyr" aria-hidden="true">{mark("satyr")}</div>
    <h1>Are you over {age}?</h1>
    <p>We sell alcohol, so we have to ask. We check photo ID at the counter
    and at the door as well &mdash; this is just the first gate.</p>
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
        f'<li><a href="{base}shop.html?c={c["slug"]}">{esc(c["name"])}</a></li>'
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
    return f'<div class="{css_class} {css_class}--mark" aria-hidden="true">{mark("motif")}</div>'


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
    return f'<div class="mark" aria-hidden="true">{mark("motif")}</div>'


def card(product: dict, cats: dict, base: str, order: int) -> str:
    draft = (
        '<span class="badge badge--draft">Draft</span>' if product.get("placeholder") else ""
    )
    return f"""<li class="card" data-category="{esc(product['category'])}"
    data-price="{product['price']}" data-name="{esc(product['name'])}" data-order="{order}">
  {draft}
  {media(product, base, "card__media")}
  <p class="card__category">{esc(cats[product['category']]['name'])}</p>
  <h3 class="card__name"><a class="card__link" href="{base}shop/{product['slug']}.html">{esc(product['name'])}</a></h3>
  <p class="card__meta">{product['volume']} ml &middot; {product['abv']}%</p>
  <div class="card__foot">
    <span class="price">{money(product['price'])} <small>{esc('CZK')}</small></span>
    <button class="card__add" type="button" data-add="{esc(product['slug'])}"
            data-label="Add" aria-label="Add {esc(product['name'])} to cart">Add</button>
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
) -> None:
    ivs = {
        "base": base,
        "currency": site["currency"],
        "commerce": {
            k: v for k, v in site["commerce"].items() if not k.startswith("_")
        },
        "products": {
            p["slug"]: {
                "name": p["name"],
                "price": p["price"],
                "volume": p["volume"],
                "abv": p["abv"],
                "category": p["category"],
            }
            for p in catalogue["products"]
        },
    }

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
        "share_image": esc(site["url"].rstrip("/") + "/assets/brand/share.png"),
        "base": base,
        "body_attrs": "",
        "head_extra": head_extra,
        "age_gate": age_gate(site),
        "wordmark_inline": wordmark_inline(),
        "wordmark_stacked": mark("wordmark-stacked"),
        "nav_links": nav_links(base, current),
        "main": body,
        "legal": esc(
            "We sell alcohol only to adults. Photo ID is checked in the shop and "
            "again on delivery."
        ),
        "year": date.today().year,
        "ivs_data": json.dumps(ivs, separators=(",", ":")),
        "analytics": analytics,
    }
    values.update(footer_blocks(site, catalogue, base))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(fill(template("base.html"), values))


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

    # Home -------------------------------------------------------------------
    featured = [p for p in products if p.get("featured")] or products[:4]
    category_cards = "".join(
        f'<li><a class="category-card" href="shop.html?c={c["slug"]}">'
        f'<h3>{esc(c["name"])}</h3><p>{esc(c["blurb"])}</p>'
        f'<span class="category-card__count">'
        f'{sum(1 for p in products if p["category"] == c["slug"])} bottles</span></a></li>'
        for c in catalogue["categories"]
    )
    home = fill(
        template("home.html"),
        {
            "base": "",
            "site_name": esc(site["name"]),
            "tagline": esc(site["tagline"]),
            "description": esc(site["description"]),
            "motif": mark("motif"),
            "satyr": mark("satyr"),
            "wordmark_stacked": mark("wordmark-stacked"),
            "category_cards": category_cards,
            "featured_grid": grid(featured, cats, ""),
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
        description=site["description"], slug="", base="",
    )
    pages.append(("", "1.0"))

    # Shop -------------------------------------------------------------------
    chips = '<li><button class="chip" type="button" data-filter="all" aria-pressed="true">All</button></li>'
    chips += "".join(
        f'<li><button class="chip" type="button" data-filter="{c["slug"]}" '
        f'aria-pressed="false">{esc(c["name"])}</button></li>'
        for c in catalogue["categories"]
    )
    shop = fill(
        template("shop.html"),
        {
            "heading": "Everything on the shelf.",
            "intro": "Twenty-odd bottles, chosen one at a time. Filter by category, or "
                     "read down the list and let something catch you.",
            "chips": chips,
            "product_grid": grid(products, cats, ""),
            "product_count": len(products),
        },
    )
    render_page(
        site=site, catalogue=catalogue, body=shop, out=ROOT / "shop.html",
        title=f"Shop — {site['name']}",
        description="Spirits, vermouth and liqueur, chosen one bottle at a time.",
        slug="shop.html", base="", current="shop.html",
    )
    pages.append(("shop.html", "0.9"))

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

        buy = ""
        if product.get("stripe_buy_button"):
            buy = (
                f'<p style="margin:-1rem 0 2rem"><a class="button button--primary" '
                f'href="{esc(product["stripe_buy_button"])}"><span>Buy now with card</span></a></p>'
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
                "buy_now": buy,
                "delivery_note": esc(site["commerce"]["delivery_note"]),
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
                "availability": "https://schema.org/InStock" if stock else "https://schema.org/OutOfStock",
                "url": f"{site['url'].rstrip('/')}/shop/{product['slug']}.html",
            },
        }
        if product.get("producer"):
            jsonld["brand"] = {"@type": "Brand", "name": product["producer"]}
        # Google rejects a block containing null, so empty fields go before serialising.
        jsonld = {k: v for k, v in jsonld.items() if v not in ("", None, [], {})}

        render_page(
            site=site, catalogue=catalogue, body=body,
            out=SHOP_DIR / f"{product['slug']}.html",
            title=f"{product['name']} — {site['name']}",
            description=product.get("notes", "") or f"{product['name']}, {product['volume']} ml.",
            slug=f"shop/{product['slug']}.html", base="../", current="shop.html",
            og_type="product",
            head_extra='<script type="application/ld+json">'
                       + json.dumps(jsonld, separators=(",", ":")) + "</script>",
        )
        pages.append((f"shop/{product['slug']}.html", "0.7"))

    # Cart -------------------------------------------------------------------
    endpoint = site["commerce"]["order_form_endpoint"]
    if endpoint:
        checkout = f"""<form data-checkout-form action="{esc(endpoint)}" method="post">
            <div class="field"><label for="name">Your name</label>
              <input id="name" name="name" type="text" autocomplete="name" required></div>
            <div class="field"><label for="email">Email</label>
              <input id="email" name="email" type="email" autocomplete="email" required></div>
            <div class="field"><label for="phone">Phone</label>
              <input id="phone" name="phone" type="tel" autocomplete="tel" required></div>
            <div class="field"><label for="delivery">Delivery address, or say collection</label>
              <textarea id="delivery" name="delivery" required></textarea></div>
            <button class="button button--solid" type="submit"><span>Place order</span></button>
            <p class="note" data-checkout-status role="status"></p>
            <p class="note">{esc(site['commerce']['delivery_note'])}</p>
          </form>
          <div data-checkout-done hidden>
            <p class="lede" style="font-size:var(--step-0)">Order received. We will confirm by
            phone before anything moves, and ID is checked at handover.</p>
          </div>"""
    else:
        checkout = f"""<p class="note">Online ordering is not switched on yet. Add an order
          form endpoint in <code>data/site.json</code> and this becomes a working checkout.</p>
          <p class="note">{esc(site['commerce']['delivery_note'])}</p>"""
        warnings.append(
            "no order_form_endpoint configured — the cart works but checkout cannot submit"
        )

    cart = fill(
        template("cart.html"),
        {"base": "", "motif": mark("motif"), "checkout": checkout},
    )
    render_page(
        site=site, catalogue=catalogue, body=cart, out=ROOT / "cart.html",
        title=f"Cart — {site['name']}",
        description="Your order.", slug="cart.html", base="",
    )
    pages.append(("cart.html", "0.4"))

    # About ------------------------------------------------------------------
    about = fill(
        template("about.html"),
        {
            "heading": "Two ways to hold a drink.",
            "motif": mark("motif"),
            "satyr": mark("satyr"),
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

    free = site["commerce"]["free_delivery_over"]
    flat = site["commerce"]["delivery_flat"]
    visit = fill(
        template("visit.html"),
        {
            "street": esc(site["address"]["street"]),
            "district": esc(site["address"]["district"]),
            "address_block": address_block(site),
            "maps_link": maps,
            "hours_list": hours_list(site),
            "contact_block": contact_block,
            "delivery_note": esc(site["commerce"]["delivery_note"]),
            "delivery_terms": esc(
                f"Delivery inside Prague is {money(flat)} {site['currency']}, "
                f"and free over {money(free)} {site['currency']}."
            ),
        },
    )
    render_page(
        site=site, catalogue=catalogue, body=visit, out=ROOT / "visit.html",
        title=f"Visit — {site['name']}",
        description=f"{site['address']['street']}, {site['address']['district']}, {site['address']['city']}.",
        slug="visit.html", base="", current="visit.html",
    )
    pages.append(("visit.html", "0.6"))

    # 404 --------------------------------------------------------------------
    notfound = fill(template("404.html"), {"base": "", "motif": mark("motif")})
    render_page(
        site=site, catalogue=catalogue, body=notfound, out=ROOT / "404.html",
        title=f"Not found — {site['name']}", description="Page not found.",
        slug="404.html", base="",
    )

    # sitemap + robots -------------------------------------------------------
    # Generated from the same list the pages were, so it cannot drift into 404s.
    base_url = site["url"].rstrip("/")
    today = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{base_url}/{path}</loc><lastmod>{today}</lastmod>"
        f"<priority>{priority}</priority></url>"
        for path, priority in pages
    )
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>\n"
    )
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nDisallow: /cart.html\n\nSitemap: {base_url}/sitemap.xml\n"
    )
    (ROOT / ".nojekyll").write_text("")

    print(f"built {len(pages) + 1} pages ({len(products)} products)")
    # Deduplicated: the per-page checks would otherwise repeat once per page.
    for w in dict.fromkeys(warnings):
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
