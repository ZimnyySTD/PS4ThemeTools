"""Hand-written ``.gp4`` project file for PkgTool / orbis packaging.

``.gp4`` is plain XML.  Generating it directly avoids calling a tool once per
file (a 48-frame theme has 80+ files).  The structure is the one the official
tools emit for a ``pkg_ps4_theme`` volume:

* ``volume_type`` is ``pkg_ps4_theme``.
* ``IRO_TAG=2`` in param.sfo is what makes the console treat it as a theme.
* Themes carry no chunk info and no storage type.
"""

from __future__ import annotations

import time
from pathlib import Path


class Gp4Error(ValueError):
    """Invalid file list for the project file."""


def _escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _validate_target(target: str) -> str:
    raw = str(target or "")
    if raw.startswith(("/", "\\")) or (len(raw) > 1 and raw[1] == ":"):
        raise Gp4Error(f"Absolute paths are not allowed: {target!r}")
    cleaned = raw.replace("\\", "/").strip("/")
    if not cleaned:
        raise Gp4Error("An empty file path cannot be packaged.")
    if ":" in cleaned:
        raise Gp4Error(f"Absolute paths are not allowed: {target!r}")
    parts = cleaned.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise Gp4Error(f"Invalid path component in {target!r}")
        if any(ch in part for ch in '<>:"|?*'):
            raise Gp4Error(f"Invalid character in {target!r}")
    return "/".join(parts)


def build_gp4(
    *,
    content_id: str,
    targets: list[str] | str,
    content_dir_name: str = "Image0",
    volume_ts: str | None = None,
) -> str:
    """Builds the ``psproject`` XML for a theme package."""
    if isinstance(targets, str):
        raise Gp4Error("targets must be a list of relative paths.")
    files = sorted(_validate_target(target) for target in targets)
    if not files:
        raise Gp4Error("There is nothing to package.")

    directory_tree: dict[str, dict] = {}
    for target in files:
        node = directory_tree
        for part in target.split("/")[:-1]:
            node = node.setdefault(part, {})

    def render(node: dict[str, dict], indent: int) -> list[str]:
        lines: list[str] = []
        pad = " " * indent
        for name, children in node.items():
            if children:
                lines.append(f'{pad}<dir targ_name="{_escape(name)}">')
                lines += render(children, indent + 2)
                lines.append(f"{pad}</dir>")
            else:
                lines.append(f'{pad}<dir targ_name="{_escape(name)}"/>')
        return lines

    file_lines = [
        f'    <file targ_path="{_escape(target)}" '
        f'orig_path="{_escape(content_dir_name)}\\{_escape(target.replace("/", chr(92)))}"/>'
        for target in files
    ]
    stamp = volume_ts or time.strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
        '<psproject fmt="gp4" version="1000">',
        "  <volume>",
        "    <volume_type>pkg_ps4_theme</volume_type>",
        "    <volume_id></volume_id>",
        f"    <volume_ts>{stamp}</volume_ts>",
        f'    <package content_id="{_escape(content_id)}" passcode="{"0" * 32}"/>',
        "  </volume>",
        '  <files img_no="0">',
        *file_lines,
        "  </files>",
        "  <rootdir>",
        *render(directory_tree, 4),
        "  </rootdir>",
        "</psproject>",
        "",
    ]
    return "\n".join(lines)


def write_gp4(path: Path, **kwargs) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_gp4(**kwargs), encoding="utf-8")
    return path
