"""Project model, validation and on-disk project format.

A project is a folder with a ``theme.ps4t.json`` file and an ``assets``
folder holding the images, video and music the user picked.  Copying the
folder is therefore enough to move a theme to another machine.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import constants as C

TITLE_ID_RE = re.compile(r"^[A-Z]{4}[0-9]{5}$")
CONTENT_ID_RE = re.compile(r"^[A-Z0-9]{6}-[A-Z0-9]{9}_00-[A-Z0-9]{16}$")
ARGB_RE = re.compile(r"^#[0-9A-Fa-f]{8}$")
VERSION_RE = re.compile(r"^\d{2}\.\d{2}$")


class ProjectError(RuntimeError):
    """The project file is missing or cannot be understood."""


def build_content_id(title_id: str, name: str) -> str:
    """Builds a syntactically valid Content ID from the title and the name."""
    clean = re.sub(r"[^A-Z0-9]", "", (name or "").upper())[:16] or "THEME"
    clean = clean.ljust(16, "0")
    return f"{C.CONTENT_PREFIX}-{title_id}_00-{clean}"


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._")
    return cleaned or "asset"


@dataclass
class ThemeProject:
    """Everything the user can edit about a theme."""

    name: str = "My Theme"
    creator: str = ""
    version: str = C.SFO_VERSION
    title_id: str = C.DEFAULT_TITLE_ID
    content_id: str = ""

    mode: str = "static"  # "static" | "dynamic"

    # Asset paths are relative to the project folder and use forward slashes.
    background: str = ""
    functionscreen: str = ""
    icon: str = ""
    music: str = ""

    video: str = ""
    frame_count: int = C.DEFAULT_FRAME_COUNT
    resolution: str = C.DEFAULT_RESOLUTION
    #: 0 means "derive from the video duration"; otherwise seconds per frame.
    frame_wait: float = 0.0

    themecolor: int = 0
    font_color: str = C.THEME_XML_DEFAULTS["fontcolor"]
    font_shadow_color: str = C.THEME_XML_DEFAULTS["fontshadowcolor"]
    focus_color: str = C.THEME_XML_DEFAULTS["focuscolor"]
    home_dimmer: str = C.THEME_XML_DEFAULTS["homescreen_dimmer"]
    function_dimmer: str = C.THEME_XML_DEFAULTS["functionscreen_dimmer"]
    title_dimmer: str = C.THEME_XML_DEFAULTS["titlename_dimmer"]

    function_icons: dict[str, str] = field(default_factory=dict)
    content_icons: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content_id:
            self.content_id = build_content_id(self.title_id, self.name)

    # -- derived helpers ---------------------------------------------------

    @property
    def is_dynamic(self) -> bool:
        return self.mode == "dynamic"

    @property
    def frame_size(self) -> tuple[int, int]:
        return C.resolution_size(self.resolution)

    @property
    def max_frames(self) -> int:
        return C.max_frames_for(*self.frame_size)

    def icon_for(self, kind: str, name: str) -> str:
        table = self.function_icons if kind == "function" else self.content_icons
        return table.get(name, "")

    def set_icon(self, kind: str, name: str, value: str) -> None:
        table = self.function_icons if kind == "function" else self.content_icons
        if value:
            table[name] = value
        else:
            table.pop(name, None)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ThemeProject":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in (data or {}).items() if k in known}
        for table in ("function_icons", "content_icons"):
            if not isinstance(clean.get(table), dict):
                clean.pop(table, None)
        try:
            clean["frame_count"] = int(clean.get("frame_count", C.DEFAULT_FRAME_COUNT))
        except (TypeError, ValueError):
            clean["frame_count"] = C.DEFAULT_FRAME_COUNT
        try:
            clean["frame_wait"] = float(clean.get("frame_wait", 0.0))
        except (TypeError, ValueError):
            clean["frame_wait"] = 0.0
        try:
            clean["themecolor"] = int(clean.get("themecolor", 0))
        except (TypeError, ValueError):
            clean["themecolor"] = 0
        clean["themecolor"] = min(7, max(0, clean["themecolor"]))
        if clean.get("mode") not in ("static", "dynamic"):
            clean["mode"] = "static"
        if clean.get("resolution") not in C.ANIMATED_SIZES:
            clean["resolution"] = C.DEFAULT_RESOLUTION
        return cls(**clean)


@dataclass
class Project:
    """A :class:`ThemeProject` bound to its folder on disk."""

    root: Path
    theme: ThemeProject

    # -- creation / loading ------------------------------------------------

    @classmethod
    def create(cls, root: Path, theme: ThemeProject | None = None) -> "Project":
        root = Path(root).expanduser().resolve()
        (root / C.ASSETS_DIR_NAME).mkdir(parents=True, exist_ok=True)
        project = cls(root=root, theme=theme or ThemeProject())
        project.save()
        return project

    @classmethod
    def load(cls, root: Path) -> "Project":
        root = Path(root).expanduser().resolve()
        path = root / C.PROJECT_FILE_NAME
        if not path.is_file():
            raise ProjectError(f"No {C.PROJECT_FILE_NAME} found in {root}.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectError(f"Cannot read the project file: {exc}") from exc
        if not isinstance(data, dict):
            raise ProjectError("The project file is not a JSON object.")
        theme = ThemeProject.from_dict(data.get("theme", data))
        return cls(root=root, theme=theme)

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": C.PROJECT_FORMAT,
            "application": C.APP_NAME,
            "theme": self.theme.to_dict(),
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        target = self.root / C.PROJECT_FILE_NAME
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(text + "\n", encoding="utf-8")
        temporary.replace(target)

    # -- assets ------------------------------------------------------------

    def path_for(self, value: str) -> Path | None:
        """Absolute path of an asset, or None when it is unset."""
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else (self.root / path)

    def exists(self, value: str) -> bool:
        path = self.path_for(value)
        return bool(path and path.is_file())

    def import_asset(self, source: Path, category: str) -> str:
        """Copies a file into the project and returns its relative path."""
        source = Path(source)
        if not source.is_file():
            raise ProjectError(f"File not found: {source}")
        folder = self.root / C.ASSETS_DIR_NAME / category
        folder.mkdir(parents=True, exist_ok=True)

        try:
            relative_source = source.resolve().relative_to(self.root)
            return relative_source.as_posix()
        except ValueError:
            pass

        stem = _safe_filename(source.stem)
        suffix = source.suffix.lower()
        candidate = folder / f"{stem}{suffix}"
        counter = 1
        while candidate.exists():
            if candidate.stat().st_size == source.stat().st_size and _digest(candidate) == _digest(source):
                return candidate.relative_to(self.root).as_posix()
            candidate = folder / f"{stem}-{counter}{suffix}"
            counter += 1
        shutil.copy2(source, candidate)
        return candidate.relative_to(self.root).as_posix()

    def clear_asset(self, value: str) -> None:
        """Deletes a copied asset when it is no longer referenced."""
        if not value:
            return
        path = self.path_for(value)
        if not path:
            return
        try:
            relative = path.resolve().relative_to((self.root / C.ASSETS_DIR_NAME).resolve())
        except (ValueError, OSError):
            return
        if relative and path.is_file():
            path.unlink()


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(project: Project) -> tuple[list[str], list[str]]:
    """Checks the project, returning ``(errors, warnings)``.

    Errors stop a build; warnings still produce a package.
    """
    theme = project.theme
    errors: list[str] = []
    warnings: list[str] = []

    name = (theme.name or "").strip()
    if not name:
        errors.append("Theme name cannot be empty.")
    elif len(name.encode("utf-8")) > 127:
        errors.append("Theme name is too long (127 bytes maximum).")

    if theme.creator and len(theme.creator.encode("utf-8")) > 127:
        errors.append("Creator name is too long (127 bytes maximum).")

    if not VERSION_RE.match(theme.version or ""):
        errors.append("Version must look like 01.00.")

    if not TITLE_ID_RE.match(theme.title_id or ""):
        errors.append("Title ID must be 4 letters followed by 5 digits, e.g. CUSA00000.")

    if not CONTENT_ID_RE.match(theme.content_id or ""):
        errors.append(
            "Content ID must look like UP9000-CUSA00000_00-ABCDEFGHIJKLMNOP."
        )
    elif theme.title_id not in theme.content_id:
        errors.append("Content ID must contain the Title ID.")

    if theme.mode not in ("static", "dynamic"):
        errors.append("Theme type must be static or dynamic.")

    if not 0 <= int(theme.themecolor) <= 7:
        errors.append("Theme colour must be between 0 and 7.")

    for field_name, label in (
        ("font_color", "Font colour"),
        ("font_shadow_color", "Font shadow colour"),
        ("focus_color", "Focus colour"),
        ("home_dimmer", "Home dimmer"),
        ("function_dimmer", "Function dimmer"),
        ("title_dimmer", "Title dimmer"),
    ):
        if not ARGB_RE.match(getattr(theme, field_name) or ""):
            errors.append(f"{label} must be #AARRGGBB, e.g. #FF1E9BFF.")

    if theme.mode == "static":
        if not theme.background:
            errors.append("Static themes need a background image.")
        elif not project.exists(theme.background):
            errors.append("The background image is missing from the project folder.")
    else:
        if not theme.video:
            errors.append("Dynamic themes need a source video.")
        elif not project.exists(theme.video):
            errors.append("The source video is missing from the project folder.")
        if theme.resolution not in C.ANIMATED_SIZES:
            errors.append("Unknown dynamic resolution.")
        if not C.MIN_FRAME_COUNT <= int(theme.frame_count) <= theme.max_frames:
            errors.append(
                f"Frame count must be between {C.MIN_FRAME_COUNT} and "
                f"{theme.max_frames} at {theme.resolution}."
            )
        if theme.frame_wait and not (
            C.MIN_WAIT_SECONDS <= float(theme.frame_wait) <= C.MAX_WAIT_SECONDS
        ):
            errors.append(
                f"Seconds per frame must be between {C.MIN_WAIT_SECONDS} and "
                f"{C.MAX_WAIT_SECONDS}, or 0 for automatic."
            )

    if theme.background and not project.exists(theme.background):
        warnings.append("The background image set for previews is missing; it will be skipped.")
    if theme.functionscreen and not project.exists(theme.functionscreen):
        warnings.append("The top-menu background is missing; the main background will be used.")
    if theme.icon and not project.exists(theme.icon):
        warnings.append("The theme icon is missing; one will be derived from the background.")
    if theme.music and not project.exists(theme.music):
        warnings.append("The music file is missing; the theme will be silent.")

    for kind, names, table in (
        ("function", C.FUNCTION_ICONS, theme.function_icons),
        ("content", C.CONTENT_ICONS, theme.content_icons),
    ):
        for icon_name in names:
            value = table.get(icon_name, "")
            if value and not project.exists(value):
                warnings.append(
                    f"The {kind} icon '{C.ICON_LABELS.get(icon_name, icon_name)}' "
                    "is missing; it will be skipped."
                )

    return errors, warnings
