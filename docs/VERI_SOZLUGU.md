# Trendyol Satıcı Veri Seti — Veri Sözlüğü

Kurulum, klasör yapısı ve güncelleme komutları için proje kökündeki [README.md](../README.md) dosyasına bakın.

`gercek` ve `sahte` klasörleri **aynı tablo ve sütunlara** sahiptir. Sahte veride geliştirilen kod,
klasör adı değiştirilerek gerçek veride çalışır.

### Gerçek veride hangi tablo ne kadar geriye gider?

| kaynak | kapsam | not |
|---|---|---|
| siparişler | ilk çekimden itibaren birikir (API tek seferde son ~3 ayı verir), yalnızca Türkiye mağazası | günlük çekimle geçmiş kaybolmaz |
| iadeler | mağazanın açılışından bugüne, tüm ülkeler | |
| finans hareketleri, kesintiler, kargo faturaları | ilk çekimde son 1 yıl, sonra birikir; tüm ülkeler | `cekim/finans.py` içindeki `ILK_GUN` |
| ürünler, sorular, yorumlar | bugünkü katalog / ilk çekimde 12 hafta, sonra birikir / tümü | fiyat-stok geçmişi `veri/ham/urun_gecmisi/` altında günlük birikir |

Bu yüzden eski ve yurt dışı iade/finans kayıtları `siparisler`'e bağlanmaz ama **barkod ile `urunler`'e bağlanır**.
1 yıllık ürün satış/iade geçmişi için finans kayıtlarını kullanın (`urun_ozet.yil_*`, `beden_iade_analizi`).

## Tablolar arası ilişkiler

```
                       sorular ──model_kodu──┐
                                             ▼
siparisler ─paket_id─► siparis_satirlari ─barkod─► urunler ◄─icerik_id── urun_yorumlari
 │ ▲  ▲  ▲                 ▲       ▲               ▲  ▲
 │ │  │  │          satir_id│       │satir_id  barkod│  │barkod
 │ │  │  │                 │  finans_hareketleri ───┘  │
 │ │  │  │                 └── iadeler ────────────────┘
 │ │  │  └─paket_id── kargo_faturalari
 │ │  └────paket_id── siparis_indirimleri
 │ └───────paket_id── siparis_durum_gecmisi
 └─musteri_id (anonim)

kesintiler (kargo/reklam/platform/ceza faturaları, ödemeler) ve satici_yorumlari: mağaza geneli, tarihle ilişkilenir
```

Ürün hiyerarşisi: **model_kodu** (model) → **icerik_id** (renk / ürün sayfası) → **barkod** (renk + beden varyantı).
Yorumlar renk düzeyinde (`icerik_id`), sorular model düzeyinde (`model_kodu`), satışlar varyant düzeyinde (`barkod`) gelir.

Bir sipariş satırı birden çok **birim (kalem)** içerebilir (`adet` > 1). İade ve finans kayıtları birim bazındadır:
`kalem_id` birimi, `satir_id` ait olduğu sipariş satırını gösterir.

## Temel tablolar

### urunler — varyant başına bir satır (anahtar: `barkod`)
| sütun | açıklama |
|---|---|
| barkod, urun_kodu | varyant kimlikleri (urun_kodu = API `productCode`) |
| icerik_id | ürün sayfası / renk (API `productContentId`) |
| model_kodu | model (API `productMainId`) |
| urun_adi, kategori, is_birimi, renk, beden | |
| liste_fiyati, satis_fiyati | **bugünkü** fiyat (0 TL → boş) |
| stok, satista, arsivde | bugünkü durum |
| katalogda | False = katalogdan silinmiş ama geçmiş sipariş/iadelerde geçen ürün |
| olusturma_tarihi | ürünün eklendiği tarih |

### siparisler — kargo paketi başına bir satır (anahtar: `paket_id`)
| sütun | açıklama |
|---|---|
| siparis_no, musteri_id | müşteri ID'si tek yönlü özet (ör. `Mf93d2ac869`) |
| siparis_tarihi | Türkiye saati (tüm tablolarda tarihler Türkiye saatidir) |
| sehir, ilce | teslimat il/ilçe |
| odeme_yontemi | **~8 haftadan eski siparişlerde boş** (Trendyol gizliyor) |
| kargo_firmasi, hizli_teslimat | FastDelivery / SameDayShipping / Yok |
| paket_durumu | Delivered, Cancelled, Shipped, ReadyToShip, UnDeliveredAndReturned, UnPacked. **UnPacked** = Trendyol'un böldüğü paket; satırları yeni paketlerde tekrar yer alır, satış sayılmaz (gerçek veride 2 paket) |
| brut_tutar, satici_indirimi, trendyol_indirimi, net_tutar | net = brüt − indirimler |
| tahmini_teslim_bas/bit, kargoya_verilis_tarihi, teslim_tarihi | |
| iptal, teslim_edilemedi, iade_dondu | durum geçmişinden türetilen bayraklar |

### siparis_satirlari — paketteki ürünler (anahtar: `satir_id`)
`birim_*` sütunları **birim** fiyattır; `satir_net_tutar = birim_net_fiyat × adet`.
`komisyon_orani` (%) ve `kdv_orani` (%) kârlılık hesabı için.

### siparis_durum_gecmisi
Paket başına durum adımları: Awaiting → Created → Picking → Shipped → (UnDelivered) → Delivered / Cancelled / Returned.

### siparis_indirimleri
Paket başına uygulanan her indirim. `indirim_turu`: magaza_kuponu, sepet_indirimi, plus_fiyat, coklu_alim, diger.

### sorular (anahtar: `soru_id`)
`konu` (kural tabanlı): beden, olcu, kargo, stok, kumas, renk, iade_degisim, diger. `cevap_suresi_dk` hazır.

### urun_yorumlari / satici_yorumlari
Ürün yorumu: puan 1–5, metin, alınan beden, (varsa) boy/kilo.
Satıcı yorumu: satıcı ve kargo puanı ayrı, Trendyol'un neden kodları (`PRODUCT_QUALITY_NEGATIVE` vb.).

### iadeler — iade talebindeki her birim (anahtar: `iade_kalem_id`)
| sütun | açıklama |
|---|---|
| iade_id | talep; aynı paketten birlikte iade edilen birimler aynı talepte |
| siparis_no, paket_id, satir_id, kalem_id, barkod | bağlantılar. `paket_id` temizlemede satır üzerinden sipariş tablosundaki pakete çevrilir (Trendyol'un iade kaydındaki paket kimliği farklıdır); satırı bilinmeyen eski ve yurt dışı iadelerde boştur |
| siparis_tarihi, iade_tarihi, son_guncelleme | |
| neden_kodu, neden | Trendyol kodu (SMALLSIZE, BIGSIZE, DISLIKE, DAMAGEDITEM ...) ve metni |
| neden_grubu | beden_kucuk, beden_buyuk, begenmedim, kusurlu, yanlis_eksik_urun, vazgecti, teslim_edilemedi, diger |
| musteri_notu | müşterinin iade açıklaması (serbest metin, NLP için) |
| durum | Accepted, Cancelled (müşteri vazgeçti), Rejected, Created/WaitingInAction (sürüyor) |
| karar_veren | SYSTEM (otomatik kabul) / SELLER |

**İade oranı hesaplarken yalnızca `durum == "Accepted"` kullanın.**

### finans_hareketleri — cari hesap, birim bazında (anahtar: `hareket_id`)
Her teslim edilen birim için teslim anında `Satış`, varsa `İndirim` ve `Kupon` (mağaza kuponları) kaydı düşer.
İade kabul edilince `İade`, `İndirim İptal`, `Kupon İptal` düşer.

| sütun | açıklama |
|---|---|
| islem_turu | Satış, İndirim, Kupon, İade, İndirim İptal, Kupon İptal |
| borc / alacak | tutar (satıcı alacaklı = gelir) |
| komisyon_orani, komisyon_tutari | komisyon = tutar × oran |
| satici_hakedisi | tutar − komisyon |
| vade_gun, odeme_tarihi | Trendyol'un ödeme yapacağı tarih |
| ulke | Türkiye veya mikro ihracat ülkesi |

Net hakediş = Σ hakediş × işaret (Satış, İptaller +; İndirim, Kupon, İade −).

### kesintiler — siparişe bağlı olmayan cari hareketler (anahtar: `kesinti_id`)
`grup`: kargo, platform_hizmet, reklam, ceza_tazmin, uluslararasi, finansman, diger, **odeme**, **komisyon_faturasi**.
Giderleri toplarken `odeme` (Trendyol'un satıcıya yaptığı ödeme) ve `komisyon_faturasi` (satır komisyonlarının
haftalık faturası, finans_hareketleri ile mükerrer) gruplarını **dahil etmeyin**.

### kargo_faturalari — kargo faturalarının gönderi bazlı detayı
`gonderi_turu`: Gönderi Kargo Bedeli (satış gönderisi) / İade Kargo Bedeli (iade kargosu da satıcıya yansır).
`desi`, `tutar`, `paket_id`. Faturalar 2–5 hafta gecikmeli kesilir; son haftaların gönderilerinin faturası henüz yoktur.

## Analiz tabloları (`analiz/`)

| tablo | düzey | ne için |
|---|---|---|
| satis_detay | satış satırı | keşifsel analiz; sipariş+ürün+iade+maliyet+takvim tek tabloda |
| gunluk_satis | gün | mağaza satış tahmini; iade ve gider (reklam, kargo ...) serileri |
| gunluk_urun_satis | ürün × gün | ürün talep tahmini, fiyat/indirim esnekliği, stok planlama |
| urun_ozet | ürün (renk) | ürün skorlama: satış, puan, iade oranları (neden kırılımlı), katkı payı, 1 yıllık finans |
| musteri_ozet | müşteri | RFM segmentasyonu, CLV, churn; müşterinin iade oranı ve katkısı |
| musteri_urun_etkilesim | müşteri × ürün | öneri sistemi (matrix factorization, neural CF) |
| birlikte_alinanlar | model çifti | çapraz satış, paket/kombin önerisi (destek, güven, lift) |
| aylik_finans | ay | kâr-zarar: brüt satış, indirim, iade, komisyon, net hakediş, giderler, net kalan |
| beden_iade_analizi | model × beden | beden önerisi: küçük/büyük geldi iade oranları, `kalip_egilimi` (dar/bol/normal) |

**Katkı payı** (`satis_detay.katki_payi`, `urun_ozet.toplam_katki`): elde kalan net satış − komisyon − kargo payı −
iade kargo payı − platform bedeli payı. **Ürün maliyeti düşülmemiştir**; maliyet tablosu eklenince
`katki_payi − adet × birim_maliyet` gerçek kârı verir. Faturası henüz kesilmemiş paketlerde kargo, son 90 günün
ortalamasıyla tahmin edilir (`kargo_tahmini = True`).

Günlük tablolarda takvim özellikleri hazırdır: yil, ay, hafta_gunu, yilin_gunu, ayin_gunu,
hafta_sonu, maas_donemi, ozel_gun (Efsane Kasım, 11.11, Black Friday, bayram öncesi, Anneler Günü ...).
İptal edilen siparişler ciro ve adetlere katılmaz.

## Sahte verinin içerdiği ilişkiler

Sahte veri, gerçek verinin özetlerine göre ayarlandı. Modellerin bulabilmesi için bilinçli olarak şu ilişkiler gömüldü:

- **Mevsimsellik:** şort/tişört yazın, ceket/bot/sweatshirt kışın satar.
- **Takvim:** kampanya günlerinde talep artar (11.11 ve Black Friday ~2 kat); pazartesi yüksek, cuma düşük; gece 22–01 tepe.
- **Fiyat:** ürüne özel kupon dönemlerinde talep, ürünün fiyat esnekliğine (1,2–2,2) göre artar; kategorisine göre pahalı ürün daha az satar.
- **Reklam:** reklam bakiyesi alımı sonraki 7 günde satışları artırır (1.000 TL ≈ +%6, 3.000 TL ≈ +%15).
- **Enflasyon:** ürün fiyatları 3–5 ayda bir %6–15, kargo tarifesi ve platform bedeli kademeli artar.
- **Kalite:** gizli kalite puanı düşük ürün az satar, daha çok iptal/iade edilir ve düşük puan alır.
- **Sorunlu ürün:** defolu ya da yanlış ürün gelen müşteri iade eder (kusurlu/yanlış ürün), 1 puan verir; satıcıya tazmin faturası kesilebilir.
- **Beden ve kalıp:** müşteri bedenini boy-kiloya göre seçer. Kalıbı dar ürünlerde "küçük geldi" iadeleri, "dar geldi" yorumları ve beden soruları artar (bol için tersi). Mağazanın beden cevabı kalıba göre düzeltilmiştir.
- **Birlikte alım:** jean/pantolon/şort + kemer, eşofman altı + tişört/sweatshirt; aynı modelin ikinci rengi.
- **Sadakat:** tekrar alan müşteri daha önce aldığı kategoriden almaya yatkındır.

Sahte veride yurt dışı (mikro ihracat) satış yoktur; `ulke` her zaman Türkiye'dir.

Bu ilişkileri üreten gizli parametreler ve formüller `veri/sahte/dogru_cevaplar/` klasöründedir; modelin bunları
bulup bulamadığını kontrol etmek için [MODEL_DOGRULAMA.md](MODEL_DOGRULAMA.md) rehberine bakın.

## Veride olmayanlar (gerçek sistem için önerilir)

- **Ürün görüntülenme / sepete ekleme / favori sayıları:** API'de yok; satıcı panelinin ürün/satış analizi raporlarından (Excel) alınabilir. Dönüşüm oranı olmadan "talep yok" ile "görünmüyor" ayırt edilemez.
- **Günlük fiyat ve stok geçmişi:** API geçmiş vermez. `cekim/urunler.py` her çalıştırmada o günün kaydını `veri/ham/urun_gecmisi/` altına yazıyor, ancak bu projenin analizleri buna dayanmaz; fiyat ve indirim bilgisi satış satırlarından alınır.
- **Ürün maliyeti:** Trendyol'da yok; `barkod, birim_maliyet` tablosu eklenmeli.
- **Reklam kampanya detayı:** finans verisinde yalnızca bakiye alımı (`Reklam Bedeli`) var; hangi ürüne harcandığı panelin reklam raporlarındadır.
- **Yurt dışı siparişler:** `cekim/siparisler.py` yalnızca Türkiye mağazasını çeker (`storeFrontCode: TR`).
