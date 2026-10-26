# Sahte veri v3: talep dinamiği ve iade eğilimi kalibrasyonu (geliştirme turu, adım 2)

**Görev:** F1-07 · **Yazan:** Tahir · **Tarih:** 2026-10-26 · **Kod:** `hazirlama/kalibrasyon_talep.py`, `hazirlama/sahte_veri_uret.py`

> **Önceden kayıt.** Bu bölüm, üretici değiştirilmeden ve v3 ile hiçbir model eğitilmeden yazıldı. Kurallar
> sonuçlar görüldükten sonra değiştirilmez; sonradan yapılan her şey "keşifsel" diye etiketlenir.

## Neden
F2-05 (haftalık talep) gerçek veride "geçen haftanın satışı"ndan anlamlı biçimde kötüydü. Model kartında iki tanı
konmuştu: gerçek talep kalıcı sıçramalar yapıyor, sahte talep ise ortalamaya dönüyor; gerçek çok satanlar sahte
ölçeğin dışında kalıyor. F2-02 de gerçek iade oranının zamanla artması yüzünden iadeyi düşük tahmin ediyordu.
Test öncesi pencerede (23.10.2025–15.07.2026) ölçülen değerler bu tanıları doğruluyor (sahte = 3 tohum ortalaması):

| hedef | istatistik | gerçek | sahte v2 | tolerans | v2 |
|---|---|---|---|---|---|
| D1 | WAPE(geçen hafta) / WAPE(son 4 hafta ort.) | 0,90 | 1,20 | ±0,05 | ✗ |
| D2 | haftalık satışın 1 gecikmeli otokorelasyonu (ürün medyanı) | 0,53 | 0,16 | ±0,10 | ✗ |
| D3 | en çok satan %10 ürünün satış payı | 0,67 | 0,44 | ±0,08 | ✗ |
| D3 | ürün-hafta satışı, 99. yüzdelik | 150 | 23 | ±%30 | ✗ |
| D3 | mağaza haftalık satış medyanı | 387 | 150 | ±%25 | ✗ |
| D4 | iade oranı: pencerenin son 3 ayı / ilk 3 ayı | 2,42 | 1,10 | ±%25 | ✗ |
| D5 | mağaza haftalık satışının değişkenlik katsayısı | 0,34 | 0,29 | ±0,10 | ✓ |

## Kurallar
- **Veri:** Gerçek veride yalnızca test öncesi pencere kullanılır (F1-06 ile aynı). Yalnızca toplu sayılar. Sahte istatistikler 3 tohumun ortalamasıdır (42, 1, 2).
- **Üreticide izin verilen değişiklikler (yalnızca bunlar):**
  1. **Ürün talebinin kalıcı bileşeni:** Her ürüne haftalık log-çarpan eklenir. Bu, AR(1) bir süreçtir ve seyrek sıçramalar içerir. Ayrı bir üreteçle çekilir; v2'nin rastgele akışı değişmez.
  2. **Popülerlik dağılımının kuyruğu:** lognormal standart sapma (v2: 0,8).
  3. **Ölçek:** Talep, son 90 güne (test penceresi içinde kalıyordu) göre değil, **test öncesi penceredeki mağaza haftalık satış medyanına** (D3) göre ölçeklenir.
  4. **İade oranının zaman eğilimi:** İade olasılığına zamanla artan bir çarpan eklenir; genel iade oranı (K1) korunur.
- **Ayar turu:** En fazla 6 tur. Durma koşulu: ölçüt A sağlanınca.
- **v2 korunur:** `python hazirlama/sahte_veri_uret.py --v2` v2'yi birebir üretir (testle doğrulanır).

## Başarı ölçütleri
**A. Kalibrasyon** (3 tohum ortalaması):
- D1–D5'in 7 istatistiğinden en az 6'sı tolerans içinde olmalı.
- F1-06'nın K1–K6 hedeflerinden en az 14/16'sı hâlâ tutmalı.

**B. Talep modeli (birincil):**
- F2-05'in kodu ve seçim kuralı değişmeden v3'ün 3 tohumuyla eğitilir.
- Gerçek veride **aynı test haftalarında** test edilir: 07.09–12.10.2026 haftaları; test penceresi bu tarihlere sabitlenir.
- **Başarı:** WAPE(model) − WAPE(en iyi referans) farkının %95 kümeli bootstrap üst sınırı 0'ın altında olmalı; bu, 3 tohumun en az 2'sinde sağlanmalı. Bu, F2-05 ile aynı ölçüt.
- **Ayrıca raporlanır:** v2 → v3 WAPE değişimi, mağaza toplamı WAPE, aktarım açığı.

**C. İade riski (ikincil, raporlanır):**
- F2-02, v3 ile 3 tohumda yeniden eğitilir.
- Raporlanır: gerçek AUC, ürün geçmişine göre fark, ortalama tahmin ile gerçekleşen oran (kalibrasyon).

**Ana sahte verinin değişmesi:**
- v3, **yalnızca A'ya göre** ana sahte veri olur. Model sonuçları (B, C) bu kararda kullanılmaz; gerçek test sonucuna bakarak veri seçmek testi kirletir.
- Dondurulmuş doğrulama raporu (`02_dogrulama.md`) değişmez; v3 sonuçları bu raporda ve model kartlarında ayrı bölüm olarak yer alır.

## Sonuçlar
_(Kalibrasyon ve model sonuçları sonraki commit'te.)_
