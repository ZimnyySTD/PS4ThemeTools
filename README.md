<p align="center">
  <img src="assets/logo.png" width="112" alt="PS4 Theme Tools logo">
</p>

<h1 align="center">PS4 Theme Tools</h1>

<p align="center">
  A clean Windows desktop app for building <strong>static</strong> and
  <strong>dynamic</strong> PS4 themes: artwork, icons, colours and music in,
  a ready-to-install <code>.pkg</code> out.
</p>

---

## What it does

- **Static themes** – a 1920×1080 home-screen background, an optional top-menu
  background, an optional theme icon and optional background music.
- **Dynamic themes** – pick a video; the app samples it into the PS4's DXT1
  frame budget, builds the RAF scene and verifies the 6 MiB / 48-frame console
  limits before packing.
- **App icons** – replace any of the 9 function icons and 10 content icons.
  152×152 glow versions are generated automatically.
- **Appearance** – all 8 system theme colours, font/focus colours, the three
  dimmer overlays and a live PS4 home-screen mock.
- **One-click build** – validates the project, writes `theme.xml` and
  `param.sfo`, generates every PNG and the `.gp4`, then calls PkgTool and
  validates the resulting package.
- **Automatic dependencies** – the Build button detects missing tools and
  downloads FFmpeg, PkgTool and at9tool, checking hashes before use.
- **Everything stays local** – projects are portable folders, settings live in
  `%LOCALAPPDATA%`, and the app never contacts a console.

## Screens

| Tab | Purpose |
| --- | --- |
| **Theme** | Name, IDs, background/video, music, animation frames |
| **App Icons** | Function and content icon replacements |
| **Appearance** | Live preview, theme colour, text colours, dimmers |
| **Build** | Validation, build options, progress, full log, result |
| **Install Guide** | Normal and permanent install methods, troubleshooting |
| **Tools** | Dependency status, downloads, manual locations, cache |

## Requirements

- **Windows 10 or 11** (64-bit).
- **Python 3.11 or newer** to run from source. The packaged `.exe` needs no
  Python installation.
- To *install* the finished theme: a PS4 that can install unsigned packages
  (for example a console running GoldHEN). The app does not modify, connect to,
  or exploit a console.
- FFmpeg, PkgTool and at9tool are downloaded on demand. A source checkout can
  also use copies on `PATH`.

## Quick start

```bat
git clone <this repository>
cd PS4ThemeTools

python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Or double-click **`run.bat`**, which creates the virtual environment and
installs the dependencies the first time.

### Your first theme

1. Open the **Theme** tab and give the theme a name. Press **Generate** next to
   the Content ID if you want a fresh identity.
2. Choose a **background** (static) or a **video** (dynamic). Optionally add
   music, a theme icon and a top-menu image.
3. Dynamic themes only: choose a resolution and frame count. The app shows the
   estimated scene size and keeps you inside the console limits.
4. Optionally replace icons in **App Icons** and adjust colours in
   **Appearance**.
5. Open **Build** and press **Build theme**. The first build offers to download
   any missing tools, then produces:
   - `<output>\<theme>_static.pkg` or `<output>\<theme>_dynamic.pkg`
   - the complete content folder under `<project>\build\<theme>\work\Image0`
6. Follow the **Install Guide** tab to copy the package to a USB drive,
   install it, and apply the theme in **Settings → Themes**.

## Command line

```bat
:: format and dependency checks (no console needed)
.venv\Scripts\python.exe app.py --self-test

:: build without opening the window
.venv\Scripts\python.exe app.py --build "C:\path\to\My Theme" --output dist

:: rebuild and let it download missing tools
.venv\Scripts\python.exe app.py --build "C:\path\to\My Theme" --auto-install

:: theme folder only, no .pkg
.venv\Scripts\python.exe app.py --build "C:\path\to\My Theme" --no-package

:: open a specific project and tab
.venv\Scripts\python.exe app.py "C:\path\to\My Theme" --page appearance
```

`--version` prints the version. `python -m ps4theme` works from the repository
root and forwards to the same entry point.

## Building the Windows executable

```bat
build_exe.bat
```

or, with more control:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -Clean -SkipTests
```

The script installs `requirements-dev.txt`, runs the test-suite, builds with
PyInstaller, starts the packaged exe and runs its self-test. The result is a
self-contained folder:

```
dist\PS4ThemeTools\
  PS4ThemeTools.exe
  _internal\...
```

Zip that whole folder to distribute it. Downloaded tools are **not** bundled:
each user's copy fetches them into `%LOCALAPPDATA%\PS4ThemeTools\tools` on first
build, so the download is always visible and hash-checked.

## Dependencies the app downloads

| Tool | Why | Source | Verification |
| --- | --- | --- | --- |
| **FFmpeg** | Decode video, extract frames, convert music | [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases) latest `win64-lgpl-shared` | Release `checksums.sha256` |
| **PkgTool** 0.2.231 | Build the fake `.pkg` | [LibOrbisPkg release](https://github.com/maxton/LibOrbisPkg/releases) | Pinned SHA-256 `c639e591…30097` |
| **at9tool** | Encode ATRAC9 background music (optional) | [ATRACTool-Reloaded portable](https://github.com/XyLe-GBP/ATRACTool-Reloaded/releases) | Pinned SHA-256 `cbac59b9…9687` |

Downloads go to `tools\downloads\` while in progress, then archives are
deleted. The **Tools** tab can show every resolved path, reinstall a tool,
accept a manual executable location, or clear the cache.

## Console limits encoded in the app

| Resolution | DXT1 frame size | Frames that fit in 6 MiB | Console cap |
| --- | --- | --- | --- |
| 1280×720 | 460,928 B | 13 | 48 |
| 960×540 | 259,328 B | 24 | 48 |
| 640×360 | 115,328 B | 48 | 48 |

The scene (all `.dds` frames + `index.xml` + `plane.mdx`) must stay under
**6 MiB**. The app refuses to package a larger animation; lowering resolution
or frame count is the fix. See [`docs/FORMAT.md`](docs/FORMAT.md) for why these
numbers are fixed.

## Project layout

```
PS4ThemeTools/
  app.py                     GUI / CLI entry point
  ps4theme/
    constants.py             every console limit, path, URL and colour
    models.py                project format, validation, asset handling
    sfo.py                   param.sfo writer and reader
    theme_xml.py             theme.xml generator
    gp4.py                   .gp4 project generator
    dxt1.py                  DXT1a encoder and decoder
    mdx.py                   PS4 .mdx model builder/parser
    raf.py                   animated scene (index.xml) generator
    images.py                PNG pipeline (cover crop, icons, glows)
    media.py                 FFmpeg/ffprobe layer
    audio.py                 ATRAC9 encoding
    tools.py                 dependency detection and downloads
    builder.py               the build pipeline
    settings.py              LocalAppData settings
    selftest.py              --self-test checks
    ui/                      CustomTkinter pages and shared widgets
  assets/                    logo and application icon
  scripts/                   asset and executable build scripts
  tests/                     pytest suite, including real package builds
  docs/FORMAT.md             technical notes on the PS4 containers
```

A project folder looks like this:

```
My Theme/
  theme.ps4t.json            editable project (JSON)
  assets/images/...          artwork copied from wherever you picked it
  assets/video/...           source video
  assets/audio/...           source music
  assets/icons/...           custom icons
  build/<slug>/work/         generated content, .gp4 and PkgTool output
```

Copying the folder is enough to move the theme to another PC.

## Testing

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

The suite covers the binary formats, validation, the project model, the GUI
smoke path, real static and dynamic builds, and package validation when PkgTool
is available. Tests that need FFmpeg, PkgTool or at9tool skip cleanly when a
tool is not installed.

`app.py --self-test` is the quickest health check of an installed copy. Where
no console is attached (the windowed `.exe`), the report is written to
`%LOCALAPPDATA%\PS4ThemeTools\self-test.log`.

## DPI and appearance

The window enables per-monitor DPI awareness and uses a light blue/white/cyan
palette throughout. Minimum window size is 1120×720; the default is 1320×860.
All pages scroll when the window is smaller than their content.

## Notes and limitations

- Packages are **fake** (unsigned) packages: installing them requires a PS4
  that already permits that. This is a packaging tool, not a jailbreak.
- Themes are visual content only. Do not include game assets, music or artwork
  you do not have the right to distribute.
- PkgTool builds a package from the folder; if PkgTool is unavailable, the app
  still leaves a complete theme folder and explains what was skipped.
- A rebuilt theme may be cached by Content ID. Use **Generate** on the Theme tab
  to give the new build a fresh identity.
- Background music requires at9tool. Without it the theme is still valid, just
  silent; the build log says so explicitly.

## License

MIT — see [`LICENSE`](LICENSE). Third-party components and their licenses are
listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
PlayStation and PS4 are trademarks of Sony Interactive Entertainment Inc. This
project is unofficial and not endorsed by Sony.
