# Kurulum Rehberi

Bu rehber Windows içindir. macOS/Linux farkları her adımın sonunda not olarak
belirtilmiştir.

**Toplam süre:** ~45 dakika (çoğu indirme beklemesi)
**Toplam indirme:** ~8 GB
**Gereken boş disk:** ~15 GB

---

## Neden bu kurulum yöntemi?

Projede üç ayrı parça çalışıyor. Bunları farklı şekillerde kuruyoruz ve her birinin
gerekçesi var:

| Parça | Nasıl kurulacak | Neden |
|---|---|---|
| Qdrant (vektör veritabanı) | Docker | Kurulumu yok, tek komutla kalkar, sisteminizi kirletmez |
| Ollama (model sunucusu) | Normal Windows kurulumu | Donanımınızı kendisi tanır, Docker katmanı performans kaybettirir |
| Backend + Frontend | Doğrudan makinede | Kodu sürekli değiştireceksiniz; Docker'da her değişiklikte imaj yeniden inşa edilir |

Her şeyi Docker'a koymak da mümkün (`docker-compose.yml` bunu destekliyor) ama
geliştirme sırasında zahmetli olur. Projeyi başkasına teslim ederken tam Docker
yolunu kullanın.

---

## Adım 0 — Ön gereksinimler

Dört program gerekiyor. Zaten kuruluysa sürüm kontrolü yapın, değilse kurun.

### Kontrol

`cmd` açın ve şunları tek tek çalıştırın:

```cmd
python --version
node --version
docker --version
ollama --version
```

Beklenen çıktı: `Python 3.11` veya üstü, `v20` veya üstü, herhangi bir Docker sürümü,
herhangi bir Ollama sürümü.

`'python' is not recognized` gibi bir hata alırsanız o program kurulu değil (veya
PATH'e eklenmemiş) demektir.

### Kurulum bağlantıları

| Program | Nereden | Not |
|---|---|---|
| Python 3.11+ | python.org/downloads | Kurulumda **"Add Python to PATH"** kutusunu mutlaka işaretleyin |
| Node.js 20+ | nodejs.org | LTS sürümünü seçin |
| Docker Desktop | docker.com/products/docker-desktop | Kurulumdan sonra bilgisayarı yeniden başlatmanız istenebilir |
| Ollama | ollama.com/download | Kurulunca arka planda servis olarak çalışmaya başlar |

> **macOS/Linux:** Docker Desktop yerine `docker` + `docker compose` paketleri yeterli.
> Ollama için `curl -fsSL https://ollama.com/install.sh | sh`.

---

## Adım 1 — Projeyi indirin

```cmd
git clone <depo-adresi> C:\projeler\mercek
```

Yol içinde **Türkçe karakter ve boşluk olmasın** — bazı Python araçları bunlarla
sorun çıkarır.

İyi: `C:\projeler\mercek`
Kötü: `C:\Users\Kullanıcı\Masaüstü\Bitirme Projesi\mercek`

`cmd` açıp bu klasöre gidin:

```cmd
cd C:\projeler\mercek
dir
```

`backend`, `frontend`, `README.md` ve `docker-compose.yml` görüyorsanız doğru
yerdesiniz.

### Türkçe karakter ayarı (Windows'ta önerilir)

`cmd` varsayılan olarak Türkçe karakterleri düzgün göstermez ve bazı Python
çıktılarında hata verir. Her yeni `cmd` penceresinde ilk komut olarak:

```cmd
chcp 65001
```

Bu komut karakter kodlamasını UTF-8'e alır. Kalıcı değildir, her pencerede tekrar
gerekir.

---

## Adım 2 — Qdrant'ı başlatın

Qdrant vektör veritabanı. Bilgi tabanınız (OWASP, KVKK metinleri) burada duracak.

**Önce Docker Desktop'ı açın.** Sistem tepsisindeki balina simgesi yeşile dönene
kadar bekleyin. Docker Desktop kapalıyken aşağıdaki komut hata verir.

```cmd
docker compose up -d qdrant
```

`-d` = arka planda çalış, terminali bana geri ver.

İlk çalıştırmada Qdrant imajını indirir (~150 MB, birkaç dakika). Sonraki
çalıştırmalarda anında açılır.

### Kontrol

```cmd
docker ps
```

`qdrant/qdrant` satırını ve `STATUS` sütununda `Up` görmelisiniz.

Tarayıcıda **http://localhost:6333/dashboard** adresini açın. Qdrant'ın yönetim
arayüzü gelmelidir. Koleksiyon listesi şu an boş, normal.

### Sorun çıkarsa

`cannot connect to the Docker daemon` → Docker Desktop kapalı, açın.
`port is already allocated` → 6333 portu dolu. `docker ps` ile başka bir Qdrant
çalışıyor mu bakın, varsa `docker stop <isim>`.

---

## Adım 3 — Modeli indirin

Ollama zaten arka planda çalışıyor. Modeli çekin:

```cmd
ollama pull qwen3.5:4b
```

**Bu ~2.6 GB indirir, internet hızınıza göre 5-20 dakika sürer.** İlerleme çubuğu
görürsünüz.

> **Model seçimi:** `qwen3.5:4b` 16 GB RAM'li, ayrı ekran kartı olmayan makineler
> içindir. 32 GB RAM'iniz varsa `qwen3.5:9b` çekin, sentez kalitesi belirgin şekilde
> artar. `qwen3.5:4b` dışında bir model çekerseniz Adım 4c'ye bakın.

### Kontrol

```cmd
ollama list
```

`qwen3.5:4b` satırını görmelisiniz. Şimdi gerçekten çalıştığını test edin:

```cmd
ollama run --think=false --verbose qwen3.5:4b "Tek cumleyle kendini tanit."
```

**`--think=false` bayrağını atlamayın.** Qwen3.5 bir akıl yürütme modeli ve Ollama bu
modu varsayılan olarak açar; model cevap vermeden önce yüzlerce token'lık iç muhakeme
üretir. Basit bir soru bile dakikalar sürebilir.

`--verbose` gerçek hızınızı gösterir. Çıktının sonunda:

```
total duration:       3.2s
eval count:           38 token(s)
eval rate:            12.4 tokens/s
```

**`eval rate` değeri sizin gerçek hızınız.**

| eval rate | Anlamı |
|---|---|
| 10-15 tok/sn | Normal. Belge başına 3-5 dakika bekleyin. |
| 5-9 tok/sn | Kabul edilebilir ama yavaş. Diğer programları kapatın. |
| 3 tok/sn altı | Model RAM'e sığmıyor, diske takas ediyor. Daha küçüğüne inin. |

3 tok/sn altındaysanız: `ollama pull qwen3.5:1.7b` ve `.env` içinde
`MERCEK_LLM_MODEL=qwen3.5:1.7b` yapın.

Sohbetten çıkmak için `/bye` yazın.

> Projede düşünme modu kodda kapatılmış durumda (`MERCEK_LLM_DUSUNME=false`).
> Bu ayar performansı en çok etkileyen tek değişkendir.

---

## Adım 4 — Backend kurulumu

### 4a. Sanal ortam oluşturun

Sanal ortam, bu projenin Python paketlerini sisteminizdeki diğer projelerden ayırır.
Bozulursa klasörü silip yeniden kurarsınız, sisteminiz etkilenmez.

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
```

Son komuttan sonra satır başında `(.venv)` görmelisiniz. **Bu işaret önemli** —
görmüyorsanız paketler yanlış yere kurulur.

> **macOS/Linux:** `source .venv/bin/activate`

### 4b. Paketleri kurun

```cmd
pip install -r requirements.txt
```

**5-10 dakika sürer.** En büyük paketler PyTorch (~200 MB) ve FlagEmbedding.

> **Önemli:** `requirements.txt` dosyasının ilk satırlarındaki
> `--extra-index-url https://download.pytorch.org/whl/cpu` satırını silmeyin. Bu satır
> PyTorch'un CPU sürümünü indirmesini sağlıyor. Silinirse pip CUDA sürümünü indirir —
> 2.5 GB fazladan dosya, ve NVIDIA kartınız yoksa hiç kullanılmaz.

### 4c. Ayarlar (çoğu kurulumda atlanabilir)

**Bu adımı atlayabilirsiniz.** Varsayılanlar yerel kurulum için zaten doğru:
Qdrant `localhost:6333`, Ollama `localhost:11434`, model `qwen3.5:4b`. Adım 3'te
bu modeli çektiyseniz hiçbir dosya oluşturmanız gerekmez.

Bir ayarı değiştirmek isterseniz `backend` klasöründe `.env` adında bir dosya
oluşturup yalnızca değiştireceğiniz satırları yazın. Sık kullanılanlar:

```ini
# Farklı bir model çektiyseniz
MERCEK_LLM_MODEL=qwen3.5:1.7b

# Model indirildikten sonra: açılışta internete çıkma
MERCEK_HF_OFFLINE=true

# Ayrı ekran kartınız varsa
MERCEK_EMBED_DEVICE=cuda

# Uzak, OpenAI uyumlu bir uç nokta kullanacaksanız
MERCEK_LLM_OLLAMA_YEREL=false
MERCEK_LLM_BASE_URL=https://<saglayici>/v1
MERCEK_LLM_API_KEY=<anahtar>
```

Ayarların tam listesi, varsayılanları ve gerekçeleri
[`backend/app/config.py`](backend/app/config.py) içinde yazılı.

> **Ayarlar iki konumdan okunur:** `backend/.env` ve ev dizinindeki
> `~/.mercek/mercek.env`. İkisinde de tanımlı bir değer varsa ev dizinindeki
> geçerlidir. **Gerçek bir API anahtarını ev dizinindeki dosyaya koyun** — orası
> depo ağacının dışındadır, yanlışlıkla commit edilmesi mümkün değildir.

### 4d. Bilgi tabanını doldurun

Bu adım OWASP ASVS, CWE, LINDDUN ve KVKK metinlerini vektöre çevirip Qdrant'a yazar.

```cmd
python -m app.knowledge.ingest
```

**İlk çalıştırmada BGE-M3 gömme modelini indirir (~2.2 GB), 5-15 dakika sürebilir.**
Ekranda uzun süre bir şey görünmeyebilir, normal. Bir kez indirilir, sonraki
çalıştırmalarda önbellekten okunur.

Bittiğinde şuna benzer bir çıktı görmelisiniz:

```
37 kayit 'mercek_bilgi_tabani' koleksiyonuna yazildi
  asvs         12
  cwe           6
  gdpr          3
  kvkk          6
  linddun       5
  saglayici     5
```

**Kontrol:** http://localhost:6333/dashboard adresini yenileyin.
`mercek_bilgi_tabani` koleksiyonu görünmeli ve içinde 37 kayıt olmalı.

### 4d-2. Kurulumu doğrulayın

Sunucuyu başlatmadan önce her şeyin yerinde olduğunu tek komutla kontrol edin:

```cmd
python -m app.dogrula
```

Yedi başlık altında sırayla test eder: Python sürümü, paketler, ayarlar, Qdrant
bağlantısı, LLM yanıtı, gömme modeli ve uçtan uca arama. Bir şey eksikse hangi
komutu çalıştırmanız gerektiğini söyler.

Hepsi `[TAMAM]` ise devam edin.

### 4e. Sunucuyu başlatın

```cmd
uvicorn app.main:app --reload
```

`--reload` = kodu her kaydettiğinizde sunucu kendini yeniler. Geliştirme sırasında
çok işinize yarayacak.

**Bu pencereyi kapatmayın.** Sunucu burada çalışıyor.

### Kontrol

Yeni bir tarayıcı sekmesinde:

- **http://localhost:8000/saglik** → `{"durum":"ayakta","model":"qwen3.5:4b"}`
- **http://localhost:8000/docs** → Otomatik API dokümantasyonu (Swagger)

`/docs` sayfasından dosya yükleyip API'yi arayüzsüz de test edebilirsiniz.

---

## Adım 5 — Frontend kurulumu

**Yeni bir `cmd` penceresi açın** (backend'inki çalışmaya devam etsin).

```cmd
cd C:\projeler\mercek\frontend
npm install
npm run dev
```

`npm install` 1-2 dakika sürer. Ardından şuna benzer bir çıktı görürsünüz:

```
  VITE v6.0.7  ready in 412 ms
  ➜  Local:   http://localhost:5173/
```

Tarayıcıda **http://localhost:5173** adresini açın. Mor-siyah arayüz gelmelidir.

---

## Adım 6 — İlk analizi çalıştırın

Bir PDF veya DOCX tez yükleyin. Elinizde yoksa test için basit bir metin dosyası
oluşturun:

`test.txt` adında bir dosya yapıp içine şunu yazın:

```
3.1 Sistem Mimarisi
Kullanicilarin semptom fotograflari Firebase Realtime Database uzerinde saklanmaktadir.
Hasta teshis bilgileri PostgreSQL veritabanina yazilir ve gunluk olarak yedeklenir.
Metin ozetleme icin OpenAI API kullanilmaktadir.
Ilac hatirlatmalari FCM uzerinden anlik bildirim olarak gonderilir.

4.1 Kullanici Akisi
Kullanici kayit ekraninda ad, soyad, dogum tarihi ve telefon numarasi girer.
```

Bunu arayüze sürükleyin.

**Ne olacak:** Sol taraftaki çalışma rayı ajanları sırayla çalıştıracak. 4B modelle
belge başına **3-6 dakika** beklemeniz normal. Rayın ilerlemesi ve ölçüm etiketleri
işin gerçekten yürüdüğünü gösterir.

İlk analizde model belleğe yüklenirken ekstra 30-60 saniye gecikme olabilir.

---

## Günlük kullanım

Kurulum bir kez yapılır. Sonraki günlerde:

```cmd
:: 1. Docker Desktop'ı açın, sonra:
docker compose up -d qdrant

:: 2. Backend (bir cmd penceresi)
cd C:\projeler\mercek\backend
.venv\Scripts\activate
uvicorn app.main:app --reload

:: 3. Frontend (başka bir cmd penceresi)
cd C:\projeler\mercek\frontend
npm run dev
```

Ollama arka planda kendiliğinden çalışır, ayrıca başlatmanız gerekmez.

**Kapatmak için:** Her iki `cmd` penceresinde `Ctrl+C`, sonra
`docker compose stop qdrant`.

---

## Sık karşılaşılan sorunlar

**`'python' is not recognized`**
Python PATH'e eklenmemiş. Python'u kaldırıp yeniden kurun, kurulumda "Add Python to
PATH" kutusunu işaretleyin.

**`(.venv)` işareti görünmüyor**
Sanal ortam etkin değil. `backend` klasöründe olduğunuzdan emin olup
`.venv\Scripts\activate` komutunu tekrar çalıştırın. Bu işaret olmadan `pip install`
paketleri yanlış yere kurar.

**`Could not find a version that satisfies the requirement torch==...`**
Sürüm sabitlemesi eskimiş. Güncel `requirements.txt` alt sınır (`>=`) kullanıyor,
sabit pin (`==`) değil. Dosyanızda `torch==` görüyorsanız `git pull` ile güncelleyin
veya elle `torch>=2.9` yapın.

**`pip install` çok büyük dosya indiriyor**
`requirements.txt` içindeki `--extra-index-url .../whl/cpu` satırı silinmiş olabilir.
Geri ekleyip `pip cache purge` ile önbelleği temizleyin, yeniden deneyin.

**Backend `Connection refused` diyor**
Qdrant çalışmıyor. `docker ps` ile kontrol edin, yoksa
`docker compose up -d qdrant` çalıştırın.

**Analiz başlıyor ama `getir` adımında takılıyor**
Bilgi tabanı boş. Adım 4d'yi çalıştırdınız mı? http://localhost:6333/dashboard
adresinden `mercek_bilgi_tabani` koleksiyonunda kayıt olup olmadığını kontrol edin.

**Analiz `cikar` adımında hata veriyor**
Ollama'ya ulaşılamıyor olabilir. `ollama list` çalışıyor mu? `.env` içindeki
`MERCEK_LLM_MODEL` değeri `ollama list` çıktısındaki isimle birebir aynı mı?

**Analiz ayrıştırma adımında takılıyor**
Uvicorn penceresine bakın. `[model] BGE-M3 yukleniyor...` yazıyorsa model belleğe
alınıyor demektir; bir kez olur ve 1-3 dakika sürer. Sunucu açılışında bu yüklemeyi
öne almak için `MERCEK_BASLANGICTA_YUKLE=true` (varsayılan) bırakın.

**Analiz çok yavaş veya bilgisayar kilitleniyor**
Model RAM'inize sığmıyor. Daha küçüğüne inin:
`ollama pull qwen3.5:1.7b`, sonra `.env` içinde `MERCEK_LLM_MODEL=qwen3.5:1.7b`.

**Arayüzde `Sunucuya bağlanılamadı`**
Backend çalışmıyor veya farklı bir portta. http://localhost:8000/saglik açılıyor mu?

**`You are sending unauthenticated requests to the HF Hub`**
Uyarıdır, hata değil. BGE-M3 herkese açık bir model, token gerektirmez. Paylaşımlı bir
ağdaysanız (üniversite) kotaya takılabilirsiniz; ücretsiz bir token alıp `.env` içine
`MERCEK_HF_TOKEN=` satırıyla ekleyin.

**Model indirildikten sonra çevrimdışına alın (önerilir)**
İlk `ingest` başarıyla bittiyse ayar dosyasında `MERCEK_HF_OFFLINE=true` yapın. Bundan
sonra sistem açılışta HuggingFace sürüm kontrolü için internete çıkmaz.
`python -m app.dogrula` modelin önbellekte olduğunu doğruladıktan sonra yapın.

**`UnicodeEncodeError` veya bozuk Türkçe karakterler**
`cmd` penceresinde `chcp 65001` çalıştırın.

**Port zaten kullanımda (`address already in use`)**
Aynı servisin eski bir örneği çalışıyor. Backend için:
`netstat -ano | findstr :8000` ile PID bulun, `taskkill /PID <numara> /F` ile kapatın.

---

## Tam ASVS korpusunu yükleme (isteğe bağlı)

Tohum veri 12 ASVS maddesi içeriyor — sistemi denemek için yeterli. Gerçek
değerlendirme yapacaksanız tam korpusu yükleyin:

`backend` klasöründe, sanal ortam etkinken:

```cmd
curl -L -o asvs.json https://github.com/OWASP/ASVS/releases/download/v5.0.0_release/OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json

python -m app.knowledge.ingest --asvs asvs.json --sifirla
```

Bu 345 ASVS 5.0 maddesi ekler. Gömme işlemi CPU'da 3-8 dakika sürer.

`--sifirla` koleksiyonu baştan kurar; kullanmazsanız tohum veri iki kez yazılır.
Ayrıca tam korpus verildiğinde tohumdaki 12 ASVS maddesi atılır: tohum 4.0.3
numaralarını kullanıyor, resmi JSON 5.0 kullanıyor ve aynı kimlik iki sürümde farklı
gereksinimi gösteriyor.

**İndirmeyi doğrulayın.** `curl` bir hata sayfası indirmiş olabilir:

```cmd
dir asvs.json
```

Boyut ~160 KB olmalı. 5 KB civarıysa indirme başarısız olmuştur, adresi tarayıcıda
açıp elle indirin.

---

## Kalite ölçümünü çalıştırma (isteğe bağlı)

`backend/degerlendirme/` altında iki temiz, iki tuzaklı test belgesi ve beklenen
çıktıları var. Değişiklik yaptıktan sonra çıktının bozulup bozulmadığını buradan
görebilirsiniz.

`backend` klasöründe, sanal ortam etkinken:

```cmd
python -m degerlendirme.olcek --hizli --ozetsiz
```

Bu mod hiç LLM çağrısı yapmaz, saniyeler sürer ve determinist katmanı ölçer. Tam
boru hattını ölçmek için (dakikalar sürer):

```cmd
python -m degerlendirme.olcek
```
