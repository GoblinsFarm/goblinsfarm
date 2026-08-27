#!/usr/bin/env python3
"""Give every wiki entry its portrait from Supercell's own art, and write it out.

    python3 _build/art.py            # match, resize, report coverage
    python3 _build/art.py --sheet    # also write a contact sheet of what matched

Reads the sprites that ../coc-gamefiles/extract_art.py pulls off the asset CDN
and writes a web-sized WebP per entry that has one. Entries with no art keep the
drawn emblem from icons.py, so every page still gets a picture.

Which file, and which figure in it
----------------------------------
Both come from the game data, not from the name. Each unit's row carries
`BigPictureSWF` (the sheet) and `BigPicture` (its export name inside the sheet),
and build_gamedata.py copies the pair onto every entry as `art`. Matching on the
unit's name instead -- which is what this did first -- goes wrong twice over:

  Names in the files are development names. The Bowler's art is info_troll, the
  Lava Hound's is info_tiny, the Valkyrie's export is unit_warriorGirl_big. No
  amount of aliasing finds those reliably; the column states them.

  A sheet is not one unit. sc/info_barbarian.sc holds the Barbarian, the
  Barbarian King and the King's Iron Fist, and the Iron Fist -- a crowned King
  flanked by two Barbarians -- is the biggest figure on it, so "take the largest"
  put the King's ability art on the Barbarian page. The Archer's sheet is the
  same story with the Archer Queen.

The export name settles which figure only if you know where it sits on the sheet,
and nothing readable says so: the order the names appear in the header does not
track the order the figures are packed in. So PICK below records the position for
the sheets that carry more than one unit, checked by eye against a contact sheet.
Everything else takes the first figure, which is right for the 81 single-unit
sheets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent
DATA = BUILD / "data"
GAME = ROOT.parent / "coc-gamefiles" / "art" / "png"
SPRITES = GAME / "all"
OUT = ROOT / "assets" / "art"

MAX_HEIGHT = 256

# "<sheet>:<export>" -> which figure on that sheet it is, counting from the
# largest. Only the sheets holding more than one unit need an entry.
PICK = {
    # The Iron Fist is the biggest figure here, the King the next, the Barbarian
    # the smallest -- exactly backwards from what "largest is the subject" wants.
    "info_barbarian:unit_barbarian_big": 2,
    "info_barbarian:unit_barbarianKing_big": 1,
    "info_archer:unit_archer_big": 2,
    "info_archer:unit_archerQueen_big": 1,
    # The Druid's sheet leads with the bear he turns into.
    "info_druid_bear:unit_druid_big": 1,
    # Two loose elephants and a dismounted rider come before the pair together.
    "info_elephant_rider:unit_elephant_rider_big": 1,
    "info_electrofire_wizard:unit_electrofire_wizard_fire": 1,
    # Her sheet leads with the skeleton blimp, which is the Drop Ship's picture
    # and takes the default -- the two pages want different figures from one file.
    "info_witch:unit_witch_big": 1,
    # Leads with the rubble and the Ruin Knight she summons out of it.
    "info_ruin_witch:unit_ruin_witch_big": 1,
    # Sneezy and her bubble spirit overlap on the sheet and come out as one blob;
    # the second figure is Sneezy on her own.
    "info_pet_sneezy:unit_pet_sneezy_big": 1,
    "info_pet_raven:unit_pet_raven_big": 2,
}

# Buildings carry no BigPicture column at all -- none of them do -- but the two
# Builder Base hero altars are pages about the hero, and the hero has one.
EXTRA = {
    "bb_buildings:battle-machine": {"sheet": "info_warmachine",
                                    "export": "unit_warmachine_big"},
    "bb_buildings:battle-copter": {"sheet": "info_battlecopter",
                                   "export": "unit_battlecopter_big"},
}

# Rows whose BigPicture column points at another unit's art. The Dragon Duke's
# still holds the Builder Base Battle Copter it was copied from, so he would get
# a picture of a helicopter; the drawn emblem is the more honest answer.
BORROWED = {"heroes:dragon-duke"}


def sprite(art: dict) -> Path | None:
    """The file holding the figure this entry's art column names."""
    if not art:
        return None
    index = PICK.get(f"{art['sheet']}:{art['export']}", 0)
    for path in (SPRITES / f"{art['sheet']}.g{index}.png",
                 SPRITES / f"{art['sheet']}.g0.png",
                 GAME / f"{art['sheet']}.png"):
        if path.exists():
            return path
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()

    if not SPRITES.exists():
        print(f"no extracted art at {SPRITES} -- run coc-gamefiles/extract_art.py first")
        return 1

    # Start clean: a renamed or dropped entry would otherwise leave its old
    # picture behind and the next page to take that slug would inherit it.
    for stale in OUT.rglob("*.webp"):
        stale.unlink()

    report, matched, unmatched = [], [], []
    for path in sorted(DATA.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "entries" not in data:
            continue
        collection = path.stem
        folder = OUT / collection.replace("_", "-")
        hits = 0
        for entry in data["entries"]:
            if f"{collection}:{entry['slug']}" in BORROWED:
                continue
            src = sprite(EXTRA.get(f"{collection}:{entry['slug']}") or entry.get("art"))
            if not src:
                if entry.get("art"):
                    unmatched.append(f"{collection}/{entry['slug']}")
                continue
            im = Image.open(src).convert("RGBA")
            if im.height > MAX_HEIGHT:
                im = im.resize((max(1, round(im.width * MAX_HEIGHT / im.height)), MAX_HEIGHT),
                               Image.LANCZOS)
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / f"{entry['slug']}.webp"
            im.save(dest, "WEBP", quality=88, method=6)
            hits += 1
            matched.append((entry["name"], dest))
        report.append((collection, hits, len(data["entries"])))

    total = sum(h for _, h, _ in report)
    pages = sum(n for _, _, n in report)
    for collection, hits, n in report:
        if n:
            print(f"  {collection:20} {hits:3}/{n:3}")
    size = sum(p.stat().st_size for p in OUT.rglob('*.webp')) / 1e6 if OUT.exists() else 0
    print(f"\n{total} of {pages} entries have game art ({size:.1f} MB); "
          f"the rest use the drawn emblem")
    for name in unmatched:
        print("  named art that is not on disk:", name)

    if args.sheet:
        cells = "".join(
            f'<figure><img src="../{d.relative_to(ROOT)}" loading="lazy">'
            f'<figcaption>{n}</figcaption></figure>' for n, d in matched)
        (BUILD / "artsheet.html").write_text(
            '<!doctype html><meta charset=utf-8><title>art</title>'
            '<style>body{background:#d7c4ac;font:11px system-ui;margin:0;padding:10px}'
            'main{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px}'
            'figure{margin:0;text-align:center;background:#f4ecdc;border:2px solid #eadfcb;'
            'border-radius:8px;padding:6px 2px}'
            'img{width:88px;height:88px;object-fit:contain;display:block;margin:0 auto}'
            'figcaption{color:#4a3226;margin-top:3px}</style>'
            f'<main>{cells}</main>', encoding="utf-8")
        print("contact sheet: _build/artsheet.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
