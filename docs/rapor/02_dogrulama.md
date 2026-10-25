# Model doğrulama raporu (F2-12)

> Bu dosya `python -m modeller.dogrulama_raporu` ile üretilir; elle değiştirmeyin. Yalnızca "Yorum" bölümü elle yazılır ve yeniden üretimde korunur. Web için tablo: `02_dogrulama.json`.

## Yöntem (tüm modellerde aynı)
- **Eğitim yalnızca sahte veriyle** (sahte v2, [F1-06](sahte_v2_kalibrasyon.md)); gerçek veri yalnızca test. Gerçek test dönemi: 2026-07-16 – 2026-10-01 siparişleri (talep ve duygu için kendi pencereleri, bkz. kartlar).
- **Önceden kayıt:** her modelin tasarımı ve başarı ölçütü eğitimden önce commitlendi; sonradan değiştirilmedi. Gerçek sonuç görüldükten sonra yapılan denemeler kartlarda "keşifsel" etiketli.
- **Referans:** her model, eğitim gerektirmeyen en güçlü basit yöntemle karşılaştırılır. **Başarı:** farkın %95 bootstrap güven aralığı 0'ın doğru tarafında. 3 sahte tohumlu modellerde en az 2 tohumda.
- **Seviye 1:** sahte veride gizli doğru cevapla (kâhin) karşılaştırma.

## Sonuç tablosu (gerçek test)

| görev | soru | ölçüt | model | referans | fark [%95 GA] | tohumlarda | karar | web'de |
|---|---|---|---|---|---|---|---|---|
| [F2-02](../../docs/modeller/F2-02.md) | Bu sipariş satırı iade edilecek mi? | ROC-AUC | 0,668 | ürün geçmiş iade oranı: 0,680 | -0,012 [-0,026, +0,001] | 0/3 | ✗ | Ürün düzeyinde risk ürün geçmişinden; model yeni (geçmişi az) ürünlerde yedek |
| [F2-03](../../docs/modeller/F2-03.md) | Bu sipariş satırı iade edilecek mi? | ROC-AUC | 0,590 | ürün geçmiş iade oranı: 0,680 | -0,090 [-0,118, -0,059] | — | ✗ | Kullanılmaz (F2-02 daha iyi); karşılaştırma için |
| [F2-04A](../../docs/modeller/F2-04.md) | Beden iadesi küçük mü büyük mü gelecek? (ürün kalıbından) | ROC-AUC | 0,586 | sabit tahmin: 0,500 | +0,086 [-0,001, +0,165] | — | ✗ | Kalıbı dar/bol ürün tavsiyesi, kanıt sayısıyla |
| [F2-04B](../../docs/modeller/F2-04.md) | Beden iadesi küçük mü büyük mü gelecek? (satır düzeyi) | ROC-AUC | 0,546 | kalıp skoru: 0,585 | -0,039 [-0,125, +0,048] | 0/3 | ✗ | Kullanılmaz |
| [F2-04C](../../docs/modeller/F2-04.md) | Boyu ve kilosu bilinen müşteriye hangi beden? | tam isabet | 0,419 | en sık beden: 0,284 | +0,135 [+0,013, +0,257] | 3/3 | ✓ | Beden önerici (müşteri boy-kilo girer) |
| [F2-05](../../docs/modeller/F2-05.md) | Bu ürün gelecek hafta kaç adet satar? | WAPE | 0,651 | geçen haftanın satışı: 0,469 | +0,183 [+0,007, +0,299] | 0/3 | ✗ | Kullanılmaz; stok tükenme tablosu geçen haftanın satış hızıyla |
| [F2-06](../../docs/modeller/F2-06.md) | Bu yorum olumlu mu olumsuz mu? | ROC-AUC | 0,910 | kelime listesi: 0,833 | +0,020 [-0,036, +0,076] | — | ✗ | Şikâyet işareti ve şikâyet konusu (genel duygu puandan) |
| [F3-04](../../docs/modeller/F3-04.md) | Boyunu ve kilosunu yazan müşteriye satıcı hangi bedeni önerir? | tam isabet | 0,498 | en sık beden (L): 0,191 | +0,306 [+0,226, +0,383] | 3/3 | ✓ | Soru cevap önerici (taslak; beden kodla belirlenir) |

**Başarılı:** F2-04C, F3-04 · **Başarısız:** F2-02, F2-03, F2-04A, F2-04B, F2-05, F2-06

WAPE'de düşük değer iyidir (fark < 0 model lehine); diğer ölçütlerde yüksek değer iyidir.

## Seviye 1 (sahte veri, gizli doğru cevap)

| görev | model | referans | kâhin (tavan / taban) |
|---|---|---|---|
| F2-02 | 0,691 | 0,694 | 0,831 |
| F2-03 | 0,692 | 0,694 | 0,831 |
| F2-04A | 0,987 | — | — |
| F2-04B | 0,819 | 0,768 | — |
| F2-04C | 0,561 | 0,226 | — |
| F2-05 | 0,510 | 0,517 | 0,433 |
| F2-06 | 0,947 | 0,748 | — |
| F3-04 | 0,486 | 0,197 | — |

## Tohumlara göre (sahte v2: 42, 1, 2)

| görev | tohum | model | fark [%95 GA] |
|---|---|---|---|
| F2-02 | 42 | 0,668 | -0,012 [-0,026, +0,001] |
| F2-02 | 1 | 0,683 | +0,002 [-0,013, +0,017] |
| F2-02 | 2 | 0,644 | -0,037 [-0,061, -0,013] |
| F2-04B | 42 | 0,546 | -0,039 [-0,125, +0,048] |
| F2-04B | 1 | 0,627 | +0,041 [-0,030, +0,115] |
| F2-04B | 2 | 0,551 | -0,034 [-0,124, +0,055] |
| F2-04C | 42 | 0,419 | +0,135 [+0,013, +0,257] |
| F2-04C | 1 | 0,500 | +0,216 [+0,095, +0,338] |
| F2-04C | 2 | 0,486 | +0,378 [+0,243, +0,500] |
| F2-05 | 42 | 0,651 | +0,183 [+0,007, +0,299] |
| F2-05 | 1 | 0,574 | +0,105 [+0,014, +0,173] |
| F2-05 | 2 | 0,559 | +0,090 [+0,003, +0,244] |
| F3-04 | 42 | 0,498 | +0,306 [+0,226, +0,383] |
| F3-04 | 1 | 0,489 | +0,298 [+0,217, +0,379] |
| F3-04 | 2 | 0,451 | +0,260 [+0,179, +0,340] |

## Sahte veri v1 → v2 (F2-02, gerçek AUC)

| sürüm | tohum | seçilen | gerçek AUC | − ürün geçmişi [%95 GA] |
|---|---|---|---|---|
| v1 | 42 | gbm_monoton_goreli | 0,671 | -0,010 [-0,035, +0,017] |
| v1 | 1 | gbm_monoton_goreli | 0,568 | -0,113 [-0,146, -0,079] |
| v1 | 2 | gbm_monoton_goreli | 0,638 | -0,042 [-0,064, -0,018] |
| v2 | 42 | gbm | 0,668 | -0,012 [-0,026, +0,001] |
| v2 | 1 | gbm_monoton | 0,683 | +0,002 [-0,013, +0,017] |
| v2 | 2 | gbm_monoton_goreli | 0,644 | -0,037 [-0,061, -0,013] |

## Notlar

- **F2-02:** seçilen varyant: gbm
- **F2-03:** seçilen varyant: mlp; F2-02'ye göre fark -0.078 [-0.106, -0.048]
- **F2-04A:** Seviye 1: gizli dar kalıbı ayırt etme AUC'si
- **F2-04C:** ±1 beden isabeti 0.743; 74 gerçek yorum
- **F2-05:** mağaza toplamı WAPE: model 0.270, naif 0.140
- **F2-06:** 221 gerçek yorum (52 olumsuz); ürün yorumlarında BERT 0.924, sözlük 0.822
- **F3-04:** 235 gerçek satıcı cevabı; ±1 beden isabeti 0.957. LLM taslak kontrolü (B): önerilen bedeni yazma oranı 0.882 (ölçüt ≥ 0,90, tutmadı); sonradan eklenen güvenlik kontrolü yanlış bedenli taslağı şablona çevirir.

## Yorum

<!-- YORUM -->
**Yazan:** Tahir · 2026-10-26

### 1. Ne taşındı, ne taşınmadı?
Sahteden gerçeğe ancak sahte veri o konuda gerçeğe benziyorsa aktarım oluyor.

| ilişki | sahte gerçeğe benziyor mu? | sonuç |
|---|---|---|
| vücut ölçüsü → beden (F2-04C, F3-04) | evet: üreticinin boy-kilo kuralı gerçekçi | **taşındı**: aldığı bedende en sık bedenden 14–38 puan, satıcının önerisinde 26–31 puan iyi (±1 beden %94–96) |
| ürünün geçmiş iade oranı → iade (F2-02) | evet (v2 kalibrasyonundan sonra) | taşındı, ama ürün geçmişinin kendisini geçmedi |
| kategori ve beden konumu → iade (F2-02 v1) | hayır: kurgusal | taşınmadı; v2'de düzeltildi |
| haftalık talep dinamiği (F2-05) | hayır: sahte talep ortalamaya dönüyor, gerçek talep kalıcı sıçrıyor | **taşınmadı**: model naiften kötü |
| dil → duygu (F2-06) | sahte veri kullanılmadı; hazır BERT | çok iyi sıralıyor (0,91), sözlükten anlamlı farkı yok |

### 2. Gerçek veride güçlü sinyaller var, ama basit
- **Ürünün geçmiş iade oranı** (AUC 0,680), **geçen haftanın satışı** (WAPE 0,469) ve **elle yazılmış bir kelime listesi** (AUC 0,833) güçlü referanslar.
- Sahteyle eğitilen modeller bu referanslara yaklaşıyor ama geçemiyor. İki farklı model ailesi (GBM, MLP) iade riskinde aynı tavana çarptı.
- Yalnızca sahte veriyle eğitim kuralı altında, bu verinin satır düzeyinde taşınabilir sinyali büyük ölçüde ürünün kendi geçmişinde.

### 3. Yöntem dersleri
1. **Önceden kayıt işe yaradı.** Gerçek sonuçlara bakıp model değiştirmek kolaydı. F2-03'te geniş-derin varyant, F2-05'te ofset modeli, F2-06'da eşik ayarı gerçekte daha iyi görünüyordu. Hepsi keşifsel kaldı. Böylece raporlanan başarılar seçim yanlılığı taşımıyor.
2. **Tek tohum güvenilmez.** F2-02'nin v1 sonucu (0,671) şanslıydı; başka tohumlarla 0,568–0,639. Sonraki tüm modeller 3 tohumla raporlandı.
3. **Sahte doğrulama aktarılabilirliği ölçemiyor.** Sahtede en iyi görünen esnek modeller gerçekte çöktü: kısıtsız GBM v1'de 0,58, MLP v2'de 0,59. Kısıtlı ve basit yapılar daha sağlam (K-14).
4. **Kâhin (gizli doğru cevap) tavanı gösteriyor.**
   - Talepte kâhin bile WAPE 0,40–0,44: haftalık ürün satışının yarısı gürültü.
   - İade riskinde kâhin 0,83: model ile tavan arasındaki fark, gözlenemeyen müşteri–beden uyumundan geliyor.
5. **Kalibrasyon sahte veriyi gerçekçileştirdi.** Hedeflerin 6/16'sından 15/16'sına çıktı, aktarım kararlılaştı. Ama yalnızca kalibre edilen yapıda (iade) işe yaradı; talep dinamiği kalibre edilmedi.

### 4. Web'de ne kullanılıyor?
| ihtiyaç | kullanılan | neden |
|---|---|---|
| ürün iade riski | ürünün geçmiş iade oranı (F2-02 yedek) | model referansı geçemedi |
| kalıp uyarısı | kalıp skoru + kanıt sayısı (F2-04A) | sınırda ama yönü doğru; kanıtla gösterilir |
| beden önerisi | `beden_oner()` (F2-04C, F3-04) | gerçekte iki ayrı testte doğrulandı: müşterinin aldığı beden (74 yorum) ve satıcının önerdiği beden (235 soru) |
| stok tükenme | geçen haftanın satış hızı (F2-05) | model naiften kötü |
| şikâyet ve konu | BERT şikâyet işareti + konu kuralları (F2-06) | puanın göstermediği şikâyeti buluyor |

### 5. Daha iyi sonuç için (2 haftalık kapsam dışında)
- Gerçek veriyle eğitim. Projenin kuralı gereği yapılmadı; en büyük kazanç burada olurdu.
- Sahte üreticiye talep dinamiği kalibrasyonu (test öncesi pencereyle).
- Zamanla biriken yeni gerçek veriyle daha geniş test pencereleri. Güven aralıkları şu an geniş: 52 olumsuz yorum, 217 beden iadesi.
<!-- /YORUM -->
