"""One-shot: build app_icon.png + app_icon.ico from a source image (Pillow). Run from repo root."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path, help="Source PNG (e.g. Gemini export)")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    out_png = root / "rawview" / "qt_ui" / "resources" / "app_icon.png"
    out_ico = root / "rawview" / "qt_ui" / "resources" / "app_icon.ico"
    wix_ico = root / "packaging" / "wix" / "app_icon.ico"
    out_png.parent.mkdir(parents=True, exist_ok=True)

    im = Image.open(args.source).convert("RGBA")
    max_side = 512
    w, h = im.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox = (side - im.width) // 2
    oy = (side - im.height) // 2
    sq.paste(im, (ox, oy), im)
    sq.save(out_png, format="PNG")

    # Pillow embeds every size when saving one high-res image + explicit sizes= (append_images is unreliable).
    master = sq.resize((256, 256), Image.Resampling.LANCZOS)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(out_ico, format="ICO", sizes=ico_sizes)
    wix_ico.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_ico, wix_ico)
    print(out_png, out_png.stat().st_size, "bytes")
    print(out_ico, out_ico.stat().st_size, "bytes")
    print(wix_ico)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
