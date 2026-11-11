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
        self.direct_messages: list[tuple[int, str]] = []

    def send(self, message: str) -> None:
        self.messages.append(message)

    def send_to(self, chat_id: int, message: str) -> None:
        self.direct_messages.append((chat_id, message))


class FakeBackoffice:
    def __init__(self) -> None:
        self.failed_client = 2
        self.updated_tokens: list[str] = []

    def update_token(self, token: str) -> None:
        self.updated_tokens.append(token)

    def get_clients(self, max_rows: int, **kwargs: object) -> list[dict]:
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
    assert first.count("API kontrolü tamamlanamadı") == 1
    assert first.count("Pragmatic Kayıt FreeSpin 500") == 1
    assert "Genel sonuç" not in first
    assert first == second
    assert len(telegram.messages) == 2


def test_cycle_reloads_changed_token_file(settings, tmp_path) -> None:
    from dataclasses import replace

    token_file = tmp_path / "backoffice.token"
    token_file.write_text("new-token\n", encoding="utf-8")
    configured = replace(settings, backoffice_token_file=token_file)
    telegram = FakeTelegram()
    backoffice = FakeBackoffice()
    service = BonusCheckService(configured, backoffice, telegram)
    service.run_cycle(datetime.fromisoformat("2026-11-06T12:20:00+03:00"))
    assert backoffice.updated_tokens == ["new-token"]


def test_client_list_api_failure_is_sent_only_to_admin_private_chat(settings) -> None:
    from app.errors import ApiError

    class FailedBackoffice(FakeBackoffice):
        def get_clients(self, max_rows: int, **kwargs: object) -> list[dict]:
            raise ApiError("unavailable")

    telegram = FakeTelegram()
    service = BonusCheckService(settings, FailedBackoffice(), telegram)
    message = service.run_cycle(datetime.fromisoformat("2026-11-11T10:30:00+03:00"))

    assert "API kontrolü tamamlanamadı" in message
    assert telegram.messages == []
    assert telegram.direct_messages == [(7265030719, message)]


def test_requested_compact_report_wording() -> None:
    results = [CheckResult(make_client(1), CheckStatus.BONUS_BULUNAMADI)]
    message = build_report(
        results,
        datetime.fromisoformat("2026-11-06T12:20:00+03:00"),
        datetime.fromisoformat("2026-11-06T12:40:00+03:00"),
    )
    assert message.startswith("KONTROL RAPORU\n")
    assert "EXTRABET" not in message
    assert "❌ FS Yansıması bulunamadı." in message
    assert "Bonus kaydı bulunamadı" not in message
    assert "Genel sonuç" not in message


def test_bonus_results_are_grouped_by_name_and_no_bonus_preference_is_hidden() -> None:
    results = [
        CheckResult(make_client(1, "one"), CheckStatus.BONUS_ISTEMIYOR),
        CheckResult(make_client(2, "two"), CheckStatus.BONUS_ISTEMIYOR),
        CheckResult(
            make_client(3, "three"),
            CheckStatus.BONUS_BULUNDU,
            "Pragmatic Kayıt FreeSpin 500",
        ),
        CheckResult(
            make_client(4, "four"),
            CheckStatus.BONUS_BULUNDU,
            "Pragmatic Kayıt FreeSpin 500",
        ),
        CheckResult(
            make_client(5, "five"),
            CheckStatus.BONUS_BULUNDU,
            "Kayıt Özel 500 FreeBet",
        ),
    ]
    message = build_report(
        results,
        datetime.fromisoformat("2026-11-06T12:20:00+03:00"),
        datetime.fromisoformat("2026-11-06T12:40:00+03:00"),
    )
    assert "Bonus istemeyen" not in message
    assert "Deneme bonusu istemiyorum" not in message
    assert "one (1)" not in message
    assert "two (2)" not in message
    assert message.count("✅ Pragmatic Kayıt FreeSpin 500") == 1
    assert "- three (3)" in message
    assert "- four (4)" in message
    assert message.count("✅ Kayıt Özel 500 FreeBet") == 1
    assert "- five (5)" in message
    assert "Bonus tercihi:" not in message
    assert "Sonuç:" not in message
