"""Boru hattinin veri sozlesmesi.

LLM'in uretebilecegi her sey burada tanimli bir semaya uymak zorundadir.
`kesinlik` alani uc kademelidir; sistem kesin iddia uretmez.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- taksonomi


class RiskAlani(str, Enum):
    GUVENLIK = "guvenlik"
    VERI_SIZINTISI = "veri_sizintisi"
    HUKUKI = "hukuki"


# Uc kademeli, temkinli olcek:
#
# GOZLEM       -> raporda acikca yazan bir olgu aktarilir
# OLASI        -> olgu ve standart eslesmesinden cikan bir ihtimal
# DOGRULANMALI -> raporda bilgi eksik, kontrol edilmesi onerilir
class Kesinlik(str, Enum):

    GOZLEM = "gozlem"
    OLASI = "olasi"
    DOGRULANMALI = "dogrulanmali"


# Projenin uygulama alani; serbest metin degil enum.
#
# Serbest metin alaninda model her kosumda farkli bir etiket yaziyor ve
# kisa alana duzyazi yazdiginda dilbilgisi metni ortadan kesiyor. Enum bu
# durumu yapisal olarak engeller: strict semada dilbilgisine cevrilir ve
# model listede olmayani uretemez. Kod tabanindaki diger siniflandirmalar
# (OlguTuru, RiskAlani, Kesinlik) da enum'dur.
class UygulamaAlani(str, Enum):

    EGITIM = "egitim"
    SAGLIK = "saglik"
    FINTEK = "fintek"
    ETICARET = "e-ticaret"
    KAMU = "kamu"
    ULASIM = "ulasim"
    MEDYA = "medya"
    SOSYAL = "sosyal"
    KURUMSAL = "kurumsal"
    IOT = "iot"
    OYUN = "oyun"
    AKADEMIK = "akademik"
    DIGER = "diger"
    BELIRTILMEMIS = "belirtilmemis"


class OlguTuru(str, Enum):
    TEKNOLOJI = "teknoloji"       # Firebase, S3, OpenAI API...
    VERI_TURU = "veri_turu"       # kimlik, konum, saglik, biyometrik
    VERI_AKISI = "veri_akisi"     # "fotograflar sunucuya yuklenir"
    KIMLIK_DOGRULAMA = "kimlik_dogrulama"
    DAGITIM = "dagitim"           # hosting, deployment
    EKSIK_BILGI = "eksik_bilgi"   # raporda hic bahsedilmeyen konu


# ---------------------------------------------------------------- belge


# Belgenin bolum farkindalikli parcasi.
class Bolum(BaseModel):

    bolum_id: str
    baslik: str
    seviye: int = 1
    metin: str
    sayfa_baslangic: int | None = None
    # Bu bolum derin analize deger mi? Ayristirma ucuz bir sezgisel kuralla
    # doldurur, `belirsiz` kalanlara yonlendirme dugumu karar verir.
    #
    # Alan uc durumludur: ikili olsaydi bilinmeyen basliklarin tamami bir
    # tarafa dusecekti, oysa gercek bir tezde basliklarin cogu iki listeye
    # de uymaz.
    karar: Literal["evet", "hayir", "belirsiz"] = "belirsiz"


class BelgeOzeti(BaseModel):
    baslik: str | None = None
    amac: str = Field(description="Projenin amaci, 2-3 cumle")
    alan: str = Field(description="Uygulama alani, orn. 'saglik', 'fintek'")
    ana_bilesenler: list[str] = Field(default_factory=list, max_length=8)


# ---------------------------------------------------------------- olgu


# Belgeden cikarilan, risk tasiyabilecek atomik bir tespit.
#
# Her olgu bir getirme sorgusuna donusur. `arama_ifadesi` bu yuzden ayri
# bir alandir: olgunun kendisi Turkce, bilgi tabani buyuk olcude
# Ingilizcedir.
class Olgu(BaseModel):

    olgu_id: str
    tur: OlguTuru
    ad: str = Field(description="Kisa etiket, orn. 'Firebase Realtime Database'")
    aciklama: str = Field(description="Olgunun belgedeki karsiligi, 1 cumle")
    arama_ifadesi: str = Field(description="Bilgi tabani icin normalize sorgu (EN)")
    kaynak_bolum: str = Field(description="Hangi bolumden cikti")
    alinti: str = Field(description="Belgeden birebir kisa alinti, max 25 kelime")
    # Determinist sozlukten mi geldi, LLM mi cikardi
    tespit_yontemi: Literal["sozluk", "llm", "her_ikisi"] = "llm"


# ---------------------------------------------------------------- kanit


# Bilgi tabanindan cekilen, bir olguyla eslesen kaynak.
class Kanit(BaseModel):

    kaynak_turu: str          # asvs | cwe | linddun | kvkk | gdpr | saglayici
    kaynak_kimlik: str        # "ASVS 8.3.4", "CWE-311", "KVKK m.12"
    baslik: str
    ozet: str
    skor: float
    url: str | None = None


# ---------------------------------------------------------------- bulgu


# Kullaniciya gosterilen nihai cikti.
#
# `belge_dayanagi` ve `kaynak_dayanagi` bos olan bir bulgu kullaniciya
# ulasmaz; dogrulayici dugumu bunu zorunlu tutar.
class Bulgu(BaseModel):

    bulgu_id: str
    alan: RiskAlani
    kesinlik: Kesinlik
    baslik: str = Field(max_length=120)
    # Temkinli dil zorunludur; sema aciklamasi isteme de gider.
    aciklama: str = Field(
        description=(
            "Teknolojinin veri alisverisini nasil yaptigini kisaca anlatir ve "
            "kontrol edilmesini onerir. 'Acik vardir', 'guvensizdir' gibi "
            "kesin ifadeler KULLANILMAZ."
        )
    )
    kontrol_onerisi: str = Field(description="Kullanicinin dogrulamasi gereken tek soru")
    belge_dayanagi: list[str] = Field(min_length=1, description="olgu_id listesi")
    kaynak_dayanagi: list[Kanit] = Field(min_length=1)
    ilgili_bolumler: list[str] = Field(default_factory=list)
    # Bulgunun nasil uretildigi. `sablon` olanlar determinist kurulur:
    # metni kod yazar, dili sabit ve temkinlidir. Dogrulayici onlara LLM
    # denetimi uygulamaz, makine kontrolu yine calisir.
    uretim: Literal["sablon", "llm"] = "llm"


# Dogrulayicinin reddettigi bulgu; seffaflik icin kullaniciya gosterilir.
class ElenenBulgu(BaseModel):

    baslik: str
    ret_nedeni: str


# Raporda deginilmemis, kontrol edilmesi onerilen bir baslik.
#
# Ayri bir tip olmasinin sebebi, bir yoklugun kanitinin olamamasidir.
# `Bulgu` semasi `kaynak_dayanagi` icin en az bir Kanit sart kosar; belgede
# olmayan bir konuyu bu semaya sokmak sistemi ona bir standart
# ilistirmeye zorlar. Eksik bilgiler bu yuzden getir/analiz/dogrula
# hattina girmez; kanit aranmadan, ciktinin altinda kisa bir liste olarak
# sunulur.
class SoruIsareti(BaseModel):

    baslik: str = Field(max_length=120, description="Deginilmemis konu, kisa")
    kaynak_bolum: str = Field(default="", description="Eksikligin fark edildigi bolum")


# ---------------------------------------------------------------- izleme


# Ajan grafigindeki her dugumun calisma izi; arayuzdeki ray bunu cizer.
class DugumIzi(BaseModel):

    dugum: str
    durum: Literal["bekliyor", "calisiyor", "bitti", "hata"]
    baslangic_ms: int | None = None
    sure_ms: int | None = None
    olcum: dict[str, int | float | str] = Field(default_factory=dict)
    not_: str | None = Field(default=None, alias="not")


# ------------------------------------------- LLM'e verilecek yapisal semalar
# Kisitli cozumleme icin sadelestirilmis sarmalayici modeller.


# LLM'in urettigi olgu; `alinti` alani bulunmaz.
#
# Alinti belgede zaten var olan bir metindir, modele kopyalatmak uretim
# suresine yazilir ve kopyalarken model metni degistirebilir. Cumleyi
# `gazetteer.alinti_cikar` belgeden dogrudan keser; hem ucuzdur hem de
# alintinin belgede gectigi kesindir.
class OlguTaslagi(BaseModel):

    # `arama_ifadesi` alani da bulunmaz; gerekce aynidir.
    #
    # Alan modelden istendiginde bos ya da anlamsiz gelebiliyor: bos sorgu
    # bilgi tabaninda rastgele bir kayda takilir ve birbirinden farkli
    # olgular ayni alakasiz kaniti alir. Teknoloji adi sozlukte, tur semada
    # durdugu icin ikisini birlestirmek Python'un isidir (bkz.
    # nodes.arama_ifadesi_kur).
    # Tur kumesi daraltilmistir; `veri_turu` disaridadir.
    #
    # Cikarim istemi `veri_turu` turunu anlatmaz, dolayisiyla model tarif
    # edilmemis bir tur uretebilir. Bu tur KAYNAK_YONLENDIRME uzerinden
    # kvkk/gdpr/linddun koluna gider, yani hukuki bir bulguya donusur.
    #
    # Veri turu siniflandirmasi determinist katmanin isidir:
    # gazetteer.VERI_ISARETCILERI kod tanimlayicilarinda yanlis pozitif
    # vermez, gercek terimler gectiginde yakalar. Sozlukte olmayan bir veri
    # turu eklemek gerekirse dogru yer `VERI_ISARETCILERI` dosyasidir.
    tur: Literal[
        OlguTuru.TEKNOLOJI,
        OlguTuru.VERI_AKISI,
        OlguTuru.KIMLIK_DOGRULAMA,
        OlguTuru.DAGITIM,
        OlguTuru.EKSIK_BILGI,
    ]
    ad: str = Field(description="Kisa etiket, orn. 'Firebase Realtime Database'")
    aciklama: str = Field(max_length=250, description="Tek cumle")
    kaynak_bolum: str = Field(description="Hangi bolumden cikti")


# Belgenin ne anlattigi; yargi gerektirdigi icin LLM'e verilen alanlar.
#
# Determinist kurulumda (ilk giris bolumunun ilk uc cumlesi) kapak bilgisi
# bir baslik altina girdiginde ozet "Ekip Uyeleri: ..., Teslim Tarihi: ..."
# haline geliyor. Kapak sayfasiyla amac cumlesini ayirt etmek kelime
# sayarak yapilamaz.
#
# `ana_bilesenler` burada yoktur: teknoloji listesini sozluk kesin olarak
# bilir, modele saydirmaya gerek yoktur.
class OzetTaslagi(BaseModel):

    amac: str = Field(
        max_length=320,
        description=(
            "Projenin NE YAPTIGI, en fazla 2 cumle. Kapak bilgisini (ekip "
            "uyeleri, danisman, teslim tarihi, ogrenci numarasi, bolum, "
            "anahtar kelimeler) ASLA yazma; onlar projenin amaci degildir."
        ),
    )
    alan: UygulamaAlani = Field(
        description=(
            "Projenin HIZMET ETTIGI alan — kullanicisi kim, hangi sektorde ise "
            "yariyor. Bir ALT MODULE gore secme: fotograf paylasan bir okul "
            "uygulamasi 'medya' degil, aidat tahsil eden bir okul uygulamasi "
            "'e-ticaret' veya 'fintek' degil, ikisi de 'egitim'dir. "
            "Degerler: egitim (okul, kurs, ogrenci-veli), saglik (hasta, klinik, "
            "tibbi), fintek (banka, odeme altyapisi, yatirim), e-ticaret (satis "
            "magazasi, siparis), kamu (belediye, devlet dairesi), ulasim (arac, "
            "rota, teslimat), medya (yayin, icerik dagitimi), sosyal (paylasim "
            "agi, mesajlasma), kurumsal (sirket ici surec, IK, CRM), iot "
            "(sensor, gomulu cihaz), oyun, akademik (arastirma, tez araci), "
            "diger, belirtilmemis. "
            "`belirtilmemis` DEGERINI yalnizca belge kendi alani hakkinda "
            "gercekten hicbir ipucu vermiyorsa sec; bir tez, rapor veya "
            "arastirma calismasi her zaman EN AZ 'akademik'tir."
        ),
    )


# Liste uzunlugu siniri.
#
# `max_length` JSON Semasi'nda `maxItems` olur; llama.cpp bunu GBNF
# dilbilgisine cevirir ve model N. ogeden sonra diziyi kapatmak zorunda
# kalir. Bu, `num_predict` tavanindan farklidir: tavan ciktiyi ortadan
# keser ve gecersiz JSON birakir, `maxItems` ciktiyi gecerli sekilde
# bitirir.
#
# Deger 8'dir: bir bolum obeginde bundan fazla yeni olgu, yani sozlukte
# olmayan olgu cikiyorsa uretilen sey cikarim degil gurultudur. Sinir
# `config.llm_max_token` ile de uyumlu olmali; 8 olgu yaklasik 900 token
# eder ve yerel profilin tavaninin altinda kalir.
class OlguTaslakListesi(BaseModel):

    olgular: list[OlguTaslagi] = Field(max_length=8)


# LLM'in urettigi yalin bulgu.
#
# `Bulgu` semasi `kaynak_dayanagi: list[Kanit]` icerir; dogrudan LLM'e
# verilirse model her kaynagin basligini ve ozetini yeniden uretmek
# zorunda kalir. Bu hem binlerce token kopyalama demektir hem de ic ice
# nesne dizisi kisitli cozumlemeyi yavaslatir.
#
# Burada model yalnizca kaynak kimligini soyler ("ASVS 8.3.4"); tam Kanit
# nesnesini Python, getirilen kanitlardan birlestirir. Boylece model kanit
# icerigini uyduramaz, kimlik listede yoksa bulgu elenir.
class BulguTaslagi(BaseModel):

    # Uzunluk sinirlari dogrudan uretim suresine yansir; sinirlar hem
    # isteme (description) hem semaya (max_length) yazilir. Ilki modeli
    # kisa yazmaya yonlendirir, ikincisi ust sinir koyar.
    alan: RiskAlani
    kesinlik: Kesinlik
    # `maxLength` GBNF dilbilgisine girer ve modeli tam o karakterde
    # susturur. Sinirlar (420 / 200) Turkce iki cumlenin rahatca sigacagi
    # sekilde secilmistir; dar bir sinir ciktiyi duzenli olarak kelime
    # ortasinda keser. `_yarim_cumleyi_at` kesigin yine de olustugu
    # durumlari temizler, boylece sinir yalnizca kacak uretime karsi bir
    # ust tavan olur.
    baslik: str = Field(
        max_length=100,
        description=(
            "EN FAZLA 10 KELIME. Cumle degil, kisa bir baslik — orn. "
            "'Kaynak kodda sabit API anahtari', 'Istemciden gelen kayit "
            "kimligi'. Fiil cekimiyle biten tam cumle YAZMA."
        ),
    )
    aciklama: str = Field(
        max_length=420,
        description=(
            "EN FAZLA 2 CUMLE. Teknolojinin veri alisverisini nasil yaptigini "
            "kisaca anlatir ve kontrol edilmesini onerir. 'Acik vardir', "
            "'guvensizdir' gibi kesin ifadeler KULLANILMAZ."
        ),
    )
    kontrol_onerisi: str = Field(
        max_length=200,
        description=(
            "Kullanicinin dogrulamasi gereken TEK soru. EN FAZLA 20 KELIME, "
            "tek cumle, SORU ISARETIYLE bitir. Yarim birakma."
        ),
    )
    belge_dayanagi: list[str] = Field(description="olgu_id listesi, orn. ['o003']")
    kaynak_kimlikleri: list[str] = Field(
        description="Sana verilen kaynak kimlikleri, orn. ['ASVS 8.3.4', 'KVKK m.6']"
    )


def kisitli_bulgu_semasi(olgu_kimlikleri: list[str], kaynak_kimlikleri: list[str]):
    """Atif alanlarini verilen kimliklere kilitleyen sema uretir.

    Analist ajan tutarli bulgular yazsa da atiflarini tutturamayabiliyor;
    var olmayan bir kaynak veya olgu kimligi gosteren bulgu dayanak
    kontrolunde eleniyor ve uretim bosa gidiyor.

    `maxItems`in kacak uretimi sinirlamasi gibi, `enum` da atfi sinirlar:
    kimlikler GBNF dilbilgisine girer ve model listede olmayan bir kimligi
    uretemez. Istemle rica etmek yerine yapisal olarak engellemek, projenin
    genelinde uygulanan ilkedir.

    Kisit, getirme kalitesine baglidir: olgu basina tek bir alakasiz kayit
    donuyorsa modeli o kaydi secmeye zorlamak temelsiz bulgu uretir. Her
    olgunun birkac alakali kaynagi bulundugunda secim guvenlidir.
    """
    from pydantic import create_model

    Olgu_ = Literal[tuple(olgu_kimlikleri)]      # type: ignore[valid-type]
    Kaynak_ = Literal[tuple(kaynak_kimlikleri)]  # type: ignore[valid-type]

    Taslak = create_model(
        "BulguTaslagiKisitli",
        __base__=BulguTaslagi,
        belge_dayanagi=(list[Olgu_], Field(min_length=1, max_length=4,
                                           description="Sana verilen olgu_id'ler")),
        kaynak_kimlikleri=(list[Kaynak_], Field(min_length=1, max_length=3,
                                                description="Sana verilen kaynak kimlikleri")),
    )
    return create_model(
        "BulguTaslakListesiKisitli",
        __base__=BulguTaslakListesi,
        bulgular=(list[Taslak], Field(max_length=6)),
    )


class BulguTaslakListesi(BaseModel):
    # Olgu basina tipik olarak bir bulgu cikar; 6 bir yigin icin ust
    # sinirdir. Bu sema en uzun ciktiyi uretir (aciklama 420, oneri 200
    # karakter), bulgu basina yaklasik 280 token eder ve toplam yerel
    # profilin tavaninin altinda kalir. Bkz. OlguTaslakListesi.
    bulgular: list[BulguTaslagi] = Field(max_length=6)


class VerifierKarari(BaseModel):
    bulgu_id: str
    karar: Literal["kabul", "revizyon", "ret"]
    gerekce: str = Field(max_length=200, description="Tek cumle, kisa")
    # `revizyon` kararinda bu alanin doldurulmasi esastir. Bos birakilirsa
    # bulgunun bastan yazilmasi gerekir ve bu tum bir LLM turu demektir;
    # duzeltilmis metni burada vermek ayni isi tek cumlelik ek uretimle
    # halleder.
    duzeltilmis_aciklama: str | None = Field(
        default=None,
        max_length=600,
        description=(
            "karar 'revizyon' ise bulgunun DUZELTILMIS aciklamasini buraya yaz. "
            "Bos birakma; sorunu sen gorduysen duzeltilmis halini de sen yazabilirsin."
        ),
    )


# Toplu dogrulama icin. Bulgu basina ayri cagri daha titizdir ama yavas
# makinelerde bulgu sayisi kadar istek demektir; toplu modda tek cagri.
class VerifierKararListesi(BaseModel):

    # Denetlenen bulgu sayisi kadar karar beklenir; 24 genis bir ust
    # sinirdir. Bkz. OlguTaslakListesi.
    kararlar: list[VerifierKarari] = Field(max_length=24)
