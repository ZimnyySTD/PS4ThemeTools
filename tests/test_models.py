"""Project model, asset handling and validation rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from ps4theme import constants as C
from ps4theme import models
from ps4theme.settings import Settings


def test_content_id_is_valid_and_contains_title_id():
    content_id = models.build_content_id("CUSA01234", "My Theme!")
    assert models.CONTENT_ID_RE.match(content_id)
    assert "CUSA01234" in content_id
    assert content_id.startswith("UP9000-")
    assert len(content_id) == 36


def test_content_id_is_stable_and_sanitises_names():
    assert models.build_content_id("CUSA00000", "Hello World") == models.build_content_id(
        "CUSA00000", "hello   world"
    )
    assert models.build_content_id("CUSA00000", "日本語").endswith(
        "THEME" + "0" * 11
    )


def test_project_create_save_load_roundtrip(static_project, tmp_path):
    project = static_project
    project.theme.font_color = "#FF102030"
    project.theme.frame_count = 9
    project.theme.function_icons["party"] = "assets/icons/party.png"
    project.save()

    loaded = models.Project.load(project.root)
    assert loaded.theme.name == project.theme.name
    assert loaded.theme.font_color == "#FF102030"
    assert loaded.theme.function_icons["party"] == "assets/icons/party.png"
    assert loaded.theme.content_id == project.theme.content_id

    raw = json.loads((project.root / C.PROJECT_FILE_NAME).read_text(encoding="utf-8"))
    assert raw["format"] == C.PROJECT_FORMAT
    assert raw["application"] == C.APP_NAME
    assert raw["theme"]["mode"] == "static"


def test_load_rejects_folders_without_a_project(tmp_path):
    with pytest.raises(models.ProjectError):
        models.Project.load(tmp_path)


def test_load_repairs_out_of_range_values(tmp_path, background):
    folder = tmp_path / "Broken"
    folder.mkdir()
    payload = {
        "format": C.PROJECT_FORMAT,
        "theme": {
            "name": "Broken",
            "mode": "nonsense",
            "resolution": "8K",
            "frame_count": "oops",
            "frame_wait": "oops",
            "themecolor": "oops",
        },
    }
    (folder / C.PROJECT_FILE_NAME).write_text(json.dumps(payload), encoding="utf-8")
    project = models.Project.load(folder)
    assert project.theme.mode == "static"
    assert project.theme.resolution == C.DEFAULT_RESOLUTION
    assert project.theme.frame_count == C.DEFAULT_FRAME_COUNT
    assert project.theme.frame_wait == 0.0
    assert project.theme.themecolor == 0


def test_import_asset_copies_and_deduplicates(static_project, tmp_path):
    project = static_project
    source = tmp_path / "one.png"
    Image.new("RGB", (16, 16), (1, 2, 3)).save(source)

    first = project.import_asset(source, "images")
    second = project.import_asset(source, "images")
    assert first == second
    assert (project.root / first).is_file()
    assert first.startswith("assets/images/")

    other = tmp_path / "two.png"
    Image.new("RGB", (16, 16), (9, 9, 9)).save(other)
    third = project.import_asset(other, "images")
    assert third != first


def test_clear_asset_only_removes_copied_files(static_project, tmp_path):
    project = static_project
    relative = project.import_asset(static_project.path_for(project.theme.background), "images")
    copied = project.root / relative
    assert copied.is_file()
    project.clear_asset(relative)
    assert not copied.exists()

    external = tmp_path / "external.png"
    Image.new("RGB", (8, 8), (0, 0, 0)).save(external)
    project.clear_asset(str(external))
    assert external.is_file()


def test_validate_catches_identity_and_media_errors(static_project):
    project = static_project
    project.theme.title_id = "nope"
    project.theme.content_id = "UP9000-CUSA00000_00-SHORT"
    project.theme.version = "1.0"
    project.theme.name = ""
    project.theme.background = ""

    errors, warnings = models.validate(project)
    text = " ".join(errors)
    assert "Theme name" in text
    assert "Version" in text
    assert "Title ID" in text
    assert "Content ID" in text
    assert "background image" in text.lower()
    assert warnings == []


def test_validate_dynamic_limits(dynamic_project):
    project = dynamic_project
    assert models.validate(project) == ([], [])

    project.theme.frame_count = project.theme.max_frames + 1
    errors, _warnings = models.validate(project)
    assert any("Frame count" in error for error in errors)

    project.theme.frame_count = 4
    project.theme.frame_wait = 0.001
    errors, _warnings = models.validate(project)
    assert any("Seconds per frame" in error for error in errors)


def test_validate_missing_custom_icon_is_a_warning(static_project):
    project = static_project
    project.theme.set_icon("function", "party", "assets/icons/missing.png")
    errors, warnings = models.validate(project)
    assert errors == []
    assert any("Party" in warning for warning in warnings)


def test_settings_roundtrip_and_recent_projects(tmp_path):
    settings = Settings()
    settings.output_dir = str(tmp_path / "out")
    settings.auto_install = False
    settings.remember_project(tmp_path / "A")
    settings.remember_project(tmp_path / "B")
    settings.save()

    loaded = Settings.load()
    assert loaded.output_dir == settings.output_dir
    assert loaded.auto_install is False
    assert loaded.last_project.endswith("B")
    assert loaded.recent_projects[0].endswith("B")
    assert loaded.recent_projects[1].endswith("A")
    assert loaded.default_output_dir() == Path(loaded.output_dir)


def test_settings_survive_a_corrupt_file():
    path = Settings.path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    loaded = Settings.load()
    assert loaded.last_project == ""
    assert loaded.auto_install is True
