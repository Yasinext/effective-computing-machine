# Extrabet kayıt bonusu kontrol botu

Python 3.11+ ile çalışan bu servis, her döngüde BetConstruct Backoffice API'sinden alınan üyeleri `Created` zamanına göre sıralar, extrabet (`PartnerId=1457`) için en yeni on üyeyi kontrol eder ve Telegram grubuna tek, durumlara göre gruplanmış rapor gönderir.

## Güvenlik ve doğruluk sınırları

- Uygulama varsayılan olarak `OrderedItem=1` değerinin `Created` sıralaması olduğunu varsaymaz. `GET_CLIENTS_CREATED_ORDER_VERIFIED=false` iken yanıt tüm sonuçları kapsamıyorsa yanlış dört üye raporlamak yerine teknik hata raporu gönderilir.
- 6 Kasım 2026 canlı doğrulamasında `SkeepRows=0/20/40` çakışmayan ardışık sayfalar, `OrderedItem=1` ise sayfa sınırlarında azalan `Created` sırası döndürdü. Bu kurulumda doğrulanmış mod açıldığında uygulama sayfaları sırayla alır, her sayfa sınırında sıralamayı ve tekrarlı ID'leri yeniden denetler, hedef partner için yeterli üye bulunca durur ve son seçimi yine Python'da offset-aware `Created` değerine göre yapar.
- Kategori ID'leri `.env.example` içinde boş bırakılır. Mevcut extrabet kurulumu için operatör belirlemesi ve canlı korelasyon sonucunda `NO_BONUS_CATEGORY_IDS=909`, `BONUS_EXPECTED_CATEGORY_IDS=907,908` kullanılır; başka partner veya ortamda bu değerler yeniden doğrulanmalıdır.
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

### Özel mesajla Backoffice token yenileme

İsteğe bağlı kontrol kanalı yalnız özel Telegram sohbetinde çalışır. Grup mesajları ve `TELEGRAM_ADMIN_USERNAMES` listesinde olmayan kullanıcılar hiçbir yanıt almadan yok sayılır.

```dotenv
BACKOFFICE_TOKEN_FILE=/var/lib/extrabet-bonus-bot/backoffice.token
TELEGRAM_ADMIN_USERNAMES=denizgmb,ayhanq7
```

Yetkili kullanıcı botla özel konuşmada `/token` gönderir. Bot 60 saniye içinde gelecek bir sonraki özel mesajı aday token olarak alır, mesajı silmeye çalışır ve token'ı canlı Backoffice isteğiyle doğrular. Yalnız başarılı doğrulamadan sonra izinleri `0600` olan token dosyasını atomik biçimde değiştirir ve yeni token'ı servis yeniden başlamadan kullanır. Token hiçbir cevap veya log içinde gösterilmez.

Kullanıcı adları değiştirilebilir olduğundan sayısal Telegram kullanıcı ID'leri daha güçlü bir yetkilendirme yöntemidir. Mevcut kullanıcı-adı modu operatörün açık tercihiyle sağlanmıştır; listedeki hesapların kullanıcı adı değişiklikleri düzenli kontrol edilmelidir.

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
sudo install -d -o extrabet-bot -g extrabet-bot -m 0700 /var/lib/extrabet-bonus-bot
sudo install -o extrabet-bot -g extrabet-bot -m 0600 /dev/null /var/lib/extrabet-bonus-bot/backoffice.token
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

- [x] `Client/GetClients` canlı isteğinde `SkeepRows`, `MaxRows`, `IsOrderedDesc` ve `OrderedItem` parametreleri denendi.
- [x] `SkeepRows=0/20/40` sayfalarının çakışmadığı ve sayfa sınırlarında `Created` sırasının azalan olduğu doğrulandı.
- [x] API'nin istenen 1000 kaydı tek yanıtta vermediği ve fiili sayfa boyutunun 20 olduğu gözlendi; korumalı sayfalama eklendi.
- [x] Mevcut kurulum için kategori yapılandırması `909` istemiyor, `907,908` bonus bekleniyor olarak belirlendi ve canlı ID–bonus korelasyonuyla kontrol edildi.
- [ ] Kategori metinlerini doğrudan döndüren bir API bulunursa ID→etiket eşlemesini ayrıca doğrulayın; mevcut `GetClients` yanıtı yalnız ID içeriyor.
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
