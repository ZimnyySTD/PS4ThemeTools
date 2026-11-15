"""Packaging with PkgTool: the final fake .pkg must validate."""

from __future__ import annotations

import subprocess

import pytest

from ps4theme import builder, constants as C, sfo, tools
from ps4theme.settings import Settings


@pytest.fixture
def pkgtool():
    paths = tools.resolve()
    if not paths.pkgtool:
        pytest.skip("PkgTool is not installed")
    return paths.pkgtool


def test_static_package_validates(static_project, tmp_path, pkgtool):
    result = builder.build(
        static_project,
        builder.BuildOptions(output_dir=tmp_path / "out", package=True),
        settings=Settings(),
    )
    assert result.pkg_path is not None
    assert result.pkg_path.is_file()
    assert result.pkg_path.suffix == ".pkg"
    assert result.pkg_path.name.endswith("_static.pkg")
    assert result.pkg_path.stat().st_size > 0
    assert not result.warnings

    check = subprocess.run(
        [str(pkgtool), "pkg_validate", str(result.pkg_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    assert check.returncode == 0, check.stdout.decode("utf-8", "replace")

    parsed = sfo.read_sfo((result.content_dir / C.THEME_PATH_SFO).read_bytes())
    assert parsed["CONTENT_ID"]["value"] == static_project.theme.content_id
    assert (result.build_dir / "work" / "theme.gp4").is_file()


def test_pkg_is_named_after_the_theme(static_project, tmp_path, pkgtool):
    static_project.theme.name = "Blue Horizon"
    static_project.save()
    result = builder.build(
        static_project,
        builder.BuildOptions(output_dir=tmp_path / "nested" / "out", package=True),
        settings=Settings(),
    )
    assert result.pkg_path is not None
    assert result.pkg_path.name == "Blue-Horizon_static.pkg"
    assert result.pkg_path.parent.is_dir()


def test_package_can_be_disabled_even_with_pkgtool(static_project, tmp_path, pkgtool):
    result = builder.build(
        static_project,
        builder.BuildOptions(output_dir=tmp_path / "out", package=False),
        settings=Settings(),
    )
    assert result.pkg_path is None
    assert any("No .pkg" in warning for warning in result.warnings)
