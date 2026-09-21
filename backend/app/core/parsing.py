"""Bolum farkindalikli belge ayristirma.

Tezler duz metin degildir: baslik hiyerarsisi, icindekiler, sekil altlari
ve kod bloklari icerir. Sabit boyutlu chunk'lama bu yapiyi kaybeder ve
"3.2 Veri Katmani" bolumundeki bir cumleyi literatur taramasindan gelen
bir cumleyle ayni agirlikta gosterir. Bu yuzden belge bolumlere ayrilir
ve her bolum kendi basligini tasir.
"""

from __future__ import annotations

import re
from io import BytesIO

from app.core.gazetteer import _normalize
from app.schemas import Bolum

# Tez basliklarini yakalayan desenler (Turkce ve Ingilizce). Bolum
# numarasi kademe basina en fazla iki hanelidir; boylece "2024 yilinda"
# veya "34.000 ogrenci" ile baslayan cumleler baslik sayilmaz.
_NUMARALI = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([^\n]{3,90})$")
_BUYUK_HARF = re.compile(r"^\s*([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s]{4,60})\s*$")

# Analiz degeri dusuk bolumler; yonlendirme dugumu bunlari atlar.
# Anahtarlar normalize (ASCII) yazilir, baslik da normalize edilip aranir.
_DUSUK_DEGER = (
    "icindekiler", "contents", "kaynakca", "references", "bibliography",
    "tesekkur", "ozgecmis", "onsoz", "sekiller listesi", "tablolar listesi",
    "kisaltmalar", "abstract", "ozet", "literatur taramasi", "literature review",
    # Sonuc ve bulgu bolumleri: sistemin nasil kuruldugunu degil, ne kadar
    # iyi calistigini anlatirlar ve risk analizine girdi vermezler.
    "test sonuc", "bulgular", "basari", "dogruluk", "performans degerlendirme",
    "metrik", "tartisma", "gelecek calisma", "sonuc ve oneriler",
)
# Dusuk deger anahtarlari kelime basinda aranir. Alt dizge aramasi
# "metrik" anahtarini "Biyometrik Dogrulama" basliginda da bulur ve bolum
# sozluk taramasindan cikar. `hayir` karari geri alinamadigi icin eslesme
# siki tutulur.
_DUSUK_DESEN = re.compile(r"(?<![a-z0-9])(?:" + "|".join(map(re.escape, _DUSUK_DEGER)) + ")")

# Analiz degeri yuksek bolumler. Bunlar her zaman derin analize girer.
_YUKSEK_DEGER = (
    "yontem", "method", "mimari", "architecture", "tasarim", "design",
    "uygulama", "implementation", "sistem", "system", "veri", "data",
    "guvenlik", "security", "test", "altyapi", "infrastructure",
    "gereksinim", "requirement", "materyal",
)


def _pdf_metni(icerik: bytes) -> list[tuple[int, str]]:
    """PyMuPDF ile sayfa sayfa metin. (sayfa_no, metin) dondurur."""
    # `fitz` adi kullanimdan kalkiyor; once yeni ad denenir.
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf

    sayfalar: list[tuple[int, str]] = []
    with pymupdf.open(stream=icerik, filetype="pdf") as belge:
        for i, sayfa in enumerate(belge, start=1):
            sayfalar.append((i, sayfa.get_text("text")))
    return sayfalar


def _docx_metni(icerik: bytes) -> list[tuple[int, str]]:
    """python-docx ile paragraf akisi. Stil adindan baslik seviyesi cikarilir."""
    from docx import Document

    belge = Document(BytesIO(icerik))
    parcalar: list[str] = []
    for p in belge.paragraphs:
        metin = p.text.strip()
        if not metin:
            continue
        stil = (p.style.name or "").lower()
        if stil.startswith("heading"):
            seviye = "".join(c for c in stil if c.isdigit()) or "1"
            parcalar.append(f"\n{'#' * int(seviye)} {metin}\n")
        else:
            parcalar.append(metin)
    return [(1, "\n".join(parcalar))]


def _baslik_mi(satir: str) -> tuple[bool, int, str]:
    """Satir bir baslik mi? (evet_mi, seviye, temiz_baslik)."""
    satir = satir.rstrip()
    if not satir or len(satir) > 100:
        return False, 0, ""

    if satir.startswith("#"):
        seviye = len(satir) - len(satir.lstrip("#"))
        return True, min(seviye, 4), satir.lstrip("# ").strip()

    m = _NUMARALI.match(satir)
    # Numarali liste maddesi baslik degildir: "1. Parolalar MD5 ile
    # saklanir." baslik sayilirsa metni hicbir bolume girmez. Baslik
    # noktalamayla bitmez ve kucuk harfle baslamaz.
    if m and not m.group(2)[0].islower() and m.group(2).rstrip()[-1] not in ".,;:!?":
        return True, m.group(1).count(".") + 1, f"{m.group(1)} {m.group(2)}".strip()

    m = _BUYUK_HARF.match(satir)
    if m and len(satir.split()) <= 8:
        # `title()` Turkce buyuk "İ" harfini "i" + birlesik nokta (U+0307)
        # yapar; olusan birlesik nokta temizlenir.
        return True, 1, m.group(1).strip().title().replace("̇", "")

    return False, 0, ""


def _bolum_karari(baslik: str) -> str:
    """Bolum derin analize girsin mi? evet | hayir | belirsiz.

    Bir tezde basliklarin cogu iki listeye de uymaz; bilinmeyen baslik
    otomatik dahil edilmez, `belirsiz` isaretlenir ve yonlendirme
    dugumunde gomme karsilastirmasiyla ayiklanir.

    Normalizasyon Turkce harfleri esitler; Python'da "İ".lower() iki kod
    noktasi urettigi icin bu adim olmadan "İÇİNDEKİLER" eslesmez.
    """
    alt = _normalize(baslik).replace("̇", "")
    if _DUSUK_DESEN.search(alt):
        return "hayir"
    if any(k in alt for k in _YUKSEK_DEGER):
        return "evet"
    return "belirsiz"


def _metni_coz(icerik: bytes) -> str:
    """Duz metni BOM'a bakarak cozer.

    Windows'ta Not Defteri ile kaydedilen .txt dosyalari sik sik UTF-16
    olur. Kosulsuz utf-8 varsayimiyla cozuldugunde metin anlamsizlasir,
    belge tek bolum sayilir ve tarama hicbir sey bulamaz.
    """
    for bom, kodlama in (
        (bytes((0xFF, 0xFE)), "utf-16"),
        (bytes((0xFE, 0xFF)), "utf-16"),
        (bytes((0xEF, 0xBB, 0xBF)), "utf-8-sig"),
    ):
        if icerik.startswith(bom):
            try:
                return icerik.decode(kodlama)
            except UnicodeDecodeError:
                break
    return icerik.decode("utf-8", errors="replace")


def bolumlere_ayir(icerik: bytes, dosya_adi: str) -> list[Bolum]:
    """Belgeyi bolum listesine cevirir."""
    ad = dosya_adi.lower()
    if ad.endswith(".pdf"):
        sayfalar = _pdf_metni(icerik)
    elif ad.endswith((".docx", ".doc")):
        sayfalar = _docx_metni(icerik)
    elif ad.endswith((".txt", ".md")):
        sayfalar = [(1, _metni_coz(icerik))]
    else:
        raise ValueError(f"Desteklenmeyen dosya turu: {dosya_adi}")

    bolumler: list[Bolum] = []
    aktif_baslik = "Giris"
    aktif_seviye = 1
    aktif_sayfa = 1
    tampon: list[str] = []
    sayac = 0

    def kapat() -> None:
        nonlocal tampon, sayac
        metin = "\n".join(tampon).strip()
        # Yalnizca anlamli kelimesi olmayan bolum atilir (basliktan ibaret
        # bolum, sayfa numarasi). Uzunluk tek olcut olsaydi "4.3 Veritabani
        # / Firebase kullanilir." gibi kisa ama gercek bolumler duserdi.
        if len(metin) < 40 and not re.search(r"[^\W\d_]{3,}", metin):
            tampon = []
            return
        sayac += 1
        bolumler.append(
            Bolum(
                bolum_id=f"b{sayac:03d}",
                baslik=aktif_baslik,
                seviye=aktif_seviye,
                metin=metin,
                sayfa_baslangic=aktif_sayfa,
                karar=_bolum_karari(aktif_baslik),
            )
        )
        tampon = []

    for sayfa_no, sayfa_metni in sayfalar:
        for satir in sayfa_metni.splitlines():
            evet, seviye, temiz = _baslik_mi(satir)
            if evet:
                kapat()
                aktif_baslik, aktif_seviye, aktif_sayfa = temiz, seviye, sayfa_no
            else:
                tampon.append(satir)
    kapat()

    return bolumler or [
        Bolum(
            bolum_id="b001",
            baslik="Belge",
            metin="\n".join(m for _, m in sayfalar).strip(),
            sayfa_baslangic=1,
        )
    ]
