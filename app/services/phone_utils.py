from __future__ import annotations

import re

_NON_DIGITS = re.compile(r"\D+")


def normalize_kz_phone(raw: str | None) -> str | None:
    """Normalize a Kazakhstan phone to 11-digit `7XXXXXXXXXX`.

    Accepts: +7XXX..., 8XXX..., 7XXX..., 10 digits (assumed 7-prefixed),
    with any spacing/punctuation. Returns None for anything invalid.
    """
    if not raw:
        return None
    digits = _NON_DIGITS.sub("", str(raw))
    if not digits:
        return None
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits[0] == "7":
        return digits
    return None
