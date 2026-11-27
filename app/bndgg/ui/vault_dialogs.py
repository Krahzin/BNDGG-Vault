"""Dialogs for creating and opening vaults."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..core.strength import estimate
from .widgets import GhostButton, PasswordEdit, PrimaryButton, StrengthMeter


def _default_path() -> str:
    documents = Path.home() / "Documents"
    if not documents.exists():
        documents = Path.home()
    return str(documents / "BNDGG" / "vault.json")


class CreateVaultDialog(QDialog):
    def __init__(self, parent: QWidget | None = None,
                 initial_path: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create vault")
        self.setModal(True)
        self.setMinimumWidth(540)
        self.path = ""
        self.password = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(12)

        title = QLabel("Create a new vault")
        title.setProperty("role", "h1")
        root.addWidget(title)
        subtitle = QLabel(
            "Pick where the encrypted file should live. You choose the folder — "
            "nothing is written to AppData."
        )
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        label = QLabel("Vault file")
        label.setProperty("role", "h3")
        root.addWidget(label)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.path_edit = QLineEdit(initial_path or _default_path())
        row.addWidget(self.path_edit, 1)
        browse = GhostButton("Browse…", "folder")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        root.addLayout(row)

        pw_label = QLabel("Master password")
        pw_label.setProperty("role", "h3")
        root.addWidget(pw_label)
        self.pw = PasswordEdit("Choose a strong master password", reveal_seconds=0)
        self.pw.textChanged.connect(self._update_strength)
        root.addWidget(self.pw)

        self.confirm = PasswordEdit("Repeat it", reveal_seconds=0)
        root.addWidget(self.confirm)

        self.meter = StrengthMeter()
        root.addWidget(self.meter)

        warning = QLabel(
            "There is no recovery. If you forget this password, the vault "
            "cannot be opened by anyone — including you."
        )
        warning.setProperty("role", "faint")
        warning.setWordWrap(True)
        root.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = GhostButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        create = PrimaryButton("Create vault", "shield")
        create.clicked.connect(self._create)
        buttons.addWidget(create)
        root.addLayout(buttons)

        self.pw.setFocus()

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Where should the vault live?", self.path_edit.text(),
            "BNDGG vault (*.json);;All files (*)",
        )
        if path:
            self.path_edit.setText(path)

    def _update_strength(self, text: str) -> None:
        if not text:
            self.meter.reset()
            return
        result = estimate(text)
        self.meter.set_strength(
            result.score,
            f"{result.label} · {result.bits:.0f} bits · cracked in {result.crack_time}",
            result.color,
        )

    def _create(self) -> None:
        path = self.path_edit.text().strip()
        password = self.pw.text()
        confirm = self.confirm.text()

        if not path:
            QMessageBox.warning(self, "Missing path", "Choose where to save the vault.")
            return
        if os.path.isdir(path):
            QMessageBox.warning(self, "Invalid path", "That is a folder, not a file.")
            return
        parent = os.path.dirname(os.path.abspath(path))
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Cannot use that folder", str(exc))
            return
        if os.path.exists(path):
            answer = QMessageBox.question(
                self, "File exists",
                "A file already exists there. Overwrite it with a new, empty vault?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if len(password) < 8:
            QMessageBox.warning(self, "Too short",
                                "Use a master password of at least 8 characters.")
            self.pw.setFocus()
            return
        if password != confirm:
            QMessageBox.warning(self, "Mismatch", "The passwords do not match.")
            self.confirm.setFocus()
            return
        if estimate(password).score < 2:
            answer = QMessageBox.question(
                self, "Weak master password",
                "This password is weak. The vault's security depends on it.\n\n"
                "Use it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.path = path
        self.password = password
        self.accept()
