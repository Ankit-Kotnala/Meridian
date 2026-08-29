"""Identity persistence and security implementations.

Security adapters are loaded lazily so processes that only register the
identity database mappings do not need the optional identity dependency set.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rezumi.modules.identity.infrastructure.security import (
        Argon2PasswordHasher,
        HmacTokenManager,
        NormalizedEmailValidator,
        SystemClock,
    )

__all__ = [
    "Argon2PasswordHasher",
    "HmacTokenManager",
    "NormalizedEmailValidator",
    "SystemClock",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    security = import_module(".security", __name__)
    value = getattr(security, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
