"""Ajan dugumleri.

Dort ajanin her birinin kendi sistem istemi, arac seti ve cikti semasi
vardir. Aralarindaki graf sabittir; ozerklik dugumlerin icindedir.

  Cikarici    -> belgeden risk tasiyan olgulari cikarir
  Getirici    -> her olgu icin bilgi tabanini arar, zayif kalirsa
                 sorguyu yeniden yazip tekrar dener (ozerk dongu)
  Analist     -> olgu ve kanit eslesmesinden temkinli bulgu uretir
  Dogrulayici -> dayanaksiz bulgulari eler, temkinsiz dili duzeltir
"""

from __future__ import annotations

import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from app.config import get_settings
from app.core import sablon, vectorstore
from app.core.gazetteer import (
    _normalize,
    alinti_cikar,
    teknoloji_tara,
    veri_turu_tara,
)
from app.core.gunluk import kayit
from app.core.llm import DevreKesiciAcik, ENJEKSIYON_UYARISI, belge_blogu, llm
from app.graph.state import AnalizDurumu
from app.schemas import (
    BelgeOzeti,
    Bulgu,
    DugumIzi,
    ElenenBulgu,
    Kanit,
    Olgu,
    OlguTaslakListesi,
    OlguTuru,
    OzetTaslagi,
    RiskAlani,
    SoruIsareti,
    VerifierKarari,
    VerifierKararListesi,
    kisitli_bulgu_semasi,
)

AYAR = get_settings()

# Olgu turune gore hangi bilgi kaynaklarinin sorgulanacagi. Tum
# kaynaklari birden sorgulamak gurultu uretir.
KAYNAK_YONLENDIRME: dict[OlguTuru, list[str]] = {
    OlguTuru.TEKNOLOJI: ["asvs", "cwe", "saglayici"],
    OlguTuru.VERI_AKISI: ["linddun", "asvs", "saglayici"],
    OlguTuru.VERI_TURU: ["kvkk", "gdpr", "linddun"],
    OlguTuru.KIMLIK_DOGRULAMA: ["asvs", "cwe"],
    OlguTuru.DAGITIM: ["asvs", "cwe"],
    OlguTuru.EKSIK_BILGI: ["asvs", "kvkk", "linddun"],
}

TEMKINLI_DIL = """
DIL KURALI — pazarlik disi:
- "acik vardir", "guvensizdir", "ihlal ediyor", "yasaya aykiri" gibi KESIN
  ifadeler kullanma. Bu sistem koda degil, bir rapora bakiyor; implementasyonu
  goremez, bu yuzden kesin hukum veremez.
- Bunun yerine sunu yap: ilgili teknolojinin veri alisverisini nasil yaptigini
  1-2 cumleyle anlat, ardindan kullanicinin neyi dogrulamasi gerektigini soyle.
- Iyi ornek: "Firebase Realtime Database verileri Google altyapisinda barindirir
  ve varsayilan sunucu bolgesi ABD olabilir. Projenizde bolge ayarinin ve
  guvenlik kurallarinin nasil yapilandirildigi kontrol edilmelidir."
- Kotu ornek: "Firebase kullanimi KVKK ihlalidir."
- Raporda bilgi eksikse bunu bir acik olarak degil, dogrulanmasi gereken bir
  nokta olarak sun.

BU KURAL DILE AITTIR, KESINLIK KADEMESINE DEGIL. Temkinli yazmak, her bulguyu
`dogrulanmali` yapmak demek DEGILDIR. Raporda acikca yazan bir seyi aktarirken
kademe `gozlem` olur; cumleyi yine temkinli kurarsin. Iki eksen ayridir:
  - dil    -> hicbir zaman kesin hukum verme
  - kademe -> iddianin belgede ne kadar karsiligi var
"""


ANALIZ_ISTEMI = (
    "Bir yazilim projesi raporu icin risk bulgulari yaziyorsun. Hedef kitle "
    "yazilimci ve bilgisayar muhendisi; teknik terim kullanabilirsin.\n\n"
    "Her bulgu tam olarak bir risk alanina girer:\n"
    "  guvenlik       - kimlik dogrulama, yetkilendirme, sifreleme, girdi dogrulama\n"
    "  veri_sizintisi - verinin ucuncu taraflara veya disariya akmasi\n"
    "  hukuki         - KVKK/GDPR yukumlulukleri, aydinlatma, riza, saklama suresi\n\n"
    "kesinlik alani - SIRAYLA SOR, ilk uyan kademeyi sec. "
    "OLCTUGUN SEY: RISKIN NE KADARI BELGEDE YAZIYOR.\n"
    "  1) Belge, riski OLUSTURAN yapilandirmanin KENDISINI acikca "
    "yaziyor mu?\n"
    "     -> gozlem   (orn. 'kova public-read olarak yapilandirilmistir', "
    "'jetonlar AsyncStorage icinde saklanmaktadir', 'gunluklere T.C. "
    "kimlik numarasi yazilmaktadir')\n"
    "  2) Belge NOTR bir olgu yaziyor, ama riskin gerceklesip "
    "gerceklesmeyecegi belgede YAZMAYAN bir ayrintiya mi bagli?\n"
    "     -> olasi    (orn. 'fotograflar S3 kovasina yuklenir' yaziyor "
    "ama erisim politikasi hic gecmiyor; kova acik da olabilir kapali "
    "da, riski sen standarttan cikariyorsun)\n"
    "  3) Rapor bu konuda gercekten SESSIZ mi?\n"
    "     -> dogrulanmali\n"
    "IKI HATANIN IKISINDEN DE KACIN:\n"
    "  (a) Belge riskli yapilandirmayi ACIKCA soyluyorsa 'olasi' deme. "
    "Sizintinin gerceklesip gerceklesmeyecegi belirsiz olsa bile kademe "
    "gozlemdir; sonucun belirsizligini kademeye degil DILE yansit.\n"
    "  (b) Belge yalnizca NOTR bir olgu soyluyorsa 'gozlem' deme. "
    "'PostgreSQL kullanilmaktadir' cumlesi bir olguyu kesinlestirir "
    "ama bir risk bildirmez; riski standarttan sen cikariyorsun, "
    "kademe olasidir.\n"
    "DIKKAT: `dogrulanmali` en zayif kademedir, varsayilan degildir. Bir olgu "
    "sozlukten cikmissa veya alintisi konuyu dogrudan iceriyorsa `gozlem` ya da "
    "`olasi` secilir. Bulgularin cogunun `dogrulanmali` cikmasi HATADIR.\n\n"
    # KVKK m.6 sayma yontemiyle yazilmistir; listede olmayan bir veri ozel
    # nitelikli olamaz. Blok, kesinlik merdiveninin iki yarisini ayirmamak
    # icin merdivenin altina konur.
    "OZEL NITELIKLI VERI SAYILIDIR. KVKK m.6 sunlari sayar: irk, etnik koken, "
    "siyasi dusunce, felsefi inanc, din, mezhep, kilik kiyafet, dernek/vakif/sendika "
    "uyeligi, SAGLIK, cinsel hayat, ceza mahkumiyeti ve guvenlik tedbirleri, "
    "biyometrik ve genetik veri. BU LISTEDE OLMAYAN bir veriyi ozel nitelikli "
    "DIYE NITELEME. T.C. kimlik numarasi, ad-soyad, telefon, e-posta ve konum "
    "kisisel veridir ama ozel nitelikli DEGILDIR.\n\n"
    f"{TEMKINLI_DIL}\n"
    # Aciklama belgeyi kopyalamaz: okur belgeyi zaten okumustur, aracin
    # kattigi deger cumlenin neden onemli oldugudur.
    "ACIKLAMA KURALI: `aciklama` belgeyi tekrar etmez. Ilk cumlede belgede "
    "ne yazdigini KISACA ozetle, kalan cumlelerde bunun neden risk tasidigini "
    "ve hangi mekanizmayla soruna donusebilecegini anlat.\n"
    "KANIT KURALI: `belge_dayanagi` alanina sana verilen olgu_id'leri yaz. "
    "`kaynak_kimlikleri` alanina SADECE sana verilen kaynak kimliklerini yaz "
    "(orn. 'ASVS 8.3.4'). Kaynak metnini TEKRAR YAZMA, sadece kimligini ver. "
    "Sana verilmeyen bir kimlik UYDURMA.\n"
    "Her iki dayanak alani da bos birakilamaz.\n"
    "Zorlama bulgu uretme - kanit zayifsa o olguyu atla.\n"
    # Kural bilincli olarak dar tutulur. Kesinlik merdiveninin onune
    # kosulsuz bir kapi olarak konuldugunda analist genel bir eleme
    # egilimi gosteriyor. Bu yuzden kural diger kurallarla ayni duzeyde
    # durur ve supheye dusuldugunde varsayilan bulguyu yazmaktir; bir on
    # tarama aracinda kacirmanin bedeli fazladan bir maddeden agirdir.
    "COZULMUS SORUN: belge bir eksigin GIDERILDIGINI acikca soyluyorsa "
    "(orn. 'ilk surumde su kullaniliyordu, ikinci surumde suna gecildi') "
    "o olgu icin bulgu yazma. Bu kural YALNIZCA belge duzeltmeyi acikca "
    "bildirdiginde gecerlidir; supheye dusersen bulguyu YAZ.\n"
    "KONUSU OLMAYAN BULGU YAZMA. veri_sizintisi ve hukuki alanlari "
    "KISIYE AIT ya da GIZLI veri gerektirir. Belgedeki veri kisiye "
    "baglanamiyorsa - sensor olcumu, bitki/malzeme/cihaz goruntusu, "
    "kamuya acik derlem, simulasyon ciktisi, olcum kaydi, kod ya da "
    "dilbilgisi verisi - bu iki alanda BULGU YAZMA. Korunacak bir sey "
    "yoksa mahremiyet riski de yoktur. (guvenlik alani bundan MUAF: "
    "kisisel veri olmayan bir projede de kaynak kodda sabit anahtar "
    "veya acik yapilandirma gercek bir bulgudur.)\n"
    "IMPLEMENTASYON RISKI UYDURMA. Bellek yonetimi, arabellek boyutu, "
    "isaretci guvenligi, yigin temizligi, es zamanlilik yarisi gibi KOD "
    "SEVIYESI ayrintilar bu araca gorunmez. Belge bir muhendislik "
    "ozelligini anlatiyorsa (sabit bellek kullanimi, bellege esleme, "
    "tampon yeniden kullanimi, dosya bicimi) bunu zafiyet olarak "
    "YORUMLAMA: zafiyet olup olmadigi belgede yazmayan ayrintilara bagli, "
    "dolayisiyla hakkinda bulgu yazilamaz. Bulgu ancak belgenin ACIKCA "
    "anlattigi bir yapilandirma, akis veya karar uzerine kurulabilir.\n"
    # Belgede gecmeyen bir bileseni isaret etmek, riski kacirmaktan daha
    # zararlidir.
    "BELGEDE GECMEYEN teknoloji, servis, urun veya kutuphane adi YAZMA - "
    "ne aciklamada ne kontrol onerisinde. Ornek verecegin zaman belgede "
    "gecen adlari kullan.\n"
    # Ayni riski anlatan olgular tek bulguda birlesir; `belge_dayanagi`
    # coklu olgu kabul eder.
    "AYNI RISKI ANLATAN IKI OLGU ICIN TEK BULGU YAZ ve ikisinin de "
    "olgu_id'sini `belge_dayanagi` alanina koy. Ayni konuyu iki bulguya "
    "bolme.\n"
    "Turkce yaz."
)


# Olgu turune gore Ingilizce arama omurgasi. Bilgi tabani agirlikli olarak
# Ingilizce oldugundan (ASVS, CWE, LINDDUN) Turkce olgu adini oldugu gibi
# sormak zayif eslesme verir; tur basina bir teknik omurga tutulur.
_TUR_SORGU_OMURGASI: dict[OlguTuru, str] = {
    OlguTuru.TEKNOLOJI: "third party service data handling security",
    OlguTuru.VERI_AKISI: "data transmission to external service storage location privacy",
    OlguTuru.VERI_TURU: "personal data processing legal basis retention",
    OlguTuru.KIMLIK_DOGRULAMA: "authentication session token authorization",
    OlguTuru.DAGITIM: "deployment environment secrets configuration management",
    OlguTuru.EKSIK_BILGI: "security requirement documentation",
}


# Yeniden deneme araliklari (saniye): deneme 1->2 ve 2->3 arasi.
# Asiri yuklenmis bir uc nokta saniyeler icinde bosalmadigi icin kisa
# bekleme yalnizca kotayi harcar; bekleme uzadikca deneme ise yarar.
YENIDEN_BEKLEME = (5, 15)


def _llm_dene(etiket: str, cagri, deneme: int = 3):
    """LLM cagrisini gecici saglayici hatalarina karsi yeniden dener.

    Basarisizsa None doner ve cagiran dugum determinist sonuca duser. Tek
    yigina inen dugumlerde (cikarim, analiz) tek bir gecici hata butun LLM
    dalgasini sifirlayabilir, bu yuzden deneme sayisi birden fazladir.

    Devre kesici aciksa yeniden denenmez. Her basarisiz deneme hata
    mesajiyla loglanir; kota ve odeme uyarilari sessizce kaybolmamalidir.
    """
    for n in range(1, deneme + 1):
        try:
            return cagri()
        except DevreKesiciAcik as kesici:
            kayit(f"{etiket}: {kesici}")
            return None
        except Exception as hata:  # noqa: BLE001
            kayit(f"{etiket}: deneme {n} basarisiz "
                  f"({type(hata).__name__}: {str(hata)[:140]})")
            if n < deneme:
                time.sleep(YENIDEN_BEKLEME[n - 1])
    return None


def arama_ifadesi_kur(tur: OlguTuru, metin: str) -> str:
    """Olgudan determinist Ingilizce arama ifadesi kurar.

    Arama ifadesi modelden istenmez: kucuk modeller uzun istem altinda bu
    alani bos veya anlamsiz birakabiliyor ve bos sorgu bilgi tabaninda
    rastgele bir kayda takiliyor. Teknoloji adi sozlukte, tur semada
    durdugu icin ikisini birlestirmek Python'un isidir; sozluk katmani da
    ayni yolu izler (bkz. cikar_sozluk).
    """
    adlar: list[str] = []
    for giris, _ in teknoloji_tara(metin):
        if giris.ad not in adlar:
            adlar.append(giris.ad)
    omurga = _TUR_SORGU_OMURGASI.get(tur, "security requirement")
    return " ".join([*adlar[:3], omurga])[:200]


def _tek_cumleye_kirp(metin: str, sinir: int = 180) -> str:
    """Alintiyi tek cumleye indirir.

    `_cumle_al` sabit genislikte bir pencere acar ve pencere komsu
    cumlelere tasabilir. Alinti sablon bulgusunun merkezinde durdugu icin
    (bkz. sablon._akis_bulgusu) yanlis cumle dogrudan yanlis bulgu verir.
    """
    metin = " ".join(metin.split()).strip()
    for i, k in enumerate(metin):
        if k in ".!?" and i >= 40 and (i + 1 >= len(metin) or metin[i + 1] == " "):
            return metin[: i + 1]
    return metin[:sinir]


def _ayirt_etmeyen_kanitlari_seyrelt(
    kanitlar: dict[str, list[Kanit]], hedefler: list[str]
) -> int:
    """Cok sayida olguya birden yapisan kanitlari eler.

    Bilgi tabanindaki bazi kayitlarin metni bu aracin genel temasiyla
    ("sensitive data sent to third parties") ortustugu icin her sorguya
    yapisir ve birbirinden farkli olgular ayni dayanaga baglanir. IDF
    fikri burada getirmeye uygulanir: olgularin buyuk bolumu icin
    getirilen bir kaydin hicbiri hakkinda ozel bir sey soyleme ihtimali
    dusuktur. Islem determinist ve maliyetsizdir.

    Iki koruma vardir:
      - Esik orantilidir (`kanit_yayginlik_orani`, tabani 3 olgu) ve en az
        4 olgu gerektirir; kucuk belgelerde hicbir sey elenmez.
      - Bir olgunun kanitlari tamamen bosalmaz, en iyi skorlu kanit kalir.
        Kanitsiz olgu bulgu uretemeyecegi icin seyreltme geri cagirmayi
        dusurmez, yalnizca dayanagi daraltir.
    """
    if len(hedefler) < 4:
        return 0

    # Bir kaynagin kac olguya dayanak olabilecegi. Oran belge boyutuna
    # baglidir ama taban sabittir; kucuk belgelerde 3'un altina inmez.
    tavan = max(3, int(len(hedefler) * AYAR.kanit_yayginlik_orani))

    # kaynak -> [(skor, olgu_id)]
    kullanim: dict[str, list[tuple[float, str]]] = {}
    for olgu_id in hedefler:
        for k in kanitlar.get(olgu_id, []):
            kullanim.setdefault(k.kaynak_kimlik, []).append((k.skor, olgu_id))

    # Kayit toptan atilmaz, en iyi eslesmeleri birakilir: her yere yapisan
    # bir kayit bir iki olgu icin gercekten dogru kanit olabilir. Kaynak,
    # en iyi eslestigi `tavan` kadar olguda kalir ve gerisinden duser.
    dusecek: set[tuple[str, str]] = set()   # (olgu_id, kaynak_kimlik)
    for kimlik, liste in kullanim.items():
        if len(liste) <= tavan:
            continue
        liste.sort(key=lambda t: t[0], reverse=True)
        for _, olgu_id in liste[tavan:]:
            dusecek.add((olgu_id, kimlik))

    if not dusecek:
        return 0

    atilan = 0
    for olgu_id in hedefler:
        mevcut = kanitlar.get(olgu_id)
        if not mevcut:
            continue
        kalan = [k for k in mevcut if (olgu_id, k.kaynak_kimlik) not in dusecek]
        if not kalan:
            # Hepsi dustuyse en iyi skorlu kanit geri alinir; kanitsiz olgu
            # bulgu uretemez.
            kalan = [max(mevcut, key=lambda k: k.skor)]
        atilan += len(mevcut) - len(kalan)
        kanitlar[olgu_id] = kalan
    return atilan


# `schemas.BulguTaslagi.baslik` alanindaki `max_length` ile ayni olmali;
# ikisi ayrisirsa kesik baslik tespiti calismaz.
_BASLIK_SINIRI = 100


def _basligi_temizle(metin: str) -> str:
    """Baslikta Turkce disi alfabe birakmaz.

    Model zaman zaman baslige alakasiz bir alfabeden karakter koyabiliyor.
    Esik U+0250'dir: Turkce harflerin tamami (U+00E7, U+011F, U+0131,
    U+015F ve digerleri) bu esigin altinda, Kiril, Yunan, CJK ve kana
    ustunde kalir.
    """
    izinli = '–—…'
    temiz = "".join(c for c in metin if ord(c) < 0x250 or c in izinli)
    temiz = " ".join(temiz.split())

    # Sinira dayanmis baslik, ortadan kesilmis basliktir: semadaki
    # `max_length` JSON Semasi'nda `maxLength` olarak gider, saglayici onu
    # dilbilgisine cevirir ve modeli tam o karakterde susturur.
    #
    # `_yarim_cumleyi_at` kurali burada kullanilamaz, cunku baslikler zaten
    # noktayla bitmez ve o kural her basligin son kelimesini atardi. Ayirt
    # edici olcut uzunluktur.
    if len(metin) >= _BASLIK_SINIRI - 2:
        bosluk = temiz.rfind(" ")
        if bosluk > 30:
            temiz = temiz[:bosluk].rstrip(" ,;:-–—")
    return temiz or "Belgede gecen nokta"


# Metnin sonundaki kisaltma kalibi ("T.C.", "A.S.", "vb.", "orn.",
# "bkz.", "m.6."). Normal bir cumle sonu bu kalibi tutmaz.
_KISALTMAYLA_BITIYOR = re.compile(
    r"(?:\b\w\.){1,3}$|\b(?:vb|vs|orn|ornegin|bkz|md|no|sf|str|dk|sn)\.$",
    re.IGNORECASE,
)


def _cumle_sonu(metin: str) -> int:
    """Son gercek cumle sonunun indeksi; kisaltma noktalarini atlar.

    "T.C. kimlik numarasi" icindeki nokta bir cumleyi kapatmaz. Duz
    `rfind(". ")` bunu ayirt edemez ve kirpma yanlis yerden yapilir.
    """
    for m in reversed(list(re.finditer(r"[.!?] ", metin))):
        i = m.start()
        if metin[i] == "." and _KISALTMAYLA_BITIYOR.search(metin[: i + 1]):
            continue
        return i
    return -1


def _yarim_cumleyi_at(metin: str) -> str:
    """Dilbilgisi sinirinin ortadan kestigi son cumleyi atar.

    Sema alanlarindaki `max_length`, JSON Semasi'nda `maxLength` olarak
    gider ve llama.cpp bunu GBNF dilbilgisine cevirir; model tam o
    karakterde, cumlenin hatta kelimenin ortasinda susturulur. Sinirlari
    yukseltmek kesigin yerini degistirir, kendisini kaldirmaz, cunku model
    karakter sayamaz. Bu yuzden metin son cumle sinirina geri kirpilir.

    Metin bastan sona tek cumleyse hicbir sey atilmaz; o durumda yalnizca
    kelime ortasindan kesilmis olmasi engellenir.
    """
    metin = " ".join(metin.split()).strip()
    if not metin:
        return metin
    # Zaten duzgun bitmisse dokunulmaz, ancak nokta her zaman cumle sonu
    # degildir: "...Kullanici adi ve T.C." gibi bir metin noktayla biter
    # ama cumle yarimdir. Son kelime tek harf ve nokta bicimindeyse
    # (T.C., A.S.) ya da bilinen bir kisaltmaysa metnin duzgun bittigine
    # guvenilmez, asagidaki son cumle kirpmasi calisir.
    if metin[-1] in ".!?" and not _KISALTMAYLA_BITIYOR.search(metin):
        return metin
    son = _cumle_sonu(metin)
    if son > 0:
        return metin[: son + 1]
    # Tek cumle: kelime bolunmez ve metnin yarim kaldigi belli edilir.
    bosluk = metin.rfind(" ")
    return (metin[:bosluk] if bosluk > 40 else metin).rstrip(" ,;:") + "…"


def _alinti_sec(kaynak_metin: str, ad: str, aciklama: str) -> str:
    """Olgu icin belgeden birebir alinti secer; olcut kelime ortusmesidir.

    Alt dizge aramasi iki yerde yetersiz kalir:
    1. `alinti_cikar` tam ifadeyi bulamazsa ifadenin ilk kelimesine duser.
       Olgu adi bir cumle oldugunda ("Sunucu Heroku uzerinde
       barindirilmakta") metindeki ilk "Sunucu" kelimesi bulunur ve
       bambaska bir cumle alinti olarak tasinir.
    2. Teknoloji adiyla aramak da yetmez: ayni ad bir bolumde birden cok
       kez gecer ve arama hep ilkini bulur.

    Dogru olcut, olgu adiyla en cok kelime paylasan cumledir: determinist,
    ucuz ve yeniden ifade edilmis metne dayaniklidir. Alinti sablon
    bulgusunun merkezinde durdugu icin (bkz. sablon._akis_bulgusu) bu
    secim dogrudan bulgu dogruluguna yansir.
    """
    ad_kelimeler = {k for k in _normalize(ad).split() if len(k) > 2}
    if ad_kelimeler:
        en_iyi, en_skor = None, 0
        for cumle in re.split(r"(?<=[.!?])\s+", kaynak_metin):
            temiz = " ".join(cumle.split())
            if len(temiz) < 25:
                continue
            ortak = len(ad_kelimeler & set(_normalize(temiz).split()))
            if ortak > en_skor:
                en_iyi, en_skor = temiz, ortak
        # En az iki anlamli kelime ortusmeli; tek kelimelik ortusme
        # ("veri", "sistem") rastgele bir cumleyi secmeye yeter.
        if en_iyi and en_skor >= 2:
            return _tek_cumleye_kirp(en_iyi)

    b = alinti_cikar(kaynak_metin, ad)
    return _tek_cumleye_kirp(b) if b else aciklama[:180]


def _es_zamanli_uygula(islev, girdiler: list):
    """Bagimsiz LLM yiginlarini es zamanli calistirir ve sirayi korur.

    Sira onemlidir: cikarim olgu_id'leri, analiz de bulgu sirasini buradan
    alir. `executor.map` girdi sirasina gore dondurur, `submit` ve
    `as_completed` dondurmez; bu yuzden map kullanilir.

    `llm_es_zamanli` 1 ise hicbir is parcacigi acilmaz.
    """
    n = max(1, AYAR.llm_es_zamanli)
    if n == 1 or len(girdiler) < 2:
        return [islev(g) for g in girdiler]
    with ThreadPoolExecutor(max_workers=min(n, len(girdiler))) as havuz:
        return list(havuz.map(islev, girdiler))


def _iz(dugum: str, bas: float, olcum: dict, not_: str | None = None) -> DugumIzi:
    return DugumIzi(
        dugum=dugum,
        durum="bitti",
        sure_ms=int((time.time() - bas) * 1000),
        olcum=olcum,
        **({"not": not_} if not_ else {}),
    )


# ------------------------------------------------------------------ 1. yonlendir

# Yonlendirme dugumunun `belirsiz` basliklari ayirmak icin kullandigi
# prototipler. Baslik gommesi hangi kutba daha yakinsa o karar uygulanir.
_ILGILI_PROTOTIPLER = (
    "sistem mimarisi ve bilesenleri",
    "veri modeli, veritabani ve veri saklama",
    "kimlik dogrulama, yetkilendirme ve guvenlik onlemleri",
    "dagitim, sunucu altyapisi ve calisma ortami",
    "uygulama gelistirme, API ve servis entegrasyonu",
    # Asagidaki iki prototip, aracin uc risk alanindan ikisini
    # (veri_sizintisi ve hukuki) temsil eder. Yalnizca mimari ve guvenlik
    # prototipleri bulundugunda ucuncu taraf entegrasyonu ve odeme
    # bolumleri ilgisiz kutbuna dusup LLM cikarimina hic girmiyor.
    "ucuncu taraf servis, dis API ve yapay zeka entegrasyonu",
    "kisisel veri islenmesi, riza, gizlilik ve odeme islemleri",
)
_ILGISIZ_PROTOTIPLER = (
    "giris, motivasyon ve problem tanimi",
    "literatur taramasi ve ilgili calismalar",
    "sonuc, tartisma ve gelecek calismalar",
    "tesekkur, ozgecmis ve kaynakca",
)


def _normalize_vek(v: list[float]) -> list[float]:
    n = sum(x * x for x in v) ** 0.5
    return [x / n for x in v] if n else v


def _nokta(a: list[float], b: list[float]) -> float:
    """Ikisi de birim vektor oldugu icin nokta carpimi kosinus verir."""
    return sum(x * y for x, y in zip(a, b))


@lru_cache(maxsize=1)
def _prototip_vektorleri() -> tuple[tuple, tuple]:
    """Prototipleri bir kez gomer ve surec omru boyunca saklar.

    Prototipler sabittir; her analizde yeniden gommek gereksiz ileri
    gecis anlamina gelir.
    """
    from app.core.embeddings import gomme

    tum = list(_ILGILI_PROTOTIPLER) + list(_ILGISIZ_PROTOTIPLER)
    vek = [_normalize_vek(c["dense"]) for c in gomme().kodla(tum)]
    n = len(_ILGILI_PROTOTIPLER)
    return tuple(vek[:n]), tuple(vek[n:])


def _belirsizleri_ayikla(belirsiz: list) -> set[str]:
    """`belirsiz` bolumleri LLM'siz ayiklar; olcut gomme benzerligidir.

    Is, bir basligi iki kategoriye ayirmaktan ibarettir. Ayni isi bellekte
    zaten duran BGE-M3 milisaniyeler icinde yapar; gomme modeli `getir`
    dugumu icin nasilsa yuklu oldugundan marjinal maliyeti yoktur.

    Gomme herhangi bir sebeple calismazsa uzun bolumlere dusulur; bu
    dugumun hatasi tum analizi durdurmamalidir.
    """
    try:
        ilgili, ilgisiz = _prototip_vektorleri()

        # Basliklar tek toplu kodlamayla gomulur. Tek tek gommek her biri
        # embeddings._kilit altinda sirayla calisan ayri ileri gecisler
        # demektir; prototipler ise surec omru boyunca onbellektedir.
        from app.core.embeddings import gomme

        vektorler = [_normalize_vek(c["dense"])
                     for c in gomme().kodla([b.baslik for b in belirsiz])]

        secilen: set[str] = set()
        for b, v in zip(belirsiz, vektorler):
            if max(_nokta(v, p) for p in ilgili) > max(_nokta(v, p) for p in ilgisiz):
                secilen.add(b.bolum_id)
        return secilen
    except Exception as hata:  # noqa: BLE001
        kayit(f"yonlendir: gomme ayiklamasi calismadi ({type(hata).__name__}), "
              f"en uzun bolumlere dusuluyor")
        return {b.bolum_id for b in sorted(belirsiz, key=lambda x: len(x.metin),
                                           reverse=True)[:3]}


# --------------------------------------------------------------------------


def yonlendir(durum: AnalizDurumu) -> dict:
    """Hangi bolumler derin analize deger?

    Hedef sistem mimarisi, veri modeli ve uygulama bolumleridir. Once ucuz
    sezgisel kural (ayristirmadan gelen `karar`), sonra `belirsiz` kalanlar
    icin gomme tabanli kutup karsilastirmasi calisir; LLM kullanilmaz.

    Eleme burada yapilir. Analizin maliyeti belge boyutuyla degil buradan
    gecen bolum sayisiyla orantilidir.
    """
    bas = time.time()
    bolumler = durum["bolumler"]
    kesin_evet = [b.bolum_id for b in bolumler if b.karar == "evet"]
    belirsiz = [b for b in bolumler if b.karar == "belirsiz"]

    hedef = set(kesin_evet)
    if belirsiz:
        hedef |= _belirsizleri_ayikla(belirsiz)

    # Hicbir bolum secilmezse analiz bos doner; bu durumda belirsizlerin
    # en uzunlarina dusulerek govde yine de taranir.
    if not hedef:
        yedek = sorted(belirsiz, key=lambda b: len(b.metin), reverse=True)[:3]
        hedef = {b.bolum_id for b in yedek}
        kayit("yonlendir: hicbir bolum secilmedi, en uzun 3 bolume dusuldu")

    kayit(f"yonlendir: {len(hedef)}/{len(bolumler)} bolum analize alindi "
          f"(kesin {len(kesin_evet)}, belirsiz {len(belirsiz)}, "
          f"{time.time() - bas:.2f}s, LLM yok)")
    return {
        "hedef_bolumler": sorted(hedef),
        "iz": [_iz("yonlendir", bas, {
            "toplam_bolum": len(bolumler),
            "kesin_evet": len(kesin_evet),
            "belirsiz": len(belirsiz),
            "analize_alinan": len(hedef),
        })],
    }


# ------------------------------------------------------------------ 2. ozetle


def ozetle(durum: AnalizDurumu) -> dict:
    """Belge ozeti: amac LLM'den, bilesenler sozlukten gelir.

    Is bolumu su sekildedir:
    - `amac` ve `alan` okuyup anlamayi gerektirdigi icin LLM'e birakilir.
      Determinist kurulum (girisin ilk uc cumlesi) kapak bilgisi bir
      baslik altina dustugunde bozulur; kapakla amaci ayirmak kelime
      sayarak yapilamaz.
    - `ana_bilesenler` sozlukte kesin olarak durdugundan Python tarafinda
      uretilir.

    LLM cagrisi basarisiz olursa determinist yola dusulur; ozet bir baslik
    kartindan ibarettir ve analizin hicbir asamasi ona dayanmaz.
    """
    bas = time.time()
    bolumler = durum["bolumler"]
    # Bu dugum `yonlendir`den once calistigi icin `hedef_bolumler` henuz
    # olmayabilir; yoksa `hayir` bolumleri disarida birakilip geri kalanina
    # dusulur. Bilesen listesi sozluk taramasindan gelir.
    secilen = [b for b in bolumler
               if b.bolum_id in (durum.get("hedef_bolumler") or [])] \
        or [b for b in bolumler if b.karar != "hayir"]

    # Amac belgenin basinda durur, hedef bolumlerde degil. Giris bolumu
    # risk analizine deger gorulmedigi icin elenebilir; amac bolumu, risk
    # tasiyip tasimadigindan bagimsiz olarak aranir.
    _GIRIS = ("giris", "giriş", "amac", "amaç", "ozet", "özet", "abstract",
              "problem", "kapsam", "introduction")
    girisler = [b for b in bolumler
                if any(k in b.baslik.lower() for k in _GIRIS) and len(b.metin) > 120]
    kaynak = girisler or bolumler or secilen
    ilk_metin = " ".join(kaynak[0].metin.split()) if kaynak else ""

    # LLM'e belgenin basi verilir, amac orada yazar. Bolum basliklari da
    # eklenir; "3. Sistem Mimarisi, 4. Veri Modeli" gibi bir iskelet,
    # konunun yerlestirilmesine kapak metninden daha cok yardim eder.
    basliklar = ", ".join(b.baslik for b in bolumler[:12])
    def _ozet_dene():
        return llm().yapisal(
            sistem=(
                "Sana bir yazilim projesi raporunun BASI veriliyor. Projenin NE "
                "YAPTIGINI iki cumleyle yaz.\n\n"
                "DIKKAT — kapak bilgisi projenin amaci DEGILDIR. Ekip uyeleri, "
                "ogrenci numaralari, danisman adi, teslim tarihi, bolum, mekan, "
                "anahtar kelimeler gibi ifadeleri ozete ASLA koyma. Metin bunlarla "
                "basliyorsa onlari atla ve asil anlatimi bul.\n"
                "Belge projenin ne yaptigini soylemiyorsa amaci UYDURMA; "
                "'Belgede proje amaci acikca belirtilmemis.' yaz.\n"
                "Turkce yaz.\n\n"
                f"{ENJEKSIYON_UYARISI}"
            ),
            kullanici=f"Bolum basliklari: {basliklar}\n\n{belge_blogu(ilk_metin[:1400])}",
            sema=OzetTaslagi,
            dugum="ozetle",
        )

    amac, alan, llm_cagrisi = "", "belirtilmemis", 0
    taslak = _llm_dene("ozetle", _ozet_dene)
    if taslak is not None:
        amac, alan, llm_cagrisi = taslak.amac.strip(), taslak.alan.value, 1

    if not amac:
        # Determinist yedek. Kapak bilgisi sizabilir ama analiz durmaz;
        # ozet kritik yolda degildir.
        cumleler = [c.strip() for c in ilk_metin.split(". ") if len(c.strip()) > 20]
        amac = ". ".join(cumleler[:3]).strip()
        if amac and not amac.endswith("."):
            amac += "."

    # Ana bilesenler sozluk taramasindan gelir, tahmine gerek yoktur.
    bilesenler: list[str] = []
    for b in (secilen or bolumler):
        for giris, _ in teknoloji_tara(b.metin):
            if giris.ad not in bilesenler:
                bilesenler.append(giris.ad)

    ozet = BelgeOzeti(
        baslik=bolumler[0].baslik if bolumler else None,
        amac=amac or "Belgeden proje amaci cikarilamadi.",
        alan=alan or "belirtilmemis",
        ana_bilesenler=bilesenler[:8],
    )
    kayit(f"ozetle: {len(bilesenler)} bilesen, alan={alan}, "
          f"{'LLM' if llm_cagrisi else 'determinist yedek'}")
    return {"ozet": ozet, "iz": [_iz("ozetle", bas, {
        "okunan_bolum": len(secilen), "bilesen": len(bilesenler),
        "llm_cagrisi": llm_cagrisi,
    })]}


# ------------------------------------------------------------------ 3. cikar


def cikar_sozluk(durum: AnalizDurumu) -> dict:
    """Cikarimin determinist yarisi: LLM yok, ag yok, tekrarlanabilir.

    Tarama milisaniyeler surerken LLM hatti ayni belgede dakikalar alir.
    Ikisi ayri dugumlerde durdugu icin sozluk bulgulari saniyeler icinde
    SSE'den akar ve LLM bulgulari uzerine eklenir.

    Tarama `hedef_bolumler` ile sinirli degildir: sinirli olsaydi modulun
    "sozlukte olan hicbir sey kacmaz" garantisi yonlendirme dugumunun
    kararina bagli kalirdi. `karar == "hayir"` disindaki her bolum taranir.
    """
    bas = time.time()
    bolumler = [b for b in durum["bolumler"] if b.karar != "hayir"]
    olgular: list[Olgu] = []
    sayac = 0

    gorulen: set[str] = set()
    for bolum in bolumler:
        for giris, baglam in teknoloji_tara(bolum.metin):
            if giris.ad in gorulen:
                continue
            gorulen.add(giris.ad)
            sayac += 1
            olgular.append(Olgu(
                olgu_id=f"o{sayac:03d}",
                tur=OlguTuru.TEKNOLOJI,
                ad=giris.ad,
                aciklama=f"{giris.kategori} kategorisinde, veri ikametgahi: {giris.veri_ikametgahi}."
                         + (f" {giris.not_}" if giris.not_ else ""),
                arama_ifadesi=f"{giris.ad} {giris.kategori} data handling security",
                kaynak_bolum=bolum.baslik,
                alinti=baglam[:180],
                tespit_yontemi="sozluk",
            ))
        for tur, baglam in veri_turu_tara(bolum.metin):
            if tur in gorulen:
                continue
            gorulen.add(tur)
            sayac += 1
            olgular.append(Olgu(
                olgu_id=f"o{sayac:03d}",
                tur=OlguTuru.VERI_TURU,
                ad=tur.replace("_", " "),
                aciklama="Belgede bu veri turune isaret eden ifadeler gecti.",
                arama_ifadesi=f"{tur.replace('_', ' ')} personal data processing requirements",
                kaynak_bolum=bolum.baslik,
                alinti=baglam[:180],
                tespit_yontemi="sozluk",
            ))
    kayit(f"cikar_sozluk: {len(bolumler)} bolumde {len(olgular)} olgu "
          f"({time.time() - bas:.2f}s, LLM yok)")
    return {
        "olgular": olgular,
        "getirme_turu": 0,
        "iz": [_iz("cikar", bas, {
            "sozlukten": len(olgular),
            "taranan_bolum": len(bolumler),
            "llm_cagrisi": 0,
        })],
    }


# --------------------------------------------------- 3b. cikar (LLM dalgasi)

# Istem uzunlugu cikti kalitesini dogrudan etkiler: kucuk modeller uzun
# istem altinda talimati takip edemeyip cikti semasini bozuyor. Asagidaki
# metin kisa tutulmustur; tur listesi ve zorunlu kurallar durur, sema
# `description` alanlarinda zaten yazan aciklamalar cikarilmistir.
#
# ENJEKSIYON_UYARISI kisaltilmamalidir; belge icerigini talimattan ayiran
# tek sey odur.
CIKARIM_ISTEMI = (
    "Bir yazilim projesi raporundan risk tasiyabilecek OLGULARI cikariyorsun. "
    "Risk degerlendirmesi YAPMIYORSUN, sadece olgu topluyorsun.\n\n"
    "KAPSAM — HER TUR ICIN GECERLI: bu arac projenin DIS DUNYAYLA "
    "iliskisini inceler. Hangi ucuncu taraf kullaniliyor, hangi veri "
    "nereye gidiyor, kime hangi erisim veriliyor, hangi kisisel veri "
    "toplaniyor. Projenin KENDI IC YAPISI KAPSAM DISIDIR: kendi yazdigi "
    "moduller, siniflar, katmanlar, islev imzalari, bellek yonetimi, "
    "algoritma secimi, dosya bicimi, derleme zinciri. Arac koda bakmadigi "
    "icin bunlar hakkinda hicbir sey soyleyemez; bir muhendislik "
    "ayrintisini olgu olarak CIKARMA.\n\n"
    # Tur ornekleri kisaltilmamalidir. `tur` alani, KAYNAK_YONLENDIRME
    # uzerinden hangi bilgi tabaninin sorgulanacagini belirler; veri
    # akisini `dagitim` saymak LINDDUN yerine ASVS'ye gidip mahremiyet
    # kolunu tamamen atlatir.
    "Turler (DOGRU TURU SECMEK KRITIK):\n"
    "- veri_akisi: verinin bir SINIRI gecmesi. Ornek: 'fotograflar S3'e "
    "yuklenir', 'hasta verisi Firebase'de tutulur', 'metin OpenAI'ya "
    "gonderilir', 'jetonlar cihaz deposunda saklanir'. Sinir demek: baska "
    "bir bilesen, servis, veritabani, disk, cihaz deposu, ag ya da ucuncu "
    "taraf.\n"
    "  SUREC ICI BELLEK HAREKETI VERI AKISI DEGILDIR. Yigin, arabellek, "
    "degisken, gecici kopya, bellege esleme, onbellek nesnesi, RAM'de "
    "tutulan ara yapi — bunlar program ici ayrintilardir, olgu olarak "
    "CIKARMA. 'X bellekte tutulur', 'yigin yeniden kullanilir', 'dosya "
    "bellege eslenir' gibi cumleler bu arac icin olgu DEGILDIR; arac koda "
    "bakmadigi icin haklarinda hicbir sey soyleyemez.\n"
    "- veri_turu: belgede islendigi soylenen KISISEL VERI TURLERI. "
    "Ornek: 'ogrenci numarasi', 'saglik gecmisi', 'ses kaydi', "
    "'siparis gecmisi', 'IP adresi'. Sozluk yalnizca bilinen "
    "kaliplari yakalar; sozlukte olmayan ama BIR KISIYE BAGLANABILEN "
    "her veri turunu sen yaz. DIKKAT: bu tur verinin NE OLDUGUNU "
    "anlatir; verinin NEREYE GITTIGI veri_akisi'dir. 'Ad soyad ve "
    "telefon toplanir' -> veri_turu. 'Ad soyad Firebase'e yazilir' "
    "-> veri_akisi.\n"
    "- kimlik_dogrulama: oturum, token, parola, sifreleme ve YETKILENDIRME "
    "KONTROLU. Yetkilendirme ornekleri: 'kaynak kimligi istemciden geliyor', "
    "'rol kontrolu sunucuda yapiliyor', 'jeton yalnizca gecerlilik acisindan "
    "kontrol ediliyor'. Kimin neye erisebildigine dair her cumle bu turdur.\n"
    "- dagitim: uygulamanin KENDISININ nerede kostugu ve nasil yapilandirildigi. "
    "Ornek: 'sunucu Heroku'da barinir', 'Docker ile dagitilir'. SIR VE "
    "YAPILANDIRMA YONETIMI de bu turdur: API anahtari, parola, sertifika ve "
    "baglanti dizesinin NEREDE tutuldugu (kaynak kodda sabit, ortam degiskeni, "
    "kasa). Verinin nerede saklandigi DEGIL — o veri_akisi.\n"
    "- teknoloji: projenin KULLANDIGI, BASKASININ gelistirdigi servis ve "
    "kutuphaneler — yalnizca sana verilen listede olmayanlar. Projenin "
    "KENDI yazdigi modul, katman, cekirdek veya bilesen bu tur DEGILDIR; "
    "onlari cikarma.\n"
    "- eksik_bilgi: belgede anlatilanin gerektirdigi ama deginilmemis konular, "
    "en fazla 5 tane\n\n"
    "Sozluk yalnizca bilinen teknoloji ADLARINI yakalar; cumle icindeki "
    "DAVRANISI (veri nereye gidiyor, ne nerede saklaniyor, ne sifreleniyor) "
    "sen cikaracaksin.\n"
    "`ad` alanina belgede GECEN ifadeyi yaz; alintiyi metinden biz buluyoruz.\n"
    # Uc nokta adlari veri degildir: bir raporda gecen `GET /saglik`
    # denetim ucu, "saglik verisi islenmesi" seklinde hukuki bir bulguya
    # donusebiliyor. Yol, uc nokta ve degisken adlari kod
    # tanimlayicilaridir.
    "DIKKAT — kod tanimlayicilarini veri sanma: URL yollari, uc nokta "
    "adlari, degisken ve fonksiyon adlari (orn. `/saglik`, `/health`, "
    "`healthcheck`, `user_id`) yalnizca birer ISIMDIR. Icinde gecen kelime, "
    "o verinin islendigi anlamina GELMEZ. Bir veri turunun islendigini "
    "ancak belge acikca soyluyorsa yaz. BU KURAL YALNIZCA VERI TURU ICINDIR: "
    "bir tanimlayicinin NASIL kullanildigi (orn. degerin istemciden gelmesi, "
    "dosya adinda gecmesi) yine de cikarilmasi gereken bir olgudur.\n"
    "Olgu yoksa bos liste dondur. UYDURMA.\n\n"
    f"{ENJEKSIYON_UYARISI}"
)


def cikar_llm(durum: AnalizDurumu) -> dict:
    """Cikarimin LLM yarisi: sozlukte olmayan teknolojiler, veri akislari,
    kimlik dogrulama ayrintilari ve eksik bilgiler.

    `cikar_sozluk`un urettigi olgulara ekler, onlari degistirmez; bu dugum
    tamamen basarisiz olsa bile determinist bulgular ayakta kalir.

    Cikarilan `eksik_bilgi` olgulari burada hattan ayrilir ve
    `soru_isaretleri` olarak dondurulur; analiz zincirine girmezler.
    """
    bas = time.time()
    mevcut: list[Olgu] = list(durum.get("olgular") or [])
    sayac = len(mevcut)
    gorulen = {o.ad for o in mevcut}

    bolumler = [b for b in durum["bolumler"]
                if b.bolum_id in (durum.get("hedef_bolumler") or [])]
    if not bolumler:
        kayit("cikar_llm: hedef bolum yok, atlaniyor")
        return {"olgular": mevcut, "soru_isaretleri": [],
                "iz": [_iz("cikar_llm", bas, {"llm_den": 0}, "hedef bolum yok")]}

    # Bolumler parcalara bolunerek gonderilir. Kucuk modeller (<8B) tek
    # seferde cok sayida bolum aldiginda son bolumleri yuzeysel okur ve
    # olgu kacirir.
    bulunanlar = ", ".join(sorted(gorulen)) or "yok"
    llm_olgular: list[Olgu] = []
    adim = max(1, AYAR.cikarim_bolum_basi)

    # Butce: sure belge boyutundan bagimsiz olmali. Bolumler teknik
    # yogunluga gore siralanir ve yalnizca butce kadari LLM'e gider.
    # Sozluk taramasi tum bolumlerde calistigi icin bilinen teknolojiler
    # icin verilen garanti bozulmaz.
    def _teknik_puan(b) -> float:
        return (len(teknoloji_tara(b.metin)) * 3
                + len(veri_turu_tara(b.metin)) * 3
                + min(len(b.metin) / 1500, 3))

    butce = max(1, AYAR.cikarim_max_cagri) * adim
    if len(bolumler) > butce:
        secilen_bolumler = sorted(bolumler, key=_teknik_puan, reverse=True)[:butce]
        # Belge sirasina geri donulur; istem icinde bolumler dogal sirada durur.
        sira = {b.bolum_id: i for i, b in enumerate(bolumler)}
        secilen_bolumler.sort(key=lambda b: sira[b.bolum_id])
        kayit(f"cikar: butce {butce} bolum, {len(bolumler)} bolumden en teknik "
              f"olanlar secildi")
    else:
        secilen_bolumler = bolumler

    def _cagir(govde: str):
        return llm().yapisal(
            sistem=CIKARIM_ISTEMI,
            kullanici=(
                "Sozluk taramasi sunlari zaten buldu, bunlari TEKRARLAMA: "
                + bulunanlar + chr(10) + chr(10) + belge_blogu(govde)
            ),
            sema=OlguTaslakListesi,
            dugum="cikar",
        )

    def _parca_isle(bas_i: int) -> list[Olgu]:
        oebek = secilen_bolumler[bas_i:bas_i + adim]
        govde = (chr(10) + chr(10)).join(
            f"## {b.baslik}" + chr(10) + f"{b.metin[:AYAR.cikarim_bolum_karakter]}"
            for b in oebek
        )
        no = bas_i // adim + 1
        parca = _llm_dene(f"  parca {no}", lambda: _cagir(govde))
        if parca is None:
            # Sozluk katmani garanti verdigi icin analiz durmaz.
            return []
        kayit(f"  parca {no}: +{len(parca.olgular)} olgu")
        return parca.olgular

    # Parcalar birbirinden bagimsizdir ve es zamanli gonderilebilir.
    # `map` giris sirasini korudugu icin olgu_id atamasi determinist kalir.
    basliklar = list(range(0, len(secilen_bolumler), adim))
    taslaklar: list = []
    for sonuc in _es_zamanli_uygula(_parca_isle, basliklar):
        taslaklar.extend(sonuc)

    # Alintiyi Python cikarir; model kopyalamadigi icin alintinin belgede
    # gectigi kesindir. Bulunamazsa olgu yine de gecerlidir.
    bolum_metni = {b.baslik: b.metin for b in bolumler}
    for t in taslaklar:
        kaynak = bolum_metni.get(t.kaynak_bolum) or "\n".join(bolum_metni.values())
        alinti = _alinti_sec(kaynak, t.ad, t.aciklama)
        llm_olgular.append(Olgu(
            olgu_id="gecici",
            tur=t.tur,
            ad=t.ad,
            aciklama=t.aciklama,
            # Arama ifadesini Python kurar, model degil; bkz.
            # schemas.OlguTaslagi ve arama_ifadesi_kur.
            arama_ifadesi=arama_ifadesi_kur(t.tur, f"{t.ad} {alinti}"),
            kaynak_bolum=t.kaynak_bolum,
            alinti=alinti,
            tespit_yontemi="llm",
        ))

    # Eksik bilgiler hattan ayrilir: bir yoklugun kaniti olamaz. Bunlari
    # getir/analiz/dogrula zincirine sokmak, belgede olmayan bir sey icin
    # standart aranmasina yol acar. Kanit aranmadan, ciktinin altinda kisa
    # bir liste olarak sunulurlar.
    soru_isaretleri: list[SoruIsareti] = []
    gorulen_soru: set[str] = set()
    for o in llm_olgular:
        if o.tur == OlguTuru.EKSIK_BILGI:
            # Istemdeki "en fazla 5" kurali cagri basina isler; belge geneli
            # sinir burada uygulanir.
            anahtar = o.ad.strip().lower()
            if (anahtar and anahtar not in gorulen_soru
                    and len(soru_isaretleri) < AYAR.soru_isareti_ust_sinir):
                gorulen_soru.add(anahtar)
                soru_isaretleri.append(SoruIsareti(
                    baslik=o.ad.strip()[:120],
                    kaynak_bolum=o.kaynak_bolum,
                ))
            continue
        # Ayni teknolojiyi sozluk zaten bulduysa tekrar ekleme.
        if o.ad in gorulen:
            continue
        gorulen.add(o.ad)
        sayac += 1
        o.olgu_id = f"o{sayac:03d}"
        o.tespit_yontemi = "llm"
        mevcut.append(o)

    eklenen = len([o for o in mevcut if o.tespit_yontemi == "llm"])
    kayit(f"cikar_llm: +{eklenen} olgu (toplam {len(mevcut)}), "
          f"{len(soru_isaretleri)} soru isareti ayrildi")
    return {
        # Sozluk olgularina eklenir, onlar degistirilmez; bu dugum tamamen
        # basarisiz olsa bile determinist olgular durumda kalir.
        "olgular": mevcut,
        "soru_isaretleri": soru_isaretleri,
        # Getirme sayaci sifirlanir; dalga 1'in getirme gecisi dalga 2'nin
        # sorgu yeniden yazma butcesini harcamamalidir.
        "getirme_turu": 0,
        "iz": [_iz("cikar_llm", bas, {
            "llm_den": eklenen,
            "toplam_olgu": len(mevcut),
            "soru_isareti": len(soru_isaretleri),
        })],
    }


# ------------------------------------------------------------------ 4. getir


def getir(durum: AnalizDurumu) -> dict:
    """Getirici ajan. Her olgu bir sorguya donusur.

    Skorlar esigin altinda kalirsa olgu 'zayif' isaretlenir ve graf sorgu
    yeniden yazma dugumune dallanir. Turkce olgu ile Ingilizce OWASP metni
    eslestirilirken bu dongu ise yarar.
    """
    bas = time.time()
    kanitlar: dict[str, list[Kanit]] = dict(durum.get("kanitlar") or {})
    zayif: list[str] = []
    yedekle_kurtarilan = 0
    # Kaniti olan olgu bir daha sorgulanmaz: kural, kanitlanmamis olanin
    # sorgulanmasidir. Sorgu yeniden yazma dongusu de buna uyar; zayif
    # olgunun kaniti olmadigi icin yeniden yazilan sorguyla tekrar denenir.
    hedefler = [o.olgu_id for o in durum["olgular"] if o.olgu_id not in kanitlar]
    olgu_haritasi = {o.olgu_id: o for o in durum["olgular"]}

    def _ara(olgu: Olgu, sorgu: str) -> list[Kanit]:
        # Alaka elemesi aramanin icinde yapilir; burada kalan is sayiyi
        # sinirlamaktir. Fuzyon skoruna esik konmaz, o skor sira tabanlidir.
        vurus = vectorstore.hibrit_ara(
            AYAR.kb_collection,
            sorgu,
            limit=AYAR.retrieval_top_k,
            kaynak_turleri=KAYNAK_YONLENDIRME.get(olgu.tur),
            benzerlik_esigi=AYAR.retrieval_benzerlik_esigi,
        )
        return [
            Kanit(kaynak_turu=v["kaynak_turu"], kaynak_kimlik=v["kaynak_kimlik"],
                  baslik=v["baslik"], ozet=v["metin"][:400],
                  skor=round(v["skor"], 4), url=v.get("url"))
            for v in vurus[:AYAR.kanit_basi_ust_sinir]
        ]

    for olgu_id in hedefler:
        olgu = olgu_haritasi[olgu_id]
        gecerli = _ara(olgu, olgu.arama_ifadesi)
        # LLM'e dallanmadan once maliyetsiz bir ikinci deneme: olgu kanit
        # bulamadiysa sozluk omurgasindan kurulan determinist sorgu
        # denenir. Alternatifi `sorgu_yaz` dugumune dallanmak, yani tam bir
        # LLM cagrisidir; bu deneme milisaniyeler surer.
        if not gecerli:
            yedek_sorgu = arama_ifadesi_kur(olgu.tur, f"{olgu.ad} {olgu.alinti}")
            if yedek_sorgu.strip() and yedek_sorgu != olgu.arama_ifadesi:
                gecerli = _ara(olgu, yedek_sorgu)
                if gecerli:
                    olgu.arama_ifadesi = yedek_sorgu
                    yedekle_kurtarilan += 1

        if gecerli:
            kanitlar[olgu_id] = gecerli
        else:
            zayif.append(olgu_id)

    seyreltilen = _ayirt_etmeyen_kanitlari_seyrelt(kanitlar, hedefler)

    tur = durum.get("getirme_turu", 0) + 1
    kayit(f"getir (tur {tur}): {len(hedefler) - len(zayif)}/{len(hedefler)} olgu kanitlandi"
          + (f" ({yedekle_kurtarilan}'i determinist yedek sorguyla)" if yedekle_kurtarilan else "")
          + (f", {seyreltilen} ayirt etmeyen kanit birakildi" if seyreltilen else ""))
    return {
        "kanitlar": kanitlar,
        "zayif_olgular": zayif,
        "getirme_turu": tur,
        "iz": [_iz("getir", bas, {
            "tur": tur,
            "sorgulanan_olgu": len(hedefler),
            "kanit_bulunan": len(hedefler) - len(zayif),
            "yedek_sorguyla": yedekle_kurtarilan,
            "zayif_kalan": len(zayif),
        })],
    }


def sorgu_yaz(durum: AnalizDurumu) -> dict:
    """Zayif kalan olgularin arama ifadesini yeniden yazar."""
    bas = time.time()
    olgu_haritasi = {o.olgu_id: o for o in durum["olgular"]}
    zayif = durum["zayif_olgular"]

    liste = "\n".join(
        f"{oid} | mevcut sorgu: {olgu_haritasi[oid].arama_ifadesi} "
        f"| olgu: {olgu_haritasi[oid].ad} — {olgu_haritasi[oid].aciklama}"
        for oid in zayif
    )
    # Cagri korumali yapilir: burada cikan bir istisna LangGraph'a kadar
    # cikip tum analizi durdurur, oysa determinist bulgular dalga 1'de
    # hazirdir. Basarisizlikta sorgular oldugu gibi kalir ve
    # `zayif_olgular` bosaltilir; boylece getirme dongusu temiz biter
    # (bkz. getirme_karari) ve ayni sorgularla sonsuz tur atilmaz.
    try:
        yeni = llm().metin(
            sistem=(
                "Bu arama ifadeleri OWASP ASVS, CWE, LINDDUN ve KVKK metinlerinde "
                "yeterince iyi eslesmedi. Her biri icin DAHA IYI, daha standart "
                "terminoloji kullanan yeni bir Ingilizce sorgu yaz. Urun adi yerine "
                "guvenlik kavramini hedefle: 'Firebase' yerine 'third-party managed "
                "database data residency access control' gibi.\n"
                "Cikti formati, her satirda: olgu_id|yeni sorgu"
            ),
            kullanici=liste,
            sicaklik=0.3,
            dugum="sorgu_yaz",
        )
    except Exception as hata:  # noqa: BLE001
        kayit(f"sorgu_yaz: basarisiz ({type(hata).__name__}: {str(hata)[:120]}), "
              f"sorgular oldugu gibi birakildi")
        return {
            "zayif_olgular": [],
            "iz": [_iz("sorgu_yaz", bas, {"yeniden_yazilan": 0}, "atlandi")],
        }


    guncellenen = 0
    for satir in yeni.strip().splitlines():
        if "|" not in satir:
            continue
        oid, sorgu = satir.split("|", 1)
        oid = oid.strip()
        if oid in olgu_haritasi:
            olgu_haritasi[oid].arama_ifadesi = sorgu.strip()
            guncellenen += 1

    return {
        "olgular": list(olgu_haritasi.values()),
        "iz": [_iz("sorgu_yaz", bas, {"yeniden_yazilan": guncellenen})],
    }


# ------------------------------------------------------------------ 5. analiz


def analiz_determinist(durum: AnalizDurumu) -> dict:
    """Dalga 1'in analizi: yalnizca sablon, LLM cagrisi yok.

    Dalga 1'in vaadi saniyeler icinde dayanakli sonuctur; buraya bir LLM
    cagrisi girerse ilk bulgu suresi tekrar dakikalara cikar.
    """
    return _analiz(durum, llm_butcesi=0)


def analiz_llm(durum: AnalizDurumu) -> dict:
    """Dalga 2'nin analizi: risk sirasina gore ilk N bulguyu analist yazar."""
    return _analiz(durum, llm_butcesi=max(0, AYAR.analiz_llm_bulgu_sayisi))


def _analiz(durum: AnalizDurumu, llm_butcesi: int) -> dict:
    """Analist ajan. Olgu ve kanit eslesmesinden temkinli bulgu uretir.

    Iki yol vardir:
    - Risk sirasina gore ilk `llm_butcesi` olgu LLM hattina girer.
    - Geri kalanlar `sablon` modulunde determinist kurulur (bkz.
      core/sablon.py).

    LLM'e giden olgular parcalara bolunerek gonderilir. Tek seferde
    hepsini vermek kucuk modellerde ciktiyi uzatir (kisitli cozumleme
    yavaslar) ve son olgular yuzeysel islenir.
    """
    bas = time.time()
    olgu_haritasi = {o.olgu_id: o for o in durum["olgular"]}
    olgu_turu = {o.olgu_id: o.tespit_yontemi for o in durum["olgular"]}
    kanitlar = durum["kanitlar"]
    # Onceki dalganin bulgulari korunur; bu gecis yalnizca yeni olgulari
    # isler, dolayisiyla cakisma olmaz.
    onceki = list(durum.get("bulgular") or [])

    # Zaten bulgusu olan olgu tekrar islenmez. Iki dalgali hatta bu dugum
    # iki kez calisir; kontrol olmazsa ikinci gecis birinci dalganin sablon
    # bulgularini bastan kurar ve `bulgu_id` uuid4 oldugu icin arayuzdeki
    # butun kartlar yeniden olusturulur.
    islenmis = {oid for b in onceki for oid in b.belge_dayanagi}
    adaylar = sorted(oid for oid in kanitlar if oid not in islenmis)

    # Butce risk sirasina gore dagitilir. Analist ajanin butcesi sinirli
    # oldugu icin olgular risk puanina gore siralanir; ilk N olgu analiste
    # gider, kalani sablondan kurulur ve `risk_sirasi` onlari listenin
    # altina koyar.
    adaylar.sort(key=lambda oid: (
        -sablon.risk_puani(olgu_haritasi[oid], kanitlar[oid]), oid))

    # Gurultu filtresi, bulgu uretilmeden once ve her iki yol icin
    # calisir: yerel cerceve olgulari ne LLM butcesini ne sablonu
    # harcamalidir (bkz. sablon.gurultu_mu).
    gurultu = {oid for oid in adaylar if sablon.gurultu_mu(olgu_haritasi[oid])}
    if gurultu:
        adaylar = [oid for oid in adaylar if oid not in gurultu]
        kayit(f"analiz: {len(gurultu)} yerel cerceve olgusu bulgu disi birakildi")
    hedef_olgular = adaylar[:llm_butcesi]

    sablon_bulgular: list[Bulgu] = []
    atlanan = 0
    for oid in adaylar[llm_butcesi:]:
        b = sablon.sablonla(olgu_haritasi[oid], kanitlar[oid])
        if b is None:
            # Dolgu bulgu uretilmez; genel bir sablon okura bilgi vermeyen
            # metin uretir. Olgu kaybolmaz, `olgular` listesinde durur ve
            # arayuzde gorunur.
            atlanan += 1
            continue
        sablon_bulgular.append(b)

    if adaylar:
        puanlar = [sablon.risk_puani(olgu_haritasi[o], kanitlar[o]) for o in adaylar]
        kayit(f"analiz: {len(adaylar)} olgu, risk puanlari "
              f"{puanlar[0]}..{puanlar[-1]}; ilk {len(hedef_olgular)} analiste, "
              f"{len(sablon_bulgular)} sablona")
    if atlanan:
        kayit(f"analiz: {atlanan} olgu icin sablon kurulamadi, dolgu bulgu uretilmedi")

    if not hedef_olgular:
        birlesik = sablon.tekillestir(onceki + sablon_bulgular, olgu_turu)
        birlesen = len(onceki) + len(sablon_bulgular) - len(birlesik)
        kayit(f"analiz: LLM'e olgu gitmedi, {len(sablon_bulgular)} sablon bulgu dondu"
              + (f", {birlesen} tekrar birlestirildi" if birlesen else ""))
        return {"bulgular": sorted(birlesik, key=sablon.risk_sirasi),
                "iz": [_iz("analiz", bas, {
                    "uretilen_bulgu": 0,
                    "sablondan": len(sablon_bulgular),
                }, "LLM'e giden olgu yok")]}

    adim = max(1, AYAR.analiz_olgu_basi)

    def _yigin_isle(i: int) -> list:
        oebek = hedef_olgular[i:i + adim]
        paket = []
        for oid in oebek:
            o = olgu_haritasi[oid]
            kaynaklar = "\n".join(
                f"    - [{k.kaynak_kimlik}] {k.baslik}: {k.ozet[:220]}"
                for k in kanitlar[oid][:AYAR.kanit_basi_ust_sinir]
            )
            paket.append(
                f"OLGU {oid} ({o.tur.value})\n"
                f"  ad: {o.ad}\n"
                f"  aciklama: {o.aciklama}\n"
                f"  belgedeki bolum: {o.kaynak_bolum}\n"
                f'  alinti: "{o.alinti}"\n'
                f"  eslesen kaynaklar:\n{kaynaklar}"
            )
        # Atif alanlari bu yiginin kimliklerine kilitlenir. Kisitsiz semada
        # analist var olmayan kaynak veya olgu kimligi gosterebiliyor ve
        # bulgu dayanak kontrolunde eleniyor. Enum kimligi dilbilgisine
        # koyar; model listede olmayani uretemez (bkz.
        # schemas.kisitli_bulgu_semasi).
        kaynak_kimlikleri = sorted({
            k.kaynak_kimlik for oid in oebek for k in kanitlar[oid][:AYAR.kanit_basi_ust_sinir]
        })
        no = i // adim + 1
        cikti = _llm_dene(f"  parca {no}", lambda: llm().yapisal(
            sistem=ANALIZ_ISTEMI,
            kullanici=(chr(10) + chr(10)).join(paket),
            sema=kisitli_bulgu_semasi(list(oebek), kaynak_kimlikleri),
            dugum="analiz",
        ))
        if cikti is None:
            return []
        kayit(f"  parca {no}: +{len(cikti.bulgular)} bulgu")
        return cikti.bulgular

    # Yiginlar bagimsizdir; sira korunarak es zamanli gonderilir.
    taslaklar = []
    for sonuc in _es_zamanli_uygula(_yigin_isle, list(range(0, len(hedef_olgular), adim))):
        taslaklar.extend(sonuc)

    # Taslaklar tam Bulgu'ya cevrilir: Kanit nesnelerini Python birlestirir,
    # boylece model kanit icerigini uyduramaz.
    kimlik_haritasi: dict[str, Kanit] = {}
    for liste in kanitlar.values():
        for k in liste:
            kimlik_haritasi.setdefault(k.kaynak_kimlik, k)

    bulgular: list[Bulgu] = []
    elenen_taslak: list[ElenenBulgu] = []
    for t in taslaklar:
        gecerli_kaynak = [kimlik_haritasi[k] for k in t.kaynak_kimlikleri if k in kimlik_haritasi]
        gecerli_olgu = [o for o in t.belge_dayanagi if o in olgu_haritasi]
        if not gecerli_kaynak or not gecerli_olgu:
            # Dayanaksiz taslak sessizce atilmaz; ret nedeni kaydedilir ve
            # arayuzde gorunur.
            neden = ("Atifta gecen kaynak getirilen kanitlar arasinda yok"
                     if not gecerli_kaynak else
                     "Bulgu hicbir gecerli olguya dayanmiyor")
            elenen_taslak.append(ElenenBulgu(baslik=t.baslik, ret_nedeni=neden))
            continue
        bulgular.append(Bulgu(
            bulgu_id=f"f{uuid.uuid4().hex[:6]}",
            alan=t.alan,
            kesinlik=t.kesinlik,
            baslik=_basligi_temizle(t.baslik),
            # Dilbilgisi siniri cumlenin ortasinda kesmis olabilir; yarim
            # kalan son cumle kullaniciya gosterilmez.
            aciklama=_yarim_cumleyi_at(t.aciklama),
            kontrol_onerisi=_yarim_cumleyi_at(t.kontrol_onerisi),
            belge_dayanagi=gecerli_olgu,
            kaynak_dayanagi=gecerli_kaynak,
            ilgili_bolumler=sorted({olgu_haritasi[o].kaynak_bolum for o in gecerli_olgu}),
        ))

    # Ayni bileseni anlatan bulgular kayipsiz birlestirilir ve bariz
    # riskler one alinir (bkz. sablon.tekillestir ve sablon.risk_sirasi).
    bulgular = sorted(
        sablon.tekillestir(onceki + sablon_bulgular + bulgular, olgu_turu),
        key=sablon.risk_sirasi,
    )

    kayit(f"analiz: {len(taslaklar)} taslak -> {len(bulgular)} bulgu"
          + (f", {len(elenen_taslak)} dayanaksiz elendi" if elenen_taslak else ""))
    return {
        "bulgular": bulgular,
        "elenenler": list(durum.get("elenenler") or []) + elenen_taslak,
        "iz": [_iz("analiz", bas, {
            "uretilen_bulgu": len(taslaklar),
            "sablondan": len(sablon_bulgular),
            "dayanaksiz_elenen": len(elenen_taslak),
        })],
    }


# ------------------------------------------------------------------ 6. dogrula


def dogrula(durum: AnalizDurumu) -> dict:
    """Dogrulayici ajan.

    Once makine kontrolu calisir: dayanaklar var mi, atifta gecen kaynak
    kimligi gercekten getirilmis mi? Sonra LLM kontrolu: dil temkinli mi,
    iddia kanittan buyuk mu?
    """
    bas = time.time()
    bulgular = durum["bulgular"]
    kanitlar = durum["kanitlar"]
    gecerli_olgular = {o.olgu_id for o in durum["olgular"]}
    gecerli_kimlikler = {k.kaynak_kimlik for liste in kanitlar.values() for k in liste}

    kabul: list[Bulgu] = []
    elenen: list[ElenenBulgu] = list(durum.get("elenenler") or [])
    # Denetci 'revizyon' dedigi halde duzeltilmis metni vermediginde
    # sayisi ize yazilir; artiyorsa denetci istemi gozden gecirilmelidir.
    duzeltmesiz: list[str] = []

    # --- makine kontrolu ---
    aday: list[Bulgu] = []
    for b in bulgular:
        if not b.belge_dayanagi or not any(o in gecerli_olgular for o in b.belge_dayanagi):
            elenen.append(ElenenBulgu(baslik=b.baslik, ret_nedeni="Belge dayanagi yok veya gecersiz olgu id"))
            continue
        gercek = [k for k in b.kaynak_dayanagi if k.kaynak_kimlik in gecerli_kimlikler]
        if not gercek:
            elenen.append(ElenenBulgu(baslik=b.baslik, ret_nedeni="Atifta gecen kaynak getirilen kanitlar arasinda yok"))
            continue
        b.kaynak_dayanagi = gercek
        aday.append(b)

    makine_elenen = len(bulgular) - len(aday)

    # Sablon bulgulari LLM denetimine girmez: metinlerini kod yazar, dil
    # sabit ve temkinlidir, kaynak metni bilgi tabanindan oldugu gibi
    # gelir. Makine kontrolu yukarida onlara da uygulanmistir. Denetciye
    # yalnizca LLM'in yazdiklari gider; dugumun maliyeti denetlenen bulgu
    # sayisiyla orantilidir.
    sablon_kabul = [b for b in aday if b.uretim == "sablon"]
    aday = [b for b in aday if b.uretim != "sablon"]
    kabul.extend(sablon_kabul)

    # Mahremiyet konusu var mi? Determinist kontrol, LLM'den once calisir.
    #
    # `_liste` denetciye yalnizca baslik, aciklama, oneri ve kaynak
    # kimliklerini verir; denetci belgeyi ve olgulari gormez, dolayisiyla
    # "konu disi mi?" sorusunu tek basina cevaplayamaz. En acik durum
    # burada makineyle kesilir: bir belgede (a) hicbir kisisel veri
    # isaretcisi, (b) veriyi disari cikarabilecek bir bilesen ve (c)
    # hicbir `veri_turu` olgusu yoksa `veri_sizintisi` ve `hukuki`
    # bulgulari konusuz sayilir.
    #
    # `guvenlik` bulgulari bundan muaftir: kisisel veri islemeyen bir
    # projede de kaynak kodda sabit anahtar gercek bir bulgudur.
    #
    # Elenen bulgu gerekcesiyle birlikte `elenenler` listesine girer ve
    # arayuzde gorunur; sessiz silme yapilmaz.
    def _mahremiyet_konusu() -> tuple[bool, list[str], list[str]]:
        metin = (chr(10) + chr(10)).join(
            b.metin for b in (durum.get("bolumler") or []))
        veri_turleri = sorted({a for a, _ in veri_turu_tara(metin)})
        # `degisken` de sayilir: ikametgahi belirsiz bir bilesen veriyi
        # disari cikariyor olabilir, kontrol temkinli tarafta tutulur.
        disari = sorted({g.ad for g, _ in teknoloji_tara(metin)
                         if g.veri_ikametgahi in ("harici", "degisken")})
        olgu_veri = any(o.tur is OlguTuru.VERI_TURU
                        for o in (durum.get("olgular") or []))
        return bool(veri_turleri or disari or olgu_veri), veri_turleri, disari

    konu_var, veri_turleri, disari_cikaran = _mahremiyet_konusu()
    if not konu_var and aday:
        kalan: list[Bulgu] = []
        for b in aday:
            if b.alan in (RiskAlani.VERI_SIZINTISI, RiskAlani.HUKUKI):
                elenen.append(ElenenBulgu(
                    baslik=b.baslik,
                    ret_nedeni=(
                        "Belgede kisisel veri islendigine ve verinin disari "
                        "ciktigina dair hicbir olgu yok; mahremiyet ve hukuki "
                        "risk bu projede konusuz."),
                ))
            else:
                kalan.append(b)
        if len(kalan) < len(aday):
            kayit(f"dogrula: belgede kisisel veri yok, "
                  f"{len(aday) - len(kalan)} mahremiyet bulgusu elendi")
        aday = kalan

    # --- LLM kontrolu ---
    DENETCI = (
        "Risk bulgularini denetliyorsun. Her bulgu icin DORT seyi kontrol et:\n"
        "1. Dil temkinli mi? Kesin hukum ('acik vardir', 'ihlaldir') iceriyorsa "
        "   karar 'revizyon'.\n"
        "2. Iddia, dayandigi kaynaktan buyuk mu? Kaynak genel bir gereksinimken "
        "   bulgu spesifik bir zafiyet iddia ediyorsa karar 'revizyon'.\n"
        "3. Bulgu tamamen dayanaksiz veya konu disi mi? Karar 'ret'.\n"
        "4. KONUSU VAR MI? Ustteki PROJE BAGLAMI blogunu oku. Bulgu, "
        "   bu projede VAR OLMAYAN bir seyi korumaya calisiyorsa karar "
        "   'ret'. Ornek: baglamda kisisel veri turu YOK yazarken "
        "   yazilmis bir mahremiyet/hukuki bulgusu; veya disari veri "
        "   cikaran bilesen YOK yazarken yazilmis bir sizinti bulgusu. "
        "   Kisiye baglanamayan veriler (olcum, sensor, bitki/malzeme "
        "   goruntusu, kamuya acik derlem, simulasyon ciktisi) icin "
        "   sizinti veya mahremiyet iddiasi konusuzdur.\n"
        "Sorun yoksa 'kabul'. Gereksiz yere reddetme; amac dogruluk, "
        "hepsini elemek degil. Ama KONUSU OLMAYAN bir bulguyu da kabul "
        "etme — o bulgu kullaniciya gercek bulgulari gizleyen gurultu "
        "olarak gider.\n\n"
        "'revizyon' diyorsan `duzeltilmis_aciklama` alanini MUTLAKA doldur: "
        "bulgunun senin kurallarina uyan halini oraya yaz. Bos birakirsan "
        "bulgu bastan uretilmek zorunda kalir ve bu cok pahalidir. "
        "Sorunu gorebiliyorsan duzeltilmis cumleyi de yazabilirsin."
    )

    def _liste(bulgular_: list[Bulgu]) -> str:
        ozet_ = durum.get("ozet")
        baglam = (
            "PROJE BAGLAMI — bir bulgunun KONUSU olup olmadigini "
            "bununla degerlendir:\n"
            f"  amac: {ozet_.amac if ozet_ else 'bilinmiyor'}\n"
            f"  alan: {ozet_.alan.value if ozet_ else 'bilinmiyor'}\n"
            f"  belgede tespit edilen kisisel veri turleri: "
            f"{', '.join(veri_turleri) or 'YOK'}\n"
            f"  veriyi disari cikarabilecek bilesenler: "
            f"{', '.join(disari_cikaran) or 'YOK'}\n\n"
        )
        return baglam + "\n\n".join(
            f"BULGU {b.bulgu_id} [{b.alan.value} / {b.kesinlik.value}]\n"
            f"  baslik: {b.baslik}\n"
            f"  aciklama: {b.aciklama}\n"
            f"  oneri: {b.kontrol_onerisi}\n"
            f"  dayandigi kaynaklar: {', '.join(k.kaynak_kimlik for k in b.kaynak_dayanagi)}"
            for b in bulgular_
        )

    def _uygula(b: Bulgu, karar: VerifierKarari) -> None:
        if karar.karar == "ret":
            elenen.append(ElenenBulgu(baslik=b.baslik, ret_nedeni=karar.gerekce))
        elif karar.karar == "revizyon":
            # Revizyon yerinde yapilir, bulgu analize geri gonderilmez:
            # geri gondermek analiz dugumunu bastan calistirir ve yeni bir
            # LLM turu demektir. Denetci duzeltmeyi vermediyse bulgu oldugu
            # gibi kabul edilir ve sayisi ize yazilir.
            if karar.duzeltilmis_aciklama:
                b.aciklama = karar.duzeltilmis_aciklama
            else:
                duzeltmesiz.append(b.bulgu_id)
            kabul.append(b)
        else:
            kabul.append(b)

    if AYAR.dogrulama_llm and aday:
        if AYAR.dogrulama_toplu:
            # Tek cagri, iki deneme. Bu dugum hattin sonunda durdugu icin
            # dustugunde kaybedilen yalnizca denetim katmanidir; uc deneme
            # kotayi gereksiz harcar, tek deneme ise gecici hatalara karsi
            # yetersiz kalir.
            cikti = _llm_dene("dogrula", lambda: llm().yapisal(
                sistem=DENETCI + "\n\nHER bulgu icin bir karar dondur, hicbirini atlama.",
                kullanici=_liste(aday),
                sema=VerifierKararListesi,
                dugum="dogrula",
            ), deneme=2)
            if cikti is None:
                # Denetimin calismadigi, calisip bir sey bulmamasindan
                # farkli bir bilgidir; log'a yazilir.
                kayit(f"dogrula: LLM denetimi calismadi, "
                      f"{len(aday)} bulgu denetlenmeden kabul edildi")
                kabul.extend(aday)  # makine kontrolu gecerli kalir
            else:
                haritali = {k.bulgu_id: k for k in cikti.kararlar}
                for b in aday:
                    karar = haritali.get(b.bulgu_id)
                    # Karar donmemis bulgu elenmez, denetlenmemis sayilip
                    # kabul edilir.
                    if karar:
                        _uygula(b, karar)
                    else:
                        kabul.append(b)
        else:
            for b in aday:
                try:
                    karar = llm().yapisal(
                        sistem=DENETCI,
                        kullanici=f"{_liste(aday)}\n\n---\nSimdi SADECE {b.bulgu_id} icin karar ver.",
                        sema=VerifierKarari,
                        dugum="dogrula",
                    )
                    _uygula(b, karar)
                except Exception:
                    kabul.append(b)
    else:
        kabul.extend(aday)

    kayit(f"dogrula: {len(kabul)} kabul, {len(elenen)} elendi, "
          f"{len(duzeltmesiz)} duzeltmesiz revizyon istegi")
    return {
        "bulgular": kabul,
        "elenenler": elenen,
        "iz": [_iz("dogrula", bas, {
            "denetlenen": len(bulgular),
            "kabul": len(kabul),
            "elenen": len(elenen),
            "makine_elenen": makine_elenen,
            "sablon_muaf": len(sablon_kabul),
            "llm_denetlenen": len(aday),
            "duzeltmesiz": len(duzeltmesiz),
        })],
    }


# ------------------------------------------------------------- kosullu kenarlar


def getirme_karari(durum: AnalizDurumu) -> str:
    """Zayif olgu kaldi mi ve tur hakki var mi?"""
    if durum.get("zayif_olgular") and durum.get("getirme_turu", 0) < AYAR.max_retrieval_rounds:
        return "sorgu_yaz"
    return "analiz"
