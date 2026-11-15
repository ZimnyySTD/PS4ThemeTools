"""Pillow image pipeline.

Everything that becomes a PNG inside the theme is produced here.  Images are
always scaled with "cover" (fill the frame, crop the overflow); the PS4 does
not letterbox and stretching would ruin the artwork.

The only special case is the function-icon glow: the console expects a second
152x152 file next to the 128x128 icon, so it is generated from the same
source with a soft cyan halo.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import constants as C

Image.MAX_IMAGE_PIXELS = 200_000_000

RGB = tuple[int, int, int]


class ImageError(RuntimeError):
    """The image could not be read or processed."""


def open_image(path: Path) -> Image.Image:
    """Opens any Pillow-supported image as RGBA, honouring EXIF rotation."""
    try:
        image = Image.open(path)
        image.load()
    except (OSError, ValueError) as exc:
        raise ImageError(f"Cannot read image {Path(path).name}: {exc}") from exc
    image = ImageOps.exif_transpose(image)
    return image.convert("RGBA")


def flatten(image: Image.Image, background: RGB = (0, 0, 0)) -> Image.Image:
    """Composites transparency over a solid colour and returns RGB."""
    if image.mode != "RGBA":
        return image.convert("RGB")
    canvas = Image.new("RGB", image.size, background)
    canvas.paste(image, mask=image.getchannel("A"))
    return canvas


def fit_cover(image: Image.Image, size: tuple[int, int], *, opaque: bool = False,
              background: RGB = (0, 0, 0)) -> Image.Image:
    """Scales to fill ``size`` exactly and crops the overflow from the centre."""
    width, height = size
    if width <= 0 or height <= 0:
        raise ImageError(f"Invalid target size {size}.")
    source = image.convert("RGBA")
    scale = max(width / source.width, height / source.height)
    new_size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    resized = source.resize(new_size, Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    cropped = resized.crop((left, top, left + width, top + height))
    return flatten(cropped, background) if opaque else cropped


def fit_contain(image: Image.Image, size: tuple[int, int], *, background=None) -> Image.Image:
    """Scales to fit inside ``size`` without cropping (UI thumbnails)."""
    width, height = size
    source = image.convert("RGBA")
    scale = min(width / source.width, height / source.height)
    new_size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    resized = source.resize(new_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), background or (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    return canvas


def save_png(image: Image.Image, path: Path, *, opaque: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    target = flatten(image) if opaque else image.convert("RGBA")
    target.save(path, "PNG", optimize=True)
    return path


def make_glow(icon: Image.Image) -> Image.Image:
    """152x152 version of a 128x128 function icon with a soft halo."""
    base = icon.convert("RGBA")
    if base.size != C.FUNCTION_ICON_SIZE:
        base = fit_cover(base, C.FUNCTION_ICON_SIZE)
    canvas = Image.new("RGBA", C.FUNCTION_ICON_GLOW_SIZE, (0, 0, 0, 0))
    offset = (
        (C.FUNCTION_ICON_GLOW_SIZE[0] - base.width) // 2,
        (C.FUNCTION_ICON_GLOW_SIZE[1] - base.height) // 2,
    )

    halo = Image.new("RGBA", C.FUNCTION_ICON_GLOW_SIZE, (0, 0, 0, 0))
    tint = Image.new("RGBA", base.size, (34, 211, 238, 0))
    tint.putalpha(base.getchannel("A"))
    halo.alpha_composite(tint, offset)
    halo = halo.filter(ImageFilter.GaussianBlur(7))
    canvas.alpha_composite(halo)
    canvas.alpha_composite(base, offset)
    return canvas


def _blend(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def placeholder_icon(name: str, size: int = 96) -> Image.Image:
    """A deterministic blue/cyan tile used in the icon pickers.

    It is only a UI preview; nothing generated here ends up in a theme unless
    the user actually picks an image.
    """
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    palette = [
        ((37, 99, 235), (34, 211, 238)),
        ((14, 165, 233), (37, 99, 235)),
        ((6, 182, 212), (59, 130, 246)),
        ((29, 78, 216), (6, 182, 212)),
        ((30, 64, 175), (34, 211, 238)),
    ]
    start, end = palette[digest[0] % len(palette)]

    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient = Image.new("RGB", (size, size), start)
    draw = ImageDraw.Draw(gradient)
    for y in range(size):
        draw.line([(0, y), (size, y)], fill=_blend(start, end, y / max(1, size - 1)))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=round(size * 0.24), fill=255
    )
    tile.paste(gradient, (0, 0), mask)

    letters = "".join(part[0] for part in name.split("_")[:2]).upper()[:2] or "?"
    font = None
    for candidate in ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"):
        try:
            font = ImageFont.truetype(candidate, round(size * 0.34))
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    text_draw = ImageDraw.Draw(tile)
    box = text_draw.textbbox((0, 0), letters, font=font)
    text_draw.text(
        ((size - (box[2] - box[0])) / 2 - box[0],
         (size - (box[3] - box[1])) / 2 - box[1]),
        letters,
        font=font,
        fill=(255, 255, 255, 235),
    )
    return tile


def build_image_assets(
    theme,
    project,
    content_dir: Path,
    *,
    fallback_image: Path | None = None,
) -> list[str]:
    """Writes every PNG the theme needs and returns non-fatal warnings.

    ``fallback_image`` is the first extracted video frame for dynamic themes;
    it is used for the thumbnail and the derived icon when the user did not
    pick a separate background.
    """
    warnings: list[str] = []
    content_dir = Path(content_dir)

    background_source = project.path_for(theme.background)
    if not (background_source and background_source.is_file()):
        background_source = fallback_image
    if not (background_source and Path(background_source).is_file()):
        raise ImageError(
            "No background image is available. Pick one in the Theme tab "
            "(dynamic themes can derive it from the video)."
        )

    try:
        background = open_image(Path(background_source))
    except ImageError as exc:
        raise ImageError(str(exc)) from exc

    # Static themes need both 1920x1080 screens.  A dynamic theme hides them
    # behind the RAF scene, and the sample theme does not ship them at all.
    if not theme.is_dynamic:
        save_png(
            fit_cover(background, C.STATIC_SIZE, opaque=True),
            content_dir / C.THEME_PATH_HOMESCREEN,
            opaque=True,
        )
        function_source = project.path_for(theme.functionscreen)
        if not (function_source and function_source.is_file()):
            if theme.functionscreen:
                warnings.append("Top-menu background missing; using the main background.")
            function_source = Path(background_source)
        save_png(
            fit_cover(open_image(function_source), C.STATIC_SIZE, opaque=True),
            content_dir / C.THEME_PATH_FUNCTIONSCREEN,
            opaque=True,
        )

    save_png(
        fit_cover(background, C.PREVIEW_SIZE, opaque=True),
        content_dir / C.THEME_PATH_PREVIEW,
        opaque=True,
    )
    save_png(
        fit_cover(background, C.PIC1_SIZE, opaque=True),
        content_dir / C.THEME_PATH_PIC1,
        opaque=True,
    )

    icon_source = project.path_for(theme.icon)
    if not (icon_source and icon_source.is_file()):
        if theme.icon:
            warnings.append("Theme icon missing; deriving one from the background.")
        icon_source = Path(background_source)
    save_png(
        fit_cover(open_image(icon_source), C.THEME_ICON_SIZE),
        content_dir / C.THEME_PATH_ICON0,
    )

    for name in C.FUNCTION_ICONS:
        value = theme.function_icons.get(name, "")
        source = project.path_for(value) if value else None
        if not (source and source.is_file()):
            if value:
                warnings.append(f"Function icon '{C.ICON_LABELS.get(name, name)}' is missing.")
            continue
        icon = fit_cover(open_image(source), C.FUNCTION_ICON_SIZE)
        folder = content_dir / C.THEME_PATH_FUNCTION_ICONS
        save_png(icon, folder / f"{name}.png")
        save_png(make_glow(icon), folder / f"{name}_glow.png")

    for name in C.CONTENT_ICONS:
        value = theme.content_icons.get(name, "")
        source = project.path_for(value) if value else None
        if not (source and source.is_file()):
            if value:
                warnings.append(f"Content icon '{C.ICON_LABELS.get(name, name)}' is missing.")
            continue
        save_png(
            fit_cover(open_image(source), C.CONTENT_ICON_SIZE),
            content_dir / C.THEME_PATH_CONTENT_ICONS / f"{name}.png",
        )

    return warnings
