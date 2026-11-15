"""PS4 Theme Tools - entry point.

Usage:
    python app.py                       open the app
    python app.py --self-test           run the built-in format checks
    python app.py --build PROJECT       build a project without the UI
    python app.py --version             print the version
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
import traceback
from pathlib import Path

from ps4theme import APP_NAME, APP_VERSION
from ps4theme import constants as C
from ps4theme import models
from ps4theme.builder import BuildError, build_cli
from ps4theme.selftest import run_self_test
from ps4theme.settings import Settings


def _enable_dpi_awareness() -> None:
    """Crisp text on high-DPI screens; harmless elsewhere."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
        except Exception:
            pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PS4 Theme Tools",
        description="Create, preview and package static or dynamic PS4 themes.",
    )
    parser.add_argument(
        "project",
        nargs="?",
        help="project folder to open in the UI (default: the last project)",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run format and installation checks, then exit",
    )
    parser.add_argument(
        "--build",
        metavar="PROJECT",
        help="build a project folder without opening the UI",
    )
    parser.add_argument(
        "--output",
        metavar="FOLDER",
        help="output folder for --build (default: the settings value or project/dist)",
    )
    parser.add_argument(
        "--no-package",
        action="store_true",
        help="with --build: produce the theme folder but skip the .pkg",
    )
    parser.add_argument(
        "--auto-install",
        action="store_true",
        help="with --build: download missing dependencies automatically",
    )
    parser.add_argument(
        "--page",
        default="theme",
        choices=["theme", "icons", "appearance", "build", "guide", "tools"],
        help="start the UI on this tab (default: theme)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print tracebacks from --self-test",
    )
    parser.add_argument(
        "--no-dialog",
        action="store_true",
        help="with --self-test in the windowed build: write the report but do not show a dialog",
    )
    return parser


def _dialog(title: str, message: str, *, error: bool = False) -> None:
    """Native message box, used when the windowed exe has no console."""
    if os.name != "nt":
        return
    try:
        import ctypes

        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(None, message, title, flags)  # type: ignore[attr-defined]
    except Exception:
        pass


def _run_self_test(args, *, windowed: bool) -> int:
    if not windowed:
        return run_self_test(verbose=args.verbose)

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = run_self_test(verbose=args.verbose)
    report = buffer.getvalue()
    log_path = C.config_dir() / "self-test.log"
    try:
        log_path.write_text(report, encoding="utf-8")
    except OSError:
        log_path = Path(".")

    if not args.no_dialog and os.environ.get("PS4THEME_SELFTEST_QUIET") != "1":
        summary = "All checks passed." if code == 0 else "One or more checks failed."
        _dialog(
            f"{APP_NAME} self test",
            f"{summary}\n\nReport: {log_path}\n\n{report[-2500:]}",
            error=code != 0,
        )
    return code


def _run_build(args) -> int:
    folder = Path(args.build).expanduser()
    if not (folder / C.PROJECT_FILE_NAME).is_file():
        print(f"No {C.PROJECT_FILE_NAME} found in {folder}.", file=sys.stderr)
        return 2
    output = Path(args.output).expanduser() if args.output else None
    try:
        result = build_cli(
            folder,
            output_dir=output,
            package=not args.no_package,
            auto_install=bool(args.auto_install),
        )
    except (models.ProjectError, BuildError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - unexpected CLI failure
        print(f"Build failed: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return 1

    print()
    print(f"Theme folder: {result.content_dir}")
    if result.pkg_path:
        print(f"Package:      {result.pkg_path}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    return 0


def _run_gui(args) -> int:
    _enable_dpi_awareness()
    from ps4theme.ui.app import ThemeToolsApp, AppState, load_initial_state

    if args.project:
        folder = Path(args.project).expanduser()
        try:
            project = models.Project.load(folder)
        except models.ProjectError as exc:
            print(f"Cannot open {folder}: {exc}", file=sys.stderr)
            return 2
        settings = Settings.load()
        settings.remember_project(project.root)
        try:
            settings.save()
        except OSError:
            pass
        state = AppState(settings=settings, project=project)
    else:
        state = load_initial_state()

    app = ThemeToolsApp(state, start_page=args.page)
    app.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    windowed = sys.stdout is None
    if windowed:
        # PyInstaller's windowed bootloader leaves these as None.  Most code
        # (argparse, logs) expects a writable stream.
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = sys.stdout

    args = _parser().parse_args(argv)

    if args.self_test:
        return _run_self_test(args, windowed=windowed)
    if args.build:
        code = _run_build(args)
        if code and windowed:
            _dialog(f"{APP_NAME} build", "The build failed. See the log output for details.", error=True)
        return code
    try:
        return _run_gui(args)
    except Exception as exc:  # pragma: no cover - last-resort GUI boundary
        if windowed:
            _dialog(
                f"{APP_NAME} error",
                f"{exc}\n\n{traceback.format_exc()}",
                error=True,
            )
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
