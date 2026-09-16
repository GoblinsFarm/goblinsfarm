#!/usr/bin/env python3
"""Write a patch note by diffing the published data against a previous revision.

    python3 _build/changelog.py --since origin/main --version 18.600.3
    python3 _build/changelog.py --since origin/main --version 18.600.3 --write

Why this exists
---------------
The wiki's whole claim is that its numbers come from the game's own files at a
recorded client build. That claim is only worth anything if somebody can see
what moved between two builds, and nobody -- including us -- could. A patch note
written by hand from Supercell's blog is a different document: it says what they
chose to announce. This says what the files actually hold, which is a smaller,
duller and more checkable thing, and it is the only version of it anyone
publishes.

It reads `_build/data/*.json` as it stands now against the same files at a git
revision, so what it reports is exactly what changed on the site: entries added
or dropped, quick facts moved, and every cell in every level table that is not
what it was. Changes the wiki caused itself -- a parser fix, a new exclusion --
show up here too and have to be labelled as such by hand, because the diff
cannot tell a rebalance from a correction and should not guess.
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

BUILD = Path(__file__).resolve().parent
DATA = BUILD / "data"
# Collections that describe things; the prose collections have no level tables
# and their edits are ours, not the game's.
SKIP = {"site", "wiki", "news", "blog", "tutorials", "patchnotes", "mechanics"}
LABEL = {
    "troops": ("Troops", "wiki/troops"), "spells": ("Spells", "wiki/spells"),
    "heroes": ("Heroes", "wiki/heroes"), "equipment": ("Equipment", "wiki/equipment"),
    "pets": ("Pets", "wiki/pets"), "buildings": ("Buildings", "wiki/buildings"),
    "traps": ("Traps", "wiki/traps"), "townhalls": ("Town Halls", "wiki/town-hall"),
    "bb_troops": ("Builder Base troops", "wiki/builder-base/troops"),
    "bb_buildings": ("Builder Base buildings", "wiki/builder-base/buildings"),
    "capital_troops": ("Capital troops", "wiki/clan-capital/troops"),
    "capital_spells": ("Capital spells", "wiki/clan-capital/spells"),
    "capital_buildings": ("Capital buildings", "wiki/clan-capital/buildings"),
    "capital_districts": ("Capital districts", "wiki/clan-capital/districts"),
}


def at_revision(ref: str, path: Path) -> dict:
    rel = path.relative_to(BUILD.parent)
    out = subprocess.run(["git", "show", f"{ref}:{rel}"], capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout else {}


def by_slug(doc: dict) -> dict:
    entries = doc.get("entries") if isinstance(doc, dict) else doc
    return {e["slug"]: e for e in (entries or [])}


def diff_entry(old: dict, new: dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for key, value in (new.get("quick") or {}).items():
        was = (old.get("quick") or {}).get(key)
        if was is not None and str(was) != str(value):
            out.append((key, str(was), str(value)))
    for fresh, stale in zip(new.get("tables") or [], old.get("tables") or []):
        if fresh["columns"] != stale["columns"]:
            continue
        if len(fresh["rows"]) != len(stale["rows"]):
            out.append(("Levels", str(len(stale["rows"])), str(len(fresh["rows"]))))
        for row, prior in zip(fresh["rows"], stale["rows"]):
            for i, (now, before) in enumerate(zip(row, prior)):
                if str(now) != str(before):
                    out.append((f"Level {row[0]} {fresh['columns'][i].lower()}",
                                str(before), str(now)))
    # A level count shows up twice, once from the stat block and once from the
    # table growing rows, and they say the same thing.
    seen, unique = set(), []
    for what, was, now in out:
        key = (what.lower(), was, now)
        if key in seen:
            continue
        seen.add(key)
        unique.append((what, was, now))
    return unique


def collect(since: str) -> tuple[list, list, dict]:
    added, dropped, changed = [], [], {}
    for path in sorted(DATA.glob("*.json")):
        name = path.stem
        if name in SKIP or name not in LABEL:
            continue
        new, old = by_slug(json.loads(path.read_text())), by_slug(at_revision(since, path))
        if not old:
            continue
        for slug in sorted(new.keys() - old.keys()):
            added.append((name, new[slug]))
        for slug in sorted(old.keys() - new.keys()):
            dropped.append((name, old[slug]))
        for slug in sorted(new.keys() & old.keys()):
            rows = diff_entry(old[slug], new[slug])
            if rows:
                changed[(name, slug)] = (new[slug], rows)
    return added, dropped, changed


def link(name: str, entry: dict) -> str:
    folder = LABEL[name][1]
    return f'<a href="../{folder}/{entry["slug"]}.html">{html.escape(entry["name"])}</a>'


def sections(added, dropped, changed) -> list[dict]:
    out = []
    if added:
        items = "".join(
            f"<li>{link(n, e)} <span class=\"muted\">— {LABEL[n][0]}</span></li>"
            for n, e in added)
        out.append({"h": "New in this build",
                    "body": f"<p>Pages that did not exist before this build.</p>"
                            f"<ul>{items}</ul>"})
    if dropped:
        items = "".join(f"<li>{html.escape(e['name'])} "
                        f"<span class=\"muted\">— {LABEL[n][0]}</span></li>"
                        for n, e in dropped)
        out.append({"h": "No longer published",
                    "body": f"<ul>{items}</ul>"})
    if changed:
        rows = "".join(
            f"<tr><td>{link(n, e)}</td><td>{html.escape(what)}</td>"
            f"<td>{html.escape(was)}</td><td>{html.escape(now)}</td></tr>"
            for (n, _), (e, edits) in sorted(changed.items())
            for what, was, now in edits)
        out.append({
            "h": "Every number that moved",
            "body": '<p>Read straight off the two builds. Every cell on the site '
                    'that is not what it was:</p>'
                    '<div class="tablewrap"><table><thead><tr><th>Page</th>'
                    '<th>What</th><th>Was</th><th>Now</th></tr></thead>'
                    f"<tbody>{rows}</tbody></table></div>",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="origin/main", help="git revision to compare against")
    ap.add_argument("--version", required=True, help="client build these numbers came from")
    ap.add_argument("--previous", default="", help="client build being compared against")
    ap.add_argument("--write", action="store_true", help="add the post to data/patchnotes.json")
    args = ap.parse_args()

    added, dropped, changed = collect(args.since)
    edits = sum(len(rows) for _, rows in changed.values())
    print(f"since {args.since}: {len(added)} added, {len(dropped)} dropped, "
          f"{len(changed)} entries changed, {edits} cells")
    if not (added or dropped or changed):
        print("nothing to report")
        return 0

    today = date.today()
    post = {
        "slug": f"game-files-{args.version.replace('.', '-')}",
        "name": f"What changed in the game files: build {args.version}",
        "head_title": f"Clash of Clans {args.version} — What Changed in the Game Files",
        "description": (
            f"Every stat that moved between Clash of Clans client builds "
            f"{args.previous or 'the previous build'} and {args.version}, read from "
            f"Supercell's own game files rather than from the patch notes."),
        "summary": (
            f"{len(added)} new page{'s' if len(added) != 1 else ''}, "
            f"{edits} changed value{'s' if edits != 1 else ''}."),
        "banner": "progression",
        "tags": [{"label": args.version, "kind": "gold"}],
        "date": today.isoformat(),
        "date_label": today.strftime("%-d %B %Y"),
        "sections": sections(added, dropped, changed),
        "priority": "0.7",
    }
    if not args.write:
        print(json.dumps(post, indent=1)[:1200])
        print("\n(dry run — pass --write to add it)")
        return 0

    path = DATA / "patchnotes.json"
    doc = json.loads(path.read_text()) if path.exists() else {"hub": {}, "entries": []}
    doc["entries"] = [e for e in doc["entries"] if e["slug"] != post["slug"]] + [post]
    doc["entries"].sort(key=lambda e: e["date"], reverse=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {post['slug']} to {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
