from __future__ import annotations

import json

import httpx
import pytest

from app.backoffice import BackofficeClient
from app.errors import ApiError, ApiSchemaError, UnsafeSelectionError


def client(handler) -> BackofficeClient:
    return BackofficeClient(
        "https://example.test/api/en/", "secret", retry_count=1, transport=httpx.MockTransport(handler)
    )


@pytest.mark.parametrize("status", [401, 403, 500])
def test_http_errors_are_api_errors(status: int) -> None:
    api = client(lambda request: httpx.Response(status, json={"error": "redacted"}))
    with pytest.raises(ApiError):
        api.get_client_bonuses(1)
    api.close()


def test_timeout_is_api_error() -> None:
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    api = client(handler)
    with pytest.raises(ApiError):
        api.get_client_bonuses(1)
    api.close()


def test_bad_json_is_schema_error() -> None:
    api = client(lambda request: httpx.Response(200, content=b"not-json"))
    with pytest.raises(ApiSchemaError):
        api.get_client_bonuses(1)
    api.close()


def test_has_error_is_api_error() -> None:
    api = client(lambda request: httpx.Response(200, json={"HasError": True, "Data": []}))
    with pytest.raises(ApiError):
        api.get_client_bonuses(1)
    api.close()


@pytest.mark.parametrize("data", [{}, {"Count": 1}, {"Count": 1, "Objects": {}}, {"Count": "1", "Objects": []}])
def test_invalid_objects_schema_is_not_silently_empty(data: dict) -> None:
    api = client(lambda request: httpx.Response(200, json={"HasError": False, "Data": data}))
    with pytest.raises(ApiSchemaError):
        api.get_clients(20)
    api.close()


def test_incomplete_first_page_is_rejected() -> None:
    api = client(
        lambda request: httpx.Response(
            200, json={"HasError": False, "Data": {"Count": 100, "Objects": [{"Id": 1}]}}
        )
    )
    with pytest.raises(UnsafeSelectionError):
        api.get_clients(20)
    api.close()


def test_request_uses_documented_candidate_spelling_and_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["SkeepRows"] == 0
        assert "SkipRows" not in payload
        assert request.headers["authentication"] == "secret"
        assert not request.headers["authentication"].startswith("Bearer ")
        return httpx.Response(200, json={"HasError": False, "Data": {"Count": 0, "Objects": []}})

    api = client(handler)
    assert api.get_clients(20) == []
    api.close()
