# Mercek

**Tasarım aşaması risk ön-taraması.** Bir proje raporu veya tez yüklenir; sistem
belgede anlatılan teknoloji ve veri akışlarına bakar, güvenlik / veri sızıntısı /
hukuki sorumluluk açısından **doğrulanması gereken noktaları** kaynağıyla birlikte
listeler.

Koda değil belgeye baktığı için kesin hüküm vermez: "açık vardır" demez, "bu teknoloji
veriyi şöyle işler, sizde nasıl yapılandırıldığını kontrol edin" der. Dört ajan
(çıkarıcı, getirici, analist, doğrulayıcı) LangGraph üzerinde çalışır; bilgi tabanı
OWASP ASVS, CWE, LINDDUN, KVKK ve GDPR metinlerinden oluşur. Her bulgu hem belgeden
bir alıntıya hem de bir standart maddesine dayandırılır; dayanağı olmayan bulgu
kullanıcıya ulaşmaz.

---

## Hızlı başlangıç

Adım adım rehber: **[KURULUM.md](KURULUM.md)** (~45 dakika, çoğu indirme beklemesi,
toplam ~6 GB).

```bash
git clone https://github.com/cgrayd/mercek.git
cd mercek
```

**Docker ile**

```bash
docker compose up -d qdrant ollama
docker compose exec ollama ollama pull qwen3.5:4b
docker compose up -d backend
docker compose exec backend python -m app.knowledge.ingest
```

**Elle**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.knowledge.ingest    # 37 kayıtlık tohum bilgi tabanı
python -m app.dogrula             # kurulumu yedi başlıkta doğrular
uvicorn app.main:app --reload

cd ../frontend && npm install && npm run dev
```

Arayüz `http://localhost:5173` · API `http://localhost:8000/docs`

Kurulumdan sonra Windows'ta **`baslat.bat`** dosyasına çift tıklamak yeterli. Ayar
dosyası oluşturmak gerekmez; varsayılanlar yerel kurulum için doğrudur
([`config.py`](backend/app/config.py)).

| Donanım | Model | Beklenen hız |
|---|---|---|
| 16 GB RAM, GPU yok | `qwen3.5:4b` | ~10-15 tok/sn |
| 32 GB RAM, GPU yok | `qwen3.5:9b` | ~4-6 tok/sn |
| 16 GB VRAM'li GPU | `gpt-oss:20b` | ~40+ tok/sn |

---

## Nasıl çalışır

Klasik RAG'de kullanıcı soru sorar, sistem bir doküman havuzundan parça çeker. Burada
**yüklenen tez bilgi kaynağı değil, analiz edilecek girdidir**; sorgular kullanıcıdan
değil, dokümandan ajanlar tarafından üretilir. Belge hiçbir vektör indeksine yazılmaz —
yazılsaydı kendi cümleleri "kanıt" olarak geri döner, sistem kendini doğrulamaya
başlardı.

Boru hattı iki dalgalıdır: determinist düğümler saniyeler içinde biter ve sonuçlarını
SSE ile hemen yayımlar, LLM düğümleri dakikalar sürer ve üstüne **ekler**. LLM tarafı
tamamen başarısız olsa bile determinist bulgular ayakta kalır.

```
DALGA 1 (LLM yok)   ayristir → cikar_sozluk → getir → analiz → dogrula
                                                                  ↓ SSE
DALGA 2 (LLM)       ozetle → yonlendir → cikar_llm → getir2 ⇄ sorgu_yaz
                                                        ↓      (≤3 tur)
                                                     analiz2 → dogrula2
```

---

## Tasarım kararları

| Karar | Gerekçe |
|---|---|
| **Qdrant** | Tek koleksiyonda yoğun + seyrek vektör; RRF füzyonu sunucu tarafında. `kaynak_turu` filtresi şart: filtresiz arama teknik soruya hukuki metin döndürür. |
| **BGE-M3** | Tek modelden dense + sparse. Yoğun vektör anlamı, seyrek vektör `CWE-311` / `AES-256` gibi teknik jetonları yakalar. Türkçe belge ↔ İngilizce standart eşleşmesi güçlü. |
| **ASVS, Top 10 değil** | Top 10 kategorik ve kabadır, "A01 riski olabilir" gibi içi boş bulgu üretir. ASVS'in her maddesi atomik ve doğrulanabilir bir gereksinimdir. |
| **LINDDUN + CWE + KVKK/GDPR** | Sırasıyla mahremiyet tehdit modeli, zafiyet tanımları ve hukuki kol. ASVS teknik kontrolleri, LINDDUN mahremiyeti kapsar. |
| **Yerel LLM** | Yüklenen belge yayımlanmamış olabilir; veri sızıntısı analizi yapan bir aracın girdiyi üçüncü tarafa göndermesi kendi tezini çürütür. |
| **Yapısal çıktı** | Ollama `format`, OpenAI uyumlu uçlar `response_format` ile şemayı çözümleme sırasında zorlar. Geçersiz JSON yapısal olarak imkânsız; projede serbest metin ayrıştırma yok. |
| **LangGraph** | Serbest ReAct ajanı deterministik değil. Akışın iskeletini geliştirici çizer; özerklik tek kontrollü döngüde (retrieval zayıfsa sorgu yeniden yazma, ≤3 tur). |

Üç karar daha az bariz olduğu için ayrıca:

**Alaka kapısı füzyondan *önce* kurulur.** RRF skoru sıra tabanlıdır (`1/(k+rank)`),
benzerlik değil; füzyondan sonra konan bir eşik alakasız kaydı eleyemez. Kosinüs eşiği
yoğun ön-çekime uygulanır, füzyon sonucu o kümeye daraltılır.

**Determinist sözlük LLM'in yanında durur, altında değil.** Tezde geçen "Firebase"
kaçırılırsa sonraki hiçbir aşama telafi edemez. [`gazetteer.py`](backend/app/core/gazetteer.py)
57 teknoloji girişiyle bu garantiyi verir ve **Türkçe çekim ekleri açıkça sayılmıştır** —
çıplak kelime sınırı "Çocukların", "konumu", "Docker'da" biçimlerini kaçırır. Türetme
ekleri listede yok: "çocukların" eşleşir, "çocukluk" eşleşmez.

**Halüsinasyon savunması üç katmanlı.** Makine kontrolü (atıftaki kaynak gerçekten
getirildi mi), determinist konu kapısı (belgede hiç kişisel veri yoksa mahremiyet
bulgusu konusuzdur), sonra LLM denetimi. Ayrıca atıf alanları şema düzeyinde kilitli:
kimlikler enum'a çevrilip dilbilgisine girer, model listede olmayanı üretemez. Elenen
bulgular gerekçesiyle kullanıcıya gösterilir.

Belge içeriği modele daima `<<<BELGE_ICERIGI>>>` sınırları arasında, veri olarak geçer
([`llm.py`](backend/app/core/llm.py)) — yüklenen dosyada "önceki talimatları yoksay"
yazıyor olabilir.

---

## Proje yapısı

```
backend/app/
  config.py        Tüm ayarlar ve varsayılanları (MERCEK_ önekli)
  schemas.py       Veri sözleşmesi: hem API yanıtı hem LLM çıktı şeması
  dogrula.py       python -m app.dogrula — kurulum doğrulaması
  api/routes.py    HTTP uçları, SSE canlı akışı
  core/            parsing · gazetteer · embeddings · vectorstore · llm · sablon
  graph/           state · nodes (dört ajan) · pipeline (iki dalgalı hat)
  knowledge/       seed_data (37 kayıt) · ingest (ASVS 5.0 desteği)
backend/degerlendirme/   Kalite ölçeği: 4 test belgesi + beklenen çıktılar
frontend/src/            App · api (yeniden bağlanan SSE) · components/
```

İlk okunacak iki dosya: [`graph/pipeline.py`](backend/app/graph/pipeline.py) (akışın
iskeleti) ve [`schemas.py`](backend/app/schemas.py) (boru hattının sözleşmesi).

---

## Kalite ölçümü

```bash
cd backend
python -m degerlendirme.olcek --hizli --ozetsiz   # LLM yok, saniyeler
python -m degerlendirme.olcek                      # tam boru hattı, dakikalar
```

`temiz_*` belgeleri kişisel veri içermez; çıkan her bulgu yanlış pozitiftir.
`tuzak*` belgelerinde bildirilmesi zorunlu riskler gömülüdür; kaçan her tuzak kayıptır.
İki sayı birlikte okunmalıdır — her şeye bulgu yazan bir araç da tuzak yakalamada
yüzde yüz çıkar.

---

## Bilinen sınırlar

- **Rapor ≠ kod.** Tezler niyeti anlatır, implementasyonu değil; bu kesinlik tavanını
  yapısal olarak sınırlar.
- **Değerlendirme seti küçük.** Dört belge yön gösterir, istatistiksel iddia kurmaz.
- **Sözlük genişletilmeli.** 57 giriş çekirdek teknolojileri kapsıyor.
- **Görev kuyruğu yok.** `DEPO` sözlüğü bellekte; üretimde Redis + Celery/RQ gerekir.
- **CPU'da yavaş.** 4B modelle belge başına ~3-6 dakika.

Mercek bir denetim aracı değildir. Ürettiği maddeler doğrulanması gereken noktalardır;
güvenlik denetimi, sızma testi veya hukuki danışmanlık yerine geçmez. SAST araçlarının
rakibi değil, onlardan **önce** gelen bir tamamlayıcıdır.

---

## Lisans

[MIT](LICENSE) — Copyright (c) 2026 cgrayd

Bilgi tabanındaki metinler kendi lisanslarına tabidir (OWASP ASVS, MITRE CWE, LINDDUN,
KVKK ve GDPR mevzuatı). Tohum veri kısa alıntılar içerir; tam ASVS korpusu depoda
tutulmaz, `ingest.py --asvs` ile OWASP'tan indirilir.
