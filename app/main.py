"""BNDGG Vault — entry point."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from bndgg import APP_NAME, ORG_NAME, __version__
from bndgg.core.settings import AppSettings
from bndgg.ui import icons, themes
from bndgg.ui.main_window import MainWindow


def resource_path(name: str) -> str:
    """Locate a resource in dev (app/ + project/) or a PyInstaller bundle."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return os.path.join(bundle, name)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, name),
        os.path.join(os.path.dirname(here), "project", name),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[-1]


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("bndgg-vault")

    font = QFont("Segoe UI Variable Text")
    font.setPointSize(10)
    app.setFont(font)

    icon_path = resource_path("bndgg.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    settings = AppSettings()
    themes.apply_theme(app, str(settings.get("theme")))

    window = MainWindow(settings)
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
