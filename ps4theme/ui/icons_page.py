"""App Icons tab: replaceable system and content icons."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from .. import constants as C
from .. import images
from .widgets import Colors, Card, ScrollPage, add_bottom_spacer, font


class IconTile(ctk.CTkFrame):
    def __init__(self, master, page: "IconsPage", kind: str, name: str):
        super().__init__(
            master,
            width=158,
            height=196,
            fg_color=Colors.SURFACE_ALT,
            corner_radius=12,
            border_width=1,
            border_color=Colors.BORDER,
        )
        self.grid_propagate(False)
        self.page = page
        self.kind = kind
        self.name = name
        self._image: ctk.CTkImage | None = None

        self.preview = ctk.CTkButton(
            self,
            text="",
            width=86,
            height=86,
            fg_color="transparent",
            hover_color=Colors.BORDER,
            corner_radius=10,
            command=self._choose,
        )
        self.preview.grid(row=0, column=0, columnspan=2, pady=(12, 6))

        self.label = ctk.CTkLabel(
            self, text=C.ICON_LABELS.get(name, name),
            font=font(11, "bold"), text_color=Colors.TEXT, anchor="center",
        )
        self.label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6)

        self.status = ctk.CTkLabel(
            self, text="Default", font=font(9, "bold"),
            text_color=Colors.TEXT_FAINT, fg_color=Colors.SURFACE,
            corner_radius=6, height=18,
        )
        self.status.grid(row=2, column=0, columnspan=2, pady=(3, 6))

        self.choose_button = ctk.CTkButton(
            self,
            text="Choose",
            width=92,
            height=27,
            corner_radius=7,
            fg_color=Colors.PRIMARY_SOFT,
            hover_color="#D9E8FF",
            text_color=Colors.PRIMARY,
            font=font(10, "bold"),
            command=self._choose,
        )
        self.choose_button.grid(row=3, column=0, padx=(10, 4), pady=(0, 10), sticky="w")

        self.clear_button = ctk.CTkButton(
            self,
            text="×",
            width=30,
            height=27,
            corner_radius=7,
            fg_color="transparent",
            hover_color=Colors.DANGER_SOFT,
            text_color=Colors.TEXT_SOFT,
            border_width=1,
            border_color=Colors.BORDER,
            font=font(14, "bold"),
            command=self._clear,
        )
        self.clear_button.grid(row=3, column=1, padx=(0, 10), pady=(0, 10), sticky="w")

        self.set("")

    def _choose(self) -> None:
        self.page.choose_icon(self.kind, self.name)

    def _clear(self) -> None:
        self.page.clear_icon(self.kind, self.name)

    def set(self, value: str) -> None:
        path = self.page.project.path_for(value) if value else None
        if path and path.is_file():
            try:
                image = images.fit_contain(images.open_image(path), (86, 86))
                self.status.configure(text="Custom", text_color=Colors.CYAN, fg_color=Colors.CYAN_SOFT)
            except images.ImageError:
                image = self.page.placeholder(self.name)
                self.status.configure(text="Unreadable", text_color=Colors.DANGER, fg_color=Colors.DANGER_SOFT)
        else:
            image = self.page.placeholder(self.name)
            if value:
                self.status.configure(text="Missing", text_color=Colors.DANGER, fg_color=Colors.DANGER_SOFT)
            else:
                self.status.configure(text="Default", text_color=Colors.TEXT_FAINT, fg_color=Colors.SURFACE)
        self._image = ctk.CTkImage(light_image=image, size=(86, 86))
        self.preview.configure(image=self._image)


class IconsPage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.tiles: dict[tuple[str, str], IconTile] = {}

        intro = Card(
            self,
            "Make the theme yours",
            "Pick a PNG, JPG or WebP for any slot. Images are scaled and centre-cropped "
            "to the size the PS4 expects. Anything you leave empty keeps the console's "
            "own icon, so you can start with just the icons you care about.",
        )
        intro.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        note = ctk.CTkLabel(
            intro.body,
            text="Function icons are 128x128; a 152x152 glow version is generated "
                 "automatically. Content icons are 512x512.",
            font=font(11),
            text_color=Colors.TEXT_SOFT,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        note.grid(row=0, column=0, sticky="w")

        self._build_group(
            row=1,
            kind="function",
            title="Function icons",
            subtitle="The row of system icons at the top of the home screen.",
            names=C.FUNCTION_ICONS,
        )
        self._build_group(
            row=2,
            kind="content",
            title="Content icons",
            subtitle="Browser, library, capture gallery, disc and the other content areas.",
            names=C.CONTENT_ICONS,
        )
        add_bottom_spacer(self)

    @property
    def theme(self):
        return self.app.project.theme

    @property
    def project(self):
        return self.app.project

    def _build_group(self, *, row: int, kind: str, title: str, subtitle: str, names: list[str]) -> None:
        card = Card(self, title, subtitle)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        body = card.body

        header = ctk.CTkFrame(body, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Leave a slot empty to keep the default.",
            font=font(11),
            text_color=Colors.TEXT_FAINT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="Clear all",
            width=78,
            height=28,
            corner_radius=7,
            fg_color="transparent",
            hover_color=Colors.DANGER_SOFT,
            text_color=Colors.TEXT_SOFT,
            border_width=1,
            border_color=Colors.BORDER,
            font=font(10),
            command=lambda k=kind: self.clear_group(k),
        ).grid(row=0, column=1, sticky="e")

        for column in range(5):
            body.grid_columnconfigure(column, weight=1, uniform=f"{kind}-cols")

        for index, name in enumerate(names):
            tile = IconTile(body, self, kind, name)
            tile.grid(
                row=1 + index // 5,
                column=index % 5,
                padx=5,
                pady=5,
                sticky="n",
            )
            self.tiles[(kind, name)] = tile

    def placeholder(self, name: str) -> Image.Image:
        return images.placeholder_icon(name, 120)

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        for (kind, name), tile in self.tiles.items():
            tile.set(self.theme.icon_for(kind, name))

    def choose_icon(self, kind: str, name: str) -> None:
        path = filedialog.askopenfilename(
            title=f"Choose an icon for {C.ICON_LABELS.get(name, name)}",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")],
        )
        if not path:
            return
        source = Path(path)
        try:
            images.open_image(source)
        except images.ImageError as exc:
            messagebox.showerror(C.APP_NAME, str(exc))
            return
        try:
            relative = self.project.import_asset(source, "icons")
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not copy the icon:\n{exc}")
            return

        old = self.theme.icon_for(kind, name)
        self.theme.set_icon(kind, name, relative)
        self._release(old)
        self.tiles[(kind, name)].set(relative)
        self.app.mark_dirty()
        self.app.set_status(f"{C.ICON_LABELS.get(name, name)} updated", "success")

    def clear_icon(self, kind: str, name: str) -> None:
        old = self.theme.icon_for(kind, name)
        if not old:
            return
        self.theme.set_icon(kind, name, "")
        self.tiles[(kind, name)].set("")
        self._release(old)
        self.app.mark_dirty()

    def clear_group(self, kind: str) -> None:
        names = C.FUNCTION_ICONS if kind == "function" else C.CONTENT_ICONS
        existing = [name for name in names if self.theme.icon_for(kind, name)]
        if not existing:
            return
        if not messagebox.askyesno(
            C.APP_NAME,
            f"Clear all {len(existing)} custom icons in this group?",
        ):
            return
        for name in existing:
            old = self.theme.icon_for(kind, name)
            self.theme.set_icon(kind, name, "")
            self.tiles[(kind, name)].set("")
            self._release(old)
        self.app.mark_dirty()

    def _release(self, value: str) -> None:
        if not value:
            return
        theme = self.theme
        referenced = {
            theme.background, theme.functionscreen, theme.icon, theme.video, theme.music,
            *theme.function_icons.values(), *theme.content_icons.values(),
        }
        if value not in referenced:
            try:
                self.project.clear_asset(value)
            except OSError:
                pass
