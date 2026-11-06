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


def update(username: str, text: str, *, chat_type: str = "private", message_id: int = 1) -> dict:
    return {
        "update_id": message_id,
        "message": {
            "message_id": message_id,
            "text": text,
            "chat": {"id": 100, "type": chat_type},
            "from": {"id": 200, "username": username},
        },
    }


def control(telegram: FakeTelegram, installed: list[str]) -> TokenControl:
    return TokenControl(
        telegram,
        frozenset({"authorized_user"}),
        lambda token: None,
        installed.append,
        Event(),
    )


def test_unauthorized_username_is_silently_ignored() -> None:
    telegram = FakeTelegram()
    installed: list[str] = []
    instance = control(telegram, installed)
    instance.handle_update(update("intruder", "/token"))
    instance.handle_update(update("intruder", "a" * 64, message_id=2))
    assert telegram.sent == []
    assert telegram.deleted == []
    assert installed == []


def test_group_command_is_silently_ignored_even_for_authorized_user() -> None:
    telegram = FakeTelegram()
    installed: list[str] = []
    instance = control(telegram, installed)
    instance.handle_update(update("authorized_user", "/token", chat_type="group"))
    assert telegram.sent == []
    assert telegram.deleted == []


def test_authorized_private_user_can_replace_token_case_insensitively() -> None:
    telegram = FakeTelegram()
    installed: list[str] = []
    instance = control(telegram, installed)
    instance.handle_update(update("Authorized_User", "/token"))
    candidate = "a" * 64
    instance.handle_update(update("Authorized_User", candidate, message_id=2))
    assert installed == [candidate]
    assert telegram.deleted == [(100, 1), (100, 2)]
    assert telegram.sent[-1] == (100, "Backoffice token doğrulandı ve güncellendi.")
