from __future__ import annotations

import logging
import os
import re
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event

from .errors import ApiError

LOGGER = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"^[^\s]{32,256}$")


def store_token(path: Path, token: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".token-", delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(token + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


class TokenControl:
    def __init__(
        self,
        telegram,
        allowed_usernames: frozenset[str],
        validator: Callable[[str], None],
        installer: Callable[[str], None],
        stop_event: Event,
        pending_seconds: int = 60,
    ) -> None:
        self.telegram = telegram
        self.allowed_usernames = allowed_usernames
        self.validator = validator
        self.installer = installer
        self.stop_event = stop_event
        self.pending_seconds = pending_seconds
        self.pending: dict[int, float] = {}

    def _delete_quietly(self, chat_id: int, message_id: int) -> None:
        try:
            self.telegram.delete_message(chat_id, message_id)
        except ApiError:
            LOGGER.warning("Telegram özel mesajı silinemedi error=ApiError")

    def handle_update(self, update: dict) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat")
        sender = message.get("from")
        if not isinstance(chat, dict) or chat.get("type") != "private" or not isinstance(sender, dict):
            return
        username = sender.get("username")
        if not isinstance(username, str) or username.lower() not in self.allowed_usernames:
            return
        user_id = sender.get("id")
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        text = message.get("text")
        if not all(isinstance(value, int) for value in (user_id, chat_id, message_id)):
            return
        if not isinstance(text, str):
            return

        command = text.strip().split(maxsplit=1)[0].split("@", 1)[0].lower()
        if command == "/token":
            self._delete_quietly(chat_id, message_id)
            self.pending[user_id] = time.monotonic() + self.pending_seconds
            self.telegram.send_to(
                chat_id,
                "Yeni Backoffice token değerini 60 saniye içinde tek mesaj olarak gönderin.",
            )
            return

        deadline = self.pending.pop(user_id, None)
        if deadline is None or time.monotonic() > deadline:
            return
        self._delete_quietly(chat_id, message_id)
        candidate = text.strip()
        if not TOKEN_PATTERN.fullmatch(candidate):
            self.telegram.send_to(chat_id, "Token biçimi geçersiz; değişiklik yapılmadı.")
            return
        try:
            self.validator(candidate)
            self.installer(candidate)
        except ApiError:
            LOGGER.warning("Backoffice token doğrulaması başarısız error=ApiError")
            self.telegram.send_to(chat_id, "Token doğrulanamadı; mevcut token korunuyor.")
            return
        self.telegram.send_to(chat_id, "Backoffice token doğrulandı ve güncellendi.")

    def run(self) -> None:
        offset: int | None = None
        try:
            latest = self.telegram.get_updates(-1, timeout=0)
            if latest:
                offset = int(latest[-1]["update_id"]) + 1
        except (ApiError, KeyError, TypeError, ValueError):
            LOGGER.warning("Telegram komut kuyruğu başlatılamadı")

        while not self.stop_event.is_set():
            try:
                updates = self.telegram.get_updates(offset, timeout=10)
                for update in updates:
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        offset = update_id + 1
                    self.handle_update(update)
            except ApiError:
                LOGGER.warning("Telegram komut kontrolü başarısız error=ApiError")
                self.stop_event.wait(5)
