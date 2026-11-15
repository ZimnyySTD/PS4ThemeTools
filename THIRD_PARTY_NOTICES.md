# Third-party notices

PS4 Theme Tools itself is MIT licensed (see `LICENSE`). It uses the following
software. None of the external executables are committed to this repository or
included in the built application: they are downloaded on demand into the
user's tools folder and verified against a SHA-256 checksum where a stable hash
is available.

## Python packages

| Package | License | Use |
| --- | --- | --- |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | MIT | Desktop widgets |
| [Pillow](https://python-pillow.org/) | HPND | Image decoding, scaling, PNG/ICO generation |
| [NumPy](https://numpy.org/) | BSD-3-Clause | DXT1 block compression |
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0-or-later with a special exception for bootloader use | Building the Windows executable |
| [pytest](https://pytest.org/) | MIT | Test-suite |

## FFmpeg

- Source: <https://github.com/BtbN/FFmpeg-Builds/releases>
- License: LGPL-3.0-or-later or GPL-3.0-or-later, depending on the build that is
  downloaded. The application prefers `win64-lgpl-shared` archives.
- The archive is checked against the release's published `checksums.sha256`
  before it is unpacked. FFmpeg is used as a separate executable; its license
  and source offer are inside the downloaded archive.

## PkgTool / LibOrbisPkg

- Source: <https://github.com/maxton/LibOrbisPkg/releases> (v0.2.231)
- License: GNU LGPL v3. The release archive contains `LICENSE.txt` and
  `README.md`, which are kept next to the executable when it is installed.
- Used to turn the generated theme content into a fake `.pkg`.

## at9tool / ATRACTool-Reloaded

- Source: <https://github.com/XyLe-GBP/ATRACTool-Reloaded/releases>
- `ps4_at9tool.exe` is Sony's proprietary ATRAC9 encoder, redistributed by the
  ATRACTool-Reloaded project. It is not authored by, nor bundled with, this
  application.
- The app downloads the official portable archive and extracts only
  `ps4_at9tool.exe` into its own tools folder. Use is subject to the terms of
  the project that publishes it.

## Trademarks

PlayStation, PS4 and ATRAC are trademarks of Sony Interactive Entertainment
Inc. This project is unofficial and is not affiliated with or endorsed by Sony.
