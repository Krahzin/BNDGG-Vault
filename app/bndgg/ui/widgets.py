"""Reusable widgets: cards, icon buttons, password field, strength meter, toast."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import icons, themes


def tint(name: str, role: str = "muted", size: int = 18) -> "object":
    return icons.icon(name, themes.current()[role], size)


def _remember(button: QPushButton, name: str, role: str, size: int) -> None:
    button.setProperty("iconName", name)
    button.setProperty("iconRole", role)
    button.setProperty("iconPx", size)


def refresh_icons(root: QWidget) -> None:
    """Recolour every button whose icon was created from the theme palette."""
    for button in root.findChildren(QPushButton):
        name = button.property("iconName")
        if not name:
            continue
        role = button.property("iconRole") or "muted"
        size = button.property("iconPx") or 18
        button.setIcon(icons.icon(str(name), themes.current()[str(role)], int(size)))


class Card(QFrame):
    """Rounded surface panel with an optional title row."""

    def __init__(self, parent: QWidget | None = None, *, padding: int = 18,
                 spacing: int = 12) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)

    def add_title(self, text: str, subtitle: str = "") -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "h2")
        self.body.addWidget(label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setProperty("role", "muted")
            sub.setWordWrap(True)
            self.body.addWidget(sub)
        return label


class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str = "", *, role: str = "muted",
                 size: int = 18, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("variant", "icon")
        self._icon_name = icon_name
        self.setIcon(icons.icon(icon_name, themes.current()[role], size))
        _remember(self, icon_name, role, size)
        self.setIconSize(QSize(size, size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(32, 32)
        if tooltip:
            self.setToolTip(tooltip)

    def recolor(self, role: str = "muted", size: int = 18) -> None:
        self.setIcon(icons.icon(self._icon_name, themes.current()[role], size))


class PrimaryButton(QPushButton):
    def __init__(self, text: str, icon_name: str | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("variant", "primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        if icon_name:
            self.setIcon(icons.icon(icon_name, themes.current()["on_accent"], 17))
            _remember(self, icon_name, "on_accent", 17)
            self.setIconSize(QSize(17, 17))


class DangerButton(QPushButton):
    def __init__(self, text: str, icon_name: str | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("variant", "danger")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        if icon_name:
            self.setIcon(icons.icon(icon_name, themes.current()["danger"], 16))
            _remember(self, icon_name, "danger", 16)


class GhostButton(QPushButton):
    def __init__(self, text: str, icon_name: str | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("variant", "ghost")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon_name:
            self.setIcon(icons.icon(icon_name, themes.current()["muted"], 16))
            _remember(self, icon_name, "muted", 16)


class PasswordEdit(QWidget):
    """A line edit with a reveal toggle that auto-hides after a timeout."""

    textChanged = Signal(str)
    returnPressed = Signal()

    def __init__(self, placeholder: str = "Password", parent: QWidget | None = None,
                 reveal_seconds: int = 0) -> None:
        super().__init__(parent)
        self._reveal_seconds = reveal_seconds
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self.textChanged.emit)
        self.edit.returnPressed.connect(self.returnPressed.emit)
        layout.addWidget(self.edit, 1)

        self.toggle = IconButton("eye", "Show password")
        self.toggle.clicked.connect(self.toggle_visibility)
        layout.addWidget(self.toggle)

    # -- API ---------------------------------------------------------------
    def text(self) -> str:
        return self.edit.text()

    def setText(self, value: str) -> None:
        self.edit.setText(value)

    def clear(self) -> None:
        self.edit.clear()

    def setPlaceholderText(self, text: str) -> None:
        self.edit.setPlaceholderText(text)

    def setFocus(self) -> None:  # noqa: N802 - Qt naming
        self.edit.setFocus()

    def is_revealed(self) -> bool:
        return self.edit.echoMode() == QLineEdit.EchoMode.Normal

    def toggle_visibility(self) -> None:
        if self.is_revealed():
            self.hide_text()
        else:
            self.show_text()

    def show_text(self) -> None:
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.toggle.setIcon(icons.icon("eye_off", themes.current()["accent"], 18))
        self.toggle.setToolTip("Hide password")
        if self._reveal_seconds:
            self._timer.start(self._reveal_seconds * 1000)

    def hide_text(self) -> None:
        self._timer.stop()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle.setIcon(icons.icon("eye", themes.current()["muted"], 18))
        self.toggle.setToolTip("Show password")


class StrengthMeter(QWidget):
    """Five-segment strength bar with an optional caption."""

    def __init__(self, parent: QWidget | None = None, *, show_label: bool = True) -> None:
        super().__init__(parent)
        self._score = -1
        self._bits = 0.0
        self._caption = ""
        self._color = themes.current()["border"]
        self._show_label = show_label
        self.setMinimumHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_strength(self, score: int, caption: str, color: str) -> None:
        self._score = score
        self._caption = caption
        self._color = themes.current().get(color, color)
        self.update()

    def reset(self) -> None:
        self._score = -1
        self._caption = ""
        self._color = themes.current()["border"]
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = themes.current()
        segments = 5
        gap = 4
        bar_height = 5
        width = self.width()
        seg_width = max(8.0, (width - gap * (segments - 1)) / segments)
        filled = self._score + 1 if self._score >= 0 else 0

        for index in range(segments):
            x = index * (seg_width + gap)
            rect = QRectF(x, 0, seg_width, bar_height)
            color = QColor(self._color if index < filled else palette["border"])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 2.5, 2.5)

        if self._show_label and self._caption:
            painter.setPen(QColor(palette["muted"]))
            font = painter.font()
            font.setPointSizeF(8.6)
            painter.setFont(font)
            painter.drawText(
                QRectF(0, bar_height + 3, width, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._caption,
            )
        painter.end()


class Toast(QFrame):
    """Transient status pill shown over the main window."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("CardAlt")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 9, 16, 9)
        layout.setSpacing(8)
        self._icon = QLabel()
        self._text = QLabel("")
        layout.addWidget(self._icon)
        layout.addWidget(self._text)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text: str, kind: str = "success", msec: int = 2200) -> None:
        palette = themes.current()
        color = palette.get(kind, palette["success"])
        icon_name = {"success": "check", "danger": "alert", "warning": "alert"}.get(
            kind, "info"
        )
        self._icon.setPixmap(icons.icon(icon_name, color, 16).pixmap(16, 16))
        self._text.setText(text)
        self._text.setStyleSheet(f"color: {palette['text']}; font-weight: 600;")
        self.adjustSize()
        self._reposition()
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()
        self._timer.start(msec)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._maybe_hide)
        self._anim.start()

    def _maybe_hide(self) -> None:
        try:
            self._anim.finished.disconnect(self._maybe_hide)
        except (RuntimeError, TypeError):
            pass
        if self._effect.opacity() < 0.05:
            self.hide()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 24
        self.move(QPoint(max(12, x), max(12, y)))


class Separator(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "separator")
        self.setFixedHeight(1)


class TagChip(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("role", "chip")
