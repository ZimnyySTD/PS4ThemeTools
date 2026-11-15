"""Install Guide tab: how the built theme gets onto a PS4."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from .. import constants as C
from .. import tools
from .widgets import (
    Card,
    Colors,
    ScrollPage,
    add_bottom_spacer,
    font,
)


class GuidePage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self._build_intro()
        self._build_normal()
        self._build_permanent()
        self._build_folder()
        self._build_troubleshooting()
        add_bottom_spacer(self)

    # -- helpers -----------------------------------------------------------

    def _step(self, parent, row: int, number: int, title: str, body: str) -> None:
        badge = ctk.CTkLabel(
            parent,
            text=str(number),
            width=28,
            height=28,
            corner_radius=14,
            fg_color=Colors.PRIMARY_SOFT,
            text_color=Colors.PRIMARY,
            font=font(12, "bold"),
        )
        badge.grid(row=row, column=0, sticky="nw", pady=(2, 14))

        text = ctk.CTkFrame(parent, fg_color="transparent")
        text.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=(0, 14))
        text.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            text,
            text=title,
            font=font(13, "bold"),
            text_color=Colors.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            text,
            text=body,
            font=font(12),
            text_color=Colors.TEXT_SOFT,
            anchor="w",
            justify="left",
            wraplength=780,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _note(self, parent, row: int, text: str, *, kind: str = "neutral") -> None:
        palette = {
            "neutral": (Colors.SURFACE_ALT, Colors.TEXT_SOFT),
            "warning": (Colors.WARNING_SOFT, Colors.WARNING),
            "cyan": (Colors.CYAN_SOFT, "#0E7490"),
        }
        background, foreground = palette.get(kind, palette["neutral"])
        box = ctk.CTkFrame(parent, fg_color=background, corner_radius=10)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            box,
            text=text,
            font=font(11),
            text_color=foreground,
            anchor="w",
            justify="left",
            wraplength=800,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=10)

    def _steps_body(self, card: Card) -> ctk.CTkFrame:
        body = ctk.CTkFrame(card.body, fg_color="transparent")
        body.grid(row=0, column=0, sticky="ew")
        body.grid_columnconfigure(1, weight=1)
        return body

    # -- cards -------------------------------------------------------------

    def _build_intro(self) -> None:
        card = Card(
            self,
            "From a build to your home screen",
            "The app produces a fake .pkg plus a complete theme folder. Installing it "
            "takes a minute; everything below happens on the console, not in this app.",
        )
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="flow")

        flow = [
            ("1", "Describe the theme", "Theme tab: name, artwork, video."),
            ("2", "Add details", "Icons, colours and dimmers are optional."),
            ("3", "Build", "One click; the log shows every step."),
            ("4", "Install", "Copy the .pkg and apply the theme."),
        ]
        for column, (number, title, text) in enumerate(flow):
            tile = ctk.CTkFrame(body, fg_color=Colors.SURFACE_ALT, corner_radius=12)
            tile.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 0))
            tile.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                tile, text=number, width=26, height=26, corner_radius=13,
                fg_color=Colors.PRIMARY, text_color=Colors.WHITE,
                font=font(11, "bold"),
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
            ctk.CTkLabel(
                tile, text=title, font=font(12, "bold"), text_color=Colors.TEXT, anchor="w",
            ).grid(row=1, column=0, sticky="w", padx=12)
            ctk.CTkLabel(
                tile, text=text, font=font(10), text_color=Colors.TEXT_FAINT,
                anchor="w", justify="left", wraplength=160,
            ).grid(row=2, column=0, sticky="w", padx=12, pady=(2, 12))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=1, column=0, columnspan=4, sticky="w", pady=(14, 0))
        ctk.CTkButton(
            actions, text="Go to Build", width=124, height=34, corner_radius=8,
            fg_color=Colors.PRIMARY, hover_color=Colors.PRIMARY_HOVER,
            text_color=Colors.WHITE, font=font(12, "bold"),
            command=lambda: self.app.show_page("build"),
        ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(
            actions, text="Open output folder", width=150, height=34, corner_radius=8,
            fg_color=Colors.PRIMARY_SOFT, hover_color="#D9E8FF",
            text_color=Colors.PRIMARY, font=font(12, "bold"),
            command=self._open_output,
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            actions, text="Open project folder", width=150, height=34, corner_radius=8,
            fg_color="transparent", hover_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT_SOFT, border_width=1, border_color=Colors.BORDER,
            font=font(12), command=self.app.open_project_folder,
        ).grid(row=0, column=2)

    def _build_normal(self) -> None:
        card = Card(
            self,
            "Normal method — install on the console",
            "This is the standard way. It needs a PS4 that is allowed to install "
            "unsigned packages (for example a console running GoldHEN). The app "
            "never talks to your console and does not modify it.",
        )
        card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        body = self._steps_body(card)

        self._step(
            body, 0, 1, "Build the theme",
            "Open the Build tab and press Build theme. When it finishes you get a "
            "package named <theme>_static.pkg or <theme>_dynamic.pkg in the output folder. "
            "If PkgTool is missing, the app offers to download it for you.",
        )
        self._step(
            body, 1, 2, "Copy it to a USB drive",
            "Use a USB stick formatted as exFAT or FAT32 and copy the .pkg to the drive's "
            "root. The PlayStation can read both formats; exFAT is the safer choice for "
            "packages larger than 4 GB, which themes never are.",
        )
        self._step(
            body, 2, 3, "Install the package",
            "Plug the drive into the PS4 and open the package installer provided by your "
            "setup: GoldHEN > Package Installer, or Settings > Debug Settings > Game > "
            "Package Installer. Pick the .pkg from the USB drive and confirm. Installation "
            "takes a few seconds.",
        )
        self._step(
            body, 3, 4, "Apply the theme",
            "Open Settings > Themes > Themes (some firmware says Theme Settings), select "
            "your theme from the list and choose Apply. The background, icons, music and "
            "colours appear immediately.",
        )
        self._note(
            body, 4,
            "Do not rename the .pkg before installing. The console reads the identity from "
            "inside the package, not from the filename.",
            kind="cyan",
        )

    def _build_permanent(self) -> None:
        card = Card(
            self,
            "Permanent method — keep it installed",
            "Installing to the console's internal storage makes the theme part of the "
            "system's theme list. It survives a reboot and keeps working after the USB "
            "drive is removed.",
        )
        card.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        body = self._steps_body(card)

        self._step(
            body, 0, 1, "Choose internal storage",
            "In your package installer, select the internal storage / console storage "
            "option rather than \"install to USB\". If your installer only offers one "
            "destination, it already installs permanently.",
        )
        self._step(
            body, 1, 2, "Apply it once",
            "After installing, open Settings > Themes > Themes and apply the theme. The "
            "console remembers the selection, so it is restored on the next boot.",
        )
        self._step(
            body, 2, 3, "Keep rebuilds distinct",
            "When you rebuild an installed theme, press Generate next to the Content ID on "
            "the Theme tab first. A new Content ID makes the console treat the build as a "
            "new package instead of keeping the cached old one.",
        )
        self._step(
            body, 3, 4, "Keep a backup",
            "A system software update, a database rebuild or storage initialisation can "
            "remove installed themes. Keep the project folder (or the .pkg) so you can "
            "install it again in seconds.",
        )
        self._note(
            body, 4,
            "Permanent does not mean immortal: the theme lives in the console's user "
            "storage. It is removed by the same events that remove other installed content.",
            kind="warning",
        )

    def _build_folder(self) -> None:
        card = Card(
            self,
            "What is inside the build",
            "A build always leaves the unpacked content folder on disk. It is useful for "
            "inspecting the result or for advanced install methods documented by your "
            "console setup.",
        )
        card.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        rows = [
            ("theme.xml", "Label, theme colour, text colours and the three dimmers."),
            ("sce_sys/param.sfo", "Title, Title ID, Content ID and provider."),
            ("sce_sys/icon0.png", "512x512 theme icon."),
            ("sce_sys/pic1.png", "1920x1080 artwork shown while the theme loads."),
            ("texture/preview.png", "Thumbnail shown on the theme selection screen."),
            ("texture/background/", "Static home screen and top-menu artwork (static only)."),
            ("scene/background.raf", "The DXT1 animation and its scene description (dynamic only)."),
            ("sound/bgm_home.at9", "Background music, when one was chosen."),
            ("texture/function_icon/", "Custom system icons and their glow versions."),
            ("texture/content_icon/", "Custom content icons."),
        ]
        for row, (name, description) in enumerate(rows):
            name_label = ctk.CTkLabel(
                body, text=name, font=(("Consolas"), 11), text_color=Colors.PRIMARY,
                anchor="w", width=250,
            )
            name_label.grid(row=row, column=0, sticky="w", pady=2)
            ctk.CTkLabel(
                body, text=description, font=font(11), text_color=Colors.TEXT_SOFT,
                anchor="w", justify="left", wraplength=560,
            ).grid(row=row, column=1, sticky="w", pady=2)

        self._note(
            body, len(rows),
            "Advanced route: some setups copy this folder with FTP instead of using a "
            ".pkg. Only do that when your own console guide documents the target path; "
            "the layout is exactly what the console expects.",
        )

    def _build_troubleshooting(self) -> None:
        card = Card(
            self,
            "Troubleshooting",
            "The most common problems and what actually fixes them.",
        )
        card.grid(row=4, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        items = [
            (
                "The theme does not appear in Settings > Themes",
                "Make sure the package installed without an error and that the theme list "
                "was refreshed by leaving and reopening the settings screen. If you rebuilt "
                "over an existing install, change the Content ID and install again.",
            ),
            (
                "CE-38196-7 when applying a dynamic theme",
                "The console rejected the animation for being too large. Lower the "
                "resolution or the frame count on the Theme tab and rebuild. The 6 MiB "
                "limit is enforced by the app, but staying a little below it is safer.",
            ),
            (
                "The music is silent",
                "Music is only included when at9tool was installed during the build. Open "
                "the Tools tab, install at9tool, then build again. Clips longer than five "
                "minutes are trimmed by the encoder.",
            ),
            (
                "Artwork looks stretched or soft",
                "Use an image at least 1920x1080 (or a 1280x720 video for dynamic themes). "
                "The app crops to fill the screen and never stretches, so extra resolution "
                "is kept, not squeezed.",
            ),
            (
                "The old version keeps loading after a rebuild",
                "The console caches packages by Content ID. Use Generate on the Theme tab "
                "to get a fresh identity, rebuild, then install the new package.",
            ),
            (
                "A build stops while packing",
                "Open the build log. PkgTool errors are shown verbatim; the usual cause is "
                "a locked output file or a missing tool. The generated content folder is "
                "still usable and is kept under build/ in the project.",
            ),
        ]
        for row, (title, text) in enumerate(items):
            item = ctk.CTkFrame(body, fg_color="transparent")
            item.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            item.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                item, text=title, font=font(12, "bold"), text_color=Colors.TEXT, anchor="w",
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                item, text=text, font=font(11), text_color=Colors.TEXT_SOFT,
                anchor="w", justify="left", wraplength=820,
            ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        ctk.CTkButton(
            body,
            text="Open the Tools tab",
            width=150,
            height=32,
            corner_radius=8,
            fg_color=Colors.PRIMARY_SOFT,
            hover_color="#D9E8FF",
            text_color=Colors.PRIMARY,
            font=font(11, "bold"),
            command=lambda: self.app.show_page("tools"),
        ).grid(row=len(items), column=0, sticky="w", pady=(4, 0))

    # -- actions -----------------------------------------------------------

    def _open_output(self) -> None:
        settings = self.app.settings
        folder = Path(settings.output_dir) if settings.output_dir else settings.default_output_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            tools.open_folder(folder)
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not open the folder:\n{exc}")
