"""Mercek — proje raporu risk on-taramasi."""

import sys
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.core import vectorstore

AYAR = get_settings()


def _modeli_onden_yukle() -> None:
    """BGE-M3'u arka planda yukler.

    Onden yuklenmezse ilk analiz, model bellege alinirken bekler. Bu
    bekleme boylece sunucu acilisina tasinir.
    """
    try:
        bas = time.time()
        print("  [model] BGE-M3 yukleniyor...", file=sys.stderr, flush=True)
        from app.core.embeddings import gomme

        gomme().tek("hazirlik")
        print(f"  [model] BGE-M3 hazir ({time.time() - bas:.1f}s)",
              file=sys.stderr, flush=True)
    except Exception as hata:  # noqa: BLE001
        print(f"  [model] Yuklenemedi: {hata}", file=sys.stderr, flush=True)


@asynccontextmanager
async def yasam(app: FastAPI):
    # Koleksiyon yoksa olustur. Bilgi tabani bos olabilir;
    # ingest betigi ile doldurulur.
    try:
        vectorstore.koleksiyon_kur(AYAR.kb_collection)
    except Exception as hata:  # noqa: BLE001
        print(f"  [uyari] Qdrant koleksiyonu hazirlanamadi ({AYAR.kb_collection}): {hata}",
              file=sys.stderr, flush=True)

    if AYAR.baslangicta_yukle:
        threading.Thread(target=_modeli_onden_yukle, daemon=True).start()

    print(f"  [hazir] http://localhost:8000  ·  model: {AYAR.llm_model}",
          file=sys.stderr, flush=True)
    yield


app = FastAPI(
    title="Mercek",
    description="Tasarim asamasinda risk on-taramasi",
    version="0.1.0",
    lifespan=yasam,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=AYAR.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/saglik")
def saglik() -> dict:
    return {"durum": "ayakta", "model": AYAR.llm_model}
