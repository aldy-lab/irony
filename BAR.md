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

## The owner edits the menu

`/admin/` — unlinked, noindex, and told to nobody who does not need it. What
refuses a stranger is the database, not the address: every write is rejected
unless the caller is signed in **and** listed in `irony.editors`. An
anonymous write answers 401, and a browser check asserts that it still does.

The data lives in an `irony` schema inside the **LitProfit calculator**
Supabase project (`uiuzbhekmroosmemwhdr`), beside the `iberia` schema that
already shares it. A sixth project on the Pro plan costs about ten dollars a
month; this costs nothing. Nothing here touches `public`.

The public menu still ships with the whole list built into the page, and what
comes from the store is laid over the top. If the store is slow it gives up
after six seconds; if it is unreachable, or switched off by blanking
`menu_store.url` in `data/site.json`, the menu is simply the one that was
built. A bar's wifi is not something to bet a menu on.

**Done.** `vadym.kondratenko@irony.com` is the account, created in the
dashboard and added to `irony.editors`. Checked both ways under his own
identity in a transaction that was rolled back: his update passes the policy,
and a signed-in account that is not in `editors` changes zero rows.

Another editor is two lines: create the user in the dashboard, then

```sql
insert into irony.editors (user_id, email)
select id, email from auth.users where lower(email) = lower('...');
```

Three drinks are in the store so far. The editor's "Start again from the
published list" writes all 77 over it in one go — that is the first thing to
press after signing in.

## Waiting on the bar

**Five drinks still need the bar to say what is in them.** Everything else
now has a description in all three languages — coverage went from 60% to 92%
— but these are the bar's own inventions, and a menu that lists an ingredient
a drink does not contain is a problem with allergens and with the guest who
ordered it:

- **ALL Shot** (185) — what is in it?
- **Skinny Bitch by Nemiroff Delikat** (295) — assumed vodka, soda, lime
- **Skiny beatch** (265) — the same drink at a different price, or not?
- **Mezcalita vida** (465) — the dearest drink on the list, assumed a mezcal
  margarita on Del Maguey Vida
- **White wine 200 ml Italy** — which wine?

The written descriptions are in `data/menu-notes.json`, apart from the
imported data, and never overwrite the bar's own words. **Have a Czech and a
Ukrainian speaker read them before anything is printed** — they are written
to be correct rather than translated word for word, but they are ours.

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

## Known and parked

The bottle catalogue's five screenshot baselines would not render the same
twice in CI. Two causes were found and fixed — a New badge measured against
today's date, and `content-visibility: auto` letting Chromium skip what it
judged off screen — and a third survived both. They are parked with the
catalogue in `tools/visual.py`, and the menu's two views took their place.
Every parked page is still covered by the browser checks.

## Not taken from Poster

Their 73 images are not imported. Three are line engravings from what looks
like a bought illustration set, one is a stock photograph of a framed poster,
one is the logo standing in where a drink should be, and one is a phone
photograph of the bar. Mixed provenance, mixed quality, and a licence to use
artwork inside Poster is not a licence to publish it on the bar's own site.
`poster_photo` keeps the URL so a drink can be matched later; nothing reads it.
