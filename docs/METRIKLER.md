# Metrik Sözlüğü

Projedeki her sayının tanımı. Kodun karşılığı [analiz/metrikler.py](../analiz/metrikler.py): web sayfaları, tavsiye
motoru ve asistan bir metriğe ihtiyaç duyduğunda **yalnızca** buradaki fonksiyonları kullanır. Bir metriği başka bir
yerde yeniden hesaplamayın; yeni metrik gerekiyorsa `metrikler.py` içine ekleyip bu tabloya da yazın (bir test, ikisinin
senkron olduğunu kontrol eder).

## Kullanım

```python
from analiz import metrikler as m

m.hesapla("iade_orani", veri="gercek")                                          # tek sayı
m.hesapla("ciro_net", veri="sahte", baslangic="2026-09-01", bitis="2026-09-30")  # bitis günü dahil
m.hesapla("iade_orani", veri="gercek", kirilim="kategori")                      # kategori bazında
m.hesapla("ciro_net", veri="gercek", kirilim="hafta")                           # haftalık seri
m.donem_karsilastir("ciro_net", "gercek", "2026-10-01", "2026-10-23")           # önceki eşit dönemle
m.ozet("gercek")                                                                # son 30 günün ana KPI'ları
m.metrik_listesi()                                                              # tüm tanımlar (tablo)
m.yenile()                                                                      # veri yeniden üretildiyse önbelleği temizle
```

**Kırılımlar:** her metrik zaman birimlerine (`gun`, `hafta`, `ay`, `hafta_gunu`, `saat`) ve kendi çerçevesinin
alanlarına göre kırılabilir. Satış/iade/kârlılık metrikleri için `kategori`, `model_kodu`, `icerik_id`, `beden`, `renk`,
`is_birimi`, `sehir`, `kargo_firmasi`, `hizli_teslimat`, `odeme_yontemi`. Bir metriğin tüm kırılımları:
`m.kirilimlar("iade_orani")`.

## Hesaplama kuralları

1. **Tarih:** Satış, müşteri, iade, kârlılık ve operasyon metrikleri **sipariş tarihine** göre filtrelenir. "Eylül'ün iade
   oranı", Eylül'de verilen siparişlerin iade oranıdır. Finans ve gider metrikleri **işlem tarihine**, yorum, soru ve iade
   talebi metrikleri kendi tarihlerine göre filtrelenir.
2. **İptaller:** Satış ve kârlılık tutarlarına iptal edilen paketler katılmaz.
3. **Bölünmüş paketler:** Trendyol bir paketi bölünce eski paket `UnPacked` olur ve satırları yeni paketlerde tekrar yer
   alır. Bölünmüş paketler hiçbir metriğe katılmaz; aksi halde aynı satır iki kez sayılır.
4. **İade oranının olgunlaşması:** İade teslimden sonra açılıp kabul edilir. Gerçek veride kabul edilen iadelerin %99'u
   teslimden sonraki 21 gün içinde kabul ediliyor. `iade_orani` ve `beden_kaynakli_iade_payi` yalnızca **teslimi üzerinden
   21 gün geçmiş** satırlarla hesaplanır (`OLGUNLASMA_GUN`). Bu yüzden son 3 haftanın siparişleri iade oranına girmez.
   `iade_adet` ve `iade_tutari` ise şu ana kadar gelen iadeleri gösterir ve son haftalarda eksik görünür.
5. **Az örnek:** İade oranlarında paydası 30 birimden az olan dönem veya kırılım "hesaplanamadı" (NaN) döner
   (`MIN_ORNEK`). 3 ürünün hiçbiri iade edilmedi diye "iade oranı %0" göstermek yanıltıcıdır.
6. **Müşteri iadesi:** Kargo teslim edemeyip geri dönen paketler (`teslim_edilemedi`) iade sayılmaz; yalnızca
   `durum == "Accepted"` olan müşteri iadeleri sayılır.
7. **Katkı payı:** `elde kalan net satış − komisyon − kargo − iade kargo − platform bedeli`. Elde kalan = iptal ve iade
   düşülmüş. **Ürün maliyeti düşülmez.** Faturası henüz kesilmemiş paketlerin kargosu son 90 günün ortalamasıyla tahmin
   edilir. Son haftalarda iadeler henüz gelmediği için katkı payı olduğundan yüksek görünebilir.
8. **İyi yön:** Her metriğin "yüksek iyi", "düşük iyi" ya da "nötr" yönü vardır. `ozet()` değişimi bu yöne göre iyileşme
   (+1) / kötüleşme (−1) olarak işaretler; uyarılar ve tavsiyeler bunu kullanır.

## Gerçek veride kapsam

| kaynak | dönem | not |
|---|---|---|
| Sipariş, satış, iade oranı, kârlılık | 16 Temmuz 2026'dan beri, yalnızca Türkiye | `veri_araligi("gercek")` |
| Finans (`net_hakedis`, `finans_iade_orani`), giderler | son 1 yıl, yurt dışı dahil | sipariş metrikleriyle aynı dönem seçilse bile kapsamı farklıdır |
| İade talepleri (`iade_talebi_sayisi`) | 2024'ten beri, yurt dışı dahil | |
| Yorumlar, sorular | yorum: tümü, soru: ilk çekimden 12 hafta öncesinden beri | |

## Metrikler

### Satış

| metrik | başlık | birim | tanım | tarih | iyi yön |
|---|---|---|---|---|---|
| `ciro_brut` | Brüt ciro | TL | İndirim öncesi satış tutarı (iptaller hariç) | `siparis_tarihi` | yüksek |
| `ciro_net` | Net satış | TL | Müşterinin ödediği tutar (iptaller hariç, iadeler dahil) | `siparis_tarihi` | yüksek |
| `indirim_tutari` | İndirim tutarı | TL | Satıcı ve Trendyol indirimlerinin toplamı | `siparis_tarihi` | düşük |
| `indirim_orani` | İndirim oranı | oran | İndirim tutarı / brüt ciro | `siparis_tarihi` | düşük |
| `siparis_sayisi` | Sipariş sayısı | adet | İptal edilmemiş paket sayısı | `siparis_tarihi` | yüksek |
| `satilan_adet` | Satılan adet | adet | İptal edilmemiş satırlardaki ürün birimi | `siparis_tarihi` | yüksek |
| `ortalama_sepet` | Ortalama sepet | TL | Net satış / sipariş sayısı | `siparis_tarihi` | yüksek |
| `ortalama_birim_fiyat` | Ortalama birim fiyat | TL | Net satış / satılan adet | `siparis_tarihi` | yüksek |
| `iptal_orani` | İptal oranı | oran | İptal edilen paket / tüm paketler | `siparis_tarihi` | düşük |

### Müşteri

| metrik | başlık | birim | tanım | tarih | iyi yön |
|---|---|---|---|---|---|
| `musteri_sayisi` | Müşteri sayısı | adet | Dönemde sipariş veren tekil müşteri | `siparis_tarihi` | yüksek |
| `yeni_musteri_sayisi` | Yeni müşteri | adet | İlk siparişini bu dönemde veren müşteri | `siparis_tarihi` | yüksek |
| `tekrar_eden_musteri_orani` | Tekrar eden müşteri oranı | oran | Dönemde ilk siparişi dışında da siparişi olan müşteri / dönemdeki müşteriler | `siparis_tarihi` | yüksek |

### İade

| metrik | başlık | birim | tanım | tarih | iyi yön |
|---|---|---|---|---|---|
| `teslim_edilen_adet` | Teslim edilen adet | adet | Teslim edilmiş satırlardaki ürün birimi | `siparis_tarihi` | yüksek |
| `iade_adet` | İade adedi | adet | Kabul edilen müşteri iadesi (birim); teslim edilemeyip dönenler hariç | `siparis_tarihi` | düşük |
| `iade_orani` | İade oranı | oran | İade adedi / teslim edilen adet; yalnızca teslimi üzerinden 21 gün geçmiş satırlar | `siparis_tarihi` | düşük |
| `iade_tutari` | İade tutarı | TL | İade edilen birimlerin net fiyatı | `siparis_tarihi` | düşük |
| `beden_kaynakli_iade_payi` | Beden kaynaklı iade payı | oran | Küçük/büyük geldi iadeleri / tüm iadeler (teslimi üzerinden 21 gün geçmiş satırlar) | `siparis_tarihi` | düşük |
| `iade_talebi_sayisi` | İade talebi | adet | Açılan iade talebi birimleri (tüm durumlar, iade tarihine göre) | `iade_tarihi` | düşük |

### Kârlılık (ürün maliyeti hariç)

| metrik | başlık | birim | tanım | tarih | iyi yön |
|---|---|---|---|---|---|
| `komisyon_tutari` | Komisyon | TL | Elde kalan (iade düşülmüş) net satış × komisyon oranı | `siparis_tarihi` | düşük |
| `kargo_gideri` | Kargo gideri | TL | Gönderi kargo bedeli (faturası yoksa son 90 günün ortalaması) | `siparis_tarihi` | düşük |
| `iade_kargo_gideri` | İade kargo gideri | TL | İade kargo bedeli | `siparis_tarihi` | düşük |
| `platform_gideri` | Platform hizmet bedeli | TL | Gönderi başına platform hizmet bedeli (son 90 gün ortalaması) | `siparis_tarihi` | düşük |
| `katki_payi` | Katkı payı | TL | Elde kalan net satış − komisyon − kargo − iade kargo − platform (ürün maliyeti hariç) | `siparis_tarihi` | yüksek |
| `katki_marji` | Katkı marjı | oran | Katkı payı / net satış | `siparis_tarihi` | yüksek |

### Operasyon

| metrik | başlık | birim | tanım | tarih | iyi yön |
|---|---|---|---|---|---|
| `kargoya_verilis_suresi_saat` | Kargoya veriliş süresi | saat | Siparişten kargoya verilişe medyan süre | `siparis_tarihi` | düşük |
| `teslim_suresi_saat` | Teslim süresi | saat | Siparişten teslime medyan süre | `siparis_tarihi` | düşük |

### Finans (cari hesap)

| metrik | başlık | birim | tanım | tarih | iyi yön |
|---|---|---|---|---|---|
| `net_hakedis` | Net hakediş | TL | Trendyol'un satıcıya ödeyeceği net tutar (satış − indirim − kupon − iade, komisyon düşülmüş) | `islem_tarihi` | yüksek |
| `finans_iade_orani` | İade oranı (finans) | oran | Cari hesaptaki iade kaydı / satış kaydı (birim). Gerçek veride 1 yıl ve yurt dışını kapsar | `islem_tarihi` | düşük |
| `gider_toplam` | Toplam gider | TL | Kargo, platform, reklam, ceza ve diğer kesintiler (ödemeler ve komisyon faturası hariç) | `islem_tarihi` | düşük |
| `reklam_gideri` | Reklam gideri | TL | Reklam bakiyesi alımları ve müşteri duyuruları | `islem_tarihi` | nötr |

### Müşteri sesi

| metrik | başlık | birim | tanım | tarih | iyi yön |
|---|---|---|---|---|---|
| `yorum_sayisi` | Ürün yorumu | adet | Ürün değerlendirmesi sayısı | `yorum_tarihi` | yüksek |
| `ortalama_puan` | Ortalama ürün puanı | puan | Ürün yorumlarının ortalama puanı (1–5) | `yorum_tarihi` | yüksek |
| `olumsuz_yorum_orani` | Olumsuz yorum oranı | oran | 1–2 puanlı yorum / tüm yorumlar | `yorum_tarihi` | düşük |
| `satici_puani` | Satıcı puanı | puan | Satıcı değerlendirmelerinin ortalaması (1–5) | `yorum_tarihi` | yüksek |
| `kargo_puani` | Kargo puanı | puan | Satıcı değerlendirmelerindeki kargo puanı ortalaması (1–5) | `yorum_tarihi` | yüksek |
| `soru_sayisi` | Müşteri sorusu | adet | Ürün soruları | `soru_tarihi` | nötr |
| `medyan_cevap_suresi_dk` | Cevap süresi | dk | Sorudan cevaba medyan süre | `soru_tarihi` | düşük |
| `cevaplanmamis_soru_orani` | Cevaplanmamış soru oranı | oran | Cevaplanmamış soru / tüm sorular | `soru_tarihi` | düşük |
| `beden_sorusu_orani` | Beden sorusu oranı | oran | Beden soruları / tüm sorular | `soru_tarihi` | düşük |
