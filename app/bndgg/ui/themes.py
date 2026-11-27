"""Theme system: palettes + generated Qt stylesheet.

Six built-in themes. The stylesheet is produced from a palette with
`string.Template`, so a theme is just a dict of colours.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from string import Template

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication

DARK = {
    "midnight": {
        "label": "Midnight",
        "dark": True,
        "bg": "#0e1320",
        "sidebar": "#121929",
        "surface": "#17202f",
        "surface_alt": "#1e2839",
        "hover": "#25314a",
        "border": "#26324a",
        "border_strong": "#35456a",
        "text": "#e9eefb",
        "muted": "#94a3bd",
        "faint": "#6b7a94",
        "accent": "#4f8cff",
        "accent_hover": "#6ba0ff",
        "accent_pressed": "#3d78e6",
        "accent_soft": "rgba(79, 140, 255, 0.16)",
        "on_accent": "#ffffff",
        "danger": "#ef5a5f",
        "danger_hover": "#ff7378",
        "success": "#35c48a",
        "warning": "#f0a93c",
    },
    "graphite": {
        "label": "Graphite",
        "dark": True,
        "bg": "#15171b",
        "sidebar": "#1a1d22",
        "surface": "#1f232a",
        "surface_alt": "#262b33",
        "hover": "#2e343e",
        "border": "#303743",
        "border_strong": "#414a59",
        "text": "#eceff4",
        "muted": "#9aa4b4",
        "faint": "#707a8a",
        "accent": "#8b7cf6",
        "accent_hover": "#a094ff",
        "accent_pressed": "#7364e0",
        "accent_soft": "rgba(139, 124, 246, 0.18)",
        "on_accent": "#ffffff",
        "danger": "#f06a6f",
        "danger_hover": "#ff8287",
        "success": "#3ecf94",
        "warning": "#f2ae42",
    },
    "nord": {
        "label": "Nord",
        "dark": True,
        "bg": "#2e3440",
        "sidebar": "#2b303b",
        "surface": "#343b49",
        "surface_alt": "#3b4252",
        "hover": "#434c5e",
        "border": "#434c5e",
        "border_strong": "#4c566a",
        "text": "#eceff4",
        "muted": "#a7b1c4",
        "faint": "#7d879b",
        "accent": "#88c0d0",
        "accent_hover": "#9fd0dd",
        "accent_pressed": "#6fadbf",
        "accent_soft": "rgba(136, 192, 208, 0.18)",
        "on_accent": "#22303a",
        "danger": "#e37d7d",
        "danger_hover": "#f29393",
        "success": "#a3be8c",
        "warning": "#ebcb8b",
    },
    "forest": {
        "label": "Forest",
        "dark": True,
        "bg": "#0e1713",
        "sidebar": "#121e19",
        "surface": "#16261f",
        "surface_alt": "#1c3027",
        "hover": "#233d31",
        "border": "#274435",
        "border_strong": "#356049",
        "text": "#e6f3ec",
        "muted": "#92b4a3",
        "faint": "#6a8a79",
        "accent": "#45c98b",
        "accent_hover": "#5fdda1",
        "accent_pressed": "#33b077",
        "accent_soft": "rgba(69, 201, 139, 0.16)",
        "on_accent": "#06231a",
        "danger": "#e8636a",
        "danger_hover": "#f67d84",
        "success": "#45c98b",
        "warning": "#e8b04b",
    },
    "porcelain": {
        "label": "Porcelain",
        "dark": False,
        "bg": "#f3f5f9",
        "sidebar": "#ffffff",
        "surface": "#ffffff",
        "surface_alt": "#f1f4f9",
        "hover": "#e8eef9",
        "border": "#dde4ef",
        "border_strong": "#c3cede",
        "text": "#141c28",
        "muted": "#5d6b80",
        "faint": "#8a97a9",
        "accent": "#2f6df6",
        "accent_hover": "#4b83ff",
        "accent_pressed": "#2459d4",
        "accent_soft": "rgba(47, 109, 246, 0.12)",
        "on_accent": "#ffffff",
        "danger": "#d93a41",
        "danger_hover": "#ea5158",
        "success": "#1f9d63",
        "warning": "#c07d13",
    },
    "sand": {
        "label": "Sand",
        "dark": False,
        "bg": "#faf6f0",
        "sidebar": "#fffdf9",
        "surface": "#fffdf9",
        "surface_alt": "#f4ede1",
        "hover": "#ece2d2",
        "border": "#e5dbca",
        "border_strong": "#cfc0a8",
        "text": "#2b241b",
        "muted": "#6f6353",
        "faint": "#948671",
        "accent": "#bf6a38",
        "accent_hover": "#d07c47",
        "accent_pressed": "#a4582c",
        "accent_soft": "rgba(191, 106, 56, 0.13)",
        "on_accent": "#fffaf4",
        "danger": "#c0392b",
        "danger_hover": "#d64b3d",
        "success": "#2f8f5b",
        "warning": "#b07a17",
    },
}

THEMES = DARK
THEME_ORDER = ["midnight", "graphite", "nord", "forest", "porcelain", "sand"]

_current = {"name": "midnight"}


def theme(name: str) -> dict:
    return THEMES.get(name, THEMES["midnight"])


def current() -> dict:
    return theme(_current["name"])


def set_current(name: str) -> None:
    _current["name"] = name if name in THEMES else "midnight"


def current_name() -> str:
    return _current["name"]


# --------------------------------------------------------------------------
# Runtime-drawn assets referenced from QSS (Qt has no CSS checkmarks).
# --------------------------------------------------------------------------
_ASSET_DIR = Path(tempfile.gettempdir()) / "bndgg-ui"


def _asset_dir() -> Path:
    _ASSET_DIR.mkdir(parents=True, exist_ok=True)
    return _ASSET_DIR


def _save(pixmap: QPixmap, name: str) -> str:
    path = _asset_dir() / name
    pixmap.save(str(path), "PNG")
    return str(path).replace("\\", "/")


def _check_asset(color: str) -> str:
    name = f"check_{color.lstrip('#')}.png"
    path = _asset_dir() / name
    if not path.exists():
        pm = QPixmap(36, 36)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color), 4.4, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(8, 19), QPointF(15, 26), QPointF(28, 10)])
        painter.end()
        pm.save(str(path), "PNG")
    return str(path).replace("\\", "/")


def _chevron_asset(color: str) -> str:
    name = f"chevron_{color.lstrip('#')}.png"
    path = _asset_dir() / name
    if not path.exists():
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color), 3.2, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(8, 13), QPointF(16, 21), QPointF(24, 13)])
        painter.end()
        pm.save(str(path), "PNG")
    return str(path).replace("\\", "/")


_QSS = Template(
    """
* { outline: none; }
QWidget { color: $text; font-size: 13px; background: transparent; }
QMainWindow, QDialog { background: $bg; }
QToolTip {
    background: $surface_alt; color: $text; border: 1px solid $border;
    border-radius: 6px; padding: 6px 8px;
}

#Root { background: $bg; }
#Sidebar { background: $sidebar; border-right: 1px solid $border; }
#Card { background: $surface; border: 1px solid $border; border-radius: $radius; }
#CardAlt { background: $surface_alt; border: 1px solid $border; border-radius: $radius; }
#Inset { background: $surface_alt; border-radius: 10px; }
#Divider { background: $border; border: none; }
#HeaderBar { background: $bg; border-bottom: 1px solid $border; }

QLabel { background: transparent; }
QLabel[role="display"] { font-size: 30px; font-weight: 800; letter-spacing: 1px; }
QLabel[role="h1"] { font-size: 22px; font-weight: 700; }
QLabel[role="h2"] { font-size: 16px; font-weight: 700; }
QLabel[role="h3"] { font-size: 13px; font-weight: 700; }
QLabel[role="muted"] { color: $muted; }
QLabel[role="faint"] { color: $faint; font-size: 12px; }
QLabel[role="danger"] { color: $danger; }
QLabel[role="success"] { color: $success; }
QLabel[role="warning"] { color: $warning; }
QLabel[role="mono"] {
    font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
    font-size: 14px; letter-spacing: 0.5px;
}
QLabel[role="chip"] {
    background: $accent_soft; color: $accent; border-radius: 9px;
    padding: 3px 9px; font-size: 11px; font-weight: 700;
}

QPushButton {
    background: $surface_alt; color: $text; border: 1px solid $border;
    border-radius: 9px; padding: 9px 16px; font-weight: 600;
}
QPushButton:hover { background: $hover; border-color: $border_strong; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $faint; border-color: $border; background: transparent; }
QPushButton:focus { border-color: $accent; }
QPushButton[variant="primary"] {
    background: $accent; color: $on_accent; border: 1px solid $accent;
}
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:pressed { background: $accent_pressed; }
QPushButton[variant="primary"]:disabled {
    background: $surface_alt; color: $faint; border-color: $border;
}
QPushButton[variant="danger"] {
    background: transparent; color: $danger; border: 1px solid $danger;
}
QPushButton[variant="danger"]:hover { background: $danger; color: #ffffff; }
QPushButton[variant="ghost"] {
    background: transparent; border: 1px solid transparent; color: $muted;
}
QPushButton[variant="ghost"]:hover { background: $surface_alt; color: $text; }
QPushButton[variant="icon"] {
    background: transparent; border: none; padding: 5px; border-radius: 7px;
}
QPushButton[variant="icon"]:hover { background: $surface_alt; }
QPushButton[variant="icon"]:pressed { background: $border; }
QPushButton[nav="true"] {
    background: transparent; border: none; text-align: left;
    padding: 11px 14px; border-radius: 9px; color: $muted; font-weight: 600;
}
QPushButton[nav="true"]:hover { background: $surface_alt; color: $text; }
QPushButton[nav="true"]:checked { background: $accent_soft; color: $accent; }

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background: $surface_alt; border: 1px solid $border; border-radius: 9px;
    padding: 9px 11px; selection-background-color: $accent;
    selection-color: $on_accent;
}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QComboBox:hover {
    border-color: $border_strong;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: $accent;
}
QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled { color: $faint; }
QLineEdit[flat="true"] {
    background: transparent; border: 1px solid transparent;
}
QLineEdit[flat="true"]:hover { border-color: $border; }
QLineEdit[flat="true"]:focus { background: $surface_alt; border-color: $accent; }

QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: url("$chevron"); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: $surface; border: 1px solid $border; border-radius: 8px;
    padding: 4px; outline: none;
    selection-background-color: $accent_soft; selection-color: $text;
}

QCheckBox { spacing: 9px; background: transparent; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid $border_strong; background: $surface_alt;
}
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked {
    background: $accent; border-color: $accent; image: url("$check");
}

QRadioButton { spacing: 9px; }
QRadioButton::indicator {
    width: 16px; height: 16px; border-radius: 9px;
    border: 1px solid $border_strong; background: $surface_alt;
}
QRadioButton::indicator:checked { border: 5px solid $accent; background: $surface; }

QSlider::groove:horizontal {
    height: 6px; background: $surface_alt; border-radius: 3px;
}
QSlider::sub-page:horizontal { background: $accent; border-radius: 3px; }
QSlider::handle:horizontal {
    background: $text; width: 16px; height: 16px; margin: -6px 0;
    border-radius: 8px; border: 2px solid $surface;
}
QSlider::handle:horizontal:hover { background: $accent; }

QTableWidget {
    background: transparent; border: none; gridline-color: transparent;
    selection-background-color: $accent_soft; selection-color: $text;
    alternate-background-color: transparent;
}
QTableWidget::item { padding: 10px 12px; border-bottom: 1px solid $border; }
QTableWidget::item:selected { background: $accent_soft; color: $text; }
QTableWidget::item:hover { background: $surface_alt; }
QHeaderView::section {
    background: transparent; color: $faint; border: none;
    border-bottom: 1px solid $border; padding: 8px 12px;
    font-size: 11px; font-weight: 700;
}

QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 9px 10px; border-radius: 7px; }
QListWidget::item:selected { background: $accent_soft; color: $text; }
QListWidget::item:hover { background: $surface_alt; }

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: $border_strong; min-height: 32px; border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal {
    background: $border_strong; min-width: 32px; border-radius: 5px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 10px; }

QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    background: transparent; color: $muted; padding: 8px 16px;
    border: none; border-bottom: 2px solid transparent; font-weight: 600;
}
QTabBar::tab:hover { color: $text; }
QTabBar::tab:selected { color: $text; border-bottom: 2px solid $accent; }

QMenu {
    background: $surface; border: 1px solid $border; border-radius: 9px;
    padding: 5px;
}
QMenu::item { padding: 8px 26px 8px 12px; border-radius: 6px; }
QMenu::item:selected { background: $surface_alt; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }

QProgressBar {
    background: $surface_alt; border: none; border-radius: 4px;
    text-align: center; color: $muted; font-size: 11px;
}
QProgressBar::chunk { background: $accent; border-radius: 4px; }

QMessageBox { background: $surface; }
QMessageBox QLabel { color: $text; }

QToolButton { background: transparent; border: none; border-radius: 7px; padding: 5px; }
QToolButton:hover { background: $surface_alt; }

QSpinBox::up-button, QSpinBox::down-button { width: 18px; border: none; }
QSpinBox::up-arrow, QSpinBox::down-arrow { width: 9px; height: 9px; }

QFrame[role="separator"] { background: $border; max-height: 1px; border: none; }
"""
)


def build_qss(name: str) -> str:
    t = theme(name)
    t = dict(t)
    t["radius"] = "12px"
    t["check"] = _check_asset(t["on_accent"])
    t["chevron"] = _chevron_asset(t["muted"])
    return _QSS.substitute(t)


def build_palette(name: str) -> QPalette:
    t = theme(name)
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: t["bg"],
        QPalette.ColorRole.WindowText: t["text"],
        QPalette.ColorRole.Base: t["surface_alt"],
        QPalette.ColorRole.AlternateBase: t["surface"],
        QPalette.ColorRole.Text: t["text"],
        QPalette.ColorRole.Button: t["surface_alt"],
        QPalette.ColorRole.ButtonText: t["text"],
        QPalette.ColorRole.Highlight: t["accent"],
        QPalette.ColorRole.HighlightedText: t["on_accent"],
        QPalette.ColorRole.ToolTipBase: t["surface"],
        QPalette.ColorRole.ToolTipText: t["text"],
        QPalette.ColorRole.PlaceholderText: t["faint"],
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
                     QColor(t["faint"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,
                     QColor(t["faint"]))
    return palette


def apply_theme(app: QApplication, name: str) -> None:
    set_current(name)
    app.setStyle("Fusion")
    app.setPalette(build_palette(name))
    app.setStyleSheet(build_qss(name))
