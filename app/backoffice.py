from __future__ import annotations

import logging
import time
from datetime import datetime
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

    def update_token(self, token: str) -> None:
        self._client.headers["authentication"] = token

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

    @staticmethod
    def _validate_clients_data(data: Any) -> tuple[int, list[dict[str, Any]]]:
        if not isinstance(data, dict):
            raise ApiSchemaError("GetClients Data nesne değil")
        count = data.get("Count")
        objects = data.get("Objects")
        if not isinstance(count, int) or count < 0:
            raise ApiSchemaError("GetClients Data.Count geçersiz")
        if not isinstance(objects, list) or not all(isinstance(item, dict) for item in objects):
            raise ApiSchemaError("GetClients Data.Objects geçersiz")
        return count, objects

    @staticmethod
    def _created_instant(item: dict[str, Any]) -> datetime:
        value = item.get("Created")
        if not isinstance(value, str):
            raise ApiSchemaError("GetClients üye Created alanı geçersiz")
        try:
            created = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ApiSchemaError("GetClients üye Created alanı ISO 8601 değil") from exc
        if created.tzinfo is None or created.utcoffset() is None:
            raise ApiSchemaError("GetClients üye Created alanında saat dilimi yok")
        return created

    def get_clients(
        self,
        max_rows: int,
        *,
        partner_id: int | None = None,
        required_count: int | None = None,
        created_order_verified: bool = False,
        page_size: int = 20,
        max_pages: int = 50,
    ) -> list[dict[str, Any]]:
        # These exact candidate parameter names come from the supplied specification.
        # We do not infer that OrderedItem=1 is Created ordering; Python sorts later.
        if not created_order_verified:
            data = self._post(
                "Client/GetClients",
                {"SkeepRows": 0, "MaxRows": max_rows, "IsOrderedDesc": True, "OrderedItem": 1},
            )
            count, objects = self._validate_clients_data(data)
            if count != len(objects):
                raise UnsafeSelectionError(
                    "GetClients yanıtı tüm sonuçları kapsamıyor; sayfalama/sıralama doğrulanmadan en yeni üyeler seçilemez"
                )
            return objects

        if partner_id is None or required_count is None:
            raise UnsafeSelectionError("doğrulanmış sıralama modu partner ve hedef üye sayısı gerektirir")

        collected: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        total_count: int | None = None
        previous_created: datetime | None = None
        offset = 0
        partner_matches = 0
        for _ in range(max_pages):
            data = self._post(
                "Client/GetClients",
                {
                    "SkeepRows": offset,
                    "MaxRows": page_size,
                    "IsOrderedDesc": True,
                    "OrderedItem": 1,
                },
            )
            page_count, objects = self._validate_clients_data(data)
            if total_count is None:
                total_count = page_count
            elif page_count != total_count:
                raise UnsafeSelectionError("GetClients Data.Count sayfalar arasında değişti")
            if not objects:
                if offset < page_count:
                    raise UnsafeSelectionError("GetClients beklenmedik biçimde boş sayfa döndürdü")
                return collected

            for item in objects:
                raw_id = item.get("Id")
                if isinstance(raw_id, bool):
                    raise ApiSchemaError("GetClients üye Id alanı geçersiz")
                try:
                    client_id = int(raw_id)
                except (TypeError, ValueError) as exc:
                    raise ApiSchemaError("GetClients üye Id alanı geçersiz") from exc
                if client_id in seen_ids:
                    raise UnsafeSelectionError("GetClients sayfalarında tekrarlı üye bulundu")
                seen_ids.add(client_id)

                created = self._created_instant(item)
                if previous_created is not None and created > previous_created:
                    raise UnsafeSelectionError("GetClients Created sırası azalan değil")
                previous_created = created
                collected.append(item)
                try:
                    if int(item.get("PartnerId")) == partner_id:
                        partner_matches += 1
                except (TypeError, ValueError):
                    raise ApiSchemaError("GetClients üye PartnerId alanı geçersiz")

            if partner_matches >= required_count or len(collected) >= page_count:
                return collected
            offset += len(objects)

        if partner_matches < required_count:
            raise UnsafeSelectionError(
                "GetClients sayfa sınırı içinde yeterli partner üyesi bulunamadı"
            )
        return collected

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

    def probe_authentication(self) -> None:
        data = self._post(
            "Client/GetClients",
            {"SkeepRows": 0, "MaxRows": 1, "IsOrderedDesc": True, "OrderedItem": 1},
        )
        self._validate_clients_data(data)
