"""Byte-level formats the PS4 is strict about."""

from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from ps4theme import constants as C
from ps4theme import dxt1, gp4, mdx, raf, sfo, theme_xml


def test_resolution_budgets_match_measured_console_limits():
    expected = {
        (1280, 720): (460_928, 13),
        (960, 540): (259_328, 24),
        (640, 360): (115_328, 48),
    }
    for width, height in C.ANIMATED_SIZES.values():
        size, frames = expected[(width, height)]
        assert C.dds_size_for(width, height) == size
        assert C.max_frames_for(width, height) == frames
        assert frames * size <= C.RAF_SIZE_LIMIT
        assert frames <= C.MAX_FRAME_COUNT


def test_sfo_roundtrip_and_exact_size():
    data = sfo.build_theme_sfo(
        title="My Theme",
        title_id="CUSA00000",
        content_id="UP9000-CUSA00000_00-MYTHEME00000000",
        creator="Tester",
        version="01.00",
        date=dt.date(2026, 1, 2),
    )
    assert len(data) == 1160
    parsed = sfo.read_sfo(data)
    assert parsed["TITLE"]["value"] == "My Theme"
    assert parsed["TITLE_ID"]["value"] == "CUSA00000"
    assert parsed["CONTENT_ID"]["value"] == "UP9000-CUSA00000_00-MYTHEME00000000"
    assert parsed["CATEGORY"]["value"] == "ac"
    assert parsed["FORMAT"]["value"] == "obs"
    assert parsed["IRO_TAG"]["value"] == 2
    assert parsed["PROVIDER"]["value"] == "Tester"
    assert parsed["PUBTOOLINFO"]["value"] == "c_date=20260102"


def test_sfo_omits_provider_when_creator_is_empty():
    data = sfo.build_theme_sfo(
        title="No Provider",
        title_id="CUSA00001",
        content_id="UP9000-CUSA00001_00-NOPROVIDER000000",
        date=dt.date(2026, 1, 2),
    )
    assert "PROVIDER" not in sfo.read_sfo(data)


def test_sfo_rejects_oversized_values():
    with pytest.raises(sfo.SfoError):
        sfo.build_sfo([sfo.Entry("TITLE", "x" * 200, "utf8", 128)])


def test_theme_xml_contents_and_validation():
    text = theme_xml.build_theme_xml(
        label="My Theme!!",
        themecolor=3,
        homescreen_dimmer="#66000000",
        homebgm_enable=True,
    )
    root = ET.fromstring(text)
    assert root.tag == "theme"
    assert root.findtext("format-version") == "4.0"
    assert root.findtext("themecolor") == "3"
    assert root.findtext("label") == "My-Theme"
    assert root.findtext("homescreen-dimmer") == "#66000000"
    assert root.findtext("homebgm-enable") == "True"

    with pytest.raises(theme_xml.ThemeXmlError):
        theme_xml.build_theme_xml(label="x", themecolor=8)
    with pytest.raises(theme_xml.ThemeXmlError):
        theme_xml.build_theme_xml(label="x", focuscolor="#FFF")


def test_dxt1_is_fixed_rate_and_roundtrips():
    height, width = 48, 64
    y, x = np.mgrid[0:height, 0:width]
    frame = np.zeros((height, width, 4), dtype=np.uint8)
    frame[..., 0] = (x * 255 // (width - 1)).astype(np.uint8)
    frame[..., 1] = (y * 255 // (height - 1)).astype(np.uint8)
    frame[..., 2] = 160
    frame[..., 3] = 255

    data = dxt1.encode_dds(frame)
    assert data[:4] == b"DDS "
    assert len(data) == C.dds_size_for(width, height)
    decoded = dxt1.decode_dds(data)
    assert decoded.shape == (height, width, 4)
    error = np.abs(decoded[..., :3].astype(int) - frame[..., :3].astype(int)).mean()
    assert error < 22


def test_mdx_tree_roundtrips_byte_for_byte():
    half_w, half_h = raf.plane_half_size()
    data = mdx.quad_model(half_w=half_w, half_h=half_h, depth=raf.PLANE_DEPTH)
    records = mdx.parse(data)
    assert mdx.build(records) == data
    assert len(records) == 1 and records[0].tag == mdx.TAG_ROOT

    tags = set()

    def walk(items):
        for item in items:
            if isinstance(item, mdx.Record):
                tags.add(item.tag)
                walk(item.children)

    walk(records)
    assert {mdx.TAG_MODEL, mdx.TAG_NODE, mdx.TAG_GEOMETRY, mdx.TAG_MESH, mdx.TAG_ARRAYS} <= tags


def test_half_float_helpers():
    for value in (0.0, 1.0, -1.0, 2.146484, 100.0, -12.5):
        assert mdx.h2f(mdx.f2h(value)) == pytest.approx(value, abs=0.02)


def test_raf_scene_references_frames_and_wraps():
    text = raf.build_scene(["00.dds", "01.dds", "02.dds"], 0.125)
    root = ET.fromstring(text)
    materials = root.findall("material")
    cases = root.find("sequence").findall("case")

    assert root.find("model").get("file") == "plane.mdx"
    assert [m.find("texture").get("file") for m in materials] == [
        "00.dds", "01.dds", "02.dds"
    ]
    assert len(cases) == 3
    assert cases[-1].findall("actor")[1].get("id") == "f00"
    assert float(cases[0].get("wait")) == pytest.approx(0.125)


def test_gp4_structure_and_path_safety():
    text = gp4.build_gp4(
        content_id="UP9000-CUSA00000_00-MYTHEME00000000",
        targets=["theme.xml", "sce_sys/param.sfo", "texture/preview.png"],
        volume_ts="2026-01-02 03:04:05",
    )
    root = ET.fromstring(text)
    assert root.findtext("volume/volume_type") == "pkg_ps4_theme"
    assert root.find("volume/package").get("passcode") == "0" * 32
    assert len(root.find("files").findall("file")) == 3
    assert root.find("rootdir") is not None

    for bad in ("../escape", "/absolute", "", "a/../b"):
        with pytest.raises(gp4.Gp4Error):
            gp4.build_gp4(content_id="x", targets=[bad])
