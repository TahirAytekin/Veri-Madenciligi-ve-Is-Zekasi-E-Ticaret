# Sahte veri v2: test öncesi gerçek veriye kalibrasyon (F1-06)

**Görev:** F1-06 · **Yazan:** Tahir · **Tarih:** 2026-10-25 · **Kod:** `hazirlama/kalibrasyon.py`, `hazirlama/sahte_veri_uret.py`

> **Önceden kayıt:** "Neden", "Kurallar", "Hedef istatistikler" ve "Başarı ölçütleri" bölümleri, kalibrasyon
> istatistikleri hesaplanmadan ve sahte üretici değiştirilmeden yazıldı (görev üstlenme commit'i). Sonuçlar ayrı
> commit'lerde eklenir; bu bölümler sonradan değiştirilmez.

## Neden
F2-02 (GBM) ve F2-03 (MLP) gerçek veride aynı tavana çarptı (AUC ~0,67). Bu tavan, mağazanın ürün geçmişinin altında (0,680).
- Sahtede en önemli özellik **kategori** (%34), ama bu bilgi gerçeğe taşınmıyor.
- Sahte üreticide iade olasılığı yalnızca rastgele ürün kalitesi, rastgele kalıp ve beden uyumundan geliyor. Kategoriye özgü bir ayar yok.
- Hipotez: sahte veri ürün, kategori ve beden düzeyinde gerçeğe benzerse, sahtede öğrenilen ilişkiler gerçeğe taşınır.

## Kurallar
1. **Kalibrasyon yalnızca test öncesi gerçek veriyle yapılır:** 23.10.2025 – 15.07.2026, finans kayıtları ve iade talepleri.
   - Test penceresine (16.07.2026 sonrası siparişler) ait hiçbir istatistik kalibrasyonda kullanılmaz.
   - Bu dönem modellerin geçmiş özelliklerinde zaten kullanılıyor; yeni bilgi sızmaz.
2. **Yalnızca toplu istatistikler** (oranlar, dağılımlar) kullanılır. Gerçek ürün kodu, barkod veya satır sahte veriye kopyalanmaz.
3. Kalibre edilen sayılar üreticide sabit olarak yazılır, tıpkı mevcut `HEDEF_IADE_ORANI` gibi. Kaynakları kod yorumunda belirtilir.
4. **Model kodu değişmez.** F2-02 ve F2-03 aynı kodla, aynı seçim kuralıyla v2 veride yeniden çalıştırılır.
5. F1-04'te çıkarılan 4 özellik (`ay`, `saat`, `indirim_orani`, `model_onceki_puan`) çıkarılmış kalır. O karar test penceresine bakılarak alınmıştı ve yeniden açılmaz.
6. Gerçek test sonucu görüldükten sonra yapılan her değişiklik "keşifsel" diye etiketlenir.

## Hedef istatistikler (K1–K6)
Hepsi `hazirlama/kalibrasyon.py` ile, iki veride **aynı kodla** ve aynı tanımla ölçülür. Pencere: gerçekte 23.10.2025–15.07.2026, sahtede aynı takvim aralığı.
- **Satış birimi:** finans `Satış` kaydı.
- **İade birimi:** finans `İade` kaydı (kabul edilen).
- **İade nedenleri:** kabul edilen talepler; "teslim edilemedi" hariç.

| kod | istatistik | üreticideki karşılığı |
|---|---|---|
| K1 | Genel iade oranı (İade / Satış) | ölçek (`HEDEF_IADE_ORANI`) |
| K2 | Kategori iade oranları (≥200 satışlı kategoriler) | yeni: kategori çarpanı |
| K3 | Ürünler arası gerçek iade farkı: ≥100 satışlı ürünlerde iade oranı varyansından binom gürültüsü çıkarılır (std). Ayrıca dönemin iki yarısındaki ürün oranlarının korelasyonu (kalıcılık) | kalite dağılımı ve etkisi |
| K4 | Beden konumuna göre iade oranı (4 dilim: en küçük, alt yarı, üst yarı, en büyük) | beden seçimi ve uyum katsayıları |
| K5 | İade nedeni payları (beden küçük, beden büyük, diğer müşteri nedenleri, ürün sorunu) | neden ağırlıkları, sorunlu ürün oranı |
| K6 | Kalıp: beden iadesi ≥10 olan ürünlerde "küçük geldi" payının dağılımı (çoğunlukla küçük / karışık / çoğunlukla büyük) | kalıp olasılıkları |

## Başarı ölçütleri

### A. Kalibrasyon başarısı (test öncesi pencere, sahte v2 – gerçek)
| hedef | tolerans |
|---|---|
| K1 | ±1 puan |
| K2 | satış ağırlıklı ortalama mutlak fark ≤ 2 puan **ve** sıralama korelasyonu (Spearman) ≥ 0,7 |
| K3 | ürünler arası std gerçeğin ±%25'i içinde; yarı dönem korelasyonu ±0,15 içinde |
| K4 | her dilim ±2 puan |
| K5 | her pay ±5 puan |
| K6 | her grup payı ±10 puan |

Bir hedef toleransı tutmazsa raporlanır. Kalibrasyon yine de kullanılabilir, ama "tam kalibre" denmez.

### B. Model başarısı (gerçek test penceresi, kod değişmeden)
1. **Birincil:** F2-02 (v2) − ürün geçmişi, %95 bootstrap güven aralığının alt sınırı > 0 → **başarılı**.
2. **İkincil:** aynı test satırlarında eşleştirilmiş bootstrap ile AUC(F2-02 v2) − AUC(F2-02 v1). Alt sınır > 0 ise v2 "anlamlı iyileştirme".
3. **Aktarım açığı:** (sahte doğrulama AUC − gerçek test AUC) v1'e göre küçülmeli.
4. **Tohum sağlamlığı:** v1 ve v2, üç tohumla (42, 1, 2) üretilip F2-02 gerçek AUC'si her tohumda raporlanır. Fark tohumlar arası değişimden büyük değilse "tohum gürültüsü içinde" denir.
5. F2-03 (MLP) de v2 ile yeniden çalıştırılır. Aynı ölçütler raporlanır, ama karar F2-02'ye göre verilir.

## Sonuçlar
_(Kalibrasyon ve model sonuçları sonraki commit'lerde eklenecek.)_
