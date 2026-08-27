#!/usr/bin/env python3
"""Web-size the section banners into assets/banners/.

    python3 _build/banners.py

Sources are in ../coc-gamefiles/art/banners/ -- twelve original illustrations,
generated rather than extracted, because there is nothing in the game files that
serves this purpose and imitating Supercell's own art here would be a worse idea
than not drawing anything. They are deliberately generic medieval-fantasy
scenery: no characters, no signage, nothing resembling any real game's
trademarks. They decorate the section hubs; every picture of an actual troop or
building on this site still comes out of the game's own atlases.

Kept out of the repository at full size (2 MB each) and committed only as the
web copies.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent
SOURCE = ROOT.parent / "coc-gamefiles" / "art" / "banners"
OUT = ROOT / "assets" / "banners"

WIDTH = 1400


def main() -> int:
    if not SOURCE.exists():
        print(f"no banner sources at {SOURCE}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.webp"):
        stale.unlink()
    total = 0
    for path in sorted(SOURCE.glob("*.png")):
        im = Image.open(path).convert("RGB")
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        dest = OUT / f"{path.stem}.webp"
        im.save(dest, "WEBP", quality=78, method=6)
        total += dest.stat().st_size
        print(f"  {dest.name:22} {im.width}x{im.height}  {dest.stat().st_size/1000:.0f} kB")
    print(f"\n{len(list(OUT.glob('*.webp')))} banners, {total/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
