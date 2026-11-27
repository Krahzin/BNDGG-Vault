"""Application preferences, persisted with QSettings (registry on Windows)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings

from .. import APP_NAME, ORG_NAME

DEFAULTS: dict[str, Any] = {
    # Appearance
    "theme": "midnight",
    # Security
    "auto_lock_minutes": 5,
    "lock_on_minimize": False,
    "clipboard_clear_seconds": 30,
    "reveal_seconds": 15,
    "confirm_delete": True,
    "keep_history": True,
    # Generator
    "gen_length": 20,
    "gen_upper": True,
    "gen_lower": True,
    "gen_digits": True,
    "gen_symbols": True,
    "gen_ambiguous": False,
    "gen_words": 5,
    "gen_separator": "-",
    "gen_capitalize": True,
    "gen_number": False,
    # Vault
    "vault_path": "",
    "recent_vaults": [],
    "window_geometry": b"",
    "unlocked_page": "vault",
}


class AppSettings:
    def __init__(self) -> None:
        self._store = QSettings(ORG_NAME, "Vault")

    # -- generic -----------------------------------------------------------
    def get(self, key: str) -> Any:
        default = DEFAULTS.get(key)
        if default is None:
            return self._store.value(key)
        value = self._store.value(key, default)
        if isinstance(default, bool):
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if isinstance(default, int):
            try:
                return int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default
        if isinstance(default, list):
            if value is None:
                return list(default)
            if isinstance(value, str):
                return [value] if value else []
            return list(value)
        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        self._store.setValue(key, value)

    def sync(self) -> None:
        self._store.sync()

    # -- vault paths -------------------------------------------------------
    @property
    def vault_path(self) -> str:
        return str(self.get("vault_path") or "")

    @vault_path.setter
    def vault_path(self, value: str) -> None:
        self.set("vault_path", value)
        if value:
            self.push_recent(value)

    @property
    def recent_vaults(self) -> list[str]:
        recent = [p for p in self.get("recent_vaults") if p]
        current = self.vault_path
        return [p for p in recent if p != current]

    def push_recent(self, path: str) -> None:
        recent = [p for p in self.get("recent_vaults") if p and p != path]
        recent.insert(0, path)
        self.set("recent_vaults", recent[:6])

    def remove_recent(self, path: str) -> None:
        recent = [p for p in self.get("recent_vaults") if p != path]
        self.set("recent_vaults", recent)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AppSettings {APP_NAME}>"
