#!/usr/bin/env python3
"""
Goblins Farm static content generator.

Reads _build/data/*.json and renders the /wiki, /tutorials and /news sections
into the repository root, then regenerates sitemap.xml and llms.txt.

    python3 _build/build.py            # build everything
    python3 _build/build.py --check    # build, then report unresolved links + TODO count

Design notes
------------
Every page is data, not markup. Adding a troop means adding one object to
data/troops.json; adding a tutorial means one object in data/tutorials.json.
Stat cells set to the string "TODO" render with a distinct style and are
counted by --check, so unverified numbers are always visible rather than
silently published.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

BUILD_DIR = Path(__file__).resolve().parent
ROOT = BUILD_DIR.parent
DATA_DIR = BUILD_DIR / "data"
TPL_DIR = BUILD_DIR / "templates"

# Collections rendered as wiki sub-sections: (json file, url folder)
WIKI_COLLECTIONS = [
    ("troops", "wiki/troops"),
    ("spells", "wiki/spells"),
    ("heroes", "wiki/heroes"),
    ("buildings", "wiki/buildings"),
    ("townhalls", "wiki/town-hall"),
    ("mechanics", "wiki/mechanics"),
]

# Hand-written pages that live outside the generator but belong in the sitemap.
STATIC_URLS = [
    ("/", "1.0"),
    ("/terms.html", "0.3"),
    ("/privacy.html", "0.3"),
    ("/refunds.html", "0.3"),
]


# --------------------------------------------------------------------------- helpers
def load(name: str) -> dict:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            sys.exit(f"error: {path.name} is not valid JSON — {exc}")


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")


def trim_title(title: str, brand: str) -> str:
    """Drop the brand suffix when it pushes the title past the SERP display limit."""
    if len(title) <= 60:
        return title
    for sep in (f" | {brand}", f" — {brand}", f" - {brand}"):
        if title.endswith(sep):
            return title[: -len(sep)]
    return title


def rel_prefix(url: str) -> str:
    """Relative path from a page back to the site root, e.g. '../../'.

    Directory URLs ("/wiki/troops/") are written as index.html inside that
    directory, so they sit one level deeper than the path segments suggest.
    """
    segments = [seg for seg in url.split("/") if seg]
    depth = len(segments) if url.endswith("/") else len(segments) - 1
    return "../" * max(depth, 0)


def compact_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def strip_tags(markup: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", markup)).strip()


# --------------------------------------------------------------------------- registry
class Registry:
    """Maps 'collection:slug' and bare slugs to a page URL and label."""

    def __init__(self):
        self.by_key: dict[str, dict] = {}
        self.unresolved: list[str] = []

    def add(self, collection: str, slug: str, url: str, label: str):
        record = {"href": url.lstrip("/"), "label": label}
        self.by_key[f"{collection}:{slug}"] = record
        self.by_key.setdefault(slug, record)

    def resolve(self, ref, origin: str) -> dict | None:
        if isinstance(ref, dict):
            if "href" in ref:
                return {"href": ref["href"].lstrip("/"), "label": ref["label"]}
            ref = ref.get("ref", "")
        if ref in self.by_key:
            return dict(self.by_key[ref])
        self.unresolved.append(f"{origin} -> {ref}")
        return None


# --------------------------------------------------------------------------- page build
def section_list(raw_sections, prefix=""):
    out = []
    for i, sec in enumerate(raw_sections or []):
        out.append(
            {
                "id": sec.get("id") or slugify(sec["h"]) or f"{prefix}s{i}",
                "h": sec["h"],
                "body": sec["body"],
            }
        )
    return out


def jsonld_breadcrumbs(site, crumbs):
    items = []
    for i, crumb in enumerate(crumbs, start=1):
        item = {"@type": "ListItem", "position": i, "name": crumb["label"]}
        if crumb.get("href") is not None:
            item["item"] = f"{site['base_url']}/{crumb['href'].lstrip('/')}"
        items.append(item)
    return compact_json(
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}
    )


def jsonld_faq(faq):
    return compact_json(
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f["q"],
                    "acceptedAnswer": {"@type": "Answer", "text": strip_tags(f["a"])},
                }
                for f in faq
            ],
        }
    )


def jsonld_article(site, page, kind="Article"):
    doc = {
        "@context": "https://schema.org",
        "@type": kind,
        "headline": page["h1"],
        "description": page["description"],
        "url": f"{site['base_url']}{page['url']}",
        "dateModified": page.get("iso_updated", site["iso_updated"]),
        "inLanguage": "en",
        # Reference the single organization and website nodes declared on the
        # homepage. Re-declaring them inline on every page mints ~200 anonymous
        # organisations instead of accumulating weight on one.
        "isPartOf": {"@id": site["website"]["@id"]},
        "publisher": {"@id": site["organization"]["@id"]},
        "about": {"@type": "VideoGame", "name": "Clash of Clans", "publisher": "Supercell"},
    }
    if page.get("author"):
        doc["author"] = {"@type": "Organization", "name": page["author"]}
    return compact_json(doc)


def jsonld_itemlist(site, groups):
    elements, pos = [], 1
    for group in groups:
        for item in group.get("links", []):
            elements.append(
                {
                    "@type": "ListItem",
                    "position": pos,
                    "name": item["label"],
                    "url": f"{site['base_url']}/{item['href'].lstrip('/')}",
                }
            )
            pos += 1
    return compact_json(
        {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": elements}
    )


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report unresolved links and TODO cells")
    args = ap.parse_args()

    site = load("site")
    if not site:
        sys.exit("error: _build/data/site.json missing")
    site.setdefault("todo", "TODO")

    env = Environment(
        loader=FileSystemLoader(str(TPL_DIR)),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        autoescape=False,  # bodies are authored HTML fragments
    )

    registry = Registry()
    written: list[tuple[str, str, str]] = []  # (url, priority, title)
    todo_count = 0

    # ---- pass 1: register every URL so cross-links resolve in any order
    collections: dict[str, dict] = {}
    for name, folder in WIKI_COLLECTIONS:
        data = load(name)
        if not data:
            continue
        collections[name] = {"data": data, "folder": folder}
        registry.add(name, "index", f"/{folder}/", data.get("hub", {}).get("nav_label", name.title()))
        for entry in data.get("entries", []):
            registry.add(name, entry["slug"], f"/{folder}/{entry['slug']}.html", entry["name"])

    tutorials = load("tutorials")
    registry.add("tutorials", "index", "/tutorials/", "Tutorials")
    for entry in tutorials.get("entries", []):
        registry.add("tutorials", entry["slug"], f"/tutorials/{entry['slug']}.html", entry["name"])

    registry.add("wiki", "index", "/wiki/", "The Clash of Clans wiki")

    news = load("news")
    registry.add("news", "index", "/news/", "News")
    for post in news.get("entries", []):
        registry.add("news", post["slug"], f"/news/{post['slug']}.html", post["name"])

    # hand-written guides, so wiki pages can link across to them
    for guide in site.get("guides", []):
        registry.add("guides", guide["slug"], guide["href"], guide["label"])

    # ---- render helper
    def render(template: str, page: dict, priority: str):
        nonlocal todo_count
        for key, default in (
            ("section", "wiki"), ("wide", False), ("og_type", "article"),
            ("tags", None), ("crumbs", None), ("byline", None), ("jsonld", []),
            ("related", None), ("show_tool_note", False), ("quick", None),
            ("sections", []), ("tables", None), ("faq", None), ("groups", []),
            ("intro", None), ("steps", None), ("steps_heading", "Step by step"),
            ("sources", None), ("author", None), ("source", None),
            ("has_todo", False), ("stat_only", False),
        ):
            page.setdefault(key, default)
        # Declare the organization and website nodes on every page, keyed by a
        # stable @id that Article.publisher references. Consumers process pages
        # independently, so a bare @id reference would leave publisher dangling and
        # cost the name and logo that Article rich results expect; an identical @id
        # on every page is what merges them into one entity.
        if site.get("organization") and site.get("website"):
            page["jsonld"] = [
                compact_json({
                    "@context": "https://schema.org",
                    "@graph": [site["organization"], site["website"]],
                })
            ] + list(page.get("jsonld") or [])

        for group in page["groups"]:
            group.setdefault("blurb", None)
            group.setdefault("style", "cards")
            group.setdefault("links", [])
            for link in group["links"]:
                link.setdefault("blurb", "")
        page.setdefault("iso_updated", site["iso_updated"])
        page.setdefault("updated", site["updated"])
        page.setdefault("description", page.get("summary", "")[:300])
        if "head_title" not in page:
            base = page["h1"]
            branded = f"{base} | {site['name']}"
            page["head_title"] = branded if len(branded) <= 60 else base
        page["head_title"] = trim_title(page["head_title"], site["name"])
        out_path = ROOT / page["url"].lstrip("/")
        if page["url"].endswith("/"):
            out_path = out_path / "index.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        markup = env.get_template(template).render(site=site, page=page, rel=rel_prefix(page["url"]))
        out_path.write_text(markup, encoding="utf-8")
        todo_count += markup.count(f'class="todo"')
        written.append((page["url"], priority, page["h1"]))

    def resolve_related(entry, origin):
        out = []
        for ref in entry.get("related", []):
            hit = registry.resolve(ref, origin)
            if hit:
                out.append(hit)
        return out

    # ---- pass 2: wiki entries + section hubs
    wiki_groups = []
    for name, folder in WIKI_COLLECTIONS:
        bundle = collections.get(name)
        if not bundle:
            continue
        data, folder = bundle["data"], bundle["folder"]
        hub = data.get("hub", {})
        entries = data.get("entries", [])

        for entry in entries:
            url = f"/{folder}/{entry['slug']}.html"
            crumbs = [
                {"label": "Home", "href": ""},
                {"label": "Wiki", "href": "wiki/"},
                {"label": hub.get("nav_label", name.title()), "href": f"{folder}/"},
                {"label": entry["name"], "href": None},
            ]
            page = {
                "url": url,
                "section": "wiki",
                "h1": entry.get("h1", entry["name"]),
                "head_title": entry.get(
                    "head_title", f"{entry['name']} — Clash of Clans Wiki | {site['name']}"
                ),
                "description": entry["description"],
                "summary": entry["summary"],
                "quick": entry.get("quick"),
                "tags": entry.get("tags"),
                "sections": section_list(entry.get("sections")),
                "tables": entry.get("tables"),
                "faq": entry.get("faq"),
                "related": resolve_related(entry, url),
                "crumbs": crumbs,
                "show_tool_note": entry.get("show_tool_note", False),
                "iso_updated": entry.get("iso_updated", site["iso_updated"]),
                # entry-level source wins: hand-written collections carry no
                # collection source, but individual pages may embed generated tables.
                "source": entry.get("source") or data.get("source"),
                "has_todo": any(
                    site["todo"] in row
                    for tbl in entry.get("tables", [])
                    for row in tbl["rows"]
                ) or site["todo"] in (entry.get("quick") or {}).values(),
                "stat_only": not entry.get("has_prose", True),
            }
            page["jsonld"] = [
                jsonld_breadcrumbs(site, crumbs),
                jsonld_article(site, page),
            ] + ([jsonld_faq(entry["faq"])] if entry.get("faq") else [])
            render("entry.html.j2", page, entry.get("priority", "0.6"))

        # section hub
        hub_items = [
            {
                "href": f"{folder}/{e['slug']}.html",
                "label": e["name"],
                "blurb": e.get("blurb", e["description"])[:120],
            }
            for e in entries
        ]
        groups = hub.get("groups")
        if groups:
            built_groups = []
            for g in groups:
                items = [i for i in hub_items if i["label"] in g["members"]]
                built_groups.append(
                    {
                        "id": slugify(g["h"]),
                        "h": g["h"],
                        "blurb": g.get("blurb"),
                        "style": g.get("style", "cards"),
                        "links": items,
                    }
                )
            listed = {i["label"] for g in built_groups for i in g["links"]}
            leftovers = [i for i in hub_items if i["label"] not in listed]
            if leftovers:
                built_groups.append(
                    {"id": "more", "h": "Also in this section", "style": "list", "links": leftovers}
                )
        else:
            built_groups = [
                {"id": "all", "h": hub.get("list_heading", "All pages"), "style": "cards", "links": hub_items}
            ]

        hub_url = f"/{folder}/"
        crumbs = [
            {"label": "Home", "href": ""},
            {"label": "Wiki", "href": "wiki/"},
            {"label": hub.get("nav_label", name.title()), "href": None},
        ]
        hub_page = {
            "url": hub_url,
            "section": "wiki",
            "h1": hub.get("h1", hub.get("nav_label", name.title())),
            "head_title": hub.get("head_title", f"{hub.get('h1', name.title())} | {site['name']}"),
            "description": hub.get("description", ""),
            "summary": hub.get("summary", ""),
            "sections": section_list(hub.get("sections")),
            "groups": built_groups,
            "faq": hub.get("faq"),
            "related": resolve_related(hub, hub_url),
            "crumbs": crumbs,
            "wide": True,
            "og_type": "website",
            "source": data.get("source"),
        }
        hub_page["jsonld"] = [
            jsonld_breadcrumbs(site, crumbs),
            jsonld_itemlist(site, built_groups),
        ] + ([jsonld_faq(hub["faq"])] if hub.get("faq") else [])
        render("hub.html.j2", hub_page, hub.get("priority", "0.8"))

        wiki_groups.append(
            {
                "h": hub.get("nav_label", name.title()),
                "blurb": hub.get("summary", ""),
                "href": f"{folder}/",
                "count": len(entries),
            }
        )

    # ---- tutorials
    for entry in tutorials.get("entries", []):
        url = f"/tutorials/{entry['slug']}.html"
        crumbs = [
            {"label": "Home", "href": ""},
            {"label": "Tutorials", "href": "tutorials/"},
            {"label": entry["name"], "href": None},
        ]
        page = {
            "url": url,
            "section": "tutorials",
            "h1": entry.get("h1", entry["name"]),
            "head_title": entry.get("head_title", f"{entry['name']} | {site['name']}"),
            "description": entry["description"],
            "summary": entry["summary"],
            "quick": entry.get("quick"),
            "tags": entry.get("tags"),
            "intro": entry.get("intro"),
            "steps": entry.get("steps"),
            "steps_heading": entry.get("steps_heading", "Step by step"),
            "sections": section_list(entry.get("sections")),
            "faq": entry.get("faq"),
            "related": resolve_related(entry, url),
            "crumbs": crumbs,
            "show_tool_note": entry.get("show_tool_note", False),
        }
        kind = "HowTo" if entry.get("steps") else "Article"
        page["jsonld"] = [jsonld_breadcrumbs(site, crumbs), jsonld_article(site, page, kind)] + (
            [jsonld_faq(entry["faq"])] if entry.get("faq") else []
        )
        render("tutorial.html.j2", page, entry.get("priority", "0.7"))

    if tutorials:
        hub = tutorials.get("hub", {})
        items = [
            {
                "href": f"tutorials/{e['slug']}.html",
                "label": e["name"],
                "blurb": e.get("blurb", e["description"])[:130],
            }
            for e in tutorials.get("entries", [])
        ]
        built_groups = []
        for g in hub.get("groups", []):
            built_groups.append(
                {
                    "id": slugify(g["h"]),
                    "h": g["h"],
                    "blurb": g.get("blurb"),
                    "style": g.get("style", "cards"),
                    "links": [i for i in items if i["label"] in g["members"]],
                }
            )
        listed = {i["label"] for g in built_groups for i in g["links"]}
        leftovers = [i for i in items if i["label"] not in listed]
        if leftovers:
            built_groups.append({"id": "more", "h": "More tutorials", "style": "cards", "links": leftovers})
        crumbs = [{"label": "Home", "href": ""}, {"label": "Tutorials", "href": None}]
        hub_page = {
            "url": "/tutorials/",
            "section": "tutorials",
            "h1": hub.get("h1", "Clash of Clans Tutorials"),
            "head_title": hub.get("head_title", f"Clash of Clans Tutorials | {site['name']}"),
            "description": hub.get("description", ""),
            "summary": hub.get("summary", ""),
            "sections": section_list(hub.get("sections")),
            "groups": built_groups,
            "faq": hub.get("faq"),
            "related": resolve_related(hub, "/tutorials/"),
            "crumbs": crumbs,
            "wide": True,
            "og_type": "website",
            "source": data.get("source"),
        }
        hub_page["jsonld"] = [
            jsonld_breadcrumbs(site, crumbs),
            jsonld_itemlist(site, built_groups),
        ]
        render("hub.html.j2", hub_page, "0.9")

    # ---- news
    posts_meta = []
    for post in news.get("entries", []):
        url = f"/news/{post['slug']}.html"
        crumbs = [
            {"label": "Home", "href": ""},
            {"label": "News", "href": "news/"},
            {"label": post["name"], "href": None},
        ]
        page = {
            "url": url,
            "section": "news",
            "h1": post.get("h1", post["name"]),
            "head_title": post.get("head_title", f"{post['name']} | {site['name']}"),
            "description": post["description"],
            "summary": post["summary"],
            "updated": post["date_label"],
            "byline": post.get("byline"),
            "tags": post.get("tags"),
            "sections": section_list(post.get("sections")),
            "sources": post.get("sources"),
            "related": resolve_related(post, url),
            "crumbs": crumbs,
            "iso_updated": post["date"],
        }
        page["jsonld"] = [jsonld_breadcrumbs(site, crumbs), jsonld_article(site, page, "NewsArticle")]
        render("news_post.html.j2", page, post.get("priority", "0.6"))
        posts_meta.append(
            {
                "title": post["name"],
                "url": url,
                "description": post["description"],
                "date": post["date"],
                "date_label": post["date_label"],
                "rfc822": format_datetime(
                    datetime.fromisoformat(post["date"]).replace(tzinfo=timezone.utc)
                ),
            }
        )

    posts_meta.sort(key=lambda p: p["date"], reverse=True)
    news_hub = news.get("hub", {})
    crumbs = [{"label": "Home", "href": ""}, {"label": "News", "href": None}]
    news_items = [
        {"href": p["url"].lstrip("/"), "label": p["title"], "blurb": f"{p['date_label']} — {p['description'][:110]}"}
        for p in posts_meta
    ]
    news_page = {
        "url": "/news/",
        "section": "news",
        "h1": news_hub.get("h1", "Clash of Clans News"),
        "head_title": news_hub.get("head_title", f"Clash of Clans News | {site['name']}"),
        "description": news_hub.get("description", site.get("news_description", "")),
        "summary": news_hub.get("summary", ""),
        "sections": section_list(news_hub.get("sections")),
        "groups": [{"id": "latest", "h": "Latest", "style": "cards", "links": news_items}]
        if news_items
        else [],
        "faq": news_hub.get("faq"),
        "related": resolve_related(news_hub, "/news/"),
        "crumbs": crumbs,
        "wide": True,
        "og_type": "website",
    }
    news_page["jsonld"] = [jsonld_breadcrumbs(site, crumbs)]
    render("hub.html.j2", news_page, "0.8")

    feed = env.get_template("feed.xml.j2").render(site=site, posts=posts_meta)
    (ROOT / "news").mkdir(exist_ok=True)
    (ROOT / "news" / "feed.xml").write_text(feed, encoding="utf-8")

    # ---- top-level wiki hub
    wiki = load("wiki")
    crumbs = [{"label": "Home", "href": ""}, {"label": "Wiki", "href": None}]
    groups = [
        {
            "id": "sections",
            "h": wiki.get("list_heading", "Browse the wiki"),
            "style": "cards",
            "links": [
                {"href": g["href"], "label": g["h"], "blurb": f"{g['count']} pages — {g['blurb'][:110]}"}
                for g in wiki_groups
            ],
        }
    ]
    for extra in wiki.get("groups", []):
        groups.append(
            {
                "id": slugify(extra["h"]),
                "h": extra["h"],
                "blurb": extra.get("blurb"),
                "style": extra.get("style", "list"),
                "links": [
                    {**(registry.resolve(m, "/wiki/") or {"href": "", "label": m}), "blurb": ""}
                    for m in extra["members"]
                ],
            }
        )
    wiki_page = {
        "url": "/wiki/",
        "section": "wiki",
        "h1": wiki.get("h1", "Clash of Clans Wiki"),
        "head_title": wiki.get("head_title", f"Clash of Clans Wiki | {site['name']}"),
        "description": wiki.get("description", ""),
        "summary": wiki.get("summary", ""),
        "sections": section_list(wiki.get("sections")),
        "groups": groups,
        "faq": wiki.get("faq"),
        "related": resolve_related(wiki, "/wiki/"),
        "crumbs": crumbs,
        "wide": True,
        "og_type": "website",
    }
    wiki_page["jsonld"] = [jsonld_breadcrumbs(site, crumbs), jsonld_itemlist(site, groups)]
    render("hub.html.j2", wiki_page, "0.9")

    # ---- sitemap
    urls = [(u, p) for u, p in STATIC_URLS]
    urls += [(g["href"], g.get("priority", "0.7")) for g in site.get("guides", [])]
    urls += [(u, p) for u, p, _ in written]
    seen, lines = set(), []
    for url, priority in urls:
        loc = f"{site['base_url']}/{url.lstrip('/')}" if url != "/" else f"{site['base_url']}/"
        if loc in seen:
            continue
        seen.add(loc)
        lines.append(
            f"  <url><loc>{loc}</loc><lastmod>{site['iso_updated']}</lastmod>"
            f"<priority>{priority}</priority></url>"
        )
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(lines)
        + "\n</urlset>\n",
        encoding="utf-8",
    )

    # ---- llms.txt
    def bullet(url, label):
        return f"- [{label}]({site['base_url']}/{url.lstrip('/')})"

    llms = [f"# {site['name']}", "", f"> {site['llms_summary']}", "", site["llms_note"], ""]
    llms += ["## Clash of Clans wiki", bullet("/wiki/", "Wiki index")]
    for group in wiki_groups:
        llms.append(bullet(group["href"], f"{group['h']} ({group['count']} pages)"))
    llms += ["", "## Tutorials", bullet("/tutorials/", "Tutorial index")]
    for entry in tutorials.get("entries", [])[:14]:
        llms.append(bullet(f"/tutorials/{entry['slug']}.html", entry["name"]))
    llms += ["", "## News", bullet("/news/", "News index"), bullet("/news/feed.xml", "RSS feed")]
    llms += ["", "## Bot guides"]
    for guide in site.get("guides", []):
        llms.append(bullet(guide["href"], guide["label"]))
    llms += ["", "## Product", bullet("/#pricing", "Pricing"), bullet("/#download", "Download"), ""]
    (ROOT / "llms.txt").write_text("\n".join(llms), encoding="utf-8")

    # ---- prune stale output
    # Entries removed from the data (an event unit newly excluded, a renamed slug)
    # otherwise leave their old HTML on disk, where it deploys as an orphan page:
    # live, thin, zero inbound links and absent from the sitemap.
    kept = {(ROOT / u.lstrip("/")).resolve() for u, _, _ in written}
    kept |= {(ROOT / u.lstrip("/") / "index.html").resolve() for u, _, _ in written if u.endswith("/")}
    pruned = []
    for section in ("wiki", "tutorials", "news"):
        for stale in (ROOT / section).rglob("*.html"):
            if stale.resolve() not in kept:
                stale.unlink()
                pruned.append(str(stale.relative_to(ROOT)))
    for section in ("wiki", "tutorials", "news"):
        for d in sorted((ROOT / section).rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    # ---- report
    print(f"built {len(written)} pages")
    if pruned:
        print(f"  pruned        : {len(pruned)} stale page(s)")
        for x in pruned[:10]:
            print(f"      - {x}")
    print(f"  wiki sections : {len(wiki_groups)}")
    print(f"  tutorials     : {len(tutorials.get('entries', []))}")
    print(f"  news posts    : {len(posts_meta)}")
    print(f"  sitemap urls  : {len(seen)}")
    print(f"  TODO cells    : {todo_count}")
    if registry.unresolved:
        print(f"\n{len(registry.unresolved)} unresolved link(s):")
        for item in sorted(set(registry.unresolved)):
            print(f"  ! {item}")
        if args.check:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
