"""Kalite olcegi.

    python -m degerlendirme.olcek                 # tum set, tam boru hatti
    python -m degerlendirme.olcek --hizli         # determinist katman + ozet
    python -m degerlendirme.olcek --hizli --ozetsiz  # LLM cagrisi yok
    python -m degerlendirme.olcek --belge temiz_tez.docx

`--hizli` tek basina LLM'siz degildir: determinist katmani olcer ama
`ozetle` dugumunu calistirir ve o dugum belge basina bir LLM cagrisi yapar.
Tamamen tekrarlanabilir olcum icin `--ozetsiz` eklenir; ozet sinamalari o
modda atlanir.

Olctugu dort sey:
  recall     : bilinmesi gereken olgular cikarildi mi
  precision  : cikarilmamasi gerekenler cikmadi mi (yanlis pozitif)
  gurultu    : bulgu hak etmeyen bilesenler icin bulgu uretildi mi
  ozet       : proje amaci gercekten amac mi, kapak bilgisi mi
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent
YESIL, KIRMIZI, SARI, SIFIRLA = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def _normalize_tr(m: str) -> str:
    harita = str.maketrans({"İ": "i", "I": "i", "ı": "i", "Ğ": "g", "ğ": "g",
                            "Ü": "u", "ü": "u", "Ş": "s", "ş": "s", "Ö": "o",
                            "ö": "o", "Ç": "c", "ç": "c"})
    # Alt cizgi bosluga cevrilir: determinist katman veri turunu anahtar
    # olarak ("kimlik_verisi"), tam boru hatti ise Olgu.ad icinde
    # ("kimlik verisi") verir; bkz. nodes.cikar_sozluk. Bu normalizasyon
    # olmadan ayni belge --hizli modunda gecer, tam kosumda kalir.
    return m.translate(harita).replace("_", " ").lower()


def _iceriyor(metin: str, ifade: str) -> bool:
    return _normalize_tr(ifade) in _normalize_tr(metin)


def determinist_calistir(yol: Path, ozet_ile: bool = True) -> dict:
    """Determinist katman: ayristirma + sozluk taramasi (+ istege bagli ozet).

    `ozet_ile=False` iken hicbir LLM cagrisi yapilmaz ve kosum tamamen
    tekrarlanabilir olur. Kararlilik olcumu (ayni belge N kez) bu modda
    yapilir; cikan fark model degiskenligini degil determinist katmandaki
    bir hatayi gosterir.
    """
    from app.core.gazetteer import teknoloji_tara, veri_turu_tara
    from app.core.parsing import bolumlere_ayir
    from app.graph.nodes import ozetle

    bolumler = bolumlere_ayir(yol.read_bytes(), yol.name)
    hedef = [b.bolum_id for b in bolumler if b.karar != "hayir"]
    taranan = [b for b in bolumler if b.karar != "hayir"]

    olgular: list[str] = []
    for b in taranan:
        olgular += [g.ad for g, _ in teknoloji_tara(b.metin)]
        olgular += [t for t, _ in veri_turu_tara(b.metin)]

    amac = ""
    if ozet_ile:
        amac = ozetle({"bolumler": bolumler, "hedef_bolumler": hedef})["ozet"].amac
    return {"olgular": sorted(set(olgular)), "ozet": amac, "bulgular": None}


def tam_calistir(yol: Path) -> dict:
    """Tam boru hatti. Dakikalar surer, gercek ciktiyi olcer."""
    from app.graph.pipeline import calistir

    sonuc = calistir(yol.read_bytes(), yol.name)
    return {
        "olgular": sorted({o.ad for o in sonuc.get("olgular", [])}),
        "ozet": (sonuc.get("ozet").amac if sonuc.get("ozet") else ""),
        "bulgular": sonuc.get("bulgular", []),
    }


def belgeyi_olc(ad: str, beklenen: dict, hizli: bool,
                ozet_ile: bool = True) -> tuple[int, int, list[str], dict]:
    from app.core.gazetteer import giris_bul

    yol = KOK / "belgeler" / ad
    bas = time.time()
    c = (determinist_calistir(yol, ozet_ile) if hizli else tam_calistir(yol))
    sure = time.time() - bas

    gecti, kaldi, notlar = 0, 0, []
    # `gecti/kaldi` sinama sayisidir; asil raporlanan sey oranlardir: kac
    # tuzaktan kaci yakalandi, temiz belgede kac yanlis pozitif cikti.
    olcum = {"tuzak_toplam": 0, "tuzak_yakalanan": 0, "kacan": [],
             "temiz_mi": beklenen.get("azami_bulgu") == 0,
             "bulgu": 0, "gurultu": 0, "sure": 0.0}

    def sina(kosul: bool, mesaj: str) -> None:
        nonlocal gecti, kaldi
        if kosul:
            gecti += 1
        else:
            kaldi += 1
            notlar.append(mesaj)

    olgu_metni = " | ".join(c["olgular"])
    for x in beklenen.get("olgu_olmali", []):
        sina(_iceriyor(olgu_metni, x), f"eksik olgu: {x}")
    for x in beklenen.get("olgu_olmamali", []):
        sina(not _iceriyor(olgu_metni, x), f"YANLIS POZITIF olgu: {x}")

    if not ozet_ile and hizli:
        notlar.append("  not: ozet sinamalari atlandi (--ozetsiz)")
    for x in ([] if (not ozet_ile and hizli) else beklenen.get("ozet_icermemeli", [])):
        sina(not _iceriyor(c["ozet"], x), f"ozette olmamali: '{x}'")
    anlamli = [] if (not ozet_ile and hizli) else beklenen.get("ozet_icermeli_biri", [])
    if anlamli:
        sina(any(_iceriyor(c["ozet"], x) for x in anlamli),
             f"ozet anlamsiz: {anlamli} ifadelerinden hicbiri gecmiyor")

    # Bulgu tabanli kontroller yalnizca tam kosumda anlamli.
    if c["bulgular"] is not None:
        adlar = [b.baslik.split(" — ")[0].strip() for b in c["bulgular"]]
        for x in beklenen.get("bulgu_olmamali_teknoloji", []):
            sina(x not in adlar, f"GURULTU bulgusu: {x}")
        # Tuzak sinamasi: aracin bildirmesi zorunlu olan riskler. Diger
        # sinamalar gurultuyu ve asiri uretimi olcer; bu sinama aracin ise
        # yarayip yaramadigini olcer. Kacan bir tuzak, bulgu sayisina
        # bakarak fark edilemez.
        bulgu_metni = " | ".join(
            f"{b.baslik} {b.aciklama} {b.kontrol_onerisi}" for b in c["bulgular"]
        )
        for tuzak in beklenen.get("bulgu_olmali", []):
            bulundu = any(_iceriyor(bulgu_metni, k) for k in tuzak["anahtar"])
            olcum["tuzak_toplam"] += 1
            olcum["tuzak_yakalanan"] += int(bulundu)
            if not bulundu:
                olcum["kacan"].append(tuzak["ad"])
            sina(bulundu, f"TUZAK KACTI: {tuzak['ad']}")

        azami = beklenen.get("azami_bulgu")
        if azami is not None:
            sina(len(c["bulgular"]) <= azami,
                 f"asiri uretim: {len(c['bulgular'])} bulgu (azami {azami})")
        olcum["bulgu"] = len(c["bulgular"])
        gurultu = [a for a in adlar
                   if (g := giris_bul(a)) and g.kategori in ("cerceve", "arayuz", "mobil")]
        olcum["gurultu"] = len(gurultu)
        if gurultu:
            notlar.append(f"  not: cerceve bulgulari {gurultu}")

    durum = f"{YESIL}GECTI{SIFIRLA}" if kaldi == 0 else f"{KIRMIZI}{kaldi} KALDI{SIFIRLA}"
    bulgu = "—" if c["bulgular"] is None else str(len(c["bulgular"]))
    print(f"\n{ad}  [{durum}]  {gecti}/{gecti + kaldi} sinama · {sure:.1f}s · bulgu={bulgu}")
    print(f"   ozet: {c['ozet'][:150]}")
    for n in notlar:
        renk = SARI if n.startswith("  not:") else KIRMIZI
        print(f"   {renk}{n}{SIFIRLA}")
    olcum["sure"] = sure
    return gecti, kaldi, notlar, olcum



def _oran_ozeti(olcumler: dict[str, dict], hizli: bool) -> None:
    """Oran ozeti.

    Iki kutup ayri ayri raporlanir, birlestirilmez: tek bir yuzde, her seye
    bulgu yazan bir araci da basarili gosterebilir. Tuzak yakalama oraniyla
    temiz belgedeki yanlis pozitif sayisi birlikte okunmalidir.
    """
    if hizli:
        print("\n  (bulgu tabanli oranlar yalnizca TAM kosumda uretilir)")
        return

    t_top = sum(o["tuzak_toplam"] for o in olcumler.values())
    t_yak = sum(o["tuzak_yakalanan"] for o in olcumler.values())
    temiz = {a: o for a, o in olcumler.items() if o["temiz_mi"]}
    yp = sum(o["bulgu"] for o in temiz.values())
    gurultu = sum(o["gurultu"] for o in olcumler.values())

    print("\n" + "=" * 66)
    print("  OLCUM OZETI")
    print("=" * 66)
    if t_top:
        print(f"  Tuzak yakalama (recall)   : {t_yak}/{t_top}  %{100 * t_yak / t_top:.1f}")
        for ad, o in olcumler.items():
            if o["tuzak_toplam"]:
                print(f"      {ad:<22} {o['tuzak_yakalanan']:>2}/{o['tuzak_toplam']:<2}")
                for k in o["kacan"]:
                    print(f"          {KIRMIZI}kacan: {k}{SIFIRLA}")
    if temiz:
        durum = YESIL if yp == 0 else KIRMIZI
        print(f"  Temiz belgede yanlis poz. : {durum}{yp} bulgu{SIFIRLA}  (hedef 0)")
        for ad, o in temiz.items():
            print(f"      {ad:<22} {o['bulgu']:>2}")
    print(f"  Cerceve gurultusu         : {gurultu}  (hedef 0)")
    print(f"  Toplam sure               : {sum(o['sure'] for o in olcumler.values()):.1f} sn"
          f"  ({len(olcumler)} belge)")
    print("=" * 66)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hizli", action="store_true",
                    help="yalnizca determinist katman (LLM yok, saniyeler)")
    ap.add_argument("--belge", help="tek bir belgeyi olc")
    ap.add_argument("--ozetsiz", action="store_true",
                    help="ozet dugumunu atla; --hizli ile birlikte SIFIR LLM cagrisi")
    args = ap.parse_args()

    beklenen = json.loads((KOK / "beklenen.json").read_text(encoding="utf-8"))
    belgeler = {k: v for k, v in beklenen.items() if not k.startswith("_")}
    if args.belge:
        belgeler = {args.belge: belgeler[args.belge]}

    print("=" * 66)
    print(f"  Mercek kalite olcegi - {'HIZLI (determinist)' if args.hizli else 'TAM (LLM dahil)'}")
    print("=" * 66)

    top_g = top_k = 0
    olcumler: dict[str, dict] = {}
    for ad, b in belgeler.items():
        g, k, _, o = belgeyi_olc(ad, b, args.hizli, ozet_ile=not args.ozetsiz)
        top_g, top_k = top_g + g, top_k + k
        olcumler[ad] = o

    print("\n" + "=" * 66)
    renk = YESIL if top_k == 0 else KIRMIZI
    print(f"  {renk}TOPLAM: {top_g}/{top_g + top_k} sinama gecti, {top_k} kaldi{SIFIRLA}")
    print("=" * 66)
    _oran_ozeti(olcumler, args.hizli)
    return 1 if top_k else 0


if __name__ == "__main__":
    sys.exit(main())
