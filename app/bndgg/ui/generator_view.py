"""Password + passphrase generator page."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import generator, wordlist
from ..core.settings import AppSettings
from ..core.strength import estimate
from . import icons, themes
from .widgets import Card, GhostButton, IconButton, PrimaryButton, StrengthMeter


class GeneratorView(QWidget):
    copy_requested = Signal(str, bool)
    use_password = Signal(str)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Generator")
        title.setProperty("role", "h1")
        subtitle = QLabel("Create strong, unique secrets without leaving the app.")
        subtitle.setProperty("role", "muted")
        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._password_tab(), "Password")
        self.tabs.addTab(self._passphrase_tab(), "Passphrase")
        self.tabs.currentChanged.connect(lambda _: self.regenerate())
        root.addWidget(self.tabs, 1)

        self._load_settings()
        # Populate both tabs up front so neither output can appear blank.
        self.regenerate()
        other = 1 - self.tabs.currentIndex()
        self.tabs.setCurrentIndex(other)
        self.regenerate()
        self.tabs.setCurrentIndex(1 - other)

    # -- password tab ------------------------------------------------------
    def _password_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(14)

        card = Card()
        output_widget, self.pw_output = self._output_row()
        card.body.addWidget(output_widget)
        self.pw_meter = StrengthMeter()
        card.body.addWidget(self.pw_meter)

        length_row = QHBoxLayout()
        length_label = QLabel("Length")
        length_label.setProperty("role", "h3")
        length_row.addWidget(length_label)
        self.length_slider = QSlider(Qt.Orientation.Horizontal)
        self.length_slider.setRange(8, 128)
        self.length_slider.valueChanged.connect(self._length_changed)
        length_row.addWidget(self.length_slider, 1)
        self.length_spin = QSpinBox()
        self.length_spin.setRange(8, 128)
        self.length_spin.setFixedWidth(74)
        self.length_spin.valueChanged.connect(self._spin_changed)
        length_row.addWidget(self.length_spin)
        card.body.addLayout(length_row)

        options = QGridLayout()
        options.setHorizontalSpacing(24)
        options.setVerticalSpacing(10)
        self.cb_upper = QCheckBox("Uppercase (A-Z)")
        self.cb_lower = QCheckBox("Lowercase (a-z)")
        self.cb_digits = QCheckBox("Digits (0-9)")
        self.cb_symbols = QCheckBox("Symbols (!@#$)")
        self.cb_ambiguous = QCheckBox("Exclude look-alikes (Il1O0)")
        for box in (self.cb_upper, self.cb_lower, self.cb_digits,
                    self.cb_symbols, self.cb_ambiguous):
            box.toggled.connect(self.regenerate)
        options.addWidget(self.cb_upper, 0, 0)
        options.addWidget(self.cb_lower, 0, 1)
        options.addWidget(self.cb_digits, 1, 0)
        options.addWidget(self.cb_symbols, 1, 1)
        options.addWidget(self.cb_ambiguous, 2, 0, 1, 2)
        card.body.addLayout(options)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.use_btn = PrimaryButton("Use in new entry", "plus")
        self.use_btn.clicked.connect(
            lambda: self.use_password.emit(self.pw_output.text())
        )
        buttons.addWidget(self.use_btn)
        card.body.addLayout(buttons)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # -- passphrase tab ----------------------------------------------------
    def _passphrase_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(14)

        card = Card()
        output_widget, self.phrase_output = self._output_row()
        card.body.addWidget(output_widget)
        self.phrase_meter = StrengthMeter()

        words_row = QHBoxLayout()
        words_label = QLabel("Words")
        words_label.setProperty("role", "h3")
        words_row.addWidget(words_label)
        self.words_slider = QSlider(Qt.Orientation.Horizontal)
        self.words_slider.setRange(3, 12)
        self.words_slider.valueChanged.connect(self._words_changed)
        words_row.addWidget(self.words_slider, 1)
        self.words_spin = QSpinBox()
        self.words_spin.setRange(3, 12)
        self.words_spin.setFixedWidth(74)
        self.words_spin.valueChanged.connect(self._words_spin_changed)
        words_row.addWidget(self.words_spin)
        card.body.addLayout(words_row)

        opts = QGridLayout()
        opts.setHorizontalSpacing(24)
        opts.setVerticalSpacing(10)
        sep_label = QLabel("Separator")
        sep_label.setProperty("role", "h3")
        self.separator = QComboBox()
        for value, label in (("-", "Hyphen  -"), (".", "Dot  ."),
                             ("_", "Underscore  _"), (" ", "Space")):
            self.separator.addItem(label, value)
        self.separator.currentIndexChanged.connect(self.regenerate)
        opts.addWidget(sep_label, 0, 0)
        opts.addWidget(self.separator, 0, 1)
        self.cb_capitalize = QCheckBox("Capitalize each word")
        self.cb_number = QCheckBox("Append a number")
        self.cb_capitalize.toggled.connect(self.regenerate)
        self.cb_number.toggled.connect(self.regenerate)
        opts.addWidget(self.cb_capitalize, 1, 0)
        opts.addWidget(self.cb_number, 1, 1)
        card.body.addLayout(opts)
        card.body.addWidget(self.phrase_meter)

        hint = QLabel(f"{wordlist.word_count()} word vocabulary · "
                      "memorable and strong")
        hint.setProperty("role", "faint")
        card.body.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        use = PrimaryButton("Use in new entry", "plus")
        use.clicked.connect(
            lambda: self.use_password.emit(self.phrase_output.text())
        )
        buttons.addWidget(use)
        card.body.addLayout(buttons)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # -- shared output row -------------------------------------------------
    def _output_row(self) -> tuple[QWidget, QLineEdit]:
        """Build one output row; each tab owns its own line edit and buttons."""
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        output = QLineEdit()
        output.setReadOnly(True)
        output.setStyleSheet(
            "font-family:'Cascadia Mono','Consolas',monospace; font-size:16px;"
            "padding:14px 12px; letter-spacing:0.6px;"
        )
        row.addWidget(output, 1)

        regen = IconButton("refresh", "Regenerate")
        regen.clicked.connect(self.regenerate)
        row.addWidget(regen)

        copy = IconButton("copy", "Copy")
        copy.clicked.connect(
            lambda: self.copy_requested.emit(output.text(), True)
        )
        row.addWidget(copy)
        return widget, output

    # -- state -------------------------------------------------------------
    def _load_settings(self) -> None:
        self.length_slider.setValue(int(self.settings.get("gen_length")))
        self.cb_upper.setChecked(bool(self.settings.get("gen_upper")))
        self.cb_lower.setChecked(bool(self.settings.get("gen_lower")))
        self.cb_digits.setChecked(bool(self.settings.get("gen_digits")))
        self.cb_symbols.setChecked(bool(self.settings.get("gen_symbols")))
        self.cb_ambiguous.setChecked(bool(self.settings.get("gen_ambiguous")))
        self.words_slider.setValue(int(self.settings.get("gen_words")))
        self.cb_capitalize.setChecked(bool(self.settings.get("gen_capitalize")))
        self.cb_number.setChecked(bool(self.settings.get("gen_number")))
        index = self.separator.findData(self.settings.get("gen_separator"))
        self.separator.setCurrentIndex(max(0, index))

    def _length_changed(self, value: int) -> None:
        if self.length_spin.value() != value:
            self.length_spin.setValue(value)
        self.regenerate()

    def _spin_changed(self, value: int) -> None:
        if self.length_slider.value() != value:
            self.length_slider.setValue(value)
        self.regenerate()

    def _words_changed(self, value: int) -> None:
        if self.words_spin.value() != value:
            self.words_spin.setValue(value)
        self.regenerate()

    def _words_spin_changed(self, value: int) -> None:
        if self.words_slider.value() != value:
            self.words_slider.setValue(value)
        self.regenerate()

    def regenerate(self) -> None:
        if self.tabs.currentIndex() == 0:
            value = generator.generate_password(
                self.length_spin.value(),
                use_upper=self.cb_upper.isChecked(),
                use_lower=self.cb_lower.isChecked(),
                use_digits=self.cb_digits.isChecked(),
                use_symbols=self.cb_symbols.isChecked(),
                exclude_ambiguous=self.cb_ambiguous.isChecked(),
            )
            result = estimate(value)
            self.pw_meter.set_strength(
                result.score,
                f"{result.label} · {result.bits:.0f} bits · cracked in {result.crack_time}",
                result.color,
            )
        else:
            value = generator.generate_passphrase(
                self.words_spin.value(),
                separator=self.separator.currentData() or "-",
                capitalize=self.cb_capitalize.isChecked(),
                add_number=self.cb_number.isChecked(),
            )
            bits = generator.passphrase_bits(self.words_spin.value())
            score = 4 if bits >= 80 else 3 if bits >= 60 else 2 if bits >= 40 else 1
            label = ["Very weak", "Weak", "Fair", "Strong", "Excellent"][score]
            self.phrase_meter.set_strength(
                score, f"{label} · {bits:.0f} bits of entropy", "accent"
            )
        output = self.pw_output if self.tabs.currentIndex() == 0 else self.phrase_output
        output.setText(value)
        output.setCursorPosition(0)

    def save_defaults(self) -> None:
        self.settings.set("gen_length", self.length_spin.value())
        self.settings.set("gen_upper", self.cb_upper.isChecked())
        self.settings.set("gen_lower", self.cb_lower.isChecked())
        self.settings.set("gen_digits", self.cb_digits.isChecked())
        self.settings.set("gen_symbols", self.cb_symbols.isChecked())
        self.settings.set("gen_ambiguous", self.cb_ambiguous.isChecked())
        self.settings.set("gen_words", self.words_spin.value())
        self.settings.set("gen_separator", self.separator.currentData() or "-")
        self.settings.set("gen_capitalize", self.cb_capitalize.isChecked())
        self.settings.set("gen_number", self.cb_number.isChecked())
