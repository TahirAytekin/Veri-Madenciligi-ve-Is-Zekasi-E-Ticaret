# Model Doğrulama Rehberi

Bir modelin tahminlerinin doğru olduğunu üç seviyede kontrol ediyoruz. Her model için üçünü de raporlayın.

| seviye | veri | soru |
|---|---|---|
| 1. Doğru cevap kontrolü | `veri/sahte` + `veri/sahte/dogru_cevaplar/` | Model, veriyi üreten gizli gerçeği bulabiliyor mu? (yöntem doğru mu?) |
| 2. Zaman bazlı test | `veri/gercek` (ve sahte) + `--kesim` | Geçmişle eğitilen model, görmediği dönemi ne kadar iyi tahmin ediyor? |
| 3. İleriye dönük test | her gün gelen yeni gerçek veri | Bugün yapılan tahmin, gerçekleşen gelecekle tutuyor mu? |

## Seviye 1: Doğru cevap kontrolü (yalnızca sahte veri)

`veri/sahte/dogru_cevaplar/` sahte veriyi üreten gizli parametreleri içerir: model kalıbı (dar/normal/bol), kalite,
fiyat esnekliği, müşterilerin gerçek boy-kilosu, her satırın beden uyumu, günlük reklam ve kampanya çarpanları.
Formüller klasördeki README'de. **Bu dosyalar modele özellik olarak verilmez**; yalnızca sonucu kontrol eder.

Örnek: iade nedenlerinden model kalıbını bulmak

```python
import pandas as pd
dogru = pd.read_csv("veri/sahte/dogru_cevaplar/modeller.csv")
b = pd.read_csv("veri/sahte/analiz/beden_iade_analizi.csv")
m = b.groupby("model_kodu")[["kucuk_geldi", "buyuk_geldi", "satis_adet"]].sum()
m["tahmin"] = pd.cut((m.kucuk_geldi - m.buyuk_geldi) / m.satis_adet, [-1, -0.03, 0.03, 1],
                     labels=["bol", "normal", "dar"]).astype(str)
x = m.join(dogru.set_index("model_kodu").kalip_etiketi).query("satis_adet >= 30")
print((x.tahmin == x.kalip_etiketi).mean())   # basit kural: ~%77 -> modeliniz bunu geçmeli
```

| model | bulması gereken | doğru cevap dosyası |
|---|---|---|
| beden önerisi / iade riski | dar-bol modeller, iadenin beden kaynaklı olduğu satırlar | modeller.kalip, satirlar.beden_uyumu |
| fiyat / indirim etkisi | ürün bazında esneklik (1,2–2,2) | modeller.fiyat_esnekligi, fiyat_kupon_degisimleri |
| satış tahmini | kampanya, mevsim ve haftanın günü etkileri | gunluk_carpanlar |
| reklam getirisi | reklam çarpanı (1.000 TL/7 gün ≈ +%6) | gunluk_carpanlar.reklam_carpani |
| ürün skorlama | gizli kalite | modeller.kalite |
| beden önerisi (boy-kilo) | müşterinin ideal bedeni | musteriler.boy/kilo |

Bu seviye **yöntemin** doğru çalıştığını kanıtlar, gerçek dünyayı değil: ilişkileri sahte veriye biz koyduk.

## Seviye 2: Zaman bazlı test (sızıntısız)

Rastgele train/test ayırmayın: satışta ve iadede rastgele ayırma modele geleceği gösterir. Bunun yerine bir
**kesim tarihi** seçin: özellikler kesime kadar bilinenlerden, hedef kesimden sonraki dönemden hesaplanır.

```bash
python hazirlama/ozellik_cikar.py sahte --kesim 2026-06-30   # -> veri/sahte/analiz_kesim_2026-06-30/
```

```python
import sys; sys.path.insert(0, "hazirlama")
import pandas as pd
from ortak import VERI, hepsini_oku, kesim_uygula

KESIM, UFUK = pd.Timestamp("2026-06-30"), 30
tum = hepsini_oku(VERI / "sahte")
gecmis = kesim_uygula(tum, KESIM)          # kesim anında bilinen dünya (özellikler bundan)

# Hedef: kesimden sonraki 30 günde ürün (renk) başına satış adedi
X = pd.read_csv(VERI / "sahte" / "analiz_kesim_2026-06-30" / "urun_ozet.csv")
s = tum["siparisler"]; l = tum["siparis_satirlari"].merge(s[["paket_id", "siparis_tarihi", "iptal"]])
l = l.merge(tum["urunler"][["barkod", "icerik_id"]])
gelecek = l[(l.siparis_tarihi > KESIM + pd.Timedelta(days=1)) &
            (l.siparis_tarihi <= KESIM + pd.Timedelta(days=1 + UFUK)) & ~l.iptal]
y = gelecek.groupby("icerik_id").adet.sum()
veri = X.set_index("icerik_id").join(y.rename("hedef_30g_adet")).fillna({"hedef_30g_adet": 0})
```

**Kayan pencere (backtesting):** Tek bir kesim şanslı olabilir. Birkaç kesimle (ör. her ay sonu) eğitip
ortalama hatayı raporlayın.

**Sızıntı kontrol listesi**
- `analiz/` (kesimsiz) tablolar **tüm dönemi** kapsar; model eğitiminde yalnızca `analiz_kesim_*` kullanın.
- `urunler` tablosundaki stok, fiyat, satışta ve arşivde bilgisi **bugünün** durumudur: özellik yapmayın.
  Fiyatı satış satırlarından, ileride `veri/ham/urun_gecmisi/` kayıtlarından alın.
- `tahmini_teslim_*` ve `odeme_tarihi` kesimden sonrayı gösterebilir; bunlar sipariş/işlem anında bilinen
  **planlanmış** tarihlerdir, sızıntı değildir.
- Aynı müşteri veya sipariş hem eğitimde hem testte olmasın (öneri sistemi, iade modeli): grup bazlı ayırın.
- Yeni ürün performansını ölçmek için bazı ürünleri tamamen teste ayırın (soğuk başlangıç).

**Her model bir baseline'ı geçmeli**

| model | baseline | metrik |
|---|---|---|
| iade riski | ürünün geçmiş iade oranı | AUC, Brier skoru, kalibrasyon eğrisi |
| beden önerisi | herkese kendi bedeni | doğru beden oranı; sahtede kalıp doğruluğu (%77'yi geç) |
| satış tahmini | geçen haftanın aynı günü (mevsimsel naive) | WAPE, MAE |
| indirim etkisi | tek bir sabit esneklik | katsayı ve güven aralığı |
| NLP (duygu/konu) | TF-IDF + lojistik regresyon | sınıf bazında F1 (elle etiketlenmiş 100-200 örnek) |
| öneri sistemi | en çok satanlar | Recall@10, NDCG@10 |
| segmentasyon | — | silhouette, farklı dönemlerde kararlılık, yorumlanabilirlik |

Derin öğrenme modelini her zaman klasik bir modelle (LightGBM vb.) karşılaştırın; geçemiyorsa bunu raporlamak da bir bulgudur.

## Seviye 3: İleriye dönük test

1. Tahminleri tarihli kaydedin (ör. `tahminler/2026-11-01_satis_30g.csv`), sonradan değiştirmeyin.
2. `guncelle.py` gerçekleşen veriyi her gün ekler; ufuk dolunca tahmin ile gerçeği karşılaştırın.
3. Satıcıyla küçük bir deney (A/B): modelin "dar" dediği ürünlerin yarısının açıklamasına "bir beden büyük
   alın" eklenir, yarısına eklenmez. 4-6 hafta sonra iki grubun iade oranı farkı, modelin gerçek iş etkisidir.
