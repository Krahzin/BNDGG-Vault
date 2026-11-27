"""Headless UI smoke test — builds the real window offscreen.

Run with:  .venv\\Scripts\\python -m unittest tests.test_ui_smoke -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from bndgg.core.settings import AppSettings
    from bndgg.core.vault import Entry, Vault
    from bndgg.ui import themes
    from bndgg.ui.main_window import MainWindow

    HAVE_QT = True
except ImportError:  # pragma: no cover - Qt not installed yet
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class UiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.tmp = tempfile.TemporaryDirectory()
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, cls.tmp.name
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_full_window_lifecycle(self) -> None:
        settings = AppSettings()
        settings.set("vault_path", "")

        themes.apply_theme(self.app, "midnight")
        window = MainWindow(settings)

        vault = Vault.create(Path(self.tmp.name) / "smoke.json", "smoke-password-1")
        vault.add_entry(Entry(name="GitHub", username="octocat",
                              password="vN7$kQ2!mR9@wZ4#", tags=["work"]))
        vault.add_entry(Entry(name="Mail", username="me@example.com",
                              password="another-pass", tags=["personal"]))

        window._set_vault(vault)
        window.stack.setCurrentWidget(window.workspace)
        window.vault_view.reload()
        self.assertEqual(window.vault_view.table.rowCount(), 2)

        entry = next(iter(vault.entries.values()))
        window.vault_view._show(entry)
        window.vault_view.copy_password()
        window.vault_view._tick_totp()

        for index in range(3):
            window._nav_to(index)

        for key in themes.THEME_ORDER:
            window._change_theme(key)
            self.assertTrue(themes.build_qss(key))

        generator = window.generator_view
        self.assertIsNot(generator.pw_output, generator.phrase_output)
        self.assertTrue(generator.pw_output.text())
        self.assertTrue(generator.phrase_output.text())
        self.assertNotEqual(generator.pw_output.text(), generator.phrase_output.text())
        generator.tabs.setCurrentIndex(0)
        generator.regenerate()
        self.assertTrue(generator.pw_output.text())
        generator.tabs.setCurrentIndex(1)
        generator.regenerate()
        self.assertTrue(generator.phrase_output.text())

        window.settings_view.refresh()
        window.lock_vault()
        self.assertFalse(vault.is_unlocked)
        window.close()

    def test_all_themes_compile(self) -> None:
        for key in themes.THEME_ORDER:
            qss = themes.build_qss(key)
            self.assertIn("QPushButton", qss)
            self.assertNotIn("$", qss)


if __name__ == "__main__":
    unittest.main()
