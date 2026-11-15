"""Theme tab: project details, artwork, video and music."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from .. import constants as C
from .. import images, media, models
from .widgets import (
    Card,
    Chip,
    Colors,
    FilePicker,
    FormField,
    ScrollPage,
    add_bottom_spacer,
    font,
)

MODE_LABELS = {"static": "Static image", "dynamic": "Dynamic video"}
MODE_DESCRIPTIONS = {
    "static": "A single high-resolution artwork for the home screen and the top menu. "
              "The simplest and most compatible kind of theme.",
    "dynamic": "A short video converted into a PS4 RAF animation. The console caps the "
               "whole scene at 6 MiB and 48 frames, so shorter clips work best.",
}


class ThemePage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._refreshing = False
        self._wait_error = False

        self._build_type_card()
        self._build_details_card()
        self._build_media_card()
        self._build_animation_card()
        self._build_project_card()
        add_bottom_spacer(self)

    @property
    def theme(self):
        return self.app.project.theme

    @property
    def project(self):
        return self.app.project

    # -- cards -------------------------------------------------------------

    def _build_type_card(self) -> None:
        card = Card(
            self,
            "Theme type",
            "Choose how the background is made. You can switch at any time; only the "
            "files needed by the selected type are written.",
        )
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        body = card.body

        self.mode_seg = ctk.CTkSegmentedButton(
            body,
            values=[MODE_LABELS["static"], MODE_LABELS["dynamic"]],
            command=self._select_mode,
            height=38,
            corner_radius=10,
            font=font(13, "bold"),
            fg_color=Colors.SURFACE_ALT,
            selected_color=Colors.PRIMARY,
            selected_hover_color=Colors.PRIMARY_HOVER,
            unselected_color=Colors.SURFACE_ALT,
            unselected_hover_color=Colors.PRIMARY_SOFT,
            text_color=Colors.TEXT,
        )
        self.mode_seg.grid(row=0, column=0, sticky="w")
        self.mode_seg.set(MODE_LABELS["static"])

        self.mode_description = ctk.CTkLabel(
            body,
            text=MODE_DESCRIPTIONS["static"],
            font=font(12),
            text_color=Colors.TEXT_SOFT,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.mode_description.grid(row=1, column=0, sticky="w", pady=(12, 0))

    def _build_details_card(self) -> None:
        card = Card(
            self,
            "Theme details",
            "These values end up in param.sfo and theme.xml. The Title ID and Content ID "
            "are what the console uses to identify the package.",
        )
        card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        body = card.body
        body.grid_columnconfigure(0, weight=1, uniform="details")
        body.grid_columnconfigure(1, weight=1, uniform="details")

        self.name_field = FormField(
            body,
            "Theme name",
            placeholder="My Theme",
            hint="Shown in Settings > Themes.",
            on_change=self._change_name,
        )
        self.name_field.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self.creator_field = FormField(
            body,
            "Creator / provider",
            placeholder="Your name",
            hint="Optional. Shown as the theme provider.",
            on_change=lambda value: self._set("creator", value),
        )
        self.creator_field.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(0, 12))

        self.version_field = FormField(
            body,
            "Version",
            placeholder="01.00",
            hint="Two digits, a dot, two digits.",
            on_change=lambda value: self._set("version", value),
            width=150,
        )
        self.version_field.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 12))

        self.title_field = FormField(
            body,
            "Title ID",
            placeholder=C.DEFAULT_TITLE_ID,
            hint="4 letters followed by 5 digits.",
            on_change=self._change_title_id,
            width=200,
        )
        self.title_field.grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=(0, 4))

        content_frame = ctk.CTkFrame(body, fg_color="transparent")
        content_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 0))
        content_frame.grid_columnconfigure(0, weight=1)
        self.content_field = FormField(
            content_frame,
            "Content ID",
            placeholder="UP9000-CUSA00000_00-ABCDEFGHIJKLMNOP",
            hint="36 characters. Changing it gives the console a clean identity for a rebuild.",
            on_change=lambda value: self._set("content_id", value),
        )
        self.content_field.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            content_frame,
            text="Generate",
            width=104,
            height=36,
            corner_radius=8,
            fg_color=Colors.CYAN_SOFT,
            hover_color="#CBEEF6",
            text_color=Colors.CYAN,
            font=font(12, "bold"),
            command=self._generate_content_id,
        ).grid(row=0, column=1, sticky="s", padx=(10, 0), pady=(0, 22))

    def _build_media_card(self) -> None:
        card = Card(self, "Artwork & music", "Files are copied into the project's assets folder, so the project stays portable.")
        card.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        self.media_body = card.body
        self.media_body.grid_columnconfigure(0, weight=1)

        self.background_picker = FilePicker(
            self.media_body,
            title="Home screen background",
            hint="PNG, JPG or WebP. Scaled and centre-cropped to 1920x1080. "
                 "The thumbnail and theme icon are derived from it unless you pick separate ones.",
            on_choose=self._choose_background,
            on_clear=self._clear_background,
            kinds=C.IMAGE_EXTS,
            preview_size=(250, 141),
            placeholder_kind="image",
        )
        self.functionscreen_picker = FilePicker(
            self.media_body,
            title="Top-menu background (optional)",
            hint="Used behind the function icons. Leave empty to reuse the home background.",
            on_choose=self._choose_function,
            on_clear=self._clear_function,
            kinds=C.IMAGE_EXTS,
            preview_size=(190, 107),
            placeholder_kind="image",
        )
        self.video_picker = FilePicker(
            self.media_body,
            title="Source video",
            hint="MP4, MOV, MKV, WebM, AVI or GIF. The whole clip is sampled into the "
                 "PS4's frame budget, so short loops look smoothest.",
            on_choose=self._choose_video,
            on_clear=self._clear_video,
            kinds=C.VIDEO_EXTS,
            preview_size=(250, 141),
            placeholder_kind="video",
        )
        self.cover_picker = FilePicker(
            self.media_body,
            title="Cover image (optional)",
            hint="Used for the theme thumbnail and icon. If empty, the first video frame is used.",
            on_choose=self._choose_background,
            on_clear=self._clear_background,
            kinds=C.IMAGE_EXTS,
            preview_size=(190, 107),
            placeholder_kind="image",
        )
        self.icon_picker = FilePicker(
            self.media_body,
            title="Theme icon (optional)",
            hint="512x512 appears in Settings > Themes. Defaults to a crop of the background.",
            on_choose=self._choose_icon,
            on_clear=self._clear_icon,
            kinds=C.IMAGE_EXTS,
            preview_size=(112, 112),
            placeholder_kind="icon",
        )
        self.music_picker = FilePicker(
            self.media_body,
            title="Background music (optional)",
            hint="MP3, WAV, OGG, FLAC or an existing .at9. Converted to ATRAC9 at 48 kHz "
                 "when at9tool is installed.",
            on_choose=self._choose_music,
            on_clear=self._clear_music,
            kinds=C.AUDIO_EXTS,
            preview_size=(250, 96),
            placeholder_kind="audio",
        )

        for picker in (
            self.background_picker, self.functionscreen_picker, self.video_picker,
            self.cover_picker, self.icon_picker, self.music_picker,
        ):
            picker.grid_columnconfigure(1, weight=1)

    def _build_animation_card(self) -> None:
        self.animation_card = Card(
            self,
            "Animation",
            "The PS4 stores a dynamic background as DXT1 frames. Size is fixed per "
            "resolution, so lowering it buys more frames within the 6 MiB budget.",
        )
        self.animation_card.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        body = self.animation_card.body
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="new", padx=(0, 18))
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left, text="RESOLUTION", font=font(10, "bold"),
            text_color=Colors.TEXT_FAINT, anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.resolution_menu = ctk.CTkOptionMenu(
            left,
            values=list(C.ANIMATED_SIZES),
            command=self._change_resolution,
            height=36,
            corner_radius=8,
            fg_color=Colors.SURFACE_ALT,
            button_color=Colors.PRIMARY_SOFT,
            button_hover_color="#D9E8FF",
            text_color=Colors.TEXT,
            font=font(12),
            dropdown_fg_color=Colors.SURFACE,
            dropdown_text_color=Colors.TEXT,
        )
        self.resolution_menu.grid(row=1, column=0, sticky="ew")

        self.limit_label = ctk.CTkLabel(
            left, text="", font=font(11), text_color=Colors.TEXT_FAINT,
            anchor="w", justify="left", wraplength=320,
        )
        self.limit_label.grid(row=2, column=0, sticky="w", pady=(8, 0))

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="new")
        right.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(right, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="FRAMES", font=font(10, "bold"),
            text_color=Colors.TEXT_FAINT, anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.frames_value = ctk.CTkLabel(
            header, text="12 frames", font=font(12, "bold"),
            text_color=Colors.PRIMARY, anchor="e",
        )
        self.frames_value.grid(row=0, column=1, sticky="e")

        self.frame_slider = ctk.CTkSlider(
            right,
            from_=C.MIN_FRAME_COUNT,
            to=13,
            number_of_steps=11,
            command=self._change_frames,
            progress_color=Colors.PRIMARY,
            button_color=Colors.PRIMARY,
            button_hover_color=Colors.PRIMARY_HOVER,
            fg_color=Colors.PRIMARY_SOFT,
        )
        self.frame_slider.grid(row=1, column=0, sticky="ew")
        self.frame_slider.set(C.DEFAULT_FRAME_COUNT)

        self.memory_label = ctk.CTkLabel(
            right, text="", font=font(11), text_color=Colors.TEXT_FAINT, anchor="w"
        )
        self.memory_label.grid(row=2, column=0, sticky="w", pady=(8, 12))

        self.wait_field = FormField(
            right,
            "Seconds per frame",
            value="0",
            hint="0 = spread the frames across the whole video. Otherwise 0.02 to 5 seconds.",
            on_change=self._change_wait,
            width=200,
        )
        self.wait_field.grid(row=3, column=0, sticky="w")

        self.loop_label = ctk.CTkLabel(
            right, text="", font=font(11), text_color=Colors.TEXT_SOFT, anchor="w"
        )
        self.loop_label.grid(row=4, column=0, sticky="w", pady=(6, 0))

    def _build_project_card(self) -> None:
        card = Card(self, "Project folder", "Everything lives in one folder: theme.ps4t.json plus the copied assets.")
        card.grid(row=4, column=0, sticky="ew", pady=(0, 14))
        body = card.body

        self.project_path_label = ctk.CTkLabel(
            body, text="", font=(("Consolas"), 11), text_color=Colors.TEXT_SOFT,
            anchor="w", justify="left", wraplength=740,
        )
        self.project_path_label.grid(row=0, column=0, sticky="w", pady=(0, 12))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="w")
        for index, (label, command, primary) in enumerate([
            ("Open folder", self.app.open_project_folder, True),
            ("Open project...", self.app.open_project_dialog, False),
            ("New project...", self.app.new_project_dialog, False),
        ]):
            ctk.CTkButton(
                buttons,
                text=label,
                width=124,
                height=34,
                corner_radius=8,
                fg_color=Colors.PRIMARY if primary else Colors.SURFACE_ALT,
                hover_color=Colors.PRIMARY_HOVER if primary else Colors.BORDER,
                text_color=Colors.WHITE if primary else Colors.TEXT_SOFT,
                font=font(12, "bold" if primary else "normal"),
                command=command,
            ).grid(row=0, column=index, padx=(0, 8))

        self.saved_chip = Chip(body, "Saved automatically", kind="neutral")
        self.saved_chip.grid(row=2, column=0, sticky="w", pady=(14, 0))

    # -- refresh -----------------------------------------------------------

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        theme = self.theme
        self._refreshing = True
        try:
            self.name_field.set(theme.name)
            self.creator_field.set(theme.creator)
            self.version_field.set(theme.version)
            self.title_field.set(theme.title_id)
            self.content_field.set(theme.content_id)

            self.mode_seg.set(MODE_LABELS.get(theme.mode, MODE_LABELS["static"]))

            self.background_picker.show(self.project.path_for(theme.background))
            self.cover_picker.show(self.project.path_for(theme.background))
            self.functionscreen_picker.show(self.project.path_for(theme.functionscreen))
            self.icon_picker.show(self.project.path_for(theme.icon))
            self.video_picker.show(self.project.path_for(theme.video))
            self.music_picker.show(self.project.path_for(theme.music))

            if theme.resolution not in C.ANIMATED_SIZES:
                theme.resolution = C.DEFAULT_RESOLUTION
            self.resolution_menu.set(theme.resolution)

            maximum = C.max_frames_for(*C.resolution_size(theme.resolution))
            count = max(C.MIN_FRAME_COUNT, min(int(theme.frame_count), maximum))
            if count != theme.frame_count:
                theme.frame_count = count
            self.frame_slider.configure(
                from_=C.MIN_FRAME_COUNT,
                to=maximum,
                number_of_steps=max(1, maximum - C.MIN_FRAME_COUNT),
            )
            self.frame_slider.set(count)

            wait_text = "0" if not theme.frame_wait else f"{theme.frame_wait:g}"
            self.wait_field.set(wait_text)
            self._wait_error = False

            self.project_path_label.configure(text=str(self.project.root))
        finally:
            self._refreshing = False

        self._update_mode_ui()
        self._update_animation_labels()

    def _update_mode_ui(self) -> None:
        theme = self.theme
        dynamic = theme.is_dynamic
        self.mode_description.configure(text=MODE_DESCRIPTIONS[theme.mode])

        for picker in (
            self.background_picker, self.functionscreen_picker, self.video_picker,
            self.cover_picker, self.icon_picker, self.music_picker,
        ):
            picker.grid_remove()

        row = 0
        if dynamic:
            for picker in (self.video_picker, self.cover_picker):
                picker.grid(row=row, column=0, sticky="ew", pady=(0, 16))
                row += 1
            self.animation_card.grid()
        else:
            for picker in (self.background_picker, self.functionscreen_picker):
                picker.grid(row=row, column=0, sticky="ew", pady=(0, 16))
                row += 1
            self.animation_card.grid_remove()

        self.icon_picker.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        row += 1
        self.music_picker.grid(row=row, column=0, sticky="ew")

    def _update_animation_labels(self) -> None:
        theme = self.theme
        width, height = theme.frame_size
        maximum = C.max_frames_for(width, height)
        count = min(int(theme.frame_count), maximum)
        self.frames_value.configure(text=f"{count} frames")
        self.limit_label.configure(
            text=f"{maximum} frames fit at {width}x{height} within the 6 MiB limit."
        )
        size = C.dds_size_for(width, height) * count
        self.memory_label.configure(
            text=f"Estimated scene size: {size / 1048576:.2f} MiB of 6 MiB."
        )
        if theme.frame_wait and theme.frame_wait > 0:
            self.loop_label.configure(text=f"Loop length: {count * theme.frame_wait:.2f} seconds.")
        else:
            self.loop_label.configure(text="Loop length: matches the video duration.")

    # -- field handlers ----------------------------------------------------

    def _set(self, field: str, value: str) -> None:
        if self._refreshing:
            return
        setattr(self.theme, field, value)
        self.app.mark_dirty()
        self.app.refresh_header()

    def _change_name(self, value: str) -> None:
        if self._refreshing:
            return
        self.theme.name = value
        self.app.mark_dirty()
        self.app.refresh_header()
        if self.app.current_page == "appearance":
            self.app._pages["appearance"].on_show()

    def _change_title_id(self, value: str) -> None:
        if self._refreshing:
            return
        self.theme.title_id = value.strip().upper()
        if self.title_field.get() != self.theme.title_id:
            self.title_field.set(self.theme.title_id)
        self.app.mark_dirty()

    def _generate_content_id(self) -> None:
        self.theme.content_id = models.build_content_id(self.theme.title_id, self.theme.name)
        self.content_field.set(self.theme.content_id)
        self.app.mark_dirty()
        self.app.set_status("Content ID generated", "success")

    def _select_mode(self, label: str) -> None:
        if self._refreshing:
            return
        mode = "dynamic" if label == MODE_LABELS["dynamic"] else "static"
        if mode == self.theme.mode:
            return
        self.theme.mode = mode
        self.theme.frame_count = min(self.theme.frame_count, self.theme.max_frames)
        self._update_mode_ui()
        self._update_animation_labels()
        self.app.mark_dirty()
        self.app.set_status(f"Switched to {label.lower()}", "info")

    def _change_resolution(self, value: str) -> None:
        if self._refreshing:
            return
        self.theme.resolution = value
        maximum = self.theme.max_frames
        if self.theme.frame_count > maximum:
            self.theme.frame_count = maximum
        self.frame_slider.configure(
            from_=C.MIN_FRAME_COUNT,
            to=maximum,
            number_of_steps=max(1, maximum - C.MIN_FRAME_COUNT),
        )
        self.frame_slider.set(self.theme.frame_count)
        self._update_animation_labels()
        self.app.mark_dirty()

    def _change_frames(self, value: float) -> None:
        if self._refreshing:
            return
        self.theme.frame_count = int(round(value))
        self._update_animation_labels()
        self.app.mark_dirty()

    def _change_wait(self, value: str) -> None:
        if self._refreshing:
            return
        text = (value or "").strip()
        if text in ("", "0"):
            self.theme.frame_wait = 0.0
            self._wait_error = False
            self.wait_field.set_hint("0 = spread the frames across the whole video.")
            self._update_animation_labels()
            self.app.mark_dirty()
            return
        try:
            seconds = float(text)
        except ValueError:
            self.wait_field.set_hint("Enter a number between 0.02 and 5, or 0 for automatic.")
            self._wait_error = True
            return
        if not C.MIN_WAIT_SECONDS <= seconds <= C.MAX_WAIT_SECONDS:
            self.wait_field.set_hint(f"Use 0.02 to 5 seconds (or 0 for automatic).")
            self._wait_error = True
            return
        self.theme.frame_wait = seconds
        self._wait_error = False
        self.wait_field.set_hint("0 = spread the frames across the whole video. Otherwise 0.02 to 5 seconds.")
        self._update_animation_labels()
        self.app.mark_dirty()

    # -- asset handlers ----------------------------------------------------

    def _import_image(self, path: Path) -> str | None:
        try:
            images.open_image(path)
        except images.ImageError as exc:
            messagebox.showerror(C.APP_NAME, str(exc))
            return None
        try:
            return self.project.import_asset(path, "images")
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not copy the image:\n{exc}")
            return None

    def _choose_background(self, path: Path) -> None:
        relative = self._import_image(path)
        if not relative:
            return
        old = self.theme.background
        self.theme.background = relative
        self._release(old)
        self.background_picker.show(self.project.path_for(relative))
        self.cover_picker.show(self.project.path_for(relative))
        self.app.mark_dirty()
        self.app.set_status("Background updated", "success")

    def _clear_background(self) -> None:
        old = self.theme.background
        self.theme.background = ""
        self.background_picker.show(None)
        self.cover_picker.show(None)
        self._release(old)
        self.app.mark_dirty()

    def _choose_function(self, path: Path) -> None:
        relative = self._import_image(path)
        if not relative:
            return
        old = self.theme.functionscreen
        self.theme.functionscreen = relative
        self._release(old)
        self.functionscreen_picker.show(self.project.path_for(relative))
        self.app.mark_dirty()

    def _clear_function(self) -> None:
        old = self.theme.functionscreen
        self.theme.functionscreen = ""
        self.functionscreen_picker.show(None)
        self._release(old)
        self.app.mark_dirty()

    def _choose_icon(self, path: Path) -> None:
        relative = self._import_image(path)
        if not relative:
            return
        old = self.theme.icon
        self.theme.icon = relative
        self._release(old)
        self.icon_picker.show(self.project.path_for(relative))
        self.app.mark_dirty()

    def _clear_icon(self) -> None:
        old = self.theme.icon
        self.theme.icon = ""
        self.icon_picker.show(None)
        self._release(old)
        self.app.mark_dirty()

    def _choose_video(self, path: Path) -> None:
        try:
            relative = self.project.import_asset(path, "video")
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not copy the video:\n{exc}")
            return
        old = self.theme.video
        self.theme.video = relative
        self._release(old)
        self.video_picker.show(self.project.path_for(relative))
        self.app.mark_dirty()
        if media.available():
            try:
                info = media.probe(path)
                self.app.set_status(
                    f"Video: {info.width}x{info.height}, {info.duration:.1f}s, {info.fps:.0f} fps",
                    "success",
                )
            except media.MediaError:
                self.app.set_status("Video added", "success")
        else:
            self.app.set_status("Video added", "success")

    def _clear_video(self) -> None:
        old = self.theme.video
        self.theme.video = ""
        self.video_picker.show(None)
        self._release(old)
        self.app.mark_dirty()

    def _choose_music(self, path: Path) -> None:
        try:
            relative = self.project.import_asset(path, "audio")
        except OSError as exc:
            messagebox.showerror(C.APP_NAME, f"Could not copy the music:\n{exc}")
            return
        old = self.theme.music
        self.theme.music = relative
        self._release(old)
        self.music_picker.show(self.project.path_for(relative))
        self.app.mark_dirty()

    def _clear_music(self) -> None:
        old = self.theme.music
        self.theme.music = ""
        self.music_picker.show(None)
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
