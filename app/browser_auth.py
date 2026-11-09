from __future__ import annotations

import logging
import os
import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from .backoffice import BackofficeClient
from .config import Settings
from .errors import ApiError, ConfigurationError
from .token_control import TOKEN_PATTERN, store_token

LOGGER = logging.getLogger(__name__)


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
    start_url = os.getenv(
        "BACKOFFICE_BROWSER_URL", "https://backofficewebadmin.betconstruct.com/"
    ).strip()
    refresh_seconds = _positive_minutes("BROWSER_REFRESH_MINUTES", 330) * 60

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
                "--disable-sync",
                "--disable-translate",
                "--disable-features=PasswordManagerOnboarding,PasswordLeakDetection",
                "--no-default-browser-check",
                "--no-first-run",
                "--restore-last-session",
            ],
        )

        def attach(page: Page) -> None:
            page.on("request", lambda request: capture.observe(request.url, request.all_headers()))

        for open_page in context.pages:
            attach(open_page)
        context.on("page", attach)
        page = context.pages[0] if context.pages else context.new_page()
        if page.url == "about:blank":
            try:
                page.goto(start_url, wait_until="domcontentloaded", timeout=60_000)
            except PlaywrightError:
                LOGGER.warning("Başlangıç panel sayfası açılamadı")

        next_refresh = time.monotonic() + refresh_seconds
        observed_update = capture.updated_at
        while not stopping:
            try:
                page.wait_for_timeout(1000)
                if capture.updated_at > observed_update:
                    observed_update = capture.updated_at
                    next_refresh = capture.updated_at + refresh_seconds
                if time.monotonic() >= next_refresh:
                    LOGGER.info("Backoffice tarayıcı sayfası periyodik yenileniyor")
                    previous_token = capture.last_token
                    page.reload(wait_until="domcontentloaded", timeout=60_000)
                    if capture.last_token == previous_token:
                        next_refresh = time.monotonic() + 600
                    else:
                        next_refresh = time.monotonic() + refresh_seconds
            except PlaywrightError:
                LOGGER.warning("Tarayıcı sayfası yenilemesi başarısız")
                pages = context.pages
                page = pages[0] if pages else context.new_page()
                next_refresh = time.monotonic() + 60
        context.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
