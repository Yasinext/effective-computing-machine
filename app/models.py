from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CheckStatus(StrEnum):
    BONUS_BULUNDU = "BONUS_BULUNDU"
    BONUS_ISTEMIYOR = "BONUS_ISTEMIYOR"
    BONUS_BULUNAMADI = "BONUS_BULUNAMADI"
    INCELEME_GEREKLI = "INCELEME_GEREKLI"
    API_HATASI = "API_HATASI"


@dataclass(frozen=True)
class Client:
    client_id: int
    login: str
    partner_id: int
    created: datetime
    category_id: int | None


@dataclass(frozen=True)
class CheckResult:
    client: Client
    status: CheckStatus
    bonus_name: str | None = None
    detail: str | None = None
