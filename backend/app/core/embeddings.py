"""BGE-M3 gomme katmani.

Tek modelden hem yogun (dense) hem seyrek (sparse/lexical) vektor alinir:

  yogun   -> anlamsal yakinlik. "veriler buluta gonderilir" ile
             "data is transmitted to a remote server" eslesir.
  seyrek  -> birebir terim eslesmesi. "CWE-311", "AES-256", "Firebase"
             gibi teknik jetonlari tam yakalar.

Standart kimlikleri ve urun adlari kanit zincirinin dayanagi oldugu icin
ikisi birlikte kullanilir.
"""

from __future__ import annotations

import os
import threading
from functools import lru_cache

from app.config import get_settings

_kilit = threading.Lock()


def _hub_ortami_hazirla() -> None:
    """HF Hub ortam degiskenlerini ayarlar.

    Degiskenler huggingface_hub ice aktarilmadan once ayarlanmalidir;
    kutuphane onlari ice aktarma aninda okur. FlagEmbedding importu bu
    yuzden fonksiyon icinde ve bu cagridan sonra yapilir.
    """
    ayar = get_settings()
    if ayar.hf_home:
        os.environ.setdefault("HF_HOME", ayar.hf_home)
    if ayar.hf_token:
        os.environ.setdefault("HF_TOKEN", ayar.hf_token)
    if ayar.hf_offline:
        # Ag istegi hic yapilmaz, yalnizca onbellek kullanilir.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"


class HibritGomme:
    """BGE-M3 sarmalayici. Model tek sefer yuklenir (thread-safe)."""

    def __init__(self) -> None:
        _hub_ortami_hazirla()
        from FlagEmbedding import BGEM3FlagModel

        ayar = get_settings()
        gpu = ayar.embed_device.startswith("cuda")

        # FlagEmbedding surumleri arasinda kurucu imzasi degisiyor: eski
        # surumler `device`, yeniler `devices` bekliyor, bazilari ikisini de
        # kabul etmiyor. Sirayla denenip ilk tutan kullanilir.
        denemeler = [
            {"use_fp16": gpu, "devices": ayar.embed_device},
            {"use_fp16": gpu, "device": ayar.embed_device},
            {"use_fp16": gpu},
            {},
        ]
        son_hata: Exception | None = None
        for kwargs in denemeler:
            try:
                self._model = BGEM3FlagModel(ayar.embed_model, **kwargs)
                break
            except TypeError as hata:
                son_hata = hata
        else:
            ipucu = (
                " Cevrimdisi mod acik ve model onbellekte yok olabilir; "
                "MERCEK_HF_OFFLINE=false yapip bir kez indirin."
                if ayar.hf_offline else
                " FlagEmbedding surumu beklenmedik bir kurucu imzasi kullaniyor olabilir."
            )
            raise RuntimeError(f"BGE-M3 yuklenemedi.{ipucu} Son hata: {son_hata}")

        self._max_len = ayar.embed_max_length

    def kodla(self, metinler: list[str]) -> list[dict]:
        """[{dense: [...], sparse: {index: weight}}, ...] dondurur."""
        if not metinler:
            return []
        with _kilit:
            cikti = self._model.encode(
                metinler,
                max_length=self._max_len,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
        sonuc = []
        for yogun, seyrek in zip(cikti["dense_vecs"], cikti["lexical_weights"]):
            sonuc.append(
                {
                    # numpy dizisi veya liste gelebiliyor, ikisini de destekle
                    "dense": yogun.tolist() if hasattr(yogun, "tolist") else list(yogun),
                    # BGE-M3 anahtarlari str token id dondurur -> int'e cevir
                    "sparse": {int(k): float(v) for k, v in seyrek.items() if float(v) > 0},
                }
            )
        return sonuc

    def tek(self, metin: str) -> dict:
        return self.kodla([metin])[0]


@lru_cache
def gomme() -> HibritGomme:
    return HibritGomme()
