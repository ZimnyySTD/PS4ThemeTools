"""Fixed PS4 theme formats, limits, paths and application constants.

Everything the console imposes as a hard rule lives here so the rest of the
code does not need magic numbers.  The values were verified against a working
retail theme and against the output of the packaging tools.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Application ----------------------------------------------------------

APP_NAME = "PS4 Theme Tools"
APP_VERSION = "1.0.0"
APP_AUTHOR = "PS4 Theme Tools contributors"
PROJECT_FILE_NAME = "theme.ps4t.json"
PROJECT_FORMAT = 1

#: Files the user selected are copied here so a project folder is portable.
ASSETS_DIR_NAME = "assets"
BUILD_DIR_NAME = "build"
DIST_DIR_NAME = "dist"

# --- PS4 image geometry ---------------------------------------------------

STATIC_SIZE = (1920, 1080)          # texture/background/homescreen.png
PREVIEW_SIZE = (740, 416)           # texture/preview.png
THEME_ICON_SIZE = (512, 512)        # sce_sys/icon0.png
PIC1_SIZE = (1920, 1080)            # sce_sys/pic1.png
FUNCTION_ICON_SIZE = (128, 128)
FUNCTION_ICON_GLOW_SIZE = (152, 152)
CONTENT_ICON_SIZE = (512, 512)

#: DXT1 is fixed rate, so the exact size of a frame can be predicted.
#:   1280x720 -> 460,928 B   960x540 -> 259,328 B   640x360 -> 115,328 B
ANIMATED_SIZES: dict[str, tuple[int, int]] = {
    "720p (1280x720)": (1280, 720),
    "540p (960x540)": (960, 540),
    "360p (640x360)": (640, 360),
}
DEFAULT_RESOLUTION = "720p (1280x720)"

#: Measured on a real console: more than this in scene/background.raf makes
#: the theme fail with CE-38196-7 even though the console has lots of RAM.
RAF_SIZE_LIMIT = 6 * 1024 * 1024
#: A separate cap on the number of frames (48 tested working, 54 failing).
MAX_FRAME_COUNT = 48
MIN_FRAME_COUNT = 2
DEFAULT_FRAME_COUNT = 12

#: <case wait="..."> is in SECONDS and accepts decimals.
DEFAULT_WAIT_SECONDS = 0.1
MIN_WAIT_SECONDS = 0.02
MAX_WAIT_SECONDS = 5.0

# --- PS4 theme layout -----------------------------------------------------

THEME_PATH_HOMESCREEN = "texture/background/homescreen.png"
THEME_PATH_FUNCTIONSCREEN = "texture/background/functionscreen.png"
THEME_PATH_PREVIEW = "texture/preview.png"
THEME_PATH_THEME_XML = "theme.xml"
THEME_PATH_FUNCTION_ICONS = "texture/function_icon"
THEME_PATH_CONTENT_ICONS = "texture/content_icon"
THEME_PATH_RAF = "scene/background.raf"
THEME_PATH_MUSIC = "sound/bgm_home.at9"
THEME_PATH_ICON0 = "sce_sys/icon0.png"
THEME_PATH_PIC1 = "sce_sys/pic1.png"
THEME_PATH_SFO = "sce_sys/param.sfo"

FUNCTION_ICONS = [
    "community", "event", "friend", "message", "notification",
    "party", "power", "setting", "trophy",
]
CONTENT_ICONS = [
    "browser", "disc", "discoverlay", "folder", "gallery",
    "library", "livefromps", "shareplay", "tvvideo", "usbmusic",
]

ICON_LABELS: dict[str, str] = {
    "community": "Communities",
    "event": "Events",
    "friend": "Friends",
    "message": "Messages",
    "notification": "Notifications",
    "party": "Party",
    "power": "Power",
    "setting": "Settings",
    "trophy": "Trophies",
    "browser": "Browser",
    "disc": "Disc",
    "discoverlay": "Disc (overlay)",
    "folder": "Folder",
    "gallery": "Capture Gallery",
    "library": "Library",
    "livefromps": "Live from PlayStation",
    "shareplay": "Share Play",
    "tvvideo": "TV & Video",
    "usbmusic": "USB Music",
}

#: 0-7, exactly the numbers Sony documents inside theme.xml.
THEME_COLORS: list[tuple[int, str]] = [
    (0, "Blue (default)"),
    (1, "Pink"),
    (2, "Red"),
    (3, "Navy"),
    (4, "Dark grey"),
    (5, "Gold"),
    (6, "Light steel blue"),
    (7, "Purple"),
]

THEME_XML_DEFAULTS = {
    "fontcolor": "#FFFFFFFF",
    "fontshadowcolor": "#FF000000",
    "focuscolor": "#FF1E9BFF",
    "homescreen_dimmer": "#00FFFFFF",
    "functionscreen_dimmer": "#00FFFFFF",
    "titlename_dimmer": "#00FFFFFF",
}

# --- Package metadata -----------------------------------------------------

CONTENT_PREFIX = "UP9000"
DEFAULT_TITLE_ID = "CUSA00000"
PASSCODE = "0" * 32
SFO_VERSION = "01.00"
#: Makes the console treat the package as a theme instead of an application.
IRO_TAG = 2
CATEGORY = "ac"

# --- Dependency sources ---------------------------------------------------
#: Pinned downloads.  FFmpeg uses the official BtbN release feed and its
#: checksums.sha256; the other hashes were computed from the verified files.

FFMPEG_RELEASE_API = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
FFMPEG_ASSET_PATTERNS = [
    r"^ffmpeg-n\d+(?:\.\d+)?-latest-win64-lgpl-shared-\d+(?:\.\d+)?\.zip$",
    r"^ffmpeg-n\d+(?:\.\d+)?-latest-win64-gpl-shared-\d+(?:\.\d+)?\.zip$",
    r"^ffmpeg-master-latest-win64-gpl-shared\.zip$",
    r"^ffmpeg-n\d+(?:\.\d+)?-latest-win64-lgpl-\d+(?:\.\d+)?\.zip$",
    r"^ffmpeg-n\d+(?:\.\d+)?-latest-win64-gpl-\d+(?:\.\d+)?\.zip$",
]

PKGTOOL_URL = (
    "https://github.com/maxton/LibOrbisPkg/releases/download/v0.2/PkgTool-0.2.231.zip"
)
PKGTOOL_SHA256 = "c639e591e35c2431f68410d1771541d95f7308863638f9e3a6eedf1818530097"

AT9TOOL_URL = (
    "https://github.com/XyLe-GBP/ATRACTool-Reloaded/releases/download/"
    "v1.53.2620.913/ATRACTool-Rel-Portable.zip"
)
AT9TOOL_SHA256 = "cbac59b9f022ac110c071eae57b37c70ef418c0995331333cd22163a9b969687"
AT9TOOL_MEMBER = "release-portable/res/ps4_at9tool.exe"

MAX_SFX_SECONDS = 300

# --- File types -----------------------------------------------------------

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".gif", ".wmv", ".flv"}
AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wtv", ".at9"}

# --- UI palette -----------------------------------------------------------

class Colors:
    """Blue / white / cyan palette used by every screen."""

    NAVY = "#0B1B33"
    NAVY_SOFT = "#12294A"
    NAVY_LINE = "#1E3A61"
    PRIMARY = "#2563EB"
    PRIMARY_HOVER = "#1D4ED8"
    PRIMARY_SOFT = "#E8F0FE"
    CYAN = "#06B6D4"
    CYAN_BRIGHT = "#22D3EE"
    CYAN_SOFT = "#E0F7FB"
    BACKGROUND = "#F4F8FD"
    SURFACE = "#FFFFFF"
    SURFACE_ALT = "#F7FAFE"
    BORDER = "#D9E6F4"
    BORDER_STRONG = "#BFD6EC"
    TEXT = "#0F2440"
    TEXT_SOFT = "#5B7290"
    TEXT_FAINT = "#8AA0B8"
    SUCCESS = "#0E9F6E"
    SUCCESS_SOFT = "#E3F7EF"
    WARNING = "#B45309"
    WARNING_SOFT = "#FEF3E2"
    DANGER = "#DC2626"
    DANGER_SOFT = "#FDECEC"
    WHITE = "#FFFFFF"

    #: Gradient stops for the brand mark and progress accents.
    GRADIENT = ("#2563EB", "#06B6D4")


# --- Paths ----------------------------------------------------------------

def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Folder that holds the source tree (or the exe when frozen)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(name: str) -> Path:
    """Bundled asset path that works in a source tree and in PyInstaller."""
    bundle = getattr(sys, "_MEIPASS", None)
    base = Path(bundle) if bundle else project_root()
    return base / "assets" / name


def _local_app_data() -> Path:
    raw = os.environ.get("LOCALAPPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Local"


def config_dir() -> Path:
    """Where settings and downloaded tools are kept."""
    override = os.environ.get("PS4THEME_CONFIG_DIR")
    base = Path(override) if override else _local_app_data() / APP_NAME.replace(" ", "")
    base.mkdir(parents=True, exist_ok=True)
    return base


def tools_dir() -> Path:
    """Dependency folder.

    Source checkouts keep the binaries inside ``tools/`` so the project stays
    self contained.  A frozen build writes to LocalAppData, which is always
    writable even when the app lives in Program Files.
    """
    override = os.environ.get("PS4THEME_TOOLS_DIR")
    if override:
        path = Path(override)
    elif is_frozen():
        path = config_dir() / "tools"
    else:
        path = project_root() / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- Derived helpers ------------------------------------------------------

def dds_size_for(width: int, height: int) -> int:
    """Exact size of a DXT1 DDS without mipmaps."""
    blocks = ((width + 3) // 4) * ((height + 3) // 4)
    return 128 + blocks * 8


def max_frames_for(width: int, height: int) -> int:
    """Frame cap for a resolution: the tighter of byte budget and count cap."""
    return min(RAF_SIZE_LIMIT // dds_size_for(width, height), MAX_FRAME_COUNT)


def resolution_size(label: str) -> tuple[int, int]:
    return ANIMATED_SIZES.get(label, ANIMATED_SIZES[DEFAULT_RESOLUTION])


def default_projects_dir() -> Path:
    docs = Path.home() / "Documents"
    if not docs.is_dir():
        docs = Path.home()
    return docs / "PS4 Theme Projects"
