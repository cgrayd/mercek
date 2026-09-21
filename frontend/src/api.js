/* Backend ile konusan tek katman: analiz baslatma, durum cekme ve sunucu
   tarafli olay akisiyla (SSE) canli izleme. Baska hicbir bilesen dogrudan
   fetch cagirmaz. */

const TABAN = import.meta.env.VITE_API || 'http://localhost:8000'

export async function dugumleriGetir() {
  const y = await fetch(`${TABAN}/api/dugumler`)
  if (!y.ok) throw new Error('Düğüm listesi alınamadı')
  return y.json()
}

export async function analizBaslat(dosya) {
  const govde = new FormData()
  govde.append('dosya', dosya)
  const y = await fetch(`${TABAN}/api/analiz`, { method: 'POST', body: govde })
  if (!y.ok) {
    const h = await y.json().catch(() => ({}))
    throw new Error(h.detail || 'Yükleme başarısız')
  }
  return y.json()
}

/* Bir analizin anlik durumunu ceker. Yeniden baglanirken gereklidir: SSE
   yalnizca degisiklik yayinladigi icin akisa sonradan katilan istemci o
   ana kadar birikeni goremez. */
export async function analizGetir(analizId) {
  const y = await fetch(`${TABAN}/api/analiz/${analizId}`)
  if (y.status === 404) return null       // sunucu yeniden baslamis olabilir
  if (!y.ok) throw new Error('Analiz durumu alınamadı')
  return y.json()
}

/* SSE ile canli izleme; baglanti koparsa yeniden baglanir.
 *
 * Ekran kapandiginda veya ag kesildiginde tarayici SSE baglantisini
 * dusurur. Analiz backend'de ayri bir is parcaciginda calistigi ve
 * istemcinin baglantisindan etkilenmedigi icin dogru davranis vazgecmek
 * degil, ustel geri cekilmeyle yeniden baglanmaktir.
 */
export function analiziIzle(analizId, onVeri, onDurumBildir) {
  let kaynak = null
  let kapandi = false
  let deneme = 0
  let zamanlayici = null

  const bagla = () => {
    if (kapandi) return
    kaynak = new EventSource(`${TABAN}/api/analiz/${analizId}/akis`)

    kaynak.onopen = () => {
      if (deneme > 0) onDurumBildir?.({ tur: 'baglandi' })
      deneme = 0
    }

    kaynak.onmessage = (olay) => {
      const veri = JSON.parse(olay.data)
      onVeri(veri)
      if (veri.durum === 'bitti' || veri.durum === 'hata') {
        kapandi = true
        kaynak.close()
      }
    }

    kaynak.onerror = () => {
      kaynak.close()
      if (kapandi) return
      deneme += 1
      const bekle = Math.min(1000 * 2 ** (deneme - 1), 15000)
      onDurumBildir?.({ tur: 'koptu', deneme, bekleMs: bekle })
      zamanlayici = setTimeout(async () => {
        // Once anlik durum cekilir: bekleme sirasinda analiz bitmis
        // olabilir, o durumda akisa baglanmaya gerek yoktur.
        try {
          const anlik = await analizGetir(analizId)
          if (anlik) {
            onVeri(anlik)
            if (anlik.durum === 'bitti' || anlik.durum === 'hata') {
              kapandi = true
              onDurumBildir?.({ tur: 'baglandi' })
              return
            }
          }
        } catch { /* ag hala kapali olabilir, akis denemesi surer */ }
        bagla()
      }, bekle)
    }
  }

  bagla()
  return () => {
    kapandi = true
    clearTimeout(zamanlayici)
    kaynak?.close()
  }
}
