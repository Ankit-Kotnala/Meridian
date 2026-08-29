"""Strict parsing for HTTP conditional-request resource versions."""

import re

IF_MATCH_VERSION_PATTERN = r'^"[0-9]{1,10}"$'
MAX_RESOURCE_VERSION = 2_147_483_647


def parse_if_match_version(value: str) -> int:
    """Parse the canonical quoted positive signed-int32 resource version."""

    if re.fullmatch(IF_MATCH_VERSION_PATTERN, value) is None:
        raise ValueError("If-Match must contain a quoted version")
    version = int(value[1:-1])
    if not 1 <= version <= MAX_RESOURCE_VERSION:
        raise ValueError("If-Match version must be a positive signed integer")
    return version
