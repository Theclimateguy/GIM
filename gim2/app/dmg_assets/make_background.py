#!/usr/bin/env python3
"""Render the DMG window background at 1x + 2x and combine into a HiDPI TIFF.

Finder maps the background image's PIXELS to POINTS, so the 1x file must be
exactly the installer window's POINT size (see make_dmg.sh --window-size);
crisp Retina rendering comes from a separate @2x rep combined into one file:

    python3 make_background.py
    tiffutil -cathidpicheck background.png background@2x.png -out background.tiff

make_dmg.sh consumes background.tiff. Re-run this only when the artwork/copy
changes. Palette matches the app's steel theme (Theme.swift).
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 640, 400   # window POINT size — keep in sync with make_dmg.sh --window-size
FONT_PATH = "/System/Library/Fonts/HelveticaNeue.ttc"

TEXT = (242, 243, 245)
MUTED = (154, 160, 170)
FAINT = (110, 115, 124)
ACCENT = (143, 168, 201)
BG = (10, 11, 13)
SURFACE = (21, 23, 27)
LINE = (42, 45, 51)


def render(scale: int, path: str) -> None:
    cw, ch = W * scale, H * scale
    img = Image.new("RGB", (cw, ch), BG)
    d = ImageDraw.Draw(img)

    def s(v):
        return int(round(v * scale))

    # subtle vertical gradient toward the surface tone
    for y in range(ch):
        t = y / ch
        d.line([(0, y), (cw, y)], fill=tuple(int(BG[i] + (SURFACE[i] - BG[i]) * t * 0.5) for i in range(3)))

    d.line([(s(40), s(340)), (s(W - 40), s(340))], fill=LINE, width=max(1, s(1)))

    def font(size, index=0):
        try:
            return ImageFont.truetype(FONT_PATH, s(size), index=index)
        except Exception:
            return ImageFont.load_default()

    def center(text, y, fnt, fill, cx=None):
        b = d.textbbox((0, 0), text, font=fnt)
        x = (cx * scale if cx is not None else cw / 2) - (b[2] - b[0]) / 2
        d.text((x, s(y)), text, font=fnt, fill=fill)

    center("GIM18 — интегрированная модель мира", 34, font(20, 1), TEXT)
    center("Перетащите приложение в папку «Программы»", 66, font(12.5), MUTED)

    # arrow between the app icon (x=180) and Applications (x=460), both at y=200
    ya = s(196)
    x1, x2 = s(180 + 62), s(460 - 62)
    d.line([(x1, ya), (x2 - s(14), ya)], fill=ACCENT, width=max(2, s(2.5)))
    ah = s(11)
    d.polygon([(x2, ya), (x2 - ah, ya - int(ah * 0.6)), (x2 - ah, ya + int(ah * 0.6))], fill=ACCENT)

    center("gim18.local  ·  офлайн, детерминированное ядро  ·  без установки Python/Xcode",
           362, font(11), FAINT)

    img.save(path)
    print("saved", path, img.size)


if __name__ == "__main__":
    render(1, "background.png")
    render(2, "background@2x.png")
    print("now run: tiffutil -cathidpicheck background.png background@2x.png -out background.tiff")
