"""Command-line entry points."""

from __future__ import annotations

import pytest

from ps4theme import APP_VERSION
from ps4theme.selftest import run_self_test
from app import main


def test_self_test_passes():
    assert run_self_test() == 0


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert APP_VERSION in capsys.readouterr().out


def test_build_command_produces_a_theme_folder(static_project, tmp_path, capsys):
    output = tmp_path / "cli-out"
    code = main(
        [
            "--build", str(static_project.root),
            "--output", str(output),
            "--no-package",
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "Theme folder:" in printed
    assert "Build finished" in printed


def test_build_command_rejects_a_missing_project(tmp_path, capsys):
    code = main(["--build", str(tmp_path / "nope")])
    assert code == 2
    assert "No theme.ps4t.json" in capsys.readouterr().err


def test_build_command_reports_invalid_projects(static_project, capsys):
    static_project.theme.background = ""
    static_project.save()
    code = main(["--build", str(static_project.root), "--no-package"])
    assert code == 1
    assert "Build failed" in capsys.readouterr().err


def test_unknown_page_is_rejected():
    with pytest.raises(SystemExit) as info:
        main(["--page", "nope"])
    assert info.value.code == 2
