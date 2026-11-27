"""Application shell: sidebar navigation, vault lifecycle, idle lock, clipboard."""

from __future__ import annotations

import os
import time

from PySide6.QtCore import QEvent, QSize, QTimer, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..core.crypto import InvalidPassword, VaultError
from ..core.settings import AppSettings
from ..core.vault import Vault
from . import icons, themes
from .generator_view import GeneratorView
from .settings_view import SettingsView
from .unlock_view import UnlockView
from .vault_dialogs import CreateVaultDialog
from .vault_view import VaultView
from .widgets import GhostButton, PrimaryButton, Toast, refresh_icons
from .workers import run_async

NAV = [
    ("shield", "Vault"),
    ("sparkles", "Generator"),
    ("settings", "Settings"),
]


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self.vault: Vault | None = None
        self._last_activity = time.time()
        self._clipboard_value: str | None = None
        self._nav_buttons: list[QPushButton] = []

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(980, 680)
        self.resize(1180, 780)

        geometry = self.settings.get("window_geometry")
        if geometry:
            try:
                if not isinstance(geometry, (bytes, bytearray)):
                    geometry = bytes(geometry)
                self.restoreGeometry(geometry)
            except (TypeError, ValueError):
                pass

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.unlock = UnlockView()
        self.unlock.unlock_requested.connect(self._unlock)
        self.unlock.create_requested.connect(self._create_vault)
        self.unlock.open_requested.connect(self._open_vault)
        self.unlock.open_path_requested.connect(self._open_path)
        self.stack.addWidget(self.unlock)

        self.workspace = self._build_workspace()
        self.stack.addWidget(self.workspace)

        self.toast = Toast(self)
        self.toast.setParent(self)

        # Idle auto-lock
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(10_000)
        self.idle_timer.timeout.connect(self._check_idle)
        self.idle_timer.start()
        QApplication.instance().installEventFilter(self)

        QShortcut(QKeySequence("Ctrl+L"), self, self.lock_vault)

        path = self.settings.vault_path
        if path and os.path.exists(path):
            self.vault = Vault(path)
            self.unlock.configure(path, self.settings.recent_vaults)
            self.unlock.focus_password()
        else:
            self.unlock.configure("", self.settings.recent_vaults)
        self.stack.setCurrentWidget(self.unlock)

    # -- layout ------------------------------------------------------------
    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace.setObjectName("Root")
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 22, 16, 18)
        side.setSpacing(6)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        self.brand_icon = QLabel()
        self.brand_icon.setPixmap(icons.icon("shield", themes.current()["accent"], 26)
                                  .pixmap(26, 26))
        brand_row.addWidget(self.brand_icon)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        name = QLabel("BNDGG")
        name.setStyleSheet("font-size:16px; font-weight:800; letter-spacing:1px;")
        tag = QLabel("VAULT")
        tag.setProperty("role", "faint")
        tag.setStyleSheet("font-size:10px; letter-spacing:3px; font-weight:700;")
        brand.addWidget(name)
        brand.addWidget(tag)
        brand_row.addLayout(brand)
        brand_row.addStretch(1)
        side.addLayout(brand_row)
        side.addSpacing(22)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, (icon_name, label) in enumerate(NAV):
            button = QPushButton(label)
            button.setProperty("nav", "true")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(icons.icon(icon_name, themes.current()["muted"], 18))
            button.setProperty("iconName", icon_name)
            button.setProperty("iconRole", "muted")
            button.setProperty("iconPx", 18)
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda _=False, i=index: self._nav_to(i))
            group.addButton(button)
            self._nav_buttons.append(button)
            side.addWidget(button)

        side.addStretch(1)

        self.vault_name_label = QLabel("No vault")
        self.vault_name_label.setProperty("role", "faint")
        self.vault_name_label.setWordWrap(True)
        side.addWidget(self.vault_name_label)
        side.addSpacing(6)

        self.lock_btn = GhostButton("Lock vault", "lock")
        self.lock_btn.clicked.connect(self.lock_vault)
        side.addWidget(self.lock_btn)

        version = QLabel(f"v{__version__}")
        version.setProperty("role", "faint")
        side.addWidget(version)

        layout.addWidget(sidebar)

        content_wrap = QWidget()
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(26, 22, 26, 20)
        content_layout.setSpacing(0)
        self.content = QStackedWidget()
        content_layout.addWidget(self.content)
        layout.addWidget(content_wrap, 1)
        return workspace

    # -- vault lifecycle ---------------------------------------------------
    def _set_vault(self, vault: Vault) -> None:
        self.vault = vault
        while self.content.count():
            widget = self.content.widget(0)
            self.content.removeWidget(widget)
            widget.deleteLater()

        self.vault_view = VaultView(vault, self.settings)
        self.vault_view.copy_requested.connect(self.copy_text)
        self.vault_view.toast.connect(self._toast)
        self.generator_view = GeneratorView(self.settings)
        self.generator_view.copy_requested.connect(self.copy_text)
        self.generator_view.use_password.connect(self._use_generated)
        self.settings_view = SettingsView(vault, self.settings)
        self.settings_view.theme_changed.connect(self._change_theme)
        self.settings_view.lock_requested.connect(self.lock_vault)
        self.settings_view.vault_moved.connect(self._on_vault_moved)
        self.settings_view.toast.connect(self._toast)

        self.content.addWidget(self.vault_view)
        self.content.addWidget(self.generator_view)
        self.content.addWidget(self.settings_view)

        self.vault_name_label.setText(
            f"{vault.path.name}\n{vault.path.parent}"
        )
        self.setWindowTitle(f"{APP_NAME} — {vault.path.name}")
        self._nav_to(0)

    def _unlock(self, password: str) -> None:
        if not self.vault:
            self.unlock.show_error("No vault selected.")
            return
        self.unlock.set_busy(True)
        run_async(self.vault.unlock, self._unlocked, self._unlock_failed, password)

    def _unlocked(self, _result: object) -> None:
        self.unlock.set_busy(False)
        self.unlock.password.clear()
        self.unlock.clear_error()
        if not self.vault or not self.vault.is_unlocked:
            self.unlock.show_error("Could not unlock the vault.")
            return
        self._set_vault(self.vault)
        self.stack.setCurrentWidget(self.workspace)
        self._last_activity = time.time()
        self._toast(f"Unlocked — {len(self.vault.entries)} entries", "success")
        self.vault_view.search.setFocus()

    def _unlock_failed(self, message: str) -> None:
        self.unlock.set_busy(False)
        self.unlock.show_error(message)

    def _create_vault(self) -> None:
        dialog = CreateVaultDialog(self, self.settings.vault_path or None)
        if not dialog.exec():
            return
        try:
            vault = Vault.create(dialog.path, dialog.password)
        except (VaultError, OSError) as exc:
            QMessageBox.critical(self, "Could not create vault", str(exc))
            return
        self.settings.vault_path = dialog.path
        self._set_vault(vault)
        self.stack.setCurrentWidget(self.workspace)
        self._last_activity = time.time()
        self._toast("Vault created", "success")

    def _open_vault(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open vault", self.settings.vault_path or "",
            "BNDGG vault (*.json);;All files (*)",
        )
        if path:
            self._open_path(path)

    def _open_path(self, path: str) -> None:
        kind = Vault.inspect(path)
        if kind == "legacy":
            QMessageBox.information(
                self, "Legacy vault",
                "This is an old BNDGG v1 vault.\n\n"
                "Create a new vault first, then use Settings → Vault → "
                "“Import legacy v1…” to bring the entries across.",
            )
            return
        if kind != "v2":
            QMessageBox.critical(
                self, "Not a vault",
                "That file is not a BNDGG vault, or it is damaged.",
            )
            return
        self.settings.vault_path = path
        self.vault = Vault(path)
        self.unlock.configure(path, self.settings.recent_vaults)
        self.unlock.clear_error()
        self.unlock.password.clear()
        self.unlock.focus_password()
        self.stack.setCurrentWidget(self.unlock)

    def _on_vault_moved(self, path: str) -> None:
        self.vault_name_label.setText(
            f"{os.path.basename(path)}\n{os.path.dirname(path)}"
        )
        self.setWindowTitle(f"{APP_NAME} — {os.path.basename(path)}")

    def lock_vault(self) -> None:
        if self.vault:
            self.vault.lock()
        if hasattr(self, "vault_view"):
            self.vault_view.lock_cleanup()
        if hasattr(self, "generator_view"):
            self.generator_view.save_defaults()
        self._clear_clipboard(force=True)
        self.stack.setCurrentWidget(self.unlock)
        self.unlock.configure(self.settings.vault_path, self.settings.recent_vaults)
        self.unlock.clear_error()
        self.unlock.password.clear()
        self.unlock.set_busy(False)
        self.unlock.focus_password()
        self._last_activity = time.time()

    # -- navigation --------------------------------------------------------
    def _nav_to(self, index: int) -> None:
        if self.content.count() == 0:
            return
        index = max(0, min(index, self.content.count() - 1))
        self.content.setCurrentIndex(index)
        for i, button in enumerate(self._nav_buttons):
            button.setChecked(i == index)
        if index == 2 and hasattr(self, "settings_view"):
            self.settings_view.refresh()

    # -- clipboard ---------------------------------------------------------
    def copy_text(self, text: str, sensitive: bool) -> None:
        if not text:
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        self._clipboard_value = text if sensitive else None
        self._toast("Copied to clipboard", "success")
        seconds = int(self.settings.get("clipboard_clear_seconds"))
        if sensitive and seconds > 0:
            QTimer.singleShot(seconds * 1000, self._clear_clipboard)

    def _clear_clipboard(self, force: bool = False) -> None:
        value = self._clipboard_value
        if not value:
            return
        clipboard = QGuiApplication.clipboard()
        if force or clipboard.text() == value:
            clipboard.clear()
            if not force:
                self._toast("Clipboard cleared", "warning")
        self._clipboard_value = None

    # -- theme -------------------------------------------------------------
    def _change_theme(self, key: str) -> None:
        themes.apply_theme(QApplication.instance(), key)
        self.settings.set("theme", key)
        refresh_icons(self)
        self.brand_icon.setPixmap(
            icons.icon("shield", themes.current()["accent"], 26).pixmap(26, 26)
        )
        if hasattr(self, "vault_view"):
            self.vault_view.refresh_theme()
        if hasattr(self, "generator_view"):
            self.generator_view.regenerate()

    # -- generated password -------------------------------------------------
    def _use_generated(self, password: str) -> None:
        if not self.vault or not self.vault.is_unlocked:
            return
        self._nav_to(0)
        self.vault_view.new_entry(password)

    # -- idle --------------------------------------------------------------
    def _check_idle(self) -> None:
        if not self.vault or not self.vault.is_unlocked:
            return
        minutes = int(self.settings.get("auto_lock_minutes"))
        if minutes <= 0:
            return
        if time.time() - self._last_activity >= minutes * 60:
            self.lock_vault()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() in (
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.Wheel,
            QEvent.Type.TouchBegin,
        ):
            self._last_activity = time.time()
        return super().eventFilter(obj, event)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized() and self.settings.get("lock_on_minimize"):
                self.lock_vault()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast._reposition()

    # -- misc --------------------------------------------------------------
    def _toast(self, message: str, kind: str = "success") -> None:
        self.toast.show_message(message, kind)

    def closeEvent(self, event) -> None:  # noqa: N802
        if hasattr(self, "generator_view"):
            self.generator_view.save_defaults()
        self.settings.set("window_geometry", bytes(self.saveGeometry()))
        self.settings.sync()
        self._clear_clipboard(force=True)
        if self.vault:
            self.vault.lock()
        super().closeEvent(event)
