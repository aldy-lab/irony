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

import re
import socket
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
    # Refuse to run against someone else's server. A leftover process on this
    # port would answer with different files and every assertion below would be
    # about those, not about this build.
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            sys.exit(
                f"port {PORT} is already in use — another server would answer "
                "these checks. Stop it and re-run."
            )
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
        else:
            proc.terminate()
            sys.exit(f"server on port {PORT} never came up")
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

    # Newest first, from the listing dates.
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(400)
    pg.select_option("[data-sort]", "newest")
    pg.wait_for_timeout(350)
    dates = pg.eval_on_selector_all("[data-grid] > li", "e=>e.map(x=>x.dataset.added)")
    check("newest first is actually newest first", dates == sorted(dates, reverse=True),
          str(dates[:3]))
    check("every bottle has a listing date", all(dates), f"{dates.count('')} missing")

    # Diacritics folded both ways: the haystack is folded at build time and the
    # query is folded in the browser.
    pg.select_option("[data-sort]", "default")
    pg.fill("[data-search]", "aperitivo")
    pg.wait_for_timeout(350)
    plain = painted(pg)
    pg.fill("[data-search]", "apéritivo")
    pg.wait_for_timeout(350)
    check("search ignores diacritics", painted(pg) == plain and plain > 0,
          f"{plain} plain vs {painted(pg)} accented")
    pg.fill("[data-search]", "")
    pg.wait_for_timeout(300)

    # The random pick must respect the shelf you are looking at.
    pg.click('[data-filter="rum"]')
    pg.wait_for_timeout(300)
    pg.click("[data-random]")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(300)
    crumb = pg.eval_on_selector(".eyebrow", "e=>e.textContent")
    check("the random pick stays inside the filter", "Rum" in crumb, crumb.strip()[:40])

    # A bottle is not a dead end.
    check("a bottle links to its neighbours",
          pg.eval_on_selector_all("a[rel=prev], a[rel=next]", "e=>e.length") == 2)

    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(400)
    # Everything added in this pass, asserted so it cannot rot quietly.
    check("the shelf is described as one list",
          "ItemList" in pg.content(), "no ItemList block")
    check("search has suggestions",
          pg.eval_on_selector_all("#bottle-names option", "e=>e.length") == 20)
    pg.keyboard.press("/")
    pg.wait_for_timeout(200)
    check("slash jumps to the search box",
          pg.evaluate("()=>document.activeElement.hasAttribute('data-search')"))
    pg.keyboard.press("Escape")

    opening = pg.eval_on_selector("[data-open-now]", "e=>e.textContent.trim()")
    check("the header says whether the shop is open",
          bool(opening) and ("Open" in opening or "Closed" in opening), repr(opening))

    check("prices are comparable across bottle sizes",
          pg.eval_on_selector_all(".price__rate", "e=>e.length") == 20,
          f'{pg.eval_on_selector_all(".price__rate", "e=>e.length")} per-litre figures')

    # A meta CSP cannot carry frame-ancestors; the browser warns on every load
    # if it is there, and the directive does nothing.
    csp = pg.eval_on_selector(
        'meta[http-equiv="Content-Security-Policy"]', "e=>e.content"
    )
    check("a content policy is declared", "default-src 'self'" in csp, csp[:60])
    check("no directive a meta tag cannot carry", "frame-ancestors" not in csp)

    check("the feed is reachable by a person",
          pg.eval_on_selector_all('a[href$="arrivals.xml"]', "e=>e.length") > 0)

    check(
        "nothing is buyable",
        pg.eval_on_selector_all("[data-add], .card__add, [data-checkout-form]", "e=>e.length") == 0,
    )
    pg.context.close()


def check_fonts(br):
    print("\nFonts")
    ctx = br.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    missing = []
    pg.on(
        "response",
        lambda r: missing.append(r.url.split("/")[-1])
        if ".woff2" in r.url and r.status != 200
        else None,
    )
    pg.goto(BASE + "/")
    pg.evaluate("try{localStorage.setItem('ivs.age.v1','true')}catch(e){}")
    pg.goto(BASE + "/shop/single-malt-10.html", wait_until="networkidle")
    pg.wait_for_timeout(1200)

    check("no font 404s", not missing, str(missing))

    title = pg.eval_on_selector(
        ".product__title",
        "e=>getComputedStyle(e).fontFamily.split(',')[0].replace(/\"/g,'')",
    )
    body = pg.eval_on_selector(
        ".lede", "e=>getComputedStyle(e).fontFamily.split(',')[0].replace(/\"/g,'')"
    )
    check("display face is the webfont, not a fallback", title == "Cormorant Garamond", title)
    check("text face is the webfont, not a fallback", body == "EB Garamond", body)

    loaded = pg.evaluate("()=>[...document.fonts].filter(f=>f.status==='loaded').length")
    check("webfonts actually loaded", loaded >= 2, str(loaded))

    # Italiana rendered "10 Years" as "Io Years"; figures are pinned lining so
    # a future face swap cannot quietly bring old-style figures back.
    nums = pg.eval_on_selector(".product__price", "e=>getComputedStyle(e).fontVariantNumeric")
    check("prices are lining and tabular", "lining-nums" in nums and "tabular-nums" in nums, nums)

    # A non-variable family ships one file per weight; identical names would
    # mean the last download silently wins and 400 renders as 600.
    css = (ROOT / "css" / "fonts.css").read_text()
    urls = re.findall(r"url\('([^']+)'\)", css)
    check("every @font-face has its own file", len(urls) == len(set(urls)),
          f"{len(urls)} faces, {len(set(urls))} files")
    ctx.close()


def check_a11y(br):
    print("\nAccessibility")
    ctx = br.new_context(viewport={"width": 1440, "height": 900})
    pg = open_page(ctx, "/")

    # Muted text sat at 4.46:1, fractionally under the AA floor, on six
    # different labels at once — it is one token, so it regresses as one.
    low = pg.evaluate(
        r"""()=>{
      const lum=c=>{const s=c/255; return s<=0.03928? s/12.92 : ((s+0.055)/1.055)**2.4;};
      const L=([r,g,b])=>0.2126*lum(r)+0.7152*lum(g)+0.0722*lum(b);
      const rgb=s=>s.replace(/rgba?\(|\)/g,'').split(',').slice(0,3).map(Number);
      const bgOf=e=>{let p=e; while(p){const b=getComputedStyle(p).backgroundColor;
        if(b && b!=='rgba(0, 0, 0, 0)') return b; p=p.parentElement;} return 'rgb(255,255,255)';};
      const out=[];
      for(const sel of ['.facet__label','.card__category','.card__meta','.card__stock',
                        '.results__count','.badge','.nav__link','.footer h3','.masthead__copy']){
        const e=document.querySelector(sel); if(!e) continue;
        const cs=getComputedStyle(e);
        const a=L(rgb(cs.color)), b=L(bgOf(e));
        const ratio=(Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);
        const need=parseFloat(cs.fontSize)>=18.66?3:4.5;
        if(ratio<need) out.push(sel+' '+ratio.toFixed(2)+':1 (needs '+need+')');
      }
      return out;}"""
    )
    check("all text meets its contrast floor", not low, "; ".join(low))

    levels = pg.evaluate(
        "()=>[...document.querySelectorAll('main h1,main h2,main h3,main h4')].map(h=>+h.tagName[1])"
    )
    skips = [f"h{a}->h{b}" for a, b in zip(levels, levels[1:]) if b > a + 1]
    check("no heading level is skipped", not skips, "; ".join(skips))

    # Filtering changes the results; a screen reader has to be told.
    live = pg.eval_on_selector_all(
        "[aria-live], [role=status]", "els=>els.length"
    )
    check("results are announced when they change", live > 0, f"{live} live regions")

    # The gate behaves as a modal, so it must be one: labelled, and holding
    # focus rather than letting it wander onto the page it is covering.
    gate_ctx = br.new_context(viewport={"width": 1440, "height": 900})
    gp = gate_ctx.new_page()
    gp.goto(BASE + "/", wait_until="networkidle")
    gp.wait_for_timeout(600)
    semantics = gp.eval_on_selector(
        "[data-age-gate]",
        """e=>({role:e.getAttribute('role'), modal:e.getAttribute('aria-modal'),
                label:!!e.getAttribute('aria-labelledby')})""",
    )
    check("the age gate is a labelled dialog",
          semantics["role"] == "dialog" and semantics["modal"] == "true" and semantics["label"],
          str(semantics))
    inside = []
    for _ in range(5):
        gp.keyboard.press("Tab")
        inside.append(gp.eval_on_selector(
            "[data-age-gate]", "e=>e.contains(document.activeElement)"))
    check("the age gate holds focus", all(inside), str(inside))
    gate_ctx.close()

    unlabelled = pg.eval_on_selector_all(
        "input, select, textarea",
        """els=>els.filter(e=>!e.labels?.length && !e.getAttribute('aria-label')
             && !e.getAttribute('aria-labelledby')).map(e=>e.tagName+'#'+(e.id||'?'))""",
    )
    check("every field has a label", not unlabelled, str(unlabelled))

    # Structured data is how a shop with a street address gets found at all.
    blocks = pg.evaluate(
        """()=>[...document.querySelectorAll('script[type="application/ld+json"]')]
             .map(s=>{try{return JSON.parse(s.textContent)['@type'];}catch(e){return 'INVALID';}})"""
    )
    check("the shop is described for search", "Store" in blocks, str(blocks))
    check("no structured data is malformed", "INVALID" not in blocks, str(blocks))
    ctx.close()


def check_marks(br):
    """The brand marks, after a sprite refactor broke both of these at once.

    Moving them into <symbol> + <use> dropped `fill="currentColor"` (which had
    lived on each file's <svg> root) and the viewBox. The marks went black —
    invisible on the green header — and, having no intrinsic size, fell back to
    the SVG default of 300px wide, which tore the two wordmark lines apart.
    Neither showed up in any assertion, only in a screenshot.
    """
    print("\nBrand marks")
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    pg = open_page(ctx, "/")
    # The site scrolls smoothly, so a rect read straight after scrollIntoView
    # is measured mid-flight and lands outside the frame.
    pg.add_style_tag(content="html{scroll-behavior:auto !important}")

    marks = pg.evaluate(
        r"""()=>{const out={count:0, bad:[]};
      document.querySelectorAll('.mark').forEach(m=>{
        const d=m.getBoundingClientRect();
        if(d.width<1||d.height<1) return;      // deliberately hidden
        out.count += 1;
        const cs=getComputedStyle(m);
        const ar=cs.aspectRatio.replace(/\s/g,'');
        if(ar==='auto'){out.bad.push(m.className+': no aspect-ratio'); return;}
        const parts=ar.split('/').map(Number);
        const want=parts[0]/parts[1], got=d.width/d.height;
        if(Math.abs(want-got)>0.05) out.bad.push(m.className+' ratio '+got.toFixed(2));
        if(!cs.maskImage || cs.maskImage==='none'){
          if(!cs.webkitMaskImage || cs.webkitMaskImage==='none')
            out.bad.push(m.className+': no mask');}
      });
      return out;}"""
    )
    check("marks are painted", marks["count"] > 5, f'{marks["count"]} visible')
    check("every mark keeps its shape and mask", not marks["bad"], str(marks["bad"][:3]))

    # Sampling CSS `color` here would be worthless: during the bug the parent's
    # color was gold the whole time, and the black came from the SVG's own
    # missing fill. Only the pixels tell the truth, so every mark is measured
    # against the colour it is supposed to take from its surroundings.
    # The header mark specifically: gold on green, or the logo is invisible.
    import io as _io

    from PIL import Image

    def painted_in(selector, target, label):
        # Scroll it in first: a clip outside the viewport is an error, not a
        # measurement.
        pg.eval_on_selector(selector, "e=>e.scrollIntoView({block:'center'})")
        pg.wait_for_timeout(300)
        box = pg.eval_on_selector(
            selector,
            "e=>{const b=e.getBoundingClientRect();"
            "return{x:b.x,y:b.y,width:b.width,height:b.height};}",
        )
        vh = pg.evaluate("window.innerHeight")
        vw = pg.evaluate("window.innerWidth")
        if not box or box["width"] < 2 or box["height"] < 2:
            check(f"{label} is on the page", False, "not rendered")
            return
        # Clamp to the frame rather than letting the screenshot throw.
        box["x"] = max(0, min(box["x"], vw - 2))
        box["y"] = max(0, min(box["y"], vh - 2))
        box["width"] = min(box["width"], vw - box["x"])
        box["height"] = min(box["height"], vh - box["y"])
        if box["width"] < 2 or box["height"] < 2:
            check(f"{label} could be measured", False, "outside the viewport")
            return
        im = Image.open(_io.BytesIO(pg.screenshot(clip=box))).convert("RGB")
        hit = sum(
            n for n, c in im.getcolors(400000)
            if all(abs(a - b) < 45 for a, b in zip(c, target))
        )
        check(f"{label} is painted in its own colour", hit > 300, f"{hit} matching pixels")

    # Only marks whose colour is far from black can be asserted this way. The
    # masthead wordmark is #16210b and the flute #260408 — both so close to
    # black that "did it fall back to black" is indistinguishable from "is it
    # correct", and a check that cannot fail is worse than none. The gold marks
    # carry the guard; the aspect-ratio assertion above covers the rest.
    painted_in(".brand", (211, 189, 141), "the header logo")
    painted_in(".footer__mark", (211, 189, 141), "the footer logo")
    ctx.close()


def check_links(br):
    """Every internal link and asset must resolve.

    A 404 on a stylesheet or a footer link is invisible until someone clicks
    it, and by then it is in production.
    """
    print("\nLinks and assets")
    ctx = br.new_context(viewport={"width": 1440, "height": 900})
    pg = open_page(ctx, "/")

    import urllib.parse
    import urllib.request

    pages = ["/", "/about.html", "/visit.html", "/privacy.html", "/404.html",
             "/shop.html", "/shop/single-malt-10.html"]
    seen, broken = set(), []
    for path in pages:
        pg.goto(BASE + path, wait_until="networkidle")
        refs = pg.evaluate(
            """()=>{const out=[];
              document.querySelectorAll('a[href]').forEach(a=>out.push(a.getAttribute('href')));
              document.querySelectorAll('link[href]').forEach(l=>out.push(l.getAttribute('href')));
              document.querySelectorAll('img[src], script[src]').forEach(e=>out.push(e.getAttribute('src')));
              return out;}"""
        )
        for ref in refs:
            if not ref or ref.startswith(("#", "mailto:", "tel:", "data:", "http")):
                continue
            target = urllib.parse.urljoin(BASE + path, ref.split("?")[0].split("#")[0])
            if target in seen:
                continue
            seen.add(target)
            try:
                code = urllib.request.urlopen(target, timeout=5).getcode()
            except Exception as exc:
                code = getattr(exc, "code", "error")
            if code != 200:
                broken.append(f"{path} -> {ref} ({code})")
    check(f"all {len(seen)} internal targets resolve", not broken, "; ".join(broken[:4]))

    # The card a link shows when it is shared.
    cards = pg.evaluate(
        """()=>[...document.querySelectorAll('meta[property="og:image"]')].map(m=>m.content)"""
    )
    check("the page declares a share card", bool(cards) and cards[0].endswith(".png"), str(cards))
    ctx.close()


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
            """()=>{const d=document.documentElement, f=document.querySelector('[data-facets]');
              return {overflow:d.scrollWidth-d.clientWidth,
                      page:d.scrollHeight,
                      filtersTop:Math.round(f.getBoundingClientRect().top),
                      firstCard:Math.round(document.querySelector('[data-grid] > li').getBoundingClientRect().top),
                      cols:new Set([...document.querySelectorAll('[data-grid] > li')]
                            .map(e=>Math.round(e.getBoundingClientRect().left))).size};}"""
        )
        check(f"{name}: no sideways overflow", m["overflow"] == 0, str(m["overflow"]))
        check(f"{name}: filter button above the fold", m["filtersTop"] < h, f"{m['filtersTop']} vs {h}")
        # The point of collapsing the panel: bottles on the first screen.
        check(f"{name}: a bottle is on the first screen", m["firstCard"] < h, f"{m['firstCard']} vs {h}")
        check(f"{name}: catalogue in two columns", m["cols"] == 2, f"{m['cols']} columns")
        # One column of tall cards made this 14 000px for twenty bottles.
        check(f"{name}: page under 9000px", m["page"] < 9000, f"{m['page']}px")

        # The panel is collapsed on a phone so the bottles come first; it has
        # to actually open, and filter, from the one button.
        check(f"{name}: filters start collapsed", not pg.is_visible("[data-facets] .facet__list"))
        pg.click("[data-facets-toggle]")
        pg.wait_for_timeout(250)
        check(f"{name}: the filter button opens the panel", pg.is_visible("[data-facets] .facet__list"))
        pg.click('[data-filter="rum"]')
        pg.wait_for_timeout(300)
        check(f"{name}: category filters", painted(pg) == 3, str(painted(pg)))
        check(f"{name}: active-filter badge shows", pg.inner_text("[data-facet-count]") == "1")

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

        # Opening the panel should put you in it, and Escape should get you out.
        pg.click("[data-facets-toggle]")
        pg.wait_for_timeout(300)
        check(f"{name}: opening the filters focuses the search",
              pg.evaluate("()=>document.activeElement.hasAttribute('data-search')"))
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        check(f"{name}: escape closes the filters",
              not pg.is_visible("[data-facets] .facet__list"))

        # The small-screen card rules share specificity with the base ones, so
        # source order decides. Placed too early they go inert while still
        # reading correctly in the CSS — assert the computed value, not the rule.
        card = pg.evaluate(
            """()=>{const c=document.querySelector('.card');
                    const m=document.querySelector('.card__media');
                    return {pad:parseFloat(getComputedStyle(c).paddingTop),
                            ar:m?getComputedStyle(m).aspectRatio:null,
                            frames:document.querySelectorAll('.card__media').length,
                            photos:document.querySelectorAll('.card__media img').length};}"""
        )
        check(f"{name}: compact card is in effect", card["pad"] < 18, f'padding {card["pad"]}px')
        # The frame is a slot held open for photographs that have not arrived.
        # It must be square, so the grid does not move when they do, and every
        # card must have one — a grid where some have frames and some do not
        # would be worse than either.
        check(f"{name}: every card holds a photo slot", card["frames"] == 20,
              f'{card["frames"]} frames on 20 cards')
        check(f"{name}: the slot is square", (card["ar"] or "").replace(" ", "") == "1/1",
              str(card["ar"]))
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


GROUPS = {
    "filters": check_filters,
    "fonts": check_fonts,
    "a11y": check_a11y,
    "marks": check_marks,
    "links": check_links,
    "mobile": check_mobile,
    "widths": check_widths,
    "grids": check_grids,
}


def main():
    if not (ROOT / "index.html").exists():
        sys.exit("nothing built yet — run python3 build.py first")

    # The whole suite takes two minutes, which is the wrong length for "did
    # that one change work". --only runs a group.
    wanted = list(GROUPS)
    if "--only" in sys.argv:
        names = sys.argv[sys.argv.index("--only") + 1].split(",")
        unknown = [n for n in names if n not in GROUPS]
        if unknown:
            sys.exit(f"unknown group(s): {', '.join(unknown)}. Pick from: {', '.join(GROUPS)}")
        wanted = names

    with server(), sync_playwright() as pw:
        br = pw.chromium.launch()
        for name in wanted:
            GROUPS[name](br)
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
