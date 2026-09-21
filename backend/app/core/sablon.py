"""Determinist bulgu kurucu.

Sozlukten gelen olgular icin bulgu LLM'e ugramadan burada kurulur: uretim
maliyeti yoktur, ayni belge ayni bulguyu verir ve kaynak metni bilgi
tabanindan oldugu gibi geldigi icin uydurma olusmaz. Sozlukte olmayan
olgular `analiz` dugumune gider.
"""

from __future__ import annotations

import re
import uuid

from app.config import get_settings
from app.core.gazetteer import giris_bul, teknoloji_tara
from app.schemas import Bulgu, Kanit, Kesinlik, Olgu, OlguTuru, RiskAlani

# Sablonun devralabilecegi LLM olgu turleri: bir bilesenin veri
# alisverisini anlatan, mekanik olarak tarif edilebilir olgular.
# `veri_turu` ve `eksik_bilgi` disaridadir; ilki hukuki yorum, ikincisi
# bir yokluktur.
_AKIS_TURLERI = frozenset({
    OlguTuru.VERI_AKISI,
    OlguTuru.KIMLIK_DOGRULAMA,
    OlguTuru.DAGITIM,
    OlguTuru.TEKNOLOJI,
})

# Teknoloji kategorisi -> risk alani. Veri ikametgahi "harici" ise alan
# VERI_SIZINTISI'na kayabilir; bunu asagida `_alan` degerlendirir.
_KATEGORI_ALAN: dict[str, RiskAlani] = {
    "baas": RiskAlani.VERI_SIZINTISI,
    "veritabani": RiskAlani.GUVENLIK,
    "depolama": RiskAlani.VERI_SIZINTISI,
    "medya": RiskAlani.VERI_SIZINTISI,
    "llm": RiskAlani.VERI_SIZINTISI,
    "analitik": RiskAlani.VERI_SIZINTISI,
    "izleme": RiskAlani.VERI_SIZINTISI,
    "iletisim": RiskAlani.VERI_SIZINTISI,
    "odeme": RiskAlani.HUKUKI,
    "bildirim": RiskAlani.VERI_SIZINTISI,
    "kimlik": RiskAlani.GUVENLIK,
    "onbellek": RiskAlani.GUVENLIK,
    "vektor": RiskAlani.VERI_SIZINTISI,
    "arama": RiskAlani.GUVENLIK,
    "cerceve": RiskAlani.GUVENLIK,
    "arayuz": RiskAlani.GUVENLIK,
    "mobil": RiskAlani.GUVENLIK,
    "dagitim": RiskAlani.GUVENLIK,
    "cdn": RiskAlani.GUVENLIK,
    "sensor": RiskAlani.VERI_SIZINTISI,
}

# Kategori -> kullaniciya sorulacak tek kontrol sorusu.
_KATEGORI_KONTROL: dict[str, str] = {
    "baas": "Veri bolgesi hangi ulkede secildi ve guvenlik kurallari kimin "
            "erisimine acik?",
    "veritabani": "Veritabani erisimi hangi kimlik dogrulama ile korunuyor ve "
                  "yedekler nerede tutuluyor?",
    "depolama": "Depolama alani herkese acik mi, yoksa imzali/sureli erisim mi "
                "kullaniliyor?",
    "medya": "Yuklenen medya dosyalarina erisim nasil sinirlandiriliyor?",
    "llm": "Saglayiciya gonderilen istemlerde kisisel veri bulunuyor mu ve "
           "egitim amacli kullanim kapali mi?",
    "analitik": "Toplanan olay verisi kisiyi tanimliyor mu ve kullanicidan "
                "acik riza aliniyor mu?",
    "izleme": "Hata kayitlarinda kisisel veri veya kimlik bilgisi yer aliyor mu?",
    "iletisim": "Gonderilen mesaj icerigi ve alici listesi saglayicida ne kadar "
                "sure saklaniyor?",
    "odeme": "Kart verisi sisteminize hic ugramiyor mu, dogrudan saglayiciya mi "
             "gidiyor?",
    "bildirim": "Bildirim govdesinde kisisel veri tasiniyor mu?",
    "kimlik": "Oturum sureleri, parola politikasi ve yetki kontrolu nasil "
              "yapilandirildi?",
    "onbellek": "Onbellekte kisisel veri tutuluyor mu ve erisimi kimler acik?",
    "vektor": "Vektor veritabanina yazilan metin parcalarinda kisisel veri var mi?",
    "arama": "Arama indeksine yazilan alanlar arasinda kisisel veri bulunuyor mu?",
    "cerceve": "Bagimliliklarin surumleri guncel mi ve bilinen zafiyet taramasi "
               "yapiliyor mu?",
    "arayuz": "Istemci tarafinda saklanan veriler ve API anahtarlari nasil "
              "korunuyor?",
    "mobil": "Cihazda saklanan veriler sifreleniyor mu?",
    "dagitim": "Ortam degiskenleri ve gizli anahtarlar dagitim ortaminda nasil "
               "yonetiliyor?",
    "cdn": "Onbelleklenen icerikte yetkilendirme gerektiren veri var mi?",
    "sensor": "Sensor verisi kisiyi tanimlanabilir kiliyor mu ve rizasi alindi mi?",
}

# Hassas veri turu -> (okunabilir ad, kontrol sorusu)
_VERI_TURU_METNI: dict[str, tuple[str, str]] = {
    "saglik_verisi": ("saglik verisi",
                      "Ozel nitelikli veri icin ayrica acik riza aliniyor mu ve "
                      "erisim kayitlari tutuluyor mu?"),
    "biyometrik_veri": ("biyometrik veri",
                        "Biyometrik sablon cihazda mi tutuluyor, sunucuya "
                        "gonderiliyor mu?"),
    "konum_verisi": ("konum verisi",
                     "Konum hangi sikllikta toplaniyor ve ne kadar sure "
                     "saklaniyor?"),
    "kimlik_verisi": ("kimlik verisi",
                      "Kimlik numarasi gercekten gerekli mi, saklaniyorsa "
                      "sifreleniyor mu?"),
    "finansal_veri": ("finansal veri",
                      "Odeme verisi sizin sisteminizde tutuluyor mu?"),
    "cocuk_verisi": ("cocuk verisi",
                     "Veli rizasi mekanizmasi var mi ve yas dogrulamasi "
                     "yapiliyor mu?"),
    "iletisim_verisi": ("iletisim verisi",
                        "Iletisim bilgisi pazarlama amaciyla kullaniliyorsa "
                        "ayri riza aliniyor mu?"),
}

_IKAMETGAH_METNI = {
    "harici": "Veri saglayicinin altyapisinda islenir, yani projenizin disina cikar.",
    "yerel": "Veri kendi altyapinizda kalir.",
    "degisken": "Verinin nerede tutuldugu yapilandirmaya bagli degisir.",
}


def _alan(kategori: str, ikametgah: str) -> RiskAlani:
    taban = _KATEGORI_ALAN.get(kategori, RiskAlani.GUVENLIK)
    # Yerel calisan bir bilesende "veri sizintisi" demek yaniltici olur.
    if ikametgah == "yerel" and taban is RiskAlani.VERI_SIZINTISI:
        return RiskAlani.GUVENLIK
    return taban


# Bulgu aciklamasina metni oldugu gibi konabilecek kaynaklar.
#
# Sablon ceviri yapmaz, yalnizca metni kopyalar; Ingilizce ASVS metni
# Turkce bir aciklamanin icine girdiginde cikti okunmaz olur. Ingilizce
# standardin metni bulguya girmez, kanit cipinde tam haliyle durur ve
# kullanici tiklayinca baglaminda okur.
#
# Turkce kaynaklar (saglayici notlari, KVKK maddeleri) girebilir; onlar
# bu proje icin Turkce yazilmistir ve cumleye dogal oturur.
_TURKCE_KAYNAKLAR = frozenset({"saglayici", "kvkk"})


def _kirp(metin: str, sinir: int = 300) -> str:
    """Kaynak metnini cumle sinirinda kirpar, kelime ortasinda degil."""
    # ingest, ASVS metnine "[Bolum Adi] " oneki ekler; bulguda gorunmez.
    metin = re.sub(r"^\[[^\]]{0,60}\]\s*", "", " ".join(metin.split()))
    if len(metin) <= sinir:
        return metin
    kesik = metin[:sinir]
    nokta = kesik.rfind(". ")
    if nokta > 60:
        return kesik[: nokta + 1]
    bosluk = kesik.rfind(" ")
    return (kesik[:bosluk] if bosluk > 60 else kesik).rstrip(" ,;:") + "..."


def _kaynak_cumlesi(kanitlar: list[Kanit], sinir: int = 300) -> str:
    """Aciklamaya konabilecek Turkce kaynak metni; yoksa bos."""
    for k in kanitlar:
        if k.kaynak_turu in _TURKCE_KAYNAKLAR:
            return _kirp(k.ozet, sinir)
    return ""


def gurultu_mu(olgu: Olgu) -> bool:
    """Bu olgu bulgu uretmemeli mi?

    Cerceve, arayuz ve mobil kategorisindeki yerel bilesenler elenir;
    "React kullaniyorsunuz" her React projesinde ayni cikar ve gercek
    riskleri gurultuye gomer. Olcut kategori ve ikametgahin birlikte
    degerlendirilmesidir, yani harici bir arayuz hizmeti yine bildirilir.
    Veritabani elenmez: kisisel veri tutan bir bilesen kendi sunucunda
    dursa bile duragan sifreleme ve yedek erisimi sorulari dogurur.
    """
    giris = giris_bul(olgu.ad)
    if giris is None:
        return False
    return (giris.kategori in {"cerceve", "arayuz", "mobil"}
            and giris.veri_ikametgahi == "yerel")


def _teknoloji_bulgusu(olgu: Olgu, kanitlar: list[Kanit]) -> Bulgu | None:
    giris = giris_bul(olgu.ad)
    if giris is None:
        return None

    kategori = giris.kategori
    ikametgah = giris.veri_ikametgahi
    kaynak_ozeti = _kaynak_cumlesi(kanitlar)

    parcalar = [f"Raporda {giris.ad} kullanildigi belirtiliyor."]
    parcalar.append(_IKAMETGAH_METNI.get(ikametgah, ""))
    if giris.not_:
        parcalar.append(giris.not_.rstrip(".") + ".")
    if kaynak_ozeti:
        parcalar.append(kaynak_ozeti)

    return Bulgu(
        bulgu_id=f"s{uuid.uuid4().hex[:6]}",
        alan=_alan(kategori, ikametgah),
        # Kademe `olasi`, `gozlem` degil: teknolojinin belgede gectigi
        # kesindir, ancak bulgunun sordugu sey (erisim denetimi, sifreleme,
        # yedek yapilandirmasi) belgede yazmaz. Olgu kesin, risk
        # cikarimdir; bkz. ANALIZ_ISTEMI kesinlik merdiveni 2. basamak.
        kesinlik=Kesinlik.OLASI,
        baslik=f"{giris.ad} — {kategori} bileseninin veri islemesi"[:100],
        # Kirpma `_kirp` ile yapilir; duz dilimleme kelime ortasindan keser.
        aciklama=_kirp(" ".join(p for p in parcalar if p), 450),
        kontrol_onerisi=_KATEGORI_KONTROL.get(
            kategori, "Bu bilesenin veri islemesi projede nasil yapilandirildi?"
        )[:200],
        belge_dayanagi=[olgu.olgu_id],
        kaynak_dayanagi=kanitlar,
        ilgili_bolumler=[olgu.kaynak_bolum] if olgu.kaynak_bolum else [],
        uretim="sablon",
    )


def _veri_turu_bulgusu(olgu: Olgu, kanitlar: list[Kanit]) -> Bulgu | None:
    anahtar = olgu.ad.replace(" ", "_")
    ad, kontrol = _VERI_TURU_METNI.get(
        anahtar, (olgu.ad, "Bu veri turu icin hukuki dayanak ve saklama suresi belirlendi mi?")
    )
    kaynak_ozeti = _kaynak_cumlesi(kanitlar)
    parcalar = [
        f"Raporda {ad} islendigine isaret eden ifadeler geciyor.",
        "Bu tur veriler kisisel veri mevzuati kapsamina girer; "
        "islenme amaci, hukuki dayanagi ve saklama suresi belirlenmis olmalidir.",
    ]
    if kaynak_ozeti:
        parcalar.append(kaynak_ozeti)

    return Bulgu(
        bulgu_id=f"s{uuid.uuid4().hex[:6]}",
        alan=RiskAlani.HUKUKI,
        kesinlik=Kesinlik.GOZLEM,
        baslik=f"{ad.capitalize()} islenmesi"[:100],
        aciklama=_kirp(" ".join(parcalar), 450),
        kontrol_onerisi=kontrol[:200],
        belge_dayanagi=[olgu.olgu_id],
        kaynak_dayanagi=kanitlar,
        ilgili_bolumler=[olgu.kaynak_bolum] if olgu.kaynak_bolum else [],
        uretim="sablon",
    )


def _akis_bulgusu(olgu: Olgu, kanitlar: list[Kanit]) -> Bulgu | None:
    """LLM'in buldugu akis olgusu, konusu sozlukteki bir teknoloji.

    LLM'in katkisi olgunun kendisidir: "fotograflar S3'e yuklenir"
    cumlesini metinden cikarmak. O katki `alinti` alaninda birebir korunur,
    modelin cumleyi yeniden ifade etmesine gerek yoktur. Teknoloji
    bulgusundan farki, bileseni degil veri akisini anlatmasi ve daha
    spesifik bir kontrol sorusu dogurmasidir.
    """
    # Once olgunun kendi adinda aranir: `alinti` komsu cumlelere
    # tasabildigi icin orada birden fazla teknoloji gecebilir.
    adaylar = [g for g, _ in teknoloji_tara(olgu.ad)]
    if not adaylar:
        adaylar = [g for g, _ in teknoloji_tara(olgu.alinti)]
    if not adaylar:
        return None

    # Listedeki ilk eslesme degil, en spesifik olani secilir.
    # `teknoloji_tara` sozluk sirasinda doner; "Firebase Cloud Messaging
    # ile bildirim gonderilir" olgusunda hem "Firebase" hem "Firebase Cloud
    # Messaging" eslesir ve sira geregi genel olan one gecer, bu da yanlis
    # kategori ve yanlis kontrol sorusu demektir. Uzun ad dar kapsamdir.
    giris = max(adaylar, key=lambda g: len(g.ad))
    kategori, ikametgah = giris.kategori, giris.veri_ikametgahi
    akis = " ".join(olgu.alinti.split()).strip()

    parcalar = [f"Belgede su akis geciyor: \"{akis}\"." if akis
                else f"Belgede {giris.ad} ile ilgili bir veri akisi tarif ediliyor."]
    parcalar.append(_IKAMETGAH_METNI.get(ikametgah, ""))
    if giris.not_:
        parcalar.append(giris.not_.rstrip(".") + ".")
    ek = _kaynak_cumlesi(kanitlar, 220)
    if ek:
        parcalar.append(ek)

    return Bulgu(
        bulgu_id=f"s{uuid.uuid4().hex[:6]}",
        alan=_alan(kategori, ikametgah),
        # Akis belgede acikca yazar; alinti onun birebir kanitidir.
        kesinlik=Kesinlik.GOZLEM,
        # Baslik cumle degil ad olmalidir: `olgu.ad` bir akis cumlesi
        # oldugunda baslik cumlenin ortasindan kesilir. Akis cumlesi zaten
        # aciklamada birebir durur, basligin isi bileseni adlandirmaktir.
        baslik=(f"{giris.ad} — {olgu.ad}"[:100] if len(olgu.ad) <= 45
                else f"{giris.ad} — {kategori} bileseninin veri akisi"[:100]),
        # Kirpma `_kirp` ile yapilir; duz dilimleme kelime ortasindan keser.
        aciklama=_kirp(" ".join(p for p in parcalar if p), 450),
        kontrol_onerisi=_KATEGORI_KONTROL.get(
            kategori, "Bu akista tasinan veri nasil korunuyor?"
        )[:200],
        belge_dayanagi=[olgu.olgu_id],
        kaynak_dayanagi=kanitlar,
        ilgili_bolumler=[olgu.kaynak_bolum] if olgu.kaynak_bolum else [],
        uretim="sablon",
    )


def sablonla(olgu: Olgu, kanitlar: list[Kanit]) -> Bulgu | None:
    """Bir olgu icin bulguyu determinist kurar; kuramiyorsa None.

    None donen olgu icin dolgu bulgu uretilmez, olgu listede kalir
    (bkz. nodes._analiz).
    """
    if not kanitlar:
        return None

    if olgu.tespit_yontemi == "sozluk":
        if olgu.tur is OlguTuru.TEKNOLOJI:
            return _teknoloji_bulgusu(olgu, kanitlar)
        if olgu.tur is OlguTuru.VERI_TURU:
            return _veri_turu_bulgusu(olgu, kanitlar)
        return None

    # LLM'in buldugu olgu, konusu sozlukteki bir teknoloji. Ayar
    # kapatilirsa butun olgular analiste gider.
    if get_settings().sablon_akis_kapsami and olgu.tur in _AKIS_TURLERI:
        return _akis_bulgusu(olgu, kanitlar)
    return None


# ---------------------------------------------------------------- siralama

# Once bariz riskler gosterilir. Butun bulgulari ayni onemdeymis gibi
# siralamak ciktiyi okunmaz kilar. Sira: disari veri cikaran bilesenler ve
# hassas veri once, altyapi ve cerceve notlari sonra.
_ALAN_ONCELIK = {
    RiskAlani.VERI_SIZINTISI: 0,
    RiskAlani.HUKUKI: 1,
    RiskAlani.GUVENLIK: 2,
}
_KESINLIK_ONCELIK = {
    Kesinlik.GOZLEM: 0,      # belgede acikca yaziyor, en somut kademe
    Kesinlik.OLASI: 1,
    Kesinlik.DOGRULANMALI: 2,
}


def risk_puani(olgu: Olgu, kanitlar: list[Kanit]) -> int:
    """Olgunun ne kadar ilgi hak ettigini veren determinist puan.

    Analist ajanin butcesi sinirli oldugu icin bu puan once en agir
    olgulara harcanmasini saglar. Geri kalan sablondan kurulur ve
    `risk_sirasi` onlari listenin altina koyar.

    Agirliklar:
      ozel nitelikli veri  +5  KVKK m.6 (saglik, biyometrik, cocuk)
      diger kisisel veri   +4 / +3
      harici ikametgah     +3  verinin projeden cikmasi
      akis / kimlik turu   +2  "fotograflar S3'e yuklenir" bir eylem
                               anlatir, "S3 kullaniliyor" yalnizca varlik
                               bildirir
      saglayici kaniti     +1  bilesene ozel kanit bulunmustur
      cerceve/arayuz/mobil -2  her projede ayni cikan, belgeden turemeyen
                               bulgular

    `tespit_yontemi` agirlik olarak kullanilmaz: sozlukten gelen olgular
    arasinda hukuken en agir olanlar vardir. Yerine olgu turu kullanilir.
    """
    # KVKK m.6 ozel nitelikli veriler ayri agirliktadir.
    _VERI_AGIRLIK = {
        "saglik_verisi": 5, "biyometrik_veri": 5, "cocuk_verisi": 5,
        "kimlik_verisi": 4, "finansal_veri": 4,
        "konum_verisi": 3, "iletisim_verisi": 3,
    }

    puan = 0
    giris = giris_bul(olgu.ad)
    if giris is None:
        adaylar = [g for g, _ in teknoloji_tara(olgu.ad)]
        giris = max(adaylar, key=lambda g: len(g.ad)) if adaylar else None

    if giris is not None:
        if giris.veri_ikametgahi == "harici":
            puan += 3
        if giris.kategori in ("cerceve", "arayuz", "mobil"):
            puan -= 2
    if olgu.tur is OlguTuru.VERI_TURU:
        puan += _VERI_AGIRLIK.get(olgu.ad.strip().replace(" ", "_"), 3)
    if olgu.tur in (OlguTuru.VERI_AKISI, OlguTuru.KIMLIK_DOGRULAMA):
        puan += 2
    if any(k.kaynak_turu == "saglayici" for k in kanitlar):
        puan += 1
    return puan


def _normalize_soru(metin: str) -> str:
    """Kontrol sorusunu karsilastirma icin sadelestirir.

    Bosluk, buyuk-kucuk harf ve noktalama farki iki soruyu farkli yapmaz;
    kullanici acisindan ikisi de ayni maddedir.
    """
    return "".join(c for c in metin.lower() if c.isalnum())


def _icine_kat(tutulan: Bulgu, b: Bulgu) -> None:
    """`b`nin kanit, dayanak ve bolumlerini `tutulan`a kayipsiz ekler."""
    mevcut = {k.kaynak_kimlik for k in tutulan.kaynak_dayanagi}
    tutulan.kaynak_dayanagi += [k for k in b.kaynak_dayanagi
                                if k.kaynak_kimlik not in mevcut]
    tutulan.belge_dayanagi += [o for o in b.belge_dayanagi
                               if o not in tutulan.belge_dayanagi]
    tutulan.ilgili_bolumler = sorted(set(tutulan.ilgili_bolumler) | set(b.ilgili_bolumler))


def tekillestir(bulgular: list[Bulgu], olgu_turu: dict[str, str]) -> list[Bulgu]:
    """Ayni bileseni anlatan genel ve akis bulgusunu teke indirir.

    Ayni teknoloji icin hem genel hem akisa ozel bulgu olustugunda ikisi
    birlestirilir; akis bulgusu belgeden birebir alinti tasidigi icin o
    tutulur. Birlestirme kayipsizdir: elenenin kanitlari ve dayanaklari
    kalanin uzerine eklenir.

    Olcut `kontrol_onerisi` alanlarinin ayni olmasidir; farkli soru soran
    bulgular ikisi de kalir.
    """
    gruplar: dict[tuple, list[Bulgu]] = {}
    digerleri: list[Bulgu] = []
    for b in bulgular:
        giris = giris_bul(b.baslik.split(" — ")[0].strip())
        if b.uretim != "sablon" or giris is None:
            digerleri.append(b)
            continue
        gruplar.setdefault((giris.ad, b.kontrol_onerisi), []).append(b)

    # LLM bulgulari da ayni kurala tabidir. Analist ayni paragraf icin
    # `aciklama` ve `kontrol_onerisi` alanlari birebir ayni, yalnizca
    # `alan` etiketi farkli bulgular yazabiliyor; istemdeki kural bunu
    # engellemedigi icin tekillestirme kodda yapilir.
    llm_gruplari: dict[str, list[Bulgu]] = {}
    kalanlar: list[Bulgu] = []
    for b in digerleri:
        if b.uretim != "llm":
            kalanlar.append(b)
            continue
        llm_gruplari.setdefault(_normalize_soru(b.kontrol_onerisi), []).append(b)

    for grup in llm_gruplari.values():
        for b in grup[1:]:
            _icine_kat(grup[0], b)
        kalanlar.append(grup[0])

    sonuc: list[Bulgu] = kalanlar
    for (_, _), grup in gruplar.items():
        if len(grup) == 1:
            sonuc.append(grup[0])
            continue
        # Akis bulgusu tutulur: dayandigi olgu LLM'den gelmistir ve
        # belgeden birebir alinti tasir.
        akis = [b for b in grup
                if any(olgu_turu.get(o) == "llm" for o in b.belge_dayanagi)]
        tutulan = (akis or grup)[0]
        for b in grup:
            if b is not tutulan:
                _icine_kat(tutulan, b)
        sonuc.append(tutulan)
    return sonuc


def risk_sirasi(bulgu: Bulgu) -> tuple:
    """Bulgu siralama anahtari. Kucuk deger = daha onemli."""
    disari = 1
    if bulgu.uretim == "sablon" and bulgu.belge_dayanagi:
        # Sablon bulgularinda teknoloji adi baslikta duruyor.
        ad = bulgu.baslik.split(" — ")[0].strip()
        giris = giris_bul(ad)
        if giris is not None and giris.veri_ikametgahi == "harici":
            disari = 0
    return (
        _ALAN_ONCELIK.get(bulgu.alan, 3),
        disari,
        _KESINLIK_ONCELIK.get(bulgu.kesinlik, 3),
        bulgu.baslik,
    )
