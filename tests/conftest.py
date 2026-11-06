from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        backoffice_base_url="https://backoffice.example/api/en/",
        backoffice_token="test-token",
        telegram_bot_token="telegram-test-token",
        telegram_chat_id="-100123",
        partner_id=1457,
        interval_minutes=20,
        recent_client_count=4,
        no_bonus_category_ids=frozenset({909}),
        bonus_expected_category_ids=frozenset({908}),
        report_timezone=ZoneInfo("Europe/Istanbul"),
        http_timeout_seconds=1,
        log_level="INFO",
        get_clients_max_rows=1000,
        get_clients_page_size=20,
        get_clients_max_pages=50,
        get_clients_created_order_verified=False,
        http_retry_count=1,
    )
