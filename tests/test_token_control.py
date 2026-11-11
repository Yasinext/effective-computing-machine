from __future__ import annotations

from threading import Event

from app.token_control import TokenControl


class FakeTelegram:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.deleted: list[tuple[int, int]] = []

    def send_to(self, chat_id: int, message: str) -> None:
        self.sent.append((chat_id, message))

    def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))


def update(user_id: int, text: str, *, chat_type: str = "private", message_id: int = 1) -> dict:
    return {
        "update_id": message_id,
        "message": {
            "message_id": message_id,
            "text": text,
            "chat": {"id": 100, "type": chat_type},
            "from": {"id": user_id, "username": "changeable_tag"},
        },
    }


def control(telegram: FakeTelegram, installed: list[str]) -> TokenControl:
    return TokenControl(
        telegram,
        7265030719,
        lambda token: None,
        installed.append,
        Event(),
    )


def test_unauthorized_user_id_is_silently_ignored() -> None:
    telegram = FakeTelegram()
    installed: list[str] = []
    instance = control(telegram, installed)
    instance.handle_update(update(200, "/token"))
    instance.handle_update(update(200, "a" * 64, message_id=2))
    assert telegram.sent == []
    assert telegram.deleted == []
    assert installed == []


def test_group_command_is_silently_ignored_even_for_authorized_user() -> None:
    telegram = FakeTelegram()
    installed: list[str] = []
    instance = control(telegram, installed)
    instance.handle_update(update(7265030719, "/token", chat_type="group"))
    assert telegram.sent == []
    assert telegram.deleted == []


def test_authorized_private_user_id_can_replace_token_regardless_of_tag() -> None:
    telegram = FakeTelegram()
    installed: list[str] = []
    instance = control(telegram, installed)
    instance.handle_update(update(7265030719, "/token"))
    candidate = "a" * 64
    instance.handle_update(update(7265030719, candidate, message_id=2))
    assert installed == [candidate]
    assert telegram.deleted == [(100, 1), (100, 2)]
    assert telegram.sent[-1] == (100, "Backoffice token doğrulandı ve güncellendi.")


def test_install_failure_is_reported_without_crashing() -> None:
    telegram = FakeTelegram()

    def fail_install(token: str) -> None:
        raise OSError("read-only")

    instance = TokenControl(
        telegram,
        7265030719,
        lambda token: None,
        fail_install,
        Event(),
    )
    instance.handle_update(update(7265030719, "/token"))
    instance.handle_update(update(7265030719, "a" * 64, message_id=2))
    assert telegram.sent[-1] == (100, "Token güncellenemedi; mevcut token korunuyor.")
