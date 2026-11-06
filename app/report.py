from __future__ import annotations

import html
from collections import Counter
from datetime import datetime

from .models import CheckResult, CheckStatus

ALLOWED_EMOJIS = {"✅", "❌"}


def _result_lines(result: CheckResult) -> list[str]:
    status = result.status
    if status == CheckStatus.BONUS_BULUNDU:
        return [f"Bonus: {html.escape(result.bonus_name or '')}", "Sonuç: ✅ Bonus kaydı bulundu."]
    if status == CheckStatus.BONUS_ISTEMIYOR:
        return ["Bonus tercihi: Deneme bonusu istemiyorum", "Sonuç: Bonus talep edilmemiş."]
    if status == CheckStatus.BONUS_BULUNAMADI:
        return ["Bonus: Bulunamadı", "Sonuç: ❌ Bonus kaydı bulunamadı."]
    if status == CheckStatus.INCELEME_GEREKLI:
        return ["Bonus: Kesinleştirilemedi", "Sonuç: Kontrol gerekli."]
    return ["Bonus: Kontrol edilemedi", "Sonuç: ❌ API kontrolü tamamlanamadı."]


def build_report(results: list[CheckResult], checked_at: datetime, next_run: datetime) -> str:
    lines = [
        "EXTRABET | BONUS KONTROL RAPORU",
        "",
        f"Tarih: {checked_at:%d.%m.%Y}",
        f"Kontrol saati: {checked_at:%H:%M}",
        f"Kontrol edilen: {len(results)} üye",
        "",
    ]
    for index, result in enumerate(results, start=1):
        login = html.escape(result.client.login, quote=True)
        lines.append(f"{index}. {login} ({result.client.client_id})")
        lines.extend(_result_lines(result))
        lines.append("")

    counts = Counter(result.status for result in results)
    lines.extend(
        [
            "Genel sonuç",
            f"Bonus kaydı bulunan: {counts[CheckStatus.BONUS_BULUNDU]}",
            f"Bonus istemeyen: {counts[CheckStatus.BONUS_ISTEMIYOR]}",
            f"Bonus bulunamayan: {counts[CheckStatus.BONUS_BULUNAMADI]}",
            f"Kontrol gerekli: {counts[CheckStatus.INCELEME_GEREKLI]}",
            f"API hatası: {counts[CheckStatus.API_HATASI]}",
            "",
            f"Sonraki kontrol: {next_run:%H:%M}",
        ]
    )
    return "\n".join(lines)


def build_cycle_error_report(checked_at: datetime, next_run: datetime) -> str:
    return "\n".join(
        [
            "EXTRABET | BONUS KONTROL RAPORU",
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
