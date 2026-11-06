# Doğrulama raporu

Tarih: 6 Kasım 2026

## Yerel doğrulama sonucu

- Python: 3.12.13 (proje gereksinimi: 3.11+)
- Komut: `.venv/bin/python -m pytest -q`
- Sonuç: `31 passed in 0.04s`
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

## 6 Kasım 2026 canlı API doğrulaması

- Token ile `Client/GetClients` ve `Client/GetClientBonuses` çağrıları başarılı oldu.
- API `MaxRows=1000` isteğine rağmen 20 kayıt döndürdü; güvenli durdurma mekanizması eksik sayfayı doğru biçimde yakaladı.
- `SkeepRows=0`, `20` ve `40` istekleri çakışmayan ardışık sayfalar döndürdü.
- Üç sayfada ve sayfa sınırlarında `OrderedItem=1` yanıtlarının `Created` değerleri azalan sıradaydı.
- İlk sayfadaki 20 kaydın tamamı hedef partner `1457` içindi.
- İlk 20 üyelik hassas-verisiz korelasyonda kategori `907`: 1 hedef kayıt/1 üye; `908`: 0 hedef kayıt/11 üye; `909`: 0 hedef kayıt/8 üye görüldü.
- Operatörün önceki belirlemesiyle birlikte sunucu yapılandırması `NO_BONUS_CATEGORY_IDS=909` ve `BONUS_EXPECTED_CATEGORY_IDS=907,908` olarak seçildi.
- Doğrulanmış sayfalama modu eklendi; her canlı sayfada azalan `Created`, sabit `Count`, benzersiz ID ve boş-sayfa koşulları yeniden kontrol ediliyor.
- İlk servis denemesinde `httpx` INFO erişim logunun Telegram token'ını URL içinde gösterebildiği tespit edildi. `httpx` ve `httpcore` log seviyeleri zorunlu olarak `WARNING` yapıldı. Düzeltme sonrası canlı döngüde journal'ın yalnız zamanlayıcı kayıtları içerdiği, URL/token loglanmadığı ve servisin yeniden başlatmasız aktif kaldığı doğrulandı.
- Özel Telegram sohbetinden Backoffice token yenileme desteği eklendi. Grup mesajları ve izin listesi dışındaki kullanıcı adları sessizce yok sayılıyor; aday token canlı API'de doğrulanıyor, `0600` dosyaya atomik yazılıyor ve çalışan HTTP istemcisine yeniden başlatmasız uygulanıyor.

## Hâlâ doğrulanması gerekenler

1. Kategori metnini doğrudan döndüren doğrulanmış bir endpoint bulunmadı; `GetClients` yalnız `PartnerClientCategoryId` içeriyor. Mevcut eşleme operatör belirlemesine dayanıyor.
2. Bonus kayıtlarındaki `AcceptanceType`, `ResultType`, `CanAccept`, `Count` ve `PaidAmount` alanlarının anlamları; kayıt varlığı gerçek kullanılabilirliği kanıtlamaz.
3. Backoffice token'ının kesin hareketsizlik veya mutlak süre sonu ve canlı 401/403 davranışı.
4. Telegram botunun gruptaki gönderim izni ve rate-limit davranışı.
5. VPS'de reboot sonrası `systemd` otomatik başlatma davranışı.

Bu maddeler tamamlanmadan canlı sonuçlar kesin operasyonel doğrulama olarak kabul edilmemelidir. Ayrıntılı adımlar README'deki “Gerçek veriyle zorunlu doğrulama kontrol listesi” bölümündedir.
