# Sahte verinin doğru cevapları

Bu klasör, sahte veriyi üreten **gizli parametreleri** içerir. Modellere **özellik olarak verilmez**;
yalnızca bir modelin veriden doğru şeyi öğrenip öğrenmediğini kontrol etmek için kullanılır.
Gerçek veride bu bilgiler yoktur. Ayrıntı: `docs/MODEL_DOGRULAMA.md`.

| dosya | anahtar | içerik |
|---|---|---|
| modeller.csv | model_kodu | `kalip` (-1 dar / 0 normal / +1 bol), `kalite` (0-1), `populerlik`, `fiyat_esnekligi`, `fiyat_endeksi`, mevsim, lansman ve arşiv tarihi |
| icerikler.csv | icerik_id | `renk_talep_payi`: rengin model içindeki talep payı |
| musteriler.csv | musteri_id | müşterinin gerçek boy, kilo ve ayak numarası |
| satirlar.csv | satir_id | `beden_uyumu` (<0 dar geldi, 0 tam, >0 bol geldi), `sorunlu_urun` (defolu/yanlış ürün) |
| gunluk_carpanlar.csv | tarih | trend, haftanın günü, özel gün, maaş günü, sepet indirimi, reklam harcaması ve çarpanı, mevsim eğrileri |
| fiyat_kupon_degisimleri.csv | model_kodu, tarih | liste fiyatı değişimleri ve ürüne özel kupon dönemleri |

## Veriyi üreten formüller

**Günlük beklenen satış** (renk/ürün sayfası × gün, sonra Poisson ile adet çekilir):

```
talep ∝ kategori_talebi × populerlik × renk_talep_payi × (0,5 + kalite) × fiyat_endeksi^(-1)
        × mevsim(kategori, gün) × ömür(ürün yaşı)
        × [(1 − kupon_orani) × (1 − sepet_indirimi)]^(−fiyat_esnekligi)
        × trend × haftanın_günü × özel_gün × maaş × reklam_carpani × gürültü
reklam_carpani = 1 + 0,06 × (son 7 gün reklam harcaması / 1000 TL)^0,8
```

**Beden seçimi:** müşterinin boy-kilosundan ideal beden bulunur; %75 ideali, %15 bir büyüğü, %10 bir küçüğü alır.
`beden_uyumu = seçilen − ideal + kalip` (kalıbı dar üründe ideal beden bile "dar" gelir).

**İade olasılığı** (teslim edilen birim başına, ortalaması %16,3'e ölçeklenir):

```
0,04 + 0,08 × (1 − kalite) + 0,30 × max(−beden_uyumu, 0) + 0,32 × max(beden_uyumu, 0)
sorunlu_urun ise 0,40
```

Neden: sorunlu → kusurlu / yanlış / eksik ürün; dar → çoğunlukla "küçük geldi"; bol → "büyük geldi";
diğer → "beğenmedim" (kalite düştükçe artar), "yanlış sipariş", "vazgeçtim".

**Yorum puanı:** `kalite + gürültü − 0,12 × |beden_uyumu| − (geç teslimde 0,1)`; sorunlu üründe 1-2 puan.
