from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import END, filedialog, messagebox, ttk
import tkinter as tk


APP_NAME = "PS4 Theme Tools"
APP_VERSION = "1.0.0"
FFMPEG_API = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
CREATE_GP4_RELEASE = "https://github.com/OpenOrbis/create-gp4/releases/download/v1.0/binaries.tar.gz"
LIBORBISPKG_SOURCE = "https://github.com/OpenOrbis/LibOrbisPkg/archive/refs/heads/master.zip"


@dataclass
class Asset:
    source: str
    target: str
    category: str


@dataclass
class ThemeProject:
    name: str = "Untitled Theme"
    content_id: str = "UP0001-CUSA00000_00-PS4THEMETOOLS000"
    author: str = ""
    description: str = ""
    theme_type: str = "Static"
    icon: str = ""
    background: str = ""
    video: str = ""
    audio: str = ""
    assets: list[Asset] = field(default_factory=list)


@dataclass
class BuildArtifacts:
    bundle: Path
    gp4: Path | None = None
    pkg: Path | None = None


class ToolManager:
    """Finds and installs the public tools used by the build pipeline."""

    def __init__(self, app_dir: Path):
        self.app_dir = app_dir
        self.tools_dir = app_dir / "tools"
        self.tools_dir.mkdir(parents=True, exist_ok=True)

    def find_ffmpeg(self) -> Path | None:
        candidates = [
            shutil.which("ffmpeg"),
            str(self.tools_dir / "ffmpeg.exe"),
            str(self.tools_dir / "bin" / "ffmpeg.exe"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return Path(candidate)
        return None

    def find_create_gp4(self) -> Path | None:
        candidates = [
            str(self.tools_dir / "create-gp4.exe"),
            str(self.tools_dir / "create-gp4"),
        ]
        return next((Path(candidate) for candidate in candidates if Path(candidate).exists()), None)

    def find_pkg_tool(self) -> Path | None:
        configured = os.environ.get("PS4_ORBIS_PUB_GEN")
        candidates = [
            configured,
            str(self.tools_dir / "orbis-pub-gen.exe"),
            str(self.tools_dir / "pkgtool" / "PkgTool.exe"),
            str(self.tools_dir / "pkgtool" / "PkgTool"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return Path(candidate)
        return None

    def download_ffmpeg(self, progress=None) -> Path:
        """Download the latest BtbN Windows build through its GitHub release API."""
        request = urllib.request.Request(
            FFMPEG_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": APP_NAME},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
        assets = [
            asset for asset in release.get("assets", [])
            if "win64-gpl.zip" in asset.get("name", "").lower()
        ]
        if not assets:
            raise RuntimeError("No compatible Windows FFmpeg release was found.")
        archive_url = assets[0]["browser_download_url"]
        archive_path = self.tools_dir / "ffmpeg-download.zip"
        with urllib.request.urlopen(
            urllib.request.Request(archive_url, headers={"User-Agent": APP_NAME}),
            timeout=60,
        ) as response, archive_path.open("wb") as output:
            total = int(response.headers.get("Content-Length", "0"))
            downloaded = 0
            while chunk := response.read(1024 * 256):
                output.write(chunk)
                downloaded += len(chunk)
                if progress and total:
                    progress(downloaded / total)
        with zipfile.ZipFile(archive_path) as archive:
            executable = next(
                name for name in archive.namelist()
                if name.lower().endswith("/bin/ffmpeg.exe")
            )
            with archive.open(executable) as source, (self.tools_dir / "ffmpeg.exe").open("wb") as target:
                shutil.copyfileobj(source, target)
        archive_path.unlink(missing_ok=True)
        return self.tools_dir / "ffmpeg.exe"

    def download_create_gp4(self) -> Path:
        archive_path = self.tools_dir / "create-gp4-download.tar.gz"
        request = urllib.request.Request(CREATE_GP4_RELEASE, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(request, timeout=60) as response, archive_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        with tarfile.open(archive_path, "r:gz") as archive:
            member = next(
                item for item in archive.getmembers()
                if item.name.lower().endswith("bin/windows/create-gp4.exe")
            )
            member_file = archive.extractfile(member)
            if member_file is None:
                raise RuntimeError("The create-gp4 release did not contain a Windows executable.")
            executable = self.tools_dir / "create-gp4.exe"
            with executable.open("wb") as output:
                shutil.copyfileobj(member_file, output)
        archive_path.unlink(missing_ok=True)
        return executable

    def install_pkg_tool_from_source(self, log) -> Path | None:
        if self.find_pkg_tool():
            return self.find_pkg_tool()
        dotnet = shutil.which("dotnet")
        if not dotnet:
            log("OpenOrbis PkgTool was not installed: the .NET SDK is not available.")
            return None
        source_zip = self.tools_dir / "liborbispkg-source.zip"
        source_dir = self.tools_dir / "liborbispkg-source"
        request = urllib.request.Request(LIBORBISPKG_SOURCE, headers={"User-Agent": APP_NAME})
        log("Downloading the open-source OpenOrbis PkgTool source...")
        with urllib.request.urlopen(request, timeout=60) as response, source_zip.open("wb") as output:
            shutil.copyfileobj(response, output)
        if source_dir.exists():
            shutil.rmtree(source_dir)
        source_dir.mkdir()
        with zipfile.ZipFile(source_zip) as archive:
            archive.extractall(source_dir)
        source_zip.unlink(missing_ok=True)
        repository_root = next(source_dir.iterdir())
        output_dir = self.tools_dir / "pkgtool"
        command = [
            dotnet,
            "publish",
            str(repository_root / "PkgTool" / "PkgTool.csproj"),
            "--configuration",
            "Release",
            "--output",
            str(output_dir),
            "--nologo",
        ]
        log("Building OpenOrbis PkgTool locally...")
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        shutil.rmtree(source_dir, ignore_errors=True)
        if result.returncode != 0:
            raise RuntimeError(f"OpenOrbis PkgTool build failed:\n{result.stderr[-2000:]}")
        return self.find_pkg_tool()

    def ensure_build_tools(self, project: ThemeProject, log):
        create_gp4 = self.find_create_gp4()
        if not create_gp4:
            log("Installing create-gp4...")
            create_gp4 = self.download_create_gp4()
        if project.theme_type == "Dynamic" and not self.find_ffmpeg():
            log("Installing FFmpeg for dynamic theme media...")
            self.download_ffmpeg()
        pkg_tool = self.find_pkg_tool()
        if not pkg_tool:
            pkg_tool = self.install_pkg_tool_from_source(log)
        return create_gp4, pkg_tool


class ThemeBuilder:
    def __init__(self, project: ThemeProject, output_dir: Path, tool_manager: ToolManager):
        self.project = project
        self.output_dir = output_dir
        self.tool_manager = tool_manager

    def build(self, log):
        if not self.project.name.strip():
            raise ValueError("Theme name cannot be empty.")
        if self.project.theme_type == "Static" and not self.project.background:
            raise ValueError("Choose a static background before building.")
        if self.project.theme_type == "Dynamic" and not self.project.video:
            raise ValueError("Choose a dynamic background video before building.")

        safe_name = "".join(
            character if character.isalnum() or character in " ._-" else "_"
            for character in self.project.name
        ).strip() or "PS4 Theme"
        staging = Path(tempfile.mkdtemp(prefix="ps4-theme-"))
        try:
            create_gp4, pkg_tool = self.tool_manager.ensure_build_tools(self.project, log)
            log("Preparing theme staging directory...")
            content_dir = staging / "content"
            content_dir.mkdir()
            self._copy_asset(self.project.icon, content_dir / "theme_icon", log)
            self._copy_asset(
                self.project.background if self.project.theme_type == "Static" else self.project.video,
                content_dir / ("background" if self.project.theme_type == "Static" else "background_video"),
                log,
            )
            self._copy_asset(self.project.audio, content_dir / "background_audio", log)
            for index, asset in enumerate(self.project.assets, start=1):
                target = content_dir / asset.target
                target.parent.mkdir(parents=True, exist_ok=True)
                self._copy_asset(asset.source, target, log, fallback_name=f"asset_{index}")

            manifest = {
                "format": "ps4-theme-tools-bundle",
                "format_version": 1,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "project": asdict(self.project),
                "notes": [
                    "This bundle contains prepared source assets.",
                    "A valid retail/jailbreak PKG requires a compatible orbis-pub-gen tool.",
                ],
            }
            manifest["project"]["assets"] = [asdict(asset) for asset in self.project.assets]
            (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            output = self.output_dir / f"{safe_name}.ps4theme.zip"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            gp4_output = self.output_dir / f"{safe_name}.gp4"
            files = [str(file.relative_to(content_dir)).replace("\\", "/") for file in content_dir.rglob("*") if file.is_file()]
            command = [
                str(create_gp4),
                "-out",
                str(gp4_output),
                "--content-id",
                self.project.content_id,
                "--files",
                " ".join(files),
            ]
            log("Generating GP4 project...")
            result = subprocess.run(command, cwd=content_dir, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"create-gp4 failed:\n{result.stderr[-2000:]}")
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in staging.rglob("*"):
                    if file.is_file():
                        archive.write(file, file.relative_to(staging))
            log(f"Bundle created: {output}")
            pkg_output = None
            if pkg_tool and pkg_tool.name.lower().startswith("pkgtool"):
                pkg_output_dir = self.output_dir / f"{safe_name}-pkg"
                pkg_output_dir.mkdir(exist_ok=True)
                log("Building an open-source fake PKG with OpenOrbis PkgTool...")
                result = subprocess.run(
                    [str(pkg_tool), "pkg_build", str(gp4_output), str(pkg_output_dir)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"PkgTool failed:\n{result.stderr[-2000:]}")
                pkg_candidates = list(pkg_output_dir.glob("*.pkg"))
                pkg_output = pkg_candidates[0] if pkg_candidates else None
                if pkg_output:
                    log(f"PKG created: {pkg_output}")
            elif pkg_tool:
                log("A local orbis-pub-gen was found, but no command template was assumed.")
            else:
                log("No PKG publisher available; the GP4 project and source bundle were created.")
            return BuildArtifacts(output, gp4_output, pkg_output)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _copy_asset(source: str, target: Path, log, fallback_name="asset"):
        if not source:
            return
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"Asset not found: {path}")
        target = target.with_suffix(path.suffix) if not target.suffix else target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        log(f"Added {fallback_name}: {path.name}")


class ThemeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1060x720")
        self.minsize(900, 620)
        self.configure(bg="#f4fbff")
        self.project = ThemeProject()
        self.assets: list[Asset] = []
        self.app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
        self.tools = ToolManager(self.app_dir)
        self._configure_style()
        self._build_ui()

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background="#f4fbff")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f4fbff", foreground="#17324d")
        style.configure("Card.TLabel", background="#ffffff", foreground="#17324d")
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#073b63", background="#f4fbff")
        style.configure("Muted.TLabel", foreground="#5c7487", background="#f4fbff")
        style.configure("CardMuted.TLabel", foreground="#5c7487", background="#ffffff")
        style.configure("TButton", padding=(12, 7))
        style.configure("Accent.TButton", background="#09a6d8", foreground="white", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#078ab4")])
        style.configure("TNotebook", background="#f4fbff", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 9), background="#dff5fc")
        style.map("TNotebook.Tab", background=[("selected", "#09a6d8")], foreground=[("selected", "white")])

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=28, pady=(22, 8))
        ttk.Label(header, text="PS4 Theme Tools", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Create clean, install-ready theme bundles", style="Muted.TLabel").pack(side="left", padx=18, pady=(8, 0))
        ttk.Button(header, text="Save Project", command=self.save_project).pack(side="right")
        ttk.Button(header, text="Open Project", command=self.open_project).pack(side="right", padx=8)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=22, pady=10)
        self._build_editor_tab()
        self._build_assets_tab()
        self._build_instructions_tab()
        self._build_footer()

    def _build_editor_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Theme editor")
        left = ttk.Frame(tab, style="Card.TFrame", padding=20)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=8)
        right = ttk.Frame(tab, style="Card.TFrame", padding=20)
        right.pack(side="right", fill="y", padx=(10, 0), pady=8)

        ttk.Label(left, text="Theme details", style="Card.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.name_var = tk.StringVar(value=self.project.name)
        self.content_id_var = tk.StringVar(value=self.project.content_id)
        self.author_var = tk.StringVar()
        self._field(left, "Theme name", self.name_var)
        self._field(left, "Content ID", self.content_id_var)
        self._field(left, "Author", self.author_var)
        ttk.Label(left, text="Description", style="Card.TLabel").pack(anchor="w", pady=(8, 3))
        self.description_text = tk.Text(left, height=5, relief="flat", bg="#f4fbff", fg="#17324d", insertbackground="#17324d")
        self.description_text.pack(fill="x")

        ttk.Label(right, text="Theme type", style="Card.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.type_var = tk.StringVar(value="Static")
        ttk.Radiobutton(right, text="Static theme", variable=self.type_var, value="Static", command=self._refresh_media).pack(anchor="w", pady=(12, 4))
        ttk.Radiobutton(right, text="Dynamic theme", variable=self.type_var, value="Dynamic", command=self._refresh_media).pack(anchor="w", pady=4)
        ttk.Separator(right).pack(fill="x", pady=16)
        self.icon_var = tk.StringVar()
        self.media_var = tk.StringVar()
        self.audio_var = tk.StringVar()
        self._file_field(right, "Theme icon (PNG)", self.icon_var, [("Images", "*.png *.jpg *.jpeg"), ("All files", "*.*")])
        self.media_label = ttk.Label(right, text="Background image", style="Card.TLabel")
        self.media_label.pack(anchor="w", pady=(12, 3))
        self._file_picker(
            right,
            self.media_var,
            [("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")],
            marker="_ps4_media_row",
        )
        self._file_field(right, "Background music (optional)", self.audio_var, [("Audio", "*.at9 *.mp3 *.wav *.ogg"), ("All files", "*.*")])

    def _build_assets_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="System app replacements")
        ttk.Label(tab, text="Replace system content", style="Title.TLabel").pack(anchor="w", padx=20, pady=(20, 2))
        ttk.Label(tab, text="Choose a source file and a PS4 target path. The builder keeps the selected target name.", style="Muted.TLabel").pack(anchor="w", padx=20)
        body = ttk.Frame(tab, style="Card.TFrame", padding=18)
        body.pack(fill="both", expand=True, padx=20, pady=16)
        form = ttk.Frame(body, style="Card.TFrame")
        form.pack(fill="x")
        self.asset_source_var = tk.StringVar()
        self.asset_target_var = tk.StringVar()
        self._file_picker(form, self.asset_source_var, [("Images", "*.png *.jpg *.jpeg *.dds *.tga"), ("All files", "*.*")], label="Source file")
        self._field(form, "Target path / filename", self.asset_target_var, card=True)
        ttk.Button(form, text="Add replacement", style="Accent.TButton", command=self.add_asset).pack(anchor="e", pady=(8, 0))
        self.asset_list = tk.Listbox(body, height=10, relief="flat", bg="#f4fbff", fg="#17324d", selectbackground="#09a6d8")
        self.asset_list.pack(fill="both", expand=True, pady=(18, 0))
        ttk.Button(body, text="Remove selected", command=self.remove_asset).pack(anchor="e", pady=(10, 0))

    def _build_instructions_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Install guide")
        text = tk.Text(tab, wrap="word", relief="flat", bg="#ffffff", fg="#17324d", padx=24, pady=22)
        text.pack(fill="both", expand=True, padx=20, pady=18)
        text.insert("1.0", """PS4 theme workflow

1. Build a .ps4theme.zip bundle from the Theme editor.
2. Transfer the bundle to your PC or a USB drive and inspect manifest.json.
3. Use a compatible, legally obtained orbis-pub-gen / PKG workflow for your firmware.
4. On a jailbroken PS4, install the resulting PKG with the console's package installer.

Permanent themes
Permanent theme installation changes system content and is firmware-specific. Back up the original theme files first and follow the instructions for your jailbreak payload. This application does not modify a console or provide proprietary Sony tools.

Dynamic themes
Dynamic backgrounds are staged as the original video. A firmware-specific conversion pipeline may be required to convert video frames and audio to the formats expected by your PS4 theme template.

Tool locations
• FFmpeg is optional and can be downloaded from the official BtbN GitHub release API by the Tools menu.
• Set PS4_ORBIS_PUB_GEN to a legally obtained orbis-pub-gen.exe to expose your local packaging workflow.
""")
        text.configure(state="disabled")

    def _build_footer(self):
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=22, pady=(0, 18))
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Check tools", command=self.check_tools).pack(side="right", padx=8)
        ttk.Button(footer, text="Build theme bundle", style="Accent.TButton", command=self.build).pack(side="right")

    def _field(self, parent, label, variable, card=False):
        style = "Card.TLabel" if card else "TLabel"
        ttk.Label(parent, text=label, style=style).pack(anchor="w", pady=(12, 3))
        entry = ttk.Entry(parent, textvariable=variable)
        entry.pack(fill="x")
        return entry

    def _file_picker(self, parent, variable, filetypes, label=None, marker=None):
        if label:
            ttk.Label(parent, text=label, style="Card.TLabel").pack(anchor="w", pady=(0, 3))
        row = ttk.Frame(parent, style="Card.TFrame")
        if marker:
            setattr(row, marker, True)
        row.pack(fill="x", pady=(0, 4))
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse", command=lambda: self._choose_file(variable, filetypes)).pack(side="right", padx=(8, 0))

    def _file_field(self, parent, label, variable, filetypes):
        ttk.Label(parent, text=label, style="Card.TLabel").pack(anchor="w", pady=(0, 3))
        self._file_picker(parent, variable, filetypes)

    def _choose_file(self, variable, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            variable.set(path)

    def _refresh_media(self):
        dynamic = self.type_var.get() == "Dynamic"
        self.media_label.configure(text="Background video" if dynamic else "Background image")
        self.media_var.set("")
        parent = self.media_label.master
        # Replace the browse command by rebuilding this small row.
        for child in list(parent.winfo_children()):
            if getattr(child, "_ps4_media_row", False):
                child.destroy()
        row = ttk.Frame(parent, style="Card.TFrame")
        row._ps4_media_row = True
        row.pack(fill="x", pady=(0, 4))
        ttk.Entry(row, textvariable=self.media_var).pack(side="left", fill="x", expand=True)
        types = [("Video", "*.mp4 *.mov *.mkv *.webm"), ("All files", "*.*")] if dynamic else [("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
        ttk.Button(row, text="Browse", command=lambda: self._choose_file(self.media_var, types)).pack(side="right", padx=(8, 0))

    def add_asset(self):
        source, target = self.asset_source_var.get().strip(), self.asset_target_var.get().strip()
        if not source or not target:
            messagebox.showwarning(APP_NAME, "Choose a source file and enter a target path.")
            return
        self.assets.append(Asset(source, target.replace("\\", "/").lstrip("/"), "system"))
        self.asset_list.insert(END, f"{target}  <-  {Path(source).name}")
        self.asset_source_var.set("")
        self.asset_target_var.set("")

    def remove_asset(self):
        selection = self.asset_list.curselection()
        if selection:
            index = selection[0]
            self.asset_list.delete(index)
            self.assets.pop(index)

    def collect_project(self):
        self.project.name = self.name_var.get().strip()
        self.project.content_id = self.content_id_var.get().strip()
        self.project.author = self.author_var.get().strip()
        self.project.description = self.description_text.get("1.0", "end").strip()
        self.project.theme_type = self.type_var.get()
        self.project.icon = self.icon_var.get().strip()
        self.project.audio = self.audio_var.get().strip()
        self.project.background = self.media_var.get().strip() if self.project.theme_type == "Static" else ""
        self.project.video = self.media_var.get().strip() if self.project.theme_type == "Dynamic" else ""
        self.project.assets = list(self.assets)
        return self.project

    def save_project(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Project JSON", "*.json")])
        if not path:
            return
        data = asdict(self.collect_project())
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.status_var.set(f"Saved {Path(path).name}")

    def open_project(self):
        path = filedialog.askopenfilename(filetypes=[("Project JSON", "*.json")])
        if not path:
            return
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.project = ThemeProject(**{**data, "assets": [Asset(**item) for item in data.get("assets", [])]})
        self.assets = self.project.assets
        self.name_var.set(self.project.name)
        self.content_id_var.set(self.project.content_id)
        self.author_var.set(self.project.author)
        self.description_text.delete("1.0", "end")
        self.description_text.insert("1.0", self.project.description)
        self.type_var.set(self.project.theme_type)
        self.icon_var.set(self.project.icon)
        self.audio_var.set(self.project.audio)
        self.media_var.set(self.project.background or self.project.video)
        self.asset_list.delete(0, END)
        for asset in self.assets:
            self.asset_list.insert(END, f"{asset.target}  <-  {Path(asset.source).name}")
        self._refresh_media()
        self.media_var.set(self.project.background or self.project.video)
        self.status_var.set(f"Opened {Path(path).name}")

    def check_tools(self):
        ffmpeg = self.tools.find_ffmpeg()
        create_gp4 = self.tools.find_create_gp4()
        pkg = self.tools.find_pkg_tool()
        message = (
            f"create-gp4: {'found' if create_gp4 else 'will install on build'}\n"
            f"FFmpeg: {'found' if ffmpeg else 'will install for dynamic builds'}\n"
            f"PKG tool: {'found' if pkg else 'will build from source when .NET SDK is available'}"
        )
        if not ffmpeg and messagebox.askyesno(APP_NAME, message + "\n\nDownload FFmpeg now?"):
            self.status_var.set("Downloading FFmpeg...")
            threading.Thread(target=self._download_ffmpeg, daemon=True).start()
        else:
            messagebox.showinfo(APP_NAME, message)

    def _download_ffmpeg(self):
        try:
            self.tools.download_ffmpeg()
            self.after(0, lambda: self.status_var.set("FFmpeg installed in the tools folder."))
            self.after(0, lambda: messagebox.showinfo(APP_NAME, "FFmpeg was downloaded successfully."))
        except Exception as error:
            self.after(0, lambda: messagebox.showerror(APP_NAME, f"FFmpeg download failed:\n{error}"))
            self.after(0, lambda: self.status_var.set("FFmpeg download failed."))

    def build(self):
        try:
            project = self.collect_project()
            output_dir = Path(filedialog.askdirectory(title="Choose output folder") or "")
            if not output_dir:
                return
            self.status_var.set("Building...")
            log_lines = []
            artifacts = ThemeBuilder(project, output_dir, self.tools).build(log_lines.append)
            self.status_var.set(f"Built {artifacts.bundle.name}")
            outputs = [str(artifacts.bundle), str(artifacts.gp4)]
            if artifacts.pkg:
                outputs.append(str(artifacts.pkg))
            messagebox.showinfo(APP_NAME, "Build complete:\n\n" + "\n".join(outputs))
        except Exception as error:
            self.status_var.set("Build failed.")
            messagebox.showerror(APP_NAME, f"Build failed:\n{error}")


if __name__ == "__main__":
    ThemeApp().mainloop()
