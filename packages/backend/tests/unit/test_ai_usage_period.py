"""Calendar boundary regression for monthly AI budgets."""

from datetime import UTC, datetime

from careeros.modules.change_studio.infrastructure.usage import _period_ttl_seconds


def test_monthly_budget_retry_boundary_is_next_utc_month() -> None:
    july = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
    december = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

    assert _period_ttl_seconds(july) == 5 * 86_400 + 12 * 3_600
    assert _period_ttl_seconds(december) == 1
