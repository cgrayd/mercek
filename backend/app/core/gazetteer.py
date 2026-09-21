"""Determinist teknoloji sozlugu.

LLM cikariminin geri cagirma garantisi yoktur; bu modul onu saglar:
sozlukte kayitli hicbir teknoloji kacmaz. LLM katmani bunun uzerine
calisir.

Sozluk genisletilebilir; her giris ad, kategori, veri ikametgahi ve
esanlamlilardan olusur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TeknolojiGirisi:
    ad: str
    kategori: str
    # Verinin nerede durdugu: "harici" olanlar veri sizintisi analizini tetikler
    veri_ikametgahi: str  # yerel | harici | degisken
    esanlamli: tuple[str, ...] = field(default_factory=tuple)
    not_: str = ""


# Asagidaki cekirdek set tez ve proje raporlarinda en sik gecen
# teknolojileri kapsar; uretim icin genisletilmesi gerekir.
SOZLUK: list[TeknolojiGirisi] = [
    # --- Barindirilan veritabani / BaaS (harici) ---
    TeknolojiGirisi("Firebase", "baas", "harici",
                    ("firebase", "firestore", "firebase realtime database"),
                    "Google altyapisinda barinir; veri ikametgahi proje ayarina bagli"),
    TeknolojiGirisi("Supabase", "baas", "harici", ("supabase",)),
    # Tek basina "atlas" esanlamlisi yok: Turkcede siradan bir kelime
    # ("harita atlasi") ve yanlis pozitif uretiyor.
    TeknolojiGirisi("MongoDB Atlas", "veritabani", "harici", ("mongodb atlas",)),
    TeknolojiGirisi("AWS S3", "depolama", "harici", ("s3", "amazon s3", "aws s3")),
    TeknolojiGirisi("Google Cloud Storage", "depolama", "harici", ("gcs", "cloud storage")),
    TeknolojiGirisi("Azure Blob Storage", "depolama", "harici", ("azure blob",)),
    TeknolojiGirisi("Cloudinary", "medya", "harici", ("cloudinary",)),

    # --- LLM / ML servisleri (harici, prompt icerigi disari cikar) ---
    TeknolojiGirisi("OpenAI API", "llm", "harici",
                    ("openai", "gpt-4", "gpt-4o", "chatgpt api", "gpt-3.5"),
                    "Istem ve yanit icerigi saglayici sunucularinda islenir"),
    TeknolojiGirisi("Anthropic API", "llm", "harici", ("anthropic", "claude api")),
    TeknolojiGirisi("Google Gemini API", "llm", "harici", ("gemini api", "vertex ai")),
    TeknolojiGirisi("Hugging Face Inference", "llm", "harici",
                    ("huggingface inference", "hf inference api")),
    TeknolojiGirisi("Ollama", "llm", "yerel", ("ollama",)),
    TeknolojiGirisi("vLLM", "llm", "yerel", ("vllm",)),
    TeknolojiGirisi("llama.cpp", "llm", "yerel", ("llama.cpp", "llamacpp", "gguf")),

    # --- Analitik / telemetri (harici, cogu tezde farkinda olmadan gecer) ---
    TeknolojiGirisi("Google Analytics", "analitik", "harici", ("google analytics", "ga4")),
    TeknolojiGirisi("Firebase Analytics", "analitik", "harici", ("firebase analytics",)),
    TeknolojiGirisi("Sentry", "izleme", "harici", ("sentry",),
                    "Hata yakalama araclari istek govdesini de gonderebilir"),
    TeknolojiGirisi("Mixpanel", "analitik", "harici", ("mixpanel",)),
    # Gunluk aktarimi, istek govdesindeki kisisel veriyi ucuncu tarafa
    # tasiyan yollardan biri.
    TeknolojiGirisi("Datadog", "izleme", "harici", ("datadog",),
                    "Gunluk/APM aktarimi istek govdesindeki kisisel veriyi tasiyabilir"),
    TeknolojiGirisi("New Relic", "izleme", "harici", ("new relic", "newrelic")),
    TeknolojiGirisi("Grafana Loki", "izleme", "degisken", ("grafana loki", "loki")),

    # --- Iletisim / odeme (harici, kisisel veri tasir) ---
    TeknolojiGirisi("Twilio", "iletisim", "harici", ("twilio",)),
    TeknolojiGirisi("SendGrid", "iletisim", "harici", ("sendgrid",)),
    TeknolojiGirisi("Stripe", "odeme", "harici", ("stripe",)),
    TeknolojiGirisi("iyzico", "odeme", "harici", ("iyzico",)),
    TeknolojiGirisi("PayTR", "odeme", "harici", ("paytr",)),
    TeknolojiGirisi("Firebase Cloud Messaging", "bildirim", "harici",
                    ("fcm", "cloud messaging", "push notification")),

    # --- Kimlik dogrulama ---
    TeknolojiGirisi("Auth0", "kimlik", "harici", ("auth0",)),
    TeknolojiGirisi("Keycloak", "kimlik", "yerel", ("keycloak",)),
    TeknolojiGirisi("JWT", "kimlik", "degisken", ("jwt", "json web token")),
    TeknolojiGirisi("OAuth 2.0", "kimlik", "degisken", ("oauth", "oauth2", "oauth 2.0")),
    TeknolojiGirisi("Google ile Giris", "kimlik", "harici",
                    ("google sign-in", "google ile giris", "sign in with google")),

    # --- Yerel veritabanlari ---
    TeknolojiGirisi("PostgreSQL", "veritabani", "yerel", ("postgres", "postgresql")),
    TeknolojiGirisi("MySQL", "veritabani", "yerel", ("mysql", "mariadb")),
    TeknolojiGirisi("SQLite", "veritabani", "yerel", ("sqlite",)),
    TeknolojiGirisi("Redis", "onbellek", "yerel", ("redis",)),
    TeknolojiGirisi("Qdrant", "vektor", "yerel", ("qdrant",)),
    TeknolojiGirisi("Pinecone", "vektor", "harici", ("pinecone",)),
    TeknolojiGirisi("Elasticsearch", "arama", "degisken", ("elasticsearch", "opensearch")),

    # --- Cerceve / calisma zamani ---
    TeknolojiGirisi("FastAPI", "cerceve", "yerel", ("fastapi",)),
    TeknolojiGirisi("Django", "cerceve", "yerel", ("django",)),
    TeknolojiGirisi("Flask", "cerceve", "yerel", ("flask",)),
    TeknolojiGirisi("Spring Boot", "cerceve", "yerel", ("spring boot",)),
    TeknolojiGirisi("Node.js", "cerceve", "yerel", ("node.js", "nodejs", "express.js")),
    TeknolojiGirisi("React", "arayuz", "yerel", ("react", "react.js")),
    TeknolojiGirisi("React Native", "mobil", "yerel", ("react native",)),
    TeknolojiGirisi("Flutter", "mobil", "yerel", ("flutter",)),

    # --- Dagitim ---
    TeknolojiGirisi("Docker", "dagitim", "yerel", ("docker", "dockerfile")),
    TeknolojiGirisi("Kubernetes", "dagitim", "yerel", ("kubernetes", "k8s")),
    TeknolojiGirisi("Vercel", "dagitim", "harici", ("vercel",)),
    TeknolojiGirisi("Heroku", "dagitim", "harici", ("heroku",)),
    TeknolojiGirisi("Netlify", "dagitim", "harici", ("netlify",)),
    TeknolojiGirisi("Cloudflare", "cdn", "harici", ("cloudflare",)),

    # --- Cihaz / sensor (mahremiyet acisindan yuksek riskli) ---
    TeknolojiGirisi("Kamera erisimi", "sensor", "yerel",
                    ("kamera", "camera api", "opencv", "webcam")),
    TeknolojiGirisi("Konum servisi", "sensor", "degisken",
                    ("gps", "konum", "geolocation", "location service")),
    TeknolojiGirisi("Mikrofon erisimi", "sensor", "yerel",
                    ("mikrofon", "microphone", "ses kaydi")),
    TeknolojiGirisi("Biyometrik dogrulama", "sensor", "yerel",
                    ("parmak izi", "yuz tanima", "face recognition", "biyometrik")),
]


# ---------------------------------------------------------------- veri turleri

# KVKK m.6 ozel nitelikli kisisel veri ve genel kisisel veri isaretcileri.
# Bunlarin varligi hukuki analiz kolunu tetikler.
VERI_ISARETCILERI: dict[str, tuple[str, ...]] = {
    # "alerji", "ilac" ve "kronik" de saglik verisi isaretcisidir; KVKK m.6
    # kapsamina giren bu ifadeler tibbi terim listesine takilmaz.
    "saglik_verisi": ("hasta", "teshis", "tani", "tibbi", "saglik kaydi", "recete",
                      "epikriz", "alerji", "kronik", "ilac kullan", "kullandigi ilac",
                      "patient", "diagnosis", "medical record", "allergy", "chronic"),
    "biyometrik_veri": ("parmak izi", "yuz tanima", "iris", "retina", "biyometrik",
                        "fingerprint", "face recognition", "biometric"),
    "konum_verisi": ("gps", "konum", "koordinat", "enlem", "boylam", "geolocation",
                     "latitude", "longitude"),
    "kimlik_verisi": ("tc kimlik", "t.c. kimlik", "kimlik numarasi", "tckn",
                      "pasaport", "ehliyet", "national id"),
    "finansal_veri": ("kredi karti", "iban", "hesap numarasi", "odeme bilgisi",
                      "credit card", "bank account"),
    # "ogrenci" listede yok: Turkce'de universite ogrencisini de kapsar ve
    # bu aracin girdisi ogrenci projesi raporudur, yani isaretci hedef
    # belge turunun her orneginde yanar. Cocukluk sinyali okul
    # kademesinden gelir, "ogrenci" kelimesinden degil.
    "cocuk_verisi": ("cocuk", "18 yas alti", "18 yasindan kucuk", "resit olmayan",
                     "anaokulu", "ilkokul", "ortaokul", "lise ogrencisi", "veli onayi",
                     "veli rizasi", "minor", "child", "student record"),
    "iletisim_verisi": ("e-posta", "email", "telefon numarasi", "adres bilgisi"),
}


# Normalizasyon birebir karakter eslemesi olmak zorunda: eslesme
# normalize metinde bulunur, alinti orijinal metinden kesilir. Uzunluk
# degisirse alintilar kayar. Bu yuzden NFKD kullanilmaz (birlesik
# karakterleri acar, uzunlugu degistirir) ve Turkce 'İ' ayrica ele alinir;
# Python'da "İ".lower() iki kod noktasi uretir.
_HARITA = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ğ": "g", "ğ": "g", "Ü": "u", "ü": "u",
    "Ş": "s", "ş": "s", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
    "Â": "a", "â": "a", "Î": "i", "î": "i", "Û": "u", "û": "u",
})


def _normalize(metin: str) -> str:
    """Turkce karakter farkliliklarini tolere eder, uzunlugu korur."""
    return metin.translate(_HARITA).lower()


def _cumle_al(metin: str, bas: int, son: int, pencere: int = 200) -> str:
    """Eslesmeyi iceren cumleyi orijinal metinden keser.

    Sabit genislikte bir pencere cumle ortasindan basladigi icin parca
    cumle sinirlarina hizalanir.
    """
    sol = max(0, bas - pencere)
    sag = min(len(metin), son + pencere)
    parca = metin[sol:sag]

    nokta = max(parca.rfind(". ", 0, bas - sol), parca.rfind("\n", 0, bas - sol))
    if nokta > 0:
        parca = parca[nokta + 1:]
    bitis = parca.find(". ", (son - sol) - max(0, nokta + 1))
    if bitis > 0:
        parca = parca[:bitis + 1]
    return " ".join(parca.split()).strip()


# Turkce cekim ekleri. Ciplak kelime siniri ((?![a-z0-9])) Turkce'de
# yetersiz kalir; ek almis her bicim kacar ("Cocuklarin kisisel verileri",
# "Kullanicinin konumu", "Docker'da calisir").
#
# Cozum uzunluk siniri degil ("react" + 3 harf yine "reactive" ile
# eslesirdi), acikca sayilmis cekim ekleridir: cogul -> iyelik -> hal,
# hepsi istege bagli. Turetme ekleri listede yoktur, cunku anlami
# degistirir ve yanlis pozitif uretirler:
#   konum   : "konumu/konumlari" eslesir, "konumlandirilmistir" eslesmez
#   tani    : "tanisi" eslesir,  "tanimlanmistir" eslesmez
#   cocuk   : "cocuklarin" eslesir, "cocukluk" eslesmez
#   hasta   : "hastalarin" eslesir, "hastalik" eslesmez
#   recete  : "receteler" eslesir, "recetesiz" eslesmez
#   react   : "reactive" eslesmez
# Bastaki sinir siki kalir; Turkce'de on ek yoktur.
_TR_COGUL = r"(?:l[ae]r)?"
_TR_IYELIK = r"(?:[iu]m|[iu]n|[iu]miz|[iu]niz|[sy][iu]|[iu])"
# Kaynastirma "n"si hal ekinin onune yalnizca iyelikten sonra gelir
# ("konumu-n-da", "hastasi-n-a"); iyeliksiz tek istisnasi ilgi halidir
# ("hasta-n-in"). Iyeliksiz "n+a/da/dan" Turkce cekim degildir ve o yola
# izin vermek "hastane" gibi turetilmis bicimleri eslestirir.
_TR_HAL_IYELIKLI = r"(?:n?[iu]n|n?[ae]|y[ae]|n?[dt][ae]|n?[dt][ae]n|yl[ae]|l[ae]|[iu])"
_TR_HAL = r"(?:n?[iu]n|[ae]|y[ae]|[dt][ae]|[dt][ae]n|yl[ae]|l[ae]|[iu])"
# Bastaki "'" ozel isimlerin dogru Turkce yazimi icin: "Docker'da", "Firebase'i".
_TR_EK = rf"(?:'?{_TR_COGUL}(?:{_TR_IYELIK}{_TR_HAL_IYELIKLI}?|{_TR_HAL})?)"


def _desen(ifade: str) -> re.Pattern[str]:
    """Turkce cekim eki farkindalikli desen. 'react' -> 'reactive' eslesmesin."""
    kacisli = re.escape(_normalize(ifade)).replace(r"\ ", r"[\s\-_]+")
    return re.compile(rf"(?<![a-z0-9]){kacisli}{_TR_EK}(?![a-z0-9])")


_DERLI: list[tuple[TeknolojiGirisi, list[re.Pattern[str]]]] = [
    (g, [_desen(a) for a in (g.ad, *g.esanlamli)]) for g in SOZLUK
]
_VERI_DERLI: dict[str, list[re.Pattern[str]]] = {
    tur: [_desen(i) for i in ifadeler] for tur, ifadeler in VERI_ISARETCILERI.items()
}


def teknoloji_tara(metin: str) -> list[tuple[TeknolojiGirisi, str]]:
    """Metinde gecen teknolojileri ve eslesen baglami dondurur."""
    norm = _normalize(metin)
    bulunanlar: list[tuple[TeknolojiGirisi, str]] = []
    for giris, desenler in _DERLI:
        for desen in desenler:
            m = desen.search(norm)
            if m:
                bulunanlar.append((giris, _cumle_al(metin, m.start(), m.end())))
                break
    return bulunanlar


# "Bu veriyi islemiyoruz" kaliplari. Desen eslesmesi olumsuzlamayi
# goremez; "Odeme alinmaz, kredi karti bilgisi islenmez." cumlesi aksi
# halde finansal veri islendigi sayilir.
#
# Yalnizca isleme fiillerinin olumsuzu sayilir ("islenmez", "toplanmaz"),
# guvenlik fiilleri degil: "sifrelenmeden saklanmaz" verinin varligini
# inkar etmez, dogrular.
_OLUMSUZ_ISLEME = re.compile(
    r"(?<![a-z])(islenmez|islenmiyor|islenmemekte|islenmemistir|"
    r"toplanmaz|toplanmiyor|toplanmamaktadir|toplanmamistir|"
    r"tutulmaz|tutulmuyor|tutulmamaktadir|"
    r"kaydedilmez|kaydedilmiyor|"
    r"istenmez|istenmiyor|alinmaz|alinmiyor|"
    r"icermez|icermiyor|bulunmaz|bulunmuyor|yoktur)(?![a-z])"
)

# Olumsuzlama ile eslesme arasindaki azami mesafe (karakter). Dar tutulur;
# ayni cumlede ama uzaktaki bir "yoktur" baska bir ifadeye ait olabilir.
_OLUMSUZ_MESAFE = 60


def _olumsuzlanmis_mi(cumle: str, konum: int) -> bool:
    """Eslesme "bu veriyi islemiyoruz" diyen bir cumlede mi gecmis?"""
    kuyruk = _normalize(cumle[konum:konum + _OLUMSUZ_MESAFE])
    return bool(_OLUMSUZ_ISLEME.search(kuyruk))


def veri_turu_tara(metin: str) -> list[tuple[str, str]]:
    """Metinde gecen hassas veri turlerini dondurur.

    Islenmedigi acikca soylenen eslesmeler sayilmaz; bkz. _OLUMSUZ_ISLEME.
    Bir desen belgede birden cok kez geciyorsa hepsi denenir: bir yerde
    olumsuzlanmis olmasi, baska bir yerde islendigini dislamaz.
    """
    norm = _normalize(metin)
    bulunanlar: list[tuple[str, str]] = []
    for tur, desenler in _VERI_DERLI.items():
        for desen in desenler:
            for m in desen.finditer(norm):
                cumle = _cumle_al(metin, m.start(), m.end())
                yer = _normalize(cumle).find(_normalize(metin[m.start():m.end()]))
                if _olumsuzlanmis_mi(cumle, yer if yer >= 0 else 0):
                    continue
                bulunanlar.append((tur, cumle))
                break
            else:
                continue
            break
    return bulunanlar


# ---------------------------------------------------------------- arama


_AD_HARITASI: dict[str, TeknolojiGirisi] = {g.ad: g for g in SOZLUK}


def giris_bul(ad: str) -> TeknolojiGirisi | None:
    """Teknoloji adindan sozluk girisini dondurur.

    Sablon motoru bulguyu kurarken girisin `kategori`, `veri_ikametgahi`
    ve `not_` alanlarina ihtiyac duyuyor; olgu uzerinde yalnizca ad var.
    """
    return _AD_HARITASI.get(ad)


def alinti_cikar(metin: str, ifade: str) -> str:
    """Metinde `ifade`nin gectigi cumleyi dondurur; yoksa bos string.

    Alinti belgede zaten var olan bir metin oldugu icin modele
    kopyalatilmaz. Determinist kesme hem ucuzdur hem de alintinin gercekten
    belgede gectigini garanti eder.
    """
    if not ifade:
        return ""
    norm_metin = _normalize(metin)
    norm_ifade = _normalize(ifade)
    yer = norm_metin.find(norm_ifade)
    if yer < 0:
        # Tam ifade bulunamadi; ilk kelimesiyle dene.
        ilk = norm_ifade.split()[0] if norm_ifade.split() else ""
        if len(ilk) < 3:
            return ""
        yer = norm_metin.find(ilk)
        if yer < 0:
            return ""
        return _cumle_al(metin, yer, yer + len(ilk))
    return _cumle_al(metin, yer, yer + len(norm_ifade))
