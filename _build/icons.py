#!/usr/bin/env python3
"""Draw one emblem per wiki entry into assets/icons/.

    python3 _build/icons.py            # draw every icon
    python3 _build/icons.py --sheet    # also write a contact sheet to preview them

Why these are drawn rather than extracted
-----------------------------------------
The obvious source of art for a Clash of Clans wiki is Supercell's own sprite
atlas, which the asset CDN serves alongside the CSVs the stat tables come from.
We do not use it. Supercell's Fan Content Policy covers fan use of their assets
but is conditional on not breaching their terms, and this domain also markets a
farming bot -- so shipping their art here invites a takedown against the whole
site, wiki included. Original marks carry no such risk, and unique images are
worth more in image search than the same sprite every other fan site serves.

How an emblem is built
----------------------
Three layers, all from the site's own palette so the wiki looks like one thing:

    frame   the silhouette, chosen by what kind of page it is -- a tile for a
            unit, a shield for a defence, a hexagon for equipment, a crest for
            a hero. Shape alone tells you which section you are in.
    colour  a two-tone fill keyed to resource or village: elixir purple, dark
            elixir, gold, Builder Base green, Clan Capital blue, defence red.
    motif   a flat glyph, matched to the entry by name.

Entries that match no motif fall back to a sigil built from the same vocabulary
of strokes, seeded by the slug: still distinct per page, still on-brand, and
visibly part of the set rather than a missing-image box.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent
DATA = BUILD / "data"
OUT = ROOT / "assets" / "icons"

INK = "#1f150d"        # --outline
CREAM = "#fffef9"      # --paper
SHADE = "#00000026"

# Two-tone fills, lifted from site.css so nothing here invents a colour.
PALETTE = {
    "elixir":  ("#c47cee", "#a13fdc"),
    "dark":    ("#8375a8", "#584a79"),
    "gold":    ("#ffc93d", "#e79b00"),
    "red":     ("#e06a52", "#b93b22"),
    "green":   ("#8ad86e", "#54b23a"),
    "blue":    ("#3f92dd", "#0058ab"),
    "parch":   ("#e6d6c0", "#cbb59a"),
}


# --------------------------------------------------------------------- frames
def frame_tile(c):
    return f'<rect x="8" y="10" width="80" height="78" rx="20" {c}/>'


def frame_disc(c):
    return f'<circle cx="48" cy="49" r="39" {c}/>'


def frame_shield(c):
    return ('<path d="M48 9 84 21v30c0 20-15 32-36 39C27 83 12 71 12 51V21z" '
            f'{c}/>')


def frame_hex(c):
    return f'<path d="M48 8 83 28v40L48 88 13 68V28z" {c}/>'


def frame_crest(c):
    return ('<path d="M48 7 78 17l-3 34c-1 19-13 29-27 35-14-6-26-16-27-35L18 17z" '
            f'{c}/>')


def frame_banner(c):
    return f'<path d="M14 10h68v62L48 88 14 72z" {c}/>'


FRAMES = {"tile": frame_tile, "disc": frame_disc, "shield": frame_shield,
          "hex": frame_hex, "crest": frame_crest, "banner": frame_banner}


# ---------------------------------------------------------------------- motifs
# Drawn in a 100x100 box centred on (50,50); the emblem scales them to fit.
# Kept to flat silhouettes so they stay readable at the 28px hub-card size.
def _p(d, **kw):
    extra = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in kw.items())
    return f'<path d="{d}"{extra}/>'


MOTIFS: dict[str, str] = {
    "sword": _p("M50 6 62 30 57 34 57 62 43 62 43 34 38 30z M30 62h40v9H30z "
                "M46 71h8v23h-8z"),
    "axe": _p("M44 8h12v86H44z M56 14c18 0 30 12 30 26S74 62 56 62z"),
    "hammer": _p("M20 16h60v26H20z M44 42h12v52H44z"),
    "fist": _p("M24 40c0-12 10-20 26-20s26 8 26 20v26c0 14-12 22-26 22s-26-8-26-22z "
               "M30 30h40v12H30z"),
    "arrow": _p("M50 4 66 34H56v58H44V34H34z"),
    "bow": _p("M30 10c26 10 26 70 0 80l8 6c30-14 30-78 0-92z M28 48h44v8H28z"),
    "spear": _p("M50 4 62 28H38z M45 28h10v66H45z"),
    "claw": _p("M22 12c8 26 8 52 2 76l14-6c4-24 4-46-2-66z "
               "M50 8c6 28 6 56 0 80l14-4c4-26 4-52-2-74z "
               "M76 14c4 26 4 50-2 70l12-8c4-22 4-44 0-62z"),
    "skull": _p("M50 8c22 0 34 14 34 34 0 14-6 22-12 26v14c0 6-8 10-22 10s-22-4-22-10V68"
                "c-6-4-12-12-12-26C16 22 28 8 50 8z M36 40a8 8 0 1 0 0.1 0z "
                "M64 40a8 8 0 1 0 0.1 0z"),
    "dragon": _p("M12 40c14-18 34-24 50-16l14-16 6 22 12 8-16 8c-2 20-18 34-38 34"
                 "-12 0-22-6-28-14l16-4-12-12z M62 34a5 5 0 1 0 0.1 0z"),
    "wing": _p("M10 78c0-38 22-64 54-70-8 10-12 20-12 30 14-6 26-4 34 4"
               "-16 2-26 10-30 22-4 14-18 22-46 14z"),
    "flame": _p("M50 4c4 20 22 26 22 48 0 18-10 30-22 30S28 70 28 52c0-14 8-20 12-30"
                "-2 12 4 18 10 18 6 0 8-8 0-36z"),
    "lightning": _p("M58 4 24 54h20l-8 42 36-52H50z"),
    "snowflake": _p("M46 4h8v92h-8z M8 27l4-7 76 44-4 7z M88 27l-4-7-76 44 4 7z "
                    "M50 22 34 12l-4 7 20 12zm0 0 16-10 4 7-20 12z"),
    "drop": _p("M50 6c18 24 28 38 28 52a28 28 0 1 1-56 0c0-14 10-28 28-52z"),
    "heart": _p("M50 90C22 68 12 54 12 38a22 22 0 0 1 38-15 22 22 0 0 1 38 15"
                "c0 16-10 30-38 52z"),
    "bomb": _p("M46 22a32 32 0 1 0 0.1 0z M56 20l14-14 8 8-14 14z "
               "M74 4l6 6-6 6-6-6z"),
    "mine": _p("M50 20a30 30 0 1 0 0.1 0z M46 4h8v18h-8z M14 46h18v8H14z "
               "M68 46h18v8H68z M22 20l6-6 12 12-6 6z M78 20l-6-6-12 12 6 6z"),
    "spring": _p("M22 20h56v10H22z M22 40h56v10H22z M22 60h56v10H22z M22 80h56v10H22z"),
    "tornado": _p("M12 14h76l-14 14H26z M22 34h56l-12 14H34z M32 54h36l-10 14H42z "
                  "M44 74h12l-6 18z"),
    "cannon": _p("M14 52h40v26H14z M46 44h40v18H46z M78 38h12v30H78z "
                 "M20 78h28v12H20z"),
    "tower": _p("M28 30h44v58H28z M22 18h56v14H22z M40 44h8v14h-8z M56 44h8v14h-8z "
                "M42 68h16v20H42z"),
    "wall": _p("M10 30h80v22H10z M10 58h80v22H10z M36 30v22 M64 30v22 M22 58v22 "
               "M50 58v22 M78 58v22", fill="none", stroke_width="8"),
    "gear": _p("M50 14a36 36 0 1 0 0.1 0z M50 34a16 16 0 1 1-0.1 0z "
               "M44 2h12v16H44z M44 82h12v16H44z M2 44h16v12H2z M82 44h16v12H82z"),
    "wand": _p("M20 88 68 40l-8-8L12 80z M74 6l5 15 15 5-15 5-5 15-5-15-15-5 15-5z"),
    "star": _p("M50 6 62 36l32 3-24 21 7 32-27-17-27 17 7-32-24-21 32-3z"),
    "orb": _p("M50 10a38 38 0 1 0 0.1 0z M36 30a12 8 0 1 0 0.1 0z", ),
    "eye": _p("M4 50c16-24 30-34 46-34s30 10 46 34c-16 24-30 34-46 34S20 74 4 50z "
              "M50 34a16 16 0 1 1-0.1 0z"),
    "crown": _p("M10 76h80v14H10z M10 68 18 22l18 20L50 12l14 30 18-20 8 46z"),
    "gem": _p("M30 10h40l20 26-40 54L10 36z"),
    "potion": _p("M38 6h24v20l18 40c4 16-6 28-30 28S16 82 20 66l18-40z M32 60h36v10H32z"),
    "balloon": _p("M50 6c18 0 30 14 30 32S66 72 50 72 20 56 20 38 32 6 50 6z "
                  "M40 74h20l-4 20H44z"),
    "hog": _p("M14 44c0-14 14-24 36-24s36 10 36 24v18c0 10-10 16-36 16s-36-6-36-16z "
              "M40 46a6 6 0 1 0 0.1 0z M60 46a6 6 0 1 0 0.1 0z M18 20l12 12 "
              "M82 20 70 32", fill=None),
    "pickaxe": _p("M8 26c26-16 58-16 84 0l-8 12c-22-12-46-12-68 0z M44 34h12v60H44z"),
    "cart": _p("M12 30h60l8 26H12z M26 62a12 12 0 1 0 0.1 0z M66 62a12 12 0 1 0 0.1 0z"),
    "shieldglyph": _p("M50 6 86 18v30c0 22-16 34-36 42-20-8-36-20-36-42V18z"),
    "book": _p("M12 14h34c4 0 4 4 4 6v66c0-4-2-6-6-6H12z "
               "M88 14H54c-4 0-4 4-4 6v66c0-4 2-6 6-6h32z"),
    "boot": _p("M26 8h22v46l32 16c8 4 10 12 10 22H26z M26 82h64v10H26z"),
    "mirror": _p("M50 6c20 0 34 16 34 36S70 78 50 78 16 62 16 42 30 6 50 6z "
                 "M44 78h12v16H44z M30 82h40v10H30z"),
    "horn": _p("M12 74c0-34 26-60 60-62-4 12-4 22 0 30-18 2-30 12-34 26-4 12-14 14-26 6z"),
    "leaf": _p("M84 8C40 10 14 34 14 62c0 12 6 22 14 28 2-30 22-52 52-62"
               "-24 16-38 36-40 62 26 2 44-22 44-82z"),
    "feather": _p("M84 6C48 12 24 34 18 62l-8 26 26-8c28-6 50-30 56-66z "
                  "M30 74 74 30", fill=None),
    "anvil": _p("M10 26h48c0 14 12 20 32 20v14H34l-8 10h32v14H22l10-24H10z"),
    "net": _p("M14 14h72v72H14z M38 14v72 M62 14v72 M14 38h72 M14 62h72",
              fill="none", stroke_width="7"),
    "jet": _p("M50 4c8 16 12 32 12 48v18l14 12v10l-20-8h-12l-20 8V82l14-12V52"
              "c0-16 4-32 12-48z"),
    "egg": _p("M50 6c20 0 32 24 32 46a32 32 0 1 1-64 0C18 30 30 6 50 6z"),
    "paw": _p("M50 44c16 0 28 12 28 24s-12 16-28 16-28-4-28-16 12-24 28-24z "
              "M24 20a10 12 0 1 0 0.1 0z M76 20a10 12 0 1 0 0.1 0z "
              "M8 46a9 11 0 1 0 0.1 0z M92 46a9 11 0 1 0 0.1 0z"),
    "sack": _p("M36 10h28l-6 14c16 6 26 20 26 38 0 20-14 32-34 32S16 82 16 62"
               "c0-18 10-32 26-38z"),
    "tesla": _p("M50 6 24 52h18L36 94l30-50H46z M14 22h14v8H14z M72 22h14v8H72z"),
    "cog": _p("M50 20a30 30 0 1 0 0.1 0z M50 38a12 12 0 1 1-0.1 0z "
              "M46 4h8v14h-8z M46 82h8v14h-8z M4 46h14v8H4z M82 46h14v8H82z "
              "M16 22l6-6 10 10-6 6z M84 22l-6-6-10 10 6 6z "
              "M16 78l6 6 10-10-6-6z M84 78l-6 6-10-10 6-6z"),
    "flag": _p("M22 6h8v88h-8z M30 10h56l-14 18 14 18H30z"),
    "house": _p("M50 8 92 42h-14v46H22V42H8z M40 56h20v32H40z"),
    "storage": _p("M18 28h64v58H18z M14 14h72v14H14z M34 44h32v10H34z M34 62h32v10H34z"),
    "camp": _p("M50 10 88 84H12z M50 38 70 76H30z"),
    "hall": _p("M50 6 90 26v10H10V26z M20 40h12v40H20z M44 40h12v40H44z "
               "M68 40h12v40H68z M10 84h80v10H10z"),
    "moon": _p("M62 6a44 44 0 1 0 0 88 36 36 0 1 1 0-88z"),
    "sun": _p("M50 26a24 24 0 1 0 0.1 0z M46 2h8v16h-8z M46 82h8v16h-8z "
              "M2 46h16v8H2z M82 46h16v8H82z M14 20l6-6 12 12-6 6z "
              "M86 20l-6-6-12 12 6 6z M14 80l6 6 12-12-6-6z M86 80l-6 6-12-12 6-6z"),
}


# Name fragment -> motif. Order matters: the first fragment found in the entry
# name wins, so put the specific ones first.
RULES: list[tuple[str, str]] = [
    ("wall wrecker", "cart"), ("battle blimp", "balloon"), ("stone slammer", "hammer"),
    ("log launcher", "cart"), ("flame flinger", "cart"), ("battle drill", "pickaxe"),
    ("troop launcher", "cart"), ("siege barracks", "camp"), ("sky wagon", "cart"),
    ("raid cart", "cart"), ("siege cart", "cart"),
    ("apprentice warden", "book"), ("grand warden", "book"),
    ("archer queen", "bow"), ("barbarian king", "sword"), ("minion prince", "wing"),
    ("royal champion", "spear"), ("dragon duke", "dragon"),
    ("electro dragon", "tesla"), ("inferno dragon", "flame"), ("baby dragon", "dragon"),
    ("dragon rider", "dragon"), ("dragon", "dragon"),
    ("lava hound", "flame"), ("ice hound", "snowflake"), ("hound", "flame"),
    ("headhunter", "skull"), ("skeleton", "skull"), ("witch", "skull"),
    ("golem", "fist"), ("yeti", "snowflake"), ("valkyrie", "axe"),
    ("bowler", "orb"), ("miner", "pickaxe"), ("goblin", "sack"),
    ("wall breaker", "bomb"), ("wall", "wall"),
    ("balloon", "balloon"), ("rocket", "jet"), ("minion", "wing"),
    ("hog rider", "hog"), ("hog", "hog"), ("healer", "heart"), ("heal", "heart"),
    ("wizard", "wand"), ("archer", "arrow"), ("barbarian", "sword"),
    ("giant", "fist"), ("pekka", "sword"), ("p.e.k.k.a", "sword"),
    ("druid", "leaf"), ("root rider", "leaf"), ("thrower", "spear"),
    ("furnace", "flame"), ("electro", "tesla"), ("titan", "fist"),
    ("meteor", "orb"), ("phoenix", "flame"), ("owl", "feather"),
    ("unicorn", "horn"), ("yak", "horn"), ("lizard", "drop"), ("diggy", "pickaxe"),
    ("frosty", "snowflake"), ("fox", "paw"), ("jelly", "orb"), ("raven", "feather"),
    ("lassi", "paw"), ("sneezy", "drop"), ("bear", "paw"),
    ("lightning", "lightning"), ("rage", "fist"), ("jump", "boot"),
    ("freeze", "snowflake"), ("frost", "snowflake"), ("ice", "snowflake"),
    ("poison", "drop"), ("earthquake", "hammer"), ("haste", "boot"),
    ("clone", "mirror"), ("mirror", "mirror"), ("invisibility", "eye"),
    ("recall", "moon"), ("revive", "heart"), ("overgrowth", "leaf"),
    ("totem", "flag"), ("bat", "wing"), ("graveyard", "skull"),
    ("puppet", "sack"), ("vial", "potion"), ("tome", "book"), ("gem", "gem"),
    ("crown", "crown"), ("boots", "boot"), ("gauntlet", "fist"),
    ("shield", "shieldglyph"), ("arrow", "arrow"), ("spear", "spear"),
    ("bracelet", "gem"), ("orb", "orb"), ("pants", "boot"), ("iron", "anvil"),
    ("torch", "flame"), ("fireball", "flame"), ("fire", "flame"),
    ("vampstache", "moon"), ("spiky ball", "orb"), ("action figure", "star"),
    ("staff", "wand"), ("charm", "gem"), ("horse", "horn"), ("backpack", "jet"),
    ("blaster", "lightning"), ("blower", "flame"), ("fangs", "tesla"),
    ("henchmen", "wing"), ("lavaloon", "balloon"), ("snake", "claw"),
    ("seeking air mine", "mine"), ("air bomb", "mine"), ("giga bomb", "bomb"),
    ("bomb", "bomb"), ("mine", "mine"), ("spring", "spring"), ("tornado", "tornado"),
    ("trap", "net"),
    ("x-bow", "bow"), ("crossbow", "bow"), ("tesla", "tesla"),
    ("inferno", "flame"), ("eagle", "feather"), ("scattershot", "orb"),
    ("mortar", "cannon"), ("cannon", "cannon"), ("archer tower", "tower"),
    ("air defense", "jet"), ("air sweeper", "wing"), ("monolith", "gem"),
    ("spell tower", "tower"), ("tower", "tower"), ("crusher", "hammer"),
    ("roaster", "flame"), ("firecracker", "jet"), ("guard post", "camp"),
    ("multi", "cannon"), ("giga", "tesla"), ("blast bow", "bow"),
    ("reflector", "mirror"), ("rapid rockets", "jet"), ("artillery", "cannon"),
    ("hive", "wing"), ("laboratory", "potion"), ("lab", "potion"),
    ("barracks", "camp"), ("army camp", "camp"), ("camp", "camp"),
    ("factory", "potion"), ("workshop", "anvil"), ("forge", "anvil"),
    ("blacksmith", "anvil"), ("pet house", "paw"), ("clock tower", "gear"),
    ("clan castle", "flag"), ("castle", "flag"), ("clan house", "house"),
    ("storage", "storage"), ("gold mine", "pickaxe"), ("gem mine", "gem"),
    ("collector", "drop"), ("drill", "pickaxe"), ("mine", "pickaxe"),
    ("town hall", "hall"), ("builder hall", "hall"), ("capital hall", "hall"),
    ("district hall", "hall"), ("hall", "hall"), ("house", "house"),
    ("hut", "house"), ("cabin", "house"), ("outpost", "flag"),
    ("healing hut", "heart"), ("otto", "gear"), ("b.o.b", "gear"),
    ("battle machine", "gear"), ("battle copter", "jet"),
    ("quarry", "pickaxe"), ("yard", "camp"), ("post", "flag"),
    ("spell storage", "storage"), ("reinforcement", "camp"),
    ("bomber", "bomb"), ("boxer", "fist"), ("beta", "wing"),
    ("night", "moon"), ("zappy", "tesla"), ("sparky", "tesla"),
    ("mountain", "fist"), ("power", "sword"), ("glider", "wing"),
    ("drop ship", "balloon"), ("super", "star"),
]

# Which frame and colour family each collection uses.
STYLE = {
    "troops":            ("tile", "elixir"),
    "spells":            ("disc", "elixir"),
    "heroes":            ("crest", "gold"),
    "equipment":         ("hex", "gold"),
    "pets":              ("tile", "dark"),
    "buildings":         ("shield", "parch"),
    "traps":             ("hex", "red"),
    "townhalls":         ("banner", "gold"),
    "mechanics":         ("disc", "parch"),
    "bb_troops":         ("tile", "green"),
    "bb_buildings":      ("shield", "green"),
    "capital_troops":    ("tile", "blue"),
    "capital_spells":    ("disc", "blue"),
    "capital_buildings": ("shield", "blue"),
    "capital_districts": ("banner", "blue"),
}

# Within a collection, a tag or quick fact can override the colour so that, for
# example, a dark elixir troop does not look like an elixir one.
TAG_COLOUR = {"dark": "dark", "elixir": "elixir", "gold": "gold"}


def colour_for(collection: str, entry: dict) -> str:
    base = STYLE[collection][1]
    if collection in ("troops", "spells"):
        for tag in entry.get("tags") or []:
            kind = TAG_COLOUR.get(tag.get("kind") or "")
            if kind:
                return kind
    if collection == "buildings":
        category = (entry.get("quick") or {}).get("Category", "")
        if category == "Defense":
            return "red"
        if category == "Resource":
            return "gold"
        if category == "Army":
            return "elixir"
    if collection == "equipment":
        return "dark" if (entry.get("quick") or {}).get("Rarity") == "Epic" else "gold"
    return base


def motif_for(name: str) -> str | None:
    low = name.lower()
    for fragment, motif in RULES:
        if fragment in low:
            return motif
    return None


def sigil(slug: str) -> str:
    """A deterministic mark for entries no rule matches.

    Built from the same flat vocabulary as the motifs -- a ring, a bar count and
    a rotated diamond -- so an unmatched entry still looks drawn rather than
    defaulted. Seeded by the slug, so it never changes between builds.
    """
    h = hashlib.sha1(slug.encode()).digest()
    bars = 2 + h[0] % 3
    ring = 26 + h[1] % 10
    rot = h[2] % 90
    parts = [f'<circle cx="50" cy="50" r="{ring}" fill="none" stroke-width="9"/>']
    for i in range(bars):
        y = 50 - (bars - 1) * 7 + i * 14
        w = 16 + (h[3 + i] % 14)
        parts.append(f'<rect x="{50 - w}" y="{y - 4}" width="{w * 2}" height="8" rx="4"/>')
    parts.append(f'<rect x="38" y="38" width="24" height="24" rx="5" '
                 f'transform="rotate({rot} 50 50)"/>')
    return "".join(parts)


def emblem(collection: str, entry: dict) -> str:
    shape, _ = STYLE[collection]
    light, deep = PALETTE[colour_for(collection, entry)]
    glyph = MOTIFS.get(motif_for(entry["name"]) or "", None) or sigil(entry["slug"])

    frame = FRAMES[shape]
    body = frame(f'fill="url(#g)" stroke="{INK}" stroke-width="5" stroke-linejoin="round"')
    # A solid offset copy behind the frame gives the chunky edge the rest of the
    # site has, without a blur filter that would cost more bytes than the icon.
    rim = frame(f'fill="{INK}" transform="translate(0,4)"')

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" '
        f'role="img" aria-label="{entry["name"]}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{light}"/>'
        f'<stop offset="1" stop-color="{deep}"/></linearGradient></defs>'
        f'{rim}{body}'
        f'<g transform="translate(24,25) scale(0.48)" fill="{CREAM}" '
        f'stroke="{INK}" stroke-width="7" stroke-linejoin="round" '
        f'stroke-linecap="round">{glyph}</g>'
        '</svg>'
    )


def sheet(rows: list[tuple[str, str, str]]) -> str:
    cells = "".join(
        f'<figure><img src="{path}" width="72" height="72" alt="">'
        f'<figcaption>{name}</figcaption></figure>'
        for _, name, path in rows)
    return (
        '<!doctype html><meta charset="utf-8"><title>icon sheet</title>'
        '<style>body{background:#d7c4ac;font:12px/1.3 system-ui;margin:0;padding:16px}'
        'main{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:10px}'
        'figure{margin:0;text-align:center;background:#f4ecdc;border:2px solid #eadfcb;'
        'border-radius:10px;padding:8px 4px}'
        'figcaption{margin-top:4px;color:#4a3226;word-break:break-word}</style>'
        f'<main>{cells}</main>')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true",
                    help="also write _build/iconsheet.html to preview every icon")
    args = ap.parse_args()

    drawn, matched, rows = 0, 0, []
    for collection in STYLE:
        path = DATA / f"{collection}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        folder = OUT / collection.replace("_", "-")
        folder.mkdir(parents=True, exist_ok=True)
        for entry in data.get("entries", []):
            svg = emblem(collection, entry)
            (folder / f"{entry['slug']}.svg").write_text(svg, encoding="utf-8")
            drawn += 1
            if motif_for(entry["name"]):
                matched += 1
            rows.append((collection, entry["name"],
                         f"../assets/icons/{collection.replace('_', '-')}/{entry['slug']}.svg"))
    print(f"drew {drawn} icons  ({matched} from a named motif, "
          f"{drawn - matched} from a seeded sigil)")
    if args.sheet:
        (BUILD / "iconsheet.html").write_text(sheet(rows), encoding="utf-8")
        print(f"contact sheet: _build/iconsheet.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
