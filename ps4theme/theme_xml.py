"""Generator for ``theme.xml``, the descriptor the PS4 reads when applying.

The schema comes from a working theme (Sony's own comments are embedded in
it).  Two rules matter:

* ``format-version`` and ``themecolor`` are mandatory.
* Everything else is optional and falls back to a system default.

Without this file the package installs but the console crashes when the theme
is applied, so it is always written.
"""

from __future__ import annotations

import re

FORMAT_VERSION = "4.0"
ARGB_RE = re.compile(r"^#[0-9A-Fa-f]{8}$")
LABEL_RE = re.compile(r"[^A-Za-z0-9_-]+")


class ThemeXmlError(ValueError):
    """An invalid theme.xml setting."""


def sanitize_label(value: str) -> str:
    """The label allows only ``[A-Za-z0-9_-]`` and 64 characters."""
    cleaned = LABEL_RE.sub("-", (value or "").strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned[:64] or "custom-theme"


def _argb(value: str, field: str) -> str:
    if not ARGB_RE.match(value or ""):
        raise ThemeXmlError(
            f"{field} must be an 8-digit ARGB colour such as #FF1E9BFF (got {value!r})."
        )
    return value.upper()


def build_theme_xml(
    *,
    label: str,
    themecolor: int = 0,
    fontcolor: str = "#FFFFFFFF",
    fontshadowcolor: str = "#FF000000",
    focuscolor: str = "#FF1E9BFF",
    homescreen_dimmer: str = "#00FFFFFF",
    functionscreen_dimmer: str = "#00FFFFFF",
    titlename_dimmer: str = "#00FFFFFF",
    homebgm_enable: bool = False,
) -> str:
    """Builds the XML text.

    ``homebgm_enable`` should only be True when ``sound/bgm_home.at9`` is
    actually present; otherwise the console plays the system music instead of
    silence.
    """
    try:
        colour = int(themecolor)
    except (TypeError, ValueError) as exc:
        raise ThemeXmlError(f"themecolor must be a number from 0 to 7, got {themecolor!r}.") from exc
    if not 0 <= colour <= 7:
        raise ThemeXmlError(f"themecolor must be between 0 and 7, got {colour}.")

    rows = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<theme>",
        f"    <format-version>{FORMAT_VERSION}</format-version>",
        f"    <themecolor>{colour}</themecolor>",
        f"    <label>{sanitize_label(label)}</label>",
        f"    <fontcolor>{_argb(fontcolor, 'fontcolor')}</fontcolor>",
        f"    <fontshadowcolor>{_argb(fontshadowcolor, 'fontshadowcolor')}</fontshadowcolor>",
        f"    <focuscolor>{_argb(focuscolor, 'focuscolor')}</focuscolor>",
        f"    <homescreen-dimmer>{_argb(homescreen_dimmer, 'homescreen-dimmer')}</homescreen-dimmer>",
        f"    <functionscreen-dimmer>{_argb(functionscreen_dimmer, 'functionscreen-dimmer')}</functionscreen-dimmer>",
        f"    <titlename-dimmer>{_argb(titlename_dimmer, 'titlename-dimmer')}</titlename-dimmer>",
        f"    <homebgm-enable>{'True' if homebgm_enable else 'False'}</homebgm-enable>",
        "</theme>",
        "",
    ]
    return "\n".join(rows)


def write_theme_xml(path, **kwargs):
    from pathlib import Path

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_theme_xml(**kwargs), encoding="utf-8")
    return path
