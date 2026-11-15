"""Generates the bundled logo and Windows icon.

Run from the repository root:

    .venv\\Scripts\\python.exe scripts\\make_assets.py

The output is deterministic, so re-running it produces identical files.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

SUPERSAMPLE = 4
SIZE = 256
CANVAS = SIZE * SUPERSAMPLE

NAVY = (11, 27, 51, 255)
BLUE = (37, 99, 235, 255)
CYAN = (6, 182, 212, 255)
WHITE = (255, 255, 255, 255)


def _lerp(a, b, t: float):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def _gradient(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        # Diagonal feel: blend horizontally as well, row by row.
        for x in range(0, size, 4):
            t = (x + y) / (2 * max(1, size - 1))
            draw.rectangle([x, y, x + 3, y], fill=_lerp(BLUE[:3], CYAN[:3], t))
    return image


def make_mark() -> Image.Image:
    mark = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    gradient = _gradient(CANVAS)

    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, CANVAS - 1, CANVAS - 1), radius=round(CANVAS * 0.23), fill=255
    )
    mark.paste(gradient, (0, 0), mask)

    # Navy inset so the gradient reads as a frame.
    inset = round(CANVAS * 0.055)
    inner = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ImageDraw.Draw(inner).rounded_rectangle(
        (inset, inset, CANVAS - inset - 1, CANVAS - inset - 1),
        radius=round(CANVAS * 0.19),
        fill=NAVY,
    )
    mark.alpha_composite(inner)

    draw = ImageDraw.Draw(mark)
    # Play triangle: the "launch" idea, readable down to 16 px.
    left = CANVAS * 0.385
    right = CANVAS * 0.685
    top = CANVAS * 0.325
    bottom = CANVAS * 0.675
    draw.polygon(
        [(left, top), (left, bottom), (right, CANVAS / 2)],
        fill=WHITE,
    )

    # Cyan underline: ties the mark to the app's accent colour.
    draw.rounded_rectangle(
        [CANVAS * 0.385, CANVAS * 0.755, CANVAS * 0.615, CANVAS * 0.785],
        radius=CANVAS * 0.015,
        fill=CYAN,
    )
    return mark


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    mark = make_mark().resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    mark.save(ASSETS / "logo.png", "PNG", optimize=True)
    mark.save(ASSETS / "app_icon.png", "PNG", optimize=True)
    mark.save(
        ASSETS / "app_icon.ico",
        "ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    for name in ("logo.png", "app_icon.png", "app_icon.ico"):
        path = ASSETS / name
        print(f"{name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
