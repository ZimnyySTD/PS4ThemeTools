"""Tools tab: dependency detection, downloads and manual overrides."""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import constants as C
from .. import tools
from .widgets import (
    Card,
    Colors,
    ScrollPage,
    add_bottom_spacer,
    elide,
    font,
    MONO_FONT,
)

TOOL_HINTS = {
    "ffmpeg": "Required for dynamic themes and for converting music to ATRAC9.",
    "pkgtool": "Required to turn the generated theme folder into a .pkg.",
    "at9tool": "Only needed when you add background music that is not already .at9.",
}


class ToolCard(ctk.CTkFrame):
    def __init__(self, master, page: "ToolsPage", key: str):
        super().__init__(
            master,
            fg_color=Colors.SURFACE,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER,
        )
        self.page = page
        self.key = key
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 0))
        header.grid_columnconfigure(0, weight=1)

        self.title = ctk.CTkLabel(
            header, text="", font=font(15, "bold"), text_color=Colors.TEXT, anchor="w"
        )
        self.title.grid(row=0, column=0, sticky="w")
        self.chip = ctk.CTkLabel(
            header,
            text="Checking...",
            font=font(10, "bold"),
            text_color=Colors.TEXT_SOFT,
            fg_color=Colors.SURFACE_ALT,
            corner_radius=7,
            height=22,
        )
        self.chip.grid(row=0, column=1, sticky="e")

        self.description = ctk.CTkLabel(
            self, text="", font=font(12), text_color=Colors.TEXT_SOFT,
            anchor="w", justify="left", wraplength=760,
        )
        self.description.grid(row=1, column=0, sticky="w", padx=20, pady=(3, 8))

        info = ctk.CTkFrame(self, fg_color=Colors.SURFACE_ALT, corner_radius=10)
        info.grid(row=2, column=0, sticky="ew", padx=20)
        info.grid_columnconfigure(0, weight=1)
        self.path_label = ctk.CTkLabel(
            info, text="Not installed", font=(MONO_FONT, 10),
            text_color=Colors.TEXT_SOFT, anchor="w", justify="left", wraplength=660,
        )
        self.path_label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
        self.meta_label = ctk.CTkLabel(
            info, text="", font=font(10), text_color=Colors.TEXT_FAINT, anchor="w",
        )
        self.meta_label.grid(row=1, column=0, sticky="w", padx=12, pady=(1, 8))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=20, pady=(12, 16))
        actions.grid_columnconfigure(3, weight=1)

        self.install_button = ctk.CTkButton(
            actions, text="Install", width=104, height=32, corner_radius=8,
            fg_color=Colors.PRIMARY, hover_color=Colors.PRIMARY_HOVER,
            text_color=Colors.WHITE, font=font(11, "bold"),
            command=lambda: page.install(self.key),
        )
        self.install_button.grid(row=0, column=0, padx=(0, 8))

        self.locate_button = ctk.CTkButton(
            actions, text="Locate...", width=88, height=32, corner_radius=8,
            fg_color="transparent", hover_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT_SOFT, border_width=1, border_color=Colors.BORDER,
            font=font(11), command=lambda: page.locate(self.key),
        )
        self.locate_button.grid(row=0, column=1, padx=(0, 8))

        self.reset_button = ctk.CTkButton(
            actions, text="Use automatic", width=112, height=32, corner_radius=8,
            fg_color=Colors.PRIMARY_SOFT, hover_color="#D9E8FF",
            text_color=Colors.PRIMARY, font=font(11, "bold"),
            command=lambda: page.reset_override(self.key),
        )
        self.reset_button.grid(row=0, column=2, padx=(0, 8))

        self.remove_button = ctk.CTkButton(
            actions, text="Remove", width=82, height=32, corner_radius=8,
            fg_color="transparent", hover_color=Colors.DANGER_SOFT,
            text_color=Colors.TEXT_SOFT, border_width=1, border_color=Colors.BORDER,
            font=font(11), command=lambda: page.remove(self.key),
        )
        self.remove_button.grid(row=0, column=3, sticky="e")

    def update(self, info: tools.ToolInfo, override: str) -> None:
        self.title.configure(text=info.label)
        self.description.configure(text=TOOL_HINTS.get(self.key, info.description))
        if info.found:
            self.chip.configure(
                text="Installed", text_color=Colors.SUCCESS, fg_color=Colors.SUCCESS_SOFT
            )
            self.path_label.configure(text=str(info.path), text_color=Colors.TEXT_SOFT)
            self.meta_label.configure(
                text=f"{info.version}  ·  about {info.install_size} on disk"
                + ("  ·  optional" if info.optional else "  ·  required")
            )
        else:
            self.chip.configure(
                text="Missing", text_color=Colors.WARNING, fg_color=Colors.WARNING_SOFT
            )
            self.path_label.configure(text="Not installed", text_color=Colors.TEXT_FAINT)
            self.meta_label.configure(
                text=f"Download size about {info.install_size}"
                + ("  ·  optional" if info.optional else "  ·  required")
            )

        self.install_button.configure(text="Reinstall" if info.found else "Install")
        self.remove_button.configure(state="normal" if info.found else "disabled")
        self.reset_button.grid() if override else self.reset_button.grid_remove()

    def set_busy(self, busy: bool, active: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (
            self.install_button, self.locate_button,
            self.reset_button, self.remove_button,
        ):
            if button is self.remove_button and not button.cget("state") == "normal":
                continue
            try:
                button.configure(state=state)
            except Exception:
                pass
        if active:
            self.chip.configure(
                text="Working...", text_color=Colors.PRIMARY, fg_color=Colors.PRIMARY_SOFT
            )


class ToolsPage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._cards: dict[str, ToolCard] = {}
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue = queue.Queue()
        self._pump_job = None
        self._busy_key = ""

        self._build_intro()
        for row, key in enumerate(("ffmpeg", "pkgtool", "at9tool"), start=1):
            card = ToolCard(self, self, key)
            card.grid(row=row, column=0, sticky="ew", pady=(0, 12))
            self._cards[key] = card
        self._build_cache_card()
        self._build_progress_card()
        add_bottom_spacer(self)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # -- cards -------------------------------------------------------------

    def _build_intro(self) -> None:
        card = Card(
            self,
            "Dependencies",
            "Three small tools do the heavy lifting. The app finds them in this order: "
            "a manual location you choose, then its own tools folder, then the system PATH.",
        )
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        row.grid_columnconfigure(1, weight=1)

        self.summary_chip = ctk.CTkLabel(
            row, text="Checking...", font=font(11, "bold"),
            text_color=Colors.TEXT_SOFT, fg_color=Colors.SURFACE_ALT,
            corner_radius=8, height=26,
        )
        self.summary_chip.grid(row=0, column=0, sticky="w")

        self.summary_text = ctk.CTkLabel(
            row, text="", font=font(11), text_color=Colors.TEXT_FAINT,
            anchor="w", justify="left", wraplength=600,
        )
        self.summary_text.grid(row=0, column=1, sticky="w", padx=(12, 0))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="w", pady=(12, 0))
        ctk.CTkButton(
            actions, text="Check again", width=108, height=30, corner_radius=8,
            fg_color=Colors.PRIMARY_SOFT, hover_color="#D9E8FF",
            text_color=Colors.PRIMARY, font=font(11, "bold"),
            command=self.refresh,
        ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(
            actions, text="Open tools folder", width=134, height=30, corner_radius=8,
            fg_color="transparent", hover_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT_SOFT, border_width=1, border_color=Colors.BORDER,
            font=font(11), command=self._open_tools_folder,
        ).grid(row=0, column=1)

    def _build_cache_card(self) -> None:
        card = Card(
            self,
            "Download cache",
            "Archives are deleted after a successful install. Anything left here is "
            "safe to remove and will be downloaded again only when needed.",
        )
        card.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        self.cache_label = ctk.CTkLabel(
            row, text="", font=font(11), text_color=Colors.TEXT_SOFT,
            anchor="w", justify="left", wraplength=560,
        )
        self.cache_label.grid(row=0, column=0, sticky="w")
        self.clear_cache_button = ctk.CTkButton(
            row, text="Clear cache", width=104, height=30, corner_radius=8,
            fg_color="transparent", hover_color=Colors.DANGER_SOFT,
            text_color=Colors.TEXT_SOFT, border_width=1, border_color=Colors.BORDER,
            font=font(11), command=self._clear_cache,
        )
        self.clear_cache_button.grid(row=0, column=1, sticky="e")

    def _build_progress_card(self) -> None:
        card = Card(self, "Installer")
        card.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(
            body, height=8, corner_radius=4,
            progress_color=Colors.CYAN, fg_color=Colors.CYAN_SOFT,
        )
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(
            body, text="Idle. Downloads are verified against published checksums.",
            font=font(11), text_color=Colors.TEXT_SOFT, anchor="w",
            justify="left", wraplength=820,
        )
        self.progress_label.grid(row=1, column=0, sticky="w", pady=(7, 0))

    # -- refresh -----------------------------------------------------------

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        try:
            infos = tools.check(self.app.settings)
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.summary_chip.configure(
                text="Check failed", text_color=Colors.DANGER, fg_color=Colors.DANGER_SOFT
            )
            self.summary_text.configure(text=str(exc))
            return

        overrides = {
            "ffmpeg": self.app.settings.ffmpeg,
            "pkgtool": self.app.settings.pkgtool,
            "at9tool": self.app.settings.at9tool,
        }
        for info in infos:
            card = self._cards.get(info.key)
            if card:
                card.update(info, overrides.get(info.key, ""))
                card.set_busy(self.running, active=self._busy_key == info.key)

        required = [info for info in infos if not info.optional]
        missing_required = [info for info in required if not info.found]
        missing_optional = [info for info in infos if info.optional and not info.found]
        if not missing_required:
            self.summary_chip.configure(
                text="Ready to build", text_color=Colors.SUCCESS, fg_color=Colors.SUCCESS_SOFT
            )
            tail = (
                f" Optional: {missing_optional[0].label} is not installed; "
                "you only need it for custom music."
                if missing_optional else ""
            )
            self.summary_text.configure(
                text="FFmpeg and PkgTool are available." + tail
            )
        else:
            names = ", ".join(info.label for info in missing_required)
            self.summary_chip.configure(
                text="Missing tools", text_color=Colors.WARNING, fg_color=Colors.WARNING_SOFT
            )
            self.summary_text.configure(
                text=f"Not installed: {names}. Install them here, or let a build fetch them "
                     "automatically."
            )

        self._update_cache()
        self.app.refresh_tool_status()

    def _update_cache(self) -> None:
        folder = C.tools_dir() / "downloads"
        total = 0
        files = 0
        if folder.is_dir():
            for path in folder.rglob("*"):
                if path.is_file():
                    files += 1
                    try:
                        total += path.stat().st_size
                    except OSError:
                        pass
        if files:
            self.cache_label.configure(
                text=f"{files} file{'s' if files != 1 else ''}, {total / 1048576:.1f} MB in "
                     f"{folder}"
            )
            self.clear_cache_button.configure(state="normal")
        else:
            self.cache_label.configure(text="The cache is empty.")
            self.clear_cache_button.configure(state="disabled")

    # -- actions -----------------------------------------------------------

    def install(self, key: str) -> None:
        if self.running:
            return
        label = tools.LABELS.get(key, key)
        self._busy_key = key
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.progress_label.configure(
            text=f"Installing {label}...", text_color=Colors.TEXT_SOFT
        )
        self._set_buttons_busy(True)
        self._append_status(f"Starting {label} installation.")
        self._thread = threading.Thread(
            target=self._worker, args=(key,), name=f"ps4theme-install-{key}", daemon=True
        )
        self._thread.start()
        self._pump_job = self.after(80, self._drain)

    def _worker(self, key: str) -> None:
        def progress(message: str, fraction: float) -> None:
            self._queue.put(("progress", (message, fraction)))

        try:
            path = tools.install(key, progress)
            self._queue.put(("done", (key, path)))
        except tools.ToolError as exc:
            self._queue.put(("error", (key, str(exc))))
        except Exception as exc:  # pragma: no cover - unexpected failures only
            self._queue.put(("error", (key, f"{exc}")))

    def _drain(self) -> None:
        self._pump_job = None
        finished = False
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "progress":
                    message, fraction = payload
                    self.progress_label.configure(text=message, text_color=Colors.TEXT_SOFT)
                    if fraction < 0:
                        if str(self.progress.cget("mode")) != "indeterminate":
                            self.progress.configure(mode="indeterminate")
                            self.progress.start()
                    else:
                        if str(self.progress.cget("mode")) != "determinate":
                            self.progress.stop()
                            self.progress.configure(mode="determinate")
                        self.progress.set(max(0.0, min(1.0, fraction)))
                elif kind == "done":
                    key, path = payload
                    finished = True
                    label = tools.LABELS.get(key, key)
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.progress.set(1.0)
                    self.progress_label.configure(
                        text=f"{label} installed: {elide(str(path), 80)}",
                        text_color=Colors.SUCCESS,
                    )
                    self.app.set_status(f"{label} installed", "success")
                elif kind == "error":
                    key, message = payload
                    finished = True
                    label = tools.LABELS.get(key, key)
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.progress.set(0)
                    self.progress_label.configure(
                        text=f"{label} could not be installed: {message}",
                        text_color=Colors.DANGER,
                    )
                    self.app.set_status(f"{label} installation failed", "danger")
                    messagebox.showerror(C.APP_NAME, f"{label} could not be installed:\n\n{message}")
        except queue.Empty:
            pass

        if finished:
            self._thread = None
            self._busy_key = ""
            self._set_buttons_busy(False)
            self.refresh()
        elif self.running or not self._queue.empty():
            self._pump_job = self.after(80, self._drain)

    def _set_buttons_busy(self, busy: bool) -> None:
        for card in self._cards.values():
            card.set_busy(busy, active=self._busy_key == card.key)
        self.clear_cache_button.configure(state="disabled" if busy else "normal")

    def locate(self, key: str) -> None:
        settings = self.app.settings
        current = {
            "ffmpeg": settings.ffmpeg,
            "pkgtool": settings.pkgtool,
            "at9tool": settings.at9tool,
        }.get(key, "")
        patterns = {
            "ffmpeg": "ffmpeg.exe",
            "pkgtool": "PkgTool.exe",
            "at9tool": "ps4_at9tool.exe at9tool.exe",
        }.get(key, "*.*")
        path = filedialog.askopenfilename(
            title=f"Locate {tools.LABELS.get(key, key)}",
            initialdir=str(Path(current).parent) if current else str(C.tools_dir()),
            filetypes=[("Executable", patterns), ("All files", "*.*")],
        )
        if not path:
            return
        setattr(settings, key, path)
        settings.save()
        if key == "ffmpeg":
            # Selecting ffmpeg.exe is enough; ffprobe is looked up next to it.
            pass
        self.refresh()
        self.app.set_status(f"{tools.LABELS.get(key, key)} location saved", "success")

    def reset_override(self, key: str) -> None:
        setattr(self.app.settings, key, "")
        self.app.settings.save()
        self.refresh()
        self.app.set_status(f"{tools.LABELS.get(key, key)} uses automatic detection again", "info")

    def remove(self, key: str) -> None:
        if self.running:
            return
        label = tools.LABELS.get(key, key)
        if not messagebox.askyesno(
            C.APP_NAME,
            f"Remove the installed copy of {label}?\n\n"
            "The app can download it again at any time. A manual location is not changed.",
        ):
            return
        tools.remove(key)
        self.refresh()
        self.app.set_status(f"{label} removed", "warning")

    def _clear_cache(self) -> None:
        if self.running:
            return
        tools.clear_download_cache()
        self._update_cache()
        self.app.set_status("Download cache cleared", "info")

    def _open_tools_folder(self) -> None:
        try:
            tools.open_folder(C.tools_dir())
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not open the folder:\n{exc}")

    def _append_status(self, message: str) -> None:
        self.progress_label.configure(text=message, text_color=Colors.TEXT_SOFT)

    # -- lifecycle ---------------------------------------------------------

    def destroy(self) -> None:
        if self._pump_job:
            try:
                self.after_cancel(self._pump_job)
            except Exception:
                pass
        super().destroy()
