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

import subprocess
import sys
import time
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
                print(f"  {'same    ' if ok else 'CHANGED '}  {name}  ({detail})")
                if not ok:
                    failures.append(name)
            shot.unlink(missing_ok=True)

    if approve:
        print("\nbaselines approved")
        return 0
    if new:
        print(f"\n{len(new)} view(s) had no baseline and were recorded — commit tests/baseline/")
    if failures:
        print(
            f"\n{len(failures)} view(s) changed: {', '.join(failures)}\n"
            "Look at tests/diff/*.diff.png. If the change is wanted, run with --approve."
        )
        return 1
    print("\nevery view matches its approved screenshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
