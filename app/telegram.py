from __future__ import annotations

import httpx

from .errors import ApiError


class TelegramClient:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout_seconds: int = 20,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.chat_id = chat_id
        self._client = httpx.Client(
            base_url=f"https://api.telegram.org/bot{bot_token}/",
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def send(self, message: str) -> None:
        if len(message) > 4096:
            raise ApiError("Telegram mesajı 4096 karakter sınırını aşıyor")
        try:
            response = self._client.post(
                "sendMessage",
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"},
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError(f"Telegram isteği tamamlanamadı: {type(exc).__name__}") from exc
        if not isinstance(data, dict) or data.get("ok") is not True:
            raise ApiError("Telegram sendMessage başarısız")
