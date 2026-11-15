"""Read/write support for the PS4's XDM (``.mdx``) model format.

A dynamic theme does not need real geometry: every frame is the same quad and
only the material and the actor alpha change.  The record tree written here is
the one used by planes that render correctly on a console.

Record layout::

    REC 0x0002  root
      REC 0x0010  model
        PROP 0x8083 / 0x8084  bounding volume and metric
        REC 0x0011 RootNode
        REC 0x0011 node      transform
        REC 0x0012 geometry
          REC 0x0013 mesh
          REC 0x0014 arrays  vertices (raw payload)
        REC 0x0016 material

Inside a record body a uint16 with the high bit set is a property; otherwise
it starts a child record.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field

MAGIC = b"XDM.00.1MSP\x00" + b"\x00" * 4

TAG_ROOT = 0x0002
TAG_MODEL = 0x0010
TAG_NODE = 0x0011
TAG_GEOMETRY = 0x0012
TAG_MESH = 0x0013
TAG_ARRAYS = 0x0014
TAG_MATERIAL = 0x0016

PROP_PARENT = 0x8440
PROP_TRANSLATION = 0x8443
PROP_ROTATION = 0x8444
PROP_SCALE = 0x844B
PROP_GEOMETRY_REF = 0x847F
PROP_MATERIAL_REF = 0x84C0
PROP_ARRAYS_REF = 0x84C1
PROP_INDICES = 0x84E0

_MIN_NAME_FIELD = 8


class MdxError(ValueError):
    """A malformed .mdx file."""


# --- half floats ----------------------------------------------------------

def f2h(value: float) -> int:
    """float -> IEEE 754 half, round to nearest even."""
    packed = struct.unpack("<I", struct.pack("<f", value))[0]
    sign = (packed >> 16) & 0x8000
    exponent = (packed >> 23) & 0xFF
    mantissa = packed & 0x7FFFFF
    if exponent == 0xFF:
        return sign | 0x7C00 | (0x200 if mantissa else 0)
    e = exponent - 127 + 15
    if e >= 0x1F:
        return sign | 0x7C00
    if e <= 0:
        if e < -10:
            return sign
        mantissa |= 0x800000
        shift = 14 - e
        half = mantissa >> shift
        if (mantissa >> (shift - 1)) & 1:
            half += 1
        return sign | half
    half = sign | (e << 10) | (mantissa >> 13)
    if (mantissa >> 12) & 1:
        half += 1
    return half & 0xFFFF


def h2f(value: int) -> float:
    sign = (value >> 15) & 1
    exponent = (value >> 10) & 0x1F
    mantissa = value & 0x3FF
    if exponent == 0:
        result = (mantissa / 1024.0) * 2 ** -14
    elif exponent == 31:
        result = float("inf") if mantissa == 0 else float("nan")
    else:
        result = (1 + mantissa / 1024.0) * 2 ** (exponent - 15)
    return -result if sign else result


# --- tree -----------------------------------------------------------------

@dataclass
class Prop:
    pid: int
    data: bytes

    @property
    def size(self) -> int:
        return 4 + len(self.data)

    def pack(self) -> bytes:
        return struct.pack("<HH", self.pid, self.size) + self.data


@dataclass
class Record:
    tag: int
    name: str = ""
    children: list = field(default_factory=list)
    payload: bytes = b""

    @property
    def name_field(self) -> int:
        if not self.name:
            return 0
        return max(_MIN_NAME_FIELD, ((len(self.name) + 1 + 3) // 4) * 4)

    @property
    def header_size(self) -> int:
        return 0x10 + self.name_field

    def pack(self) -> bytes:
        body = self.payload + b"".join(child.pack() for child in self.children)
        header = self.header_size
        total = header + len(body)
        if self.tag == TAG_ARRAYS:
            a, b = header + 12, total
        else:
            a, b = header, header
        out = struct.pack("<HHIII", self.tag, header, a, b, total)
        if self.name_field:
            out += self.name.encode("ascii").ljust(self.name_field, b"\x00")
        return out + body


def _parse_body(data: bytes, start: int, end: int) -> list:
    items: list = []
    offset = start
    while offset + 4 <= end:
        first = struct.unpack_from("<H", data, offset)[0]
        if first & 0x8000:
            pid, size = struct.unpack_from("<HH", data, offset)
            if size < 4 or offset + size > end:
                raise MdxError(f"property {pid:#06x} has an invalid size at {offset:#x}")
            items.append(Prop(pid, data[offset + 4:offset + size]))
            offset += size
            continue
        if offset + 16 > end:
            raise MdxError(f"truncated record at {offset:#x}")
        tag, header = struct.unpack_from("<HH", data, offset)
        _a, _b, total = struct.unpack_from("<III", data, offset + 4)
        if header < 0x10 or total < header or offset + total > end:
            raise MdxError(f"record {tag:#06x} has an invalid header at {offset:#x}")
        name = ""
        if header > 0x10:
            name = data[offset + 0x10:offset + header].split(b"\x00")[0].decode("ascii", "replace")
        record = Record(tag, name)
        if tag == TAG_ARRAYS:
            record.payload = data[offset + header:offset + total]
        else:
            record.children = _parse_body(data, offset + header, offset + total)
        items.append(record)
        offset += total
    return items


def parse(data: bytes) -> list:
    if data[:len(MAGIC)] != MAGIC:
        raise MdxError("not an .mdx (missing the XDM.00.1 header)")
    return _parse_body(data, len(MAGIC), len(data))


def build(records: list) -> bytes:
    return MAGIC + b"".join(record.pack() for record in records)


# --- building a plane -----------------------------------------------------

def vertex(x: float, y: float, z: float, u: float, v: float,
           normal: bytes = b"\x00\x81\x00\x00") -> bytes:
    """One vertex: half-float position, 4 normal bytes, two half-float UVs."""
    return (
        struct.pack("<HHH", f2h(x), f2h(y), f2h(z))
        + normal
        + struct.pack("<HH", f2h(u), f2h(v))
    )


def quad_arrays(half_w: float, half_h: float, depth: float,
                uv: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)) -> Record:
    u0, v0, u1, v1 = uv
    vertices = b"".join([
        vertex(-half_w, depth, +half_h, u0, v0),
        vertex(-half_w, depth, -half_h, u0, v1),
        vertex(+half_w, depth, -half_h, u1, v1),
        vertex(+half_w, depth, +half_h, u1, v0),
    ])
    payload = struct.pack("<HHII", 0x0023, 0x0490, 14, 4) + vertices
    return Record(TAG_ARRAYS, "arrays-0", payload=payload)


#: Two triangles: (1,0,2) and (0,3,2), like the reference planes.
_QUAD_INDICES = struct.pack("<II", 3, 6) + struct.pack("<8H", 1, 0, 0, 1, 2, 0, 2, 3)


def quad_model(
    *,
    node_name: str = "plane",
    half_w: float = 1.0,
    half_h: float = 0.5625,
    depth: float = 2.14648,
    uv: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
    scale: float = 100.0,
) -> bytes:
    """Builds an ``.mdx`` containing a single textured quad."""
    root2 = math.sqrt(0.5)
    rotation = struct.pack("<4f", -root2, 0.0, 0.0, root2)  # -90 degrees on X
    scaling = struct.pack("<3f", scale, scale, scale)

    radius = math.hypot(half_w * scale, half_h * scale)
    center = (0.0, 0.0, -depth * scale)

    node = Record(TAG_NODE, node_name, [
        Prop(PROP_PARENT, bytes([0x00, 0x10, 0x11, 0x00])),
        Prop(PROP_ROTATION, rotation),
        Prop(PROP_SCALE, scaling),
        Prop(PROP_GEOMETRY_REF, bytes([0x00, 0x10, 0x12, 0x00])),
    ])
    mesh = Record(TAG_MESH, "mesh-0", [
        Prop(PROP_MATERIAL_REF, bytes([0x00, 0x20, 0x16, 0x00])),
        Prop(PROP_ARRAYS_REF, bytes([0x00, 0x10, 0x14, 0x00])),
        Prop(PROP_INDICES, _QUAD_INDICES),
    ])
    geometry = Record(TAG_GEOMETRY, node_name, [mesh, quad_arrays(half_w, half_h, depth, uv)])

    model = Record(TAG_MODEL, "model-0", [
        Prop(0x8083, struct.pack("<4f", center[0], center[1], center[2], radius)),
        Prop(0x8084, struct.pack("<I4f", 1, 0.0, depth, 0.0, 6.0)),
        Record(TAG_NODE, "RootNode"),
        node,
        geometry,
        Record(TAG_MATERIAL, "material-0"),
    ])
    return build([Record(TAG_ROOT, "", [model])])
