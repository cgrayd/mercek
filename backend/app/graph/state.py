"""Ajan grafiginin paylasilan durumu.

LangGraph'ta durum dugumler arasinda tasinir. `iz` alani her dugumun ne
yaptigini kaydeder ve arayuzdeki calisma rayini besler.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.schemas import (
    BelgeOzeti,
    Bolum,
    Bulgu,
    DugumIzi,
    ElenenBulgu,
    Kanit,
    Olgu,
    SoruIsareti,
)


class AnalizDurumu(TypedDict, total=False):
    dosya_adi: str
    # Yuklenen dosyanin ham icerigi. LangGraph, TypedDict'te tanimli
    # olmayan alanlari atar; bu alan burada tanimli olmak zorunda.
    _ham: bytes

    # ayristir -> yonlendir
    bolumler: list[Bolum]
    hedef_bolumler: list[str]      # analize girecek bolum_id listesi

    # ozetle
    ozet: BelgeOzeti | None

    # cikar
    olgular: list[Olgu]
    # Deginilmemis konular. Hatta girmez, ciktinin altinda listelenir;
    # bkz. schemas.SoruIsareti.
    soru_isaretleri: list[SoruIsareti]

    # getir  (olgu_id -> kanit listesi)
    kanitlar: dict[str, list[Kanit]]
    zayif_olgular: list[str]       # yeterli kanit bulunamayan olgular
    getirme_turu: int              # kacinci retrieval turundayiz

    # analiz + dogrula
    bulgular: list[Bulgu]
    elenenler: list[ElenenBulgu]

    # izleme: dugumler kendi izlerini ekler
    iz: Annotated[list[DugumIzi], operator.add]
