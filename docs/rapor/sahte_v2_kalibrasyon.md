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

### Özet
| | sonuç |
|---|---|
| **A. Kalibrasyon** | v1 16 hedefin 6'sını, **v2 15'ini** tutturuyor (3 tohum ortalaması) |
| **B1. F2-02 v2 − ürün geçmişi** | −0,012 [−0,026, +0,001] → **başarısız** |
| **B2. F2-02 v2 − v1 (eşleştirilmiş, tohum 42)** | −0,002 [−0,029, +0,025] → anlamlı iyileştirme yok |
| **B3. Aktarım açığı** | tohum 42'de 0,020 → 0,022 (küçülmedi); 3 tohum ortalamasında **0,075 → 0,036** (yarıya indi) |
| **B4. Tohum sağlamlığı** | gerçek AUC ortalaması 0,626 → **0,665**; en kötü durum 0,568 → **0,644**. Fark, v1'in tohumlar arası değişiminin (0,103) içinde → "tohum gürültüsü içinde" |
| **B5. F2-03 (MLP) v2** | seçilen varyant gerçekte **0,590**: v1'den (0,669) ve ürün geçmişinden anlamlı biçimde kötü |

**Karar:** Önceden belirlenen birincil ölçüte göre v2, F2-02'yi başarılı hale getirmedi. Buna rağmen ana sahte veri v2 olarak değiştirildi. Gerekçeler:
1. v2 gerçeğe çok daha yakın (15/16 hedef).
2. Sahteden gerçeğe aktarım daha kararlı (en kötü tohum 0,568 → 0,644).
3. Model artık gerçekte de geçerli olan yapıyı öğreniyor: en önemli özellik kategori (%34) değil, ürün geçmişi (%55).

v1, `--v1` seçeneğiyle aynı tohumdan birebir yeniden üretilebiliyor (18 dosya bayt bayt aynı).

### A. Kalibrasyon (test öncesi pencere; sahte = tohum 42, 1, 2 ortalaması)
| hedef | gerçek | v1 | v2 | tolerans | v1 | v2 |
|---|---|---|---|---|---|---|
| K1 iade oranı | 0,082 | 0,113 | 0,078 | ±0,01 | ✗ | ✓ |
| K2 kategori ağırlıklı mutlak fark | — | 0,053 | 0,015 | ≤0,02 | ✗ | ✓ |
| K2 kategori sıralama korelasyonu | — | 0,46 | 0,93 | ≥0,7 | ✗ | ✓ |
| K3 ürünler arası std | 0,056 | 0,061 | 0,044 | ±%25 | ✓ | ✓ |
| K3 yarı dönem korelasyonu | 0,61 | 0,86 | 0,75 | ±0,15 | ✗ | ✓ |
| K4 en küçük beden | 0,099 | 0,133 | 0,078 | ±0,02 | ✗ | ✗ (−0,021) |
| K4 alt yarı | 0,075 | 0,106 | 0,072 | ±0,02 | ✗ | ✓ |
| K4 üst yarı | 0,100 | 0,121 | 0,081 | ±0,02 | ✗ | ✓ |
| K4 en büyük beden | 0,093 | **0,216** | 0,098 | ±0,02 | ✗ | ✓ |
| K5 küçük geldi | 0,425 | 0,422 | 0,432 | ±0,05 | ✓ | ✓ |
| K5 büyük geldi | 0,226 | 0,186 | 0,190 | ±0,05 | ✓ | ✓ |
| K5 diğer | 0,296 | 0,324 | 0,330 | ±0,05 | ✓ | ✓ |
| K5 ürün sorunu | 0,054 | 0,067 | 0,048 | ±0,05 | ✓ | ✓ |
| K6 çoğunlukla küçük | 0,55 | 0,68 | 0,51 | ±0,10 | ✗ | ✓ |
| K6 karışık | 0,35 | 0,16 | 0,40 | ±0,10 | ✗ | ✓ |
| K6 çoğunlukla büyük | 0,10 | 0,16 | 0,09 | ±0,10 | ✓ | ✓ |

**Kategori iade oranları (K2):**

| kategori | gerçek | v1 | v2 |
|---|---|---|---|
| Bluz | 0,057 | 0,140 | 0,052 |
| T-Shirt | 0,065 | 0,123 | 0,058 |
| Spor T-Shirt | 0,070 | 0,114 | 0,055 |
| Body | 0,093 | 0,153 | 0,083 |
| Jeans | 0,104 | 0,172 | 0,096 |
| Eşofman Altı | 0,104 | 0,103 | 0,075 |
| Şort & Bermuda | 0,187 | 0,171 | 0,144 |

**v1'in iki ana kusuru:**
1. **Uç bedenlerde yapay iade sıçraması.** En büyük bedende %21,6; gerçekte %9,3. Sebebi: bedeni setin dışında kalan müşteri en yakın bedeni alıyor ve uyumsuzluk sınırsız büyüyordu. F2-02'de beden konumu bu yüzden ikinci en önemli özellikti.
2. **Gerçekle ilgisiz kategori oranları** (sıralama korelasyonu 0,46). Kategori farkları rastgele kaliteden geliyordu. F2-02'de en önemli özellik kategoriydi ve bu bilgi gerçeğe taşınmıyordu.

**Üreticide yapılan değişiklikler (v1 → v2):**

| parametre | v1 | v2 | hedef |
|---|---|---|---|
| kategori düzeyi | yok | gerçek oranlarla orantılı | K2 |
| beden uyumsuzluğu sınırı | yok | ±1 | K4 |
| beden seçimi (ideal / büyük / küçük) | 75 / 15 / 10 | 62 / 18 / 20 | K5, K6 |
| kalıp (dar / normal / bol) | 20 / 65 / 15 | 25 / 70 / 5 | K6 |
| uyumsuzluk katsayıları (dar / bol) | 0,30 / 0,32 | 0,60 / 0,60 | K5 |
| beden nedeni ağırlığı | 3 | 6 | K5 |
| sorunlu ürün oranı | 0,035 | 0,025 | K5 |
| ürün eğilimi (lognormal std) | yok | 0,85 | K3 |
| genel talep oranı | %16,3 | %11,7 | K1 |

**Önceden kayıttan sapmalar (açıkça):**
- **Üç tohum ortalaması.** Kayıtta sahte istatistiklerin tek veri setinden ölçüleceği varsayılmıştı. K3 ve K6 tek tohumda çok gürültülü çıktı: aynı ayarla K6 farkı −0,10 ile −0,42 arasında oynadı, çünkü pencerede yalnızca 8–15 ürün var. Bu yüzden kalibrasyon 3 tohum ortalamasıyla yapıldı. Yalnızca tohum 42 ile v2, 16 hedefin 12'sini tutturuyor.
- **Ayar turu sayısı.** Ayar 6 turda yapıldı ve 16 hedefin 15'i tutunca durduruldu. Tüm turlar test öncesi pencereyle ölçüldü; gerçek test penceresine bakılmadı.
- **Kâhin değişti.** v2'de iade olasılığı daha karmaşık olduğu için kâhin artık formülden hesaplanmıyor; üreticinin kaydettiği olasılık (`dogru_cevaplar/satirlar.csv` → `iade_olasiligi`) kullanılıyor. Bu değişiklik model kodunu değil, değerlendirme kodunu (`kahin_skoru`) etkiliyor.

**Bilinen fark (kalibre edilmedi):** Gerçek veride iade oranı zamanla güçlü biçimde artıyor: Ekim 2025'te %5, Haziran 2026'da %12, Temmuz'da %17. Sahte veride oran zamanla düz. Bu eğilim hedef listesinde yoktu. Sonuçları:
- v2 modelleri gerçek test penceresinde iadeyi düşük tahmin ediyor (ortalama %9,1; gerçekleşen %11,7).
- Gerçek test satırlarının %21,7'sinde kategori geçmiş oranı, sahte eğitim verisinin %1–%99 aralığının dışında.

### B. Model sonuçları (gerçek test penceresi, kod değişmeden)

**F2-02, 3 tohum:**

| sürüm | tohum | seçilen varyant | sahte doğrulama AUC | gerçek AUC | aktarım açığı | − ürün geçmişi [%95 GA] | ürün içi AUC |
|---|---|---|---|---|---|---|---|
| v1 | 42 | gbm_monoton_goreli | 0,691 | 0,671 | 0,020 | −0,010 [−0,035, +0,017] | 0,534 |
| v1 | 1 | gbm_monoton_goreli | 0,681 | **0,568** | 0,113 | −0,113 [−0,146, −0,080] | 0,449 |
| v1 | 2 | gbm_monoton_goreli | 0,731 | 0,639 | 0,092 | −0,042 [−0,064, −0,018] | 0,489 |
| v2 | 42 | gbm | 0,691 | 0,668 | 0,022 | −0,012 [−0,026, +0,001] | 0,454 |
| v2 | 1 | gbm_monoton | 0,710 | **0,683** | 0,028 | +0,002 [−0,013, +0,017] | 0,548 |
| v2 | 2 | gbm_monoton_goreli | 0,701 | 0,644 | 0,057 | −0,037 [−0,061, −0,013] | 0,461 |
| **v1 ortalama** | | | 0,701 | **0,626** | 0,075 | −0,055 | 0,491 |
| **v2 ortalama** | | | 0,701 | **0,665** | 0,036 | −0,015 | 0,488 |

Ürün geçmişi gerçek AUC: 0,680.

**F2-02 v2, tohum 42 (resmi çalıştırma, `python -m modeller.iade_riski`):**

| varyant | sahte doğrulama AUC | gerçek AUC |
|---|---|---|
| gbm (kısıtsız) | 0,691 | 0,665 (v1'de 0,580) |
| gbm_monoton | 0,686 | 0,675 |
| gbm_monoton_goreli | 0,688 | 0,678 |

- Seviye 1 (sahte doğrulama): model 0,691, ürün geçmişi 0,694, kategori geçmişi 0,587, kâhin 0,831.
- Özellik önemi: ürün geçmişi 0,55 · küçük geldi oranı 0,10 · kategori geçmişi 0,06 · kategori 0,06 · büyük geldi oranı 0,06 · beden konumu 0,03 (v1'de 0,14).

**F2-03 (MLP) v2, tohum 42:**

| varyant | sahte doğrulama AUC | gerçek AUC |
|---|---|---|
| mlp (seçilen) | 0,692 | 0,607 |
| mlp_genis_derin | 0,663 | 0,684 |

- Son model gerçekte 0,590: ürün geçmişine göre −0,090 [−0,118, −0,059], F2-02'ye göre −0,078 [−0,106, −0,048].

### Ne öğrendik
1. **F2-02'nin v1 sonucu (0,671) şanslı bir tohumdu.** Aynı v1 üreticisi başka tohumlarla gerçekte 0,568 ve 0,639 verdi. Tek tohumla yapılan sahte → gerçek değerlendirmesi güvenilir değil. Sonraki modellerde en az 3 tohum raporlanmalı.
2. **Kalibrasyon, sahteye özgü sahte sinyalleri temizledi.** v1'de kısıtsız GBM gerçekte çöküyordu (0,580), v2'de çökmüyor (0,665). Model kategori ve beden konumu yerine ürün geçmişine dayanıyor.
3. **Tavan değişmedi.** v2 ile de gerçekte ürün geçmişini (0,680) geçen kararlı bir model yok. v2 sahtede bile model ile ürün geçmişi başa baş (0,691 / 0,694). Bu veride satır düzeyinde aktarılabilir sinyal, büyük ölçüde ürünün geçmişinde.
4. **Beden konumu iadeyi öngörmüyor.** Gerçekte beden dilimlerinin iade oranları düz (%7,5–10). Ürün içi AUC v1 ve v2'de ~0,49. F2-02 kartındaki "model beden düzeyinde eğilim verir" önerisi v1'in yapay sıçramasına dayanıyordu ve geri çekildi. F2-04 için önemli: beden riski, beden konumundan değil, ürünün "küçük/büyük geldi" geçmişinden (kalıp) gelmeli.
5. **Kısıtsız MLP dağılım kaymasına dayanıksız.** v2'de gerçek test, sahte eğitimin aralığı dışına daha çok taşıyor (zaman eğilimi). Kısıtsız MLP burada çöktü, monoton geniş-derin varyant ve GBM çökmedi. Bu, K-14 önerisini (yapısal kısıtlı aday zorunlu) destekliyor.

## Nasıl yeniden üretilir
```bash
python hazirlama/sahte_veri_uret.py                     # v2, tohum 42 → veri/sahte/
python hazirlama/sahte_veri_uret.py --tohum 1           # v2, tohum 1 → veri/sahte_t1/  (2 için de)
python hazirlama/sahte_veri_uret.py --v1 [--tohum 1]    # v1 → veri/sahte_v1[_t1]/
python -m hazirlama.kalibrasyon --tohumlar              # A: kalibrasyon tablosu
python -m modeller.surum_karsilastirma                  # B: F2-02, v1/v2 × 3 tohum (~50 sn)
python -m modeller.iade_riski && python -m modeller.iade_riski_mlp
```
