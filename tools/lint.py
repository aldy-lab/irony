#!/usr/bin/env python3
"""Refuse the things a browser check will not notice.

    python3 tools/lint.py

Two jobs:

**Copy consistency.** Straight quotes beside curly ones, a double space, a
place name spelled with diacritics in one sentence and without in the next —
none of it breaks anything, and all of it is what makes a careful site look
careless. Nothing else in this repository is watching the prose.

**Page weight.** The front page has been 1.13 MB, 188 KB and 28 KB during this
project's life. Nothing stopped it growing back except me remembering to
measure. A budget stops it without anyone remembering.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Gzipped, because that is what a visitor actually receives.
# Measured, then rounded up for room to work. Raising one is a decision to
# make on purpose, which is the entire point of writing them down.
BUDGET_KB = {
    "index.html": 10,
    "shop/single-malt-10.html": 8,
    "css/main.css": 14,
    "js/main.js": 9,
}

PROSE_FILES = ["data/site.json", "data/catalogue.json"]
PROSE_TEMPLATES = sorted((ROOT / "templates").glob("*.html"))

# Words that must be spelled the same way everywhere they appear.
CONSISTENT = [
    ("Nove Mesto", ["Nové Město", "Nove mesto", "nove mesto"]),
    ("Soukenicka", ["Soukenická", "soukenicka"]),
    ("catalogue", ["catalog"]),
    ("whisky", ["whiskey"]),
]


def prose_from(path: Path) -> list[tuple[int, str]]:
    """Lines of human-facing text, skipping markup and keys."""
    out = []
    text = path.read_text()
    if path.suffix == ".json":
        def walk(node, line_hint=0):
            if isinstance(node, str):
                out.append((line_hint, node))
            elif isinstance(node, dict):
                for k, v in node.items():
                    if k.startswith("_"):      # readme blocks are notes to us
                        continue
                    walk(v, line_hint)
            elif isinstance(node, list):
                for v in node:
                    walk(v, line_hint)
        walk(json.loads(text))
    else:
        # Text nodes only, and collapsed: stripping tags with a regex leaves
        # whitespace where markup was, and checking that for double spaces
        # reports every line in the file. A linter that cries wolf everywhere
        # gets ignored, which is worse than not having one.
        for i, line in enumerate(text.split("\n"), 1):
            without_markup = re.sub(r"<[^>]*>", "\x00", line)
            without_tokens = re.sub(r"\{\{[a-z0-9_]+\}\}", "\x00", without_markup)
            for chunk in without_tokens.split("\x00"):
                if len(chunk.strip()) > 2:
                    out.append((i, chunk))
    return out


def check_copy() -> list[str]:
    problems = []
    for name in PROSE_FILES + [str(p.relative_to(ROOT)) for p in PROSE_TEMPLATES]:
        path = ROOT / name
        for line_no, text in prose_from(path):
            where = f"{name}" + (f":{line_no}" if line_no else "")

            body = text.strip()
            # A run of spaces inside a sentence, not indentation around it.
            if re.search(r"\S {2,}\S", body):
                problems.append(f"{where}: double space — {body[:60]!r}")
            if "’" in text and "'" in text:
                problems.append(f"{where}: curly and straight apostrophes in one line")
            if re.search(r"\s--\s", text):
                problems.append(f"{where}: double hyphen where a dash belongs")
            if re.search(r"\bi\.e\.|\be\.g\.", text):
                problems.append(f"{where}: abbreviation in visitor-facing copy — {text.strip()[:50]!r}")

            for canonical, wrong_forms in CONSISTENT:
                for wrong in wrong_forms:
                    # Case-sensitive: matching "nove mesto" case-insensitively
                    # flags the correct "Nove Mesto" as wrong. Word boundaries
                    # too, or "catalog" matches inside "catalogue".
                    if re.search(rf"\b{re.escape(wrong)}\b", text):
                        problems.append(
                            f"{where}: {wrong!r} — this site spells it {canonical!r}"
                        )
    return problems


def check_orphan_classes() -> list[str]:
    """Classes used in markup that nothing styles.

    A plain substring search is not enough: `.tray__actions .link-quiet` makes
    the name appear in the stylesheet while leaving the class itself unstyled,
    which is exactly how the compare dialog ended up with a browser-default
    button. This looks for a selector where the class stands on its own.
    """
    css = "".join(
        (ROOT / "css" / name).read_text()
        for name in ("main.css", "marks.css")
        if (ROOT / "css" / name).exists()
    )
    # Strip descendant context: keep only the final simple selector of each part.
    styled = set()
    for selector in re.findall(r"([^{}]+)\{", css):
        for part in selector.split(","):
            last = part.strip().split()[-1] if part.strip() else ""
            styled.update(re.findall(r"\.([a-zA-Z][\w-]*)", last))

    used = set()
    sources = [ROOT / "build.py"] + sorted((ROOT / "templates").glob("*.html"))
    for f in sources:
        for group in re.findall(r'class="([^"{}]+)"', f.read_text()):
            used.update(group.split())

    # Hooks that carry no styling by design.
    structural = {"brand__line", "masthead__brand", "results", "compare__body", "sprite"}
    orphans = sorted(c for c in used if c not in styled and c not in structural)
    return [f"class {c!r} is used in markup but nothing styles it" for c in orphans]


def check_weight() -> list[str]:
    problems = []
    for name, limit in BUDGET_KB.items():
        path = ROOT / name
        if not path.exists():
            problems.append(f"{name}: missing — has it been renamed?")
            continue
        size = len(gzip.compress(path.read_bytes(), 9)) / 1024
        status = "ok " if size <= limit else "OVER"
        print(f"  {status} {name:32} {size:6.1f} KB gzipped (budget {limit})")
        if size > limit:
            problems.append(
                f"{name}: {size:.1f} KB gzipped, budget {limit} KB. "
                "Either make it smaller or raise the budget deliberately."
            )
    return problems


def main() -> int:
    print("Weight")
    weight = check_weight()
    print("\nUnstyled classes")
    orphans = check_orphan_classes()
    print("  " + ("\n  ".join(orphans) if orphans else "none"))

    print("\nCopy")
    copy = check_copy()
    if copy:
        for p in copy:
            print(f"  {p}")
    else:
        print("  consistent")

    problems = weight + orphans + copy
    if problems:
        print(f"\n{len(problems)} problem(s)")
        return 1
    print("\nnothing to report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
