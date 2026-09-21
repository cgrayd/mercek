/* Belge secme ve analizi baslatma alani: surukle-birak, dosya secici,
   boyut ve uzanti dogrulamasi. */

import { useRef, useState } from 'react'

/* Secim ile baslatma iki ayri adimdir. Dosya birakildigi anda analize
   baslamak, yanlis dosya birakan kullaniciya geri donus birakmiyor ve
   islem yerel modelde dakikalar suruyor. */
export default function Yukleme({ onBaslat, hata, calisiyor }) {
  const girdi = useRef(null)
  const [uzerinde, setUzerinde] = useState(false)
  const [dosya, setDosya] = useState(null)
  const [yerelHata, setYerelHata] = useState(null)

  const UZANTILAR = ['.pdf', '.docx', '.txt', '.md']
  const MB = 25

  // Dogrulama yuklemeden once yapilir; aksi halde tur ve boyut hatasi
  // ancak sunucudan doner.
  const dosyayiAl = (d) => {
    if (!d) return
    if (!UZANTILAR.some((u) => d.name.toLowerCase().endsWith(u))) {
      setDosya(null)
      setYerelHata('PDF, DOCX, TXT veya MD yükleyin')
      return
    }
    if (d.size > MB * 1024 * 1024) {
      setDosya(null)
      setYerelHata(`Dosya ${MB} MB sınırını aşıyor (${(d.size / 1024 / 1024).toFixed(1)} MB)`)
      return
    }
    setYerelHata(null)
    setDosya(d)
  }

  const birak = (olay) => {
    olay.preventDefault()
    setUzerinde(false)
    dosyayiAl(olay.dataTransfer.files?.[0])
  }

  const gosterilenHata = yerelHata || hata

  return (
    <div className="giris">
      <h1>Kod yazılmadan önce <em>riski görün</em></h1>
      <p>
        Proje raporunuzu veya tezinizi yükleyin. Dört ajan belgeyi okur, kullandığınız
        teknolojilerin veriyi nasıl işlediğini çıkarır ve doğrulamanız gereken noktaları
        kaynağıyla birlikte listeler.
      </p>

      {!dosya ? (
        <div
          className={`birak ${uzerinde ? 'aktif' : ''}`}
          onClick={() => girdi.current?.click()}
          onDragOver={(o) => { o.preventDefault(); setUzerinde(true) }}
          onDragLeave={() => setUzerinde(false)}
          onDrop={birak}
          role="button"
          tabIndex={0}
          onKeyDown={(o) => (o.key === 'Enter' || o.key === ' ') && girdi.current?.click()}
        >
          <div className="birak-ikon">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
            </svg>
          </div>
          <div className="birak-ana">Belgeyi buraya sürükleyin</div>
          <div className="birak-alt">
            veya seçmek için tıklayın · PDF, DOCX, TXT · en fazla {MB} MB
          </div>
        </div>
      ) : (
        /* Belge yerlesti, analiz henuz baslamadi. */
        <div className="birak yerlesik">
          <div className="secilen">
            <div className="secilen-ikon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z"
                      strokeLinejoin="round" />
                <path d="M14 3v5h5" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="secilen-bilgi">
              <div className="secilen-ad">{dosya.name}</div>
              <div className="secilen-boyut">{(dosya.size / 1024).toFixed(0)} KB · yüklemeye hazır</div>
            </div>
            <button
              type="button"
              className="secilen-kaldir"
              onClick={() => { setDosya(null); setYerelHata(null) }}
              disabled={calisiyor}
              aria-label="Belgeyi kaldır"
            >
              ×
            </button>
          </div>

          <div className="baslat-satiri">
            <button
              type="button"
              className="baslat"
              onClick={() => onBaslat(dosya)}
              disabled={calisiyor}
            >
              {calisiyor ? 'Başlatılıyor…' : 'Analizi başlat'}
            </button>
            <button
              type="button"
              className="baslat-ikincil"
              onClick={() => girdi.current?.click()}
              disabled={calisiyor}
            >
              Başka belge seç
            </button>
          </div>
        </div>
      )}

      <input
        ref={girdi}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        onChange={(o) => { dosyayiAl(o.target.files?.[0]); o.target.value = '' }}
      />

      {gosterilenHata && (
        <div className="not-satiri" style={{ color: '#EE8AA3' }}>{gosterilenHata}</div>
      )}

      <div className="not-satiri">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3l7 3v6c0 4-3 7.5-7 9-4-1.5-7-5-7-9V6l7-3z" strokeLinejoin="round" />
        </svg>
        Belgeniz yerel modelle işlenir ve analiz bitince oturum dizininden silinir.
      </div>
    </div>
  )
}
