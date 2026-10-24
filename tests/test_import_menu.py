#!/usr/bin/env python3
"""Unit tests for pulling the bar's three languages apart.

    python3 tests/test_import_menu.py

Every case here is one the importer actually got wrong against the bar's real
menu. The failures all had the same shape: a language quietly absorbed into
another, no error anywhere, and a menu that reads in two languages at once to
whoever opens it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import import_menu as im  # noqa: E402


class DetectsLanguage(unittest.TestCase):
    def test_plain_english(self):
        self.assertEqual(im.language_of("A classic combination of dry gin"), "en")

    def test_an_english_sentence_opening_with_the_article(self):
        # "a" is a Czech conjunction as well as an English article. It was in
        # the Czech word list, so every English sentence that began "A ..."
        # was filed as Czech and glued onto the Czech text.
        self.assertEqual(im.language_of("A little tomato juice and lime"), "en")

    def test_czech_by_its_diacritics(self):
        self.assertEqual(im.language_of("klasická kombinace suchého ginu"), "cs")

    def test_ukrainian_by_its_script(self):
        self.assertEqual(im.language_of("класичне поєднання сухого джину"), "uk")

    def test_one_cyrillic_letter_inside_a_czech_word_is_still_czech(self):
        # The bar's own text has "Выznačuje" and a Cyrillic "с" for a Latin
        # "s". Reading any Cyrillic as Ukrainian pulled 750 characters of
        # English and Czech into the Ukrainian field.
        self.assertEqual(
            im.language_of("Выznačuje se výraznou bylinnou vůní a hořkostí"), "cs"
        )

    def test_nothing_to_go_on(self):
        self.assertEqual(im.language_of("---"), "")
        self.assertEqual(im.language_of("40 %"), "")


class SplitsDescriptions(unittest.TestCase):
    def test_blank_lines(self):
        text, unplaced = im.split_description(
            "A classic combination of dry gin\n\n"
            "klasická kombinace suchého ginu\n\n"
            "класичне поєднання сухого джину"
        )
        self.assertEqual(set(text), {"en", "cs", "uk"})
        self.assertNotIn("klasická", text["en"])
        self.assertEqual(unplaced, [])

    def test_a_heading_line_naming_the_language(self):
        text, _ = im.split_description(
            "English\n\nThe Basil Smash is refreshing\n\n"
            "Český\n\nBasil Smash je osvěžující\n\n"
            "Українська\n\nBasil Smash – це освіжаючий"
        )
        self.assertEqual(set(text), {"en", "cs", "uk"})
        self.assertNotIn("English", text["en"])

    def test_a_heading_written_with_a_cyrillic_lookalike(self):
        # "СZ" with a Cyrillic С reads as Czech to a person and as Ukrainian
        # to a parser, so the Czech section was filed under Ukrainian.
        text, _ = im.split_description(
            "A classic cocktail of dry gin\nСZ\nKlasický koktejl ze suchého ginu"
        )
        self.assertIn("Klasický", text.get("cs", ""))
        self.assertNotIn("Klasický", text.get("uk", ""))

    def test_three_letter_markers(self):
        text, _ = im.split_description(
            "a little tomato juice\nCZ\ntrochu rajčatové šťávy\nUKR\nтрохи томатного соку"
        )
        self.assertEqual(set(text), {"en", "cs", "uk"})

    def test_languages_divided_by_a_slash(self):
        text, _ = im.split_description(
            "Klasický koktejl ginu a Luxardo Maraschino/ "
            "Classic cocktail of gin and Luxardo Maraschino/"
            "Класичний коктейль з джину"
        )
        self.assertEqual(set(text), {"en", "cs", "uk"})

    def test_a_slash_inside_one_language_survives(self):
        # The slash is a divider between languages and a word inside one.
        # Splitting on it and rejoining carelessly turned "tonic/cola" into
        # "tonic cola".
        text, _ = im.split_description("Serve on the rocks or mixed with tonic/cola")
        self.assertIn("tonic/cola", text["en"])

    def test_the_bar_signs_every_description_and_it_is_dropped(self):
        text, _ = im.split_description(
            "Irony vs.Satyr Bar Praha\n\nWe use a special ginger lemonade"
        )
        self.assertNotIn("Satyr", text["en"])
        self.assertIn("ginger lemonade", text["en"])

    def test_empty(self):
        self.assertEqual(im.split_description(""), ({}, []))
        self.assertEqual(im.split_description("   \n\n  "), ({}, []))


class Audits(unittest.TestCase):
    """The import must say so when a field holds the wrong language."""

    def menu(self, text):
        return {"products": [{"name": "X", "text": text}]}

    def test_clean_split_passes(self):
        self.assertEqual(im.audit(self.menu({
            "en": "A classic combination of dry gin",
            "cs": "klasická kombinace suchého ginu",
            "uk": "класичне поєднання сухого джину",
        })), [])

    def test_english_holding_czech_is_reported(self):
        problems = im.audit(self.menu({
            "en": "A classic combination klasická kombinace suchého",
            "cs": "klasická kombinace suchého ginu",
        }))
        self.assertTrue(any("Czech letters" in p for p in problems))

    def test_two_languages_in_one_field_is_reported_by_length(self):
        problems = im.audit(self.menu({
            "en": "A classic combination of dry gin with bitterness and vermouth too",
            "uk": "класичне",
        }))
        self.assertTrue(any("two languages in one field" in p for p in problems))

    def test_identical_text_in_two_languages_is_reported(self):
        problems = im.audit(self.menu({"en": "Negroni", "cs": "Negroni"}))
        self.assertTrue(any("identical" in p for p in problems))


if __name__ == "__main__":
    unittest.main(verbosity=2)
