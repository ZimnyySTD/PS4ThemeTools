"""Build pipeline: project -> theme folder -> fake .pkg.

The flow is intentionally linear and leaves every intermediate file on disk,
so a failed build can be inspected and a build without PkgTool still gives a
complete, installable theme folder.

    validate -> copy assets -> images -> music -> RAF scene -> theme.xml
             -> param.sfo -> .gp4 -> PkgTool -> .pkg
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import audio, constants as C, dxt1, images, media, models, raf, sfo, theme_xml, tools
from .gp4 import build_gp4
from .settings import Settings

Progress = Callable[[str, float], None]

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PKG_BUILD_TIMEOUT = 30 * 60


class BuildError(RuntimeError):
    """A required step failed."""


class BuildCancelled(RuntimeError):
    """The user cancelled the build."""


@dataclass
class BuildOptions:
    output_dir: Path
    package: bool = True
    auto_install: bool = True
    validate_package: bool = True


@dataclass
class BuildResult:
    content_dir: Path
    build_dir: Path
    pkg_path: Path | None
    warnings: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def packaged(self) -> bool:
        return self.pkg_path is not None


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip()).strip(".-")
    return (cleaned or "theme")[:60]


class _Reporter:
    def __init__(
        self,
        progress: Progress | None,
        log: list[str],
        log_sink: Callable[[str], None] | None = None,
    ) -> None:
        self.progress = progress
        self.log = log
        self.log_sink = log_sink

    def _write(self, message: str) -> None:
        self.log.append(message)
        if self.log_sink:
            try:
                self.log_sink(message)
            except Exception:
                # A broken UI callback must never break a build.
                pass

    def __call__(self, message: str, fraction: float) -> None:
        self._write(message)
        if self.progress:
            # Negative values mean "unknown total" (indeterminate progress).
            value = -1.0 if fraction < 0 else min(1.0, max(0.0, fraction))
            self.progress(message, value)

    def detail(self, message: str) -> None:
        self._write(message)

    def check_cancel(self, cancel) -> None:
        if cancel is not None and cancel.is_set():
            raise BuildCancelled("Build cancelled.")


def _clean_tool_output(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace").replace("\r\n", "\n")
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^(Fake PKG Tools|LibOrbisPkg|PkgTool|orbis-pub-cmd|Custom Patches|-{3,})", stripped):
            continue
        lines.append(stripped)
    if len(lines) > 120:
        lines = ["..."] + lines[-120:]
    return "\n".join(lines)


def _run_pkgtool(exe: Path, args: list[str], reporter: _Reporter, label: str) -> str:
    command = [str(exe), *args]
    reporter.detail(f"$ {Path(command[0]).name} {' '.join(args)}")
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=PKG_BUILD_TIMEOUT,
            creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise BuildError(f"{label} timed out after {PKG_BUILD_TIMEOUT // 60} minutes.") from exc
    except OSError as exc:
        raise BuildError(f"Cannot run PkgTool: {exc}") from exc

    output = _clean_tool_output(proc.stdout or b"")
    if output:
        reporter.detail(output)
    errors = [line for line in output.splitlines() if "[Error]" in line or line.lower().startswith("error")]
    if proc.returncode != 0 or errors:
        detail = "\n".join(errors) or output.splitlines()[-1] if output else f"exit code {proc.returncode}"
        raise BuildError(f"{label} failed: {detail}")
    return output


def _copy_music(project, content: Path, work: Path, reporter: _Reporter) -> bool:
    """Converts the chosen music and returns True when bgm_home.at9 exists."""
    theme = project.theme
    source = project.path_for(theme.music)
    if not (source and source.is_file()):
        if theme.music:
            reporter.detail("Music file is missing; the theme will be silent.")
        return False

    target = content / C.THEME_PATH_MUSIC
    target.parent.mkdir(parents=True, exist_ok=True)

    if source.suffix.lower() == ".at9":
        if not audio.is_at9(source):
            reporter.detail(
                f"{source.name} does not look like a valid ATRAC9 file; "
                "the music will be skipped."
            )
            return False
        shutil.copy2(source, target)
        reporter("Music copied (.at9).", 0.17)
        return True

    at9 = audio.find_tool()
    if at9 is None:
        reporter.detail(
            "at9tool is not installed, so the music will be skipped. "
            "Install it from the Tools tab and build again."
        )
        return False
    if not media.available():
        reporter.detail("FFmpeg is unavailable; the music will be skipped.")
        return False

    wav = work / "bgm_home.wav"
    reporter("Converting music...", 0.14)
    try:
        media.to_wav(source, wav, rate=audio.SAMPLE_RATE, max_seconds=C.MAX_SFX_SECONDS)
        audio.configure(at9)
        audio.encode(wav, target)
        reporter("Music encoded to ATRAC9.", 0.18)
        return True
    except (media.MediaError, audio.AudioError) as exc:
        reporter.detail(f"Music conversion failed, continuing without it: {exc}")
        return False
    finally:
        wav.unlink(missing_ok=True)


def _build_raf(project, content: Path, work: Path, reporter: _Reporter, cancel) -> float:
    """Extracts frames, writes DDS files and the scene.  Returns the wait time."""
    theme = project.theme
    video = project.path_for(theme.video)
    if not (video and video.is_file()):
        raise BuildError("The source video is missing.")

    width, height = theme.frame_size
    raf_dir = content / C.THEME_PATH_RAF
    raf_dir.mkdir(parents=True, exist_ok=True)

    reporter("Reading the video...", 0.20)
    try:
        info = media.probe(video)
    except media.MediaError as exc:
        raise BuildError(f"Cannot read the video: {exc}") from exc

    count = max(C.MIN_FRAME_COUNT, min(int(theme.frame_count), theme.max_frames))
    if theme.frame_wait and theme.frame_wait > 0:
        wait = max(C.MIN_WAIT_SECONDS, min(C.MAX_WAIT_SECONDS, float(theme.frame_wait)))
    else:
        wait = info.duration / count
        wait = max(C.MIN_WAIT_SECONDS, min(C.MAX_WAIT_SECONDS, wait))

    reporter.detail(
        f"Video: {info.width}x{info.height}, {info.duration:.2f}s, "
        f"{info.fps:.3f} fps, {info.codec}."
    )
    reporter.detail(
        f"Animation: {count} frames at {width}x{height}, {wait:.4f}s per frame "
        f"({count * wait:.2f}s loop)."
    )

    from . import mdx

    half_w, half_h = raf.plane_half_size()
    plane = mdx.quad_model(half_w=half_w, half_h=half_h, depth=raf.PLANE_DEPTH)
    (raf_dir / raf.MODEL_FILE).write_bytes(plane)

    frame_names: list[str] = []
    total = 0
    try:
        for index, frame in enumerate(media.iter_frames(video, count, (width, height), info.duration)):
            reporter.check_cancel(cancel)
            data = dxt1.encode_dds(frame)
            name = f"{index:02d}.dds"
            (raf_dir / name).write_bytes(data)
            frame_names.append(name)
            total += len(data)
            fraction = 0.22 + 0.55 * ((index + 1) / count)
            reporter(f"Encoding frame {index + 1} of {count}...", fraction)
            del frame
    except media.MediaError as exc:
        raise BuildError(f"Frame extraction failed: {exc}") from exc

    if not frame_names:
        raise BuildError("No frames were extracted from the video.")
    if total > C.RAF_SIZE_LIMIT:
        raise BuildError(
            f"The animation weighs {total / 1048576:.1f} MiB, over the "
            f"{C.RAF_SIZE_LIMIT / 1048576:.0f} MiB console limit. "
            "Choose a lower resolution or fewer frames."
        )

    (raf_dir / "index.xml").write_text(
        raf.build_scene(frame_names, wait), encoding="utf-8"
    )
    reporter.detail(f"Animation written: {len(frame_names)} frames, {total / 1048576:.2f} MiB.")
    return wait


def _prepare_tools(options: BuildOptions, settings: Settings, theme, reporter: _Reporter) -> tools.ToolPaths:
    needed = []
    if options.package:
        needed.append("pkgtool")
    if theme.is_dynamic or (theme.music and not theme.music.lower().endswith(".at9")):
        needed.append("ffmpeg")
    if theme.music and not theme.music.lower().endswith(".at9"):
        needed.append("at9tool")

    paths = tools.resolve(settings)
    if options.auto_install and settings.auto_install:
        missing = [
            key for key in needed
            if not {
                "ffmpeg": paths.ffmpeg,
                "pkgtool": paths.pkgtool,
                "at9tool": paths.at9tool,
            }.get(key)
        ]
        if missing:
            reporter(f"Installing missing dependencies: {', '.join(missing)}...", 0.02)
            installed, failures = tools.ensure(needed, settings, reporter)
            for key in installed:
                reporter.detail(f"Installed {tools.LABELS.get(key, key)}.")
            for failure in failures:
                reporter.detail(f"Dependency warning: {failure}")
            paths = tools.resolve(settings)

    media.configure(paths.ffmpeg, paths.ffprobe)
    audio.configure(paths.at9tool)
    return paths


def build(
    project: models.Project,
    options: BuildOptions,
    *,
    settings: Settings | None = None,
    progress: Progress | None = None,
    cancel=None,
    log_sink: Callable[[str], None] | None = None,
) -> BuildResult:
    """Builds the theme described by ``project``."""
    settings = settings or Settings()
    started = time.time()
    log: list[str] = []
    reporter = _Reporter(progress, log, log_sink)
    warnings: list[str] = []

    reporter.check_cancel(cancel)
    reporter("Checking the project...", 0.01)
    errors, project_warnings = models.validate(project)
    warnings += project_warnings
    if errors:
        raise BuildError("Please fix these problems first:\n- " + "\n- ".join(errors))

    theme = project.theme
    paths = _prepare_tools(options, settings, theme, reporter)
    reporter.check_cancel(cancel)

    if theme.is_dynamic and not paths.can_decode:
        raise BuildError(
            "FFmpeg is required for dynamic themes. Install it from the Tools tab."
        )

    reporter("Preparing the build folder...", 0.05)
    build_dir = project.root / C.BUILD_DIR_NAME / _slug(theme.name)
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    work = build_dir / "work"
    content = work / "Image0"
    output = work / "out"
    content.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    fallback_image: Path | None = None
    if theme.is_dynamic:
        video = project.path_for(theme.video)
        if not (theme.background and project.exists(theme.background)):
            reporter("Extracting the cover frame...", 0.08)
            try:
                fallback_image = media.extract_thumbnail(video, work / "cover.png", (1920, 1080))
            except media.MediaError as exc:
                raise BuildError(f"Cannot extract a cover frame from the video: {exc}") from exc

    reporter("Processing images...", 0.10)
    try:
        warnings += images.build_image_assets(
            theme, project, content, fallback_image=fallback_image
        )
    except images.ImageError as exc:
        raise BuildError(str(exc)) from exc
    reporter.check_cancel(cancel)

    music_written = False
    if theme.music:
        reporter("Preparing music...", 0.13)
        music_written = _copy_music(project, content, work, reporter)
    else:
        reporter("No background music selected.", 0.15)

    reporter.check_cancel(cancel)
    if theme.is_dynamic:
        if not paths.can_decode:
            raise BuildError("FFmpeg is required to convert the video.")
        _build_raf(project, content, work, reporter, cancel)
    else:
        reporter("Static theme: no animation to build.", 0.62)

    reporter.check_cancel(cancel)
    reporter("Writing theme.xml...", 0.80)
    try:
        theme_xml.write_theme_xml(
            content / C.THEME_PATH_THEME_XML,
            label=theme.name,
            themecolor=theme.themecolor,
            fontcolor=theme.font_color,
            fontshadowcolor=theme.font_shadow_color,
            focuscolor=theme.focus_color,
            homescreen_dimmer=theme.home_dimmer,
            functionscreen_dimmer=theme.function_dimmer,
            titlename_dimmer=theme.title_dimmer,
            homebgm_enable=music_written,
        )
    except theme_xml.ThemeXmlError as exc:
        raise BuildError(str(exc)) from exc

    reporter("Writing param.sfo...", 0.83)
    try:
        sfo.write_theme_sfo(
            content / C.THEME_PATH_SFO,
            title=theme.name.strip(),
            title_id=theme.title_id,
            content_id=theme.content_id,
            creator=theme.creator.strip(),
            version=theme.version,
        )
    except sfo.SfoError as exc:
        raise BuildError(f"param.sfo: {exc}") from exc

    files = sorted(
        path.relative_to(content).as_posix()
        for path in content.rglob("*")
        if path.is_file()
    )
    if not files:
        raise BuildError("The content folder is empty; nothing to package.")
    reporter.detail(f"Content: {len(files)} files, {sum((content / f).stat().st_size for f in files) / 1048576:.2f} MiB.")

    pkg_path: Path | None = None
    if options.package and paths.pkgtool:
        reporter("Generating the .gp4 project...", 0.86)
        gp4_path = work / "theme.gp4"
        gp4_path.write_text(
            build_gp4(
                content_id=theme.content_id,
                targets=files,
                content_dir_name=content.name,
            ),
            encoding="utf-8",
        )

        reporter("Building the package with PkgTool...", 0.88)
        _run_pkgtool(
            paths.pkgtool,
            ["pkg_build", str(gp4_path), str(output)],
            reporter,
            "pkg_build",
        )
        built = sorted(output.glob("*.pkg"))
        if not built:
            raise BuildError("PkgTool finished but produced no .pkg file.")
        produced = built[0]

        if options.validate_package:
            reporter("Validating the package...", 0.96)
            _run_pkgtool(paths.pkgtool, ["pkg_validate", str(produced)], reporter, "pkg_validate")

        destination_dir = Path(options.output_dir).expanduser()
        destination_dir.mkdir(parents=True, exist_ok=True)
        final_name = f"{_slug(theme.name)}_{theme.mode}.pkg"
        pkg_path = destination_dir / final_name
        shutil.copy2(produced, pkg_path)
        reporter(f"Package created: {pkg_path.name}", 0.99)
    else:
        reason = "disabled" if not options.package else "PkgTool is not installed"
        warnings.append(
            f"No .pkg was created ({reason}). The ready-to-install theme folder "
            f"is at {content}."
        )
        reporter(f"Packaging skipped ({reason}).", 0.95)

    elapsed = time.time() - started
    reporter(f"Build finished in {elapsed:.1f}s.", 1.0)
    return BuildResult(
        content_dir=content,
        build_dir=build_dir,
        pkg_path=pkg_path,
        warnings=warnings,
        log=log,
        seconds=elapsed,
    )


def build_cli(
    project_folder: Path,
    *,
    output_dir: Path | None = None,
    package: bool = True,
    auto_install: bool = False,
) -> BuildResult:
    """Headless entry point used by ``app.py --build``."""
    project = models.Project.load(project_folder)
    settings = Settings.load()
    destination = output_dir or settings.default_output_dir()
    return build(
        project,
        BuildOptions(output_dir=destination, package=package, auto_install=auto_install),
        settings=settings,
        progress=lambda message, fraction: print(f"[{fraction * 100:5.1f}%] {message}"),
    )
