"""Shared CustomTkinter widgets and visual helpers."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog
from typing import Callable

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from .. import constants as C
from .. import images

Colors = C.Colors

UI_FONT = "Segoe UI"
MONO_FONT = "Consolas"


def font(size: int = 13, weight: str = "normal") -> tuple:
    return (UI_FONT, size, weight)


def elide(text: str, length: int = 52) -> str:
    text = str(text or "")
    if len(text) <= length:
        return text
    return "..." + text[-(length - 3):]


class ScrollPage(ctk.CTkScrollableFrame):
    """A transparent, vertically scrolling page body."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=Colors.BORDER_STRONG,
            scrollbar_button_hover_color=Colors.CYAN,
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)

    def on_show(self) -> None:
        """Called when the page becomes visible; project pages override this."""

    def refresh(self) -> None:
        """Re-read the project; pages that display project data override this."""


class Card(ctk.CTkFrame):
    """White rounded panel with an optional title and description."""

    def __init__(self, master, title: str | None = None, subtitle: str | None = None, **kwargs):
        super().__init__(
            master,
            fg_color=Colors.SURFACE,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER,
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)
        row = 0
        if title:
            heading = ctk.CTkFrame(self, fg_color="transparent")
            heading.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 0))
            heading.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                heading,
                text=title,
                font=font(15, "bold"),
                text_color=Colors.TEXT,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            if subtitle:
                ctk.CTkLabel(
                    heading,
                    text=subtitle,
                    font=font(12),
                    text_color=Colors.TEXT_SOFT,
                    anchor="w",
                    justify="left",
                    wraplength=760,
                ).grid(row=1, column=0, sticky="w", pady=(3, 0))
            row = 1

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=row, column=0, sticky="nsew", padx=20, pady=(14 if title else 18, 18))
        self.body.grid_columnconfigure(0, weight=1)


class FormField(ctk.CTkFrame):
    """Labelled entry that reports every edit through ``on_change``."""

    def __init__(
        self,
        master,
        label: str,
        value: str = "",
        *,
        placeholder: str = "",
        hint: str = "",
        on_change: Callable[[str], None] | None = None,
        width: int = 260,
        show: str | None = None,
    ):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.on_change = on_change
        self._suspend = False

        ctk.CTkLabel(
            self, text=label, font=font(12, "bold"),
            text_color=Colors.TEXT_SOFT, anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.var = tk.StringVar(value=value)
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.var,
            placeholder_text=placeholder,
            height=36,
            width=width,
            corner_radius=8,
            border_width=1,
            border_color=Colors.BORDER_STRONG,
            fg_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT,
            placeholder_text_color=Colors.TEXT_FAINT,
            font=font(13),
            show=show or "",
        )
        self.entry.grid(row=1, column=0, sticky="ew")
        self.var.trace_add("write", self._changed)

        self.hint = ctk.CTkLabel(
            self, text=hint, font=font(11), text_color=Colors.TEXT_FAINT,
            anchor="w", justify="left", wraplength=width,
        )
        if hint:
            self.hint.grid(row=2, column=0, sticky="w", pady=(4, 0))

    def _changed(self, *_args) -> None:
        if self._suspend:
            return
        if self.on_change:
            self.on_change(self.var.get())

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self._suspend = True
        self.var.set(value)
        self._suspend = False

    def set_hint(self, text: str) -> None:
        self.hint.configure(text=text)


class Chip(ctk.CTkLabel):
    """Small coloured status pill."""

    def __init__(self, master, text: str, *, kind: str = "info", **kwargs):
        palette = {
            "info": (Colors.PRIMARY_SOFT, Colors.PRIMARY),
            "success": (Colors.SUCCESS_SOFT, Colors.SUCCESS),
            "warning": (Colors.WARNING_SOFT, Colors.WARNING),
            "danger": (Colors.DANGER_SOFT, Colors.DANGER),
            "neutral": (Colors.SURFACE_ALT, Colors.TEXT_SOFT),
            "cyan": (Colors.CYAN_SOFT, Colors.CYAN),
        }
        background, foreground = palette.get(kind, palette["info"])
        super().__init__(
            master,
            text=text,
            font=font(11, "bold"),
            text_color=foreground,
            fg_color=background,
            corner_radius=8,
            **kwargs,
        )


class StatTile(ctk.CTkFrame):
    def __init__(self, master, label: str, value: str, *, accent: str = Colors.PRIMARY):
        super().__init__(master, fg_color=Colors.SURFACE_ALT, corner_radius=12)
        self.grid_columnconfigure(0, weight=1)
        bar = ctk.CTkFrame(self, fg_color=accent, width=4, height=34, corner_radius=2)
        bar.grid(row=0, column=0, rowspan=2, sticky="w", padx=(12, 0), pady=12)
        self.label = ctk.CTkLabel(
            self, text=label.upper(), font=font(10, "bold"),
            text_color=Colors.TEXT_FAINT, anchor="w",
        )
        self.label.grid(row=0, column=1, sticky="w", padx=(10, 12), pady=(11, 0))
        self.value = ctk.CTkLabel(
            self, text=value, font=font(13, "bold"),
            text_color=Colors.TEXT, anchor="w",
        )
        self.value.grid(row=1, column=1, sticky="w", padx=(10, 12), pady=(0, 11))

    def set(self, value: str) -> None:
        self.value.configure(text=value)


def _blend(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def media_placeholder(size: tuple[int, int], kind: str, caption: str = "") -> Image.Image:
    """Gradient card with a simple pictogram, used when nothing is selected."""
    width, height = size
    image = Image.new("RGBA", (width, height), (11, 27, 51, 255))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        draw.line(
            [(0, y), (width, y)],
            fill=_blend((11, 27, 51), (24, 78, 140), y / max(1, height - 1)) + (255,),
        )

    cyan = (34, 211, 238, 230)
    white = (255, 255, 255, 235)
    scale = min(width, height)
    center_x, center_y = width // 2, height // 2
    if kind == "video":
        radius = max(14, scale // 7)
        draw.ellipse(
            [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
            outline=cyan, width=max(2, scale // 44),
        )
        triangle = [
            (center_x - radius // 3, center_y - radius // 2),
            (center_x - radius // 3, center_y + radius // 2),
            (center_x + radius // 2, center_y),
        ]
        draw.polygon(triangle, fill=white)
    elif kind == "audio":
        bars = [0.35, 0.7, 1.0, 0.55, 0.85, 0.45, 0.65]
        bar_width = max(3, width // 45)
        gap = bar_width
        total = len(bars) * bar_width + (len(bars) - 1) * gap
        start = center_x - total // 2
        for index, factor in enumerate(bars):
            bar_height = int(height * 0.42 * factor)
            x0 = start + index * (bar_width + gap)
            draw.rounded_rectangle(
                [x0, center_y - bar_height // 2, x0 + bar_width, center_y + bar_height // 2],
                radius=bar_width // 2, fill=cyan,
            )
    elif kind == "icon":
        side = int(scale * 0.46)
        draw.rounded_rectangle(
            [center_x - side // 2, center_y - side // 2, center_x + side // 2, center_y + side // 2],
            radius=max(8, side // 6), outline=cyan, width=max(2, scale // 44),
        )
        try:
            label_font = load_font(True, max(12, side // 4))
            text = "512"
            box = draw.textbbox((0, 0), text, font=label_font)
            draw.text(
                (center_x - (box[2] - box[0]) / 2, center_y - (box[3] - box[1]) / 2 - box[1]),
                text, font=label_font, fill=white,
            )
        except Exception:
            pass
    else:
        radius = max(12, scale // 9)
        draw.arc(
            [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
            start=200, end=340, fill=cyan, width=max(2, scale // 50),
        )
        draw.ellipse(
            [center_x - radius // 4, center_y + radius // 3,
             center_x + radius // 4, center_y + radius // 2],
            outline=cyan, width=max(2, scale // 60),
        )
        peak = [
            (center_x - radius, center_y + radius // 2),
            (center_x - radius // 3, center_y - radius // 4),
            (center_x + radius // 5, center_y + radius // 2),
        ]
        draw.polygon(peak, fill=(34, 211, 238, 90))

    if caption:
        caption_font = load_font(False, max(10, scale // 13))
        box = draw.textbbox((0, 0), caption, font=caption_font)
        draw.text(
            ((width - (box[2] - box[0])) / 2, height - (box[3] - box[1]) - max(8, height // 18)),
            caption, font=caption_font, fill=(214, 232, 250, 200),
        )
    return image


_FONT_CACHE: dict[tuple[bool, int], ImageFont.FreeTypeFont] = {}


def load_font(bold: bool, size: int):
    key = (bool(bold), int(size))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    names = ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")
    chosen = None
    for name in names:
        try:
            chosen = ImageFont.truetype(name, int(size))
            break
        except OSError:
            continue
    if chosen is None:
        chosen = ImageFont.load_default()
    _FONT_CACHE[key] = chosen
    return chosen


class FilePicker(ctk.CTkFrame):
    """Preview + choose/remove buttons for an image, video, audio or icon."""

    def __init__(
        self,
        master,
        *,
        title: str,
        hint: str,
        on_choose: Callable[[Path], None],
        on_clear: Callable[[], None],
        kinds: set[str],
        preview_size: tuple[int, int] = (250, 141),
        placeholder_kind: str = "image",
    ):
        super().__init__(master, fg_color="transparent")
        self.on_choose = on_choose
        self.on_clear = on_clear
        self.kinds = kinds
        self.preview_size = preview_size
        self.placeholder_kind = placeholder_kind
        self._image: ctk.CTkImage | None = None
        self._current: Path | None = None

        self.grid_columnconfigure(1, weight=1)

        self.preview = ctk.CTkLabel(
            self,
            text="",
            width=preview_size[0],
            height=preview_size[1],
            fg_color=Colors.SURFACE_ALT,
            corner_radius=10,
        )
        self.preview.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 16))

        ctk.CTkLabel(
            self, text=title, font=font(13, "bold"),
            text_color=Colors.TEXT, anchor="w",
        ).grid(row=0, column=1, sticky="w")

        self.name_label = ctk.CTkLabel(
            self, text="No file selected", font=font(12),
            text_color=Colors.TEXT_SOFT, anchor="w", justify="left",
            wraplength=340,
        )
        self.name_label.grid(row=1, column=1, sticky="w", pady=(3, 6))

        ctk.CTkLabel(
            self, text=hint, font=font(11), text_color=Colors.TEXT_FAINT,
            anchor="w", justify="left", wraplength=390,
        ).grid(row=2, column=1, sticky="w")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=3, column=1, sticky="w", pady=(10, 0))
        self.choose_button = ctk.CTkButton(
            buttons,
            text="Choose file",
            width=118,
            height=32,
            corner_radius=8,
            fg_color=Colors.PRIMARY_SOFT,
            hover_color="#D9E8FF",
            text_color=Colors.PRIMARY,
            font=font(12, "bold"),
            command=self._choose,
        )
        self.choose_button.grid(row=0, column=0)
        self.remove_button = ctk.CTkButton(
            buttons,
            text="Remove",
            width=82,
            height=32,
            corner_radius=8,
            fg_color="transparent",
            hover_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT_SOFT,
            border_width=1,
            border_color=Colors.BORDER,
            font=font(12),
            command=self._clear,
        )
        self.remove_button.grid(row=0, column=1, padx=(8, 0))

        self.show(None)

    def _choose(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(self.kinds))
        path = filedialog.askopenfilename(
            title="Choose a file",
            filetypes=[("Supported files", patterns), ("All files", "*.*")],
        )
        if path:
            self.on_choose(Path(path))

    def _clear(self) -> None:
        self.on_clear()

    def show(self, path: Path | None, caption: str | None = None) -> None:
        self._current = path
        if path and Path(path).is_file() and self.placeholder_kind != "audio":
            try:
                image = images.open_image(Path(path))
                image = images.fit_contain(image, self.preview_size, background=(7, 18, 34, 255))
            except images.ImageError:
                image = media_placeholder(self.preview_size, self.placeholder_kind, "Cannot read image")
                self.name_label.configure(text=f"Cannot read {Path(path).name}", text_color=Colors.DANGER)
        else:
            text = caption or ("No file selected" if not path else Path(path).name)
            image = media_placeholder(self.preview_size, self.placeholder_kind, text)
            if path and Path(path).is_file():
                self.name_label.configure(
                    text=f"{Path(path).name}  (audio preview not available)",
                    text_color=Colors.TEXT,
                )
            elif path:
                self.name_label.configure(text=f"Missing: {Path(path).name}", text_color=Colors.DANGER)
            else:
                self.name_label.configure(text="No file selected", text_color=Colors.TEXT_SOFT)

        if path and Path(path).is_file():
            try:
                size_kb = Path(path).stat().st_size / 1024
                readable = f"{Path(path).name}  ·  {size_kb:,.0f} KB"
                self.name_label.configure(text=readable, text_color=Colors.TEXT)
            except OSError:
                pass
        self._image = ctk.CTkImage(light_image=image, size=self.preview_size)
        self.preview.configure(image=self._image, text="")


class ColorRow(ctk.CTkFrame):
    """Swatch + ARGB entry + system colour picker."""

    def __init__(self, master, label: str, value: str, *, on_change: Callable[[str], None]):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        self.on_change = on_change
        self._suspend = False

        ctk.CTkLabel(
            self, text=label, font=font(12, "bold"),
            text_color=Colors.TEXT_SOFT, width=150, anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.var = tk.StringVar(value=value)
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.var,
            height=32,
            width=130,
            corner_radius=8,
            border_width=1,
            border_color=Colors.BORDER_STRONG,
            fg_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT,
            font=(MONO_FONT, 12),
        )
        self.entry.grid(row=0, column=1, sticky="w", padx=(0, 8))

        self.swatch = ctk.CTkButton(
            self, text="", width=32, height=32, corner_radius=8,
            fg_color=self._swatch_color(value), hover_color=self._swatch_color(value),
            command=self._pick,
        )
        self.swatch.grid(row=0, column=2, padx=(0, 8))

        self.pick = ctk.CTkButton(
            self, text="Pick", width=58, height=32, corner_radius=8,
            fg_color=Colors.PRIMARY_SOFT, hover_color="#D9E8FF",
            text_color=Colors.PRIMARY, font=font(11, "bold"),
            command=self._pick,
        )
        self.pick.grid(row=0, column=3)

        self.var.trace_add("write", self._changed)

    @staticmethod
    def _swatch_color(value: str) -> str:
        try:
            text = value.strip().lstrip("#")
            if len(text) == 8:
                return f"#{text[2:]}"
        except Exception:
            pass
        return Colors.SURFACE_ALT

    def _changed(self, *_args) -> None:
        value = self.var.get()
        if len(value.strip().lstrip("#")) == 8:
            self.swatch.configure(
                fg_color=self._swatch_color(value),
                hover_color=self._swatch_color(value),
            )
        if not self._suspend and self.on_change:
            self.on_change(value)

    def _pick(self) -> None:
        current = self.var.get().strip().lstrip("#")
        alpha = current[:2] if len(current) == 8 else "FF"
        try:
            initial = f"#{current[2:]}" if len(current) == 8 else "#1E9BFF"
        except Exception:
            initial = "#1E9BFF"
        _rgb, hex_color = colorchooser.askcolor(color=initial, title="Choose a colour")
        if not hex_color:
            return
        value = f"#{alpha}{hex_color.lstrip('#').upper()}"
        self._suspend = True
        self.var.set(value)
        self._suspend = False
        self.swatch.configure(fg_color=self._swatch_color(value), hover_color=self._swatch_color(value))
        if self.on_change:
            self.on_change(value)

    def set(self, value: str) -> None:
        self._suspend = True
        self.var.set(value)
        self._suspend = False
        self.swatch.configure(fg_color=self._swatch_color(value), hover_color=self._swatch_color(value))


def add_bottom_spacer(page: ScrollPage, height: int = 18) -> None:
    spacer = ctk.CTkFrame(page, fg_color="transparent", height=height)
    spacer.grid(sticky="ew")
