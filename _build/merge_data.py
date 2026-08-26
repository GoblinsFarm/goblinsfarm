#!/usr/bin/env python3
"""
Merge the verified game-data layer with hand-written prose.

    _build/prose/<collection>.json   prose overlays, keyed by slug   (hand-written)
    ../coc-data-out/<collection>.json  stats, tables, quick facts    (generated, card #281)
                    |
                    v
    _build/data/<collection>.json    what build.py renders

Run after either side changes:   python3 _build/merge_data.py

Prose wins on every field it defines except `tables` and `quick`, which come from
the data layer; `quick` is merged, with prose keys taking precedence. Entries the
data layer has but prose does not are kept as stat-only reference pages unless
they appear in an EXCLUDE list below.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
DATA_IN = BUILD.parent.parent / "coc-data-out"
PROSE = BUILD / "prose"
DATA_OUT = BUILD / "data"

COLLECTIONS = ["troops", "spells", "heroes", "buildings", "townhalls",
               "pets", "equipment", "traps",
               "bb_troops", "bb_buildings",
               "capital_troops", "capital_spells", "capital_buildings",
               "capital_districts"]

# Limited-time event units. Real, but they are not part of the standard roster and
# publishing them as stat-only pages adds thin content for no search value.
EXCLUDE = {
    # Limited-time event units. Real, but not part of the standard roster, and they
    # publish as stat-only pages with an unrecorded unlock, so they add thin content
    # for no search value.
    "troops": {
        "Azure Dragon", "Barbarian Kicker", "Barcher", "Battle Ram", "Broom Witch",
        "C.O.O.K.I.E", "Firecracker", "Giant Giant", "Giant Skeleton", "Hog Wizard",
        "Ice Minion", "Ice Wizard", "Lavaloon", "M.E.C.H.A", "Party Wizard",
        "Pumpkin Barbarian", "Ram Rider", "Royal Ghost", "Skeleton Barrel",
        "Snake Barrel", "Witch Golem",
    },
    "buildings": {
        # Seasonal decorations and event set pieces: one level, 3x3, "Town Hall 1".
        "Candy Cage", "Candy Cane", "Festive Fireworks", "Fizzling Fireworks",
        "Spell Surprise", "Spell Cauldron", "Troop Coop", "Enemy Post",
        # Goblin-map scenery, not the Home Village.
        "Foreboding Cave", "Goblin Castle", "Goblin Hall", "Goblin Hut",
        "Sour Elixir Cauldron",
        # Builder Base huts.
        "B.O.B's Hut", "Helper Hut",
        # Hero altars are emitted as buildings; they would duplicate /wiki/heroes/.
        "Archer Queen", "Barbarian King", "Grand Warden", "Royal Champion",
    },
    "spells": {"Birthday Boom", "Santa's Surprise", "Bag of Frostmites"},
    # Event traps, on the same footing as the event troops above: real, but not
    # part of a base anyone builds, and they publish with an unlock nobody can act on.
    "traps": {"Pumpkin Bomb", "Santa Strike", "Shrink Trap", "Freeze Trap"},
    "capital_buildings": {
        # District population houses: one level, no stats, purely decorative.
        "Giants' House", "Large House", "Slanted House", "Small Cabin", "Small Hut",
        "Thatched Hut", "Wooden Cabin", "Wooden House",
        # Goblin-map scenery, same as the Home Village list above.
        "Goblin Hall", "Goblin Hut", "Goblin Outpost",
    },
}

# Supercell removed troop training entirely: the game files carry no training cost
# and no training time column, and nothing derivable. Both render as an em dash for
# every unit at every level, so a column implying the mechanic still exists is worse
# than no column. Dropped here rather than upstream so the data layer keeps a stable
# shape. See /news/ for the note explaining this to readers.
DROP_COLUMNS = {"Training cost", "Training time"}

# Heal rates are stored as negative damage in the extracted files. Relabel the
# column rather than silently serving a minus sign as if it were DPS.
HEAL_UNITS = {"healer", "druid"}

PROSE_FIELDS = (
    "h1", "head_title", "description", "blurb", "summary", "sections",
    "faq", "related", "tags", "show_tool_note", "priority",
)


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# A page reachable only from its section hub gets one internal link and ranks like
# it. Entries without hand-written prose carry no `related`, which was leaving over
# a hundred pages on a single inbound link. Wire each into a ring of its siblings
# plus the mechanic that explains its behaviour.
TOPIC_LINK = {
    "troops": "mechanics:troop-targeting-and-ai",
    "spells": "mechanics:spell-mechanics",
    "heroes": "mechanics:hero-equipment",
    "buildings": "mechanics:defence-mechanics",
    "townhalls": "mechanics:upgrade-priority",
    "pets": "mechanics:hero-equipment",
    "equipment": "mechanics:hero-equipment",
    "traps": "mechanics:defence-mechanics",
    "bb_troops": "mechanics:builder-base",
    "bb_buildings": "mechanics:builder-base",
    "capital_troops": "mechanics:clan-capital-and-raid-weekends",
    "capital_spells": "mechanics:clan-capital-and-raid-weekends",
    "capital_buildings": "mechanics:clan-capital-and-raid-weekends",
    "capital_districts": "mechanics:clan-capital-and-raid-weekends",
}


def autolink(collection: str, data: dict) -> int:
    """Give every entry without `related` a deterministic set of sibling links."""
    groups = data.get("hub", {}).get("groups") or []
    group_of, order = {}, {}
    for g in groups:
        for i, name in enumerate(g["members"]):
            group_of[name] = g["h"]
            order[name] = i
    members = {}
    for g in groups:
        members[g["h"]] = list(g["members"])

    by_name = {e["name"]: e for e in data["entries"]}
    filled = 0
    for entry in data["entries"]:
        if entry.get("related"):
            continue
        siblings = members.get(group_of.get(entry["name"], ""), [])
        picks = []
        if len(siblings) > 1:
            i = siblings.index(entry["name"])
            # neighbours either side, wrapping, so the group forms a ring rather
            # than everything pointing at whichever entry sorts first
            for offset in (1, -1, 2):
                cand = siblings[(i + offset) % len(siblings)]
                if cand != entry["name"] and cand in by_name and cand not in picks:
                    picks.append(cand)
        related = [f"{collection}:{by_name[n]['slug']}" for n in picks[:3]]
        topic = TOPIC_LINK.get(collection)
        if topic:
            related.append(topic)
        if related:
            entry["related"] = related
            filled += 1
    return filled


def unrecorded_unlock(collection: str, entry: dict) -> bool:
    """True when a unit's unlock Town Hall is missing from the game files.

    Every unit on the standard roster records the Town Hall it unlocks at. The ones
    that do not are event and special units, which would otherwise publish as pages
    whose most useful column is blank. Rule rather than a name list, so units added
    by future events are handled without an edit here.
    """
    if collection != "troops":
        return False
    for table in entry.get("tables", []):
        cols = table.get("columns", [])
        if "Town Hall" not in cols:
            continue
        i = cols.index("Town Hall")
        first = table["rows"][0] if table["rows"] else []
        if i < len(first) and first[i] == "TODO":
            return True
    return False


def drop_columns(entry: dict) -> None:
    """Remove columns that no longer correspond to a live game mechanic."""
    for table in entry.get("tables", []):
        keep = [i for i, col in enumerate(table.get("columns", [])) if col not in DROP_COLUMNS]
        if len(keep) == len(table.get("columns", [])):
            continue
        table["columns"] = [table["columns"][i] for i in keep]
        table["rows"] = [[row[i] for i in keep if i < len(row)] for row in table["rows"]]


def relabel_heal(entry: dict) -> None:
    for table in entry.get("tables", []):
        cols = table.get("columns", [])
        for i, col in enumerate(cols):
            if col in ("DPS", "Damage"):
                cols[i] = "Heal rate"
                for row in table.get("rows", []):
                    if i < len(row) and row[i].startswith("-"):
                        row[i] = row[i][1:] + " per second"


def inject_mechanics_tables() -> int:
    """Build the per-Town-Hall loot table into the hand-written loot mechanics page.

    These constants are the least reproducible thing on the site, so they are
    generated from the data layer rather than transcribed, and regenerate whenever
    the game files are re-read.
    """
    loot_file = DATA_IN / "townhall_loot.json"
    mech_file = DATA_OUT / "mechanics.json"
    if not (loot_file.exists() and mech_file.exists()):
        return 0

    loot = load(loot_file)
    mech = load(mech_file)
    entry = next((e for e in mech["entries"] if e["slug"] == "loot-mechanics"), None)
    if not entry:
        return 0

    def fmt(n):
        return f"{n:,}"

    rows = []
    for th, v in sorted(loot["entries"].items(), key=lambda kv: int(kv[0])):
        rows.append([
            f"TH{th}",
            f"{v['ResourceStorageLootPercentage']}%",
            fmt(v["ResourceStorageLootCap"]),
            f"{v['DarkElixirStorageLootPercentage']}%",
            fmt(v["DarkElixirStorageLootCap"]),
            fmt(v["AttackCost"]),
        ])

    entry["tables"] = [{
        "caption": "How much a single attack can take from a village at each Town Hall level, "
                   "and what the attacker pays to search. Percentages are of the defender's "
                   "current storage contents.",
        "columns": ["Town Hall", "Storage loot", "Max per attack", "Dark elixir", "Max dark elixir", "Search fee"],
        "rows": rows,
    }]
    entry["source"] = loot.get("source")
    mech_file.write_text(json.dumps(mech, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def main() -> int:
    if not DATA_IN.exists():
        sys.exit(f"error: data layer not found at {DATA_IN}")
    DATA_OUT.mkdir(exist_ok=True)
    report = []

    for name in COLLECTIONS:
        data = load(DATA_IN / f"{name}.json")
        if not data:
            print(f"  skip {name}: no data file")
            continue
        overlay = load(PROSE / f"{name}.json")
        excluded = EXCLUDE.get(name, set())

        kept, dropped, with_prose = [], 0, 0
        for entry in data.get("entries", []):
            if entry["name"] in excluded or unrecorded_unlock(name, entry):
                dropped += 1
                continue
            prose = overlay.get(entry["slug"])
            if prose:
                with_prose += 1
                merged_quick = dict(entry.get("quick", {}))
                merged_quick.update(prose.get("quick", {}))
                for field in PROSE_FIELDS:
                    if field in prose:
                        entry[field] = prose[field]
                if merged_quick:
                    entry["quick"] = merged_quick
            drop_columns(entry)
            if entry["slug"] in HEAL_UNITS:
                relabel_heal(entry)
            entry["has_prose"] = bool(prose)
            kept.append(entry)

        data["entries"] = kept
        names = {e["name"] for e in kept}
        for group in data.get("hub", {}).get("groups", []):
            group["members"] = [m for m in group["members"] if m in names]
        data["hub"]["groups"] = [g for g in data["hub"]["groups"] if g["members"]]

        linked = autolink(name, data)

        # hub prose overlay lives under the reserved key "_hub"
        if "_hub" in overlay:
            data["hub"].update(overlay["_hub"])

        (DATA_OUT / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report.append((name, len(kept), with_prose, dropped, linked))

    injected = inject_mechanics_tables()
    if injected:
        print(f"injected per-Town-Hall loot table ({injected} rows) into loot-mechanics")

    print(f"{'collection':<12}{'pages':>7}{'with prose':>12}{'excluded':>10}{'autolinked':>12}")
    for name, kept, prose, dropped, linked in report:
        print(f"{name:<12}{kept:>7}{prose:>12}{dropped:>10}{linked:>12}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
