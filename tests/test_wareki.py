from datetime import date

import pytest

from tsfmbench.data.wareki import parse_wareki


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("S64.1.7", date(1989, 1, 7)),
        ("H1.1.8", date(1989, 1, 8)),
        ("H31.4.30", date(2019, 4, 30)),
        ("R1.5.1", date(2019, 5, 1)),
        ("R8.7.31", date(2026, 7, 31)),
    ],
)
def test_parse_wareki_boundaries(value: str, expected: date) -> None:
    assert parse_wareki(value) == expected


@pytest.mark.parametrize("value", ["S64.1.8", "H1.1.7", "H31.5.1", "R1.4.30", "R0.5.1"])
def test_parse_wareki_rejects_nonexistent_era_dates(value: str) -> None:
    with pytest.raises(ValueError):
        parse_wareki(value)

