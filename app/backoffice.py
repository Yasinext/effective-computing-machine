from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .errors import ApiError, ApiSchemaError, UnsafeSelectionError

LOGGER = logging.getLogger(__name__)


class BackofficeClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout_seconds: int = 20,
        retry_count: int = 3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.retry_count = retry_count
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "authentication": token,
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BackofficeClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.retry_count):
            try:
                response = self._client.post(endpoint, json=payload)
                if response.status_code in (401, 403):
                    raise ApiError(f"yetkilendirme reddedildi (HTTP {response.status_code})")
                response.raise_for_status()
                try:
                    body = response.json()
                except ValueError as exc:
                    raise ApiSchemaError("API geçersiz JSON döndürdü") from exc
                if not isinstance(body, dict) or not isinstance(body.get("HasError"), bool):
                    raise ApiSchemaError("API yanıt zarfı beklenen biçimde değil")
                if body["HasError"]:
                    raise ApiError("API HasError=true döndürdü")
                if "Data" not in body:
                    raise ApiSchemaError("API yanıtında Data eksik")
                return body["Data"]
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                retryable = status is None or status == 429 or status >= 500
                LOGGER.warning(
                    "API isteği başarısız operation=%s attempt=%s error=%s status=%s",
                    endpoint,
                    attempt + 1,
                    type(exc).__name__,
                    status,
                )
                if not retryable or attempt + 1 >= self.retry_count:
                    break
                time.sleep(0.25 * (2**attempt))
            except ApiError:
                raise
        raise ApiError(f"API isteği tamamlanamadı: {type(last_error).__name__}") from last_error

    def get_clients(self, max_rows: int) -> list[dict[str, Any]]:
        # These exact candidate parameter names come from the supplied specification.
        # We do not infer that OrderedItem=1 is Created ordering; Python sorts later.
        data = self._post(
            "Client/GetClients",
            {"SkeepRows": 0, "MaxRows": max_rows, "IsOrderedDesc": True, "OrderedItem": 1},
        )
        if not isinstance(data, dict):
            raise ApiSchemaError("GetClients Data nesne değil")
        count = data.get("Count")
        objects = data.get("Objects")
        if not isinstance(count, int) or count < 0:
            raise ApiSchemaError("GetClients Data.Count geçersiz")
        if not isinstance(objects, list) or not all(isinstance(item, dict) for item in objects):
            raise ApiSchemaError("GetClients Data.Objects geçersiz")
        if count > len(objects):
            raise UnsafeSelectionError(
                "GetClients yanıtı tüm sonuçları kapsamıyor; sayfalama/sıralama doğrulanmadan en yeni üyeler seçilemez"
            )
        return objects

    def get_client_bonuses(self, client_id: int) -> list[dict[str, Any]]:
        data = self._post(
            "Client/GetClientBonuses",
            {
                "StartDateLocal": None,
                "EndDateLocal": None,
                "BonusType": None,
                "AcceptanceType": None,
                "ClientBonusId": "",
                "PartnerBonusId": "",
                "PartnerExternalBonusId": "",
                "ClientId": client_id,
            },
        )
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ApiSchemaError("GetClientBonuses Data dizi değil")
        return data
