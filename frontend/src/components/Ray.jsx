/* Ajan hattinin calisma rayi: her dugumun ne is yaptigi, durumu ve
   olcumleri. Dogrulayici dugumunde elenen bulgu sayisi da gosterilir. */

import { useEffect, useRef, useState } from 'react'

/* Olcum anahtari -> ekranda gorunecek Turkce etiket. Backend anahtarlari
   log ve JSON icinde snake_case ve ASCII durur; kullaniciya gosterilen
   metin Turkce olmalidir. Liste backend'deki butun `_iz(...)`
   cagrilarindan cikarilmistir ve tam tutulmalidir. */
const OLCUM_ADLARI = {
  // ayristir / ozetle
  bolum: 'bölüm',
  analize_deger: 'analize değer',
  okunan_bolum: 'bölüm okundu',
  bilesen: 'bileşen',
  // yonlendir
  toplam_bolum: 'bölüm',
  kesin_evet: 'kesin seçildi',
  belirsiz: 'belirsiz bölüm',
  analize_alinan: 'analize alındı',
  llm_cagrisi: 'LLM çağrısı',
  // cikar (sozluk) / cikar_llm
  taranan_bolum: 'bölüm tarandı',
  sozlukten: 'sözlükten',
  llm_den: "LLM'den",
  toplam_olgu: 'olgu',
  soru_isareti: 'soru işareti',
  // getir / sorgu_yaz
  tur: 'tur',
  sorgulanan_olgu: 'olgu sorgulandı',
  kanit_bulunan: 'olgu kanıtlandı',
  zayif_kalan: 'zayıf kaldı',
  yedek_sorguyla: 'yedek sorguyla',
  yeniden_yazilan: 'yeniden yazıldı',
  // analiz
  uretilen_bulgu: 'bulgu',
  sablondan: 'şablondan',
  dayanaksiz_elenen: 'dayanaksız elendi',
  // dogrula
  denetlenen: 'denetlendi',
  kabul: 'kabul',
  elenen: 'elendi',
  makine_elenen: 'makine eledi',
  sablon_muaf: 'şablon muaf',
  llm_denetlenen: 'LLM denetledi',
  duzeltmesiz: 'düzeltmesiz revizyon',
}

/* Haritada olmayan bir anahtar gelirse alt cizgiler bosluga cevrilir;
   harita eksik kalsa da cikti okunabilir olur. */
const olcumAdi = (k) => OLCUM_ADLARI[k] || k.replace(/_/g, ' ')

export default function Ray({ dugumler, iz, bitti }) {
  const listeRef = useRef(null)
  const [yukseklik, setYukseklik] = useState(0)

  const izHaritasi = {}
  for (const kayit of iz) izHaritasi[kayit.dugum] = kayit

  const durumu = (anahtar, sira) => {
    if (izHaritasi[anahtar]) return 'bitti'
    if (bitti) return 'atlandi'
    const oncekiler = dugumler.slice(0, sira)
    const hepsiBitti = oncekiler.every((d) => izHaritasi[d.anahtar] || d.anahtar === 'sorgu_yaz')
    return hepsiBitti ? 'calisiyor' : 'bekliyor'
  }

  useEffect(() => {
    if (!listeRef.current) return
    const ogeler = [...listeRef.current.querySelectorAll('.dugum')]
    const sonAktif = ogeler.reduce(
      (a, o, i) => (o.classList.contains('bitti') || o.classList.contains('calisiyor') ? i : a),
      -1,
    )
    if (sonAktif < 0) return setYukseklik(0)
    const o = ogeler[sonAktif]
    setYukseklik(o.offsetTop + 12)
  }, [iz, bitti, dugumler])

  return (
    <aside className="ray">
      <div className="ray-baslik">çalışma rayı</div>
      <div className="ray-liste" ref={listeRef}>
        <div className="ray-ilerleme" style={{ height: `${yukseklik}px` }} />
        {dugumler.map((d, i) => {
          const durum = durumu(d.anahtar, i)
          const kayit = izHaritasi[d.anahtar]
          return (
            <div className={`dugum ${durum}`} key={d.anahtar}>
              <span className="dugum-nokta" />
              <div className="dugum-ad">{d.ad}</div>
              {/* Aciklama dugum bittikten sonra da kalir: raporu okurken
                  hangi adimin ne yaptigi gorunur olmalidir. Sure ayri bir
                  satirda gosterilir. */}
              <div className="dugum-aciklama">{d.aciklama}</div>
              {kayit?.sure_ms != null && (
                <div className="dugum-sure">
                  {(kayit.sure_ms / 1000).toFixed(1)} sn
                </div>
              )}
              {kayit?.olcum && (
                <div className="olcumler">
                  {Object.entries(kayit.olcum)
                    .filter(([, v]) => v !== 0)
                    .map(([k, v]) => (
                      <span
                        className={`olcum ${k.includes('elen') ? 'eleme' : ''}`}
                        key={k}
                      >
                        {v} {olcumAdi(k)}
                      </span>
                    ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </aside>
  )
}
