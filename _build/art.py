#!/usr/bin/env python3
"""Match extracted game art to wiki entries and write it into assets/art/.

    python3 _build/art.py            # match, resize, report coverage
    python3 _build/art.py --sheet    # also write a contact sheet of what matched

Reads the PNGs that ../coc-gamefiles/extract_art.py pulls out of Supercell's
asset CDN and writes a web-sized WebP per entry that has one. Entries with no
art keep the drawn emblem from icons.py, so every page still gets a picture.

Matching is by name, normalised, plus the alias table below for the cases where
the file name is not the name the game shows. Two groups need it:

  Super troops ship under "elite_" -- Super Barbarian is `elite_barbarian`,
  Sneaky Goblin is `goblin_elite`. Nothing in the file says so.

  Siege machines ship under what they do rather than what they are called:
  the Wall Wrecker is `siege_machine_ram`, the Stone Slammer is
  `siege_machine_catapult`, the Siege Barracks is `siege_machine_commandtower`.

Clan Capital squads and their Home Village namesakes are the same creature, so
a squad reuses the base unit's portrait rather than going without.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent
DATA = BUILD / "data"
SOURCE = ROOT.parent / "coc-gamefiles" / "art" / "png"
OUT = ROOT / "assets" / "art"

MAX_HEIGHT = 256

ALIAS = {
    # Super troops are "elite" in the files.
    "Super Barbarian": "elite_barbarian", "Super Archer": "elite_archer",
    "Super Giant": "giant_elite", "Sneaky Goblin": "goblin_elite",
    "Super Wall Breaker": "wallbreaker_elite", "Super Wizard": "elite_wizard",
    "Super Minion": "elite_minion", "Super Valkyrie": "elite_valkyrie",
    "Super Witch": "elite_witch", "Ice Hound": "elite_icehound",
    "Super Bowler": "elite_bowler", "Super Miner": "elite_miner",
    "Super Hog Rider": "elite_hogrider", "Inferno Dragon": "elite_infernodragon",
    # Siege machines are named for the mechanism, not the machine.
    "Wall Wrecker": "siege_machine_ram", "Battle Blimp": "siege_machine_balloon",
    "Stone Slammer": "siege_machine_catapult",
    "Siege Barracks": "siege_machine_commandtower",
    "Log Launcher": "siege_machine_loglauncher",
    "Flame Flinger": "siege_machine_flyer",
    "Battle Drill": "siege_machine_battledrill",
    "Troop Launcher": "siege_machine_air_troop_launcher",
    "Sky Wagon": "siege_clan_carrier",
    # Pets ship under a working name.
    "Spirit Fox": "pet_phasefennec", "Angry Jelly": "pet_rage_jelly",
    "Greedy Raven": "pet_raven", "L.A.S.S.I": "pet_lassi",
    # Odds and ends.
    "Apprentice Warden": "apprentice", "Druid": "druid_bear",
    "Cannon Cart": "moving_cannon", "Battle Machine": "warmachine",
    "Night Witch": "nightwitch",
    # Clan Capital squads are the Home Village creature, several at a time.
    "Super Barbarians": "elite_barbarian", "Sneaky Archers": "sneaky_archer",
    "Super Giants": "giant_elite", "Minion Horde": "minion",
    "Super Wizards": "elite_wizard", "Rocket Balloons": "rocket_balloon",
    "Skeleton Barrels": "skeleton_barrel", "Hog Raiders": "hog_glider",
    "Raid Cart": "siege_clan_carrier",
}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def index() -> dict[str, Path]:
    """Every art file under each name it could plausibly be looked up by."""
    found: dict[str, Path] = {}
    for path in sorted(SOURCE.glob("*.png")):
        stem = path.stem.replace("info_", "")
        keys = {stem, stem.replace("pet_", ""), stem.replace("siege_machine_", "")}
        for key in keys:
            found.setdefault(norm(key), path)
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()

    if not SOURCE.exists():
        print(f"no extracted art at {SOURCE} -- run coc-gamefiles/extract_art.py first")
        return 1

    by_name = index()
    report, matched = [], []
    for path in sorted(DATA.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "entries" not in data:
            continue
        collection = path.stem
        folder = OUT / collection.replace("_", "-")
        hits = 0
        for entry in data["entries"]:
            alias = ALIAS.get(entry["name"])
            src = (by_name.get(norm(alias)) if alias else None) \
                or by_name.get(norm(entry["name"])) \
                or by_name.get(norm(entry["slug"]))
            if not src:
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
