from pathlib import Path

from app.browser_auth import (
    AuthCapture,
    attempt_login,
    is_getclients_url,
    is_mfa_url,
    is_signin_url,
    read_systemd_credential,
    select_work_page,
    trigger_getclients,
)


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


def test_browser_url_classification() -> None:
    assert is_getclients_url("https://example.test/api/en/Client/GetClients")
    assert not is_getclients_url("https://example.test/api/en/Client/GetClientBonuses")
    assert is_signin_url("https://www.accounts-bc.com/signin?returnUrl=x")
    assert is_mfa_url("https://www.accounts-bc.com/authentication")


def test_work_page_prefers_backoffice_over_unrelated_newer_tabs() -> None:
    pages = [
        FakePage("https://www.accounts-bc.com/signin?returnUrl=x"),
        FakePage("https://backoffice.betconstruct.com/#/customers"),
        FakePage("https://accounts-bc.com/"),
    ]
    assert select_work_page(pages) is pages[1]


def test_systemd_credential_is_read_without_trailing_newline(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "backoffice_username").write_text("operator@example.test\n", encoding="utf-8")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
    assert read_systemd_credential("backoffice_username") == "operator@example.test"


class FakeLocator:
    def __init__(self, visible: bool = True) -> None:
        self.first = self
        self.filled: list[str] = []
        self.clicked = 0
        self.visible = visible

    def wait_for(self, **kwargs) -> None:
        return None

    def fill(self, value: str) -> None:
        self.filled.append(value)

    def click(self, **kwargs) -> None:
        self.clicked += 1

    def is_visible(self) -> bool:
        return self.visible

    def all(self) -> list["FakeLocator"]:
        return [self]


class FakeRequest:
    url = "https://backofficewebadmin.betconstruct.com/api/en/Client/GetClients"


class FakeExpectation:
    def __init__(self, predicate) -> None:
        self.predicate = predicate

    def __enter__(self):
        assert self.predicate(FakeRequest())
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeKeyboard:
    def __init__(self) -> None:
        self.keys: list[str] = []

    def press(self, key: str) -> None:
        self.keys.append(key)


class FakePage:
    def __init__(self, url: str) -> None:
        self.url = url
        self.email = FakeLocator()
        self.password = FakeLocator()
        self.button = FakeLocator()
        self.close_button = FakeLocator()
        self.keyboard = FakeKeyboard()
        self.frames = [self]
        self.goto_urls: list[str] = []

    def locator(self, selector: str) -> FakeLocator:
        if selector == "#close-btn":
            return self.close_button
        return self.password if "password" in selector else self.email

    def get_by_placeholder(self, placeholder) -> FakeLocator:
        return self.password if "password" in placeholder.pattern else self.email

    def get_by_role(self, role: str, name) -> FakeLocator:
        if "close" in name.pattern:
            return self.close_button
        return self.button

    def get_by_text(self, text, exact: bool = False) -> FakeLocator:
        return self.close_button

    def wait_for_timeout(self, milliseconds: int) -> None:
        if milliseconds == 1000:
            self.url = "https://backoffice.betconstruct.com/#/customers"

    def goto(self, url: str, **kwargs) -> None:
        self.goto_urls.append(url)
        self.url = url

    def expect_request(self, predicate, **kwargs) -> FakeExpectation:
        return FakeExpectation(predicate)


def test_attempt_login_fills_credentials_without_logging_or_storing_them() -> None:
    page = FakePage("https://www.accounts-bc.com/signin?returnUrl=x")
    assert attempt_login(page, "operator@example.test", "secret") == "authenticated"
    assert page.email.filled == ["operator@example.test"]
    assert page.password.filled == ["secret"]
    assert page.button.clicked == 1


def test_trigger_getclients_navigates_to_customers_and_clicks_apply() -> None:
    page = FakePage("https://backoffice.betconstruct.com/")
    trigger_getclients(page)
    assert page.goto_urls == ["https://backoffice.betconstruct.com/#/customers"]
    assert page.keyboard.keys == ["Escape"]
    assert page.close_button.clicked == 1
    assert page.button.clicked == 1
