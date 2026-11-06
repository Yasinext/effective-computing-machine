from __future__ import annotations

from datetime import datetime
from typing import Any

from .errors import ApiSchemaError
from .models import Client


def _required_int(item: dict[str, Any], key: str) -> int:
    value = item.get(key)
    if isinstance(value, bool):
        raise ApiSchemaError(f"üye alanı geçersiz: {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ApiSchemaError(f"üye alanı geçersiz: {key}") from exc


def _parse_created(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ApiSchemaError("üye Created alanı geçersiz")
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiSchemaError("üye Created alanı ISO 8601 değil") from exc
    if created.tzinfo is None or created.utcoffset() is None:
        raise ApiSchemaError("üye Created alanında saat dilimi yok")
    return created


def select_recent_clients(
    objects: list[dict[str, Any]], partner_id: int, limit: int
) -> list[Client]:
    clients: list[Client] = []
    for item in objects:
        item_partner_id = _required_int(item, "PartnerId")
        if item_partner_id != partner_id:
            continue
        login = item.get("Login")
        if not isinstance(login, str) or not login:
            raise ApiSchemaError("üye Login alanı geçersiz")
        raw_category = item.get("PartnerClientCategoryId")
        category_id = None if raw_category is None else _required_int(item, "PartnerClientCategoryId")
        clients.append(
            Client(
                client_id=_required_int(item, "Id"),
                login=login,
                partner_id=item_partner_id,
                created=_parse_created(item.get("Created")),
                category_id=category_id,
            )
        )
    return sorted(clients, key=lambda client: client.created, reverse=True)[:limit]
