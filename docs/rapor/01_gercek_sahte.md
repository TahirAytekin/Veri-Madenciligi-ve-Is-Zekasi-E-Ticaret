# Gerçek–sahte karşılaştırma (F1-04)

Modeller sahte veriyle eğitilip gerçek verinin son 3 ayında test edilecek. Bu rapor, iade riski ve beden
modellerinin kullanacağı her özelliğin iki veride **benzer dağılıp dağılmadığını** ve **iade ile ilişkisinin
aynı yönde olup olmadığını** gösterir. Üretim: `python -m modeller.ortak.aktarim` (yalnızca toplulaştırılmış
oranlar içerir).

## Veri

| | sahte (eğitim) | gerçek (test) |
|---|---|---|
| iade oranı | %12,0 | %11,6 |
| satır | 11.676 | 2.636 |
| dönem | 2024-10-17 – 2026-09-24 | 2026-07-16 – 2026-10-01 |

## Eğitimsiz referans (baseline) AUC

Mağazanın kendi geçmişinden hesaplanan oranların iadeyi ne kadar ayırt ettiği.
Modellerin geçmesi gereken çıta.

| skor | sahte | gerçek |
|---|---|---|
| baseline_kategori_gecmisi | 0,637 | 0,664 |
| baseline_model_gecmisi | 0,640 | 0,680 |

## Özellik karşılaştırması

- **Dağılım farkı:** sayısal özelliklerde PSI (<0,10 düşük, 0,10–0,25 orta, >0,25 yüksek),
  kategoriklerde TVD (<0,10 düşük, 0,10–0,30 orta, >0,30 yüksek).
- **İlişki benzerliği:** özellik dilimlerindeki iade oranlarının iki veri arasındaki Spearman
  korelasyonu (her iki veride de en az 30 satırı olan dilimler). 1'e yakın: sahtedeki ilişki
  gerçekte de var.

| özellik | tür | ölçü | dağılım farkı | ilişki benzerliği | dilim | değerlendirme |
|---|---|---|---|---|---|---|
| `kuponlu` | sayısal | PSI | 0,202 | — | 2 | uygun (dağılım farkı orta, ilişki ölçülemedi) |
| `musteri_onceki_iade_orani` | sayısal | PSI | 0,134 | — | 2 | uygun (dağılım farkı orta, ilişki ölçülemedi) |
| `kategori` | kategorik | TVD | 0,182 | 0,67 | 12 | uygun (dağılım farkı orta, ilişki aynı yön) |
| `beden_tipi` | kategorik | TVD | 0,157 | 1,00 | 3 | uygun (dağılım farkı orta, ilişki aynı yön) |
| `musteri_onceki_siparis` | sayısal | PSI | 0,057 | — | 1 | uygun (dağılım farkı düşük, ilişki ölçülemedi) |
| `hizli_teslimat` | kategorik | TVD | 0,020 | — | 2 | uygun (dağılım farkı düşük, ilişki ölçülemedi) |
| `adet` | sayısal | PSI | 0,001 | — | 1 | uygun (dağılım farkı düşük, ilişki ölçülemedi) |
| `dogu_ili` | sayısal | PSI | 0,001 | — | 2 | uygun (dağılım farkı düşük, ilişki ölçülemedi) |
| `sepet_satir_sayisi` | sayısal | PSI | 0,000 | — | 2 | uygun (dağılım farkı düşük, ilişki ölçülemedi) |
| `is_birimi` | kategorik | TVD | 0,043 | 1,00 | 4 | uygun (dağılım farkı düşük, ilişki aynı yön) |
| `kargo_firmasi` | kategorik | TVD | 0,005 | 0,50 | 3 | uygun (dağılım farkı düşük, ilişki aynı yön) |
| `hafta_gunu` | sayısal | PSI | 0,002 | 0,60 | 6 | uygun (dağılım farkı düşük, ilişki aynı yön) |
| `ay` | sayısal | PSI | 5,086 | -0,50 | 3 | riskli (dağılım farkı yüksek, ilişki ters yön) |
| `indirim_orani` | sayısal | PSI | 0,411 | -0,09 | 10 | riskli (dağılım farkı yüksek, ilişki ters yön) |
| `saat` | sayısal | PSI | 0,124 | -0,58 | 10 | riskli (dağılım farkı orta, ilişki ters yön) |
| `model_onceki_puan` | sayısal | PSI | 0,116 | -0,48 | 8 | riskli (dağılım farkı orta, ilişki ters yön) |
| `model_onceki_satis_log` | sayısal | PSI | 1,542 | 0,78 | 10 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `kategori_onceki_iade_orani` | sayısal | PSI | 1,529 | 0,90 | 8 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `model_onceki_kucuk_orani` | sayısal | PSI | 0,516 | 0,96 | 7 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `fiyat_endeksi` | sayısal | PSI | 0,509 | 0,68 | 7 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `model_onceki_iade_orani` | sayısal | PSI | 0,393 | 0,98 | 10 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `beden_konum` | sayısal | PSI | 0,341 | 0,71 | 7 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `beden_sinirda` | sayısal | PSI | 0,327 | 1,00 | 3 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `model_onceki_buyuk_orani` | sayısal | PSI | 0,319 | 0,83 | 6 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `sepet_tutari_endeksi` | sayısal | PSI | 0,279 | 0,71 | 10 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `model_onceki_yorum_log` | sayısal | PSI | 0,251 | 0,71 | 7 | dikkat (dağılım farkı yüksek, ilişki aynı yön) |
| `renk_grubu` | kategorik | TVD | 0,261 | 0,32 | 7 | dikkat (dağılım farkı orta, ilişki zayıf) |
| `il_grubu` | kategorik | TVD | 0,012 | 0,21 | 11 | dikkat (dağılım farkı düşük, ilişki zayıf) |

## Beden konumu ve beden kaynaklı iade

Beden modelinin temel varsayımı: küçük bedenlerde 'küçük geldi', büyük bedenlerde 'büyük geldi'
daha sık.

| beden konumu | veri | satır | küçük geldi | büyük geldi |
|---|---|---|---|---|
| en küçük | gerçek | 340 | %2,4 | %5,9 |
| en küçük | sahte | 1767 | %2,8 | %5,9 |
| küçük | gerçek | 749 | %5,2 | %2,4 |
| küçük | sahte | 1802 | %3,3 | %3,1 |
| orta | gerçek | 570 | %5,6 | %2,6 |
| orta | sahte | 1624 | %2,7 | %3,2 |
| büyük | gerçek | 449 | %9,6 | %1,8 |
| büyük | sahte | 1957 | %4,5 | %3,5 |
| en büyük | gerçek | 106 | %18,9 | %2,8 |
| en büyük | sahte | 2388 | %13,1 | %2,7 |

## Sonuç

<!-- SONUC -->
**1. Kullanılmayacak özellikler (ilişki gerçekte ters yönde):** `ay`, `saat`, `indirim_orani`, `model_onceki_puan`.
Sahte veri 2 yılı kapsarken gerçek test yalnızca Temmuz–Ekim'i kapsıyor; sahte üretici saat ve indirimi iadeyle
ilişkilendirmedi; yorum sayısı az olduğu için puan geçmişi gürültülü. Bu özellikler `ozellikler.AKTARILAMAZ`
listesinde ve modellerin varsayılan özellik setinden (`MODEL_SAYISAL`, `MODEL_KATEGORIK`) çıkarıldı.

**2. Ölçeği farklı ama ilişkisi güçlü:** ürün ve kategori geçmişi oranları (`model_onceki_iade_orani`,
`kategori_onceki_iade_orani`, `model_onceki_kucuk_orani` ...) iki veride de iadeyle aynı yönde ve güçlü ilişkili
(benzerlik 0,78–0,98), ama dağılımları farklı: gerçek mağazanın finans geçmişi daha uzun ve iade oranları biraz daha
düşük. Ağaç modeller sahtedeki mutlak eşikleri öğrenebileceği için F2-02'de göreli sürümleri (ürün oranı / kategori
oranı) denenmeli.

**3. Beden konumu ilişkisi iki veride aynı:** en büyük bedeni alanlar en sık "küçük geldi" (sahte %13,1, gerçek %18,9),
en küçük bedeni alanlar en sık "büyük geldi" (ikisinde de %5,9) diyor. Beden dağılımı farklı (gerçekte S/M, sahtede
L/XL ağırlıklı) ama ilişki aynı; beden modeli (F2-04) için aktarım beklentisi iyi.

**4. Zayıf ilişki:** `renk_grubu` ve `il_grubu` sahtede iadeyi etkilemiyor (üretici böyle kurguladı); modelde kalabilir
ama bu özelliklerden gerçek veride katkı beklenmemeli.

**5. Çıta:** eğitimsiz referanslar gerçek veride AUC 0,664 (kategori geçmişi) ve 0,680 (model geçmişi). Sahtede eğitilen
bir modelin değer katması için gerçek veride bunları geçmesi gerekir.
