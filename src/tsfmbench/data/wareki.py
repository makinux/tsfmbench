"""Strict Japanese era date parsing."""

from __future__ import annotations

import re
from datetime import date

_ERAS: dict[str, tuple[date, date]] = {
    "M": (date(1868, 1, 25), date(1912, 7, 29)),
    "T": (date(1912, 7, 30), date(1926, 12, 24)),
    "S": (date(1926, 12, 25), date(1989, 1, 7)),
    "H": (date(1989, 1, 8), date(2019, 4, 30)),
    "R": (date(2019, 5, 1), date.max),
}
_WAREKI_RE = re.compile(r"^\s*([MTSHR])\s*(\d+)\.(\d{1,2})\.(\d{1,2})\s*$", re.IGNORECASE)


def parse_wareki(s: str) -> date:
    """Parse ``R8.7.31`` while enforcing the exact historical era boundary."""

    match = _WAREKI_RE.fullmatch(s)
    if match is None:
        raise ValueError(f"invalid wareki date: {s!r}")
    era = match.group(1).upper()
    era_year, month, day = (int(value) for value in match.groups()[1:])
    if era_year < 1:
        raise ValueError(f"era year must be positive: {s!r}")

    first, last = _ERAS[era]
    try:
        parsed = date(first.year + era_year - 1, month, day)
    except ValueError as exc:
        raise ValueError(f"invalid wareki date: {s!r}") from exc
    if not first <= parsed <= last:
        raise ValueError(f"date is outside the {era} era: {s!r}")
    return parsed

