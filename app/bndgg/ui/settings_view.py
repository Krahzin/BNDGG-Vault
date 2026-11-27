"""Settings page: appearance, security, vault management, master password."""

from __future__ import annotations

import os

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.crypto import InvalidPassword, VaultError
from ..core.settings import AppSettings
from ..core.strength import estimate
from ..core.vault import Vault
from . import themes
from .widgets import (
    Card,
    DangerButton,
    GhostButton,
    PasswordEdit,
    PrimaryButton,
    Separator,
    StrengthMeter,
)


class ThemeSwatch(QPushButton):
    def __init__(self, key: str, palette: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(palette["label"])
        self.setIcon(QIcon(self._preview(palette)))
        self.setIconSize(QSize(46, 30))
        self.setFixedSize(64, 56)
        self.setStyleSheet(
            "QPushButton { padding: 6px; border-radius: 10px;"
            " border: 2px solid transparent; }"
            f"QPushButton:checked {{ border: 2px solid {palette['accent']}; }}"
        )

    @staticmethod
    def _preview(palette: dict) -> QPixmap:
        ratio = 2
        pm = QPixmap(46 * ratio, 30 * ratio)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(1, 1, 44 * ratio, 28 * ratio)
        painter.setPen(QPen(QColor(palette["border"]), 1.4 * ratio))
        painter.setBrush(QColor(palette["bg"]))
        painter.drawRoundedRect(rect, 6 * ratio, 6 * ratio)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette["surface"]))
        painter.drawRoundedRect(QRectF(6 * ratio, 7 * ratio, 14 * ratio, 16 * ratio),
                                3 * ratio, 3 * ratio)
        painter.setBrush(QColor(palette["accent"]))
        painter.drawEllipse(QRectF(25 * ratio, 9 * ratio, 6 * ratio, 6 * ratio))
        painter.setBrush(QColor(palette["muted"]))
        painter.drawRoundedRect(QRectF(25 * ratio, 18 * ratio, 14 * ratio, 3 * ratio),
                                1.5 * ratio, 1.5 * ratio)
        painter.end()
        pm.setDevicePixelRatio(ratio)
        return pm


class SettingsView(QWidget):
    theme_changed = Signal(str)
    lock_requested = Signal()
    vault_moved = Signal(str)
    toast = Signal(str, str)

    def __init__(self, vault: Vault, settings: AppSettings,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.settings = settings
        self._theme_buttons: dict[str, ThemeSwatch] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 20)
        layout.setSpacing(14)

        title = QLabel("Settings")
        title.setProperty("role", "h1")
        layout.addWidget(title)

        layout.addWidget(self._appearance_card())
        layout.addWidget(self._security_card())
        layout.addWidget(self._vault_card())
        layout.addWidget(self._password_card())
        layout.addWidget(self._about_card())
        layout.addStretch(1)

    # -- appearance --------------------------------------------------------
    def _appearance_card(self) -> Card:
        card = Card()
        card.add_title("Appearance", "Pick a theme — applied instantly.")
        row = QHBoxLayout()
        row.setSpacing(6)
        group = QButtonGroup(self)
        group.setExclusive(True)
        current = self.settings.get("theme")
        for key in themes.THEME_ORDER:
            palette = themes.theme(key)
            swatch = ThemeSwatch(key, palette)
            swatch.setChecked(key == current)
            swatch.clicked.connect(lambda _=False, k=key: self._pick_theme(k))
            group.addButton(swatch)
            self._theme_buttons[key] = swatch
            row.addWidget(swatch)
        row.addStretch(1)
        card.body.addLayout(row)
        return card

    def _pick_theme(self, key: str) -> None:
        self.settings.set("theme", key)
        self.theme_changed.emit(key)

    # -- security ----------------------------------------------------------
    def _security_card(self) -> Card:
        card = Card()
        card.add_title("Security", "How the vault behaves while unlocked.")

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)

        auto_label = QLabel("Auto-lock after")
        auto_label.setProperty("role", "muted")
        self.auto_lock = QComboBox()
        for minutes, text in ((1, "1 minute"), (2, "2 minutes"), (5, "5 minutes"),
                              (10, "10 minutes"), (15, "15 minutes"),
                              (30, "30 minutes"), (60, "1 hour"),
                              (0, "Never (not recommended)")):
            self.auto_lock.addItem(text, minutes)
        index = self.auto_lock.findData(int(self.settings.get("auto_lock_minutes")))
        self.auto_lock.setCurrentIndex(max(0, index))
        self.auto_lock.currentIndexChanged.connect(self._save_security)
        grid.addWidget(auto_label, 0, 0)
        grid.addWidget(self.auto_lock, 0, 1)

        clip_label = QLabel("Clear clipboard after")
        clip_label.setProperty("role", "muted")
        self.clipboard_spin = QSpinBox()
        self.clipboard_spin.setRange(0, 300)
        self.clipboard_spin.setSuffix(" s")
        self.clipboard_spin.setSpecialValueText("Never")
        self.clipboard_spin.setValue(int(self.settings.get("clipboard_clear_seconds")))
        self.clipboard_spin.valueChanged.connect(self._save_security)
        grid.addWidget(clip_label, 0, 2)
        grid.addWidget(self.clipboard_spin, 0, 3)

        reveal_label = QLabel("Re-hide passwords after")
        reveal_label.setProperty("role", "muted")
        self.reveal_spin = QSpinBox()
        self.reveal_spin.setRange(0, 120)
        self.reveal_spin.setSuffix(" s")
        self.reveal_spin.setSpecialValueText("Never")
        self.reveal_spin.setValue(int(self.settings.get("reveal_seconds")))
        self.reveal_spin.valueChanged.connect(self._save_security)
        grid.addWidget(reveal_label, 1, 0)
        grid.addWidget(self.reveal_spin, 1, 1)

        card.body.addLayout(grid)
        card.body.addWidget(Separator())

        self.cb_minimize = QCheckBox("Lock the vault when the window is minimized")
        self.cb_minimize.setChecked(bool(self.settings.get("lock_on_minimize")))
        self.cb_minimize.toggled.connect(self._save_security)
        card.body.addWidget(self.cb_minimize)

        self.cb_confirm = QCheckBox("Ask before deleting an entry")
        self.cb_confirm.setChecked(bool(self.settings.get("confirm_delete")))
        self.cb_confirm.toggled.connect(self._save_security)
        card.body.addWidget(self.cb_confirm)

        self.cb_history = QCheckBox("Keep the last 5 passwords per entry when changing")
        self.cb_history.setChecked(bool(self.settings.get("keep_history")))
        self.cb_history.toggled.connect(self._save_security)
        card.body.addWidget(self.cb_history)

        lock_now = QHBoxLayout()
        lock_now.addStretch(1)
        button = GhostButton("Lock vault now", "lock")
        button.clicked.connect(self.lock_requested.emit)
        lock_now.addWidget(button)
        card.body.addLayout(lock_now)
        return card

    def _save_security(self) -> None:
        self.settings.set("auto_lock_minutes", self.auto_lock.currentData())
        self.settings.set("clipboard_clear_seconds", self.clipboard_spin.value())
        self.settings.set("reveal_seconds", self.reveal_spin.value())
        self.settings.set("lock_on_minimize", self.cb_minimize.isChecked())
        self.settings.set("confirm_delete", self.cb_confirm.isChecked())
        self.settings.set("keep_history", self.cb_history.isChecked())

    # -- vault -------------------------------------------------------------
    def _vault_card(self) -> Card:
        card = Card()
        card.add_title("Vault", "Where the encrypted file lives and how to move it.")

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_label = QLabel(str(self.vault.path))
        self.path_label.setProperty("role", "muted")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_row.addWidget(self.path_label, 1)
        open_folder = GhostButton("Open folder", "folder")
        open_folder.clicked.connect(self._open_folder)
        path_row.addWidget(open_folder)
        card.body.addLayout(path_row)

        health = self.vault.health()
        self.health_label = QLabel(self._health_text(health))
        self.health_label.setProperty("role", "faint")
        card.body.addWidget(self.health_label)
        card.body.addWidget(Separator())

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        move = GhostButton("Move vault…", "arrow_right")
        move.clicked.connect(self._move_vault)
        grid.addWidget(move, 0, 0)

        backup = GhostButton("Backup now…", "save")
        backup.clicked.connect(self._backup)
        grid.addWidget(backup, 0, 1)

        export_enc = GhostButton("Export encrypted…", "download")
        export_enc.clicked.connect(self._export_encrypted)
        grid.addWidget(export_enc, 0, 2)

        import_enc = GhostButton("Import encrypted…", "upload")
        import_enc.clicked.connect(self._import_encrypted)
        grid.addWidget(import_enc, 1, 0)

        legacy = GhostButton("Import legacy v1…", "database")
        legacy.clicked.connect(self._import_legacy)
        grid.addWidget(legacy, 1, 1)

        csv_btn = GhostButton("Export CSV…", "external")
        csv_btn.clicked.connect(self._export_csv)
        grid.addWidget(csv_btn, 1, 2)
        card.body.addLayout(grid)

        warning = QLabel("CSV exports are unencrypted plain text. Delete the file when done.")
        warning.setProperty("role", "faint")
        warning.setWordWrap(True)
        card.body.addWidget(warning)
        return card

    def _open_folder(self) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.vault.path.parent)))

    @staticmethod
    def _health_text(health: dict) -> str:
        return (
            f"{health['total']} entries · {len(health['weak'])} weak · "
            f"{len(health['reused'])} reused · "
            f"{len(health['stale'])} not changed in a year"
        )

    def refresh(self) -> None:
        """Re-read vault-derived labels after entries change."""
        self.path_label.setText(str(self.vault.path))
        if hasattr(self, "health_label"):
            self.health_label.setText(self._health_text(self.vault.health()))
        for key, button in self._theme_buttons.items():
            button.setChecked(key == self.settings.get("theme"))

    def _move_vault(self) -> None:
        suggested = str(self.vault.path)
        path, _ = QFileDialog.getSaveFileName(
            self, "Move vault to…", suggested, "BNDGG vault (*.json);;All files (*)"
        )
        if not path:
            return
        if os.path.abspath(path) == os.path.abspath(self.vault.path):
            return
        try:
            old = self.vault.relocate(path)
            self.settings.vault_path = str(self.vault.path)
            self.path_label.setText(str(self.vault.path))
            self.vault_moved.emit(str(self.vault.path))
            self.toast.emit("Vault moved", "success")
            answer = QMessageBox.question(
                self, "Remove old file?",
                f"The vault now lives at:\n{path}\n\n"
                f"Delete the old file?\n{old}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(old)
                    backup = old + ".bak"
                    if os.path.exists(backup):
                        os.remove(backup)
                except OSError as exc:
                    QMessageBox.warning(self, "Could not delete", str(exc))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Move failed", str(exc))

    def _backup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save encrypted backup", "bndgg-backup.json",
            "BNDGG vault (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            self.vault.backup_to(path)
            self.toast.emit("Backup written", "success")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Backup failed", str(exc))

    def _export_encrypted(self) -> None:
        self._backup()

    def _import_encrypted(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import encrypted vault", "",
            "BNDGG vault (*.json);;All files (*)",
        )
        if not path:
            return
        password, ok = QInputDialog.getText(
            self, "Vault password", "Master password of the vault being imported:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return
        merge = QMessageBox.question(
            self, "Import mode",
            "Merge with the current vault?\n\n"
            "Yes = add imported entries\nNo = replace everything",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if merge == QMessageBox.StandardButton.Cancel:
            return
        try:
            count = self.vault.import_encrypted(
                path, password, merge=merge == QMessageBox.StandardButton.Yes
            )
            self.toast.emit(f"Imported {count} entries", "success")
        except InvalidPassword:
            QMessageBox.critical(self, "Import failed", "Incorrect password for that vault.")
        except VaultError as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

    def _import_legacy(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import legacy BNDGG vault (v1)", "",
            "Legacy vault (*.json);;All files (*)",
        )
        if not path:
            return
        password, ok = QInputDialog.getText(
            self, "Legacy password", "Master password of the legacy vault:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return
        try:
            count = self.vault.import_legacy(path, password)
            self.toast.emit(f"Imported {count} legacy entries", "success")
        except InvalidPassword:
            QMessageBox.critical(self, "Import failed", "Incorrect legacy password.")
        except VaultError as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

    def _export_csv(self) -> None:
        answer = QMessageBox.warning(
            self, "Unencrypted export",
            "This writes every password in plain text.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "bndgg-export.csv", "CSV (*.csv);;All files (*)"
        )
        if not path:
            return
        try:
            self.vault.export_csv(path)
            self.toast.emit("CSV exported", "warning")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))

    # -- master password ---------------------------------------------------
    def _password_card(self) -> Card:
        card = Card()
        card.add_title("Master password", "Changing it re-encrypts the whole vault.")

        self.current_pw = PasswordEdit("Current master password")
        self.new_pw = PasswordEdit("New master password", reveal_seconds=0)
        self.confirm_pw = PasswordEdit("Repeat new password", reveal_seconds=0)
        self.new_pw.textChanged.connect(self._password_strength)
        self.meter = StrengthMeter()

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(self.current_pw, 0, 0, 1, 2)
        form.addWidget(self.new_pw, 1, 0)
        form.addWidget(self.confirm_pw, 1, 1)
        card.body.addLayout(form)
        card.body.addWidget(self.meter)

        row = QHBoxLayout()
        row.addStretch(1)
        self.change_btn = PrimaryButton("Change password", "key")
        self.change_btn.clicked.connect(self._change_password)
        row.addWidget(self.change_btn)
        card.body.addLayout(row)
        return card

    def _password_strength(self, text: str) -> None:
        if not text:
            self.meter.reset()
            return
        result = estimate(text)
        self.meter.set_strength(
            result.score,
            f"{result.label} · {result.bits:.0f} bits · cracked in {result.crack_time}",
            result.color,
        )

    def _change_password(self) -> None:
        current = self.current_pw.text()
        new = self.new_pw.text()
        confirm = self.confirm_pw.text()
        if not current:
            QMessageBox.warning(self, "Missing password", "Enter your current master password.")
            return
        if len(new) < 8:
            QMessageBox.warning(self, "Too short", "Use at least 8 characters.")
            return
        if new != confirm:
            QMessageBox.warning(self, "Mismatch", "The new passwords do not match.")
            return
        if estimate(new).score < 2:
            answer = QMessageBox.question(
                self, "Weak password",
                "That master password is weak. Use it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.vault.change_master_password(current, new)
        except InvalidPassword as exc:
            QMessageBox.critical(self, "Change failed", str(exc))
            return
        except VaultError as exc:
            QMessageBox.critical(self, "Change failed", str(exc))
            return
        self.current_pw.clear()
        self.new_pw.clear()
        self.confirm_pw.clear()
        self.meter.reset()
        self.toast.emit("Master password changed", "success")

    # -- about -------------------------------------------------------------
    def _about_card(self) -> Card:
        card = Card()
        card.add_title("About")
        info = QLabel(
            f"BNDGG Vault {__version__}\n"
            "Argon2id key derivation · AES-256-GCM authenticated encryption\n"
            "No telemetry, no cloud, no network access."
        )
        info.setProperty("role", "muted")
        info.setWordWrap(True)
        card.body.addWidget(info)
        return card
