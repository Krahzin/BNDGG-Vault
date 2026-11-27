"""Add / edit entry dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import generator, totp
from ..core.settings import AppSettings
from ..core.strength import estimate
from ..core.vault import Entry, Vault
from . import icons, themes
from .widgets import GhostButton, IconButton, PasswordEdit, PrimaryButton, StrengthMeter


def _label(text: str, hint: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "h3")
    if hint:
        label.setToolTip(hint)
    return label


class EntryDialog(QDialog):
    def __init__(self, parent: QWidget, vault: Vault, settings: AppSettings,
                 entry: Entry | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.settings = settings
        self.entry = entry
        self.saved_entry: Entry | None = None

        self.setWindowTitle("Edit entry" if entry else "New entry")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setObjectName("EntryDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Edit entry" if entry else "New entry")
        title.setProperty("role", "h1")
        header.addWidget(title)
        header.addStretch(1)
        close = IconButton("x", "Close")
        close.clicked.connect(self.reject)
        header.addWidget(close)
        root.addLayout(header)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. GitHub, Proton Mail")
        root.addWidget(_label("Service name"))
        root.addWidget(self.name_edit)

        row = QHBoxLayout()
        row.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(_label("Username / email"))
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("you@example.com")
        left.addWidget(self.username_edit)
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(_label("URL"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://")
        right.addWidget(self.url_edit)
        row.addLayout(left, 1)
        row.addLayout(right, 1)
        root.addLayout(row)

        root.addWidget(_label("Password"))
        pw_row = QHBoxLayout()
        pw_row.setSpacing(8)
        self.password = PasswordEdit("Password", reveal_seconds=settings.get("reveal_seconds"))
        pw_row.addWidget(self.password, 1)
        self.generate_btn = GhostButton("Generate", "sparkles")
        self.generate_btn.clicked.connect(self._generate)
        pw_row.addWidget(self.generate_btn)
        root.addLayout(pw_row)

        self.meter = StrengthMeter()
        root.addWidget(self.meter)

        row2 = QHBoxLayout()
        row2.setSpacing(12)
        tag_col = QVBoxLayout()
        tag_col.setSpacing(6)
        tag_col.addWidget(_label("Tags", "Comma separated"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("work, personal")
        tag_col.addWidget(self.tags_edit)
        totp_col = QVBoxLayout()
        totp_col.setSpacing(6)
        totp_col.addWidget(_label("2FA secret", "Optional — base32 or otpauth:// URL"))
        self.totp_edit = QLineEdit()
        self.totp_edit.setPlaceholderText("JBSWY3DPEHPK3PXP")
        totp_col.addWidget(self.totp_edit)
        row2.addLayout(tag_col, 1)
        row2.addLayout(totp_col, 1)
        root.addLayout(row2)

        root.addWidget(_label("Notes"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Recovery codes, security questions, reminders…")
        self.notes_edit.setFixedHeight(96)
        root.addWidget(self.notes_edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = GhostButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save_btn = PrimaryButton("Save entry", "check")
        self.save_btn.clicked.connect(self._save)
        buttons.addWidget(self.save_btn)
        root.addLayout(buttons)

        self.password.textChanged.connect(self._update_strength)
        self.name_edit.returnPressed.connect(self._save)

        if entry:
            self._fill(entry)
        else:
            self.password.setFocus()

        self._update_strength(self.password.text())

    # -- helpers -----------------------------------------------------------
    def _fill(self, entry: Entry) -> None:
        self.name_edit.setText(entry.name)
        self.username_edit.setText(entry.username)
        self.url_edit.setText(entry.url)
        self.password.setText(entry.password)
        self.tags_edit.setText(", ".join(entry.tags))
        self.totp_edit.setText(entry.totp)
        self.notes_edit.setPlainText(entry.notes)

    def _generate(self) -> None:
        value = generator.generate_password(
            self.settings.get("gen_length"),
            use_upper=self.settings.get("gen_upper"),
            use_lower=self.settings.get("gen_lower"),
            use_digits=self.settings.get("gen_digits"),
            use_symbols=self.settings.get("gen_symbols"),
            exclude_ambiguous=self.settings.get("gen_ambiguous"),
        )
        self.password.setText(value)
        self.password.show_text()

    def _update_strength(self, text: str) -> None:
        if not text:
            self.meter.reset()
            return
        result = estimate(text)
        detail = f"{result.label} · {result.bits:.0f} bits · cracked in {result.crack_time}"
        self.meter.set_strength(result.score, detail, result.color)

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        password = self.password.text()
        if not name:
            QMessageBox.warning(self, "Missing name", "Give the entry a service name.")
            self.name_edit.setFocus()
            return
        if not password:
            QMessageBox.warning(self, "Missing password", "The password cannot be empty.")
            self.password.setFocus()
            return

        duplicate = self.vault.find_by_name(
            name, exclude_id=self.entry.id if self.entry else None
        )
        if duplicate is not None:
            QMessageBox.warning(
                self, "Name already used",
                f"“{duplicate.name}” already exists. Pick a different name.",
            )
            self.name_edit.setFocus()
            self.name_edit.selectAll()
            return

        secret = self.totp_edit.text().strip()
        if secret and not totp.is_valid(secret):
            QMessageBox.warning(
                self, "Invalid 2FA secret",
                "That does not look like a valid base32 TOTP secret.",
            )
            self.totp_edit.setFocus()
            return

        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]

        if self.entry is None:
            entry = Entry(name=name, password=password)
        else:
            entry = Entry.from_dict(self.entry.to_dict())

        entry.name = name
        entry.username = self.username_edit.text().strip()
        entry.url = self.url_edit.text().strip()
        entry.password = password
        entry.tags = tags
        entry.totp = secret
        entry.notes = self.notes_edit.toPlainText().strip()
        self.saved_entry = entry
        self.accept()

    # -- theme refresh -----------------------------------------------------
    def refresh_theme(self) -> None:
        self.setStyleSheet(themes.build_qss(themes.current_name()))
