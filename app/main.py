from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from .backoffice import BackofficeClient
from .config import Settings
from .errors import AppError
from .service import BonusCheckService
from .telegram import TelegramClient


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
        try:
            if args.once:
                service.run_cycle()
                return 0
            service.run_cycle()
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
            backoffice.close()
            telegram.close()
    except (AppError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            return 130
        logging.getLogger(__name__).error("Uygulama başlatılamadı: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
