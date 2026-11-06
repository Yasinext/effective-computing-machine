from __future__ import annotations

import html
from datetime import datetime

from .models import CheckResult, CheckStatus

ALLOWED_EMOJIS = {"✅", "❌"}


def _compact_result(result: CheckResult) -> str:
    status = result.status
    if status == CheckStatus.BONUS_BULUNDU:
        return f"✅ {html.escape(result.bonus_name or 'Bonus kaydı bulundu')}"
    if status == CheckStatus.BONUS_ISTEMIYOR:
        return "Deneme bonusu istemiyorum"
    if status == CheckStatus.BONUS_BULUNAMADI:
        return "❌ FS Yansıması bulunamadı."
    if status == CheckStatus.INCELEME_GEREKLI:
        return "Kontrol gerekli."
    return "❌ API kontrolü tamamlanamadı."


STATUS_GROUPS = (
    (CheckStatus.BONUS_BULUNDU, "Bonus kaydı bulunan"),
    (CheckStatus.BONUS_ISTEMIYOR, "Bonus istemeyen"),
    (CheckStatus.BONUS_BULUNAMADI, "FS yansıması bulunamayan"),
    (CheckStatus.INCELEME_GEREKLI, "Kontrol gerekli"),
    (CheckStatus.API_HATASI, "API hatası"),
)


def build_report(results: list[CheckResult], checked_at: datetime, next_run: datetime) -> str:
    lines = [
        "KONTROL RAPORU",
        "",
        f"Tarih: {checked_at:%d.%m.%Y}",
        f"Kontrol saati: {checked_at:%H:%M}",
        f"Kontrol edilen: {len(results)} üye",
        "",
    ]
    for status, heading in STATUS_GROUPS:
        grouped = [result for result in results if result.status == status]
        if not grouped:
            continue
        lines.append(heading)
        for result in grouped:
            login = html.escape(result.client.login, quote=True)
            lines.append(
                f"- {login} ({result.client.client_id}) — {_compact_result(result)}"
            )
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
