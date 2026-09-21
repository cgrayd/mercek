"""Kurulum dogrulama betigi.

    python -m app.dogrula

Her bileseni sirayla sinar ve hangi adimda sorun oldugunu, cozum onerisiyle
birlikte yazar.
"""

from __future__ import annotations

import sys

YESIL, KIRMIZI, SARI, SIFIRLA = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def ok(mesaj: str) -> None:
    print(f"  {YESIL}[TAMAM]{SIFIRLA} {mesaj}")


def hata(mesaj: str, cozum: str = "") -> None:
    print(f"  {KIRMIZI}[HATA]{SIFIRLA}  {mesaj}")
    if cozum:
        print(f"          {SARI}Cozum:{SIFIRLA} {cozum}")


def basli(mesaj: str) -> None:
    print(f"\n{mesaj}")
    print("-" * 58)


def main() -> int:
    sorun = 0
    print("=" * 58)
    print("  Mercek kurulum dogrulama")
    print("=" * 58)

    # ---------------------------------------------------------- 1. Python
    basli("1. Python surumu")
    s = sys.version_info
    if s >= (3, 11):
        ok(f"Python {s.major}.{s.minor}.{s.micro}")
    else:
        hata(f"Python {s.major}.{s.minor} cok eski", "Python 3.11 veya ustunu kurun")
        sorun += 1

    # ---------------------------------------------------------- 2. paketler
    basli("2. Paketler")
    paketler = [
        ("fastapi", "FastAPI"),
        ("pydantic", "Pydantic"),
        ("httpx", "httpx"),
        ("langgraph", "LangGraph"),
        ("qdrant_client", "Qdrant istemcisi"),
        ("torch", "PyTorch"),
        ("FlagEmbedding", "FlagEmbedding"),
        ("fitz", "PyMuPDF"),
        ("docx", "python-docx"),
    ]
    for modul, ad in paketler:
        try:
            m = __import__(modul)
            surum = getattr(m, "__version__", None)
            if not surum:
                # Bazi paketler __version__ tanimlamaz; paket ustverisinden okunur
                try:
                    from importlib.metadata import version as _s

                    surum = _s({"qdrant_client": "qdrant-client",
                                "docx": "python-docx",
                                "fitz": "PyMuPDF"}.get(modul, modul))
                except Exception:
                    surum = "kurulu"
            ok(f"{ad} {surum}")
        except ImportError:
            hata(f"{ad} kurulu degil", "pip install -r requirements.txt")
            sorun += 1

    # PyTorch CPU mu CUDA mi?
    try:
        import torch

        if "+cpu" in torch.__version__:
            ok("PyTorch CPU yapisi (dogru, gereksiz indirme yok)")
        elif torch.cuda.is_available():
            ok(f"PyTorch CUDA yapisi, GPU bulundu: {torch.cuda.get_device_name(0)}")
        else:
            print(f"  {SARI}[UYARI]{SIFIRLA} PyTorch CUDA yapisi ama GPU yok. "
                  "~2.5 GB gereksiz dosya indirilmis.")
            print("          requirements.txt icindeki --extra-index-url satirini "
                  "kontrol edip yeniden kurun.")
    except ImportError:
        pass

    # ---------------------------------------------------------- 3. ayarlar
    basli("3. Ayarlar")
    try:
        from app.config import get_settings

        a = get_settings()
        ok(f"Qdrant adresi: {a.qdrant_url}")
        ok(f"LLM adresi:    {a.llm_base_url}")
        ok(f"Model:         {a.llm_model}")
        ok(f"Gomme cihazi:  {a.embed_device}")
        ok(f"Dusunme modu:  {'acik' if a.llm_dusunme else 'kapali'}"
           + (f" (istisna: {a.dusunen_dugumler})" if a.dusunen_dugumler else ""))
        ok(f"HF cevrimdisi: {'evet' if a.hf_offline else 'hayir'}"
           + ("" if a.hf_token else "  (token yok, anonim kota)"))
    except Exception as e:
        hata(f"Ayarlar okunamadi: {e}", "Ayar dosyasi var mi? copy .env.ornek .env")
        return sorun + 1

    # ---------------------------------------------------------- 4. Qdrant
    basli("4. Qdrant baglantisi")
    try:
        from app.core.vectorstore import istemci

        q = istemci()
        koleksiyonlar = [c.name for c in q.get_collections().collections]
        ok(f"Baglandi. Koleksiyonlar: {koleksiyonlar or 'yok'}")

        if a.kb_collection in koleksiyonlar:
            adet = q.count(a.kb_collection).count
            if adet > 0:
                ok(f"Bilgi tabaninda {adet} kayit var")
            else:
                hata("Bilgi tabani bos", "python -m app.knowledge.ingest")
                sorun += 1
        else:
            hata("Bilgi tabani koleksiyonu yok", "python -m app.knowledge.ingest")
            sorun += 1
    except Exception as e:
        hata(f"Qdrant'a baglanilamadi: {type(e).__name__}",
             "Docker Desktop acik mi? docker compose up -d qdrant")
        sorun += 1

    # ---------------------------------------------------------- 5. LLM
    basli("5. Yerel LLM")
    try:
        import time

        from app.core.llm import llm

        bas = time.time()
        yanit = llm().metin(
            sistem="Sadece istenen kelimeyi yaz, baska hicbir sey yazma.",
            kullanici="'hazir' kelimesini yaz.",
        )
        sure = time.time() - bas
        ok(f"Model yanit verdi ({sure:.1f} sn): {yanit.strip()[:60]}")
        if sure > 30:
            print(f"  {SARI}[UYARI]{SIFIRLA} Yanit yavas. Ilk cagri model yuklemesi "
                  "icerir, tekrar calistirip karsilastirin.")
    except Exception as e:
        hata(f"LLM'e ulasilamadi: {type(e).__name__}",
             f"ollama list calisiyor mu? Model adi '{a.llm_model}' listede var mi?")
        sorun += 1

    # ---------------------------------------------------------- 6. gomme
    basli("6. Gomme modeli (BGE-M3)")

    # Model onbellekte mi? Cevrimdisi moda gecmeden once kontrol edilir.
    import os
    from pathlib import Path

    hf_kok = Path(a.hf_home or os.environ.get("HF_HOME")
                  or Path.home() / ".cache" / "huggingface")
    onbellek = hf_kok / "hub" / "models--BAAI--bge-m3"
    if onbellek.exists():
        boyut = sum(f.stat().st_size for f in onbellek.rglob("*") if f.is_file())
        ok(f"Model onbellekte: {onbellek}  ({boyut / 1024**3:.1f} GB)")
        if not a.hf_offline:
            print(f"  {SARI}[ONERI]{SIFIRLA} Model indirilmis. Artik .env icinde "
                  "MERCEK_HF_OFFLINE=true yapabilirsiniz;")
            print("          boylece acilista internete hic cikilmaz "
                  "(sunum gunu icin onemli).")
    else:
        print(f"  {SARI}[BILGI]{SIFIRLA} Model henuz indirilmemis, "
              "~2.2 GB indirilecek. Sabirli olun...")
        if a.hf_offline:
            hata("Cevrimdisi mod acik ama model onbellekte yok",
                 ".env icinde MERCEK_HF_OFFLINE=false yapip bir kez calistirin")
            sorun += 1
    try:
        from app.core.embeddings import gomme

        v = gomme().tek("Firebase veritabani kullanici verilerini saklar.")
        ok(f"Yogun vektor: {len(v['dense'])} boyut")
        ok(f"Seyrek vektor: {len(v['sparse'])} terim")
        if len(v["dense"]) != a.embed_dim:
            hata(f"Boyut uyusmuyor: {len(v['dense'])} != {a.embed_dim}",
                 f".env icinde MERCEK_EMBED_DIM={len(v['dense'])} yapin")
            sorun += 1
    except Exception as e:
        hata(f"Gomme modeli calismadi: {type(e).__name__}: {e}")
        sorun += 1

    # ---------------------------------------------------------- 7. arama
    basli("7. Uctan uca arama")
    try:
        from app.core.vectorstore import hibrit_ara

        sonuc = hibrit_ara(
            a.kb_collection,
            "third party cloud database stores personal data",
            limit=3,
        )
        if sonuc:
            ok(f"{len(sonuc)} kaynak bulundu:")
            for r in sonuc:
                print(f"          {r['kaynak_kimlik']:22s} skor={r['skor']:.3f}")
        else:
            hata("Arama sonuc dondurmedi", "Bilgi tabani dolu mu?")
            sorun += 1
    except Exception as e:
        hata(f"Arama basarisiz: {type(e).__name__}: {e}")
        sorun += 1

    # ---------------------------------------------------------- ozet
    print("\n" + "=" * 58)
    if sorun == 0:
        print(f"  {YESIL}Her sey hazir. uvicorn app.main:app --reload{SIFIRLA}")
    else:
        print(f"  {KIRMIZI}{sorun} sorun bulundu. Yukaridaki cozumleri uygulayin.{SIFIRLA}")
    print("=" * 58)
    return sorun


if __name__ == "__main__":
    sys.exit(min(main(), 1))
