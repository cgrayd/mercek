/* Uygulamanin ana ekrani ve tek durum sahibi: belge yukleme, canli analiz
   izleme (SSE), bulgu listesi ve risk alanina gore sekme filtresi burada
   birlesir. Analiz kimligi sessionStorage'da tutulur, sayfa yenilense de
   kosum kaybolmaz. */

import { useEffect, useRef, useState } from 'react'
import { analizBaslat, analizGetir, analiziIzle, dugumleriGetir } from './api'
import Bulgu from './components/Bulgu'
import Ozet from './components/Ozet'
import Ray from './components/Ray'
import Yukleme from './components/Yukleme'

const SEKMELER = [
  { anahtar: 'hepsi', ad: 'Tümü' },
  { anahtar: 'guvenlik', ad: 'Güvenlik' },
  { anahtar: 'veri_sizintisi', ad: 'Veri sızıntısı' },
  { anahtar: 'hukuki', ad: 'Hukuki' },
]

/* Calisan analizin kimligi sekme deposunda tutulur.
 *
 * sessionStorage secilmesinin sebebi omru: sayfa yenilendiginde veya ekran
 * kapandiginda kayit durur, sekme ya da pencere kapatildiginda tarayici
 * kendisi siler. localStorage kapatildiktan sonra da tutardi. */
const DEPO_ANAHTARI = 'mercek.calisan_analiz'

export default function App() {
  const [dugumler, setDugumler] = useState([])
  const [analiz, setAnaliz] = useState(null)
  const [dosyaAdi, setDosyaAdi] = useState(null)
  const [sekme, setSekme] = useState('hepsi')
  const [hata, setHata] = useState(null)
  const [baglanti, setBaglanti] = useState(null)   // kopma/yeniden baglanma bildirimi
  const [baslatiliyor, setBaslatiliyor] = useState(false)
  const izleyiciyiBirak = useRef(null)

  useEffect(() => {
    dugumleriGetir().then(setDugumler).catch(() => setHata('Sunucuya bağlanılamadı'))
  }, [])

  const durumBildir = (d) => {
    if (d.tur === 'koptu') {
      setBaglanti(`Bağlantı koptu — ${Math.round(d.bekleMs / 1000)} sn içinde yeniden denenecek. `
                  + 'Analiz sunucuda çalışmaya devam ediyor.')
    } else {
      setBaglanti(null)
    }
  }

  const izlemeyeBasla = (analizId) => {
    izleyiciyiBirak.current?.()
    izleyiciyiBirak.current = analiziIzle(analizId, setAnaliz, durumBildir)
  }

  /* Acilista calisan analize devam edilir.
   *
   * Sayfa yenilendiginde React durumu sifirlanir; kimlik tutulmazsa
   * backend'de calismaya devam eden analize geri donmenin yolu kalmaz.
   * Kimlik sekme deposunda durur: acilista once anlik durum cekilir, is
   * hala suruyorsa akisa yeniden baglanilir. */
  useEffect(() => {
    const kayitli = sessionStorage.getItem(DEPO_ANAHTARI)
    if (!kayitli) return
    let iptal = false
    ;(async () => {
      try {
        const { analiz_id, dosya_adi } = JSON.parse(kayitli)
        const anlik = await analizGetir(analiz_id)
        if (iptal) return
        if (!anlik) {                       // sunucu yeniden baslamis
          sessionStorage.removeItem(DEPO_ANAHTARI)
          return
        }
        setDosyaAdi(anlik.dosya_adi || dosya_adi)
        setAnaliz(anlik)
        if (anlik.durum === 'calisiyor' || anlik.durum === 'kuyrukta') {
          izlemeyeBasla(analiz_id)
        }
      } catch {
        sessionStorage.removeItem(DEPO_ANAHTARI)
      }
    })()
    return () => { iptal = true }
  }, [])

  // Sayfa kapanirken izleyici birakilir; kayit sekme deposunda kalir.
  useEffect(() => () => izleyiciyiBirak.current?.(), [])

  const basla = async (dosya) => {
    setHata(null)
    setBaglanti(null)
    setBaslatiliyor(true)
    setDosyaAdi(dosya.name)
    try {
      const { analiz_id } = await analizBaslat(dosya)
      sessionStorage.setItem(DEPO_ANAHTARI,
        JSON.stringify({ analiz_id, dosya_adi: dosya.name }))
      setAnaliz({
        durum: 'calisiyor',
        iz: [], bulgular: [], olgular: [], elenenler: [], soru_isaretleri: [],
      })
      izlemeyeBasla(analiz_id)
    } catch (h) {
      setHata(h.message)
      setDosyaAdi(null)
    } finally {
      setBaslatiliyor(false)
    }
  }

  const yeniAnaliz = () => {
    izleyiciyiBirak.current?.()
    sessionStorage.removeItem(DEPO_ANAHTARI)
    setAnaliz(null)
    setDosyaAdi(null)
    setHata(null)
    setBaglanti(null)
    setSekme('hepsi')
  }

  const sayim = (alan) =>
    alan === 'hepsi'
      ? analiz?.bulgular.length || 0
      : analiz?.bulgular.filter((b) => b.alan === alan).length || 0

  const gorunen =
    sekme === 'hepsi'
      ? analiz?.bulgular || []
      : (analiz?.bulgular || []).filter((b) => b.alan === sekme)

  return (
    <div className="kabuk">
      <header className="ust">
        <div className="marka">
          <div className="isaret">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="10.5" cy="10.5" r="6.5" />
              <path d="M15.5 15.5L21 21" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <div className="marka-ad">Mercek</div>
            <div className="marka-alt">tasarım aşaması risk ön-taraması</div>
          </div>
        </div>
        <div className="ust-sag">
          {dosyaAdi && <span className="rozet">{dosyaAdi}</span>}
          {analiz && (
            <button type="button" className="baslat-ikincil" onClick={yeniAnaliz}>
              Yeni analiz
            </button>
          )}
        </div>
      </header>

      {/* Baglanti kopmasi bir hata degil, gecici bir durumdur: analiz
          sunucuda calismaya devam eder ve kullaniciya bu bildirilir. */}
      {baglanti && <div className="baglanti-uyarisi">{baglanti}</div>}

      {!analiz ? (
        <Yukleme onBaslat={basla} hata={hata} calisiyor={baslatiliyor} />
      ) : (
        <div className="duzen">
          <Ray dugumler={dugumler} iz={analiz.iz || []} bitti={analiz.durum === 'bitti'} />

          <main>
            {analiz.durum === 'hata' && (
              <div className="kart">
                <div className="kart-basi"><h2>Analiz tamamlanamadı</h2></div>
                <p style={{ color: 'var(--sis)' }}>{analiz.hata}</p>
              </div>
            )}

            {/* Bulgular akarak geldigi icin son bulgu ekrana dustukten
                sonraki hareketsizlik, dogrulayicinin hala calistigi
                durumla ayni gorunur; bitis acikca bildirilir. */}
            {analiz.durum === 'bitti' && (
              <div className="tamamlandi" role="status">
                <span className="tamamlandi-im" aria-hidden="true">✓</span>
                <span>
                  Analiz tamamlandı
                  {analiz.bulgular?.length > 0 && (
                    <span className="tamamlandi-ayrinti">
                      {' — '}{analiz.bulgular.length} bulgu
                      {analiz.olgular?.length > 0 && `, ${analiz.olgular.length} olgu`}
                    </span>
                  )}
                </span>
              </div>
            )}

            <Ozet ozet={analiz.ozet} olguSayisi={analiz.olgular?.length || 0} />

            {analiz.bulgular?.length > 0 && (
              <>
                <div className="suzgec">
                  {SEKMELER.map((s) => (
                    <button
                      key={s.anahtar}
                      className={`sekme ${sekme === s.anahtar ? 'secili' : ''}`}
                      onClick={() => setSekme(s.anahtar)}
                    >
                      {s.ad}<span className="sekme-sayi">{sayim(s.anahtar)}</span>
                    </button>
                  ))}
                </div>

                {gorunen.map((b) => (
                  <Bulgu key={b.bulgu_id} bulgu={b} olgular={analiz.olgular || []} />
                ))}
              </>
            )}

            {analiz.durum === 'calisiyor' && !analiz.bulgular?.length && (
              <div className="bos">Ajanlar çalışıyor. Bulgular hazır oldukça burada belirir.</div>
            )}

            {analiz.durum === 'bitti' && !analiz.bulgular?.length && (
              <div className="bos">
                Doğrulanmış bir bulgu çıkmadı. Belge yeterli teknik ayrıntı içermiyor
                olabilir; mimari ve veri bölümleri daha detaylıysa tekrar deneyin.
              </div>
            )}

            {/* Deginilmemis konular. Bunlar bulgu degildir: bir yoklugun
                kaniti olamayacagi icin detaya girilmeden, ciktinin en
                altinda kisa bir liste halinde sunulur. */}
            {analiz.durum === 'bitti' && analiz.soru_isaretleri?.length > 0 && (
              <div className="kart soru-isaretleri">
                <div className="kart-basi">
                  <h2>Soru işaretleri</h2>
                  <span className="rozet">{analiz.soru_isaretleri.length}</span>
                </div>
                <p style={{ color: 'var(--sis)', marginBottom: 12 }}>
                  Raporda değinilmemiş, kontrol etmek isteyebileceğiniz başlıklar.
                  Bunlar bulgu değildir; bir eksikliğin kanıtı olamayacağı için
                  ayrı tutulur.
                </p>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {analiz.soru_isaretleri.map((s, i) => (
                    <li key={i} style={{ marginBottom: 6 }}>
                      {s.baslik}
                      {s.kaynak_bolum && (
                        <span style={{ color: 'var(--sis)' }}> — {s.kaynak_bolum}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Dogrulayicinin reddettigi taslaklar; seffaflik icin
                gosterilir. */}
            {analiz.elenenler?.length > 0 && (
              <details className="elenen-kart">
                <summary>
                  Doğrulayıcının elediği {analiz.elenenler.length} taslak bulgu
                </summary>
                <div style={{ marginTop: 14 }}>
                  {analiz.elenenler.map((e, i) => (
                    <div className="elenen-satir" key={i}>
                      <b>{e.baslik}</b>
                      <span>{e.ret_nedeni}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}

            {analiz.durum === 'bitti' && (
              <div className="feragat">
                <b>Bu bir denetim raporu değildir.</b> Mercek koda değil, belgeye bakar;
                implementasyonu göremediği için kesin hüküm vermez. Buradaki maddeler
                doğrulanması gereken noktalardır ve hukuki danışmanlık yerine geçmez.
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  )
}
