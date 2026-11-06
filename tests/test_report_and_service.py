from __future__ import annotations

from datetime import datetime

from app.models import CheckResult, CheckStatus, Client
from app.report import build_report
from app.service import BonusCheckService


def make_client(client_id: int, login: str = "user") -> Client:
    return Client(client_id, login, 1457, datetime.fromisoformat("2026-11-06T10:00:00+03:00"), 908)


def test_report_escapes_login_and_contains_no_sensitive_fields() -> None:
    result = CheckResult(make_client(1, "<b>attacker</b>"), CheckStatus.BONUS_BULUNDU, "Kayıt Özel 500 FreeBet")
    message = build_report(
        [result],
        datetime.fromisoformat("2026-11-06T12:20:00+03:00"),
        datetime.fromisoformat("2026-11-06T12:40:00+03:00"),
    )
    assert "&lt;b&gt;attacker&lt;/b&gt;" in message
    assert "<b>attacker</b>" not in message
    for forbidden in ("FirstName", "LastName", "Email", "Phone", "RegistrationIp", "Balance"):
        assert forbidden not in message
    emojis = {character for character in message if ord(character) > 0xFFFF}
    assert emojis <= {"✅", "❌"}


class FakeTelegram:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, message: str) -> None:
        self.messages.append(message)


class FakeBackoffice:
    def __init__(self) -> None:
        self.failed_client = 2

    def get_clients(self, max_rows: int) -> list[dict]:
        return [
            {"Id": i, "Login": f"u{i}", "PartnerId": 1457, "Created": f"2026-11-06T1{i}:00:00+03:00", "PartnerClientCategoryId": 908}
            for i in range(1, 5)
        ]

    def get_client_bonuses(self, client_id: int) -> list[dict]:
        from app.errors import ApiError

        if client_id == self.failed_client:
            raise ApiError("fail")
        return [{"PartnerBonusId": 625042, "BonusType": 5}]


def test_one_member_error_does_not_stop_others_and_one_message_per_cycle(settings) -> None:
    telegram = FakeTelegram()
    service = BonusCheckService(settings, FakeBackoffice(), telegram)
    now = datetime.fromisoformat("2026-11-06T12:20:00+03:00")
    first = service.run_cycle(now)
    second = service.run_cycle(now)
    assert "Kontrol edilen: 4 üye" in first
    assert "API hatası: 1" in first
    assert "Bonus kaydı bulunan: 3" in first
    assert first == second
    assert len(telegram.messages) == 2
