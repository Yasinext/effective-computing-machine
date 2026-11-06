# Extrabet kayıt bonusu kontrol botu

Python 3.11+ ile çalışan bu servis, her döngüde BetConstruct Backoffice API'sinden alınan üyeleri `Created` zamanına göre sıralar, extrabet (`PartnerId=1457`) için en yeni dört üyeyi kontrol eder ve Telegram grubuna tek rapor gönderir.

## Güvenlik ve doğruluk sınırları

- Uygulama `OrderedItem=1` değerinin `Created` sıralaması olduğunu varsaymaz. Yanıttaki tüm kayıtları Python'da offset-aware `Created` değerine göre sıralar.
- `Data.Count`, dönen `Data.Objects` sayısından büyükse yanıtın tüm üyeleri kapsamadığı kabul edilir. Doğrulanmamış sayfalama kullanılmaz; yanlış dört üye raporlamak yerine teknik hata raporu gönderilir.
- `908` ve `909` için anlam atanmaz. `NO_BONUS_CATEGORY_IDS` ve `BONUS_EXPECTED_CATEGORY_IDS` yalnızca operatör gerçek veride doğruladıktan sonra doldurulmalıdır.
- “Bonus kaydı bulundu”, hedef bonus kaydının API yanıtında mevcut olduğu anlamına gelir. `AcceptanceType`, `ResultType`, `CanAccept`, `Count` ve `PaidAmount` doğrulanmadığından oyuncunun bonusu fiilen kullanabildiğini kanıtlamaz.
- Ham API yanıtları ve token'lar loglanmaz. Telegram'a yalnız kullanıcı adı ve ClientId gönderilir.

## Yerel kurulum

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

`.env` dosyasına gerçek değerleri yalnız kendi makinenizde ekleyin. Token'ları sohbet, kaynak kodu, ekran görüntüsü veya git deposu üzerinden paylaşmayın.

Testler gerçek token veya ağ bağlantısı gerektirmez:

```bash
pytest -q
```

Tek seferlik gerçek kontrol ve sürekli çalışma:

```bash
python -m app.main --once
python -m app.main
```

Sürekli mod başlangıçta hemen bir kontrol yapar, ardından sabit 20 dakikalık aralıklarla çalışır. Aynı anda yalnız bir kontrol çalışır.

## Telegram hazırlığı

1. BotFather üzerinden bot oluşturun ve token'ı yalnız `.env` dosyasına koyun.
2. Botu hedef gruba ekleyip mesaj gönderme izni verin.
3. Grupta bir test mesajı gönderin. Tarayıcıda `https://api.telegram.org/bot<TOKEN>/getUpdates` çağrısının sonucundaki `message.chat.id` değerini yerel olarak bulun. Token veya yanıtı paylaşmayın.
4. Grup kimliğini `TELEGRAM_CHAT_ID` olarak ayarlayın. Süper grup kimlikleri genellikle negatif bir sayıdır.
5. `python -m app.main --once` ile tek raporu doğrulayın.

Webhook kullanan bir botta `getUpdates` çalışmayabilir. Bu durumda mevcut bot yönetim yöntemiyle chat ID'yi güvenli biçimde belirleyin; webhook'u üretimde rastgele kaldırmayın.

## Ubuntu/Debian VPS kurulumu

Aşağıdaki örnek proje dosyalarının `/opt/extrabet-bonus-bot` altında olduğunu varsayar:

```bash
sudo useradd --system --home /opt/extrabet-bonus-bot --shell /usr/sbin/nologin extrabet-bot
sudo mkdir -p /opt/extrabet-bonus-bot
sudo cp -a app deployment requirements.txt /opt/extrabet-bonus-bot/
sudo chown -R extrabet-bot:extrabet-bot /opt/extrabet-bonus-bot
sudo -u extrabet-bot python3.11 -m venv /opt/extrabet-bonus-bot/.venv
sudo -u extrabet-bot /opt/extrabet-bonus-bot/.venv/bin/pip install -r /opt/extrabet-bonus-bot/requirements.txt
sudo install -o root -g extrabet-bot -m 0640 .env.example /etc/extrabet-bonus-bot.env
sudo editor /etc/extrabet-bonus-bot.env
sudo cp deployment/extrabet-bonus-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now extrabet-bonus-bot
```

Servis yönetimi ve loglar:

```bash
sudo systemctl status extrabet-bonus-bot
sudo systemctl restart extrabet-bonus-bot
sudo journalctl -u extrabet-bonus-bot -f
sudo journalctl -u extrabet-bonus-bot --since today
```

Güncellemeden önce mock testleri çalıştırın. Dosyaları kopyaladıktan sonra sahipliği koruyun ve servisi yeniden başlatın. `/etc/extrabet-bonus-bot.env` dosyasını yedeklere veya kaynak deposuna eklemeyin.

## Gerçek veriyle zorunlu doğrulama kontrol listesi

- [ ] Tarayıcı Network sekmesinde `Client/GetClients` gerçek istek gövdesini kaydedin; `SkeepRows`, `MaxRows`, `IsOrderedDesc` ve `OrderedItem` ad/değerlerini doğrulayın.
- [ ] Farklı sayfalardaki kayıtları karşılaştırarak sunucu sıralamasının gerçekten `Created` alanına göre olup olmadığını belirleyin.
- [ ] API'nin tek yanıtta en fazla kaç kayıt döndürdüğünü belirleyin. `Data.Count > len(Data.Objects)` oluyorsa gerçek sayfalama davranışını doğrulamadan canlıya çıkmayın.
- [ ] Doğrulanmış sayfalama gerekiyorsa request/response örnekleriyle uygulama ve testleri güncelleyin; `SkeepRows` davranışını tahmin etmeyin.
- [ ] Backoffice profil ekranında aynı üyeyi ve kategori metnini birlikte görerek `908`/`909` anlamlarını doğrulayın veya gerçek kategori sözlüğü endpoint'ini Network sekmesinden tespit edin.
- [ ] “Deneme bonusu istemiyorum” ID'lerini `NO_BONUS_CATEGORY_IDS`, bonus beklenen ve uygunluğu doğrulanmış ID'leri `BONUS_EXPECTED_CATEGORY_IDS` içine yazın.
- [ ] Hedef bonus kayıtlarının `PartnerBonusId` ve `BonusType` çiftlerini gerçek yanıtta doğrulayın.
- [ ] Bonus kaydı varlığının kullanılabilirlikten farklı olduğu kabulünü operasyon ekibiyle teyit edin.
- [ ] Token'ın hareketsizlik/mutlak süre sınırını ve 401/403 davranışını test edin. Her 20 dakikalık çağrının token yenilediğini varsaymayın.
- [ ] Telegram chat ID, bot izni, tek mesaj ve HTML kaçışını test grubunda doğrulayın.
- [ ] VPS'de `pytest -q`, manuel `--once`, servis restart ve reboot sonrası otomatik başlatma testlerini tamamlayın.

## Durumların anlamı

- `BONUS_BULUNDU`: Tam olarak bir hedef ID+tip kaydı var.
- `BONUS_ISTEMIYOR`: Kategori, yapılandırılmış doğrulanmış istememe ID'lerinden biri.
- `BONUS_BULUNAMADI`: Hedef kayıt yok ve kategori, yapılandırılmış doğrulanmış bonus-beklenen ID'lerden biri.
- `INCELEME_GEREKLI`: Kategori bilinmiyor, birden fazla hedef kayıt var veya hedef ID beklenmeyen tipte.
- `API_HATASI`: HTTP/yetki/timeout/şema hatası; bonus eksikliği olarak yorumlanmaz.
