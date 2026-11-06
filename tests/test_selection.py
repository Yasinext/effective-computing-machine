from __future__ import annotations

import pytest

from app.errors import ApiSchemaError
from app.selection import select_recent_clients


def row(client_id: int, created: str, partner: int = 1457, **extra: object) -> dict:
    return {
        "Id": client_id,
        "Login": f"user{client_id}",
        "PartnerId": partner,
        "Created": created,
        "PartnerClientCategoryId": 908,
        **extra,
    }


def test_created_controls_order_not_last_login() -> None:
    objects = [
        row(1, "2026-11-06T10:00:00+03:00", LastLoginTime="2099-01-01T00:00:00+03:00"),
        row(2, "2026-11-06T12:00:00+03:00", LastLoginTime="2000-01-01T00:00:00+03:00"),
        row(3, "2026-11-06T11:00:00+03:00"),
    ]
    assert [client.client_id for client in select_recent_clients(objects, 1457, 2)] == [2, 3]


def test_different_utc_offsets_are_compared_as_instants() -> None:
    objects = [
        row(1, "2026-11-06T12:00:00+04:00"),  # 08:00 UTC
        row(2, "2026-11-06T11:30:00+03:00"),  # 08:30 UTC
    ]
    assert [client.client_id for client in select_recent_clients(objects, 1457, 2)] == [2, 1]


def test_other_partners_are_filtered() -> None:
    objects = [row(1, "2026-11-06T12:00:00+03:00", 999), row(2, "2026-11-06T11:00:00+03:00")]
    assert [client.client_id for client in select_recent_clients(objects, 1457, 4)] == [2]


@pytest.mark.parametrize("created", ["2026-11-06T12:00:00", "not-a-date", None])
def test_created_requires_valid_timezone(created: object) -> None:
    with pytest.raises(ApiSchemaError):
        select_recent_clients([row(1, created)], 1457, 4)  # type: ignore[arg-type]
