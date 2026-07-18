"""Conditional request headers share one strict resource-version parser."""

import pytest

from careeros_api.conditional_requests import parse_if_match_version


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ('"1"', 1),
        ('"0000000001"', 1),
        ('"2147483647"', 2_147_483_647),
    ],
)
def test_parse_if_match_version_accepts_quoted_positive_int32(header: str, expected: int) -> None:
    assert parse_if_match_version(header) == expected


@pytest.mark.parametrize(
    "header",
    [
        "1",
        ' "1"',
        '"1" ',
        'W/"1"',
        '"+1"',
        '"-1"',
        '"0"',
        '"0000000000"',
        '"2147483648"',
        '"99999999999"',
        '"one"',
        '"1","2"',
    ],
)
def test_parse_if_match_version_rejects_noncanonical_or_out_of_range_values(
    header: str,
) -> None:
    with pytest.raises(ValueError):
        parse_if_match_version(header)
