"""Writer and reader for the PS4 ``param.sfo`` format.

The format is a small index + key table + data table:

    header  (20 bytes)  magic, version, key-table offset, data offset, count
    index   (16 * n)    key offset, format, used size, max size, data offset
    keys    (variable)  NUL terminated ASCII names
    data    (variable)  values, each one reserved ``max size`` bytes

The layout written here was checked against the param.sfo of a retail PS4
theme and against the file produced by the LibOrbisPkg based tools.
"""

from __future__ import annotations

import datetime as _dt
import struct
from dataclasses import dataclass
from pathlib import Path

from . import constants as C

MAGIC = 0x46535000          # b"\x00PSF"
VERSION = 0x101
HEADER_SIZE = 0x14
ENTRY_SIZE = 0x10

FMT_UTF8 = 0x0204
FMT_INT32 = 0x0404


class SfoError(ValueError):
    """An entry does not fit or the file is malformed."""


@dataclass(frozen=True)
class Entry:
    key: str
    value: str | int
    kind: str = "utf8"
    max_len: int = 4

    @property
    def fmt(self) -> int:
        return FMT_INT32 if self.kind == "int32" else FMT_UTF8

    def payload(self) -> bytes:
        if self.kind == "int32":
            try:
                return struct.pack("<i", int(self.value))
            except struct.error as exc:
                raise SfoError(f"{self.key}: {self.value!r} does not fit in 32 bits.") from exc
        raw = str(self.value).encode("utf-8") + b"\x00"
        if len(raw) > self.max_len:
            raise SfoError(
                f"{self.key}: value is {len(raw)} bytes but the field allows {self.max_len}."
            )
        return raw

    @property
    def used_len(self) -> int:
        return 4 if self.kind == "int32" else len(str(self.value).encode("utf-8")) + 1


def build_sfo(entries: list[Entry]) -> bytes:
    """Serialises entries, sorted by key the way Sony's tools do."""
    ordered = sorted(entries, key=lambda entry: entry.key.encode("ascii"))
    if len(ordered) > 0xFFFF:
        raise SfoError("Too many param.sfo entries.")
    for entry in ordered:
        if not entry.key or len(entry.key) > 0xFFFF:
            raise SfoError(f"Invalid param.sfo key: {entry.key!r}")
        try:
            entry.key.encode("ascii")
        except UnicodeEncodeError as exc:
            raise SfoError(f"Key '{entry.key}' is not ASCII.") from exc

    key_table = b"".join(entry.key.encode("ascii") + b"\x00" for entry in ordered)
    key_table_offset = HEADER_SIZE + ENTRY_SIZE * len(ordered)
    data_table_offset = key_table_offset + len(key_table)
    data_table_offset += (-data_table_offset) % 4

    index = bytearray()
    data = bytearray()
    key_offset = 0
    data_offset = 0
    for entry in ordered:
        payload = entry.payload()
        max_len = 4 if entry.kind == "int32" else max(entry.max_len, len(payload))
        if entry.kind == "utf8" and max_len > 0xFFFFFFFF:
            raise SfoError(f"{entry.key}: field is too large.")
        index += struct.pack(
            "<HHIII",
            key_offset,
            entry.fmt,
            len(payload) if entry.kind == "int32" else len(payload),
            max_len,
            data_offset,
        )
        data += payload.ljust(max_len, b"\x00")
        key_offset += len(entry.key) + 1
        data_offset += max_len

    total = data_table_offset + len(data)
    header = struct.pack(
        "<IIIII",
        MAGIC,
        VERSION,
        key_table_offset,
        data_table_offset,
        len(ordered),
    )
    output = bytearray(total)
    output[0:HEADER_SIZE] = header
    output[HEADER_SIZE:HEADER_SIZE + len(index)] = index
    output[key_table_offset:key_table_offset + len(key_table)] = key_table
    output[data_table_offset:data_table_offset + len(data)] = data
    return bytes(output)


def theme_entries(
    *,
    title: str,
    title_id: str,
    content_id: str,
    creator: str = "",
    version: str = C.SFO_VERSION,
    date: _dt.date | None = None,
) -> list[Entry]:
    """The exact set of fields a PS4 theme needs."""
    day = date or _dt.date.today()
    entries = [
        Entry("ATTRIBUTE", 0, "int32", 4),
        Entry("CATEGORY", C.CATEGORY, "utf8", 4),
        Entry("CONTENT_ID", content_id, "utf8", 48),
        Entry("FORMAT", "obs", "utf8", 4),
        Entry("IRO_TAG", C.IRO_TAG, "int32", 4),
        Entry("TITLE", title, "utf8", 128),
        Entry("TITLE_ID", title_id, "utf8", 12),
        Entry("VERSION", version, "utf8", 8),
        Entry("CONTENT_VER", version, "utf8", 8),
        Entry("PUBTOOLINFO", f"c_date={day:%Y%m%d}", "utf8", 512),
    ]
    if creator.strip():
        # Shown as the theme's provider in Settings > Themes.
        entries.append(Entry("PROVIDER", creator.strip(), "utf8", 128))
    return entries


def build_theme_sfo(
    *,
    title: str,
    title_id: str,
    content_id: str,
    creator: str = "",
    version: str = C.SFO_VERSION,
    date: _dt.date | None = None,
) -> bytes:
    return build_sfo(
        theme_entries(
            title=title,
            title_id=title_id,
            content_id=content_id,
            creator=creator,
            version=version,
            date=date,
        )
    )


def write_theme_sfo(path: Path, **kwargs) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_theme_sfo(**kwargs))
    return path


# --- reader (used by the tests and the tools window) ----------------------

def read_sfo(data: bytes) -> dict[str, dict]:
    """Decodes a param.sfo into ``{key: {value, fmt, max_len}}``."""
    if len(data) < HEADER_SIZE:
        raise SfoError("File is shorter than the param.sfo header.")
    magic, version, key_base, data_base, count = struct.unpack_from("<IIIII", data, 0)
    if magic != MAGIC:
        raise SfoError("Not a param.sfo file (bad magic).")
    if version != VERSION:
        # Unknown versions are still readable; record it instead of failing.
        pass
    if count > 4096:
        raise SfoError("Unreasonable number of param.sfo entries.")

    result: dict[str, dict] = {}
    for index in range(count):
        offset = HEADER_SIZE + ENTRY_SIZE * index
        if offset + ENTRY_SIZE > len(data):
            raise SfoError("Truncated param.sfo index.")
        key_offset, fmt, used, max_len, data_offset = struct.unpack_from("<HHIII", data, offset)
        key_start = key_base + key_offset
        key_end = data.find(b"\x00", key_start)
        if key_end < 0:
            raise SfoError("Unterminated param.sfo key.")
        key = data[key_start:key_end].decode("ascii", "replace")
        start = data_base + data_offset
        end = start + max_len
        if end > len(data) or used > max_len:
            raise SfoError(f"Entry '{key}' points outside the file.")
        raw = data[start:start + max_len]
        if fmt == FMT_INT32:
            value = struct.unpack_from("<i", raw, 0)[0]
        elif fmt == FMT_UTF8:
            value = raw[:used - 1 if used > 0 else used].split(b"\x00")[0].decode("utf-8", "replace")
        else:
            value = raw[:used].split(b"\x00")[0].decode("utf-8", "replace")
        result[key] = {"value": value, "fmt": fmt, "max_len": max_len}
    return result
