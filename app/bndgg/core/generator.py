"""Password and passphrase generation.

Every password is guaranteed to contain at least one character from each
enabled class (the old generator could hand back an all-symbol string).
"""

from __future__ import annotations

import secrets
import string

from .wordlist import WORDS

AMBIGUOUS = "Il1O0o|`'\";:,.{}[]()/\\"

LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>/?~"

_rng = secrets.SystemRandom()


def _pool(use_upper: bool, use_lower: bool, use_digits: bool,
          use_symbols: bool, exclude_ambiguous: bool) -> list[str]:
    pools: list[str] = []
    if use_upper:
        pools.append(UPPER)
    if use_lower:
        pools.append(LOWER)
    if use_digits:
        pools.append(DIGITS)
    if use_symbols:
        pools.append(SYMBOLS)
    if not pools:
        pools = [LOWER]

    chars = "".join(pools)
    if exclude_ambiguous:
        chars = "".join(c for c in chars if c not in AMBIGUOUS)
    # De-duplicate while keeping order stable.
    seen: dict[str, None] = {}
    for c in chars:
        seen.setdefault(c, None)
    return list(seen)


def generate_password(
    length: int = 20,
    *,
    use_upper: bool = True,
    use_lower: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
    exclude_ambiguous: bool = False,
) -> str:
    length = max(4, min(int(length), 128))
    pool = _pool(use_upper, use_lower, use_digits, use_symbols, exclude_ambiguous)
    if not pool:
        pool = list(LOWER)

    required: list[str] = []
    if use_upper:
        required.append(_pick(UPPER, exclude_ambiguous))
    if use_lower:
        required.append(_pick(LOWER, exclude_ambiguous))
    if use_digits:
        required.append(_pick(DIGITS, exclude_ambiguous))
    if use_symbols:
        required.append(_pick(SYMBOLS, exclude_ambiguous))

    required = [c for c in required if c]
    required = required[:length]
    rest = [secrets.choice(pool) for _ in range(length - len(required))]
    chars = required + rest
    _rng.shuffle(chars)
    return "".join(chars)


def _pick(alphabet: str, exclude_ambiguous: bool) -> str:
    candidates = [c for c in alphabet if not (exclude_ambiguous and c in AMBIGUOUS)]
    return secrets.choice(candidates) if candidates else ""


def generate_passphrase(
    words: int = 5,
    *,
    separator: str = "-",
    capitalize: bool = True,
    add_number: bool = False,
) -> str:
    words = max(3, min(int(words), 12))
    picked = [secrets.choice(WORDS) for _ in range(words)]
    if capitalize:
        picked = [w.capitalize() for w in picked]
    if add_number:
        picked.append(str(secrets.randbelow(90) + 10))
    return separator.join(picked)


def passphrase_bits(words: int) -> float:
    import math

    return max(3, min(int(words), 12)) * math.log2(max(len(WORDS), 2))
