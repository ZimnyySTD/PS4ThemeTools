"""Dependency detection, download and installation.

Three external tools are used:

* **FFmpeg** - video/audio decoding.  Official BtbN builds, verified against
  the release's ``checksums.sha256``.
* **PkgTool** - LibOrbisPkg 0.2.231, turns the content folder into a fake
  ``.pkg``.  Pinned URL and SHA-256.
* **at9tool** - Sony's ATRAC9 encoder, extracted from the ATRACTool-Reloaded
  portable release.  Optional (only needed for custom music).

Downloads are written to ``tools/`` in a source checkout and to
``%LOCALAPPDATA%\\PS4ThemeTools\\tools`` in a frozen build.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from . import constants as C
from .settings import Settings

Progress = Callable[[str, float], None]
USER_AGENT = f"{C.APP_NAME}/{C.APP_VERSION} (+https://github.com/)"

FFMPEG_DIR_NAME = "ffmpeg"
PKGTOOL_DIR_NAME = "pkgtool"
AT9TOOL_DIR_NAME = "at9tool"


class ToolError(RuntimeError):
    """A dependency is missing or could not be installed."""


@dataclass(frozen=True)
class ToolPaths:
    ffmpeg: Path | None = None
    ffprobe: Path | None = None
    pkgtool: Path | None = None
    at9tool: Path | None = None

    @property
    def can_decode(self) -> bool:
        return bool(self.ffmpeg and self.ffprobe)

    @property
    def can_package(self) -> bool:
        return self.pkgtool is not None


@dataclass(frozen=True)
class ToolInfo:
    key: str
    label: str
    description: str
    path: Path | None
    version: str
    optional: bool
    install_size: str

    @property
    def found(self) -> bool:
        return self.path is not None


def pkgtool_folder() -> Path:
    return C.tools_dir() / PKGTOOL_DIR_NAME


def at9tool_folder() -> Path:
    return C.tools_dir() / AT9TOOL_DIR_NAME


def ffmpeg_folder() -> Path:
    return C.tools_dir() / FFMPEG_DIR_NAME


def _first_file(candidates: list[Path | None]) -> Path | None:
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def _which(name: str) -> Path | None:
    found = shutil.which(name)
    return Path(found) if found else None


def resolve(settings: Settings | None = None) -> ToolPaths:
    """Locates every tool following settings -> tools folder -> PATH."""
    settings = settings or Settings()
    tools = C.tools_dir()

    ffmpeg_candidates: list[Path | None] = []
    if settings.ffmpeg:
        override = Path(settings.ffmpeg).expanduser()
        ffmpeg_candidates += [override, override / "ffmpeg.exe", override / "bin" / "ffmpeg.exe"]
    ffmpeg_candidates += [
        ffmpeg_folder() / "bin" / "ffmpeg.exe",
        ffmpeg_folder() / "ffmpeg.exe",
        tools / "ffmpeg.exe",
        _which("ffmpeg"),
    ]
    ffmpeg = _first_file(ffmpeg_candidates)

    ffprobe_candidates: list[Path | None] = []
    if ffmpeg:
        ffprobe_candidates.append(ffmpeg.with_name("ffprobe.exe"))
    if settings.ffmpeg:
        override = Path(settings.ffmpeg).expanduser()
        ffprobe_candidates += [override.with_name("ffprobe.exe"), override / "ffprobe.exe"]
    ffprobe_candidates += [
        ffmpeg_folder() / "bin" / "ffprobe.exe",
        ffmpeg_folder() / "ffprobe.exe",
        tools / "ffprobe.exe",
        _which("ffprobe"),
    ]
    ffprobe = _first_file(ffprobe_candidates)

    pkgtool_candidates: list[Path | None] = []
    if settings.pkgtool:
        override = Path(settings.pkgtool).expanduser()
        pkgtool_candidates += [override, override / "PkgTool.exe"]
    pkgtool_candidates += [
        pkgtool_folder() / "PkgTool.exe",
        tools / "PkgTool.exe",
        _which("PkgTool.exe"),
    ]
    pkgtool = _first_file(pkgtool_candidates)

    at9_candidates: list[Path | None] = []
    if settings.at9tool:
        override = Path(settings.at9tool).expanduser()
        at9_candidates += [override, override / "ps4_at9tool.exe"]
    at9_candidates += [
        at9tool_folder() / "ps4_at9tool.exe",
        at9tool_folder() / "at9tool.exe",
        tools / "ps4_at9tool.exe",
        tools / "at9tool.exe",
        pkgtool_folder() / "ext" / "ps4_at9tool.exe",
        _which("ps4_at9tool.exe"),
        _which("at9tool.exe"),
    ]
    at9tool = _first_file(at9_candidates)

    return ToolPaths(ffmpeg=ffmpeg, ffprobe=ffprobe, pkgtool=pkgtool, at9tool=at9tool)


def check(settings: Settings | None = None) -> list[ToolInfo]:
    paths = resolve(settings)
    from . import media

    ffmpeg_version = ""
    if paths.ffmpeg:
        media.configure(paths.ffmpeg, paths.ffprobe)
        ffmpeg_version = media.version() or "installed"
    return [
        ToolInfo(
            "ffmpeg", "FFmpeg",
            "Decodes video and audio, extracts animation frames and converts music.",
            paths.ffmpeg, ffmpeg_version or "not installed", False, "~80 MB",
        ),
        ToolInfo(
            "pkgtool", "PkgTool (LibOrbisPkg)",
            "Builds the final fake .pkg from the generated theme folder.",
            paths.pkgtool, "v0.2.231" if paths.pkgtool else "not installed", False, "84 KB",
        ),
        ToolInfo(
            "at9tool", "at9tool (ATRAC9)",
            "Encodes background music to .at9. Optional: themes work without music.",
            paths.at9tool, "installed" if paths.at9tool else "not installed", True, "25 MB",
        ),
    ]


# --- download helpers -----------------------------------------------------

def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})


def _fetch(url: str, timeout: int = 60) -> bytes:
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as exc:
        raise ToolError(f"Could not reach {url}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(
    url: str,
    destination: Path,
    *,
    progress: Progress | None = None,
    expected_sha256: str | None = None,
) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    if temporary.exists():
        temporary.unlink()

    if progress:
        progress(f"Downloading {destination.name}...", -1.0)

    try:
        with urllib.request.urlopen(_request(url), timeout=90) as response:
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            with temporary.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    if progress:
                        if total:
                            progress(
                                f"Downloading {destination.name} "
                                f"({received / 1048576:.1f} / {total / 1048576:.1f} MB)",
                                received / total,
                            )
                        else:
                            progress(
                                f"Downloading {destination.name} "
                                f"({received / 1048576:.1f} MB)",
                                -1.0,
                            )
    except (urllib.error.URLError, OSError) as exc:
        if temporary.exists():
            temporary.unlink()
        raise ToolError(f"Download failed: {exc}") from exc

    if expected_sha256:
        if progress:
            progress("Verifying SHA-256...", -1.0)
        actual = _sha256(temporary)
        if actual.lower() != expected_sha256.lower():
            temporary.unlink()
            raise ToolError(
                "The downloaded file did not match its SHA-256 checksum. "
                "The download was discarded; please try again."
            )
    temporary.replace(destination)
    return destination


def _checksum_for(text: str, filename: str) -> str | None:
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            candidate = parts[-1].lstrip("*")
            if candidate == filename:
                return parts[0]
    return None


def _safe_extract(zip_file: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for info in zip_file.infolist():
        if info.is_dir():
            continue
        member = PurePosixPath(info.filename)
        if member.is_absolute() or ".." in member.parts:
            continue
        target = destination.joinpath(*member.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zip_file.open(info) as source, target.open("wb") as handle:
            shutil.copyfileobj(source, handle)


def _run_version(exe: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            [str(exe), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.decode("utf-8", "replace").strip()


def _replace_folder(temporary: Path, final: Path) -> None:
    if final.exists():
        shutil.rmtree(final, ignore_errors=True)
    temporary.replace(final)


# --- FFmpeg ---------------------------------------------------------------

_FFMPEG_FALLBACKS = (
    "https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-n9.0-latest-win64-lgpl-shared-9.0.zip",
    "https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-n8.1-latest-win64-lgpl-shared-8.1.zip",
    "https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl-shared.zip",
)


def _ffmpeg_asset() -> tuple[str, str | None]:
    """Returns (asset URL, expected SHA-256 or None)."""
    checksums = ""
    try:
        payload = json.loads(_fetch(C.FFMPEG_RELEASE_API, timeout=40) or b"{}")
        assets = {
            asset["name"]: asset["browser_download_url"]
            for asset in payload.get("assets", [])
            if asset.get("name") and asset.get("browser_download_url")
        }
        checksum_url = assets.get("checksums.sha256")
        if checksum_url:
            checksums = _fetch(checksum_url, timeout=40).decode("utf-8", "replace")
        for pattern in C.FFMPEG_ASSET_PATTERNS:
            for name, url in assets.items():
                if re.match(pattern, name):
                    return url, _checksum_for(checksums, name)
    except (ToolError, json.JSONDecodeError, KeyError):
        pass

    # API blocked or rate limited: use the release's direct URLs and try to
    # fetch the checksum file separately.
    try:
        checksum_url = (
            "https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/"
            "latest/checksums.sha256"
        )
        checksums = _fetch(checksum_url, timeout=40).decode("utf-8", "replace")
    except ToolError:
        checksums = ""
    for url in _FFMPEG_FALLBACKS:
        name = url.rsplit("/", 1)[-1]
        digest = _checksum_for(checksums, name)
        if digest:
            return url, digest
    return _FFMPEG_FALLBACKS[0], None


def install_ffmpeg(progress: Progress | None = None) -> Path:
    if progress:
        progress("Looking up the latest FFmpeg build...", -1.0)
    url, digest = _ffmpeg_asset()
    downloads = C.tools_dir() / "downloads"
    archive = downloads / url.rsplit("/", 1)[-1]
    _download(url, archive, progress=progress, expected_sha256=digest)

    if progress:
        progress("Extracting FFmpeg...", -1.0)
    final = ffmpeg_folder()
    temporary = final.with_name(final.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    (temporary / "bin").mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as bundle:
            found_exe = False
            for info in bundle.infolist():
                parts = PurePosixPath(info.filename).parts
                if len(parts) < 2 or parts[-2].lower() != "bin":
                    continue
                name = parts[-1].lower()
                if not (name.endswith(".exe") or name.endswith(".dll")):
                    continue
                if name == "ffplay.exe":
                    continue
                with bundle.open(info) as source, (temporary / "bin" / parts[-1]).open("wb") as handle:
                    shutil.copyfileobj(source, handle)
                if name == "ffmpeg.exe":
                    found_exe = True
        if not found_exe:
            raise ToolError("The FFmpeg archive did not contain bin/ffmpeg.exe.")
        _replace_folder(temporary, final)
    except (zipfile.BadZipFile, OSError) as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ToolError(f"Could not extract FFmpeg: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)

    exe = final / "bin" / "ffmpeg.exe"
    probe = final / "bin" / "ffprobe.exe"
    if not probe.is_file():
        raise ToolError("The FFmpeg archive did not contain bin/ffprobe.exe.")
    if "ffmpeg version" not in _run_version(exe, "-version").lower():
        raise ToolError("FFmpeg was extracted but does not run on this PC.")
    if progress:
        progress("FFmpeg installed.", 1.0)
    return exe


# --- PkgTool --------------------------------------------------------------

def install_pkgtool(progress: Progress | None = None) -> Path:
    downloads = C.tools_dir() / "downloads"
    archive = downloads / "PkgTool-0.2.231.zip"
    _download(C.PKGTOOL_URL, archive, progress=progress, expected_sha256=C.PKGTOOL_SHA256)

    if progress:
        progress("Extracting PkgTool...", -1.0)
    final = pkgtool_folder()
    temporary = final.with_name(final.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as bundle:
            _safe_extract(bundle, temporary)
        exe = temporary / "PkgTool.exe"
        if not exe.is_file():
            raise ToolError("The PkgTool archive did not contain PkgTool.exe.")
        _replace_folder(temporary, final)
    except (zipfile.BadZipFile, OSError) as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ToolError(f"Could not extract PkgTool: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)

    if progress:
        progress("PkgTool installed.", 1.0)
    return final / "PkgTool.exe"


# --- at9tool --------------------------------------------------------------

def install_at9tool(progress: Progress | None = None) -> Path:
    downloads = C.tools_dir() / "downloads"
    archive = downloads / "ATRACTool-Rel-Portable.zip"
    _download(C.AT9TOOL_URL, archive, progress=progress, expected_sha256=C.AT9TOOL_SHA256)

    if progress:
        progress("Extracting ps4_at9tool.exe...", -1.0)
    final = at9tool_folder()
    temporary = final.with_name(final.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as bundle:
            try:
                member = bundle.getinfo(C.AT9TOOL_MEMBER)
            except KeyError as exc:
                raise ToolError("The archive did not contain ps4_at9tool.exe.") from exc
            target = temporary / "ps4_at9tool.exe"
            with bundle.open(member) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)
            target.chmod(0o755)
        _replace_folder(temporary, final)
    except (zipfile.BadZipFile, OSError) as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ToolError(f"Could not extract at9tool: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)

    if progress:
        progress("at9tool installed.", 1.0)
    return final / "ps4_at9tool.exe"


# --- high level -----------------------------------------------------------

INSTALLERS = {
    "ffmpeg": install_ffmpeg,
    "pkgtool": install_pkgtool,
    "at9tool": install_at9tool,
}

LABELS = {"ffmpeg": "FFmpeg", "pkgtool": "PkgTool", "at9tool": "at9tool"}


def install(key: str, progress: Progress | None = None) -> Path:
    try:
        installer = INSTALLERS[key]
    except KeyError as exc:
        raise ToolError(f"Unknown dependency: {key}") from exc
    return installer(progress)


def needed_for(theme) -> list[str]:
    """Tools that a build of this project can make use of."""
    keys = ["pkgtool"]
    needs_conversion = bool(theme.music) and not theme.music.lower().endswith(".at9")
    if theme.is_dynamic or needs_conversion:
        keys.append("ffmpeg")
    if needs_conversion:
        keys.append("at9tool")
    return keys


def ensure(
    keys: list[str],
    settings: Settings | None = None,
    progress: Progress | None = None,
) -> tuple[list[str], list[str]]:
    """Installs missing tools, returning ``(installed, failures)``.

    Failures never raise: a static theme can still be produced without a
    package, and the caller shows the reason as a warning.
    """
    settings = settings or Settings()
    paths = resolve(settings)
    current = {
        "ffmpeg": paths.ffmpeg,
        "pkgtool": paths.pkgtool,
        "at9tool": paths.at9tool,
    }
    installed: list[str] = []
    failures: list[str] = []
    for key in keys:
        if current.get(key):
            continue
        try:
            install(key, progress)
            installed.append(key)
        except ToolError as exc:
            failures.append(f"{LABELS.get(key, key)}: {exc}")
    return installed, failures


def status_text(settings: Settings | None = None) -> str:
    paths = resolve(settings)
    missing = [
        label for label, path in (
            ("FFmpeg", paths.ffmpeg),
            ("PkgTool", paths.pkgtool),
            ("at9tool", paths.at9tool),
        ) if path is None
    ]
    if not missing:
        return "All tools ready"
    return "Missing: " + ", ".join(missing)


def clear_download_cache() -> None:
    downloads = C.tools_dir() / "downloads"
    if downloads.is_dir():
        shutil.rmtree(downloads, ignore_errors=True)


def _debug_paths() -> dict[str, str]:
    """Small helper used by ``app.py --self-test``."""
    paths = resolve()
    return {
        "ffmpeg": str(paths.ffmpeg or ""),
        "pkgtool": str(paths.pkgtool or ""),
        "at9tool": str(paths.at9tool or ""),
        "tools_dir": str(C.tools_dir()),
    }


def remove(key: str) -> None:
    """Deletes an installed dependency (used by the Tools tab)."""
    folders = {
        "ffmpeg": ffmpeg_folder(),
        "pkgtool": pkgtool_folder(),
        "at9tool": at9tool_folder(),
    }
    folder = folders.get(key)
    if folder and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


def open_folder(path: Path) -> None:
    """Opens a folder in Explorer (UI convenience)."""
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])
