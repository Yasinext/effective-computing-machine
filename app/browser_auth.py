from __future__ import annotations

import logging
import os
import re
import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from .backoffice import BackofficeClient
from .config import Settings
from .errors import ApiError, ConfigurationError
from .telegram import TelegramClient
from .token_control import TOKEN_PATTERN, store_token

LOGGER = logging.getLogger(__name__)
CUSTOMERS_URL = "https://backoffice.betconstruct.com/#/customers"
GET_CLIENTS_PATH = "/client/getclients"
APPLY_BUTTON = re.compile(r"^(apply|ara|search)$", re.IGNORECASE)
LOGIN_BUTTON = re.compile(r"^(sign in|giriş yap|login)$", re.IGNORECASE)
CLOSE_BUTTON = re.compile(r"close|kapat", re.IGNORECASE)
EMAIL_PLACEHOLDER = re.compile(r"^(email|e-mail|e-posta)$", re.IGNORECASE)
PASSWORD_PLACEHOLDER = re.compile(r"^(password|parola|şifre)$", re.IGNORECASE)


class AuthCapture:
    def __init__(
        self,
        validator: Callable[[str], None],
        installer: Callable[[str], None],
        initial_token: str = "",
    ) -> None:
        self.validator = validator
        self.installer = installer
        self.last_token = initial_token
        self.updated_at = 0.0

    def observe(self, url: str, headers: dict[str, str]) -> bool:
        path = urlparse(url).path.lower().rstrip("/")
        if not path.endswith("/client/getclients"):
            return False
        token = next(
            (value for key, value in headers.items() if key.lower() == "authentication"), ""
        ).strip()
        if not token or token == self.last_token or not TOKEN_PATTERN.fullmatch(token):
            return False
        try:
            self.validator(token)
            self.installer(token)
        except (ApiError, OSError) as exc:
            LOGGER.warning("Tarayıcı token yenilemesi başarısız error=%s", type(exc).__name__)
            return False
        self.last_token = token
        self.updated_at = time.monotonic()
        LOGGER.info("Tarayıcıdan yeni Backoffice token doğrulandı ve kaydedildi")
        return True


def is_getclients_url(url: str) -> bool:
    return urlparse(url).path.lower().rstrip("/").endswith(GET_CLIENTS_PATH)


def is_signin_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in {"accounts-bc.com", "www.accounts-bc.com"} and parsed.path.lower().startswith(
        "/signin"
    )


def is_mfa_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in {"accounts-bc.com", "www.accounts-bc.com"} and parsed.path.lower().startswith(
        "/authentication"
    )


def read_systemd_credential(name: str) -> str:
    directory = os.getenv("CREDENTIALS_DIRECTORY", "").strip()
    if not directory:
        return ""
    path = Path(directory) / name
    try:
        return path.read_text(encoding="utf-8").rstrip("\r\n")
    except OSError:
        return ""


def select_work_page(pages):
    for page in pages:
        if page.url.startswith("https://backoffice.betconstruct.com/"):
            return page
    for page in pages:
        if is_signin_url(page.url) or is_mfa_url(page.url):
            return page
    return pages[-1] if pages else None


def attempt_login(page, username: str, password: str) -> str:
    if not is_signin_url(page.url):
        return "not-needed"
    if not username or not password:
        return "credentials-missing"

    email = page.get_by_placeholder(EMAIL_PLACEHOLDER).first
    password_input = page.get_by_placeholder(PASSWORD_PLACEHOLDER).first
    email.wait_for(state="visible", timeout=30_000)
    password_input.wait_for(state="visible", timeout=30_000)
    email.fill(username)
    password_input.fill(password)
    page.get_by_role("button", name=LOGIN_BUTTON).first.click(timeout=30_000)

    for _ in range(90):
        page.wait_for_timeout(1000)
        if is_mfa_url(page.url):
            return "mfa-required"
        if page.url.startswith("https://backoffice.betconstruct.com/"):
            return "authenticated"
    return "login-timeout"


def trigger_getclients(page) -> None:
    if not page.url.startswith("https://backoffice.betconstruct.com/"):
        page.goto(CUSTOMERS_URL, wait_until="domcontentloaded", timeout=60_000)
    if not page.url.startswith(CUSTOMERS_URL):
        page.goto(CUSTOMERS_URL, wait_until="domcontentloaded", timeout=60_000)

    page.wait_for_timeout(3000)
    page.keyboard.press("Escape")
    modal_closed = False
    close_button = page.locator("#close-btn")
    if close_button.is_visible():
        close_button.click(timeout=30_000)
        close_button.wait_for(state="hidden", timeout=10_000)
        modal_closed = True
    for frame in page.frames:
        if modal_closed:
            break
        candidates = (
            frame.get_by_role("button", name=CLOSE_BUTTON),
            frame.get_by_text(CLOSE_BUTTON),
        )
        for candidate in candidates:
            for close_button in candidate.all():
                if not close_button.is_visible():
                    continue
                close_button.click(timeout=30_000)
                close_button.wait_for(state="hidden", timeout=10_000)
                modal_closed = True
                break
            if modal_closed:
                break
        if modal_closed:
            break

    apply_button = page.get_by_role("button", name=APPLY_BUTTON).first
    apply_button.wait_for(state="visible", timeout=30_000)
    with page.expect_request(lambda request: is_getclients_url(request.url), timeout=30_000):
        apply_button.click(timeout=30_000)


def _positive_minutes(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ConfigurationError(f"{name} tam sayı olmalıdır") from exc
    if value < 1:
        raise ConfigurationError(f"{name} en az 1 olmalıdır")
    return value


def main() -> int:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    settings = Settings.from_env()
    if settings.backoffice_token_file is None:
        raise ConfigurationError("BACKOFFICE_TOKEN_FILE tarayıcı yenilemesi için zorunludur")

    profile_dir = Path(
        os.getenv("BROWSER_PROFILE_DIR", "/var/lib/extrabet-bonus-bot/browser-profile")
    )
    profile_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(profile_dir, 0o700)
    start_url = os.getenv("BACKOFFICE_BROWSER_URL", CUSTOMERS_URL).strip()
    keepalive_seconds = _positive_minutes("BROWSER_KEEPALIVE_MINUTES", 5) * 60
    retry_seconds = _positive_minutes("BROWSER_RETRY_MINUTES", 10) * 60
    refresh_seconds = _positive_minutes("BROWSER_REFRESH_MINUTES", 330) * 60
    username = read_systemd_credential("backoffice_username")
    password = read_systemd_credential("backoffice_password")

    telegram = None
    if settings.telegram_bot_token and settings.telegram_chat_id:
        telegram = TelegramClient(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            settings.http_timeout_seconds,
        )
    last_alert: str | None = None

    def alert_once(key: str, message: str) -> None:
        nonlocal last_alert
        if last_alert == key:
            return
        last_alert = key
        LOGGER.warning(message)
        if telegram is not None:
            try:
                telegram.send(message)
            except ApiError:
                LOGGER.warning("Tarayıcı durum bildirimi Telegram'a gönderilemedi")

    def validate(token: str) -> None:
        with BackofficeClient(
            settings.backoffice_base_url,
            token,
            settings.http_timeout_seconds,
            1,
        ) as candidate:
            candidate.probe_authentication()

    capture = AuthCapture(
        validate,
        lambda token: store_token(settings.backoffice_token_file, token),
        settings.backoffice_token,
    )

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import Page, sync_playwright
    except ImportError as exc:
        raise ConfigurationError("playwright kurulmamış") from exc

    stopping = False

    def stop_handler(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            args=[
                "--disable-dev-shm-usage",
                "--disable-crash-reporter",
                "--disable-crashpad",
                "--disable-sync",
                "--disable-translate",
                "--disable-features=PasswordManagerOnboarding,PasswordLeakDetection",
                "--no-default-browser-check",
                "--no-first-run",
            ],
        )

        def observe_request(request) -> None:
            if not is_getclients_url(request.url):
                return
            try:
                capture.observe(request.url, request.all_headers())
            except PlaywrightError:
                LOGGER.warning("GetClients istek başlıkları okunamadı")

        def attach(page: Page) -> None:
            page.on("request", observe_request)

        for open_page in context.pages:
            attach(open_page)
        context.on("page", attach)
        page = context.new_page()
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=60_000)
        except PlaywrightError:
            LOGGER.warning("Başlangıç panel sayfası açılamadı")

        next_keepalive = time.monotonic()
        next_refresh = time.monotonic() + refresh_seconds
        while not stopping:
            try:
                page.wait_for_timeout(1000)
                now = time.monotonic()
                if now < next_keepalive:
                    continue

                if page.is_closed():
                    page = context.new_page()
                    page.goto(start_url, wait_until="domcontentloaded", timeout=60_000)
                if is_signin_url(page.url):
                    login_result = attempt_login(page, username, password)
                    if login_result == "mfa-required":
                        alert_once(
                            "mfa-required",
                            "Backoffice otomatik girişi 2FA doğrulaması bekliyor; manuel giriş gerekli.",
                        )
                        next_keepalive = now + retry_seconds
                        continue
                    if login_result != "authenticated":
                        alert_once(
                            login_result,
                            "Backoffice otomatik girişi tamamlanamadı; manuel kontrol gerekli.",
                        )
                        next_keepalive = now + retry_seconds
                        continue
                elif is_mfa_url(page.url):
                    alert_once(
                        "mfa-required",
                        "Backoffice otomatik girişi 2FA doğrulaması bekliyor; manuel giriş gerekli.",
                    )
                    next_keepalive = now + retry_seconds
                    continue

                if now >= next_refresh:
                    LOGGER.info("Backoffice tarayıcı sayfası periyodik yenileniyor")
                    page.reload(wait_until="domcontentloaded", timeout=60_000)
                    next_refresh = time.monotonic() + refresh_seconds

                trigger_getclients(page)
                last_alert = None
                LOGGER.info("Backoffice GetClients keepalive isteği gönderildi")
                next_keepalive = time.monotonic() + keepalive_seconds
            except PlaywrightError as exc:
                if stopping:
                    break
                LOGGER.warning(
                    "Backoffice keepalive işlemi başarısız error=%s",
                    type(exc).__name__,
                )
                if page.is_closed():
                    page = context.new_page()
                    try:
                        page.goto(start_url, wait_until="domcontentloaded", timeout=60_000)
                    except PlaywrightError:
                        LOGGER.warning("Başlangıç panel sayfası yeniden açılamadı")
                next_keepalive = time.monotonic() + retry_seconds
        context.close()
    if telegram is not None:
        telegram.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
