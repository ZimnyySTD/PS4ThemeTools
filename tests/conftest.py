"""Shared fixtures for the PS4 Theme Tools test-suite."""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ps4theme import media, models  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep settings and generated projects out of the real user profile."""
    monkeypatch.setenv("PS4THEME_CONFIG_DIR", str(tmp_path / "config"))
    yield


@pytest.fixture(scope="session")
def ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        pytest.skip("FFmpeg is not on PATH")
    return path


@pytest.fixture
def background(tmp_path: Path) -> Path:
    image = Image.new("RGB", (1920, 1080), (12, 40, 90))
    draw = ImageDraw.Draw(image)
    draw.ellipse((520, 180, 1400, 900), fill=(30, 140, 210))
    draw.rectangle((80, 80, 360, 200), fill=(6, 182, 212))
    path = tmp_path / "background.png"
    image.save(path)
    return path


@pytest.fixture
def icon(tmp_path: Path) -> Path:
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, 240, 240), radius=60, fill=(37, 99, 235, 255))
    draw.ellipse((80, 80, 176, 176), fill=(255, 255, 255, 255))
    path = tmp_path / "icon.png"
    image.save(path)
    return path


@pytest.fixture
def music(tmp_path: Path) -> Path:
    """One second of a quiet 48 kHz stereo tone."""
    path = tmp_path / "music.wav"
    frames = bytearray()
    for index in range(48_000):
        value = int(6_000 * ((index % 96) / 96 - 0.5) * 2)
        frames += struct.pack("<hh", value, value)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(48_000)
        handle.writeframes(bytes(frames))
    return path


@pytest.fixture
def video(tmp_path: Path, ffmpeg: str) -> Path:
    path = tmp_path / "clip.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=24",
            "-t", "2", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
        timeout=120,
    )
    return path


@pytest.fixture
def static_project(tmp_path: Path, background: Path) -> models.Project:
    project = models.Project.create(tmp_path / "Static Theme")
    project.theme.name = "Static Test Theme"
    project.theme.creator = "Test Runner"
    project.theme.title_id = "CUSA01234"
    project.theme.content_id = models.build_content_id("CUSA01234", "Static Test Theme")
    project.theme.background = project.import_asset(background, "images")
    project.save()
    return project


@pytest.fixture
def dynamic_project(tmp_path: Path, video: Path) -> models.Project:
    project = models.Project.create(tmp_path / "Dynamic Theme")
    project.theme.name = "Dynamic Test Theme"
    project.theme.mode = "dynamic"
    project.theme.title_id = "CUSA05678"
    project.theme.content_id = models.build_content_id("CUSA05678", "Dynamic Test Theme")
    project.theme.video = project.import_asset(video, "video")
    project.theme.resolution = "360p (640x360)"
    project.theme.frame_count = 4
    project.save()
    return project


@pytest.fixture
def tools_ready() -> None:
    """Skip when a build step needs an external binary that is not installed."""
    from ps4theme import tools

    paths = tools.resolve()
    if not media.available():
        pytest.skip("FFmpeg is not available")
    if not paths.pkgtool:
        pytest.skip("PkgTool is not installed")
    _ = paths
