from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .errors import ApiError
from .models import CheckResult, CheckStatus, Client

LOGGER = logging.getLogger(__name__)

TARGET_BONUSES = {
    625042: (5, "Pragmatic Kayıt FreeSpin 500"),
    625095: (6, "Kayıt Özel 500 FreeBet"),
}


def _numeric_bonus_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    return numeric


def check_client(
    client: Client,
    fetch_bonuses: Callable[[int], list[dict[str, Any]]],
    no_bonus_category_ids: frozenset[int],
    bonus_expected_category_ids: frozenset[int],
) -> CheckResult:
    if client.category_id in no_bonus_category_ids:
        return CheckResult(client, CheckStatus.BONUS_ISTEMIYOR)

    try:
        bonuses = fetch_bonuses(client.client_id)
    except ApiError as exc:
        LOGGER.error(
            "Bonus kontrolü başarısız client_id=%s error=%s",
            client.client_id,
            type(exc).__name__,
        )
        return CheckResult(client, CheckStatus.API_HATASI, detail=type(exc).__name__)

    matches: list[str] = []
    inconsistent_target = False
    for row in bonuses:
        bonus_id = _numeric_bonus_id(row.get("PartnerBonusId"))
        if bonus_id not in TARGET_BONUSES:
            continue
        expected_type, name = TARGET_BONUSES[bonus_id]
        if _numeric_bonus_id(row.get("BonusType")) != expected_type:
            inconsistent_target = True
        else:
            matches.append(name)
    if inconsistent_target:
        LOGGER.warning("Hedef bonus kimliği beklenmedik tipte client_id=%s", client.client_id)
        return CheckResult(client, CheckStatus.INCELEME_GEREKLI, detail="target_bonus_type_mismatch")
    if len(matches) == 1:
        return CheckResult(client, CheckStatus.BONUS_BULUNDU, bonus_name=matches[0])
    if len(matches) > 1:
        LOGGER.warning("Birden fazla hedef bonus bulundu client_id=%s count=%s", client.client_id, len(matches))
        return CheckResult(client, CheckStatus.INCELEME_GEREKLI, detail="multiple_target_bonuses")
    if client.category_id in bonus_expected_category_ids:
        return CheckResult(client, CheckStatus.BONUS_BULUNAMADI)
    return CheckResult(client, CheckStatus.INCELEME_GEREKLI, detail="unknown_category")
