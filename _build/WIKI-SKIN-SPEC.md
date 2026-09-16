# Wiki visual overhaul — spec

Goal: `/wiki` should read as a maintained game reference — the shape a player
already knows from Fandom — instead of a blog post with a picture at the top.

## What is wrong now

Measured on `/wiki/troops/dragon.html` at 1440px:

1. **Roughly 45% of the window is empty.** The shell is 1560px, running text is
   capped at 74ch (~690px), and nothing occupies the rest. The quick-facts panel
   floats into part of it and then the column dies for the remaining 2,400px of
   scroll.
2. **The subject is a 96px thumbnail.** A wiki entry's own artwork is the one
   image that page has, and it is smaller than the goblin mascot beside the FAQ.
3. **Quick facts is a beige `<dl>`.** No title, no image, no typing by resource,
   nothing that says "this is the stat block".
4. **No way to move sideways.** Reaching Balloon from Dragon costs two page
   loads through the hub. Real wikis put every sibling one click away, always.
5. **No search.** 369 pages and no way to ask for one by name.
6. **Card grids are text with a 56px thumb.** The art exists — 973 extracted
   files — and the layout spends almost none of it.
7. **Tables are flat.** A 21-row Cannon table scrolls its header off screen and
   the cost column is an undifferentiated string of digits.

None of this is a content problem. The data layer is good and the prose is
good. It is a skin problem, so this is a skin change: templates, CSS, and the
two build-time indexes the new chrome needs.

## What changes

### 1. Three-column shell

```
[ 232px category rail ][ article ][ 340px stat rail ]
```

* Left rail: every wiki section, with the active section expanded to its full
  entry list, each entry carrying its 22px icon. Sticky, scrolls inside itself.
* Right rail: the infobox, then the on-this-page contents. Sticky.
* `--shell` drops 1560px → 1400px so the article column lands near its measure
  instead of trailing 250px of slack.

Breakpoints: 3 columns ≥1280px; rail + article ≥1000px with the infobox moved
to the top of the article; single column below that, with the rail collapsed
into a `<details>` and the infobox above the lede.

### 2. Portable infobox

Replaces `.quick`. Titled header bar, the entry's artwork at 200px on a tinted
plaque, then the fact rows, then a footer line for the page it is unlocked by.
The tint comes from the entry's own tags — elixir, dark elixir, gold, builder
base, capital — so a page's colour tells you which economy it belongs to before
you have read a word.

### 3. Search

`assets/search-index.json` written by the build: one record per generated page
(title, url, section, thumbnail, blurb). `assets/search.js` puts an input in
the site bar: prefix-and-substring scoring, thumbnails in the results,
arrow keys and Enter, `/` to focus, Escape to dismiss. No dependency, no
network call.

### 4. Art-forward grids

Hub cards get an 84px art plaque; name-only cards become vertical tiles with
the art at 72px over the label. Tiles are tinted by section, as the infobox is.

### 5. Tables

Sticky header row inside the scroll box, hover highlight, a level badge in the
first column, and cost cells that carry a small resource pip so gold, elixir
and dark elixir are distinguishable at a glance.

### 6. Headers

Hub banners take the page title as an overlay with a scrim, which is what makes
a section front page look like a section front page. Entry headers get the
artwork at 128px and a tinted band behind the title.

### 7. Mascots stay, but stop competing

They move into circular parchment medallions and shrink in the H2 rows. The
game art is the subject of every page; the cast is the furniture.

## Non-goals

* No new artwork is generated. Everything here uses assets already extracted.
* No data or prose changes. `_build/data` and `_build/prose` are untouched.
* No change to URLs, titles, descriptions, JSON-LD, sitemap or `llms.txt` —
  the SEO and GEO surface is deliberately identical before and after.

## Done means

`python3 _build/build.py --check` renders all 369 pages with no unresolved
links, the TODO count is unchanged from `main`, and the three page types
(wiki index, section hub, entry) have been looked at on a desktop and a phone
viewport.
