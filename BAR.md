# Irony vs. Satyr — the bar

The shop catalogue is parked. What this site presents from here is the bar:
the drinks, the room, and a menu a guest reaches by scanning a coaster.

## Decided

| | |
|---|---|
| Where | This repository. The design system, the satyr, the build, the 131 checks and the fixed caching all carry over. |
| Menu data | Supabase, so the owner changes a price and the site and the QR menu change with it. |
| Cocktail visuals | Rendered from the 3D cocktail system, one source for both the "build your cocktail" page and the stills in the menu. |
| Order of work | The menu and the coaster first — the things a guest holds — then the presentation site and the 3D. |

## What is in hand

`data/menu.json`, imported from the bar's own Poster menu by
`tools/import_menu.py`:

- **77 drinks** in **14 categories**, 32 of them cocktails
- prices in CZK, 60–465
- **46 descriptions in each of English, Czech and Ukrainian**, separated

The separation is the work. In the bar's menu all three languages sit in one
field, so today a guest reading any one of them reads all three. The importer
cuts them apart, and `tests/test_import_menu.py` holds the eighteen cases it
got wrong on the way — an English sentence beginning "A ...", a Cyrillic "С"
used as the C in a "CZ" heading, a Cyrillic vowel inside a Czech word, the
markers CZ/UKR/ENG on a line of their own, languages divided by a slash where
"tonic/cola" must survive intact.

Run it again whenever the bar's menu changes:

```sh
python3 tools/import_menu.py --from tools/fixtures/poster-menu.json --report
```

It exits non-zero while anything is still wrong, and names the drink.

## Waiting on the bar

**Three descriptions have the alphabets mixed inside words** and need
retyping by someone who reads them — a parser that "fixes" this is guessing
at a menu:

- Tajin Margarita Cocktail
- Adriatico Amaretto Sweet and Sour
- Pelinkovac + TH Tonic (has `Выznačuje`, with a Cyrillic В and ы)

**Thirty drinks have no description at all**, among them Pisco Sour,
Caipirinha, Mezcalita Vida and every shot. Fine for a spirits list, thin for
a cocktail the guest is choosing between.

**Names to confirm.** `Skinny Bitch by Nemiroff Delikat` (295) and
`Skiny beatch` (295) look like the same drink entered twice; `Pinnaple
Daiquiri` is misspelt, and its description is for a Banana Daiquiri;
`Del Maguey Mezcal Vida 40 ml Mexico»` carries a stray `»`.

**Google Maps place.** The coaster's second code points at the bar's review
page. That needs the Place ID, which only the bar's own listing gives.

**Address, hours, contact** for the presentation site.

## Not taken from Poster

Their 73 images are not imported. Three are line engravings from what looks
like a bought illustration set, one is a stock photograph of a framed poster,
one is the logo standing in where a drink should be, and one is a phone
photograph of the bar. Mixed provenance, mixed quality, and a licence to use
artwork inside Poster is not a licence to publish it on the bar's own site.
`poster_photo` keeps the URL so a drink can be matched later; nothing reads it.
