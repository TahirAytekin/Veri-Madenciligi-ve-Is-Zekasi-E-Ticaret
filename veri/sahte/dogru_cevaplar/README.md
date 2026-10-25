# Sahte verinin doğru cevapları

Bu klasör, sahte veriyi üreten **gizli parametreleri** içerir. Modellere **özellik olarak verilmez**;
yalnızca bir modelin veriden doğru şeyi öğrenip öğrenmediğini kontrol etmek için kullanılır.
Gerçek veride bu bilgiler yoktur. Ayrıntı: `docs/MODEL_DOGRULAMA.md`.

| dosya | anahtar | içerik |
|---|---|---|
| modeller.csv | model_kodu | `kalip` (-1 dar / 0 normal / +1 bol), `kalite` (0-1), `populerlik`, `fiyat_esnekligi`, `fiyat_endeksi`, mevsim, lansman ve arşiv tarihi |
| icerikler.csv | icerik_id | `renk_talep_payi`: rengin model içindeki talep payı |
| musteriler.csv | musteri_id | müşterinin gerçek boy, kilo ve ayak numarası |
| satirlar.csv | satir_id | `beden_uyumu` (<0 dar geldi, 0 tam, >0 bol geldi), `sorunlu_urun` (defolu/yanlış ürün), `iade_olasiligi` (teslim edilen birimin gerçek iade talebi olasılığı; kâhin skoru) |
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

> **Sahte veri v2 (F1-06):** iade yapısı test öncesi gerçek veriye (23.10.2025–15.07.2026) kalibre edildi.
> Parametreler `hazirlama/sahte_veri_uret.py` başındaki sabitlerde; ayrıntı `docs/rapor/sahte_v2_kalibrasyon.md`.
> Eski üretici: `python hazirlama/sahte_veri_uret.py --v1` (aynı tohumla v1 verisini birebir üretir).

**Beden seçimi:** müşterinin boy-kilosundan ideal beden bulunur; %62 ideali, %18 bir büyüğü, %20 bir küçüğü alır
(v1: %75 / %15 / %10). `beden_uyumu = kes(seçilen − ideal, −1, +1) + kalip`: bedeni setin dışında kalan müşteri en
fazla bir beden uyumsuz alır (v1'de kesilmiyordu; uç bedenlerde yapay iade sıçraması oluşuyordu). Kalıp olasılıkları:
dar %25, normal %70, bol %5.

**İade olasılığı** (teslim edilen birim başına):

```
ham  = [0,04 + 0,08 × (1 − kalite) + 0,60 × max(−beden_uyumu, 0) + 0,60 × max(beden_uyumu, 0)] × ürün_eğilimi
       sorunlu_urun ise 0,40 × ürün_eğilimi
ürün_eğilimi ~ lognormal(0; 0,85), ürün başına sabit
ham, her kategoride ortalaması o kategorinin gerçek iade oranıyla orantılı olacak şekilde ölçeklenir
olasılık = kes(ham × ölçek, 0, 0,9)   (ölçek: genel talep oranı %11,7)
```

`satirlar.csv` → `iade_olasiligi` bu son değerdir. Sorunlu ürün olasılığı `0,025 × (1,6 − kalite)`.

Neden: sorunlu → kusurlu / yanlış / eksik ürün; uyumsuz bedende iade ağırlığı 6 ile "küçük / büyük geldi"
(v1: 3); diğer → "beğenmedim" (kalite düştükçe artar), "yanlış sipariş", "vazgeçtim".

**Yorum puanı:** `kalite + gürültü − 0,12 × |beden_uyumu| − (geç teslimde 0,1)`; sorunlu üründe 1-2 puan.
