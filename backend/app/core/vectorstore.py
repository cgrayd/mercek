"""Qdrant katmani: yalnizca bilgi tabani.

Yuklenen belge bu indekse yazilmaz. Yazilirsa belgenin kendi cumleleri
kanit olarak geri doner ve sistem kendi kendini dogrulamis olur.

  mercek_bilgi_tabani -> kalici. ASVS, CWE, LINDDUN, KVKK ve saglayici
                         politikalari. Kanit sadece buradan cekilir.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from qdrant_client import QdrantClient, models

from app.config import get_settings
from app.core.embeddings import gomme

_YOGUN = "yogun"
_SEYREK = "seyrek"


@lru_cache
def istemci() -> QdrantClient:
    """Surec boyunca tek istemci.

    Her aramada yeni istemci kurmak, arama basina ayri bir surum kontrolu
    istegi anlamina gelir.
    """
    ayar = get_settings()
    return QdrantClient(url=ayar.qdrant_url, api_key=ayar.qdrant_api_key, timeout=60)


def koleksiyon_kur(ad: str, sifirla: bool = False) -> None:
    ayar = get_settings()
    q = istemci()
    if sifirla and q.collection_exists(ad):
        q.delete_collection(ad)
    if q.collection_exists(ad):
        return

    q.create_collection(
        collection_name=ad,
        vectors_config={
            _YOGUN: models.VectorParams(size=ayar.embed_dim, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            _SEYREK: models.SparseVectorParams(
                index=models.SparseIndexParams(on_disk=False)
            )
        },
    )
    # Kaynak turu filtresi olmadan hibrit arama teknik bir soruya hukuki
    # metin dondurebilir; bu indeks filtrelemeyi mumkun kilar.
    q.create_payload_index(ad, "kaynak_turu", models.PayloadSchemaType.KEYWORD)
    q.create_payload_index(ad, "dil", models.PayloadSchemaType.KEYWORD)


def yaz(ad: str, kayitlar: list[dict]) -> int:
    """kayitlar: [{metin: str, ...payload}]"""
    if not kayitlar:
        return 0
    vektorler = gomme().kodla([k["metin"] for k in kayitlar])
    noktalar = [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector={
                _YOGUN: v["dense"],
                _SEYREK: models.SparseVector(
                    indices=list(v["sparse"].keys()),
                    values=list(v["sparse"].values()),
                ),
            },
            payload=kayit,
        )
        for kayit, v in zip(kayitlar, vektorler)
    ]
    istemci().upsert(collection_name=ad, points=noktalar, wait=True)
    return len(noktalar)


def hibrit_ara(
    ad: str,
    sorgu: str,
    limit: int = 6,
    kaynak_turleri: list[str] | None = None,
    benzerlik_esigi: float | None = None,
) -> list[dict]:
    """Yogun + seyrek on-cekim, ardindan RRF fuzyonu.

    kaynak_turleri verilirse arama o kaynaklarla sinirlanir. Cikarim
    dugumu olgunun turune gore bunu belirler: teknik olgu -> asvs/cwe,
    veri akisi -> linddun, kisisel veri -> kvkk/gdpr.

    benzerlik_esigi verilirse yogun on-cekime `score_threshold` olarak
    uygulanir. Esik burada kurulur, cunku fuzyon skoru sira tabanlidir,
    benzerlik degil; fuzyondan sonra konan bir esik alakasiz kaydi eleyemez
    (bkz. config.retrieval_benzerlik_esigi). Hicbir kayit esigi gecemezse
    bos liste doner ve cagiran bunu 'kanit bulunamadi' olarak yorumlar.
    """
    # Bos sorgu kanit uretemez. BGE-M3 bos dizgeyi de gomer ve cikan
    # anlamsiz vektor bilgi tabanindaki rastgele bir kayda esigi gecen bir
    # benzerlik verebilir. Bos liste donmek dogru davranistir: cagiran bunu
    # "kanit bulunamadi" olarak yorumlar, olgu zayif isaretlenir ve sorgu
    # yeniden yazma dongusu devreye girer.
    if not sorgu or not sorgu.strip():
        return []

    v = gomme().tek(sorgu)
    filtre = None
    if kaynak_turleri:
        filtre = models.Filter(
            must=[models.FieldCondition(
                key="kaynak_turu",
                match=models.MatchAny(any=kaynak_turleri),
            )]
        )

    # Esigi yalnizca yogun on-cekime koymak yetmez: seyrek on-cekim esiksiz
    # calisir ve alakasiz bir kayit fuzyona oradan sizabilir. Once esigi
    # gecen kimlikler belirlenir, fuzyon sonucu sonra o kumeye daraltilir.
    izinli: set | None = None
    if benzerlik_esigi is not None:
        kapi = istemci().query_points(
            collection_name=ad,
            query=v["dense"],
            using=_YOGUN,
            limit=limit * 4,
            query_filter=filtre,
            score_threshold=benzerlik_esigi,
            with_payload=False,
        )
        izinli = {n.id for n in kapi.points}
        if not izinli:
            return []

    sonuc = istemci().query_points(
        collection_name=ad,
        prefetch=[
            models.Prefetch(
                query=v["dense"],
                using=_YOGUN,
                limit=limit * 4,
                filter=filtre,
                score_threshold=benzerlik_esigi,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=list(v["sparse"].keys()),
                    values=list(v["sparse"].values()),
                ),
                using=_SEYREK,
                limit=limit * 4,
                filter=filtre,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    return [
        {**n.payload, "skor": n.score}
        for n in sonuc.points
        if izinli is None or n.id in izinli
    ]
