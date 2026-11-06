# Doğrulama raporu

Tarih: 6 Kasım 2026

## Yerel doğrulama sonucu

- Python: 3.12.13 (proje gereksinimi: 3.11+)
- Komut: `.venv/bin/python -m pytest -q`
- Sonuç: `29 passed in 0.04s`
- `app/` ve `tests/` için bytecode derleme kontrolü başarılı.
- `python -m app.main --help` başarılı.
- Testlerde gerçek Backoffice veya Telegram bağlantısı kurulmadı; tüm HTTP davranışları mock yanıtlarla sınandı.

## Mock testlerle doğrulananlar

- `Created` sıralaması, farklı UTC offset'leri, `LastLoginTime` alanının etkisizliği ve partner filtresi.
- Her iki hedef bonusun tekil bulunması, bulunamama, bilinmeyen kategori, istememe kategorisi, çift/tekrarlı hedef kayıt ve ID-tip çelişkisi.
- 401, 403, 500, timeout, bozuk JSON, `HasError=true` ve bozuk yanıt şemaları.
- Eksik ilk sayfanın güvenli biçimde reddedilmesi.
- Üye bazlı hatanın diğer üyeleri durdurmaması.
- Her döngüde tek Telegram mesajı ve sonraki döngüde yeni mesaj.
- HTML kaçışı, hassas alanların rapora girmemesi ve emoji kısıtı.

## Canlı bağlantı olmadan doğrulanamayanlar

1. `Client/GetClients` gövdesindeki `SkeepRows`, `MaxRows`, `IsOrderedDesc` ve `OrderedItem` parametrelerinin mevcut canlı API'deki kesin davranışı.
2. `OrderedItem=1` değerinin gerçekten `Created` sıralaması olup olmadığı.
3. API'nin maksimum sayfa boyutu ve güvenilir sayfalama davranışı. Uygulama bu nedenle `Data.Count > len(Data.Objects)` olduğunda yanlış sonuç üretmek yerine döngüyü teknik hatayla sonlandırır.
4. `908` ve `909` kategori ID'lerinin metin karşılıkları. İki kategori yapılandırmasının varsayılanı bilerek boştur.
5. Bonus kayıtlarındaki `AcceptanceType`, `ResultType`, `CanAccept`, `Count` ve `PaidAmount` alanlarının anlamları; kayıt varlığı gerçek kullanılabilirliği kanıtlamaz.
6. Backoffice token'ının hareketsizlik veya mutlak süre sonu ve canlı 401/403 davranışı.
7. Telegram botunun gerçek grup chat ID'si, gruptaki gönderim izni ve rate-limit davranışı.
8. VPS'de reboot sonrası `systemd` otomatik başlatma davranışı.

Bu maddeler tamamlanmadan canlı sonuçlar kesin operasyonel doğrulama olarak kabul edilmemelidir. Ayrıntılı adımlar README'deki “Gerçek veriyle zorunlu doğrulama kontrol listesi” bölümündedir.
