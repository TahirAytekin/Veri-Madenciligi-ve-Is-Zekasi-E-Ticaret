# Model Doğrulama Rehberi

**Temel kural:** modeller **sahte veriyle eğitilir**, **gerçek verinin son 3 ayıyla** (16 Temmuz – 23 Ekim 2026)
test edilir. Gerçek veri eğitimde, hiperparametre seçiminde ya da özellik tasarımında **hiç kullanılmaz**.
Yeni veri çekilmez, gelecekteki veri beklenmez.

Her model için iki seviye raporlanır:

| seviye | veri | soru |
|---|---|---|
| 1. Doğru cevap kontrolü | `veri/sahte` + `veri/sahte/dogru_cevaplar/` | Model, sahte veriyi üreten gizli gerçeği bulabiliyor mu? (yöntem doğru mu?) |
| 2. Sahte → gerçek testi | eğitim `veri/sahte`, test `veri/gercek` | Sahtede öğrenilen, gerçek mağazada işe yarıyor mu? Baseline'ı geçiyor mu? |

---

## Seviye 1: Doğru cevap kontrolü (sahte veri)

`veri/sahte/dogru_cevaplar/` sahte veriyi üreten gizli parametreleri içerir. Bunlar şunlardır:
- model kalıbı (dar/normal/bol), kalite, fiyat esnekliği,
- müşterilerin gerçek boy-kilosu,
- her satırın beden uyumu,
- günlük reklam ve kampanya çarpanları.

Formüller klasördeki README'de. Bu dosyalar modele **özellik olarak verilmez**, yalnızca sonucu kontrol eder.

| model | bulması gereken | dosya |
|---|---|---|
| beden uyumu / kalıp | dar-bol modeller, beden kaynaklı iadeler | `modeller.kalip`, `satirlar.beden_uyumu` |
| iade riski | sorunlu ve uyumsuz satırların yüksek risk alması | `satirlar.sorunlu_urun`, `satirlar.beden_uyumu` |
| talep tahmini | kampanya, mevsim ve haftanın günü etkileri | `gunluk_carpanlar` |
| indirim etkisi | ürün bazında esneklik (1,2–2,2) | `modeller.fiyat_esnekligi` |
| beden önerisi | müşterinin ideal bedeni | `musteriler.boy/kilo` |

Örnek: basit kural, model kalıbını ~%77 doğrulukla buluyor. Modelin bunu geçmesi gerekir.

```python
import pandas as pd
dogru = pd.read_csv("veri/sahte/dogru_cevaplar/modeller.csv")
b = pd.read_csv("veri/sahte/analiz/beden_iade_analizi.csv")
m = b.groupby("model_kodu")[["kucuk_geldi", "buyuk_geldi", "satis_adet"]].sum()
m["tahmin"] = pd.cut((m.kucuk_geldi - m.buyuk_geldi) / m.satis_adet, [-1, -0.03, 0.03, 1],
                     labels=["bol", "normal", "dar"]).astype(str)
x = m.join(dogru.set_index("model_kodu").kalip_etiketi).query("satis_adet >= 30")
print((x.tahmin == x.kalip_etiketi).mean())
```

---

## Seviye 2: Sahte → gerçek testi

### Akış
1. **Eğitim:** sahte veri. Hiperparametre seçimi için sahtenin son dönemi doğrulama kümesi olarak ayrılır.
2. **Özellikler:** aynı fonksiyonla (`modeller/ortak/ozellikler.py`) hem sahte hem gerçek veriden üretilir.
3. **Test:** model değiştirilmeden gerçek verinin test penceresine uygulanır.
4. **Rapor:** gerçek veride model ve baseline aynı metrikle karşılaştırılır; sonuç `docs/rapor/02_dogrulama.md` tablosuna yazılır.

### Kural 1: Aktarılabilir özellikler
Sahte ve gerçek verideki ürün, model ve müşteri ID'leri farklıdır. Modelde ID veya ID'den türeyen embedding kullanılmaz.

| kullanılabilir | kullanılamaz |
|---|---|
| kategori, iş birimi, renk grubu | `barkod`, `icerik_id`, `model_kodu`, `musteri_id` |
| beden ve bedenin setteki konumu (küçük → büyük) | ürün adı kelimeleri (sahte adlar uydurma) |
| fiyat, **kategori içi fiyat endeksi**, indirim oranı, indirim türü | mutlak tarih (sahte 2 yıl, gerçek 3 ay) |
| ürünün **o tarihe kadarki** iade oranı, satış hızı, puanı (her veri setinde kendi geçmişinden hesaplanır) | |
| haftanın günü, ay, özel gün, il, kargo firması, hızlı teslimat | |

Ürünün geçmiş iade oranı gibi özellikler her veri setinde **o satırın tarihinden öncesine** bakılarak hesaplanmalı; yoksa sızıntı olur.

### Kural 2: Etiketin "olgunlaşması"
İade teslimden sonra açılır ve birkaç gün içinde kabul edilir: gerçek veride kabul edilen iadelerin %93'ü 15, %99'u **21 gün** içinde kabul ediliyor. Gerçek verinin son günlerinde teslim edilen satırların iadesi henüz gelmemiş olabilir.

| model | gerçek test penceresi |
|---|---|
| iade riski, beden uyumu | 16 Temmuz – 2 Ekim arası **teslim edilmiş** satırlar (son 21 gün hariç; `analiz.metrikler.OLGUNLASMA_GUN`); etiket = `durum == "Accepted"` iade |
| talep tahmini | son 6 hafta (gecikme özellikleri için önceki haftalar yalnızca girdi olarak) |
| duygu analizi | tüm gerçek yorumlar; etiket puandan (1–2 olumsuz, 4–5 olumlu, 3 hariç) |
| konu sınıflandırma | elle etiketlenmiş 100 gerçek soru |
| segmentasyon | tüm gerçek müşteriler (etiket yok: kararlılık ve yorumlanabilirlik) |

### Kural 3: Toplam oranı tutturmak başarı değildir
Sahte veri, gerçek verinin **toplam** dağılımlarına göre ayarlandı: iade oranı, neden dağılımı, kategori payları. Bu yüzden
"modelin tahmin ettiği ortalama iade oranı gerçeğe çok yakın" demek bir başarı göstergesi değildir. Başarı, **sıralama ve hata**
metrikleriyle ölçülür:
- riskli satırı risksizden ayırabiliyor mu? (AUC),
- ürün bazında talebi doğru büyüklükte tahmin ediyor mu? (WAPE).

### Baseline'lar ve metrikler

| model | gerçek veride baseline | metrik |
|---|---|---|
| iade riski | kategorinin ortalama iade oranı | ROC-AUC, PR-AUC, Brier skoru, kalibrasyon eğrisi |
| beden uyumu | herkese "tam" (en sık sınıf) / kategori oranı | sınıf bazında PR-AUC, makro F1 |
| beden önerisi | kullanıcının seçtiği beden | boy-kilo bilgili, memnun yorumlarda doğru beden oranı |
| talep tahmini | son 4 haftanın ortalaması, geçen haftanın aynısı | WAPE, MAE (ürün × hafta ve mağaza toplamı) |
| duygu analizi | olumlu/olumsuz kelime listesi | F1 (olumsuz sınıf), doğruluk |
| konu sınıflandırma | mevcut kural tabanlı `soru_konusu()` | makro F1 |
| derin öğrenme modelleri | aynı problemin klasik modeli (GBM) | aynı metrik |

Derin öğrenme modeli klasik modeli geçemiyorsa bu da raporlanır; küçük tablo verisinde bu sık görülen ve değerli bir bulgudur.

### Önerilen ek karşılaştırma: gerçek-içi referans
Aynı modelin gerçek verinin ilk ~2 ayıyla eğitilip son ayda test edilen sürümü (`ozellik_cikar.py gercek --kesim 2026-09-15`).
Sahte → gerçek sonucuyla yan yana konunca "sahte veriyle eğitmenin bedeli ne kadar?" sorusu cevaplanır. Bu referans
yalnızca karşılaştırma içindir; kullanılan model sahtede eğitilen modeldir.

### Sızıntı kontrol listesi
- Gerçek veriye bakarak özellik veya eşik seçilmedi (yalnızca F1-04 dağılım karşılaştırması sonrası, gerekçesiyle).
- Ürün geçmişi özellikleri satırın tarihinden öncesiyle hesaplandı.
- `analiz/` tablolarının tüm dönemi kapsayan özetleri (ör. `urun_ozet.iade_orani`) özellik olarak kullanılmadı.
- `urunler` tablosundaki stok, fiyat, satışta ve arşivde bilgisi bugünün durumu: özellik yapılmaz; fiyat satış satırlarından alınır.
- `tahmini_teslim_*` ve `odeme_tarihi` planlanmış tarihlerdir, sızıntı değildir.

---

## Kapsam dışı
Yeni veri gelmesini beklemeyi gerektiren yöntemler kullanılmaz: ileriye dönük test (bugün tahmin edip gerçekleşmesini
beklemek) ve satıcıyla A/B deneyi.
