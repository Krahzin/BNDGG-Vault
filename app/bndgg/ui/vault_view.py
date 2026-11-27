"""Main vault page: searchable table + entry detail panel."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import totp
from ..core.settings import AppSettings
from ..core.strength import estimate
from ..core.vault import Entry, Vault
from . import icons, themes
from .entry_dialog import EntryDialog
from .widgets import (
    Card,
    DangerButton,
    GhostButton,
    IconButton,
    PrimaryButton,
    Separator,
    StrengthMeter,
    TagChip,
)


class VaultView(QWidget):
    toast = Signal(str, str)
    copy_requested = Signal(str, bool)  # text, sensitive

    def __init__(self, vault: Vault, settings: AppSettings,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.settings = settings
        self._current: Entry | None = None
        self._totp_timer = QTimer(self)
        self._totp_timer.setInterval(1000)
        self._totp_timer.timeout.connect(self._tick_totp)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("Vault")
        title.setProperty("role", "h1")
        header.addWidget(title)
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "faint")
        header.addWidget(self.count_label)
        header.addStretch(1)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name, username, URL or tag…")
        self._search_action = self.search.addAction(
            icons.icon("search", themes.current()["faint"], 16),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search.textChanged.connect(self.reload)
        toolbar.addWidget(self.search, 1)

        self.tag_filter = QComboBox()
        self.tag_filter.setMinimumWidth(140)
        self.tag_filter.currentIndexChanged.connect(self.reload)
        toolbar.addWidget(self.tag_filter)

        self.new_btn = PrimaryButton("New entry", "plus")
        self.new_btn.clicked.connect(self.new_entry)
        toolbar.addWidget(self.new_btn)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        root.addWidget(splitter, 1)

        table_card = Card(padding=8)
        table_card.body.setContentsMargins(6, 6, 6, 6)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Username", "Tags"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setHighlightSections(False)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda _: self.edit_entry())
        table_card.body.addWidget(self.table)

        self.empty = QLabel("No entries yet — create your first one.")
        self.empty.setProperty("role", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_card.body.addWidget(self.empty)

        splitter.addWidget(table_card)

        self.detail = self._build_detail()
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([620, 380])

        QShortcut(QKeySequence("Ctrl+N"), self, self.new_entry)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+C"), self.table, self.copy_password)
        QShortcut(QKeySequence("Delete"), self.table, self.delete_entry)

        # Populate immediately — otherwise the table stays blank until some
        # signal (search, tag change, or a new entry) happens to call reload().
        self.reload()

    # -- detail panel ------------------------------------------------------
    def _build_detail(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(12)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        placeholder = QWidget()
        pv = QVBoxLayout(placeholder)
        pv.addStretch(1)
        icon = QLabel()
        icon.setPixmap(icons.icon("key", themes.current()["faint"], 34).pixmap(34, 34))
        icon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        pv.addWidget(icon)
        text = QLabel("Select an entry to see its details")
        text.setProperty("role", "muted")
        text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        pv.addWidget(text)
        pv.addStretch(1)
        self.stack.addWidget(placeholder)

        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(10)

        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.d_name = QLabel("")
        self.d_name.setProperty("role", "h1")
        self.d_name.setWordWrap(True)
        self.d_user = QLabel("")
        self.d_user.setProperty("role", "muted")
        self.d_user.setWordWrap(True)
        titles.addWidget(self.d_name)
        titles.addWidget(self.d_user)
        top.addLayout(titles, 1)
        self.edit_btn = IconButton("edit", "Edit entry")
        self.edit_btn.clicked.connect(self.edit_entry)
        top.addWidget(self.edit_btn)
        self.delete_btn = IconButton("trash", "Delete entry", role="danger")
        self.delete_btn.clicked.connect(self.delete_entry)
        top.addWidget(self.delete_btn)
        cv.addLayout(top)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy_pw_btn = PrimaryButton("Copy password", "copy")
        self.copy_pw_btn.clicked.connect(self.copy_password)
        actions.addWidget(self.copy_pw_btn, 1)
        self.copy_user_btn = GhostButton("Username", "user")
        self.copy_user_btn.clicked.connect(self.copy_username)
        actions.addWidget(self.copy_user_btn)
        cv.addLayout(actions)

        self.meter = StrengthMeter()
        cv.addWidget(self.meter)
        cv.addWidget(Separator())

        self.pw_field = QLineEdit()
        self.pw_field.setReadOnly(True)
        self.pw_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_field.setProperty("role", "mono")
        self.pw_field.setStyleSheet("font-family: 'Cascadia Mono','Consolas',monospace;")
        self.reveal_btn = IconButton("eye", "Reveal password")
        self.reveal_btn.clicked.connect(self._toggle_reveal)
        pw_row = QHBoxLayout()
        pw_row.setSpacing(6)
        pw_row.addWidget(self.pw_field, 1)
        pw_row.addWidget(self.reveal_btn)
        self.pw_block = self._block("Password", pw_row)
        cv.addWidget(self.pw_block)

        self.url_value = QLabel("")
        self.url_value.setOpenExternalLinks(False)
        self.url_value.linkActivated.connect(self._open_url)
        self.url_value.setWordWrap(True)
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        url_row.addWidget(self.url_value, 1)
        self.url_copy = IconButton("copy", "Copy URL")
        self.url_copy.clicked.connect(self.copy_url)
        url_row.addWidget(self.url_copy)
        self.url_block = self._block("Website", url_row)
        cv.addWidget(self.url_block)

        self.totp_value = QLabel("")
        self.totp_value.setStyleSheet(
            "font-family:'Cascadia Mono','Consolas',monospace; font-size:20px;"
            "font-weight:700; letter-spacing:2px;"
        )
        self.totp_hint = QLabel("")
        self.totp_hint.setProperty("role", "faint")
        totp_row = QHBoxLayout()
        totp_row.setSpacing(8)
        totp_row.addWidget(self.totp_value)
        totp_row.addWidget(self.totp_hint)
        totp_row.addStretch(1)
        self.totp_copy = IconButton("copy", "Copy code")
        self.totp_copy.clicked.connect(self.copy_totp)
        totp_row.addWidget(self.totp_copy)
        self.totp_block = self._block("One-time code", totp_row)
        cv.addWidget(self.totp_block)

        self.tags_row = QHBoxLayout()
        self.tags_row.setSpacing(6)
        self.tags_block = self._block("Tags", self.tags_row)
        cv.addWidget(self.tags_block)

        self.notes_value = QLabel("")
        self.notes_value.setWordWrap(True)
        self.notes_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.notes_block = self._block("Notes", self.notes_value)
        cv.addWidget(self.notes_block)

        cv.addStretch(1)
        self.meta = QLabel("")
        self.meta.setProperty("role", "faint")
        self.meta.setWordWrap(True)
        cv.addWidget(self.meta)

        self.stack.addWidget(content)
        self.stack.setCurrentIndex(0)
        return panel

    def _block(self, title: str, content) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)
        label = QLabel(title.upper())
        label.setProperty("role", "faint")
        layout.addWidget(label)
        if isinstance(content, QHBoxLayout):
            layout.addLayout(content)
        else:
            layout.addWidget(content)
        return block

    # -- data --------------------------------------------------------------
    def reload(self) -> None:
        self._refresh_tags()
        query = self.search.text()
        tag = self.tag_filter.currentData() if self.tag_filter.currentIndex() > 0 else None
        entries = self.vault.sorted_entries(query, tag)

        selected = self._current.id if self._current else None
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row, entry in enumerate(entries):
            self.table.insertRow(row)
            name_item = QTableWidgetItem(entry.name)
            name_item.setData(Qt.ItemDataRole.UserRole, entry.id)
            user_item = QTableWidgetItem(entry.username)
            tag_item = QTableWidgetItem(", ".join(entry.tags))
            tag_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, user_item)
            self.table.setItem(row, 2, tag_item)
        self.table.blockSignals(False)

        self.empty.setVisible(not entries)
        self.table.setVisible(bool(entries))
        total = len(self.vault.entries)
        shown = len(entries)
        self.count_label.setText(
            f"{shown} of {total}" if shown != total else f"{total} entries"
        )

        target_row = -1
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected:
                target_row = row
                break
        if target_row >= 0:
            self.table.selectRow(target_row)
        elif entries:
            self.table.selectRow(0)
        else:
            self._current = None
            self.stack.setCurrentIndex(0)

    def _refresh_tags(self) -> None:
        current = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("All tags", None)
        for tag in self.vault.all_tags():
            self.tag_filter.addItem(tag, tag)
        index = self.tag_filter.findData(current)
        self.tag_filter.setCurrentIndex(max(0, index))
        self.tag_filter.blockSignals(False)

    def _selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self._current = None
            self.stack.setCurrentIndex(0)
            return
        item = self.table.item(rows[0].row(), 0)
        entry = self.vault.get(item.data(Qt.ItemDataRole.UserRole))
        if entry is None:
            return
        self._current = entry
        self._show(entry)

    def _show(self, entry: Entry) -> None:
        self.stack.setCurrentIndex(1)
        self.d_name.setText(entry.name)
        self.d_user.setText(entry.username or "No username")
        self.pw_field.setText(entry.password)
        self.pw_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.reveal_btn.setIcon(icons.icon("eye", themes.current()["muted"], 18))

        result = estimate(entry.password)
        self.meter.set_strength(
            result.score,
            f"{result.label} · {result.bits:.0f} bits · cracked in {result.crack_time}",
            result.color,
        )

        if entry.url:
            url = entry.url if "://" in entry.url else f"https://{entry.url}"
            self.url_value.setText(f'<a href="{url}" style="color:{themes.current()["accent"]}">{entry.url}</a>')
            self.url_block.show()
        else:
            self.url_block.hide()

        if entry.tags:
            self._clear_layout(self.tags_row)
            for tag in entry.tags:
                self.tags_row.addWidget(TagChip(tag))
            self.tags_row.addStretch(1)
            self.tags_block.show()
        else:
            self.tags_block.hide()

        if entry.notes:
            self.notes_value.setText(entry.notes)
            self.notes_block.show()
        else:
            self.notes_block.hide()

        if entry.totp:
            self.totp_block.show()
            self._tick_totp()
            self._totp_timer.start()
        else:
            self.totp_block.hide()
            self._totp_timer.stop()

        self.meta.setText(
            f"Created {self._pretty(entry.created)}   ·   Updated {self._pretty(entry.updated)}"
        )
        self.copy_user_btn.setEnabled(bool(entry.username))

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

    @staticmethod
    def _pretty(value: str) -> str:
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo:
                dt = dt.astimezone()
            return dt.strftime("%d %b %Y, %H:%M")
        except Exception:  # noqa: BLE001
            return value

    # -- actions -----------------------------------------------------------
    def new_entry(self, preset_password: str | None = None) -> None:
        dialog = EntryDialog(self, self.vault, self.settings)
        if preset_password:
            dialog.password.setText(str(preset_password))
        if dialog.exec() and dialog.saved_entry:
            self.vault.add_entry(dialog.saved_entry)
            self._current = dialog.saved_entry
            self.reload()
            self.toast.emit(f"Saved “{dialog.saved_entry.name}”", "success")

    def edit_entry(self) -> None:
        if not self._current:
            return
        entry = self._current
        dialog = EntryDialog(self, self.vault, self.settings, entry)
        if dialog.exec() and dialog.saved_entry:
            self.vault.update_entry(entry.id, dialog.saved_entry)
            self.reload()
            self.toast.emit("Entry updated", "success")

    def delete_entry(self) -> None:
        entry = self._current
        if not entry:
            return
        if self.settings.get("confirm_delete"):
            answer = QMessageBox.question(
                self, "Delete entry",
                f"Delete “{entry.name}”?\n\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.vault.delete_entry(entry.id)
        self._current = None
        self.reload()
        self.toast.emit("Entry deleted", "warning")

    def copy_password(self) -> None:
        if self._current:
            self.copy_requested.emit(self._current.password, True)

    def copy_username(self) -> None:
        if self._current and self._current.username:
            self.copy_requested.emit(self._current.username, False)

    def copy_url(self) -> None:
        if self._current and self._current.url:
            self.copy_requested.emit(self._current.url, False)

    def copy_totp(self) -> None:
        if self._current and self._current.totp:
            self.copy_requested.emit(totp.code(self._current.totp), True)

    def _toggle_reveal(self) -> None:
        if self.pw_field.echoMode() == QLineEdit.EchoMode.Password:
            self.pw_field.setEchoMode(QLineEdit.EchoMode.Normal)
            self.reveal_btn.setIcon(icons.icon("eye_off", themes.current()["accent"], 18))
            seconds = int(self.settings.get("reveal_seconds"))
            if seconds:
                QTimer.singleShot(seconds * 1000, self._hide_reveal)
        else:
            self._hide_reveal()

    def _hide_reveal(self) -> None:
        if not hasattr(self, "pw_field"):
            return
        self.pw_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.reveal_btn.setIcon(icons.icon("eye", themes.current()["muted"], 18))

    def _tick_totp(self) -> None:
        if not self._current or not self._current.totp:
            return
        try:
            value = totp.code(self._current.totp)
            left = totp.remaining()
            self.totp_value.setText(totp.pretty(value))
            self.totp_hint.setText(f"{left}s")
        except Exception:  # noqa: BLE001
            self.totp_value.setText("invalid secret")
            self.totp_hint.setText("")

    def _open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def lock_cleanup(self) -> None:
        self._totp_timer.stop()
        self._current = None
        self.search.clear()
        self.table.setRowCount(0)
        self.stack.setCurrentIndex(0)

    def refresh_theme(self) -> None:
        self._search_action.setIcon(icons.icon("search", themes.current()["faint"], 16))
        if self._current:
            self._show(self._current)
        else:
            self.reveal_btn.setIcon(icons.icon("eye", themes.current()["muted"], 18))
