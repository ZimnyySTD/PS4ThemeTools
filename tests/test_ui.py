"""Smoke tests for the real CustomTkinter window.

These tests need a desktop session; on a headless machine they are skipped
instead of failing the suite.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from ps4theme.models import Project
from ps4theme.settings import Settings

ctk = pytest.importorskip("customtkinter")

from ps4theme.ui.app import AppState, ThemeToolsApp  # noqa: E402
from ps4theme.ui.ps4_preview import _argb, render_ps4_preview  # noqa: E402


@pytest.fixture
def window(tmp_path):
    try:
        project = Project.create(tmp_path / "UI Theme")
        state = AppState(settings=Settings(), project=project)
        app = ThemeToolsApp(state)
        app.update_idletasks()
        app.update()
    except tk.TclError as exc:  # pragma: no cover - headless CI
        pytest.skip(f"no desktop session: {exc}")
    try:
        yield app
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_every_tab_opens_and_refreshes(window):
    for key in ("theme", "icons", "appearance", "build", "guide", "tools"):
        window.show_page(key)
        window.update_idletasks()
        window.update()
        assert window.current_page == key
        assert "Could not refresh" not in window.status_label.cget("text")

    assert set(window._pages) == {
        "theme", "icons", "appearance", "build", "guide", "tools"
    }


def test_theme_xml_colours_are_read_as_argb():
    assert _argb("#FF1E9BFF", (0, 0, 0, 0)) == (30, 155, 255, 255)
    assert _argb("#00FFFFFF", (0, 0, 0, 0)) == (255, 255, 255, 0)
    assert _argb("#33112233", (0, 0, 0, 0)) == (0x11, 0x22, 0x33, 0x33)
    assert _argb("not a colour", (1, 2, 3, 4)) == (1, 2, 3, 4)


def test_preview_leaves_a_transparent_dimmer_untouched(tmp_path):
    project = Project.create(tmp_path / "Preview Theme")
    image = render_ps4_preview(project.theme, project, (320, 180))
    red, green, blue = image.getpixel((160, 110))
    # The default dimmer is #00FFFFFF (transparent), so the blue gradient shows.
    assert blue > green > red and blue > 90


def test_appearance_preview_is_rendered(window):
    window.show_page("appearance")
    window.update()
    page = window._pages["appearance"]
    assert page._preview_image is not None
    window._pages["appearance"]._set_theme_color(4)
    window.update()
    assert window.project.theme.themecolor == 4


def test_invalid_colour_is_not_saved(window):
    page = window._pages["appearance"]
    window.show_page("appearance")
    before = window.project.theme.font_color
    page._set_color("font_color", "#XYZ")
    assert window.project.theme.font_color == before
    page._set_color("font_color", "#FF112233")
    assert window.project.theme.font_color == "#FF112233"


def test_build_page_reports_readiness(window, background):
    window.project.theme.background = window.project.import_asset(background, "images")
    window.show_page("build")
    window.update()
    page = window._pages["build"]
    assert page.running is False
    assert "Ready to build" in page.validation_title.cget("text")
    assert page._expected_name().endswith("_static.pkg")


def test_theme_page_writes_project_file(window):
    window.show_page("theme")
    page = window._pages["theme"]
    page.name_field.set("Renamed Theme")
    page._change_name("Renamed Theme")
    window.save_now()
    assert window.project.theme.name == "Renamed Theme"
    assert (window.project.root / "theme.ps4t.json").is_file()
    assert "Renamed Theme" in window.project_name.cget("text")
