"""ATRAC9 (.at9) encoding through Sony's ``at9tool``.

ATRAC9 is proprietary: FFmpeg decodes it but cannot encode it.  The official
``ps4_at9tool.exe`` is downloaded on demand from the ATRACTool-Reloaded
portable release (MIT wrapper, Sony's original PS4 converter inside).  It is
deliberately not committed to this repository.

The command line was verified against a theme that plays on a console:

    ps4_at9tool -e -br 144 -fs 48000 -wholeloop input.wav output.at9

144 kbps / 48 kHz produces block align 384 and the config bytes a PS4 theme
uses for ``sound/bgm_home.at9``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import constants as C
from .media import NO_WINDOW, MediaError

DEFAULT_BITRATE = 144
SAMPLE_RATE = 48000
TOOL_NAMES = ("ps4_at9tool.exe", "at9tool.exe")

_CONFIGURED: Path | None = None


class AudioError(MediaError):
    """ATRAC9 conversion failed."""


def configure(path: Path | str | None) -> None:
    global _CONFIGURED
    _CONFIGURED = Path(path) if path else None


def find_tool() -> Path | None:
    """Looks in the configured path, ``tools/``, its ``ext`` folder and PATH."""
    if _CONFIGURED and _CONFIGURED.is_file():
        return _CONFIGURED
    roots = [C.tools_dir(), C.tools_dir() / "at9tool", C.tools_dir() / "pkgtool" / "ext"]
    for folder in roots:
        for name in TOOL_NAMES:
            candidate = folder / name
            if candidate.is_file():
                return candidate
    for name in TOOL_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def available() -> bool:
    return find_tool() is not None


def encode(wav_path: Path, dest: Path, bitrate: int = DEFAULT_BITRATE) -> Path:
    """Encodes a PCM WAV to .at9.  Requires at9tool, otherwise raises."""
    tool = find_tool()
    if tool is None:
        raise AudioError(
            "at9tool was not found. Install it from the Tools tab to convert "
            "music automatically, or provide an .at9 file directly."
        )
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    try:
        proc = subprocess.run(
            [
                str(tool), "-e",
                "-br", str(bitrate),
                "-fs", str(SAMPLE_RATE),
                # Menu music loops forever: writes the smpl chunk with
                # playCount=0, which is what a theme's BGM needs.
                "-wholeloop",
                str(wav_path), str(dest),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=1800,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioError(f"at9tool failed to run: {exc}") from exc

    if not dest.is_file() or dest.stat().st_size == 0:
        tail = proc.stdout.decode("utf-8", "replace").strip().splitlines()[-6:]
        raise AudioError("at9tool produced no file: " + ("\n".join(tail) or "no output"))
    return dest


def is_at9(path: Path) -> bool:
    """Cheap container check for a Sony ``.at9`` file.

    The codec is stored as an extensible WAVE GUID, not as the text
    ``atrac9``, so the RIFF/WAVE header plus the extension is the reliable
    test here; ffprobe validates the actual codec during a build.
    """
    path = Path(path)
    if path.suffix.lower() != ".at9":
        return False
    try:
        with path.open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return False
    return len(header) == 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE"
