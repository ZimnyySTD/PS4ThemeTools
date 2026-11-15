"""Appearance tab: theme colour, text colours, dimmers and a live console mock."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from .. import constants as C
from .. import models
from .ps4_preview import render_ps4_preview
from .widgets import (
    Card,
    Colors,
    ColorRow,
    ScrollPage,
    add_bottom_spacer,
    font,
)

#: Rough sRGB equivalents of the eight colours the PS4 exposes in theme.xml.
SWATCHES: dict[int, str] = {
    0: "#1E88E5",
    1: "#E91E63",
    2: "#E53935",
    3: "#1A237E",
    4: "#37474F",
    5: "#C8A24A",
    6: "#7FA8C9",
    7: "#8E24AA",
}

PREVIEW_SIZE = (720, 405)

#: ThemeProject field -> key in C.THEME_XML_DEFAULTS.
DEFAULT_KEYS = {
    "font_color": "fontcolor",
    "font_shadow_color": "fontshadowcolor",
    "focus_color": "focuscolor",
    "home_dimmer": "homescreen_dimmer",
    "function_dimmer": "functionscreen_dimmer",
    "title_dimmer": "titlename_dimmer",
}


class AppearancePage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._refreshing = False
        self._preview_job = None
        self._preview_image: ctk.CTkImage | None = None
        self._swatch_buttons: dict[int, ctk.CTkButton] = {}
        self._swatch_labels: dict[int, ctk.CTkLabel] = {}
        self.color_rows: dict[str, ColorRow] = {}

        self._build_preview_card()
        self._build_color_card()
        self._build_text_card()
        self._build_dimmer_card()
        add_bottom_spacer(self)

    @property
    def theme(self):
        return self.app.project.theme

    @property
    def project(self):
        return self.app.project

    # -- cards -------------------------------------------------------------

    def _build_preview_card(self) -> None:
        card = Card(
            self,
            "Live preview",
            "A quick mock of the home screen using your artwork, icons and colours. "
            "It is an approximation: the console adds its own shadows and transitions.",
        )
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        self.preview = ctk.CTkLabel(
            card.body,
            text="",
            width=PREVIEW_SIZE[0],
            height=PREVIEW_SIZE[1],
            fg_color=Colors.NAVY,
            corner_radius=12,
        )
        self.preview.grid(row=0, column=0, sticky="w")

        footer = ctk.CTkFrame(card.body, fg_color="transparent")
        footer.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        footer.grid_columnconfigure(0, weight=1)
        self.preview_caption = ctk.CTkLabel(
            footer,
            text="",
            font=font(11),
            text_color=Colors.TEXT_FAINT,
            anchor="w",
            justify="left",
        )
        self.preview_caption.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer,
            text="Refresh",
            width=84,
            height=28,
            corner_radius=7,
            fg_color=Colors.PRIMARY_SOFT,
            hover_color="#D9E8FF",
            text_color=Colors.PRIMARY,
            font=font(11, "bold"),
            command=lambda: self._render_preview(),
        ).grid(row=0, column=1, sticky="e")

    def _build_color_card(self) -> None:
        card = Card(
            self,
            "Theme colour",
            "The console's own highlight colour. It tints system menus and the "
            "selection glow; it does not recolour your artwork.",
        )
        card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        body = card.body

        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.grid(row=0, column=0, sticky="w")
        for index, (value, label) in enumerate(C.THEME_COLORS):
            column = index % 4
            group = 0 if index < 4 else 1
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=group, column=column, padx=(0, 14), pady=(0, 12), sticky="w")

            button = ctk.CTkButton(
                cell,
                text="",
                width=64,
                height=36,
                corner_radius=9,
                fg_color=SWATCHES.get(value, Colors.PRIMARY),
                hover_color=SWATCHES.get(value, Colors.PRIMARY),
                border_width=2,
                border_color=Colors.SURFACE,
                command=lambda v=value: self._set_theme_color(v),
            )
            button.grid(row=0, column=0)
            text = ctk.CTkLabel(
                cell,
                text=label,
                font=font(10),
                text_color=Colors.TEXT_SOFT,
                anchor="w",
            )
            text.grid(row=1, column=0, sticky="w", pady=(4, 0))
            self._swatch_buttons[value] = button
            self._swatch_labels[value] = text

        self.color_note = ctk.CTkLabel(
            body,
            text="",
            font=font(11),
            text_color=Colors.TEXT_FAINT,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.color_note.grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_text_card(self) -> None:
        card = Card(
            self,
            "Text & focus",
            "Colours are written as #AARRGGBB: two digits of transparency followed "
            "by red, green and blue. Use FF for fully opaque.",
        )
        card.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        body = card.body

        for row, (field, label) in enumerate((
            ("font_color", "Font colour"),
            ("font_shadow_color", "Font shadow"),
            ("focus_color", "Focus glow"),
        )):
            widget = ColorRow(
                body,
                label,
                C.THEME_XML_DEFAULTS[DEFAULT_KEYS[field]],
                on_change=lambda value, f=field: self._set_color(f, value),
            )
            widget.grid(row=row, column=0, sticky="ew", pady=(0, 8))
            self.color_rows[field] = widget

        note = ctk.CTkLabel(
            body,
            text="Font colour affects labels and the clock; the focus glow is the "
                 "outline around the selected icon.",
            font=font(11),
            text_color=Colors.TEXT_FAINT,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        note.grid(row=3, column=0, sticky="w", pady=(4, 0))

    def _build_dimmer_card(self) -> None:
        card = Card(
            self,
            "Screen dimmers",
            "A transparent black overlay drawn over each screen. Alpha 00 is fully "
            "transparent; a higher alpha darkens the artwork and makes icons pop.",
        )
        card.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        body = card.body

        for row, (field, label) in enumerate((
            ("home_dimmer", "Home screen"),
            ("function_dimmer", "Top menu"),
            ("title_dimmer", "Title name"),
        )):
            widget = ColorRow(
                body,
                label,
                C.THEME_XML_DEFAULTS[DEFAULT_KEYS[field]],
                on_change=lambda value, f=field: self._set_color(f, value),
            )
            widget.grid(row=row, column=0, sticky="ew", pady=(0, 8))
            self.color_rows[field] = widget

        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            footer,
            text="Example: #66000000 is a 40% black dimmer. #00FFFFFF leaves the screen untouched.",
            font=font(11),
            text_color=Colors.TEXT_FAINT,
            anchor="w",
            justify="left",
            wraplength=560,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer,
            text="Reset to defaults",
            width=148,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT_SOFT,
            border_width=1,
            border_color=Colors.BORDER,
            font=font(11),
            command=self._reset_defaults,
        ).grid(row=0, column=1, sticky="e")

    # -- state -------------------------------------------------------------

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        theme = self.theme
        self._refreshing = True
        try:
            for field, widget in self.color_rows.items():
                value = getattr(theme, field)
                if not models.ARGB_RE.match(value or ""):
                    value = C.THEME_XML_DEFAULTS[DEFAULT_KEYS[field]]
                widget.set(value)
            self._update_swatches(theme.themecolor)
        finally:
            self._refreshing = False
        self._update_note()
        self._render_preview()

    def _update_swatches(self, selected: int) -> None:
        for value, button in self._swatch_buttons.items():
            active = value == int(selected)
            button.configure(
                border_width=3 if active else 2,
                border_color=Colors.TEXT if active else Colors.SURFACE,
                height=40 if active else 36,
            )
            self._swatch_labels[value].configure(
                text_color=Colors.TEXT if active else Colors.TEXT_SOFT,
                font=font(10, "bold" if active else "normal"),
            )

    def _update_note(self) -> None:
        label = dict(C.THEME_COLORS).get(int(self.theme.themecolor), "Unknown")
        self.color_note.configure(
            text=f"Selected: {label}. Saved in theme.xml as themecolor=\"{int(self.theme.themecolor)}\"."
        )

    # -- handlers ----------------------------------------------------------

    def _set_theme_color(self, value: int) -> None:
        if self._refreshing:
            return
        self.theme.themecolor = int(value)
        self._update_swatches(value)
        self._update_note()
        self._schedule_preview()
        self.app.mark_dirty()

    def _set_color(self, field: str, value: str) -> None:
        if self._refreshing:
            return
        text = value.strip().upper()
        if not models.ARGB_RE.match(text):
            self.app.set_status("Colour must be #AARRGGBB (8 hex digits).", "warning")
            return
        if getattr(self.theme, field) == text:
            return
        setattr(self.theme, field, text)
        self._schedule_preview()
        self.app.mark_dirty()

    def _reset_defaults(self) -> None:
        for field in (
            "font_color", "font_shadow_color", "focus_color",
            "home_dimmer", "function_dimmer", "title_dimmer",
        ):
            setattr(self.theme, field, C.THEME_XML_DEFAULTS[DEFAULT_KEYS[field]])
        self.theme.themecolor = 0
        self.refresh()
        self.app.mark_dirty()
        self.app.set_status("Appearance reset to the defaults", "success")

    # -- preview -----------------------------------------------------------

    def _schedule_preview(self) -> None:
        if self._preview_job:
            try:
                self.after_cancel(self._preview_job)
            except tk.TclError:
                pass
        self._preview_job = self.after(180, self._render_preview)

    def _render_preview(self) -> None:
        if self._preview_job:
            try:
                self.after_cancel(self._preview_job)
            except tk.TclError:
                pass
            self._preview_job = None
        try:
            image = render_ps4_preview(self.theme, self.project, PREVIEW_SIZE)
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.preview_caption.configure(
                text=f"Preview unavailable: {exc}", text_color=Colors.DANGER
            )
            return
        self._preview_image = ctk.CTkImage(light_image=image, size=PREVIEW_SIZE)
        self.preview.configure(image=self._preview_image, text="")
        mode = "dynamic video" if self.theme.is_dynamic else "static artwork"
        count = len(self.theme.function_icons) + len(self.theme.content_icons)
        custom = f"{count} custom icon{'s' if count != 1 else ''}" if count else "default icons"
        self.preview_caption.configure(
            text=f"{mode.capitalize()}  ·  {custom}  ·  theme colour {int(self.theme.themecolor)}",
            text_color=Colors.TEXT_FAINT,
        )
