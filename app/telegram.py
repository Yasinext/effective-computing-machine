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

    def _request(self, method: str, payload: dict) -> dict:
        try:
            response = self._client.post(method, json=payload)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError(f"Telegram isteği tamamlanamadı: {type(exc).__name__}") from exc
        if not isinstance(data, dict) or data.get("ok") is not True:
            raise ApiError(f"Telegram {method} başarısız")
        return data

    def send_to(self, chat_id: str | int, message: str) -> None:
        if len(message) > 4096:
            raise ApiError("Telegram mesajı 4096 karakter sınırını aşıyor")
        self._request(
            "sendMessage",
            {"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        )

    def send(self, message: str) -> None:
        self.send_to(self.chat_id, message)

    def get_updates(self, offset: int | None, timeout: int = 10) -> list[dict]:
        payload: dict = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        data = self._request("getUpdates", payload)
        result = data.get("result")
        if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
            raise ApiError("Telegram getUpdates sonucu geçersiz")
        return result

    def delete_message(self, chat_id: str | int, message_id: int) -> None:
        self._request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
