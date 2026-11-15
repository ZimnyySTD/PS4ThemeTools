"""Main window, navigation and shared application state."""

from __future__ import annotations

import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from .. import constants as C
from .. import tools
from ..models import Project, ProjectError
from ..settings import Settings
from .widgets import Colors, elide, font


@dataclass
class AppState:
    settings: Settings
    project: Project


NAV_ITEMS = [
    ("theme", "▦", "Theme"),
    ("icons", "◈", "App Icons"),
    ("appearance", "◐", "Appearance"),
    ("build", "⬢", "Build"),
    ("guide", "▷", "Install Guide"),
    ("tools", "⚙", "Tools"),
]

PAGE_META = {
    "theme": ("Theme", "Name, artwork and the video behind a dynamic background"),
    "icons": ("App Icons", "Replace the system and content icons with your own artwork"),
    "appearance": ("Appearance", "Theme colour, text colours and the dimmer overlays"),
    "build": ("Build", "Package the theme and put it on your console"),
    "guide": ("Install Guide", "Install and apply the theme on a PS4"),
    "tools": ("Tools", "Download and manage the external dependencies"),
}


def _unique_folder(parent: Path, name: str) -> Path:
    candidate = parent / name
    counter = 2
    while candidate.exists() and (not candidate.is_dir() or any(candidate.iterdir())):
        candidate = parent / f"{name} {counter}"
        counter += 1
    return candidate


def load_initial_state() -> AppState:
    settings = Settings.load()
    candidates = [settings.last_project, *settings.recent_projects]
    for value in candidates:
        if not value:
            continue
        folder = Path(value)
        if (folder / C.PROJECT_FILE_NAME).is_file():
            try:
                project = Project.load(folder)
                settings.remember_project(folder)
                return AppState(settings=settings, project=project)
            except ProjectError:
                continue

    try:
        parent = C.default_projects_dir()
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        parent = C.config_dir() / "projects"
        parent.mkdir(parents=True, exist_ok=True)

    folder = _unique_folder(parent, "My Theme")
    try:
        project = Project.create(folder)
    except OSError as exc:
        # Last resort: a folder inside the app data area is always writable.
        fallback = C.config_dir() / "projects" / "My Theme"
        fallback.mkdir(parents=True, exist_ok=True)
        project = Project.create(fallback)
        _ = exc
    settings.remember_project(project.root)
    settings.save()
    return AppState(settings=settings, project=project)


class NavButton(ctk.CTkFrame):
    def __init__(self, master, glyph: str, label: str, command):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        self.indicator = ctk.CTkFrame(self, fg_color="transparent", width=3, height=22, corner_radius=2)
        self.indicator.grid(row=0, column=0, padx=(0, 8))
        self.button = ctk.CTkButton(
            self,
            text=f"{glyph}   {label}",
            anchor="w",
            height=42,
            corner_radius=10,
            fg_color="transparent",
            hover_color=Colors.NAVY_SOFT,
            text_color="#A9C1DA",
            font=font(13),
            command=command,
        )
        self.button.grid(row=0, column=1, sticky="ew")

    def set_active(self, active: bool) -> None:
        if active:
            self.indicator.configure(fg_color=Colors.CYAN_BRIGHT)
            self.button.configure(
                fg_color=Colors.NAVY_SOFT,
                text_color=Colors.WHITE,
                font=font(13, "bold"),
            )
        else:
            self.indicator.configure(fg_color="transparent")
            self.button.configure(
                fg_color="transparent",
                text_color="#A9C1DA",
                font=font(13),
            )


class ThemeToolsApp(ctk.CTk):
    def __init__(self, state: AppState, start_page: str = "theme"):
        ctk.set_appearance_mode("light")
        super().__init__(fg_color=Colors.BACKGROUND)
        self.data = state
        self._dirty = False
        self._save_job = None
        self.current_page = ""
        self._nav: dict[str, NavButton] = {}
        self._pages: dict[str, object] = {}
        self._logo_image = None

        self.title(f"{C.APP_NAME} {C.APP_VERSION}")
        self.minsize(1120, 720)
        width, height = 1320, 860
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 20)
        self.geometry(f"{width}x{height}+{x}+{y}")

        icon = C.resource_path("app_icon.ico")
        if icon.is_file():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass

        self._build_layout()
        self._build_pages()
        self.refresh_all()
        self.show_page(start_page if start_page in self._pages else "theme")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-s>", lambda _event: self.save_now())
        self.after(250, self.refresh_tool_status)

    # -- layout ------------------------------------------------------------

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=238, fg_color=Colors.NAVY, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 10))
        brand.grid_columnconfigure(1, weight=1)

        logo_path = C.resource_path("logo.png")
        if logo_path.is_file():
            try:
                logo = Image.open(logo_path).convert("RGBA")
                self._logo_image = ctk.CTkImage(light_image=logo, size=(42, 42))
                ctk.CTkLabel(brand, image=self._logo_image, text="").grid(
                    row=0, column=0, rowspan=2, padx=(0, 12)
                )
            except OSError:
                pass

        ctk.CTkLabel(
            brand, text="PS4 Theme", font=font(17, "bold"),
            text_color=Colors.WHITE, anchor="w",
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            brand, text="TOOLS", font=font(10, "bold"),
            text_color=Colors.CYAN_BRIGHT, anchor="w",
        ).grid(row=1, column=1, sticky="w")

        ctk.CTkLabel(
            sidebar,
            text="CREATE  ·  PACKAGE  ·  INSTALL",
            font=font(9, "bold"),
            text_color="#5F7E9E",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))

        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.grid(row=2, column=0, sticky="new", padx=12)
        nav.grid_columnconfigure(0, weight=1)
        for index, (key, glyph, label) in enumerate(NAV_ITEMS):
            item = NavButton(nav, glyph, label, lambda k=key: self.show_page(k))
            item.grid(row=index, column=0, sticky="ew", pady=2)
            self._nav[key] = item

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 20))
        footer.grid_columnconfigure(0, weight=1)

        self.tool_dot = ctk.CTkLabel(
            footer, text="●", font=font(10), text_color=Colors.WARNING, anchor="w"
        )
        self.tool_dot.grid(row=0, column=0, sticky="w")
        self.tool_status = ctk.CTkLabel(
            footer, text="Checking tools...", font=font(10),
            text_color="#8FAAC6", anchor="w",
        )
        self.tool_status.grid(row=0, column=0, sticky="w", padx=(14, 0))

        ctk.CTkButton(
            footer,
            text="Open project folder",
            height=28,
            corner_radius=8,
            fg_color="transparent",
            hover_color=Colors.NAVY_SOFT,
            text_color="#8FAAC6",
            font=font(10),
            anchor="w",
            command=self.open_project_folder,
        ).grid(row=1, column=0, sticky="ew", pady=(10, 6))
        ctk.CTkLabel(
            footer, text=f"Version {C.APP_VERSION}", font=font(9),
            text_color="#5F7E9E", anchor="w",
        ).grid(row=2, column=0, sticky="w")

        main = ctk.CTkFrame(self, fg_color=Colors.BACKGROUND, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent", height=96)
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(20, 8))
        header.grid_columnconfigure(0, weight=1)
        header.grid_rowconfigure(1, weight=0)

        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        self.page_title = ctk.CTkLabel(
            titles, text="Theme", font=font(26, "bold"),
            text_color=Colors.TEXT, anchor="w",
        )
        self.page_title.grid(row=0, column=0, sticky="w")
        self.page_subtitle = ctk.CTkLabel(
            titles, text="", font=font(12),
            text_color=Colors.TEXT_SOFT, anchor="w",
        )
        self.page_subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e")
        project_box = ctk.CTkFrame(right, fg_color="transparent")
        project_box.grid(row=0, column=0, padx=(0, 14))
        self.project_name = ctk.CTkLabel(
            project_box, text="", font=font(13, "bold"),
            text_color=Colors.TEXT, anchor="e", justify="right",
        )
        self.project_name.grid(row=0, column=0, sticky="e")
        self.project_path = ctk.CTkLabel(
            project_box, text="", font=font(10),
            text_color=Colors.TEXT_FAINT, anchor="e", justify="right",
        )
        self.project_path.grid(row=1, column=0, sticky="e")

        ctk.CTkButton(
            right,
            text="Save project",
            width=118,
            height=38,
            corner_radius=10,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_HOVER,
            text_color=Colors.WHITE,
            font=font(12, "bold"),
            command=self.save_now,
        ).grid(row=0, column=1)

        self.status_label = ctk.CTkLabel(
            header,
            text="All changes saved",
            font=font(10),
            text_color=Colors.TEXT_FAINT,
            anchor="e",
        )
        self.status_label.grid(row=1, column=0, columnspan=3, sticky="e", pady=(4, 0))

        self.page_host = ctk.CTkFrame(main, fg_color="transparent")
        self.page_host.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)

    def _build_pages(self) -> None:
        from .appearance_page import AppearancePage
        from .build_page import BuildPage
        from .guide_page import GuidePage
        from .icons_page import IconsPage
        from .theme_page import ThemePage
        from .tools_page import ToolsPage

        classes = {
            "theme": ThemePage,
            "icons": IconsPage,
            "appearance": AppearancePage,
            "build": BuildPage,
            "guide": GuidePage,
            "tools": ToolsPage,
        }
        for key, cls in classes.items():
            page = cls(self.page_host, self)
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()
            self._pages[key] = page

    # -- navigation --------------------------------------------------------

    def show_page(self, key: str) -> None:
        if key not in self._pages:
            return
        if self.current_page:
            current = self._pages.get(self.current_page)
            if current:
                current.grid_remove()
        page = self._pages[key]
        page.grid()
        self.current_page = key
        for nav_key, item in self._nav.items():
            item.set_active(nav_key == key)
        title, subtitle = PAGE_META[key]
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)
        try:
            page.on_show()
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.set_status(f"Could not refresh this tab: {exc}", "danger")

    # -- project -----------------------------------------------------------

    @property
    def project(self) -> Project:
        return self.data.project

    @property
    def settings(self) -> Settings:
        return self.data.settings

    def refresh_all(self) -> None:
        self.refresh_header()
        for page in self._pages.values():
            try:
                page.refresh()
            except Exception:
                pass
        self.refresh_tool_status()

    def refresh_header(self) -> None:
        theme = self.project.theme
        self.project_name.configure(text=theme.name.strip() or "Untitled theme")
        self.project_path.configure(text=elide(str(self.project.root), 58))
        if not self._dirty:
            self.status_label.configure(text="All changes saved", text_color=Colors.TEXT_FAINT)

    def mark_dirty(self) -> None:
        self._dirty = True
        self.status_label.configure(text="Saving...", text_color=Colors.TEXT_FAINT)
        if self._save_job:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(650, self._auto_save)

    def _auto_save(self) -> None:
        self._save_job = None
        self.save_now()

    def save_now(self) -> None:
        if self._save_job:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
            self._save_job = None
        try:
            self.project.save()
            self.settings.remember_project(self.project.root)
            self.settings.save()
            self._dirty = False
            self.status_label.configure(text="All changes saved", text_color=Colors.SUCCESS)
            self.refresh_header()
            self.refresh_tool_status()
        except OSError as exc:
            self._dirty = True
            self.status_label.configure(text=f"Could not save: {exc}", text_color=Colors.DANGER)

    def set_status(self, message: str, kind: str = "info") -> None:
        colours = {
            "info": Colors.TEXT_FAINT,
            "success": Colors.SUCCESS,
            "warning": Colors.WARNING,
            "danger": Colors.DANGER,
        }
        self.status_label.configure(text=message, text_color=colours.get(kind, Colors.TEXT_FAINT))

    def refresh_tool_status(self) -> None:
        try:
            paths = tools.resolve(self.settings)
        except Exception:
            return
        missing = [name for name, path in (
            ("FFmpeg", paths.ffmpeg),
            ("PkgTool", paths.pkgtool),
            ("at9tool", paths.at9tool),
        ) if path is None]
        if missing:
            self.tool_dot.configure(text_color=Colors.WARNING)
            self.tool_status.configure(text="Missing: " + ", ".join(missing))
        else:
            self.tool_dot.configure(text_color=Colors.SUCCESS)
            self.tool_status.configure(text="All tools ready")

    # -- project operations ------------------------------------------------

    def open_project_folder(self) -> None:
        folder = self.project.root
        if not folder.is_dir():
            self.set_status("The project folder does not exist.", "danger")
            return
        try:
            tools.open_folder(folder)
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not open the folder:\n{exc}")

    def open_project_dialog(self) -> None:
        initial = Path(self.settings.last_project).parent if self.settings.last_project else C.default_projects_dir()
        folder = filedialog.askdirectory(
            title="Open a PS4 Theme Tools project",
            initialdir=str(initial if initial.is_dir() else C.default_projects_dir()),
        )
        if folder:
            self.open_project(Path(folder))

    def open_project(self, folder: Path) -> None:
        try:
            project = Project.load(folder)
        except ProjectError as exc:
            messagebox.showerror(C.APP_NAME, str(exc))
            return
        self.data.project = project
        self.settings.remember_project(project.root)
        self.settings.save()
        self.refresh_all()
        self.show_page("theme")
        self.set_status("Project opened", "success")

    def new_project_dialog(self) -> None:
        parent = filedialog.askdirectory(
            title="Choose where to create the project folder",
            initialdir=str(Path(self.settings.last_project).parent if self.settings.last_project else C.default_projects_dir()),
        )
        if not parent:
            return
        dialog = ctk.CTkInputDialog(text="Name for the new theme folder:", title="New project")
        name = (dialog.get_input() or "").strip()
        if not name:
            return
        safe = re.sub(r'[<>:"/\\|?*]+', "-", name).strip(" .-") or "New Theme"
        folder = _unique_folder(Path(parent), safe)
        try:
            project = Project.create(folder)
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not create the project:\n{exc}")
            return
        self.data.project = project
        self.settings.remember_project(project.root)
        self.settings.save()
        self.refresh_all()
        self.show_page("theme")
        self.set_status("New project created", "success")

    def duplicate_content_id(self) -> None:
        messagebox.showinfo(
            C.APP_NAME,
            "Changing the Content ID gives the console a fresh package identity. "
            "Use it if a rebuilt theme is not recognised or an old version stays cached.\n\n"
            "The Generate button on the Theme tab creates one from the name and Title ID.",
        )

    # -- lifecycle ---------------------------------------------------------

    def _on_close(self) -> None:
        build_page = self._pages.get("build")
        if build_page is not None and getattr(build_page, "running", False):
            if not messagebox.askyesno(
                C.APP_NAME,
                "A build is still running. Quit anyway? The unfinished package will be discarded.",
            ):
                return
        try:
            self.project.save()
        except OSError:
            pass
        self.destroy()
