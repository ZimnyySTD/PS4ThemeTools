# PS4 Theme Tools

PS4 Theme Tools is a Windows desktop utility for preparing static and dynamic PS4 theme assets. It uses only Python's standard library at runtime, so the source application can be started without installing Python packages:

```powershell
python ps4_theme_tools.py
```

## Features

- Static themes with an image background, optional audio, theme icon, and replacements.
- Dynamic themes with a video background, optional audio, theme icon, and replacements.
- Project save/open as JSON.
- System app replacement staging with a user-selected target path.
- Automatic installation of the public `create-gp4` Windows tool during the first build.
- Automatic FFmpeg installation for dynamic themes.
- Automatic OpenOrbis `PkgTool` source build when the .NET SDK is installed.
- `.gp4`, fake PKG, and portable `.ps4theme.zip` output when the available toolchain supports them.

## Build the Windows executable

Run PowerShell on Windows:

```powershell
.\build.ps1
```

The executable is written to `dist\PS4 Theme Tools\PS4 Theme Tools.exe`. PyInstaller is the only build dependency. `requirements.txt` intentionally does not include GUI/runtime packages.

## Automatic tool setup

Click **Build theme bundle**. The first build automatically installs `create-gp4` from the official OpenOrbis release and, for dynamic themes, FFmpeg from the latest BtbN Windows release. If the .NET SDK is available, the app also downloads the OpenOrbis LibOrbisPkg source and builds `PkgTool` locally.

The public download URLs used by the app are:

- `create-gp4`: https://github.com/OpenOrbis/create-gp4/releases/download/v1.0/binaries.tar.gz
- FFmpeg release API: https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest
- OpenOrbis LibOrbisPkg source: https://github.com/OpenOrbis/LibOrbisPkg/archive/refs/heads/master.zip

## Packaging note

Sony's `orbis-pub-gen` and related SDK tools are proprietary and firmware/workflow-specific. They are not downloaded or redistributed by this project. When OpenOrbis `PkgTool` is available, the app creates a fake PKG directly. Otherwise it creates a GP4 project and source bundle for a compatible local PKG workflow.

To use a legally obtained local publisher, set:

```powershell
$env:PS4_ORBIS_PUB_GEN = "C:\Path\To\orbis-pub-gen.exe"
```

The output is not a signed retail package. Use only on a compatible jailbroken console and follow the theme template and installation method required by your target firmware.

## URLs

- FFmpeg release API used by the app: https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest
- FFmpeg project: https://ffmpeg.org/
- PyInstaller documentation: https://pyinstaller.org/
