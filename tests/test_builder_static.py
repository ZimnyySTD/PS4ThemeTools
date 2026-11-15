"""End-to-end static builds (no console or package tool required)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ps4theme import builder, constants as C, tools
from ps4theme.settings import Settings


def _build(project, tmp_path: Path, **kwargs):
    output = tmp_path / "output"
    options = builder.BuildOptions(output_dir=output, **kwargs)
    progress = []
    logs = []
    result = builder.build(
        project,
        options,
        settings=Settings(),
        progress=lambda message, fraction: progress.append((message, fraction)),
        log_sink=logs.append,
    )
    return result, progress, logs


def test_static_build_writes_every_required_file(static_project, tmp_path):
    result, progress, logs = _build(static_project, tmp_path, package=False)

    content = result.content_dir
    expected = [
        C.THEME_PATH_THEME_XML,
        C.THEME_PATH_SFO,
        C.THEME_PATH_ICON0,
        C.THEME_PATH_PIC1,
        C.THEME_PATH_PREVIEW,
        C.THEME_PATH_HOMESCREEN,
        C.THEME_PATH_FUNCTIONSCREEN,
    ]
    for relative in expected:
        assert (content / relative).is_file(), relative

    assert not result.packaged
    assert any("No .pkg" in warning for warning in result.warnings)
    assert progress and progress[0][0] == "Checking the project..."
    assert progress[-1][1] == 1.0
    assert [fraction for _message, fraction in progress] == sorted(
        fraction for _message, fraction in progress
    )
    assert logs and any("Build finished" in line for line in logs)

    with Image.open(content / C.THEME_PATH_HOMESCREEN) as image:
        assert image.size == C.STATIC_SIZE
        assert image.mode == "RGB"
    with Image.open(content / C.THEME_PATH_PREVIEW) as image:
        assert image.size == C.PREVIEW_SIZE
    with Image.open(content / C.THEME_PATH_ICON0) as image:
        assert image.size == C.THEME_ICON_SIZE

    theme_xml = (content / C.THEME_PATH_THEME_XML).read_text(encoding="utf-8")
    assert "<homebgm-enable>False</homebgm-enable>" in theme_xml
    assert "<themecolor>0</themecolor>" in theme_xml

    from ps4theme import sfo

    parsed = sfo.read_sfo((content / C.THEME_PATH_SFO).read_bytes())
    assert parsed["TITLE"]["value"] == "Static Test Theme"
    assert parsed["PROVIDER"]["value"] == "Test Runner"
    assert parsed["CONTENT_ID"]["value"] == static_project.theme.content_id


def test_static_build_derives_icon_and_top_menu(static_project, tmp_path):
    result, _progress, _logs = _build(static_project, tmp_path, package=False)
    content = result.content_dir

    # No separate function screen or icon was chosen, so both reuse the
    # background instead of failing the build.
    assert (content / C.THEME_PATH_FUNCTIONSCREEN).stat().st_size > 0
    assert (content / C.THEME_PATH_ICON0).stat().st_size > 0
    assert not [w for w in result.warnings if "No .pkg" not in w]


def test_custom_icons_are_scaled_and_glowed(static_project, icon, tmp_path):
    project = static_project
    relative = project.import_asset(icon, "icons")
    project.theme.set_icon("function", "party", relative)
    project.theme.set_icon("content", "browser", relative)
    project.save()

    result, _progress, _logs = _build(project, tmp_path, package=False)
    content = result.content_dir

    function_dir = content / C.THEME_PATH_FUNCTION_ICONS
    with Image.open(function_dir / "party.png") as image:
        assert image.size == C.FUNCTION_ICON_SIZE
    with Image.open(function_dir / "party_glow.png") as image:
        assert image.size == C.FUNCTION_ICON_GLOW_SIZE
    with Image.open(content / C.THEME_PATH_CONTENT_ICONS / "browser.png") as image:
        assert image.size == C.CONTENT_ICON_SIZE


def test_build_overwrites_the_previous_build_folder(static_project, tmp_path):
    first, _progress, _logs = _build(static_project, tmp_path, package=False)
    marker = first.content_dir / "stale.txt"
    marker.write_text("old", encoding="utf-8")

    second, _progress, _logs = _build(static_project, tmp_path, package=False)
    assert not (second.content_dir / "stale.txt").exists()
    assert second.content_dir == first.content_dir


def test_invalid_project_is_rejected_before_writing(static_project, tmp_path):
    static_project.theme.background = ""
    with pytest.raises(builder.BuildError) as info:
        _build(static_project, tmp_path, package=False)
    assert "background image" in str(info.value).lower()


def test_cancellation_stops_the_build(static_project, tmp_path):
    import threading

    cancel = threading.Event()
    cancel.set()
    with pytest.raises(builder.BuildCancelled):
        builder.build(
            static_project,
            builder.BuildOptions(output_dir=tmp_path / "out", package=False),
            settings=Settings(),
            cancel=cancel,
        )


def test_static_theme_with_music(static_project, music, tmp_path):
    if not tools.resolve().at9tool:
        pytest.skip("at9tool is not installed")
    from ps4theme import media

    if not media.available():
        pytest.skip("FFmpeg is not available")

    project = static_project
    project.theme.music = project.import_asset(music, "audio")
    project.save()

    result, _progress, _logs = _build(project, tmp_path, package=False)
    at9 = result.content_dir / C.THEME_PATH_MUSIC
    assert at9.is_file() and at9.stat().st_size > 0
    assert at9.read_bytes()[:4] == b"RIFF"
    theme_xml = (result.content_dir / C.THEME_PATH_THEME_XML).read_text(encoding="utf-8")
    assert "<homebgm-enable>True</homebgm-enable>" in theme_xml


def test_missing_music_is_a_warning_not_a_failure(static_project, tmp_path):
    project = static_project
    project.theme.music = "assets/audio/missing.wav"
    project.save()

    result, _progress, _logs = _build(project, tmp_path, package=False)
    assert not (result.content_dir / C.THEME_PATH_MUSIC).exists()
    assert any("music" in warning.lower() for warning in result.warnings)
    theme_xml = (result.content_dir / C.THEME_PATH_THEME_XML).read_text(encoding="utf-8")
    assert "<homebgm-enable>False</homebgm-enable>" in theme_xml
