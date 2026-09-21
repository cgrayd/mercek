/* Proje ozeti karti: belgenin amaci ve cikarilan olgu sayisi. Analizin en
   ustunde, bulgulardan once gosterilir. */

export default function Ozet({ ozet, olguSayisi }) {
  if (!ozet) return null
  return (
    <section className="kart">
      <div className="kart-basi">
        <h2>Proje özeti</h2>
        <span className="kart-sayi">{olguSayisi} olgu çıkarıldı</span>
      </div>
      <p className="ozet-amac">{ozet.amac}</p>
    </section>
  )
}
