#!/usr/bin/env python3
"""Give every wiki entry its picture from Supercell's own art, web-sized.

    python3 _build/art.py            # match, resize, report coverage
    python3 _build/art.py --sheet    # also write a contact sheet of what matched

Reads what ../coc-gamefiles/render_art.py drew and writes one WebP per entry.

There is no matching left to do here. Each entry carries the atlas file and the
export name inside it, copied out of the game's own columns by build_gamedata.py,
and render_art.py draws exactly that export. This used to guess -- match art to a
page by the unit's name, and take the biggest figure on the sheet -- which is how
the Bowler ended up with no picture (his file is info_troll), the Barbarian with
the Barbarian King's Iron Fist (three units share one file), and a dozen fliers
stored sideways with a hand-kept table of quarter turns. All of that is gone: the
container states the name and carries the transform.

Entries whose art the atlas does not have keep the drawn emblem from icons.py, so
every page still gets a picture.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent
DATA = BUILD / "data"
DRAWN = ROOT.parent / "coc-gamefiles" / "art" / "png" / "named"
OUT = ROOT / "assets" / "art"

MAX_HEIGHT = 256
# The level strip runs six abreast under the stats, so each frame is small.
STRIP_HEIGHT = 132

# Rows whose art column points at another unit's picture. The Dragon Duke's still
# holds the Builder Base Battle Copter it was copied from, so he would get a
# helicopter; the drawn emblem is the more honest answer.
BORROWED = {"heroes:dragon-duke"}

# Buildings carry no info-card picture -- none of them do -- but the two Builder
# Base hero altars are pages about the hero, and the hero has one.
EXTRA = {
    "bb_buildings:battle-machine": "info_warmachine__unit_warmachine_big",
    "bb_buildings:battle-copter": "info_battlecopter__unit_battlecopter_big",
    # The Clan House's own export draws nothing; a house from the estate does.
    "capital_buildings:clan-house": "buildings_cc__estate_house_01",
    # Every district's icon column points at the same generic_district_icon, so
    # nine pages would carry one identical picture. Each district is named after
    # what it builds, and that building is in the atlas, so use it: the choice is
    # editorial, which is why it lives here and not in the data layer.
    "capital_districts:capital-peak": "buildings_cc__d0_HQ_lvl10",
    "capital_districts:barbarian-camp": "buildings_cc__troop_barrack_super_barbarian_lvl5",
    "capital_districts:wizard-valley": "buildings_cc__troop_barrack_super_wizard_lvl5",
    "capital_districts:balloon-lagoon": "buildings_cc__troop_barrack_hasty_balloon_lvl5",
    "capital_districts:builders-workshop": "buildings_cc__troop_barrack_battle_ram_lvl5",
    "capital_districts:dragon-cliffs": "buildings_cc__troop_barrack_super_dragon_lvl5",
    "capital_districts:golem-quarry": "buildings_cc__troop_barrack_golem_quarry_lvl5",
    "capital_districts:skeleton-park": "buildings_cc__troop_barrack_skeleton_balloon_lvl5",
    "capital_districts:goblin-mines": "buildings_cc__troop_barrack_miner_lvl4",
}


def source(entry: dict, key: str) -> Path | None:
    if key in BORROWED:
        return None
    named = EXTRA.get(key)
    if not named:
        art = entry.get("art")
        if not art:
            return None
        named = f"{art['sheet']}__{art['export']}"
    path = DRAWN / f"{named}.png"
    return path if path.exists() else None


def web_copy(src: Path, dest: Path, height: int) -> None:
    im = Image.open(src).convert("RGBA")
    if im.height > height:
        im = im.resize((max(1, round(im.width * height / im.height)), height), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=88, method=6)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()

    if not DRAWN.exists():
        print(f"nothing drawn at {DRAWN} -- run coc-gamefiles/render_art.py first")
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
            if not isinstance(entry, dict):
                continue
            key = f"{collection}:{entry['slug']}"
            src = source(entry, key)
            if not src:
                if entry.get("art") and key not in BORROWED:
                    unmatched.append(key)
                continue
            dest = folder / f"{entry['slug']}.webp"
            web_copy(src, dest, MAX_HEIGHT)
            hits += 1
            matched.append((entry["name"], dest))

            # A building looks different at level 1 and level 21, and the page is
            # otherwise a table. Write the strip beside it.
            for step in (entry.get("art") or {}).get("levels", []):
                frame = DRAWN / f"{entry['art']['sheet']}__{step['export']}.png"
                if frame.exists():
                    web_copy(frame, folder / "levels" / f"{entry['slug']}-{step['level']}.webp",
                             STRIP_HEIGHT)
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
        print("  named art that was not drawn:", name)

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
