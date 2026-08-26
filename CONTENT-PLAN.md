# Content and SEO plan

How the wiki, tutorials and news sections are built, how to add to them, and
where the remaining search opportunity is.

## What exists now

| Section | Pages | Source |
|---|---|---|
| `/wiki/mechanics/` | 23 | hand-written |
| `/wiki/troops/` | 57 | verified stats + prose on 28 |
| `/wiki/spells/` | 17 | verified stats + prose on all |
| `/wiki/heroes/` | 6 | verified stats + prose on all |
| `/wiki/buildings/` | 41 | verified stats + prose on 24 |
| `/wiki/town-hall/` | 18 | verified stats + loot tables + prose on all |
| `/tutorials/` | 14 | hand-written |
| `/news/` | 1 + RSS | hand-written |

186 generated pages, plus the 14 existing bot guides and the homepage.

## How the build works

```
_build/prose/*.json        hand-written prose, keyed by slug
../coc-data-out/*.json     verified game data (card #281, regenerate with build_gamedata.py)
        |  merge_data.py
        v
_build/data/*.json         what the generator reads
        |  build.py
        v
/wiki/, /tutorials/, /news/, sitemap.xml, llms.txt, news/feed.xml
```

```bash
python3 _build/merge_data.py     # after either data or prose changes
python3 _build/build.py          # regenerate the site
python3 _build/build.py --check  # non-zero exit if any internal link is unresolved
python3 _build/new_post.py "Title of a news post"
```

Nothing is hand-edited in `/wiki/`, `/tutorials/` or `/news/`. Those directories
are build output and get overwritten.

### Adding a page

- **Wiki entry** — add an object to `_build/prose/<collection>.json` keyed by the
  slug that already exists in the data layer. Prose fields override the generated
  ones; `tables` and most of `quick` come from the data layer.
- **Tutorial** — add an entry to `_build/data/tutorials.json` and list its `name`
  in one of the hub `groups[].members`.
- **News post** — `new_post.py`, fill the TODOs, build.

`related` accepts `"collection:slug"` (e.g. `"mechanics:funnelling"`), a bare
slug, or `{"href": ..., "label": ...}`. Unresolved references are reported by
`--check` rather than silently dropped.

## The data source

Stat tables are read from **Clash of Clans' own game files**, pulled from Supercell's
asset CDN and decompressed:

```
https://game-assets.clashofclans.com/<fingerprint>/logic/*.csv
fingerprint 0f781c13f654eace7ed90a527d47654b1cc192b0 -> game version 18.350.7
```

`coc-gamefiles/fetch_assets.sh` reproduces the pull. The build number is printed
under every table and comes from `source.game_version`, so captions update
themselves when the files are re-read.

**Refreshing needs a new fingerprint.** There is no public "latest" endpoint —
every discovery URL 403s — so a newer hash has to come from the game client
handshake or a data-mining source. Version 18.350.7 predates the June 2026 update,
so the Ruin Witch and Angry Spell are not in the wiki yet. Put a calendar reminder
on this rather than assuming it stays current.

**This replaced a source that was 21 months old and a whole Town Hall behind.** The
site originally launched on a community extract dated 2024-11-25 that stopped at
TH17 and was missing an entire hero. Nothing about the data looked wrong from the
inside. Keep the vintage caption on every table; it is the only defence against
repeating that.

## The training-cost correction

Reading the real files established that **troops have no training cost and no
training time** — the columns do not exist, and the only resource cost on any troop,
spell or siege machine is laboratory research. Supercell removed troop training.

A large amount of the farming content was rewritten because of this. The old
"cheap army versus loot" arithmetic is dead; what an attack actually spends is the
**search fee** (a per-Town-Hall gold charge, 1,700 at TH18) and the player's time.
If you write new farming content, do not reintroduce army-cost framing — it is one
of the most common errors in existing CoC guides and correcting it is a
differentiator worth keeping.

## Keyword strategy

The existing 14 guides target commercial bot intent — high conversion, low
volume, and a topic most sites will not touch. The new sections target
informational game intent: far higher volume, no conversion on the page, and the
authority that makes the commercial pages rank.

**Clusters now covered**

- *Mechanics* — "how does X work in clash of clans", loot percentages, shields,
  matchmaking, troop AI, funnelling, war scoring. Strong AI-answer material: these
  are exactly the questions asked in natural language.
- *Unit reference* — "[troop] clash of clans", "[troop] stats", "what counters X".
  High volume, heavily contested by Fandom. Wins on the behaviour/counter prose,
  not on the numbers.
- *Town Hall progression* — "th11 upgrade order", "what to upgrade first at th9".
  Best commercial-adjacent cluster: high intent, seasonal evergreen, and the
  per-TH loot tables are uniquely citable.
- *Tutorials* — "how to farm dark elixir", "how to lure clan castle troops",
  "clash of clans for beginners". Long-tail, low competition, high dwell time.

**Gaps worth filling next, in priority order**

1. **Prose on the remaining 24 troops and 21 buildings.** These pages exist with
   verified tables but no strategy section, and they carry a "reference page"
   banner. Thin-ish content at scale is the main risk to the whole section.
2. **Attack strategy pages per Town Hall** — "best th12 attack strategy" is one of
   the highest-volume query families in the game and there is currently nothing
   targeting it.
3. **Base layout pages.** Enormous volume. Requires images, which the site has
   none of yet — see below.
4. **Comparison and decision pages** — "hog rider vs miner", "which hero to
   upgrade first", "is the gold pass worth it". Cheap to write, well suited to
   featured snippets.
5. **Clan Capital / CWL depth.** One page each currently; both support clusters.

## Internal linking rules

- Every wiki page links to 3–5 siblings via `related`. Keep it.
- Mechanics pages are the hubs; unit pages should link *up* to the mechanic that
  explains their behaviour, not sideways to twelve other units.
- Tutorials link into the wiki for the "why"; the wiki links into tutorials for
  the "what do I do". Do not duplicate the explanation on both.
- Bot guides now link into the wiki, and wiki pages carry at most a single
  footer-level mention of the bot (`show_tool_note`). **Do not raise that.** The
  neutral tone is what makes the wiki linkable from Reddit and Discord, and a
  wiki that pitches on every page gets flagged as spam and never shared.

## Publishing cadence

The generator makes the marginal cost of a page very low, so the constraint is
writing, not building.

- **Weekly:** one or two wiki entries filled with prose, working down the gap list.
- **On update:** a news post within 48 hours of a Supercell balance change, with
  the analysis rather than the patch notes, plus the wiki corrections it triggers.
  This is the single best recurring ranking opportunity the site has, because it
  is genuinely time-sensitive and most competitors just repost the notes.
- **Monthly:** one tutorial, targeting whichever query family is showing
  impressions but no clicks in Search Console.

## Distribution

- `sitemap.xml` regenerates on every build. Resubmit after large batches.
- IndexNow key is already in the repo root — ping it after publishing.
- `llms.txt` regenerates with the full section index, and `robots.txt` already
  allows GPTBot, ClaudeBot, PerplexityBot and Google-Extended. The mechanics pages
  are the ones most likely to be cited by AI answers; the FAQ blocks on every page
  are structured for exactly that.
- Every page emits BreadcrumbList and Article JSON-LD, FAQPage where an FAQ
  exists, and ItemList on hubs. HowTo is emitted on tutorials with steps.

## Known gaps and risks

- **No images anywhere.** Every competing wiki has troop and building art. This is
  the largest single quality gap and it blocks the base-layout cluster entirely.
  Supercell's Fan Content Policy governs what art can be used; check it before
  sourcing anything.
- **35 pages are stat-only** and flagged as such. Fill or consider noindexing them
  if Search Console shows quality issues.
- **Anything after game version 18.350.7 is absent**, which means the June 2026
  update (Ruin Witch, Angry Spell) and later. Refreshing needs a new fingerprint.
- **Event units are excluded by rule**, not by name list: a unit whose unlock Town
  Hall is missing from the game files is treated as event content and dropped. If a
  legitimate unit ever ships without a recorded unlock it will vanish from the site,
  so check the excluded count in `merge_data.py` output after each data refresh.
- **Some new defences have stats but no verified behaviour** — Revenge Tower, Super
  Wizard Tower, Multi-Gear Tower, Spell Tower, and the Ice Block and Totem spells.
  Those pages carry an explicit "not yet verified" panel rather than invented
  mechanics. Filling them from actual play is high-value and low-effort.
- **Legal footing.** Every page carries the Supercell disclaimer and the Fan
  Content Policy attribution. The wiki itself is ordinary fan content; the bot is
  the part that carries ToS risk, and that risk is disclosed on the bot pages
  rather than hidden. Keep those separate.
