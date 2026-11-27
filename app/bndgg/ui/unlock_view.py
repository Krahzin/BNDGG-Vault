"""Lock screen / first-run welcome screen."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from . import icons, themes
from .widgets import Card, GhostButton, PasswordEdit, PrimaryButton


class UnlockView(QWidget):
    unlock_requested = Signal(str)
    create_requested = Signal()
    open_requested = Signal()
    open_path_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Root")
        self._busy = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.card = Card(padding=34, spacing=14)
        self.card.setFixedWidth(460)
        row.addWidget(self.card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

        body = self.card.body

        mark = QLabel()
        mark.setPixmap(icons.icon("shield", themes.current()["accent"], 40).pixmap(40, 40))
        mark.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(mark)

        self.title = QLabel("BNDGG VAULT")
        self.title.setProperty("role", "display")
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(self.title)

        self.subtitle = QLabel("Enter your master password to unlock")
        self.subtitle.setProperty("role", "muted")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(self.subtitle)

        self.vault_label = QLabel("")
        self.vault_label.setProperty("role", "faint")
        self.vault_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.vault_label.setWordWrap(True)
        body.addWidget(self.vault_label)

        self.password = PasswordEdit("Master password", reveal_seconds=0)
        self.password.returnPressed.connect(self._submit)
        body.addWidget(self.password)

        self.error = QLabel("")
        self.error.setProperty("role", "danger")
        self.error.setWordWrap(True)
        self.error.hide()
        body.addWidget(self.error)

        self.unlock_btn = PrimaryButton("Unlock vault", "unlock")
        self.unlock_btn.clicked.connect(self._submit)
        body.addWidget(self.unlock_btn)

        self.links = QWidget()
        links = QHBoxLayout(self.links)
        links.setContentsMargins(0, 4, 0, 0)
        links.setSpacing(6)
        links.addStretch(1)
        self.create_btn = GhostButton("Create new vault", "plus")
        self.create_btn.clicked.connect(self.create_requested.emit)
        self.open_btn = GhostButton("Open vault…", "folder")
        self.open_btn.clicked.connect(self.open_requested.emit)
        links.addWidget(self.create_btn)
        links.addWidget(self.open_btn)
        links.addStretch(1)
        body.addWidget(self.links)

        self.recent_box = QWidget()
        self.recent_layout = QVBoxLayout(self.recent_box)
        self.recent_layout.setContentsMargins(0, 6, 0, 0)
        self.recent_layout.setSpacing(2)
        body.addWidget(self.recent_box)
        self.recent_box.hide()

        footer = QLabel(f"v{__version__}  ·  Argon2id + AES-256-GCM  ·  zero-knowledge")
        footer.setProperty("role", "faint")
        footer.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(footer)

    # -- state -------------------------------------------------------------
    def configure(self, vault_path: str, recent: list[str]) -> None:
        has_vault = bool(vault_path) and os.path.exists(vault_path)
        self.password.setVisible(has_vault)
        self.unlock_btn.setVisible(has_vault)
        self.subtitle.setText(
            "Enter your master password to unlock" if has_vault
            else "No vault selected yet. Create one, or open an existing vault."
        )
        if has_vault:
            name = os.path.basename(vault_path)
            folder = os.path.dirname(vault_path)
            self.vault_label.setText(f"{name}  ·  {folder}")
        else:
            self.vault_label.setText("")

        for i in reversed(range(self.recent_layout.count())):
            item = self.recent_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

        shown = [p for p in recent if p != vault_path][:3]
        if not shown:
            self.recent_box.hide()
            return
        label = QLabel("Recent vaults")
        label.setProperty("role", "faint")
        self.recent_layout.addWidget(label)
        for path in shown:
            button = QPushButton(os.path.basename(path))
            button.setProperty("variant", "ghost")
            button.setToolTip(path)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _=False, p=path: self.open_path_requested.emit(p)
            )
            self.recent_layout.addWidget(button)
        self.recent_box.show()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.unlock_btn.setEnabled(not busy)
        self.unlock_btn.setText("Unlocking…" if busy else "Unlock vault")
        self.password.edit.setEnabled(not busy)

    def show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.setVisible(bool(message))
        self.password.edit.selectAll()
        self.password.setFocus()

    def clear_error(self) -> None:
        self.error.hide()

    def focus_password(self) -> None:
        self.password.setFocus()

    # -- actions -----------------------------------------------------------
    def _submit(self) -> None:
        if self._busy:
            return
        password = self.password.text()
        if not password:
            self.show_error("Enter your master password.")
            return
        self.clear_error()
        self.unlock_requested.emit(password)
