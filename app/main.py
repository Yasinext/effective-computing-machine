from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from threading import Event, Thread

from apscheduler.schedulers.blocking import BlockingScheduler

from .backoffice import BackofficeClient
from .config import Settings
from .errors import AppError
from .service import BonusCheckService
from .telegram import TelegramClient
from .token_control import TokenControl, store_token


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extrabet kayıt bonusu kontrol botu")
    parser.add_argument("--once", action="store_true", help="Kontrolü bir kez çalıştır ve çık")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        settings = Settings.from_env()
        settings.validate_runtime_secrets()
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        # httpx logs complete request URLs at INFO. Telegram embeds the bot
        # token in its URL, so these dependency logs must never reach journal.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        backoffice = BackofficeClient(
            settings.backoffice_base_url,
            settings.backoffice_token,
            settings.http_timeout_seconds,
            settings.http_retry_count,
        )
        telegram = TelegramClient(
            settings.telegram_bot_token, settings.telegram_chat_id, settings.http_timeout_seconds
        )
        service = BonusCheckService(settings, backoffice, telegram)
        control_stop = Event()
        control_thread: Thread | None = None
        try:
            if args.once:
                service.run_cycle()
                return 0
            service.run_cycle()
            if settings.telegram_admin_user_id is not None and settings.backoffice_token_file is not None:
                def validate_candidate(token: str) -> None:
                    with BackofficeClient(
                        settings.backoffice_base_url,
                        token,
                        settings.http_timeout_seconds,
                        1,
                    ) as candidate:
                        candidate.probe_authentication()

                def install_candidate(token: str) -> None:
                    store_token(settings.backoffice_token_file, token)
                    backoffice.update_token(token)

                control = TokenControl(
                    telegram,
                    settings.telegram_admin_user_id,
                    validate_candidate,
                    install_candidate,
                    control_stop,
                )
                control_thread = Thread(target=control.run, name="token-control", daemon=True)
                control_thread.start()
            scheduler = BlockingScheduler(timezone=settings.report_timezone)
            scheduler.add_job(
                service.run_cycle,
                "interval",
                minutes=settings.interval_minutes,
                next_run_time=datetime.now(settings.report_timezone)
                + timedelta(minutes=settings.interval_minutes),
                max_instances=1,
                coalesce=True,
                id="bonus-check",
            )
            scheduler.start()
            return 0
        finally:
            control_stop.set()
            if control_thread is not None:
                control_thread.join(timeout=15)
            backoffice.close()
            telegram.close()
    except (AppError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            return 130
        logging.getLogger(__name__).error("Uygulama başlatılamadı: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
