"""Generator for the RAF scene (``scene/background.raf/index.xml``).

A PS4 animated theme background is not a video: it is a 3D scene with one
shared quad, one material per frame and one actor per frame stacked at the
same position.  The sequence fades each actor out while fading the next one
in, which produces the animation.

The plane is sized so it exactly fills the camera's vertical field of view at
its distance.  The XML references ``plane.mdx``; the console accepts ``.mdx``
directly (the sample retail-style theme does exactly that).
"""

from __future__ import annotations

import math

MODEL_ID = "plane"
MODEL_FILE = "plane.mdx"

CAMERA_YFOV = 29.0
CAMERA_ZNEAR = 0.1
CAMERA_ZFAR = 300.0

PLANE_DEPTH = 2.146484
PLANE_SCALE = 100.0
OVERSCAN_X = 1.0
ASPECT = 16 / 9
ACTOR_Z = 9


def plane_half_size() -> tuple[float, float]:
    """Half width and height of the quad in local model units."""
    world_depth = PLANE_DEPTH * PLANE_SCALE
    half_h_world = world_depth * math.tan(math.radians(CAMERA_YFOV / 2))
    half_w_world = half_h_world * ASPECT * OVERSCAN_X
    return half_w_world / PLANE_SCALE, half_h_world / PLANE_SCALE


def frame_id(index: int) -> str:
    return f"f{index:02d}"


def _format_wait(seconds: float) -> str:
    text = f"{max(0.001, float(seconds)):.6f}".rstrip("0").rstrip(".")
    return text or "0.1"


def build_scene(frame_files: list[str], wait_seconds: float) -> str:
    """Builds ``index.xml`` for a sequence of DDS texture names."""
    if not frame_files:
        raise ValueError("at least one frame is required")
    wait = _format_wait(wait_seconds)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<raf angle_unit="degree">',
        "",
        '\t<system camera_switch_mode="vertical" layer_switch_distance="0"/>',
        "",
        f'\t<camera id="camera1" type="perspective" yfov="{CAMERA_YFOV:g}"'
        f' znear="{CAMERA_ZNEAR:g}" zfar="{CAMERA_ZFAR:g}"'
        ' position="0 0 0" direction="0 0 -1" up="0 1 0"/>',
        '\t<light id="light1" type="ambient" color="1 1 1"/>',
        "",
        f'\t<model id="{MODEL_ID}" file="{MODEL_FILE}"/>',
        "",
    ]

    for index, name in enumerate(frame_files):
        fid = frame_id(index)
        lines += [
            f'\t<material id="{fid}" effect="pure_texture">',
            f'\t\t<texture file="{name}"/>',
            "\t</material>",
        ]
    lines.append("")

    for index in range(len(frame_files)):
        fid = frame_id(index)
        alpha = 1 if index == 0 else 0
        lines.append(
            f'\t<actor id="{fid}" model="{MODEL_ID}" material="{fid}"'
            f' color="1 1 1 {alpha}" position="0 0 {ACTOR_Z}" zsort="back_to_front"/>'
        )
    lines.append("")

    lines.append("\t<sequence>")
    count = len(frame_files)
    for index in range(count):
        nxt = (index + 1) % count
        lines += [
            f'\t\t<case wait="{wait}">',
            f'\t\t\t<actor id="{frame_id(index)}" color="1 1 1 0"/>',
            f'\t\t\t<actor id="{frame_id(nxt)}" color="1 1 1 1"/>',
            "\t\t</case>",
        ]
    lines += ["\t</sequence>", "", "</raf>", ""]
    return "\n".join(lines)
