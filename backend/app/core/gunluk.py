"""Konsol kaydi.

Her dugum ne yaptigini uvicorn penceresine yazar; boylece uzun suren bir
kosumda hangi adimda beklendigi gorunur.
"""

from __future__ import annotations

import sys
import time

_BASLANGIC = time.time()


def kayit(mesaj: str) -> None:
    """Gecen sureyle birlikte tek satir yazar."""
    gecen = time.time() - _BASLANGIC
    print(f"  [{gecen:7.1f}s] {mesaj}", file=sys.stderr, flush=True)


def analiz_basladi(dosya_adi: str) -> None:
    global _BASLANGIC
    _BASLANGIC = time.time()
    print(f"\n{'=' * 60}\n  ANALIZ: {dosya_adi}\n{'=' * 60}", file=sys.stderr, flush=True)


def analiz_bitti(bulgu_sayisi: int, elenen: int) -> None:
    gecen = time.time() - _BASLANGIC
    print(
        f"{'=' * 60}\n  BITTI: {bulgu_sayisi} bulgu, {elenen} elendi, "
        f"toplam {gecen:.1f}s\n{'=' * 60}\n",
        file=sys.stderr,
        flush=True,
    )
