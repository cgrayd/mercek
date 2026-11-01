"""Bilgi tabani yukleyici.

    python -m app.knowledge.ingest              # tohum veriyi yukle
    python -m app.knowledge.ingest --sifirla    # koleksiyonu bastan kur
    python -m app.knowledge.ingest --asvs asvs.json   # tam ASVS korpusu
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.core import vectorstore
from app.knowledge.seed_data import TOHUM

AYAR = get_settings()


def asvs_json_oku(yol: Path) -> list[dict]:
    """OWASP ASVS resmi JSON dagitimini kayit listesine cevirir.

    Beklenen dosya: `..._en.flat.json` (ASVS 5.0 ve sonrasi).
    Indirme adresi icin SETUP.md'ye bakin.

    Yapisi:
        {"requirements": [
            {"chapter_id": "V1", "chapter_name": "...",
             "section_id": "V1.1", "section_name": "...",
             "req_id": "V1.1.1", "req_description": "...", "L": "2"},
            ...
        ]}

    Eski (4.x) ic ice yapi da desteklenir.
    """
    veri = json.loads(yol.read_text(encoding="utf-8"))
    kayitlar: list[dict] = []
    URL = "https://owasp.org/www-project-application-security-verification-standard/"

    # --- ASVS 5.x: duz liste ---
    if isinstance(veri, dict) and "requirements" in veri:
        for m in veri["requirements"]:
            metin = (m.get("req_description") or "").strip()
            if not metin:
                continue
            # "V1.1.1" -> "ASVS 1.1.1"
            kimlik = str(m.get("req_id", "")).lstrip("Vv")
            seviye = m.get("L") or m.get("level") or ""
            kayitlar.append({
                "kaynak_turu": "asvs",
                "kaynak_kimlik": f"ASVS {kimlik}",
                "baslik": m.get("section_name") or m.get("chapter_name") or "ASVS",
                # Bolum adi metne katilir: gomme vektoru baglami korur ve
                # "Encoding" gibi ust kavramlar aranabilir hale gelir.
                "metin": f"[{m.get('chapter_name', '')}] {metin}",
                "dil": "en",
                "seviye": seviye,
                "url": URL,
            })
        return kayitlar

    # --- ASVS 4.x: ic ice yapi (geriye donuk uyumluluk) ---
    for bolum in veri.get("Requirements", []):
        for alt in bolum.get("Items", []):
            for madde in alt.get("Items", []):
                metin = (madde.get("Description") or "").strip()
                if not metin:
                    continue
                kayitlar.append({
                    "kaynak_turu": "asvs",
                    "kaynak_kimlik": f"ASVS {madde.get('Shortcode', '').lstrip('Vv')}",
                    "baslik": alt.get("Name", bolum.get("Name", "ASVS")),
                    "metin": metin,
                    "dil": "en",
                    "url": URL,
                })
    return kayitlar


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sifirla", action="store_true", help="koleksiyonu sil ve yeniden kur")
    ap.add_argument("--asvs", type=Path, help="OWASP ASVS JSON dosyasi")
    args = ap.parse_args()

    vectorstore.koleksiyon_kur(AYAR.kb_collection, sifirla=args.sifirla)

    kayitlar = list(TOHUM)
    if args.asvs:
        ek = asvs_json_oku(args.asvs)
        print(f"ASVS dosyasindan {len(ek)} madde okundu")
        # Tam korpus verildiyse tohumdaki ASVS maddeleri atilir. Tohum
        # ASVS 4.0.3 numaralarini, resmi JSON ise 5.0 numaralarini kullanir
        # ve ayni kimlik iki surumde farkli gereksinimi gosterir. Kanit
        # zinciri kimlik uzerinden kuruldugundan ayni kimlige iki farkli
        # metin, atfin yanlis metni gostermesi demektir.
        kayitlar = [k for k in kayitlar if k["kaynak_turu"] != "asvs"] + ek

    yazilan = vectorstore.yaz(AYAR.kb_collection, kayitlar)
    print(f"{yazilan} kayit '{AYAR.kb_collection}' koleksiyonuna yazildi")

    dagitim: dict[str, int] = {}
    for k in kayitlar:
        dagitim[k["kaynak_turu"]] = dagitim.get(k["kaynak_turu"], 0) + 1
    for tur, adet in sorted(dagitim.items()):
        print(f"  {tur:12s} {adet}")


if __name__ == "__main__":
    main()
