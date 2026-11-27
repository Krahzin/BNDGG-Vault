"""RFC 6238 TOTP generation (no external dependency)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
import urllib.parse


def normalize_secret(secret: str) -> str:
    text = (secret or "").strip()
    if text.lower().startswith("otpauth://"):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(text).query)
        text = (query.get("secret") or [""])[0]
    text = "".join(text.split()).replace("-", "").upper().rstrip("=")
    return text


def is_valid(secret: str) -> bool:
    text = normalize_secret(secret)
    if len(text) < 8:
        return False
    try:
        _b32(text)
        return True
    except Exception:  # noqa: BLE001
        return False


def _b32(secret: str) -> bytes:
    text = normalize_secret(secret)
    padding = "=" * ((8 - len(text) % 8) % 8)
    return base64.b32decode(text + padding, casefold=True)


def code(secret: str, at: float | None = None, period: int = 30,
         digits: int = 6) -> str:
    counter = int((at if at is not None else time.time()) // period)
    digest = hmac.new(_b32(secret), struct.pack(">Q", counter),
                      hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** digits)).zfill(digits)


def remaining(period: int = 30) -> int:
    return period - int(time.time()) % period


def pretty(code_value: str) -> str:
    return f"{code_value[:3]} {code_value[3:]}" if len(code_value) == 6 else code_value
