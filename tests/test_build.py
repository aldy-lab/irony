#!/usr/bin/env python3
"""Unit tests for the pure functions in build.py.

    python3 tests/test_build.py

These run in under a second and need no browser. tools/check.py drives a real
browser and takes two minutes; it is the right tool for "does the page work"
and the wrong one for "does this function round correctly".

Written with unittest rather than pytest so CI needs no extra dependency.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402


class Money(unittest.TestCase):
    def test_groups_thousands_with_a_space(self):
        # The Czech convention, and it must match money() in js/main.js —
        # they disagreed once and the cart read 4,560 while a card read 4 560.
        self.assertEqual(build.money(4560), "4 560")
        self.assertEqual(build.money(990), "990")
        self.assertEqual(build.money(1000000), "1 000 000")

    def test_rounds_rather_than_truncates(self):
        self.assertEqual(build.money(989.6), "990")
        self.assertEqual(build.money(989.4), "989")

    def test_zero(self):
        self.assertEqual(build.money(0), "0")


class PerLitre(unittest.TestCase):
    def test_compares_sizes_honestly(self):
        # The whole point: 1150 for 500ml is dearer than 990 for 700ml.
        dearer = build.per_litre({"price": 1150, "volume": 500})
        cheaper = build.per_litre({"price": 990, "volume": 700})
        self.assertEqual(dearer, "2 300")
        self.assertEqual(cheaper, "1 414")

    def test_no_volume_says_nothing(self):
        self.assertEqual(build.per_litre({"price": 500, "volume": 0}), "")
        self.assertEqual(build.per_litre({"price": 500}), "")


class Fold(unittest.TestCase):
    def test_strips_diacritics_and_case(self):
        self.assertEqual(build.fold("Bečerovka"), "becerovka")
        self.assertEqual(build.fold("Plzeňský"), "plzensky")

    def test_leaves_plain_text_alone(self):
        self.assertEqual(build.fold("Single Malt"), "single malt")

    def test_search_text_carries_both_spellings(self):
        cats = {"gin": {"name": "Gin"}}
        product = {"name": "Bečerovka", "category": "gin", "notes": ""}
        haystack = build.search_text(product, cats)
        # Typed either way, it has to be found.
        self.assertIn("becerovka", haystack)
        self.assertIn("bečerovka", haystack)


class OpeningHours(unittest.TestCase):
    def test_expands_a_range_of_days(self):
        site = {"hours": [["Monday - Thursday", "12:00 - 22:00"]]}
        spec = build.opening_hours(site)[0]
        self.assertEqual(
            spec["dayOfWeek"], ["Monday", "Tuesday", "Wednesday", "Thursday"]
        )
        self.assertEqual(spec["opens"], "12:00")
        self.assertEqual(spec["closes"], "22:00")

    def test_a_single_day(self):
        site = {"hours": [["Sunday", "14:00 - 20:00"]]}
        self.assertEqual(build.opening_hours(site)[0]["dayOfWeek"], ["Sunday"])

    def test_a_range_that_wraps_the_week(self):
        site = {"hours": [["Friday - Monday", "12:00 - 24:00"]]}
        self.assertEqual(
            build.opening_hours(site)[0]["dayOfWeek"],
            ["Friday", "Saturday", "Sunday", "Monday"],
        )

    def test_nonsense_is_dropped_not_guessed(self):
        site = {"hours": [["Whenever", "sometimes"]]}
        self.assertEqual(build.opening_hours(site), [])


class New(unittest.TestCase):
    def test_recent_is_new(self):
        recent = (date.today() - timedelta(days=3)).isoformat()
        self.assertTrue(build.is_new({"added": recent}))

    def test_old_is_not(self):
        old = (date.today() - timedelta(days=200)).isoformat()
        self.assertFalse(build.is_new({"added": old}))

    def test_missing_or_broken_dates_are_not_new(self):
        self.assertFalse(build.is_new({}))
        self.assertFalse(build.is_new({"added": "last Tuesday"}))


class Escaping(unittest.TestCase):
    def test_a_name_cannot_break_out_of_an_attribute(self):
        # Product names come from a JSON file somebody edits by hand.
        self.assertEqual(
            build.esc('Gin "Navy" & <b>Strength</b>'),
            "Gin &quot;Navy&quot; &amp; &lt;b&gt;Strength&lt;/b&gt;",
        )


class Templating(unittest.TestCase):
    def test_an_unknown_token_is_an_error_not_a_blank(self):
        with self.assertRaises(KeyError):
            build.fill("{{nothing_supplies_this}}", {})

    def test_known_tokens_are_replaced(self):
        self.assertEqual(build.fill("a {{x}} c", {"x": "b"}), "a b c")


class Validation(unittest.TestCase):
    """The build must name the offending record, not raise from deep inside."""

    def setUp(self):
        self.site = {"url": "https://example.test"}
        self.catalogue = {
            "categories": [{"slug": "gin", "name": "Gin"}],
            "products": [
                {
                    "slug": "a-gin",
                    "name": "A Gin",
                    "category": "gin",
                    "price": 500,
                    "volume": 700,
                    "abv": 40,
                }
            ],
        }

    def test_good_data_passes(self):
        build.validate(self.site, self.catalogue)  # must not raise

    def test_unknown_category_is_rejected(self):
        self.catalogue["products"][0]["category"] = "whiskey"
        with self.assertRaises(SystemExit):
            build.validate(self.site, self.catalogue)

    def test_a_price_as_text_is_rejected(self):
        self.catalogue["products"][0]["price"] = "500"
        with self.assertRaises(SystemExit):
            build.validate(self.site, self.catalogue)

    def test_duplicate_slugs_are_rejected(self):
        self.catalogue["products"].append(dict(self.catalogue["products"][0]))
        with self.assertRaises(SystemExit):
            build.validate(self.site, self.catalogue)

    def test_a_malformed_date_is_rejected(self):
        self.catalogue["products"][0]["added"] = "24/09/2026"
        with self.assertRaises(SystemExit):
            build.validate(self.site, self.catalogue)


if __name__ == "__main__":
    unittest.main(verbosity=2)
