"""User settings, stored in LocalAppData.

Settings are deliberately separate from theme projects: tool locations and
window preferences are machine-specific, while a project folder should keep
working when it is copied to another PC.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import constants as C


@dataclass
class Settings:
    last_project: str = ""
    output_dir: str = ""
    #: Optional manual overrides chosen in the Tools tab.
    ffmpeg: str = ""
    pkgtool: str = ""
    at9tool: str = ""
    auto_install: bool = True
    open_output_after_build: bool = True
    package_as_fpkg: bool = True
    recent_projects: list[str] = field(default_factory=list)

    @classmethod
    def path(cls) -> Path:
        return C.config_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        path = cls.path()
        if not path.is_file():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in raw.items() if k in known}
        if isinstance(clean.get("recent_projects"), list):
            clean["recent_projects"] = [
                str(item) for item in clean["recent_projects"] if isinstance(item, str)
            ]
        else:
            clean.pop("recent_projects", None)
        for key in ("last_project", "output_dir", "ffmpeg", "pkgtool", "at9tool"):
            if key in clean and not isinstance(clean[key], str):
                clean.pop(key)
        for key in ("auto_install", "open_output_after_build", "package_as_fpkg"):
            if key in clean:
                clean[key] = bool(clean[key])
        return cls(**clean)

    def save(self) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def remember_project(self, folder: Path | str) -> None:
        value = str(Path(folder).resolve())
        self.last_project = value
        recent = [item for item in self.recent_projects if item != value]
        recent.insert(0, value)
        self.recent_projects = recent[:8]

    def default_output_dir(self) -> Path:
        if self.output_dir:
            return Path(self.output_dir)
        if self.last_project:
            return Path(self.last_project) / C.DIST_DIR_NAME
        return C.default_projects_dir()
