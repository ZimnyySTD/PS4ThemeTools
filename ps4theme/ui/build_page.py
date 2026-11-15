"""Build tab: options, validation, a live log and one-click packaging."""

from __future__ import annotations

import copy
import os
import queue
import subprocess
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import builder
from .. import constants as C
from .. import models, tools
from .widgets import (
    Card,
    Colors,
    ScrollPage,
    StatTile,
    add_bottom_spacer,
    elide,
    font,
    MONO_FONT,
)

CANCELLED = "cancelled"
STARTING = "starting"


class BuildPage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._thread: threading.Thread | None = None
        self._cancel: threading.Event | None = None
        self._queue: queue.Queue = queue.Queue()
        self._pump_job = None
        self._result: builder.BuildResult | None = None
        self._last_message = ""

        self._build_status_card()
        self._build_output_card()
        self._build_options_card()
        self._build_progress_card()
        self._build_result_card()
        self._build_log_card()
        add_bottom_spacer(self)

    @property
    def theme(self):
        return self.app.project.theme

    @property
    def project(self):
        return self.app.project

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # -- cards -------------------------------------------------------------

    def _build_status_card(self) -> None:
        card = Card(
            self,
            "Build overview",
            "A build writes a ready-to-install theme folder and, when PkgTool is "
            "available, a fake .pkg. Missing dependencies can be downloaded for you.",
        )
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stats")

        self.type_tile = StatTile(body, "Theme type", "Static", accent=Colors.PRIMARY)
        self.type_tile.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.frames_tile = StatTile(body, "Animation", "—", accent=Colors.CYAN)
        self.frames_tile.grid(row=0, column=1, sticky="ew", padx=4)
        self.icons_tile = StatTile(body, "Custom icons", "0", accent=Colors.CYAN)
        self.icons_tile.grid(row=0, column=2, sticky="ew", padx=4)
        self.package_tile = StatTile(body, "Package", "Ready", accent=Colors.SUCCESS)
        self.package_tile.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        self.validation = ctk.CTkFrame(body, fg_color=Colors.SURFACE_ALT, corner_radius=12)
        self.validation.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(14, 0))
        self.validation.grid_columnconfigure(0, weight=1)
        self.validation_title = ctk.CTkLabel(
            self.validation,
            text="Checking the project...",
            font=font(12, "bold"),
            text_color=Colors.TEXT,
            anchor="w",
            justify="left",
        )
        self.validation_title.grid(row=0, column=0, sticky="w", padx=14, pady=(11, 2))
        self.validation_text = ctk.CTkLabel(
            self.validation,
            text="",
            font=font(11),
            text_color=Colors.TEXT_SOFT,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.validation_text.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 11))

    def _build_output_card(self) -> None:
        card = Card(
            self,
            "Build location",
            "The .pkg is copied here. A complete content folder is always kept "
            "inside the project under build/ for inspection.",
        )
        card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.output_var = ctk.StringVar(value="")
        self.output_entry = ctk.CTkEntry(
            body,
            textvariable=self.output_var,
            height=36,
            corner_radius=8,
            border_width=1,
            border_color=Colors.BORDER_STRONG,
            fg_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT,
            font=font(12),
        )
        self.output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            body,
            text="Choose...",
            width=92,
            height=36,
            corner_radius=8,
            fg_color=Colors.PRIMARY_SOFT,
            hover_color="#D9E8FF",
            text_color=Colors.PRIMARY,
            font=font(12, "bold"),
            command=self._choose_output,
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            body,
            text="Open",
            width=72,
            height=36,
            corner_radius=8,
            fg_color="transparent",
            hover_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT_SOFT,
            border_width=1,
            border_color=Colors.BORDER,
            font=font(12),
            command=self._open_output,
        ).grid(row=0, column=2)

        self.output_hint = ctk.CTkLabel(
            body,
            text="",
            font=font(11),
            text_color=Colors.TEXT_FAINT,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.output_hint.grid(row=1, column=0, columnspan=3, sticky="w", pady=(7, 0))

    def _build_options_card(self) -> None:
        card = Card(self, "Build options")
        card.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.package_switch = self._switch(
            body,
            "Create the .pkg package",
            "Uses PkgTool. Turn this off to produce only the theme folder.",
            self.app.settings.package_as_fpkg,
            self._toggle_package,
        )
        self.package_switch.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.validate_switch = self._switch(
            body,
            "Validate the package",
            "Runs pkg_validate after packing. Recommended; costs a few seconds.",
            True,
            lambda value: None,
        )
        self.validate_switch.grid(row=1, column=0, sticky="w", pady=(0, 10))

        self.auto_switch = self._switch(
            body,
            "Download missing tools automatically",
            "Fetches FFmpeg, PkgTool or at9tool from their official releases when a "
            "build needs them. Every download is size-checked and hash-verified.",
            self.app.settings.auto_install,
            self._toggle_auto_install,
        )
        self.auto_switch.grid(row=2, column=0, sticky="w")

    def _switch(self, master, label: str, hint: str, value: bool, command):
        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.grid_columnconfigure(1, weight=1)
        switch = ctk.CTkSwitch(
            frame,
            text=label,
            font=font(13, "bold"),
            text_color=Colors.TEXT,
            progress_color=Colors.PRIMARY,
            button_color=Colors.SURFACE,
            button_hover_color=Colors.SURFACE_ALT,
            fg_color=Colors.BORDER_STRONG,
            command=lambda s=None: command(bool(switch.get())),
        )
        switch.grid(row=0, column=0, sticky="w")
        if value:
            switch.select()
        else:
            switch.deselect()
        ctk.CTkLabel(
            frame,
            text=hint,
            font=font(11),
            text_color=Colors.TEXT_FAINT,
            anchor="w",
            justify="left",
            wraplength=720,
        ).grid(row=1, column=0, sticky="w", padx=(46, 0), pady=(1, 0))
        return frame

    def _build_progress_card(self) -> None:
        card = Card(self, "Build")
        card.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)

        self.build_button = ctk.CTkButton(
            row,
            text="Build theme",
            width=190,
            height=44,
            corner_radius=11,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_HOVER,
            text_color=Colors.WHITE,
            font=font(14, "bold"),
            command=self.start_build,
        )
        self.build_button.grid(row=0, column=0, sticky="w")

        self.cancel_button = ctk.CTkButton(
            row,
            text="Cancel",
            width=96,
            height=40,
            corner_radius=10,
            fg_color=Colors.DANGER_SOFT,
            hover_color="#F9D7D7",
            text_color=Colors.DANGER,
            font=font(12, "bold"),
            state="disabled",
            command=self.cancel_build,
        )
        self.cancel_button.grid(row=0, column=1, sticky="e")

        self.progress = ctk.CTkProgressBar(
            body,
            height=8,
            corner_radius=4,
            progress_color=Colors.PRIMARY,
            fg_color=Colors.PRIMARY_SOFT,
        )
        self.progress.grid(row=1, column=0, sticky="ew", pady=(16, 6))
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(
            body,
            text="Ready to build.",
            font=font(11),
            text_color=Colors.TEXT_SOFT,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.progress_label.grid(row=2, column=0, sticky="w")

    def _build_result_card(self) -> None:
        self.result_card = Card(self, "Build finished")
        self.result_card.grid(row=4, column=0, sticky="ew", pady=(0, 14))
        body = self.result_card.body
        body.grid_columnconfigure(0, weight=1)

        self.result_title = ctk.CTkLabel(
            body,
            text="",
            font=font(15, "bold"),
            text_color=Colors.SUCCESS,
            anchor="w",
        )
        self.result_title.grid(row=0, column=0, sticky="w")
        self.result_detail = ctk.CTkLabel(
            body,
            text="",
            font=font(11),
            text_color=Colors.TEXT_SOFT,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.result_detail.grid(row=1, column=0, sticky="w", pady=(4, 12))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="w")
        self.open_pkg_button = ctk.CTkButton(
            buttons,
            text="Show package",
            width=126,
            height=34,
            corner_radius=8,
            fg_color=Colors.PRIMARY,
            hover_color=Colors.PRIMARY_HOVER,
            text_color=Colors.WHITE,
            font=font(12, "bold"),
            command=self._show_package,
        )
        self.open_pkg_button.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text="Open output folder",
            width=142,
            height=34,
            corner_radius=8,
            fg_color=Colors.PRIMARY_SOFT,
            hover_color="#D9E8FF",
            text_color=Colors.PRIMARY,
            font=font(12, "bold"),
            command=self._open_output,
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text="Open theme folder",
            width=136,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT_SOFT,
            border_width=1,
            border_color=Colors.BORDER,
            font=font(12),
            command=self._open_content,
        ).grid(row=0, column=2)

        self.result_card.grid_remove()

    def _build_log_card(self) -> None:
        card = Card(
            self,
            "Build log",
            "Every step, command and warning is kept here. The log stays available "
            "after a failure so you can see exactly where it stopped.",
        )
        card.grid(row=5, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.log_box = ctk.CTkTextbox(
            body,
            height=240,
            corner_radius=10,
            border_width=0,
            fg_color=Colors.NAVY,
            text_color="#C7DFF5",
            font=(MONO_FONT, 11),
            wrap="word",
            scrollbar_button_color=Colors.NAVY_LINE,
            scrollbar_button_hover_color=Colors.CYAN,
        )
        self.log_box.grid(row=0, column=0, sticky="ew")
        self.log_box.configure(state="disabled")

        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        footer.grid_columnconfigure(0, weight=1)
        self.log_status = ctk.CTkLabel(
            footer,
            text="Nothing built yet.",
            font=font(11),
            text_color=Colors.TEXT_FAINT,
            anchor="w",
        )
        self.log_status.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer,
            text="Clear log",
            width=86,
            height=28,
            corner_radius=7,
            fg_color="transparent",
            hover_color=Colors.SURFACE_ALT,
            text_color=Colors.TEXT_SOFT,
            border_width=1,
            border_color=Colors.BORDER,
            font=font(10),
            command=self._clear_log,
        ).grid(row=0, column=1, sticky="e")

    # -- refresh -----------------------------------------------------------

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        theme = self.theme
        if theme.is_dynamic:
            width, height = theme.frame_size
            self.type_tile.set("Dynamic")
            self.frames_tile.set(f"{theme.frame_count} @ {width}x{height}")
        else:
            self.type_tile.set("Static")
            self.frames_tile.set("No animation")

        count = len(theme.function_icons) + len(theme.content_icons)
        self.icons_tile.set(str(count))

        paths = tools.resolve(self.app.settings)
        needed = tools.needed_for(theme)
        missing = [
            tools.LABELS.get(key, key)
            for key in needed
            if not {"ffmpeg": paths.ffmpeg, "pkgtool": paths.pkgtool, "at9tool": paths.at9tool}.get(key)
        ]
        if missing and self.app.settings.auto_install:
            self.package_tile.set("Tools pending")
            self.package_tile.value.configure(text_color=Colors.WARNING)
        elif missing:
            self.package_tile.set("Folder only")
            self.package_tile.value.configure(text_color=Colors.WARNING)
        else:
            self.package_tile.set(".pkg ready")
            self.package_tile.value.configure(text_color=Colors.SUCCESS)

        if not self.running:
            if self.app.settings.output_dir:
                output = self.app.settings.output_dir
            else:
                output = str(self.app.settings.default_output_dir())
            if self.output_var.get().strip() in ("",) or not self.output_entry.focus_get():
                self.output_var.set(output)
            self.output_hint.configure(text=f"Package name: {self._expected_name()}")

        self._refresh_validation(missing)
        self._refresh_buttons()

    def _expected_name(self) -> str:
        slug = builder._slug(self.theme.name)
        return f"{slug}_{self.theme.mode}.pkg"

    def _refresh_validation(self, missing: list[str]) -> None:
        errors, warnings = models.validate(self.project)
        messages: list[str] = []
        if errors:
            title = f"{len(errors)} problem{'s' if len(errors) != 1 else ''} to fix before building"
            colour = Colors.DANGER
            messages += errors
        elif missing:
            title = "The theme is valid; some tools are not installed yet"
            colour = Colors.WARNING
            messages.append("Missing: " + ", ".join(missing) + ".")
            if self.app.settings.auto_install:
                messages.append("They will be downloaded automatically when you press Build.")
            else:
                messages.append("Install them from the Tools tab, or turn on automatic downloads.")
        else:
            title = "Ready to build"
            colour = Colors.SUCCESS
            messages.append("Everything needed for this theme is present.")
        messages += warnings

        self.validation_title.configure(text=title, text_color=colour)
        if len(messages) == 1:
            self.validation_text.configure(text=messages[0], text_color=Colors.TEXT_SOFT)
        else:
            self.validation_text.configure(
                text="\n".join("• " + message for message in messages[:8]),
                text_color=Colors.TEXT_SOFT,
            )

    def _refresh_buttons(self) -> None:
        running = self.running
        self.build_button.configure(
            state="disabled" if running else "normal",
            text="Building..." if running else "Build theme",
        )
        self.cancel_button.configure(state="normal" if running else "disabled")

    # -- settings ----------------------------------------------------------

    def _choose_output(self) -> None:
        initial = self.output_var.get().strip() or str(self.app.settings.default_output_dir())
        folder = filedialog.askdirectory(
            title="Where should the finished package go?",
            initialdir=initial if Path(initial).is_dir() else str(self.project.root),
        )
        if not folder:
            return
        self.output_var.set(folder)
        self.app.settings.output_dir = folder
        self.app.settings.save()
        self.output_hint.configure(text=f"Package name: {self._expected_name()}")

    def _current_output(self) -> Path:
        raw = self.output_var.get().strip()
        return Path(raw).expanduser() if raw else self.app.settings.default_output_dir()

    def _open_output(self) -> None:
        folder = self._current_output()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            tools.open_folder(folder)
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not open the folder:\n{exc}")

    def _toggle_package(self, value: bool) -> None:
        self.app.settings.package_as_fpkg = bool(value)
        self.app.settings.save()
        if not value:
            self.app.set_status("Packaging disabled; the theme folder will still be built.", "warning")

    def _toggle_auto_install(self, value: bool) -> None:
        self.app.settings.auto_install = bool(value)
        self.app.settings.save()
        self.refresh()

    # -- build -------------------------------------------------------------

    def start_build(self) -> None:
        if self.running:
            return
        self.app.save_now()
        errors, _warnings = models.validate(self.project)
        if errors:
            self._refresh_validation([])
            self.app.set_status("Fix the highlighted problems before building.", "danger")
            return

        output = self._current_output()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Cannot create the output folder:\n{exc}")
            return

        self.app.settings.output_dir = str(output)
        self.app.settings.save()

        options = builder.BuildOptions(
            output_dir=output,
            package=bool(self.package_switch.winfo_exists() and self._switch_state(self.package_switch)),
            auto_install=bool(self._switch_state(self.auto_switch)),
            validate_package=bool(self._switch_state(self.validate_switch)),
        )

        snapshot = copy.deepcopy(self.project)
        cancel = threading.Event()
        self._cancel = cancel
        self._result = None
        self.result_card.grid_remove()
        self._clear_log()
        self.progress.configure(mode="determinate")
        self.progress.stop()
        self.progress.set(0)
        self.progress_label.configure(text="Starting the build...", text_color=Colors.TEXT_SOFT)
        self.log_status.configure(text="Build running...")
        self._append_log(f"Project: {snapshot.root}")
        self._append_log(
            f"Mode: {snapshot.theme.mode}"
            + (
                f", {snapshot.theme.frame_count} frames at {snapshot.theme.resolution}"
                if snapshot.theme.is_dynamic
                else ""
            )
        )
        self._append_log(f"Output: {output}")
        self._thread = threading.Thread(
            target=self._worker,
            args=(snapshot, options, cancel),
            name="ps4theme-build",
            daemon=True,
        )
        self._thread.start()
        self._refresh_buttons()
        self._pump_job = self.after(80, self._drain)
        self.app.set_status("Build started", "info")

    def _switch_state(self, frame) -> bool:
        for child in frame.winfo_children():
            if isinstance(child, ctk.CTkSwitch):
                return bool(child.get())
        return False

    def _worker(self, project, options, cancel: threading.Event) -> None:
        try:
            result = builder.build(
                project,
                options,
                settings=self.app.settings,
                progress=lambda message, fraction: self._queue.put(
                    ("progress", (message, fraction))
                ),
                cancel=cancel,
                log_sink=lambda message: self._queue.put(("log", message)),
            )
            self._queue.put(("done", result))
        except builder.BuildCancelled:
            self._queue.put((CANCELLED, "The build was cancelled."))
        except builder.BuildError as exc:
            self._queue.put(("error", str(exc)))
        except Exception as exc:  # pragma: no cover - unexpected failures only
            self._queue.put(("error", f"{exc}\n\n{traceback.format_exc()}"))

    def _drain(self) -> None:
        self._pump_job = None
        finished = False
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "progress":
                    message, fraction = payload
                    self._last_message = message
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
                    self.log_status.configure(text=elide(message, 110))
                elif kind == "log":
                    self._append_log(payload)
                elif kind == "done":
                    finished = True
                    self._finish(payload)
                elif kind == CANCELLED:
                    finished = True
                    self._fail(payload, cancelled=True)
                elif kind == "error":
                    finished = True
                    self._fail(payload)
        except queue.Empty:
            pass

        if finished:
            self._thread = None
            self._cancel = None
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self._refresh_buttons()
            self.refresh()
        elif self.running or not self._queue.empty():
            self._pump_job = self.after(80, self._drain)

    def _finish(self, result: builder.BuildResult) -> None:
        self._result = result
        self.progress.set(1.0)
        self.progress_label.configure(
            text=f"Finished in {result.seconds:.1f}s.", text_color=Colors.SUCCESS
        )
        self.log_status.configure(text=f"Finished in {result.seconds:.1f}s.")
        if result.warnings:
            self._append_log("")
            for warning in result.warnings:
                self._append_log(f"Warning: {warning}")

        if result.pkg_path:
            size = result.pkg_path.stat().st_size / 1048576
            self.result_title.configure(text="Package ready", text_color=Colors.SUCCESS)
            self.result_detail.configure(
                text=f"{result.pkg_path.name}  ·  {size:.2f} MiB\n{result.pkg_path}"
            )
            self.open_pkg_button.configure(state="normal")
        else:
            self.result_title.configure(text="Theme folder ready", text_color=Colors.WARNING)
            self.result_detail.configure(
                text="No package was created, but the complete theme content is here:\n"
                f"{result.content_dir}"
            )
            self.open_pkg_button.configure(state="disabled")
        self.result_card.grid()
        self.app.set_status("Build finished", "success")
        self.app.refresh_tool_status()

    def _fail(self, message: str, *, cancelled: bool = False) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.progress_label.configure(
            text="Build cancelled." if cancelled else "Build failed.",
            text_color=Colors.WARNING if cancelled else Colors.DANGER,
        )
        self.log_status.configure(
            text="Cancelled." if cancelled else "Failed. See the log above."
        )
        self._append_log("")
        self._append_log(("Cancelled: " if cancelled else "Error: ") + message)
        if not cancelled:
            self.app.set_status("Build failed - see the log", "danger")
        else:
            self.app.set_status("Build cancelled", "warning")

    def cancel_build(self) -> None:
        if not self.running or self._cancel is None:
            return
        self._cancel.set()
        self.cancel_button.configure(state="disabled")
        self.progress_label.configure(text="Cancelling after the current step...")
        self._append_log("Cancellation requested.")

    # -- log helpers -------------------------------------------------------

    def _append_log(self, message: str) -> None:
        text = str(message or "")
        self.log_box.configure(state="normal")
        if text:
            self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.log_status.configure(text="Nothing built yet.")

    # -- result actions ----------------------------------------------------

    def _show_package(self) -> None:
        if self._result and self._result.pkg_path:
            self._reveal(self._result.pkg_path)

    def _open_content(self) -> None:
        if self._result and self._result.content_dir.is_dir():
            try:
                tools.open_folder(self._result.content_dir)
            except OSError as exc:
                messagebox.showerror(C.APP_NAME, f"Could not open the folder:\n{exc}")
            return
        folder = self.project.root / C.BUILD_DIR_NAME
        try:
            folder.mkdir(parents=True, exist_ok=True)
            tools.open_folder(folder)
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not open the folder:\n{exc}")

    @staticmethod
    def _reveal(path: Path) -> None:
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                tools.open_folder(Path(path).parent)
        except OSError:
            pass

    # -- lifecycle ---------------------------------------------------------

    def destroy(self) -> None:
        if self.running and self._cancel is not None:
            self._cancel.set()
        if self._pump_job:
            try:
                self.after_cancel(self._pump_job)
            except Exception:
                pass
        super().destroy()
