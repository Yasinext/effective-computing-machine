from __future__ import annotations

import html
from datetime import datetime

from .models import CheckResult, CheckStatus

ALLOWED_EMOJIS = {"✅", "❌"}


STATUS_GROUPS = (
    (CheckStatus.BONUS_BULUNAMADI, "❌ FS Yansıması bulunamadı."),
    (CheckStatus.INCELEME_GEREKLI, "Kontrol gerekli"),
    (CheckStatus.API_HATASI, "❌ API kontrolü tamamlanamadı."),
)


def _member_line(result: CheckResult) -> str:
    login = html.escape(result.client.login, quote=True)
    return f"- {login} ({result.client.client_id})"


def build_report(results: list[CheckResult], checked_at: datetime, next_run: datetime) -> str:
    lines = [
        "KONTROL RAPORU",
        "",
        f"Tarih: {checked_at:%d.%m.%Y}",
        f"Kontrol saati: {checked_at:%H:%M}",
        f"Kontrol edilen: {len(results)} üye",
        "",
    ]
    bonus_groups: dict[str, list[CheckResult]] = {}
    for result in results:
        if result.status != CheckStatus.BONUS_BULUNDU:
            continue
        bonus_name = result.bonus_name or "Bonus kaydı bulundu"
        bonus_groups.setdefault(bonus_name, []).append(result)

    for bonus_name, grouped in bonus_groups.items():
        lines.append(f"✅ {html.escape(bonus_name)}")
        lines.extend(_member_line(result) for result in grouped)
        lines.append("")

    for status, heading in STATUS_GROUPS:
        grouped = [result for result in results if result.status == status]
        if not grouped:
            continue
        lines.append(heading)
        lines.extend(_member_line(result) for result in grouped)
        lines.append("")

    lines.extend(
        [
            f"Sonraki kontrol: {next_run:%H:%M}",
        ]
    )
    return "\n".join(lines)


def build_cycle_error_report(checked_at: datetime, next_run: datetime) -> str:
    return "\n".join(
        [
            "KONTROL RAPORU",
            "",
            f"Tarih: {checked_at:%d.%m.%Y}",
            f"Kontrol saati: {checked_at:%H:%M}",
            "Kontrol edilen: 0 üye",
            "",
            "Sonuç: ❌ API kontrolü tamamlanamadı.",
            "Üye listesi güvenli biçimde alınamadı; sonuç üretilmedi.",
            "",
            f"Sonraki kontrol: {next_run:%H:%M}",
        ]
    )
