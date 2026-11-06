from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

from .errors import ConfigurationError


def _integer(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} tam sayı olmalıdır") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} en az {minimum} olmalıdır")
    return value


def _id_set(name: str) -> frozenset[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return frozenset()
    try:
        return frozenset(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise ConfigurationError(f"{name} virgülle ayrılmış sayısal ID'ler içermelidir") from exc


@dataclass(frozen=True)
class Settings:
    backoffice_base_url: str
    backoffice_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    partner_id: int
    interval_minutes: int
    recent_client_count: int
    no_bonus_category_ids: frozenset[int]
    bonus_expected_category_ids: frozenset[int]
    report_timezone: ZoneInfo
    http_timeout_seconds: int
    log_level: str
    get_clients_max_rows: int
    http_retry_count: int

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "Settings":
        load_dotenv(dotenv_path=env_file, override=False)
        timezone_name = os.getenv("REPORT_TIMEZONE", "Europe/Istanbul").strip()
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ConfigurationError("REPORT_TIMEZONE geçerli bir IANA saat dilimi olmalıdır") from exc

        base_url = os.getenv(
            "BACKOFFICE_BASE_URL", "https://backofficewebadmin.betconstruct.com/api/en/"
        ).strip()
        if not base_url.endswith("/"):
            base_url += "/"

        return cls(
            backoffice_base_url=base_url,
            backoffice_token=os.getenv("BACKOFFICE_TOKEN", "").strip(),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            partner_id=_integer("PARTNER_ID", 1457),
            interval_minutes=_integer("CHECK_INTERVAL_MINUTES", 20),
            recent_client_count=_integer("RECENT_CLIENT_COUNT", 4),
            no_bonus_category_ids=_id_set("NO_BONUS_CATEGORY_IDS"),
            bonus_expected_category_ids=_id_set("BONUS_EXPECTED_CATEGORY_IDS"),
            report_timezone=timezone,
            http_timeout_seconds=_integer("HTTP_TIMEOUT_SECONDS", 20),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            get_clients_max_rows=_integer("GET_CLIENTS_MAX_ROWS", 1000),
            http_retry_count=_integer("HTTP_RETRY_COUNT", 3),
        )

    def validate_runtime_secrets(self) -> None:
        missing = [
            name
            for name, value in (
                ("BACKOFFICE_TOKEN", self.backoffice_token),
                ("TELEGRAM_BOT_TOKEN", self.telegram_bot_token),
                ("TELEGRAM_CHAT_ID", self.telegram_chat_id),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError("Eksik zorunlu ortam değişkenleri: " + ", ".join(missing))
