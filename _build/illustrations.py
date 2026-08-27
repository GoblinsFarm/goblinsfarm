#!/usr/bin/env python3
"""Web-size the drawn illustrations into assets/.

    python3 _build/illustrations.py

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
GAME = ROOT.parent / "coc-gamefiles" / "art"

# (source folder, destination, longest side) -- banners run the width of a hub,
# mascots sit at about 90px beside a callout, so they need very different sizes.
SETS = [("banners", ROOT / "assets" / "banners", 1400),
        ("mascots", ROOT / "assets" / "mascots", 280)]


def main() -> int:
    for name, out, longest in SETS:
        source = GAME / name
        if not source.exists():
            print(f"no {name} sources at {source}")
            continue
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob("*.webp"):
            stale.unlink()
        total = 0
        for path in sorted(source.glob("*.png")):
            im = Image.open(path)
            # The mascots are cut out and have to stay cut out; the banners are
            # full-bleed scenery and gain nothing from an alpha channel.
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
            scale = longest / max(im.width, im.height)
            if scale < 1:
                im = im.resize((round(im.width * scale), round(im.height * scale)),
                               Image.LANCZOS)
            dest = out / f"{path.stem}.webp"
            im.save(dest, "WEBP", quality=80 if im.mode == "RGBA" else 78, method=6)
            total += dest.stat().st_size
        count = len(list(out.glob("*.webp")))
        print(f"  {name:10} {count:3} files  {total/1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
