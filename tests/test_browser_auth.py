from app.browser_auth import AuthCapture


def test_capture_accepts_only_new_valid_getclients_token() -> None:
    validated: list[str] = []
    installed: list[str] = []
    capture = AuthCapture(validated.append, installed.append, "old-token")
    candidate = "a" * 64
    assert capture.observe(
        "https://example.test/api/en/Client/GetClients",
        {"authentication": candidate},
    )
    assert validated == [candidate]
    assert installed == [candidate]
    assert not capture.observe(
        "https://example.test/api/en/Client/GetClients",
        {"authentication": candidate},
    )


def test_capture_ignores_other_endpoints_and_missing_header() -> None:
    installed: list[str] = []
    capture = AuthCapture(lambda token: None, installed.append)
    assert not capture.observe("https://example.test/Client/GetClientBonuses", {})
    assert not capture.observe("https://example.test/Client/GetClients", {})
    assert installed == []
