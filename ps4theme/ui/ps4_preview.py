"""A small mock of the PS4 home screen used by the Appearance tab.

The image is rendered with Pillow so it can show the real background, the
chosen function icons, the text/focus colours and the dimmer overlays.  It is
not a perfect replica of the firmware; it is a fast, honest preview of how the
colours and icons combine.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

from .. import constants as C
from .. import images
from .widgets import Colors, load_font


def _argb(value: str, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Parse ``#AARRGGBB`` (the format theme.xml uses) into Pillow RGBA."""
    text = (value or "").strip().lstrip("#")
    if len(text) != 8:
        return default
    try:
        alpha = int(text[0:2], 16)
        red = int(text[2:4], 16)
        green = int(text[4:6], 16)
        blue = int(text[6:8], 16)
    except ValueError:
        return default
    return (red, green, blue, alpha)


def _gradient(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        colour = (
            round(12 + 10 * t),
            round(34 + 46 * t),
            round(70 + 80 * t),
            255,
        )
        draw.line([(0, y), (width, y)], fill=colour)
    return image


@lru_cache(maxsize=64)
def _placeholder(name: str, size: int) -> Image.Image:
    return images.placeholder_icon(name, size)


def _icon(project, theme, kind: str, name: str, size: int) -> Image.Image:
    value = theme.icon_for(kind, name)
    path = project.path_for(value) if value else None
    if path and path.is_file():
        try:
            return images.fit_contain(images.open_image(path), (size, size))
        except images.ImageError:
            pass
    return _placeholder(name, max(32, size)).resize((size, size), Image.Resampling.LANCZOS)


def render_ps4_preview(theme, project, size: tuple[int, int] = (720, 405)) -> Image.Image:
    width, height = size
    background_path = project.path_for(theme.background) if theme.background else None
    if background_path and background_path.is_file():
        try:
            canvas = images.fit_cover(images.open_image(background_path), size, opaque=True).convert("RGBA")
        except images.ImageError:
            canvas = _gradient(size)
    else:
        canvas = _gradient(size)

    # Home-screen dimmer, exactly as theme.xml will carry it.
    dimmer = _argb(theme.home_dimmer, (0, 0, 0, 0))
    if dimmer[3] > 0:
        canvas.alpha_composite(Image.new("RGBA", size, dimmer))

    # A soft top scrim keeps the icons legible on bright artwork.
    scrim = Image.new("RGBA", size, (0, 0, 0, 0))
    scrim_draw = ImageDraw.Draw(scrim)
    for y in range(96):
        scrim_draw.line(
            [(0, y), (width, y)],
            fill=(4, 12, 26, round(112 * (1 - y / 96))),
        )
    canvas.alpha_composite(scrim)

    draw = ImageDraw.Draw(canvas)
    focus = _argb(theme.focus_color, (30, 155, 255, 255))
    text_colour = _argb(theme.font_color, (255, 255, 255, 255))
    shadow_colour = _argb(theme.font_shadow_color, (0, 0, 0, 255))

    # Function icon row.
    icon_size = 42
    gap = 13
    x = 22
    y = 17
    for index, name in enumerate(C.FUNCTION_ICONS):
        tile = Image.new("RGBA", (icon_size + 12, icon_size + 12), (0, 0, 0, 0))
        tile_draw = ImageDraw.Draw(tile)
        tile_draw.rounded_rectangle(
            [0, 0, tile.width - 1, tile.height - 1],
            radius=12,
            fill=(255, 255, 255, 18),
        )
        icon = _icon(project, theme, "function", name, icon_size)
        tile.alpha_composite(icon, (6, 6))
        canvas.alpha_composite(tile, (x - 6, y - 6))
        selected = index == 4
        if selected:
            box = [x - 9, y - 9, x + icon_size + 8, y + icon_size + 8]
            draw.rounded_rectangle(
                box,
                radius=14,
                outline=(focus[0], focus[1], focus[2], max(140, focus[3])),
                width=3,
            )
        x += icon_size + gap + 4

    # Clock, like the real home screen.
    clock_font = load_font(False, 16)
    draw.text((width - 62, 18), "12:00", font=clock_font, fill=(255, 255, 255, 205))

    # Bottom content icons.
    content_size = 30
    x = 24
    y = height - content_size - 20
    for name in C.CONTENT_ICONS:
        icon = _icon(project, theme, "content", name, content_size)
        canvas.alpha_composite(icon, (x, y))
        x += content_size + 14

    # Headline.
    title = "Themes"
    subtitle = theme.name.strip() or "Theme Settings"
    title_font = load_font(True, 34)
    subtitle_font = load_font(False, 15)
    title_x, title_y = 26, height - 150
    if shadow_colour[3] > 0:
        draw.text((title_x + 2, title_y + 2), title, font=title_font, fill=shadow_colour)
    draw.text((title_x, title_y), title, font=title_font, fill=text_colour)

    subtitle_colour = (text_colour[0], text_colour[1], text_colour[2], min(210, text_colour[3]))
    if shadow_colour[3] > 0:
        draw.text((title_x + 1, title_y + 46), subtitle, font=subtitle_font, fill=shadow_colour)
    draw.text((title_x, title_y + 45), subtitle, font=subtitle_font, fill=subtitle_colour)

    # A thin cyan line ties the preview to the app without pretending to be UI.
    draw.rounded_rectangle(
        [26, height - 18, 26 + 58, height - 15],
        radius=2,
        fill=(*_hex(Colors.CYAN), 220),
    )
    return canvas.convert("RGB")


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
