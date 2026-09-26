#!/usr/bin/env python3
"""Compare the rendered pages against approved screenshots.

    python3 tools/visual.py            # compare against tests/baseline/
    python3 tools/visual.py --approve  # accept what is on screen as the new truth

Everything else asserted here is a number: a ratio, a width, a colour at one
point. A layout can come apart in ways no number notices — a heading that
wraps into a heap, a section that collapses — and only a picture catches that.

A difference is not a failure: it is a question. Look at the diff written to
tests/diff/, and either fix the page or approve the change deliberately.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "tests" / "baseline"
DIFF = ROOT / "tests" / "diff"
PORT = 8797
BASE = f"http://127.0.0.1:{PORT}"

# Wide and narrow, because they are different layouts rather than one resized.
VIEWS = [
    ("home-wide", "/", 1440, 1000),
    ("home-narrow", "/", 390, 1200),
    ("bottle-wide", "/shop/single-malt-10.html", 1440, 900),
    ("bottle-narrow", "/shop/single-malt-10.html", 390, 1000),
    ("about", "/about.html", 1440, 1000),
    ("visit", "/visit.html", 1440, 900),
    ("notfound", "/404.html", 1440, 900),
    ("privacy", "/privacy.html", 1440, 900),
]

# A handful of pixels differ between runs from antialiasing alone.
TOLERANCE = 0.001

# The baselines are Linux renders, because CI is where they are enforced and
# CI runs ubuntu. Chromium lays the same sentence out at slightly different
# widths on macOS — different glyph advances, accumulating across a line —
# so a page with no change at all comes out 2-10% different here. Approving
# on a Mac therefore committed baselines that could only ever fail in CI,
# which is what had the check red for weeks while the pages were fine.
#
# So: Linux judges, everything else looks. Off-platform the screenshots are
# still taken and still written to tests/diff/, because seeing the page is
# most of what this tool is for; they just do not decide anything.
JUDGES = "linux"


@contextmanager
def server():
    import socket

    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            sys.exit(f"port {PORT} is busy — another server would be compared, not this build")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        import urllib.request

        for _ in range(50):
            try:
                urllib.request.urlopen(f"{BASE}/index.html", timeout=1).read(1)
                break
            except Exception:
                time.sleep(0.1)
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def capture(pw, name, path, width, height) -> Path:
    ctx = pw.chromium.launch().new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        is_mobile=width < 760,
        has_touch=width < 760,
        reduced_motion="reduce",  # no animation mid-shot
    )
    page = ctx.new_page()
    # The header says "Open until 22:00" or "Closed - opens tomorrow 12:00"
    # depending on the wall clock, so an unfrozen screenshot of any page
    # disagrees with its baseline by the time of day rather than by a change
    # anyone made. set_fixed_time pins Date without freezing timers, which
    # would stop the page's own deferred work. Thursday, inside opening hours.
    page.clock.set_fixed_time(datetime(2026, 1, 15, 15, 0, 0))
    page.goto(f"{BASE}/", wait_until="load")
    page.evaluate("try{localStorage.setItem('ivs.age.v1','true')}catch(e){}")
    page.goto(BASE + path, wait_until="networkidle")
    page.add_style_tag(
        content="html{scroll-behavior:auto!important} *{animation:none!important;"
        "transition:none!important}"
    )
    page.evaluate(
        "document.querySelectorAll('[data-reveal]')"
        ".forEach(e=>e.setAttribute('data-revealed','true'))"
    )
    page.evaluate("document.querySelectorAll('[data-grid]')"
                  ".forEach(g=>g.setAttribute('data-settled','true'))")
    # networkidle says the bytes arrived, not that the picture is on screen:
    # a WebP still has to decode, and a shot taken in between differed from the
    # same page by 8% one run to the next. A full-page screenshot also shows
    # rows that were never scrolled to, whose lazy images have not begun to
    # load at all, so those are asked for eagerly first and then decoded.
    page.evaluate(
        """() => {
             document.querySelectorAll('img[loading=lazy]')
               .forEach(i => { i.loading = 'eager'; });
           }"""
    )
    page.wait_for_function(
        "() => Array.from(document.images).every(i => i.complete)", timeout=20000
    )
    page.evaluate(
        """() => Promise.all(
             Array.from(document.images).map(i => i.decode().catch(() => {}))
           ).then(() => new Promise(r => requestAnimationFrame(
             () => requestAnimationFrame(r))))"""
    )
    page.wait_for_timeout(500)
    shot = DIFF / f"{name}.now.png"
    page.screenshot(path=str(shot), full_page=True)
    ctx.close()
    return shot


def compare(now: Path, approved: Path, name: str) -> tuple[bool, str]:
    from PIL import Image, ImageChops

    a = Image.open(now).convert("RGB")
    b = Image.open(approved).convert("RGB")

    note = ""
    if a.size != b.size:
        # A height change used to end the comparison here, which answered
        # "did it change" and not "what changed" — the only question worth
        # asking. Pad both onto the same canvas and carry on.
        note = f"height {b.height} -> {a.height}; "
        width = max(a.width, b.width)
        height = max(a.height, b.height)
        canvas_a = Image.new("RGB", (width, height), (255, 255, 255))
        canvas_b = Image.new("RGB", (width, height), (255, 255, 255))
        canvas_a.paste(a, (0, 0))
        canvas_b.paste(b, (0, 0))
        a, b = canvas_a, canvas_b

    diff = ImageChops.difference(a, b)
    changed = sum(1 for px in diff.getdata() if px != (0, 0, 0))
    share = changed / (a.width * a.height)
    if share <= TOLERANCE and not note:
        return True, f"{share:.4%}"

    # Mark where, so the question is answerable at a glance.
    mask = diff.convert("L").point(lambda v: 255 if v > 12 else 0)
    marked = a.copy()
    marked.paste(Image.new("RGB", a.size, (255, 0, 120)), mask=mask)
    marked.save(DIFF / f"{name}.diff.png")
    return False, f"{note}{share:.2%} of pixels differ — see tests/diff/{name}.diff.png"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is required")

    approve = "--approve" in sys.argv
    judging = sys.platform.startswith(JUDGES)
    if not judging:
        print(
            f"Rendering on {platform.system()}; the baselines are Linux renders, so the\n"
            "numbers below are platform difference, not change. Look at the pictures in\n"
            "tests/diff/ — CI decides.\n"
        )
        if approve:
            sys.exit(
                "refusing to approve from here: these renders would fail in CI.\n"
                "Approve where the baselines are made — push the change and let CI "
                "render it, or run this on Linux."
            )
    BASELINE.mkdir(parents=True, exist_ok=True)
    DIFF.mkdir(parents=True, exist_ok=True)

    failures, new = [], []
    with server(), sync_playwright() as pw:
        for name, path, width, height in VIEWS:
            shot = capture(pw, name, path, width, height)
            approved = BASELINE / f"{name}.png"

            if approve or not approved.exists():
                approved.write_bytes(shot.read_bytes())
                (new if not approve else []).append(name)
                print(f"  {'approved' if approve else 'new baseline'}  {name}")
            else:
                ok, detail = compare(shot, approved, name)
                label = "same    " if ok else ("CHANGED " if judging else "differs ")
                print(f"  {label}  {name}  ({detail})")
                if not ok and judging:
                    failures.append(name)
            # A failing view keeps its fresh render beside the marked-up diff.
            # CI is the only machine that renders the baselines, so when it
            # disagrees the artifact has to contain the thing that would
            # replace them, not only a picture of the disagreement.
            if judging and ok:
                shot.unlink(missing_ok=True)

    if approve:
        print("\nbaselines approved")
        return 0
    if new:
        print(f"\n{len(new)} view(s) had no baseline and were recorded — commit tests/baseline/")
    if failures:
        print(
            f"\n{len(failures)} view(s) changed: {', '.join(failures)}\n"
            "Look at tests/diff/*.diff.png. If the change is wanted, run with "
            "--approve — or, from a machine that does not render the baselines, "
            "promote the *.now.png files this left behind."
        )
        return 1
    if not judging:
        print(
            "\nnothing judged here — the screenshots are in tests/diff/ to look at."
        )
        return 0
    print("\nevery view matches its approved screenshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
