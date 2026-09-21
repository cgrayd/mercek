/* Tek bir bulgu karti: baslik, risk alani etiketi, aciklama ve kontrol
   onerisi; altta dayanak cipleri. Cipe tiklandiginda belgeden alinti veya
   standart metni acilir, boylece her iddianin kaynagi gorulebilir. */

import { useState } from 'react'

const ALAN_ADLARI = {
  guvenlik: 'güvenlik',
  veri_sizintisi: 'veri sızıntısı',
  hukuki: 'hukuki',
}

export default function Bulgu({ bulgu, olgular }) {
  const [acik, setAcik] = useState(null)

  const olguBul = (id) => olgular.find((o) => o.olgu_id === id)

  return (
    <article className={`bulgu alan-${bulgu.alan}`}>
      <span className="serit" />

      <div className="bulgu-basi">
        <h3>{bulgu.baslik}</h3>
        <span className="alan-etiketi">{ALAN_ADLARI[bulgu.alan]}</span>
      </div>

      <p>{bulgu.aciklama}</p>

      <div className="oneri">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 16v-4M12 8h.01" strokeLinecap="round" />
        </svg>
        <span>{bulgu.kontrol_onerisi}</span>
      </div>

      {/* Her bulgu iki dayanak tasir: belgeden ve standarttan. Dayanaksiz
          bulgu bu noktaya ulasmaz. */}
      <div className="dayanak">
        <span className="dayanak-etiket">dayanak</span>
        {bulgu.belge_dayanagi.map((id) => (
          <button
            key={id}
            className="cip belge"
            onClick={() => setAcik(acik === id ? null : id)}
          >
            {olguBul(id)?.ad || id}
          </button>
        ))}
        {bulgu.kaynak_dayanagi.map((k) => (
          <button
            key={k.kaynak_kimlik}
            className="cip"
            onClick={() => setAcik(acik === k.kaynak_kimlik ? null : k.kaynak_kimlik)}
          >
            {k.kaynak_kimlik}
          </button>
        ))}
      </div>

      {acik && (() => {
        const olgu = olguBul(acik)
        if (olgu) {
          return (
            <div className="alinti">
              <b>belgeden — {olgu.kaynak_bolum}</b>
              “{olgu.alinti}”
            </div>
          )
        }
        const kaynak = bulgu.kaynak_dayanagi.find((k) => k.kaynak_kimlik === acik)
        return (
          <div className="alinti">
            <b>{kaynak.kaynak_kimlik} — {kaynak.baslik}</b>
            {kaynak.ozet}
          </div>
        )
      })()}
    </article>
  )
}
