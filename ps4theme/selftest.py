"""Built-in diagnostics used by ``app.py --self-test``.

The checks only use the Python standard library, Pillow and NumPy, so they work
on any PC without FFmpeg, PkgTool or a console.  They verify the byte-level
formats the console is strict about: param.sfo, theme.xml, DXT1 DDS, MDX, RAF
and the .gp4 project file.
"""

from __future__ import annotations

import datetime as _dt
import platform
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

from . import constants as C
from . import dxt1, gp4, images, mdx, media, models, raf, sfo, theme_xml, tools

OK = "  [ok]  "
FAIL = "  [FAIL]"


def _check(name: str, function, *, verbose: bool = False) -> bool:
    try:
        detail = function()
    except Exception as exc:  # noqa: BLE001 - the point is to report anything
        print(f"{FAIL} {name}: {exc}")
        if verbose:
            traceback.print_exc()
        return False
    print(f"{OK} {name}" + (f" - {detail}" if detail else ""))
    return True


def _constants() -> str:
    expected = {
        (1280, 720): (460_928, 13),
        (960, 540): (259_328, 24),
        (640, 360): (115_328, 48),
    }
    for label, (width, height) in C.ANIMATED_SIZES.items():
        size = C.dds_size_for(width, height)
        frames = C.max_frames_for(width, height)
        assert (size, frames) == expected[(width, height)], (
            f"{label}: got {size} bytes / {frames} frames"
        )
        assert frames * size <= C.RAF_SIZE_LIMIT
    assert C.max_frames_for(*C.STATIC_SIZE) >= 1
    return "3 resolutions, frame caps match the console limits"


def _sfo() -> str:
    data = sfo.build_theme_sfo(
        title="My Theme",
        title_id="CUSA00000",
        content_id="UP9000-CUSA00000_00-MYTHEME00000000",
        creator="Tester",
        version="01.00",
        date=_dt.date(2026, 1, 2),
    )
    assert len(data) == 1160, f"expected 1160 bytes, got {len(data)}"
    parsed = sfo.read_sfo(data)
    assert parsed["TITLE"]["value"] == "My Theme"
    assert parsed["TITLE_ID"]["value"] == "CUSA00000"
    assert parsed["CONTENT_ID"]["value"].startswith("UP9000-CUSA00000_00-")
    assert parsed["CATEGORY"]["value"] == "ac"
    assert parsed["IRO_TAG"]["value"] == 2
    assert parsed["PROVIDER"]["value"] == "Tester"
    assert parsed["PUBTOOLINFO"]["value"] == "c_date=20260102"

    unnamed = sfo.build_theme_sfo(
        title="No Provider",
        title_id="CUSA00001",
        content_id="UP9000-CUSA00001_00-NOPROVIDER000000",
        date=_dt.date(2026, 1, 2),
    )
    assert "PROVIDER" not in sfo.read_sfo(unnamed)
    return f"{len(data)} bytes, 11 entries, roundtrip clean"


def _theme_xml() -> str:
    text = theme_xml.build_theme_xml(
        label="My Theme!",
        themecolor=3,
        homescreen_dimmer="#66000000",
        homebgm_enable=True,
    )
    root = ET.fromstring(text)
    assert root.tag == "theme"
    assert root.findtext("themecolor") == "3"
    assert root.findtext("format-version") == theme_xml.FORMAT_VERSION
    assert root.findtext("label") == "My-Theme"
    assert root.findtext("homescreen-dimmer") == "#66000000"
    assert root.findtext("homebgm-enable") == "True"

    try:
        theme_xml.build_theme_xml(label="x", themecolor=9)
    except theme_xml.ThemeXmlError:
        pass
    else:
        raise AssertionError("themecolor 9 should be rejected")
    return "valid XML, label sanitised, bad colour rejected"


def _dxt1() -> str:
    height, width = 48, 64
    y, x = np.mgrid[0:height, 0:width]
    frame = np.zeros((height, width, 4), dtype=np.uint8)
    frame[..., 0] = (x * 255 // max(1, width - 1)).astype(np.uint8)
    frame[..., 1] = (y * 255 // max(1, height - 1)).astype(np.uint8)
    frame[..., 2] = 160
    frame[..., 3] = 255
    data = dxt1.encode_dds(frame)
    assert data[:4] == b"DDS "
    assert len(data) == C.dds_size_for(width, height), "DDS size is not fixed rate"
    decoded = dxt1.decode_dds(data)
    assert decoded.shape == (height, width, 4)
    error = np.abs(decoded[..., :3].astype(int) - frame[..., :3].astype(int)).mean()
    assert error < 22, f"mean DXT1 error is {error:.1f}, expected < 22"
    return f"{len(data)} bytes, mean colour error {error:.1f}"


def _mdx() -> str:
    half_w, half_h = raf.plane_half_size()
    data = mdx.quad_model(half_w=half_w, half_h=half_h, depth=raf.PLANE_DEPTH)
    records = mdx.parse(data)
    assert len(records) == 1 and records[0].tag == mdx.TAG_ROOT
    assert mdx.build(records) == data, "MDX does not round-trip byte for byte"

    def tags(items):
        for item in items:
            if isinstance(item, mdx.Record):
                yield item.tag
                yield from tags(item.children)

    found = set(tags(records))
    for tag in (mdx.TAG_MODEL, mdx.TAG_NODE, mdx.TAG_GEOMETRY, mdx.TAG_MESH, mdx.TAG_ARRAYS):
        assert tag in found, f"missing MDX record {tag:#06x}"
    for value in (0.0, 1.0, -1.5, 9.25, 100.0):
        assert abs(mdx.h2f(mdx.f2h(value)) - value) < 0.01
    return f"{len(data)} bytes, tree roundtrips exactly"


def _raf() -> str:
    frames = ["00.dds", "01.dds", "02.dds"]
    text = raf.build_scene(frames, 0.125)
    root = ET.fromstring(text)
    assert root.tag == "raf"
    materials = root.findall("material")
    actors = root.findall("actor")
    cases = root.find("sequence").findall("case")
    assert len(materials) == 3 and len(actors) == 3 and len(cases) == 3
    assert materials[0].find("texture").get("file") == "00.dds"
    assert root.find("model").get("file") == "plane.mdx"
    assert abs(float(cases[0].get("wait")) - 0.125) < 1e-9
    # The last case wraps to the first frame.
    assert cases[-1].findall("actor")[1].get("id") == "f00"
    return "3 frames, wrapping sequence, plane.mdx reference"


def _gp4() -> str:
    text = gp4.build_gp4(
        content_id="UP9000-CUSA00000_00-MYTHEME00000000",
        targets=["sce_sys/param.sfo", "theme.xml", "texture/preview.png"],
        volume_ts="2026-01-02 03:04:05",
    )
    root = ET.fromstring(text)
    assert root.findtext("volume/volume_type") == "pkg_ps4_theme"
    assert root.find("volume/package").get("content_id").startswith("UP9000-")
    files = root.find("files").findall("file")
    assert len(files) == 3
    assert root.find("rootdir") is not None
    try:
        gp4.build_gp4(content_id="x", targets=["../escape"])
    except gp4.Gp4Error:
        pass
    else:
        raise AssertionError("path traversal should be rejected")
    return "3 files, theme volume, unsafe path rejected"


def _images_check(root: Path) -> str:
    source = Image.new("RGBA", (320, 180), (30, 120, 220, 255))
    source.paste((255, 255, 255, 255), (80, 40, 240, 140))
    path = root / "source.png"
    source.save(path)

    loaded = images.open_image(path)
    cover = images.fit_cover(loaded, C.STATIC_SIZE, opaque=True)
    assert cover.size == C.STATIC_SIZE and cover.mode == "RGB"
    icon = images.fit_cover(cover, C.THEME_ICON_SIZE)
    assert icon.size == C.THEME_ICON_SIZE
    glow = images.make_glow(icon)
    assert glow.size == C.FUNCTION_ICON_GLOW_SIZE
    written = images.save_png(glow, root / "icon0.png")
    assert written.is_file() and written.stat().st_size > 0
    return "cover crop, icon and glow generation"


def _project(root: Path) -> str:
    folder = root / "project"
    project = models.Project.create(folder)
    assert (folder / C.PROJECT_FILE_NAME).is_file()

    image = Image.new("RGB", (1920, 1080), (10, 40, 90))
    asset = root / "background.png"
    image.save(asset)
    relative = project.import_asset(asset, "images")
    project.theme.background = relative
    project.theme.name = "Self Test Theme"
    project.theme.creator = "Tester"
    project.theme.content_id = models.build_content_id(project.theme.title_id, "Self Test Theme")
    project.save()

    loaded = models.Project.load(folder)
    assert loaded.theme.name == "Self Test Theme"
    assert loaded.theme.background == relative
    errors, warnings = models.validate(loaded)
    assert not errors, errors
    assert not warnings, warnings

    loaded.theme.title_id = "bad"
    errors, _warnings = models.validate(loaded)
    assert errors, "an invalid Title ID should be reported"
    return "create, import, save, load and validate"


def _tools() -> str:
    paths = tools.resolve()
    present = [
        label for label, path in (
            ("FFmpeg", paths.ffmpeg),
            ("PkgTool", paths.pkgtool),
            ("at9tool", paths.at9tool),
        ) if path
    ]
    assert C.PKGTOOL_SHA256 and len(C.PKGTOOL_SHA256) == 64
    assert C.AT9TOOL_SHA256 and len(C.AT9TOOL_SHA256) == 64
    assert C.PKGTOOL_URL.startswith("https://")
    assert C.AT9TOOL_URL.startswith("https://")
    assert C.FFMPEG_RELEASE_API.startswith("https://")
    for pattern in C.FFMPEG_ASSET_PATTERNS:
        assert pattern.startswith("^ffmpeg-"), pattern
    if paths.ffmpeg:
        media.configure(paths.ffmpeg, paths.ffprobe)
        version = media.version()
        if version:
            present[present.index("FFmpeg")] = f"FFmpeg {version}"
    return ", ".join(present) if present else "not installed yet (optional for this check)"


def _assets() -> str:
    required = ("app_icon.ico", "app_icon.png", "logo.png")
    missing = [name for name in required if not C.resource_path(name).is_file()]
    assert not missing, "missing bundled assets: " + ", ".join(missing)
    with Image.open(C.resource_path("app_icon.ico")) as icon:
        assert icon.size[0] >= 32
    with Image.open(C.resource_path("logo.png")) as logo:
        assert logo.size == (256, 256), f"logo is {logo.size}"
    return "icon and logo present and readable"


def run_self_test(verbose: bool = False) -> int:
    """Prints a report and returns a process exit code."""
    print(f"{C.APP_NAME} {C.APP_VERSION} - self test")
    print(f"Python {sys.version.split()[0]} on {platform.platform()}")
    print(f"Project root: {C.project_root()}")
    print(f"Config:       {C.config_dir()}")
    print(f"Tools:        {C.tools_dir()}")
    print()

    started = _dt.datetime.now()
    results = [
        _check("Constants and frame limits", _constants, verbose=verbose),
        _check("param.sfo writer/reader", _sfo, verbose=verbose),
        _check("theme.xml generator", _theme_xml, verbose=verbose),
        _check("DXT1 encoder/decoder", _dxt1, verbose=verbose),
        _check("MDX model format", _mdx, verbose=verbose),
        _check("RAF scene (index.xml)", _raf, verbose=verbose),
        _check(".gp4 project file", _gp4, verbose=verbose),
        _check("Dependency catalogue", _tools, verbose=verbose),
        _check("Bundled assets", _assets, verbose=verbose),
    ]

    with tempfile.TemporaryDirectory(prefix="ps4theme-selftest-") as raw:
        root = Path(raw)
        results.append(_check("Image pipeline", lambda: _images_check(root), verbose=verbose))
        results.append(_check("Project model", lambda: _project(root), verbose=verbose))

    elapsed = (_dt.datetime.now() - started).total_seconds()
    failed = results.count(False)
    print()
    if failed:
        print(f"{failed} of {len(results)} checks failed in {elapsed:.2f}s.")
        return 1
    print(f"All {len(results)} checks passed in {elapsed:.2f}s.")
    return 0
