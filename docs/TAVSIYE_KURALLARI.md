# Tavsiye kuralları (F3-01…03)

Tavsiye motoru, analizleri ve model çıktılarını satıcı için **somut aksiyona** çevirir. Her tavsiye şunları taşır:
- ne görüldü (sayılarla),
- ne yapılmalı,
- ayda kaç TL kazandırır ve bu nasıl hesaplandı,
- ne kadar güvenilir.

**Kod:**
- `tavsiye/sema.py`: tavsiye yapısı.
- `tavsiye/kurallar.py`: kurallar, eşikler (`ESIK`) ve varsayımlar (`VARSAYIM`).
- `tavsiye/motor.py`: önceliklendirme ve plan.

```bash
python -m tavsiye.motor --veri sahte     # → ciktilar/sahte/tavsiyeler.json, aksiyon_plani.json
```

Model çıktısına dayanan kurallar (kalıp, stok, şikâyet) için önce ilgili model çalıştırılmış olmalı. Çıktı yoksa o kural boş döner.

## Beklenen etki nasıl hesaplanır?
**Birim:** aylık katkı payı farkı (TL), ürün maliyeti hariç. Formül, senaryo simülatörüyle (`analiz/senaryo.py`) aynı birim modeli:

```
birim katkı      u = (1 − r) × P × (1 − k) − c − r × ik
önlenen bir iade = P × (1 − k) + ik
```

| sembol | anlam |
|---|---|
| P | birim net fiyat |
| r | iade oranı |
| k | komisyon oranı |
| c | birim kargo + platform bedeli |
| ik | iade başına kargo |

Ürün değerleri son 90 günden alınır. Fiyat değişikliklerinde satış adedi (1 + fiyat değişimi)^(−esneklik) katına çıkar.

**Varsayımlar** (her tavsiyede gösterilir; `VARSAYIM`):

| varsayım | değer | nerede |
|---|---|---|
| kalıp notu, o ürünün beden iadelerini azaltır | %30 | kalıp uyarısı |
| beden önerici, mağazanın beden iadelerini azaltır | %20 | beden önerici |
| iyileştirmeyle mağaza ortalamasına farkın kapanan kısmı | %50 | yüksek iade riski |
| fiyat esnekliği | 1,5 | indirim, kampanya |
| tedarik süresi / stok hedefi | 3 / 6 hafta | stok tükenme |
| kampanya kuponu | %10 | kampanya fırsatı |

## Güven
Güven, tavsiyenin dayandığı bilginin **gerçek veride ne kadar doğrulandığına** bağlıdır ([02_dogrulama.md](rapor/02_dogrulama.md)):
- **yüksek:** mağazanın gözlenen verisi (zarar, cevap süresi) veya gerçekte en güçlü gösterge (ürün geçmiş iade oranı).
- **orta:** gerçekte doğrulanmış model ama varsayımlı etki (beden önerici), sınırdaki model (kalıp skoru), satış hızı tahmini (stok).
- **düşük:** ölçülmemiş varsayıma dayanan etki (fiyat esnekliği), kısa müşteri geçmişi.

Güven puanı: yüksek 0,9 · orta 0,6 · düşük 0,3.

## Kurallar
| kural | ne zaman | aksiyon | etki (TL/ay) | güven |
|---|---|---|---|---|
| `stok_tukenme` | stok < 3 hafta, satış ≥ 1/hafta (F2-05 stok tablosu) | X adet sipariş (tedarik + 6 hafta) | 4 haftada kaçacak adet × birim katkı | orta |
| `kalip_uyarisi` | F2-04 kalıp etiketi dar/bol (≥5 beden iadesi) | "bir beden büyük/küçük alın" notu + beden tablosu | aylık beden iadesi × %30 × önlenen iade değeri | orta |
| `beden_onerici` | beden kaynaklı iade payı ≥ %40 | beden önericiyi açıklamalara ve cevaplara ekle | senaryo: beden iadeleri %20 azalırsa | orta (model ✓, etki varsayım) |
| `yuksek_iade_riski` | ürün iade oranı ≥ mağazanın 1,5 katı (≥30 teslim) | beden ağırlıklıysa beden tablosu, değilse açıklama/fotoğraf/kalite | farkın %50'si kapanırsa | yüksek |
| `zarar_eden_urun` | 90 günlük katkı payı < 0 (≥10 adet) | fiyatı başa baş kadar artır / indirimden çıkar / kaldır | zararın durması | yüksek |
| `iade_artisi` | son 30 gün iade oranı ≥ önceki 60 günün 1,5 katı ve +5 puan (≥30 teslim) | son partiyi kontrol et | oran önceki düzeye dönerse | orta |
| `sikayetli_urun` | ≥3 yorum ve şikâyetli yorum ≥ %50 veya puan < 3,5 (F2-06) | en sık şikâyet konusuna göre aksiyon | ölçülmedi | orta |
| `marji_yiyen_indirim` | indirim ≥ %20 ve katkı marjı < %10 (≥10 adet) | indirimi yarıya indir | esneklik 1,5 ile | düşük |
| `kampanya_firsati` | marj ≥ %30, indirim < %5, stok ≥ 8 hafta, şikâyetsiz | %10 kupon | esneklik 1,5 ile (yalnızca pozitifse) | düşük |
| `geciken_cevap` | son 30 gün medyan cevap > 6 saat veya cevapsız > %10 | günde iki kez cevap; cevap önerici | ölçülmedi | yüksek |
| `kargo_desisi` | 1 desi küçültme ≥ 1.000 TL/ay | daha küçük paket | senaryo: desi −1 | orta |
| `capraz_satis` | ≥5 ortak sepet ve lift ≥ 2 (en fazla 3 çift) | "birlikte al" kombini / çapraz kupon | ölçülmedi | orta |
| `sezon_hazirligi` | geçen yıl önümüzdeki 6 hafta ≥ yıllık ortalamanın 1,3 katı (≥20 adet) | stok ve yeni ürün hazırla | ölçülmedi | orta |
| `kayip_musteri` | ≥2 sipariş vermiş müşterilerden ≥10'u 45 gündür gelmedi | takipçiye özel kupon | ölçülmedi | düşük |

## Haftalık aksiyon planı
- **Ölçülebilenler:** öncelik = aylık etki × güven puanı. İlk 7 tanesi plana girer.
- **Ölçülemeyenler:** önem, sonra güven sırasıyla. İlk 3 tanesi plana girer.
- **Toplam kazanç üst sınırdır:** bazı etkiler örtüşür; örneğin kalıp notu ve beden önerici aynı beden iadelerini azaltır.

## Yeni kural eklemek
1. `tavsiye/kurallar.py` içine `def kural(b): -> list[Tavsiye]` yaz ve `KURALLAR` listesine ekle.
2. Eşikleri `ESIK`'e, varsayımları `VARSAYIM`'a koy. Sayıyı koda gömme.
3. `tests/test_tavsiye.py` sahte veride hatasız çalıştığını ve alanların dolu olduğunu kontrol eder.
4. Bu tabloya bir satır ekle.
