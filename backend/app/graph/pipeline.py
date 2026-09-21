"""Grafigin birlestirilmesi.

Akis sabit, dongu noktasi sinirli: ozerklik dugumlerin icinde ve tek
kontrollu dongudedir (getirme <-> sorgu yeniden yazma). Ust seviye akis
tekrarlanabilir.
"""

from __future__ import annotations

import time
from typing import Callable

from langgraph.graph import END, START, StateGraph

from app.core.gunluk import analiz_basladi, analiz_bitti, kayit
from app.core.parsing import bolumlere_ayir
from app.graph import nodes
from app.graph.state import AnalizDurumu


def ayristir_dugumu(durum: AnalizDurumu) -> dict:
    """Belgeyi bolumlere ayirir.

    Belge hicbir vektor indeksine yazilmaz; kanit yalnizca bilgi
    tabanindan cekilir (bkz. core/vectorstore.py).
    """
    bas = time.time()
    bolumler = bolumlere_ayir(durum.get("_ham") or b"", durum["dosya_adi"])
    deger = sum(1 for b in bolumler if b.karar == "evet")
    kayit(f"ayristir: {len(bolumler)} bolum, {deger} tanesi analize deger")
    return {
        "bolumler": bolumler,
        "iz": [nodes._iz("ayristir", bas, {"bolum": len(bolumler), "analize_deger": deger})],
    }


def grafik_kur():
    """Iki dalgali hat.

    Determinist dugumler saniyeler icinde biterken LLM hatti dakikalar
    surer. Ikisi ayri dalgalara bolundugu icin kullanici ilk sonuclari
    LLM'i beklemeden gorur.

        Dalga 1 (determinist, LLM yok)
          ayristir -> cikar_sozluk -> getir -> analiz -> dogrula
          Sonuclar burada yayinlanir: `calistir` her super-adimdan sonra
          geri cagriyi tetikler, `routes.py` bunu SSE'ye baglar.

        Dalga 2 (LLM, arka planda zenginlestirme)
          ozetle -> yonlendir -> cikar_llm -> getir2 <-> sorgu_yaz
                 -> analiz2 -> dogrula2

    Dalga 2'nin her dugumu dalga 1'in sonucuna ekler, onu degistirmez;
    tamamen basarisiz olsa bile determinist cikti ayakta kalir. Bolme
    toplam sureyi degil, ilk sonuca kadar gecen sureyi kisaltir; toplam
    sureyi istem ve cikti butceleri belirler (bkz. config.llm_max_token
    ve schemas.OlguTaslakListesi).
    """
    g = StateGraph(AnalizDurumu)

    # --- dalga 1: determinist ---
    g.add_node("ayristir", ayristir_dugumu)
    g.add_node("cikar_sozluk", nodes.cikar_sozluk)
    g.add_node("getir", nodes.getir)
    g.add_node("analiz", nodes.analiz_determinist)
    g.add_node("dogrula", nodes.dogrula)

    # --- dalga 2: LLM ---
    g.add_node("ozetle", nodes.ozetle)
    g.add_node("yonlendir", nodes.yonlendir)
    g.add_node("cikar_llm", nodes.cikar_llm)
    g.add_node("getir2", nodes.getir)
    g.add_node("sorgu_yaz", nodes.sorgu_yaz)
    g.add_node("analiz2", nodes.analiz_llm)
    g.add_node("dogrula2", nodes.dogrula)

    g.add_edge(START, "ayristir")
    g.add_edge("ayristir", "cikar_sozluk")
    g.add_edge("cikar_sozluk", "getir")
    g.add_edge("getir", "analiz")
    g.add_edge("analiz", "dogrula")
    # Dalga 1 bitti, sonuclar SSE'den yayinlandi; buradan sonrasi
    # zenginlestirme. `ozetle` bir LLM cagrisi oldugu icin dalga 2'de
    # duruyor; dalga 1'in basinda olsa determinist bulgular onu beklerdi.
    g.add_edge("dogrula", "ozetle")
    g.add_edge("ozetle", "yonlendir")
    g.add_edge("yonlendir", "cikar_llm")
    g.add_edge("cikar_llm", "getir2")

    # Ozerk dongu: yetersiz getirme -> sorgu yeniden yaz -> tekrar ara
    g.add_conditional_edges(
        "getir2", nodes.getirme_karari,
        {"sorgu_yaz": "sorgu_yaz", "analiz": "analiz2"},
    )
    g.add_edge("sorgu_yaz", "getir2")
    g.add_edge("analiz2", "dogrula2")
    g.add_edge("dogrula2", END)

    return g.compile()


GRAFIK = grafik_kur()


def calistir(
    ham: bytes,
    dosya_adi: str,
    geri_cagri: Callable[[dict], None] | None = None,
) -> dict:
    """Grafigi calistirir; her dugumden sonra `geri_cagri` ile durumu bildirir.

    `invoke` yerine `stream` kullanilir: arayuzdeki calisma rayi bitmis
    sonucu degil ilerlemeyi gosterir. `stream_mode="values"` her
    super-adimdan sonra durumun tamamini verir.
    """
    analiz_basladi(dosya_adi)
    # Devre kesici kosum basina sifirlanir; onceki analizdeki saglayici
    # hatalari bu kosumu etkilememelidir.
    from app.core.llm import llm as _llm
    _llm().devreyi_sifirla()
    sonuc: dict = {}
    for durum in GRAFIK.stream(
        {"dosya_adi": dosya_adi, "_ham": ham, "iz": []},
        {"recursion_limit": 40},
        stream_mode="values",
    ):
        sonuc = durum
        if geri_cagri is not None:
            # Arayuze haber verirken cikan hata analizi durdurmamali.
            try:
                geri_cagri(durum)
            except Exception:  # noqa: BLE001
                pass

    analiz_bitti(len(sonuc.get("bulgular") or []), len(sonuc.get("elenenler") or []))
    # `_ham` disarida birakilir: yuklenen belgenin ham baytlari cagiranin
    # bellek icindeki kaydina gecmemelidir.
    return {k: v for k, v in sonuc.items() if k != "_ham"}
