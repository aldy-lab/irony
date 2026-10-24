#!/usr/bin/env python3
"""Turn the bar's Poster QR menu into data this site can build from.

    python3 tools/import_menu.py --from tools/fixtures/poster-menu.json
    python3 tools/import_menu.py --report        # what came in, what is missing

The bar already runs a menu at menu.ps.me, and its 79 items are the real
content: names, prices in CZK, categories and descriptions. The descriptions
are the problem. Every one of them carries English, Czech and Ukrainian run
together in a single field, so a guest reading any one language reads all
three — and the bar's own name is repeated at the top of most of them.

This splits that field by looking at each paragraph: Cyrillic letters mean
Ukrainian, Czech-only diacritics or Czech function words mean Czech, and what
is left is English. It is a guess, and a guess that is wrong in silence is
worse than one that admits it, so every paragraph it cannot place is reported
rather than filed under English.

Nothing here downloads their photographs. Three of the ones we looked at are
line engravings in a stock illustration style, one is a framed-poster mockup,
and one is the logo standing in for a drink. Republishing artwork the bar may
only have a licence to use in Poster is the client's exposure, not ours to
take on quietly.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Letters Czech has and no other language here does. Ukrainian is caught by
# its script, so these only have to separate Czech from English.
CZECH_LETTERS = set("ěščřžýáíéůúňťďó")

# Czech words for a paragraph too short to carry a diacritic. Every one of
# these has to be a word English does not also have: "a" was in this list,
# and because English sentences begin "A classic combination of dry gin...",
# every such paragraph was filed as Czech and glued onto the Czech one. The
# English text then vanished from the menu without anything failing. Czech
# almost always brings a diacritic with it, so this list is a fallback and
# stays small rather than clever.
CZECH_WORDS = {
    "nebo", "jako", "jeho", "jejich", "ktery", "ktera", "ktere", "nase",
    "nasi", "koktejl", "napoj", "sklenice", "lahev", "klasicky", "klasicka",
    "svezi", "jemny", "chutna", "vyrazny",
}

# Rules dividing a run of text, written down once so the splitter and the
# check that follows it cannot drift apart.
SEPARATOR = re.compile(r"^[\s\-–—_=*.]+$")

# The bar signs its own descriptions, every time, in several spellings.
SIGNATURES = re.compile(
    r"^\s*irony\s*vs\.?\s*satyr(\s+bar)?(\s+praha)?\s*[.:—-]*\s*", re.I
)

# Poster writes the language's own name at the head of some paragraphs.
LANGUAGE_LABELS = re.compile(
    r"^\s*(english|anglicky|czech|česky|český|ukrainian|українська|украї?нський)"
    r"\s*[:：-]\s*", re.I
)


# A line that is nothing but the name of a language is a divider. It has to
# tolerate the alphabets being mixed: one description marks its Czech section
# "CZ" with a Cyrillic С, which is invisible to a reader and meant that the
# Czech text was filed as Ukrainian because of its own heading.
_C, _Z = "[CcСс]", "[ZzЗз]"
_E, _N = "[EeЕе]", "[NnНн]"
_U, _A, _K = "[UuУу]", "[AaАа]", "[KkКк]"
_R, _G = "[RrРр]", "[GgГг]"
MARKER_LINE = re.compile(
    r"^[ \t]*(?:"
    + _C + _Z + _E + "?|" + _E + _N + _G + "?|" + _U + _A + "|" + _U + _K + _R + "?"
    + r"|english|anglicky|czech|[cč]esk[yý]|[cč]e[sš]tina"
    + r"|ukrainian|укра[иії]нськ[аий]*|украинск[аиой]*"
    + r")[ \t]*[:：\-]?[ \t]*$",
    re.I | re.M,
)


def fold(text: str) -> str:
    """Lowercase, without diacritics, for comparing words."""
    stripped = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in stripped if unicodedata.category(c) != "Mn")


def language_of(paragraph: str) -> str:
    """'uk', 'cs', 'en', or '' when the text gives nothing to go on.

    By which script dominates, not by whether a script appears at all. The
    bar's own text mixes alphabets inside single words — "Bыznacuje" with a
    Cyrillic vowel, a Cyrillic "c" standing in for a Latin "s" — and a rule
    that read one Cyrillic character as Ukrainian swallowed whole English and
    Czech passages into the Ukrainian field, 750 characters of them.
    """
    cyrillic = len(re.findall(r"[Ѐ-ӿ]", paragraph))
    latin = len(re.findall(r"[A-Za-z\u00C0-\u024F]", paragraph))
    if cyrillic and cyrillic >= latin:
        return "uk"
    letters = set(paragraph.lower())
    if letters & CZECH_LETTERS:
        return "cs"
    words = {fold(w) for w in re.findall(r"[^\W\d_]+", paragraph, re.UNICODE)}
    if not words:
        return ""
    if words & CZECH_WORDS:
        return "cs"
    # Latin letters and nothing Czech about them.
    if re.search(r"[a-z]", paragraph, re.I):
        return "en"
    return ""


def split_description(raw: str) -> tuple[dict, list]:
    """Pull one mixed description apart into languages, and say what failed.

    The bar separates its three languages four different ways, sometimes in
    one field: a blank line, a full stop, a slash, and an inline marker like
    "CZ" or a flag. So the text is cut at every one of those, each piece is
    read on its own, and neighbouring pieces in the same language are joined
    back together with the separator they were divided by — or "tonic/cola"
    would come back as "tonic cola".
    """
    text = (raw or "").replace("\r\n", "\n").strip()
    if not text:
        return {}, []

    # A heading line naming a language becomes a break of its own.
    text = MARKER_LINE.sub("\n\n", text)
    # An inline marker becomes a break of its own.
    text = re.sub(r"\s*(?:\U0001F1E8\U0001F1FF|\U0001F1FA\U0001F1E6)\s*",
                  "\n\n", text)
    text = re.sub(r"(?<=[\.\!\?])\s+(?=(?:CZ|EN|UA|UK)\b[ :])", "\n\n", text)

    out: dict = {}
    unplaced: list = []

    # Keeping the separators, so same-language pieces can be put back exactly.
    divider = re.compile(r"((?<=[\.\!\?])\s+|\s*/\s*|\n\s*\n)")

    for block in re.split(r"\n\s*\n", text):
        if not block.strip():
            continue
        parts = divider.split(block)
        pieces = parts[0::2]
        seps = parts[1::2] + [""]

        run, run_code, run_seps = [], None, []
        def flush():
            if not run:
                return
            joined = run[0]
            for sep, piece in zip(run_seps, run[1:]):
                joined += sep + piece
            joined = SIGNATURES.sub("", joined).strip()
            joined = LANGUAGE_LABELS.sub("", joined).strip()
            if not joined or SEPARATOR.match(joined):
                return
            if run_code:
                out[run_code] = (f"{out[run_code]} {joined}".strip()
                                 if run_code in out else joined)
            else:
                unplaced.append(joined[:60])

        for piece, sep in zip(pieces, seps):
            cleaned = LANGUAGE_LABELS.sub("", SIGNATURES.sub("", piece)).strip()
            code = language_of(cleaned) if cleaned else None
            if code and run_code and code != run_code:
                flush()
                run, run_seps = [], []
            if code:
                run_code = code
            run.append(piece)
            run_seps.append(sep)
        flush()
        run, run_code, run_seps = [], None, []

    return out, unplaced


def slug(text: str) -> str:
    base = fold(text)
    base = re.sub(r"&", " and ", base)
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "item"


# Poster lists a highlighted drink twice: once in its real category and once
# in "New and popular". That is a label on one drink, not two drinks, and
# importing it as a category produced two products sharing a slug — which the
# build rejects, and which would have given one cocktail two pages.
PROMOTED = {"new-and-popular", "popular"}


def convert(items: list) -> tuple[dict, dict]:
    categories: dict = {}
    products = []
    notes = {"no_description": [], "unplaced": [], "no_price": [], "no_photo": []}

    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        category = (item.get("categoryName") or "").strip() or "Other"
        key = slug(category)
        categories.setdefault(key, {"slug": key, "name": category, "count": 0})
        categories[key]["count"] += 1

        text, unplaced = split_description(item.get("description", ""))
        if not text:
            notes["no_description"].append(name)
        if unplaced:
            notes["unplaced"].append({"name": name, "paragraphs": unplaced})
        price = item.get("price")
        if not price:
            notes["no_price"].append(name)
        if not item.get("photo"):
            notes["no_photo"].append(name)

        products.append({
            "slug": slug(name),
            "name": name,
            "category": key,
            "price": price,
            "popular": key in PROMOTED,
            "text": text,
            # Kept for matching only, never served: see the note at the top.
            "poster_id": item.get("productId"),
            "poster_photo": item.get("photo") or "",
        })

    # One drink, however many lists it appears on.
    merged: dict = {}
    for product in products:
        existing = merged.get(product["slug"])
        if not existing:
            merged[product["slug"]] = product
            continue
        existing["popular"] = existing["popular"] or product["popular"]
        if existing["category"] in PROMOTED:
            existing["category"] = product["category"]
        for code, value in product["text"].items():
            existing["text"].setdefault(code, value)
    products = list(merged.values())

    # The counts were taken before the merge and now name drinks twice.
    categories = {k: v for k, v in categories.items() if k not in PROMOTED}
    for category in categories.values():
        category["count"] = sum(1 for p in products if p["category"] == category["slug"])

    menu = {
        "_readme": [
            "Imported from the bar's Poster menu by tools/import_menu.py.",
            "`text` holds one entry per language: en, cs, uk.",
            "`poster_photo` is a reference for matching, not for publishing.",
        ],
        "currency": "CZK",
        "categories": list(categories.values()),
        "products": products,
    }
    return menu, notes


def audit(menu: dict) -> list:
    """Catch a language holding another language's words.

    The split is a guess, and the way it failed the first time was silent:
    English paragraphs were filed as Czech and glued onto the Czech text, so
    `en` was empty and `cs` was twice as long and nothing anywhere failed.
    These are the assertions that would have said so.
    """
    problems = []
    for product in menu["products"]:
        text = product["text"]
        name = product["name"]

        english = text.get("en", "")
        if re.search(r"[\u0400-\u04FF]", english):
            problems.append(f"{name}: the English text contains Cyrillic")
        if set(english.lower()) & CZECH_LETTERS:
            problems.append(f"{name}: the English text contains Czech letters")

        czech = text.get("cs", "")
        if re.search(r"[\u0400-\u04FF]", czech):
            problems.append(f"{name}: the Czech text contains Cyrillic")
        if czech and not (set(czech.lower()) & CZECH_LETTERS) \
                and not ({fold(w) for w in re.findall(r"[^\W\d_]+", czech)}
                         & CZECH_WORDS):
            problems.append(f"{name}: nothing about the Czech text is Czech")

        ukrainian = text.get("uk", "")
        if ukrainian and not re.search(r"[\u0400-\u04FF]", ukrainian):
            problems.append(f"{name}: the Ukrainian text has no Cyrillic")

        # Two languages holding the same words means one of them was never
        # written and something else was copied into it.
        for a, b in (("en", "cs"), ("en", "uk"), ("cs", "uk")):
            if text.get(a) and text.get(a) == text.get(b):
                problems.append(f"{name}: {a} and {b} hold identical text")

        # A description two or three times longer than its siblings is the
        # shape of two languages glued together.
        lengths = {c: len(t) for c, t in text.items() if t}
        if len(lengths) > 1:
            longest = max(lengths, key=lengths.get)
            others = [v for k, v in lengths.items() if k != longest]
            if lengths[longest] > 1.9 * max(others):
                problems.append(
                    f"{name}: the {longest} text is {lengths[longest]} characters"
                    f" against {max(others)} — two languages in one field?")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="source", required=True)
    parser.add_argument("--out", default="data/menu.json")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    items = json.loads(Path(args.source).read_text())
    menu, notes = convert(items)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(menu, ensure_ascii=False, indent=2) + "\n")

    counts = {code: sum(1 for p in menu["products"] if code in p["text"])
              for code in ("en", "cs", "uk")}
    print(f"{len(menu['products'])} items in {len(menu['categories'])} categories"
          f" -> {out.relative_to(ROOT)}")
    print(f"  descriptions: en {counts['en']}  cs {counts['cs']}  uk {counts['uk']}")
    print(f"  no description at all: {len(notes['no_description'])}")
    print(f"  paragraphs no language could be read from: {len(notes['unplaced'])}")
    if notes["no_price"]:
        print(f"  ! no price: {', '.join(notes['no_price'])}")

    problems = audit(menu)
    print(f"  audit: {len(problems)} problem(s)")
    for line in problems:
        print(f"    ! {line}")

    if args.report:
        print("\nItems with no description:")
        for name in notes["no_description"]:
            print(f"  - {name}")
        print("\nParagraphs that could not be placed:")
        for row in notes["unplaced"]:
            print(f"  - {row['name']}: {row['paragraphs']}")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
