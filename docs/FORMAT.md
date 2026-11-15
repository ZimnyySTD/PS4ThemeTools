# PS4 theme format notes

This document records the format details the app depends on. Every rule here is
enforced in code and covered by the test-suite, because the console is strict
about several of them and fails in unhelpful ways (a black screen, a theme that
installs but crashes when applied, or `CE-38196-7`).

## Package layout

A finished theme content folder (`Image0`) looks like this:

```
theme.xml
sce_sys/param.sfo
sce_sys/icon0.png            512×512
sce_sys/pic1.png             1920×1080
texture/preview.png          740×416
texture/background/homescreen.png      1920×1080   static only
texture/background/functionscreen.png  1920×1080   static only
texture/function_icon/<name>.png       128×128
texture/function_icon/<name>_glow.png  152×152
texture/content_icon/<name>.png        512×512
scene/background.raf/index.xml          dynamic only
scene/background.raf/plane.mdx          dynamic only
scene/background.raf/00.dds …           dynamic only
sound/bgm_home.at9                      optional
```

`theme.xml`, `sce_sys/param.sfo` and the package artwork are mandatory. The
PNG screens are replaced by the RAF scene for dynamic themes; the working
retail-style sample does not ship them, so the app omits them too.

## param.sfo

The SFO writer produces the exact 11-entry / 1160-byte layout used by the
packaging tools when a creator is set. Entries are sorted by ASCII key:

| Key | Format | Notes |
| --- | --- | --- |
| `ATTRIBUTE` | int32 | 0 |
| `CATEGORY` | UTF-8 | `ac` (theme) |
| `CONTENT_ID` | UTF-8 | 36 characters |
| `FORMAT` | UTF-8 | `obs` |
| `IRO_TAG` | int32 | 2 — makes the console treat the package as a theme |
| `TITLE` | UTF-8 | theme name, max 128 bytes |
| `TITLE_ID` | UTF-8 | `[A-Z]{4}[0-9]{5}` |
| `VERSION` | UTF-8 | `01.00` |
| `CONTENT_VER` | UTF-8 | same as version |
| `PUBTOOLINFO` | UTF-8 | `c_date=YYYYMMDD` |
| `PROVIDER` | UTF-8 | only when a creator is set |

The binary layout is:

```
header  20 bytes  magic 0x46535000, version 0x101, key offset, data offset, count
index   16 bytes per entry: key offset, format, used size, max size, data offset
keys    NUL-terminated ASCII
data    values padded to each entry's reserved max size
```

`tests/test_formats.py` checks the round-trip and the exact byte length.

## theme.xml

```xml
<?xml version="1.0" encoding="utf-8"?>
<theme>
    <format-version>4.0</format-version>
    <themecolor>0</themecolor>
    <label>My-Theme</label>
    <fontcolor>#FFFFFFFF</fontcolor>
    <fontshadowcolor>#FF000000</fontshadowcolor>
    <focuscolor>#FF1E9BFF</focuscolor>
    <homescreen-dimmer>#00FFFFFF</homescreen-dimmer>
    <functionscreen-dimmer>#00FFFFFF</functionscreen-dimmer>
    <titlename-dimmer>#00FFFFFF</titlename-dimmer>
    <homebgm-enable>False</homebgm-enable>
</theme>
```

- `format-version` and `themecolor` are mandatory; a missing file or missing
  colour can crash the console when the theme is applied.
- Colours are `#AARRGGBB`.
- The label accepts only `[A-Za-z0-9_-]`, so spaces and punctuation become `-`.
- `homebgm-enable` must only be `True` when `sound/bgm_home.at9` exists,
  otherwise the console tries to play a missing track.

## DXT1 frames

Frames are DXT1a textures in a 128-byte DDS header with no mipmaps. DXT1 is
fixed-rate: 8 bytes per 4×4 block, so the size is predictable before encoding.

| Resolution | Blocks | Payload | File size |
| --- | --- | --- | --- |
| 1280×720 | 320×180 | 460,800 B | **460,928 B** |
| 960×540 | 240×135 | 259,200 B | **259,328 B** |
| 640×360 | 160×90 | 115,200 B | **115,328 B** |

The encoder tests all 8 DXT1a transparency modes per block (including the
3-colour + transparent mode) and uses principal-axis endpoints, so gradients
and alpha cut-outs survive. `tests/test_formats.py` checks the round-trip error.

## RAF scene

`scene/background.raf/index.xml` describes a 3D scene, not a video:

- one perspective camera (`yfov=29`, near 0.1, far 300),
- one ambient light,
- one shared quad model (`plane.mdx`),
- one `pure_texture` material per DDS frame,
- one actor per frame at `z=9`, all stacked in the same place,
- a sequence where each case fades the current actor out and the next one in.

The quad is sized so it exactly fills the camera's vertical field of view at its
distance, `half_h = depth * tan(yfov/2)`, with a 16:9 aspect and a small
overscan. The last case wraps to frame 0, so the loop is seamless.

The scene plus every frame must stay under **6 MiB**, and a theme may not have
more than **48 frames**. The app enforces both, and also caps frames by the
per-resolution byte budget.

## MDX model

`plane.mdx` is a small XDM (`XDM.00.1MSP`) record tree:

```
REC 0x0002 root
  REC 0x0010 model
    PROP 0x8083 bounding sphere, 0x8084 metric
    REC 0x0011 RootNode
    REC 0x0011 plane   rotation/scale/geometry reference
    REC 0x0012 geometry
      REC 0x0013 mesh  material + arrays references, indices
      REC 0x0014 arrays  four half-float vertices and UVs
    REC 0x0016 material
```

The reference theme uses `.mdx` directly in `index.xml`, so the app writes that
file name rather than converting it to a proprietary variant.

## .gp4

The PyPkg project file is plain XML with `volume_type=pkg_ps4_theme`. File
paths are validated to stay relative (no drive letters, no `..`), then written
as `<file targ_path=... orig_path=...>` entries plus a `<rootdir>` tree. The
passcode is 32 zeros (fake package).

## ATRAC9 music

`ps4_at9tool.exe` produces the `.at9` file. The command that matches a working
theme is:

```
ps4_at9tool.exe -e -br 144 -fs 48000 -wholeloop input.wav output.at9
```

`-wholeloop` writes the smpl chunk with `playCount=0`, which is what menu music
needs. Input is converted to 16-bit stereo 48 kHz PCM by FFmpeg first, and
clips longer than five minutes are trimmed.
