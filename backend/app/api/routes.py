"""API rotalari.

Analiz uzun surer (yerel LLM ile birkac dakika). Bu yuzden istek
senkron beklemez: dosya yuklenir, bir analiz kimligi doner, arayuz
SSE ile calisma rayini canli izler.
"""

from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.graph.pipeline import calistir

router = APIRouter(prefix="/api")
AYAR = get_settings()

# Uretim icin Redis ve bir gorev kuyrugu ile degistirilmelidir.
DEPO: dict[str, dict] = {}
HAVUZ = ThreadPoolExecutor(max_workers=2)

# Ray, hattin calisma sirasini gosterir. Hat iki dalgali: once determinist
# dugumler calisir ve sonuclari SSE'den yayinlanir, sonra LLM dugumleri
# bunlarin uzerine ekler. Bkz. graph/pipeline.py.
DUGUM_SIRASI = [
    # --- dalga 1: determinist, LLM yok ---
    ("ayristir", "Ayrıştırma", "Bölüm hiyerarşisi çıkarılıyor"),
    ("cikar", "Sözlük taraması", "Bilinen teknolojiler ve veri türleri"),
    ("getir", "Getirici ajan", "Bilgi tabanı aranıyor"),
    ("analiz", "Analist ajan", "Bulgular yazılıyor"),
    ("dogrula", "Doğrulayıcı ajan", "Dayanaksız bulgular eleniyor"),
    # --- dalga 2: LLM, ilk sonuclarin uzerine ekler ---
    ("ozetle", "Özet", "Proje amacı çıkarılıyor"),
    ("yonlendir", "Yönlendirme", "Derin analize değer bölümler seçiliyor"),
    ("cikar_llm", "Çıkarıcı ajan", "Sözlükte olmayan olgular aranıyor"),
    ("sorgu_yaz", "Sorgu yeniden yazma", "Zayıf eşleşmeler tazeleniyor"),
]


_LISTE_ALANLARI = ("olgular", "bulgular", "elenenler", "soru_isaretleri", "iz")


@router.get("/dugumler")
def dugumler() -> list[dict]:
    """Arayuzdeki calisma rayinin sabit iskeleti."""
    return [{"anahtar": a, "ad": b, "aciklama": c} for a, b, c in DUGUM_SIRASI]


@router.post("/analiz")
async def analiz_baslat(dosya: UploadFile) -> dict:
    ham = await dosya.read()
    boyut_mb = len(ham) / (1024 * 1024)
    if boyut_mb > AYAR.max_upload_mb:
        raise HTTPException(413, f"Dosya {AYAR.max_upload_mb} MB sınırını aşıyor")
    if not (dosya.filename or "").lower().endswith((".pdf", ".docx", ".txt", ".md")):
        raise HTTPException(415, "PDF, DOCX, TXT veya MD yükleyin")

    analiz_id = f"a{int(time.time() * 1000):x}"
    kayit = DEPO[analiz_id] = {
        "analiz_id": analiz_id,
        "dosya_adi": dosya.filename,
        "durum": "calisiyor",
        "ozet": None,
        "hata": None,
        **{k: [] for k in _LISTE_ALANLARI},
    }

    def aktar(durum: dict) -> None:
        """Her dugumden sonra ve sonda cagrilir; SSE akisi bunu okur."""
        kayit.update({"ozet": durum.get("ozet"),
                      **{k: durum.get(k, []) for k in _LISTE_ALANLARI}})

    def isi() -> None:
        try:
            aktar(calistir(ham, dosya.filename or "belge.pdf", geri_cagri=aktar))
            kayit["durum"] = "bitti"
        except Exception as hata:  # noqa: BLE001
            kayit.update({"durum": "hata", "hata": str(hata)})

    HAVUZ.submit(isi)
    return {"analiz_id": analiz_id}


def _serilestir(kayit: dict) -> dict:
    """Pydantic nesnelerini JSON'a cevirir."""
    def don(v):
        if hasattr(v, "model_dump"):
            return v.model_dump(mode="json", by_alias=True)
        if isinstance(v, list):
            return [don(x) for x in v]
        return v

    return {k: don(v) for k, v in kayit.items()}


@router.get("/analiz/{analiz_id}")
def analiz_getir(analiz_id: str) -> dict:
    kayit = DEPO.get(analiz_id)
    if not kayit:
        raise HTTPException(404, "Analiz bulunamadı")
    return _serilestir(kayit)


@router.get("/analiz/{analiz_id}/akis")
async def analiz_akisi(analiz_id: str) -> StreamingResponse:
    """SSE. Arayuzdeki ray bunu dinler."""
    if analiz_id not in DEPO:
        raise HTTPException(404, "Analiz bulunamadı")

    async def uret():
        onceki = None
        while True:
            # Kayit akis sirasinda silinmis olabilir (DELETE ucu). Sozlukten
            # dogrudan okumak KeyError atar ve istemci yeniden baglandigi
            # icin bu sonsuz bir yeniden baglanma dongusu yaratir.
            kayit = DEPO.get(analiz_id)
            if kayit is None:
                yield "event: silindi\ndata: {}\n\n"
                break
            paket = _serilestir(kayit)
            imza = json.dumps(paket, ensure_ascii=False, sort_keys=True)
            if imza != onceki:
                yield f"data: {imza}\n\n"
                onceki = imza
            if kayit["durum"] in ("bitti", "hata"):
                break
            await asyncio.sleep(0.6)

    return StreamingResponse(
        uret(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/analiz/{analiz_id}")
def analiz_sil(analiz_id: str) -> dict:
    DEPO.pop(analiz_id, None)
    return {"silindi": True}
