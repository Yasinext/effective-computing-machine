from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from .bonus_checker import check_client
from .config import Settings
from .errors import ApiError
from .report import build_cycle_error_report, build_report
from .selection import select_recent_clients

LOGGER = logging.getLogger(__name__)


class BackofficeProtocol(Protocol):
    def get_clients(self, max_rows: int, **kwargs: object) -> list[dict]: ...
    def get_client_bonuses(self, client_id: int) -> list[dict]: ...


class TelegramProtocol(Protocol):
    def send(self, message: str) -> None: ...


class BonusCheckService:
    def __init__(self, settings: Settings, backoffice: BackofficeProtocol, telegram: TelegramProtocol) -> None:
        self.settings = settings
        self.backoffice = backoffice
        self.telegram = telegram
        self._loaded_token = settings.backoffice_token

    def _reload_token_file(self) -> None:
        token_file: Path | None = self.settings.backoffice_token_file
        if token_file is None or not token_file.is_file():
            return
        token = token_file.read_text(encoding="utf-8").strip()
        if token and token != self._loaded_token:
            update_token = getattr(self.backoffice, "update_token", None)
            if callable(update_token):
                update_token(token)
                self._loaded_token = token
                LOGGER.info("Backoffice token dosyadan yeniden yüklendi")

    def run_cycle(self, now: datetime | None = None) -> str:
        self._reload_token_file()
        checked_at = (now or datetime.now(self.settings.report_timezone)).astimezone(
            self.settings.report_timezone
        )
        next_run = checked_at + timedelta(minutes=self.settings.interval_minutes)
        try:
            objects = self.backoffice.get_clients(
                self.settings.get_clients_max_rows,
                partner_id=self.settings.partner_id,
                required_count=self.settings.recent_client_count,
                created_order_verified=self.settings.get_clients_created_order_verified,
                page_size=self.settings.get_clients_page_size,
                max_pages=self.settings.get_clients_max_pages,
            )
            clients = select_recent_clients(
                objects, self.settings.partner_id, self.settings.recent_client_count
            )
            results = [
                check_client(
                    client,
                    self.backoffice.get_client_bonuses,
                    self.settings.no_bonus_category_ids,
                    self.settings.bonus_expected_category_ids,
                )
                for client in clients
            ]
            message = build_report(results, checked_at, next_run)
        except ApiError as exc:
            LOGGER.error("Üye listesi kontrolü başarısız error=%s", type(exc).__name__)
            message = build_cycle_error_report(checked_at, next_run)
        self.telegram.send(message)
        return message
