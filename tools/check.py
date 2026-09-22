#!/usr/bin/env python3
"""Check the built site in a real browser.

    python3 build.py && python3 tools/check.py

Starts its own server on a private port, runs every check, prints PASS/FAIL per
assertion and exits non-zero if anything failed.

Three rules this file exists to enforce, each learned from a bug that shipped:

* **Assert pixels, not properties.** `hidden` is overridden by any element with
  its own `display`, so a filter can report success while every card stays on
  screen. Everything here counts elements with a non-zero bounding box.
* **Sweep widths.** A grid item's automatic minimum causes overflow at middle
  widths only; 1440 and 390 both look fine.
* **Emulate the device.** macOS Chrome clamps a headless window to 500px, so a
  390px screenshot is silently fake. These use Playwright device metrics and
  sanity-check `window.innerWidth` from inside the page.
"""

from __future__ import annotations

import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"

PHONES = [
    ("iPhone SE", 320, 568),
    ("iPhone 12 mini", 360, 780),
    ("iPhone 13", 390, 844),
    ("Pixel 7", 412, 915),
    ("iPhone 14 Plus", 428, 926),
]
WIDTHS = [320, 360, 390, 414, 480, 540, 600, 680, 768, 834, 900, 1024, 1180, 1280, 1440, 1680, 1920]
PAGES = ["/", "/about.html", "/visit.html", "/404.html", "/shop/single-malt-10.html"]

failures: list[str] = []


def check(label, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + label + (f"   [{detail}]" if detail and not ok else ""))
    if not ok:
        failures.append(label)


@contextmanager
def server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # A leftover server on the same port would answer with someone else's
        # files, so wait for *this* one rather than assuming it is up.
        for _ in range(50):
            try:
                import urllib.request

                urllib.request.urlopen(f"{BASE}/index.html", timeout=1).read(1)
                break
            except Exception:
                time.sleep(0.1)
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def open_page(ctx, path):
    """Answer the age gate first — it hides the page it is protecting."""
    pg = ctx.new_page()
    pg.goto(BASE + "/")
    pg.evaluate("try{localStorage.setItem('ivs.age.v1','true')}catch(e){}")
    pg.goto(BASE + path, wait_until="networkidle")
    pg.wait_for_timeout(350)
    return pg


def painted(pg, selector="[data-grid] > li"):
    return pg.eval_on_selector_all(
        selector, "els=>els.filter(e=>e.getBoundingClientRect().height>0).length"
    )


def check_filters(br):
    print("\nFilters")
    pg = open_page(br.new_context(), "/")
    check("all bottles shown initially", painted(pg) == 20, str(painted(pg)))

    pg.click('[data-filter="whisky"]')
    pg.wait_for_timeout(250)
    cats = pg.eval_on_selector_all(
        "[data-grid] > li",
        "e=>[...new Set(e.filter(x=>x.getBoundingClientRect().height>0).map(x=>x.dataset.category))]",
    )
    check("category narrows the grid", painted(pg) == 4 and cats == ["whisky"], f"{painted(pg)} {cats}")

    pg.select_option("[data-price]", "1500-")
    pg.wait_for_timeout(250)
    check("filters stack", painted(pg) == 1, str(painted(pg)))

    pg.click("[data-reset]")
    pg.wait_for_timeout(250)
    check("reset restores everything", painted(pg) == 20, str(painted(pg)))

    pg.select_option("[data-strength]", "50-")
    pg.wait_for_timeout(250)
    abvs = pg.eval_on_selector_all(
        "[data-grid] > li",
        "e=>e.filter(x=>x.getBoundingClientRect().height>0).map(x=>+x.dataset.abv)",
    )
    check("strength band", abvs and all(a >= 50 for a in abvs), str(abvs))
    pg.click("[data-reset]")
    pg.wait_for_timeout(200)

    pg.fill("[data-search]", "juniper")
    pg.wait_for_timeout(300)
    names = pg.eval_on_selector_all(
        "[data-grid] > li",
        "e=>e.filter(x=>x.getBoundingClientRect().height>0).map(x=>x.dataset.name)",
    )
    check("search reaches tasting notes", "London Dry Gin" in names, str(names))

    pg.fill("[data-search]", "zzzz")
    pg.wait_for_timeout(300)
    check("empty state appears", painted(pg) == 0 and pg.is_visible("[data-no-results]"))
    pg.click("[data-search-clear]")
    pg.wait_for_timeout(250)
    check("clearing search restores", painted(pg) == 20, str(painted(pg)))

    pg.select_option("[data-sort]", "price-desc")
    pg.wait_for_timeout(250)
    prices = pg.eval_on_selector_all("[data-grid] > li", "e=>e.map(x=>+x.dataset.price)")
    check("sort, price high to low", prices == sorted(prices, reverse=True), str(prices[:4]))

    pg.goto(BASE + "/?c=gin&abv=43-49.9", wait_until="networkidle")
    pg.wait_for_timeout(400)
    check("a filtered URL survives a reload", painted(pg) == 2, str(painted(pg)))

    check(
        "nothing is buyable",
        pg.eval_on_selector_all("[data-add], .card__add, [data-checkout-form]", "e=>e.length") == 0,
    )
    pg.context.close()


def check_mobile(br):
    print("\nMobile")
    for name, w, h in PHONES:
        ctx = br.new_context(
            viewport={"width": w, "height": h}, device_scale_factor=3, is_mobile=True, has_touch=True
        )
        pg = open_page(ctx, "/")
        inner = pg.evaluate("window.innerWidth")
        check(f"{name}: viewport is really {w}px", inner == w, f"innerWidth={inner}")

        m = pg.evaluate(
            """()=>{const d=document.documentElement, f=document.querySelector('.filters');
              return {overflow:d.scrollWidth-d.clientWidth,
                      page:d.scrollHeight,
                      filtersTop:Math.round(f.getBoundingClientRect().top),
                      cols:new Set([...document.querySelectorAll('[data-grid] > li')]
                            .map(e=>Math.round(e.getBoundingClientRect().left))).size};}"""
        )
        check(f"{name}: no sideways overflow", m["overflow"] == 0, str(m["overflow"]))
        check(f"{name}: filters above the fold", m["filtersTop"] < h, f"{m['filtersTop']} vs {h}")
        check(f"{name}: catalogue in two columns", m["cols"] == 2, f"{m['cols']} columns")
        # One column of tall cards made this 14 000px for twenty bottles.
        check(f"{name}: page under 9000px", m["page"] < 9000, f"{m['page']}px")

        check(
            f"{name}: category control is usable",
            pg.is_visible("[data-category]") and pg.eval_on_selector(".chips", "e=>getComputedStyle(e).display") == "none",
        )
        pg.select_option("[data-category]", "rum")
        pg.wait_for_timeout(300)
        check(f"{name}: category select filters", painted(pg) == 3, str(painted(pg)))

        small = pg.eval_on_selector_all(
            "a, button, select, input",
            """els=>els.filter(e=>{const r=e.getBoundingClientRect();
                 return r.height>0 && r.height<44
                        && !e.classList.contains('skip-link')
                        && !e.classList.contains('card__link');})
               .map(e=>e.tagName+'.'+(e.className||'').split(' ')[0])""",
        )
        check(f"{name}: tap targets are 44px+", not small, str(small[:5]))

        tiny = pg.eval_on_selector_all(
            "input, select, textarea",
            "els=>els.filter(e=>parseFloat(getComputedStyle(e).fontSize)<16).map(e=>e.tagName)",
        )
        check(f"{name}: no input under 16px", not tiny, str(tiny))

        # The small-screen card rules share specificity with the base ones, so
        # source order decides. Placed too early they go inert while still
        # reading correctly in the CSS — assert the computed value, not the rule.
        card = pg.evaluate(
            """()=>({ar:getComputedStyle(document.querySelector('.card__media')).aspectRatio,
                     pad:parseFloat(getComputedStyle(document.querySelector('.card')).paddingTop)})"""
        )
        check(f"{name}: compact card is in effect", card["ar"].replace(" ", "") == "1/1" and card["pad"] < 16,
              f'aspect {card["ar"]}, padding {card["pad"]}px')
        ctx.close()


def check_widths(br):
    print("\nOverflow across widths")
    ctx = br.new_context()
    pg = open_page(ctx, "/")
    bad = []
    for w in WIDTHS:
        pg.set_viewport_size({"width": w, "height": 900})
        for path in PAGES:
            pg.goto(BASE + path, wait_until="networkidle")
            pg.wait_for_timeout(120)
            sw, cw = pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            if sw > cw + 1:
                culprits = pg.evaluate(
                    """()=>[...document.querySelectorAll('*')]
                        .filter(e=>e.getBoundingClientRect().right>document.documentElement.clientWidth+1)
                        .slice(0,2).map(e=>e.tagName+'.'+(e.className.baseVal||e.className||'').toString().split(' ')[0])"""
                )
                bad.append(f"{w}px {path} {culprits}")
    check(f"no overflow over {len(WIDTHS) * len(PAGES)} width/page combinations", not bad, "; ".join(bad[:3]))
    ctx.close()


def check_grids(br):
    print("\nFixed-count grids")
    # Only grids with a fixed item count are checked. The catalogue holds
    # however many bottles the client sells, and no longer needs to divide
    # evenly because it paints nothing behind an empty cell.
    ctx = br.new_context()
    pg = open_page(ctx, "/shop/single-malt-10.html")
    bad = []
    for w in [390, 520, 600, 768, 900, 1040, 1280, 1440, 1920]:
        pg.set_viewport_size({"width": w, "height": 1000})
        pg.wait_for_timeout(150)
        info = pg.eval_on_selector(
            ".product-grid--four",
            """g=>{const k=[...g.children].filter(e=>e.getBoundingClientRect().height>0);
                 const tops=k.map(e=>Math.round(e.getBoundingClientRect().top));
                 const rows=[...new Set(tops)].map(t=>tops.filter(x=>x===t).length);
                 return {cols:Math.max(...rows), last:rows[rows.length-1], rows};}""",
        )
        if info["cols"] > 1 and info["last"] != info["cols"]:
            bad.append(f'{w}px: {info["rows"]}')
    check("no partly-filled last row", not bad, "; ".join(bad))
    ctx.close()


def main():
    if not (ROOT / "index.html").exists():
        sys.exit("nothing built yet — run python3 build.py first")
    with server(), sync_playwright() as pw:
        br = pw.chromium.launch()
        check_filters(br)
        check_mobile(br)
        check_widths(br)
        check_grids(br)
        br.close()

    print()
    if failures:
        print(f"{len(failures)} FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
