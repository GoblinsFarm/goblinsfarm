#!/usr/bin/env python3
"""
Scaffold a news post.

    python3 _build/new_post.py "Balance changes in the October update"

Appends a skeleton entry to _build/data/news.json with today's date, then tells
you which file to edit. Run _build/build.py afterwards to publish; the post is
added to /news/, the RSS feed and the sitemap automatically.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

NEWS = Path(__file__).resolve().parent / "data" / "news.json"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70]


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit('usage: new_post.py "Post title"')
    title = " ".join(sys.argv[1:])
    slug = slugify(title)
    data = json.loads(NEWS.read_text(encoding="utf-8"))

    if any(e["slug"] == slug for e in data["entries"]):
        sys.exit(f"error: a post with slug '{slug}' already exists")

    today = date.today()
    data["entries"].append({
        "slug": slug,
        "name": title,
        "h1": title,
        "head_title": f"{title} | Goblins Farm",
        "description": "TODO one-sentence meta description, under 160 characters.",
        "summary": "TODO the lede. What changed, and why a player should care.",
        "date": today.isoformat(),
        "date_label": today.strftime("%-d %B %Y"),
        "byline": "Goblins Farm",
        "tags": [{"label": "Update"}],
        "sections": [
            {"h": "What changed", "body": "<p>TODO</p>"},
            {"h": "What it means", "body": "<p>TODO the analysis. This is the part patch-note reposts do not have.</p>"},
            {"h": "What we changed on the wiki", "body": "<p>TODO which pages were updated as a result, if any.</p>"},
        ],
        "sources": [{"href": "https://supercell.com/", "label": "TODO official source"}],
        "related": ["wiki:index"],
        "priority": "0.6",
    })

    NEWS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"added '{slug}' to {NEWS}")
    print("edit the TODO fields, then run:  python3 _build/build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
