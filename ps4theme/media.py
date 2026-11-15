"""FFmpeg / ffprobe layer.

Every video or audio conversion happens here.  Two rules are applied
consistently:

* Scaling fills the target frame (``force_original_aspect_ratio=increase``
  followed by a centred crop), so images are never distorted and never get
  letterboxed.
* The extraction rate is derived from the real duration reported by ffprobe,
  never from a guessed value, so exactly the requested number of frames is
  produced.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_FFMPEG: Path | None = None
_FFPROBE: Path | None = None


class MediaError(RuntimeError):
    """ffmpeg failed; the message carries the useful part of stderr."""


def configure(ffmpeg: Path | str | None, ffprobe: Path | str | None = None) -> None:
    """Sets the binaries resolved by the dependency manager."""
    global _FFMPEG, _FFPROBE
    _FFMPEG = Path(ffmpeg) if ffmpeg else None
    _FFPROBE = Path(ffprobe) if ffprobe else None


def _which(name: str) -> Path | None:
    found = shutil.which(name)
    return Path(found) if found else None


def ffmpeg_path() -> Path | None:
    if _FFMPEG and _FFMPEG.is_file():
        return _FFMPEG
    return _which("ffmpeg")


def ffprobe_path() -> Path | None:
    if _FFPROBE and _FFPROBE.is_file():
        return _FFPROBE
    return _which("ffprobe")


def available() -> bool:
    return ffmpeg_path() is not None and ffprobe_path() is not None


def require_tools() -> tuple[Path, Path]:
    ffmpeg, ffprobe = ffmpeg_path(), ffprobe_path()
    if ffmpeg is None or ffprobe is None:
        raise MediaError(
            "FFmpeg is not available. Open the Tools tab and install it, or put "
            "ffmpeg.exe and ffprobe.exe on the PATH."
        )
    return ffmpeg, ffprobe


def version() -> str | None:
    ffmpeg = ffmpeg_path()
    if ffmpeg is None:
        return None
    try:
        proc = subprocess.run(
            [str(ffmpeg), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    first = proc.stdout.decode("utf-8", "replace").splitlines()[0] if proc.stdout else ""
    return first.replace("ffmpeg version ", "").split(" Copyright")[0].strip() or None


def _run(cmd: list[str], *, capture_stdout: bool = False, timeout: int = 900) -> bytes:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=NO_WINDOW,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"{Path(cmd[0]).name} timed out.") from exc
    except OSError as exc:
        raise MediaError(f"Cannot run {cmd[0]}: {exc}") from exc
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-8:]
        raise MediaError("\n".join(tail) or f"{Path(cmd[0]).name} exited with {proc.returncode}.")
    return proc.stdout or b""


def scale_crop_filter(width: int, height: int) -> str:
    """Fills exactly WxH without distortion."""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={width}:{height},setsar=1"
    )


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    frame_count: int | None


def _fraction(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        numerator, denominator = value.split("/")
        denominator_f = float(denominator)
        return float(numerator) / denominator_f if denominator_f else 0.0
    except (ValueError, ZeroDivisionError):
        try:
            return float(value)
        except ValueError:
            return 0.0


def probe(path: Path) -> VideoInfo:
    """Reads duration, geometry and frame rate of the first video stream."""
    _ffmpeg, ffprobe = require_tools()
    output = _run(
        [
            str(ffprobe), "-v", "error", "-select_streams", "v:0",
            "-show_entries",
            "stream=width,height,duration,nb_frames,avg_frame_rate,r_frame_rate,codec_name:format=duration",
            "-of", "json", str(path),
        ],
        capture_stdout=True,
        timeout=120,
    )
    try:
        data = json.loads(output or b"{}")
    except json.JSONDecodeError as exc:
        raise MediaError("ffprobe returned invalid JSON.") from exc
    streams = data.get("streams") or []
    if not streams:
        raise MediaError("This file has no video stream.")
    stream = streams[0]

    def as_float(value) -> float:
        try:
            result = float(value)
            return result if result > 0 else 0.0
        except (TypeError, ValueError):
            return 0.0

    duration = as_float((data.get("format") or {}).get("duration")) or as_float(stream.get("duration"))
    frame_count: int | None = None
    try:
        frame_count = int(stream["nb_frames"])
    except (KeyError, TypeError, ValueError):
        frame_count = None

    fps = _fraction(stream.get("avg_frame_rate")) or _fraction(stream.get("r_frame_rate"))

    if not duration and frame_count and fps:
        duration = frame_count / fps
    if not duration:
        # Last resort: count packets.  Only happens with unusual containers.
        counted = _run(
            [
                str(ffprobe), "-v", "error", "-select_streams", "v:0",
                "-count_packets",
                "-show_entries", "stream=nb_read_packets,avg_frame_rate",
                "-of", "json", str(path),
            ],
            capture_stdout=True,
            timeout=120,
        )
        info = (json.loads(counted or b"{}").get("streams") or [{}])[0]
        try:
            frame_count = frame_count or int(info.get("nb_read_packets") or 0) or None
        except (TypeError, ValueError):
            pass
        fps = fps or _fraction(info.get("avg_frame_rate"))
        if frame_count and fps:
            duration = frame_count / fps
    if not duration:
        raise MediaError("Could not determine the duration of this file.")

    return VideoInfo(
        duration=duration,
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        fps=fps,
        codec=str(stream.get("codec_name") or "?"),
        frame_count=frame_count,
    )


def extraction_fps(frame_count: int, duration: float) -> float:
    """Rate that yields exactly ``frame_count`` samples over ``duration``."""
    if frame_count < 1:
        raise ValueError("frame_count must be >= 1")
    if duration <= 0:
        raise ValueError("duration must be > 0")
    return frame_count / duration


def extract_thumbnail(source: Path, dest: Path, size: tuple[int, int], *, at: float = 0.0) -> Path:
    """Writes one PNG frame, used for the video preview in the UI."""
    ffmpeg, _ = require_tools()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    args = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y"]
    if at > 0:
        args += ["-ss", f"{at:.3f}"]
    args += [
        "-i", str(source),
        "-vf", scale_crop_filter(width, height),
        "-frames:v", "1",
        "-pix_fmt", "rgba",
        str(dest),
    ]
    _run(args, timeout=120)
    if not dest.is_file():
        raise MediaError("FFmpeg produced no preview frame.")
    return dest


def _read_exact(stream, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            break
        chunks += chunk
    return bytes(chunks)


def iter_frames(source: Path, count: int, size: tuple[int, int], duration: float):
    """Yields ``count`` RGBA frames as NumPy arrays.

    The frames come straight from ffmpeg's stdout: at 1280x720 each one is
    3.5 MiB, and there is never more than one in memory.
    """
    ffmpeg, _ = require_tools()
    width, height = size
    frame_bytes = width * height * 4
    fps = extraction_fps(count, duration)
    cmd = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-vf", f"fps={fps:.9f},{scale_crop_filter(width, height)}",
        "-frames:v", str(count),
        "-fps_mode", "passthrough",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-",
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW
    )
    assert proc.stdout is not None
    emitted = 0
    last: np.ndarray | None = None
    stderr = b""
    try:
        while emitted < count:
            buffer = _read_exact(proc.stdout, frame_bytes)
            if len(buffer) < frame_bytes:
                break
            last = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
            emitted += 1
            yield last
    finally:
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            stderr = proc.stderr.read()
            proc.stderr.close()
        proc.wait()

    if emitted == 0:
        tail = stderr.decode("utf-8", "replace").strip().splitlines()[-8:]
        raise MediaError("\n".join(tail) or "FFmpeg decoded no frames.")

    # Containers sometimes report a slightly longer duration than their last
    # decodable frame.  Repeat the last one so the scene matches the files.
    while emitted < count and last is not None:
        emitted += 1
        yield last


@dataclass(frozen=True)
class AudioInfo:
    codec: str
    rate: int
    channels: int
    duration: float


def probe_audio(path: Path) -> AudioInfo:
    _ffmpeg, ffprobe = require_tools()
    output = _run(
        [
            str(ffprobe), "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels,duration",
            "-of", "json", str(path),
        ],
        capture_stdout=True,
        timeout=120,
    )
    streams = (json.loads(output or b"{}").get("streams") or [])
    if not streams:
        raise MediaError("This file has no audio stream.")
    stream = streams[0]

    def number(key: str, cast=int) -> float:
        try:
            return cast(stream.get(key))
        except (TypeError, ValueError):
            return 0

    return AudioInfo(
        codec=str(stream.get("codec_name") or "?"),
        rate=int(number("sample_rate")),
        channels=int(number("channels")),
        duration=float(number("duration", float)),
    )


def to_wav(source: Path, dest: Path, rate: int = 48000, *,
           max_seconds: float | None = None) -> Path:
    """Converts any audio to 16-bit stereo PCM WAV, which at9tool accepts."""
    ffmpeg, _ = require_tools()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
    if max_seconds:
        args += ["-t", f"{max_seconds:g}"]
    args += ["-c:a", "pcm_s16le", "-ac", "2", "-ar", str(rate), str(dest)]
    _run(args, timeout=1800)
    if not dest.is_file():
        raise MediaError("FFmpeg produced no intermediate WAV.")
    return dest
