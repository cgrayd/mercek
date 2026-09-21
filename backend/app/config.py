"""Merkezi yapılandırma.

Tüm ayarlar `MERCEK_` önekli ortam değişkeninden okunur. Değerler proje
içindeki `.env` dosyasından ve ev dizinindeki ayar dosyasından gelebilir;
ikisinde de tanımlıysa ev dizinindeki geçerlidir.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    kb_collection: str = "mercek_bilgi_tabani"   # standartlar ve sağlayıcı notları

    # --- Gömme (BGE-M3) ---
    embed_model: str = "BAAI/bge-m3"
    embed_device: str = "cpu"                    # ayrık GPU varsa "cuda"
    embed_dim: int = 1024
    embed_max_length: int = 2048

    # --- Hugging Face Hub ---
    # BGE-M3 herkese açık bir model; token yalnızca indirme kotasını yükseltir.
    hf_token: str | None = None
    # true iken huggingface_hub açılışta sürüm kontrolü yapmaz; model
    # yalnızca yerel önbellekten okunur. Model indirildikten sonra
    # açılıştaki ağ beklemesini kaldırır.
    hf_offline: bool = False
    hf_home: str | None = None                   # boş = işletim sistemi varsayılanı

    # Aşağıdaki üç ayar bir takımdır ve birlikte değişir:
    # `llm_max_token`, `cikarim_bolum_basi`, `analiz_olgu_basi`.
    #
    #   yerel profil (Ollama, küçük model) : 2000 / 4 / 4
    #   uzak profil  (API, büyük model)    : 4000 / 8 / 8
    #
    # Yerelde maliyet süredir ve küçük model uzun istemde olgu kaçırır;
    # uzakta maliyet istek sayısıdır. Dosyadaki değerler uzak profile göre
    # ayarlıdır. Yerele dönerken üçü birden geri alınmalıdır.
    #
    # Uç noktayı değiştirmek için ev dizinindeki ayar dosyasının adını
    # değiştirmek yeterlidir; kalan ayarlar varsayılana (localhost:11434,
    # Ollama dalı) döner.

    # --- LLM (OpenAI uyumlu uç nokta: Ollama, vLLM, LM Studio, OpenRouter) ---
    llm_base_url: str = "http://localhost:11434/v1"
    # SecretStr: değer log'a, traceback'e veya repr'a basılmaz. Açık değere
    # yalnızca llm.py'deki Authorization başlığında çevrilir.
    llm_api_key: SecretStr = SecretStr("yerel")
    llm_model: str = "qwen3.5:4b"
    llm_temperature: float = 0.1
    # Okuma başına zaman aşımı. Ollama üretim bitene kadar veri
    # göndermediği için yerelde yüksek tutulur.
    llm_timeout: int = 900
    # Uzak uç için toplam süre sınırı; yerel yolu etkilemez. `llm_timeout`
    # okuma başına işlediğinden, bağlantıyı açık tutmak için aralıklı bayt
    # gönderen bir sağlayıcıda o sayaç sürekli sıfırlanır ve üst sınır
    # kalmaz. Yalnızca uç nokta localhost değilse okunur.
    llm_uzak_zaman_siniri: int = 240
    # Akıl yürütme modu. Qwen3.x ve DeepSeek-R1 gibi modellerde Ollama
    # bunu varsayılan olarak açar ve çağrı başına ~1000 token ek yük biner.
    llm_dusunme: bool = False
    # Ollama tespit edilirse yerel /api/chat ucunu kullanır. Tespit yalnızca
    # localhost adreslerinde çalışır; uzak sağlayıcıların adresi de /v1 ile
    # bittiği için son ek tek başına yeterli değildir.
    llm_ollama_yerel: bool = True
    # Yapısal çıktı "strict" modu. OpenRouter'da `provider.require_parameters`
    # ile birlikte çalışır (bkz. llm.py). Sağlayıcı strict şemayı 400 ile
    # reddediyorsa false yapılır; şema o zaman isteme metin olarak gömülür.
    llm_strict_sema: bool = True
    # true iken model adı ":free" ile bitmiyorsa istemci açılışta hata verir
    # ve tek bir çağrı gitmez. Yerel modeller ":free" ile bitmediği için
    # varsayılan kapalı.
    llm_sadece_ucretsiz: bool = False
    # Model bellekte ne kadar kalsın. Ollama varsayılanı 5 dakika; çağrılar
    # arasında model boşaltılırsa her seferinde diskten okunur.
    llm_keep_alive: str = "30m"
    llm_num_ctx: int = 8192
    # Üretim tavanı. Asıl uzunluk sınırı şemadaki `max_length`; bu değer
    # yalnızca kaçak üretimi keser ve şemanın üretebileceği en uzun geçerli
    # çıktının üstünde tutulmalıdır.
    llm_max_token: int = 4000
    # Akıl yürütmenin açık olacağı düğümler, virgülle. Boş = hiçbir yerde.
    # Yargı gerektiren düğümler "analiz" ve "dogrula"dır; diğerleri
    # sınıflandırma ve dönüştürme işi yapar.
    dusunen_dugumler: str = ""

    def dusunuyor_mu(self, dugum: str) -> bool:
        """Bu dugum akil yurutme modunu kullansin mi?"""
        if self.llm_dusunme:
            return True
        return dugum in {p.strip() for p in self.dusunen_dugumler.split(",") if p.strip()}

    # --- Getirme ---
    retrieval_top_k: int = 6
    # Yoğun ön-çekime uygulanan kosinüs eşiği. Füzyondan önce uygulanır:
    # RRF skoru sıra tabanlıdır, benzerlik değil, dolayısıyla füzyondan
    # sonra konan bir eşik alakasız kaydı eleyemez. Bilgi tabanı büyürse
    # eşiğin yeniden ölçülmesi gerekir.
    retrieval_benzerlik_esigi: float = 0.50
    kanit_basi_ust_sinir: int = 3
    # Bir kanıt olguların en fazla yüzde kaçına dayanak olabilir. Bu oranın
    # üstüne çıkan kayıt ayırt edici sayılmaz ve fazlası bırakılır.
    kanit_yayginlik_orani: float = 0.10
    max_retrieval_rounds: int = 3        # sorgu yeniden yazma turu
    max_upload_mb: int = 25

    # --- Boru hattı davranışı ---
    # Gömme modeli sunucu açılırken yüklensin mi? Açık: sunucu geç açılır
    # ama ilk analiz hızlı başlar.
    baslangicta_yukle: bool = True

    # Çıkarım tek seferde kaç bölüm okusun (bkz. yukarıdaki profil notu).
    cikarim_bolum_basi: int = 8
    # Çıkarım üst sınırı: analizin süresini belge boyutundan bağımsız kılar.
    # Bölümler teknik yoğunluğa göre sıralanır ve yalnızca ilk N çağrılık
    # kısmı LLM'e gider. Determinist sözlük taraması her bölümde çalışmayı
    # sürdürdüğü için bilinen teknolojiler kaçmaz.
    cikarim_max_cagri: int = 4
    # Soru işaretleri için belge geneli üst sınır. İstemdeki "en fazla 5"
    # kuralı çağrı başına işler; bu değer tüm koşum için geçerlidir.
    soru_isareti_ust_sinir: int = 8
    cikarim_bolum_karakter: int = 2500

    # Doğrulayıcının LLM adımı. Makine kontrolü (boş dayanak, uydurma atıf)
    # bundan bağımsızdır ve her zaman çalışır.
    dogrulama_llm: bool = True
    # Toplu mod: tek çağrıda tüm bulgular. Kapalıyken bulgu başına ayrı
    # çağrı yapılır; daha titizdir ama bulgu sayısı kadar istek demektir.
    dogrulama_toplu: bool = True

    # Analist tek çağrıda kaç olgu işlesin (bkz. yukarıdaki profil notu).
    analiz_olgu_basi: int = 8
    # Kaç olgu analiste gitsin. `analiz_olgu_basi` değerini aşmamalıdır;
    # aştığı anda fazladan bir LLM çağrısı açılır. Çıktı sayısı şemayla
    # sınırlı olduğu için bu değer bulgu sayısını değil, modelin seçim
    # yaptığı havuzu büyütür.
    analiz_llm_bulgu_sayisi: int = 8
    # LLM'in bulduğu olgu sözlükteki bir teknolojiye aitse bulgu şablonla
    # kurulur, analiste gönderilmez.
    sablon_akis_kapsami: bool = True

    # Arka arkaya kaç sağlayıcı hatasından sonra bu koşumda LLM çağrıları
    # dursun. Determinist bulgular dalga 1'de yayınlandığı için kesici
    # devreye girdiğinde çıktı kaybolmaz.
    devre_kesici_esigi: int = 3
    # Aynı anda gönderilecek bağımsız LLM yığını sayısı. CPU'da kazanç
    # düşüktür, llama.cpp tek istekte bellek bant genişliğini doyurur;
    # ayrık GPU'da anlamlı olur. 1 = kapalı.
    llm_es_zamanli: int = 1

    # --- API ---
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        # İki konum okunur, sonuncusu geçerlidir. Gerçek API anahtarı ev
        # dizinindeki dosyada tutulur; orası depo ağacının dışındadır.
        env_file = (".env", str(Path.home() / ".mercek" / "mercek.env"))
        env_prefix = "MERCEK_"
        # Artık kullanılmayan bir anahtar eski bir ayar dosyasında kalmışsa
        # sunucuyu açılışta durdurmasın, yok sayılsın.
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
