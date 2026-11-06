from __future__ import annotations

import pytest

from app.bonus_checker import check_client
from app.errors import ApiError
from app.models import CheckStatus, Client


@pytest.fixture
def client() -> Client:
    from datetime import datetime

    return Client(10, "tester", 1457, datetime.fromisoformat("2026-11-06T10:00:00+03:00"), 908)


def test_freespin_alone_is_found(client: Client) -> None:
    result = check_client(client, lambda _: [{"PartnerBonusId": "625042", "BonusType": 5}], frozenset(), frozenset())
    assert result.status == CheckStatus.BONUS_BULUNDU
    assert result.bonus_name == "Pragmatic Kayıt FreeSpin 500"


def test_freebet_alone_is_found(client: Client) -> None:
    result = check_client(client, lambda _: [{"PartnerBonusId": 625095, "BonusType": "6"}], frozenset(), frozenset())
    assert result.status == CheckStatus.BONUS_BULUNDU
    assert result.bonus_name == "Kayıt Özel 500 FreeBet"


def test_no_target_with_verified_expected_category_is_missing(client: Client) -> None:
    result = check_client(client, lambda _: [], frozenset(), frozenset({908}))
    assert result.status == CheckStatus.BONUS_BULUNAMADI


def test_no_target_with_unknown_category_needs_review(client: Client) -> None:
    unknown = Client(client.client_id, client.login, client.partner_id, client.created, 777)
    result = check_client(unknown, lambda _: [], frozenset({909}), frozenset({908}))
    assert result.status == CheckStatus.INCELEME_GEREKLI


def test_verified_no_bonus_category_skips_api(client: Client) -> None:
    no_bonus = Client(client.client_id, client.login, client.partner_id, client.created, 909)
    called = False

    def fetch(_: int) -> list[dict]:
        nonlocal called
        called = True
        return []

    result = check_client(no_bonus, fetch, frozenset({909}), frozenset({908}))
    assert result.status == CheckStatus.BONUS_ISTEMIYOR
    assert called is False


def test_two_target_records_need_review(client: Client) -> None:
    result = check_client(
        client,
        lambda _: [
            {"PartnerBonusId": 625042, "BonusType": 5},
            {"PartnerBonusId": 625095, "BonusType": 6},
        ],
        frozenset(),
        frozenset({908}),
    )
    assert result.status == CheckStatus.INCELEME_GEREKLI


def test_duplicate_target_records_need_review(client: Client) -> None:
    bonus = {"PartnerBonusId": 625042, "BonusType": 5}
    result = check_client(client, lambda _: [bonus, bonus], frozenset(), frozenset({908}))
    assert result.status == CheckStatus.INCELEME_GEREKLI


def test_target_id_with_wrong_type_needs_review(client: Client) -> None:
    result = check_client(client, lambda _: [{"PartnerBonusId": 625042, "BonusType": 6}], frozenset(), frozenset({908}))
    assert result.status == CheckStatus.INCELEME_GEREKLI


def test_api_error_is_isolated_as_status(client: Client) -> None:
    def fail(_: int) -> list[dict]:
        raise ApiError("safe")

    assert check_client(client, fail, frozenset(), frozenset()).status == CheckStatus.API_HATASI
