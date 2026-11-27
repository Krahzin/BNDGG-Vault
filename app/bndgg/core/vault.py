"""Vault model: entries, atomic persistence, backups and transfer formats."""

from __future__ import annotations

import base64
import csv
import json
import os
import secrets
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import crypto
from .crypto import InvalidPassword, VaultError, VaultFormatError, utcnow

SCHEMA = 1
HISTORY_LIMIT = 5


def _iso_now() -> str:
    return utcnow()


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:  # noqa: BLE001
        return None


@dataclass
class Entry:
    name: str
    password: str = ""
    username: str = ""
    url: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    totp: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created: str = field(default_factory=_iso_now)
    updated: str = field(default_factory=_iso_now)
    history: list[dict[str, str]] = field(default_factory=list)

    # -- serialisation -----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "password": self.password,
            "url": self.url,
            "notes": self.notes,
            "tags": list(self.tags),
            "totp": self.totp,
            "created": self.created,
            "updated": self.updated,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entry":
        def text(key: str) -> str:
            value = data.get(key, "")
            return value if isinstance(value, str) else str(value or "")

        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        history = data.get("history") or []
        if not isinstance(history, list):
            history = []

        return cls(
            id=text("id") or uuid.uuid4().hex,
            name=text("name"),
            username=text("username"),
            password=text("password"),
            url=text("url"),
            notes=text("notes"),
            tags=[str(t) for t in tags if str(t).strip()],
            totp=text("totp"),
            created=text("created") or _iso_now(),
            updated=text("updated") or _iso_now(),
            history=[h for h in history if isinstance(h, dict)],
        )

    # -- helpers -----------------------------------------------------------
    def touch(self) -> None:
        self.updated = _iso_now()

    def age_days(self) -> float:
        dt = _parse_dt(self.updated)
        if not dt:
            return 0.0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)


class Vault:
    """An encrypted vault bound to a single file on disk."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.entries: dict[str, Entry] = {}
        self._key: bytes | None = None
        self._header: dict[str, Any] | None = None
        self._created: str | None = None

    # -- state -------------------------------------------------------------
    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    def lock(self) -> None:
        self._key = None
        self.entries = {}

    def _require_unlocked(self) -> None:
        if not self.is_unlocked or self._header is None:
            raise VaultError("Vault is locked.")

    # -- create / open -----------------------------------------------------
    @classmethod
    def create(cls, path: str | os.PathLike[str], password: str,
               kdf: dict[str, Any] | None = None) -> "Vault":
        if not password:
            raise VaultError("Master password cannot be empty.")
        vault = cls(path)
        vault._header = crypto.new_header(kdf)
        vault._key = crypto.derive_key(password, vault._header)
        vault._created = vault._header.get("created")
        vault.entries = {}
        vault.save()
        return vault

    @staticmethod
    def read_file(path: str | os.PathLike[str]) -> dict[str, Any]:
        p = Path(path)
        if not p.exists():
            raise VaultFormatError(f"Vault file not found: {p}")
        try:
            with open(p, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise VaultFormatError("Vault file is not valid JSON.") from exc
        if not isinstance(data, dict):
            raise VaultFormatError("Vault file has an unexpected shape.")
        return data

    @staticmethod
    def inspect(path: str | os.PathLike[str]) -> str:
        """Return 'v2', 'legacy', or 'unknown' without needing a password."""
        try:
            data = Vault.read_file(path)
        except VaultError:
            return "unknown"
        if data.get("format") == crypto.FORMAT:
            return "v2"
        if crypto.is_legacy_vault(data):
            return "legacy"
        return "unknown"

    def unlock(self, password: str) -> None:
        data = self.read_file(self.path)
        if crypto.is_legacy_vault(data):
            raise VaultFormatError(
                "This is a legacy v1 vault. Import it from Settings → Import."
            )
        key, payload, header = crypto.open_envelope(data, password)
        self._key = key
        self._header = header
        self._created = header.get("created")
        self._load_payload(payload)

    def _load_payload(self, payload: dict[str, Any]) -> None:
        raw_entries = payload.get("entries") or {}
        if not isinstance(raw_entries, dict):
            raise VaultFormatError("Vault entries are corrupt.")
        entries: dict[str, Entry] = {}
        for key, value in raw_entries.items():
            if not isinstance(value, dict):
                continue
            entry = Entry.from_dict(value)
            entries[entry.id or str(key)] = entry
        self.entries = entries

    # -- persistence -------------------------------------------------------
    def save(self) -> None:
        self._require_unlocked()
        payload = {
            "schema": SCHEMA,
            "entries": {eid: e.to_dict() for eid, e in self.entries.items()},
            "saved": _iso_now(),
        }
        envelope = crypto.seal(self._header, self._key, payload)  # type: ignore[arg-type]
        self._write_atomic(envelope)
        self._header["modified"] = envelope["modified"]

    def _write_atomic(self, envelope: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(envelope, indent=2)
        tmp = self.path.with_name(self.path.name + ".tmp")

        old_bytes: bytes | None = None
        if self.path.exists():
            try:
                old_bytes = self.path.read_bytes()
            except OSError:
                old_bytes = None

        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)

        if old_bytes:
            backup = self.path.with_name(self.path.name + ".bak")
            try:
                with open(backup, "wb") as handle:
                    handle.write(old_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError:
                pass

    # -- queries -----------------------------------------------------------
    def sorted_entries(self, query: str = "", tag: str | None = None) -> list[Entry]:
        query = query.strip().casefold()
        result = []
        for entry in self.entries.values():
            if tag and tag not in entry.tags:
                continue
            if query:
                haystack = " ".join(
                    [entry.name, entry.username, entry.url, " ".join(entry.tags)]
                ).casefold()
                if query not in haystack:
                    continue
            result.append(entry)
        result.sort(key=lambda e: (e.name.casefold(), e.username.casefold()))
        return result

    def all_tags(self) -> list[str]:
        tags = {tag for entry in self.entries.values() for tag in entry.tags}
        return sorted(tags, key=str.casefold)

    def find_by_name(self, name: str, exclude_id: str | None = None) -> Entry | None:
        wanted = name.strip().casefold()
        for entry in self.entries.values():
            if entry.id != exclude_id and entry.name.strip().casefold() == wanted:
                return entry
        return None

    def get(self, entry_id: str) -> Entry | None:
        return self.entries.get(entry_id)

    # -- mutations ---------------------------------------------------------
    def add_entry(self, entry: Entry) -> Entry:
        self._require_unlocked()
        entry.name = entry.name.strip()
        entry.touch()
        self.entries[entry.id] = entry
        self.save()
        return entry

    def update_entry(self, entry_id: str, entry: Entry) -> Entry:
        self._require_unlocked()
        current = self.entries.get(entry_id)
        if current is None:
            raise VaultError("Entry no longer exists.")
        if entry.password != current.password and current.password:
            current.history.insert(0, {"password": current.password,
                                       "changed": current.updated})
            current.history = current.history[:HISTORY_LIMIT]
        entry.id = entry_id
        entry.created = current.created
        entry.history = current.history
        entry.touch()
        self.entries[entry_id] = entry
        self.save()
        return entry

    def delete_entry(self, entry_id: str) -> None:
        self._require_unlocked()
        self.entries.pop(entry_id, None)
        self.save()

    def change_master_password(self, current: str, new: str) -> None:
        self._require_unlocked()
        if not new or len(new) < 8:
            raise VaultError("New master password must be at least 8 characters.")
        probe = crypto.derive_key(current, self._header)  # type: ignore[arg-type]
        if not secrets.compare_digest(probe, self._key or b""):
            raise InvalidPassword("Current master password is incorrect.")
        header = crypto.new_header(self._header["kdf"])  # type: ignore[index]
        header["created"] = self._created or header["created"]
        key = crypto.derive_key(new, header)
        self._header, self._key = header, key
        self.save()

    # -- transfer ----------------------------------------------------------
    def relocate(self, new_path: str | os.PathLike[str]) -> Path:
        """Move the vault to a new file, leaving the old one in place."""
        self._require_unlocked()
        old = self.path
        self.path = Path(new_path)
        self.save()
        return old

    def backup_to(self, dest: str | os.PathLike[str]) -> Path:
        self.save()
        target = Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.path, target)
        return target

    def export_encrypted(self, dest: str | os.PathLike[str]) -> Path:
        return self.backup_to(dest)

    def import_encrypted(self, src: str | os.PathLike[str], password: str,
                         merge: bool = True) -> int:
        self._require_unlocked()
        data = self.read_file(src)
        _, payload, _ = crypto.open_envelope(data, password)
        incoming: dict[str, Entry] = {}
        for value in (payload.get("entries") or {}).values():
            if isinstance(value, dict):
                entry = Entry.from_dict(value)
                incoming[entry.id] = entry
        if not merge:
            self.entries = incoming
        else:
            existing_names = {e.name.casefold() for e in self.entries.values()}
            for entry in incoming.values():
                if entry.name.casefold() in existing_names:
                    entry.name = f"{entry.name} (imported)"
                    existing_names.add(entry.name.casefold())
                self.entries[entry.id] = entry
        self.save()
        return len(incoming)

    def export_csv(self, dest: str | os.PathLike[str]) -> Path:
        self._require_unlocked()
        target = Path(dest)
        with open(target, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["name", "username", "password", "url", "notes",
                             "tags", "totp", "created", "updated"])
            for entry in self.sorted_entries():
                writer.writerow([
                    entry.name, entry.username, entry.password, entry.url,
                    entry.notes, ",".join(entry.tags), entry.totp,
                    entry.created, entry.updated,
                ])
        return target

    def import_legacy(self, src: str | os.PathLike[str], password: str) -> int:
        """Import an old BNDGG v1 vault (Fernet + Argon2id, no header)."""
        self._require_unlocked()
        from argon2.low_level import Type, hash_secret_raw
        from cryptography.fernet import Fernet, InvalidToken

        data = self.read_file(src)
        if not crypto.is_legacy_vault(data):
            raise VaultFormatError("Not a legacy BNDGG vault.")
        salt_b64 = data.get("salt")
        blob = data.get("vault_blob")
        if not salt_b64 or not blob:
            raise VaultFormatError("Legacy vault is missing its salt or data.")
        try:
            salt = base64.b64decode(salt_b64)
            raw = hash_secret_raw(
                secret=password.encode(), salt=salt, time_cost=3,
                memory_cost=65536, parallelism=4, hash_len=32, type=Type.ID,
            )
            plaintext = Fernet(base64.urlsafe_b64encode(raw)).decrypt(blob.encode())
            payload = json.loads(plaintext.decode())
        except InvalidToken as exc:
            raise InvalidPassword("Incorrect legacy master password.") from exc
        except Exception as exc:  # noqa: BLE001
            raise VaultFormatError(f"Could not read legacy vault: {exc}") from exc

        if not isinstance(payload, dict):
            raise VaultFormatError("Legacy vault payload is corrupt.")

        existing = {e.name.casefold() for e in self.entries.values()}
        count = 0
        for name, value in payload.items():
            if not isinstance(value, dict):
                continue
            entry = Entry(
                name=str(name),
                password=str(value.get("password", "")),
                created=str(value.get("created") or _iso_now()),
            )
            if entry.name.casefold() in existing:
                entry.name = f"{entry.name} (imported)"
            existing.add(entry.name.casefold())
            self.entries[entry.id] = entry
            count += 1
        self.save()
        return count

    # -- health ------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        from .strength import estimate

        total = len(self.entries)
        weak = [e for e in self.entries.values() if estimate(e.password).score <= 1]
        counts: dict[str, int] = {}
        for entry in self.entries.values():
            if entry.password:
                counts[entry.password] = counts.get(entry.password, 0) + 1
        reused = [
            e for e in self.entries.values()
            if e.password and counts.get(e.password, 0) > 1
        ]
        stale = [e for e in self.entries.values() if e.age_days() > 365]
        return {
            "total": total,
            "weak": weak,
            "reused": reused,
            "stale": stale,
            "empty": [e for e in self.entries.values() if not e.password],
        }
