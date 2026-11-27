"""Offline password strength estimation.

A compact, dependency-free heuristic (no network, no zxcvbn package):
entropy from the character pool, then penalties for the patterns that make
real passwords weak — repeats, runs, keyboard walks, dates and dictionary words.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .wordlist import WORDS

_LOWER = "abcdefghijklmnopqrstuvwxyz"
_UPPER = _LOWER.upper()
_DIGITS = "0123456789"
_SYMBOLS = "!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~"

COMMON = {
    "password", "passw0rd", "123456", "12345678", "123456789", "qwerty",
    "qwerty123", "abc123", "letmein", "welcome", "monkey", "dragon",
    "iloveyou", "admin", "login", "master", "sunshine", "princess",
    "football", "baseball", "shadow", "superman", "michael", "trustno1",
    "changeme", "secret", "summer", "winter", "spring", "autumn",
    "hunter2", "root", "toor", "test", "guest", "default", "vault",
}

_KEYBOARD_RUNS = [
    "qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890",
    "qazwsx", "wsxedc", "poiuyt", "lkjhgf",
]

_WORDSET = {w.lower() for w in WORDS}

_LABELS = ["Very weak", "Weak", "Fair", "Strong", "Excellent"]
_COLORS = ["danger", "danger", "warning", "success", "accent"]


@dataclass
class Strength:
    score: int  # 0..4
    label: str
    bits: float
    crack_seconds: float
    color: str
    feedback: list[str] = field(default_factory=list)

    @property
    def crack_time(self) -> str:
        return humanize_seconds(self.crack_seconds)


def humanize_seconds(seconds: float) -> str:
    if seconds < 1:
        return "instantly"
    units = [
        (60, "second"), (60, "minute"), (24, "hour"),
        (365, "day"), (100, "year"),
    ]
    value = seconds
    name = "second"
    for factor, unit in units:
        if value < factor:
            name = unit
            break
        value /= factor
        name = unit
    else:
        return "centuries"
    if name == "year" and value > 100:
        return "centuries"
    rounded = max(1, round(value))
    return f"{rounded} {name}{'s' if rounded != 1 else ''}"


def _pool_size(password: str) -> int:
    pool = 0
    if any(c in _LOWER for c in password):
        pool += 26
    if any(c in _UPPER for c in password):
        pool += 26
    if any(c in _DIGITS for c in password):
        pool += 10
    if any(c in _SYMBOLS for c in password):
        pool += 33
    if any(ord(c) > 127 for c in password):
        pool += 100
    return max(pool, 1)


def _has_sequence(password: str) -> bool:
    low = password.lower()
    for run in _KEYBOARD_RUNS:
        for size in (4,):
            for i in range(len(run) - size + 1):
                if run[i : i + size] in low:
                    return True
                if run[i : i + size][::-1] in low:
                    return True
    # ascending / descending runs like abcd or 4321
    for i in range(len(low) - 3):
        chunk = low[i : i + 4]
        if all(ord(chunk[j + 1]) - ord(chunk[j]) == 1 for j in range(3)):
            return True
        if all(ord(chunk[j]) - ord(chunk[j + 1]) == 1 for j in range(3)):
            return True
    return False


def _has_date(password: str) -> bool:
    return bool(re.search(r"(19|20)\d{2}", password))


def _has_repeat(password: str) -> bool:
    return bool(re.search(r"(.)\1{2,}", password))


def _dictionary_hits(password: str) -> list[str]:
    low = password.lower()
    hits = [w for w in COMMON if w in low]
    if not hits:
        hits = [w for w in _WORDSET if len(w) >= 4 and w in low][:3]
    return hits


def estimate(password: str) -> Strength:
    if not password:
        return Strength(0, "Empty", 0.0, 0.0, "danger", ["Enter a password."])

    pool = _pool_size(password)
    bits = len(password) * math.log2(pool)

    feedback: list[str] = []
    penalty = 0.0

    if _has_repeat(password):
        penalty += 12
        feedback.append("Avoid repeated characters (aaa, 111).")
    if _has_sequence(password):
        penalty += 14
        feedback.append("Avoid keyboard or alphabet runs (qwerty, abcd).")
    if _has_date(password):
        penalty += 6
        feedback.append("Years and dates are easy to guess.")
    hits = _dictionary_hits(password)
    if hits:
        penalty += 18 + 6 * len(hits)
        feedback.append(f"Contains a common word: {hits[0]}.")

    if len(password) < 8:
        feedback.append("Use at least 12 characters.")
    if not any(c.isdigit() for c in password):
        feedback.append("Add numbers.")
    if not any(c in _SYMBOLS for c in password):
        feedback.append("Add symbols.")
    if not any(c.isupper() for c in password):
        feedback.append("Mix in uppercase letters.")

    bits = max(0.0, bits - penalty)

    # Offline attack at 10 billion guesses/sec, ~ half the keyspace.
    crack_seconds = (2 ** bits) / 2 / 1e10

    if bits < 28:
        score = 0
    elif bits < 40:
        score = 1
    elif bits < 60:
        score = 2
    elif bits < 80:
        score = 3
    else:
        score = 4

    return Strength(score, _LABELS[score], round(bits, 1), crack_seconds,
                    _COLORS[score], feedback)
