"""Cryptographic core: Argon2id key derivation + AES-256-GCM authenticated encryption.

File format (v2)
----------------
{
  "format": "bndgg-vault",
  "version": 2,
  "cipher": "AES-256-GCM",
  "kdf": {"algo": "argon2id", "time_cost": 3, "memory_cost": 65536,
          "parallelism": 4, "salt": "<b64>"},
  "nonce": "<b64, 12 bytes>",
  "payload": "<b64 ciphertext||tag>",
  "created": "<iso8601>",
  "modified": "<iso8601>"
}

Everything except `nonce` and `payload` is authenticated as AAD, so header
tampering (downgrading KDF params, swapping salts) is detected on unlock.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT = "bndgg-vault"
VERSION = 2
CIPHER = "AES-256-GCM"
KDF_ALGO = "argon2id"

KEY_LEN = 32
SALT_LEN = 16
NONCE_LEN = 12

DEFAULT_KDF = {
    "algo": KDF_ALGO,
    "time_cost": 3,
    "memory_cost": 65536,
    "parallelism": 4,
}

# Bounds enforced on load so a hostile file cannot request absurd work factors.
KDF_LIMITS = {
    "time_cost": (1, 10),
    "memory_cost": (8 * 1024, 1024 * 1024),  # KiB: 8 MiB .. 1 GiB
    "parallelism": (1, 16),
}

AAD_FIELDS = ("format", "version", "cipher", "kdf")


class VaultError(Exception):
    """Base class for vault failures."""


class InvalidPassword(VaultError):
    """The password is wrong, or the file was tampered with."""


class VaultFormatError(VaultError):
    """The file is not a readable BNDGG vault."""


def b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def b64d(text: str) -> bytes:
    try:
        return base64.b64decode(text, validate=True)
    except Exception as exc:  # noqa: BLE001 - normalise to format error
        raise VaultFormatError("Corrupt base64 field in vault header.") from exc


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_header(kdf: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a fresh authenticated header, including a random salt."""
    params = dict(DEFAULT_KDF)
    if kdf:
        params.update({k: kdf[k] for k in DEFAULT_KDF if k in kdf})
    params["salt"] = b64e(os.urandom(SALT_LEN))
    return {
        "format": FORMAT,
        "version": VERSION,
        "cipher": CIPHER,
        "kdf": params,
        "created": utcnow(),
    }


def _validate_header(header: dict[str, Any]) -> None:
    if not isinstance(header, dict):
        raise VaultFormatError("Vault header is missing.")
    if header.get("format") != FORMAT:
        raise VaultFormatError("Not a BNDGG vault file.")
    if header.get("version") != VERSION:
        raise VaultFormatError(
            f"Unsupported vault version: {header.get('version')!r}."
        )
    if header.get("cipher") != CIPHER:
        raise VaultFormatError("Unsupported cipher.")

    kdf = header.get("kdf")
    if not isinstance(kdf, dict) or kdf.get("algo") != KDF_ALGO:
        raise VaultFormatError("Unsupported key derivation function.")

    for field, (low, high) in KDF_LIMITS.items():
        value = kdf.get(field)
        if not isinstance(value, int) or not low <= value <= high:
            raise VaultFormatError(f"Refusing unsafe KDF parameter: {field}.")

    if len(b64d(kdf.get("salt", ""))) != SALT_LEN:
        raise VaultFormatError("Invalid salt length.")


def _aad(header: dict[str, Any]) -> bytes:
    subset = {key: header.get(key) for key in AAD_FIELDS}
    return json.dumps(subset, sort_keys=True, separators=(",", ":")).encode("utf-8")


def derive_key(password: str, header: dict[str, Any]) -> bytes:
    """Derive the 256-bit vault key. Deliberately slow (~0.5s)."""
    _validate_header(header)
    kdf = header["kdf"]
    if not password:
        raise InvalidPassword("Master password is required.")
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=b64d(kdf["salt"]),
        time_cost=int(kdf["time_cost"]),
        memory_cost=int(kdf["memory_cost"]),
        parallelism=int(kdf["parallelism"]),
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def seal(header: dict[str, Any], key: bytes, payload: dict[str, Any]) -> dict[str, Any]:
    """Encrypt `payload` into a complete, storable envelope."""
    _validate_header(header)
    nonce = os.urandom(NONCE_LEN)
    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, _aad(header))
    envelope = dict(header)
    envelope["nonce"] = b64e(nonce)
    envelope["payload"] = b64e(ciphertext)
    envelope["modified"] = utcnow()
    return envelope


def open_envelope(
    envelope: dict[str, Any], password: str
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Verify + decrypt. Returns (key, payload, header)."""
    _validate_header(envelope)
    key = derive_key(password, envelope)
    payload = open_with_key(envelope, key)
    header = {k: envelope[k] for k in (*AAD_FIELDS, "created") if k in envelope}
    return key, payload, header


def open_with_key(envelope: dict[str, Any], key: bytes) -> dict[str, Any]:
    """Decrypt with an already-derived key (no KDF cost)."""
    _validate_header(envelope)
    try:
        nonce = b64d(envelope.get("nonce", ""))
        if len(nonce) != NONCE_LEN:
            raise VaultFormatError("Invalid nonce length.")
        ciphertext = b64d(envelope.get("payload", ""))
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, _aad(envelope))
    except InvalidTag as exc:
        raise InvalidPassword("Incorrect master password or tampered vault.") from exc
    try:
        data = json.loads(plaintext.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise VaultFormatError("Vault payload is corrupt.") from exc
    if not isinstance(data, dict):
        raise VaultFormatError("Vault payload has an unexpected shape.")
    return data


def is_legacy_vault(data: Any) -> bool:
    """True for the old Fernet-based (v1) BNDGG file layout."""
    return isinstance(data, dict) and "vault_blob" in data and "format" not in data
