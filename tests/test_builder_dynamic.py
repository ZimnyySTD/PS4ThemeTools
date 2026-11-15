"""End-to-end dynamic builds: video -> DXT1 frames -> RAF scene."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from ps4theme import builder, constants as C, dxt1, mdx, media, raf, tools
from ps4theme.settings import Settings


def _build(project, tmp_path, **kwargs):
    options = builder.BuildOptions(output_dir=tmp_path / "output", **kwargs)
    result = builder.build(project, options, settings=Settings())
    return result


def test_dynamic_build_writes_frames_and_scene(dynamic_project, tmp_path):
    if not media.available():
        pytest.skip("FFmpeg is not available")

    result = _build(dynamic_project, tmp_path, package=False)
    content = result.content_dir
    raf_dir = content / C.THEME_PATH_RAF
    assert raf_dir.is_dir()

    frames = sorted(raf_dir.glob("*.dds"))
    assert len(frames) == dynamic_project.theme.frame_count
    width, height = dynamic_project.theme.frame_size
    expected_size = C.dds_size_for(width, height)
    for frame in frames:
        data = frame.read_bytes()
        assert data[:4] == b"DDS "
        assert len(data) == expected_size
        decoded = dxt1.decode_dds(data)
        assert decoded.shape == (height, width, 4)

    plane = (raf_dir / raf.MODEL_FILE).read_bytes()
    assert mdx.parse(plane)
    index = ET.fromstring((raf_dir / "index.xml").read_text(encoding="utf-8"))
    assert len(index.findall("material")) == len(frames)
    assert len(index.find("sequence").findall("case")) == len(frames)

    total = sum(path.stat().st_size for path in raf_dir.iterdir())
    assert total <= C.RAF_SIZE_LIMIT

    # A dynamic theme still needs the package artwork, but not the two static
    # 1920x1080 screens (matching the working retail sample layout).
    assert (content / C.THEME_PATH_PREVIEW).is_file()
    assert (content / C.THEME_PATH_PIC1).is_file()
    assert (content / C.THEME_PATH_ICON0).is_file()
    assert not (content / C.THEME_PATH_HOMESCREEN).exists()
    assert not (content / C.THEME_PATH_FUNCTIONSCREEN).exists()


def test_dynamic_cover_frame_is_derived_when_no_background(dynamic_project, tmp_path):
    if not media.available():
        pytest.skip("FFmpeg is not available")
    result = _build(dynamic_project, tmp_path, package=False)
    preview = result.content_dir / C.THEME_PATH_PREVIEW
    assert preview.is_file() and preview.stat().st_size > 0


def test_dynamic_frame_count_is_clamped_to_the_budget(dynamic_project, tmp_path):
    if not media.available():
        pytest.skip("FFmpeg is not available")
    dynamic_project.theme.frame_count = dynamic_project.theme.max_frames
    result = _build(dynamic_project, tmp_path, package=False)
    frames = list((result.content_dir / C.THEME_PATH_RAF).glob("*.dds"))
    assert len(frames) == dynamic_project.theme.max_frames


def test_dynamic_without_ffmpeg_explains_the_problem(dynamic_project, tmp_path, monkeypatch):
    monkeypatch.setattr(media, "available", lambda: False)
    monkeypatch.setattr(media, "require_tools", lambda: (_ for _ in ()).throw(
        media.MediaError("missing")
    ))
    import ps4theme.builder as module

    monkeypatch.setattr(module, "_prepare_tools", lambda *args, **kwargs: tools.ToolPaths())
    dynamic_project.theme.music = ""
    with pytest.raises(builder.BuildError) as info:
        builder.build(
            dynamic_project,
            builder.BuildOptions(output_dir=tmp_path / "out", package=False),
            settings=Settings(),
        )
    assert "FFmpeg" in str(info.value)
