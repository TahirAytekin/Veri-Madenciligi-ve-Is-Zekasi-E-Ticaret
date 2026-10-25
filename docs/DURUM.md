# Durum — Kaldığımız Yer

Projeye dönen ya da yeni katılan herkesin ilk okuyacağı sayfa. **Her devirde ve her PR birleştirmesinde güncellenir.**

**Son güncelleme:** 2026-10-26 · **Güncelleyen:** Tahir
**Takvim:** 14 gün, Gün 1 = 26.10.2026 Pzt, teslim = 08.11.2026 Paz ([plan §4](PROJE_PLANI.md#4-takvim-14-gün))
**Bugün:** Gün 1 (26.10) · **Güncel faz:** F2 tamamlandı (P1) → F3 — Tavsiye motoru
**Depo:** https://github.com/TahirAytekin/Veri-Madenciligi-ve-Is-Zekasi-E-Ticaret

---

## Şu an
- Veri altyapısı hazır: gerçek veri (son 3 ay, kişisel veri yok), 2 yıllık sahte veri, analiz tabloları.
- Plan 2 haftaya göre yeniden yazıldı. Yöntem: modeller sahte veriyle eğitilir, gerçek verinin son 3 ayıyla doğrulanır ([MODEL_DOGRULAMA.md](MODEL_DOGRULAMA.md)).
- Depo GitHub'a yüklendi (2026-10-24).
- `main` dalı korumada: silinemez, `--force` push yapılamaz (doğrudan push serbest).
- Ekip depoya eklendi: 4 collaborator (F0-01 ✅).
- Ortam doğrulandı (F0-02 ✅): Python 3.14'te tüm paketler kurulu; hazır modeller indirildi ve Türkçe örneklerle denendi; `python -m pytest` ile 19 kontrol.
- Metrikler hazır (F1-01, F1-02 ✅): 39 metrik, `analiz/metrikler.py`, tanımlar `docs/METRIKLER.md`. İade oranı 21 gün olgunlaşma ve az örnek kuralıyla hesaplanıyor.
- Gerçek veride iki düzeltme: bölünmüş (`UnPacked`) paketler çift sayılmıyor; iadeler pakete satır üzerinden bağlanıyor.
- Durum analizi hazır (F1-03 ✅): `python -m analiz.durum --veri sahte` → sağlık skoru + 11 kuraldan içgörüler (gerçek veride 81/100, 18 içgörü).
- Senaryo simülatörü hazır (F1-05 ✅): değişiklik yokken gerçek katkı payını %1,6 farkla tutturuyor. Gerçek veride beden iadelerini yarıya indirmek aylık +26 bin TL, 1 desi küçültmek yalnızca +0,9 bin TL (Trendyol Express'te 0–2 desi aynı ücret).
- Model altyapısı hazır (F2-01 ✅, F1-04 ✅): `modeller/ortak/` (aktarılabilir özellikler, sızıntısız geçmiş özellikleri, sahte → gerçek değerlendirme). Gerçek–sahte raporu: 4 özellik (`ay`, `saat`, `indirim_orani`, `model_onceki_puan`) gerçekte ters ilişkili, modellerden çıkarıldı. Beden–iade ilişkisi iki veride aynı. Çıta: eğitimsiz referans AUC 0,680.
- İade riski modeli hazır (F2-02 ✅, [model kartı](modeller/F2-02.md)): sahtede referansları geçiyor (AUC 0,691 vs 0,664), gerçekte mağazanın ürün geçmişini geçemiyor (0,671 vs 0,680; fark anlamlı değil). Monotonluk kısıtı gerçek AUC'yi 0,58'den 0,67'ye taşıdı. Karar: ürün düzeyinde risk için ürün geçmişi, beden/sepet eğilimi için model kullanılacak.
- Derin öğrenme iade riski tamamlandı (F2-03 ✅, [model kartı](modeller/F2-03.md)); tasarım ve ölçüt eğitimden önce commitlendi. PyTorch MLP gerçekte 0,669: ürün geçmişini geçemedi, F2-02'den ayırt edilemiyor, sahtede F2-02'den kötü. Web F2-02'yi kullanır. Bulgu: iki model ailesi aynı tavana (~0,68 = ürün geçmişi) çarptı; sahte doğrulama aktarılabilirliği ölçemiyor → karar önerisi K-14.
- **Sahte veri v2 (F1-06 ✅, [rapor](rapor/sahte_v2_kalibrasyon.md)):** sahte üretici test öncesi gerçek veriye (23.10.2025–15.07.2026) kalibre edildi; kalibrasyon hedeflerinin 15/16'sı tutuyor (v1: 6/16). `veri/sahte/` artık v2; v1 `--v1` ile birebir üretilebiliyor. F2-02 gerçekte ortalama 0,626 → 0,665 ve daha kararlı, ama ürün geçmişini (0,680) yine geçemiyor. Düzeltmeler: F2-02'nin v1 sonucu (0,671) şanslı bir tohumdu; beden düzeyinde eğilim önerisi geri çekildi (beden konumu gerçekte iadeyi öngörmüyor). MLP v2'de 0,590'a düştü. `docs/rapor/01_gercek_sahte.md` v1 verisine aittir.
- **Beden uyumu (F2-04 ✅, [model kartı](modeller/F2-04.md)):** `beden_oner(boy, kilo)` gerçek müşterilerin %42–50'sine tam aldığı bedeni öneriyor (en sık beden: %11–28; 3/3 tohumda anlamlı). Kalıp tablosu: gerçekte 7 dar, 1 bol ürün. Kalıp skoru beden iadesinin yönünü gerçekte zayıf ayırıyor (AUC 0,586, sınırda); satır düzeyi yön modeli kalıp skorunu geçemedi.
- **Talep tahmini (F2-05 ✅, [model kartı](modeller/F2-05.md)):** sahteyle eğitilen model gerçekte "geçen haftanın satışı"ndan anlamlı biçimde kötü (WAPE 0,56–0,65'e karşı 0,47; 3/3 tohum). İki tanı: gerçek çok satanlar sahte ölçeğin dışında (ağaç tavanı) ve gerçek talep kalıcı sıçramalar yapıyor, sahte ise ortalamaya dönüyor. Web'de stok tükenme tablosu geçen haftanın satış hızıyla hesaplanıyor (gerçekte 72 aktif ürün, 2'si 4 haftadan kısa sürede tükenecek).
- **Duygu analizi (F2-06 ✅, [model kartı](modeller/F2-06.md)):** hazır Türkçe BERT gerçek yorumlarda AUC 0,910 (ürün yorumlarında 0,924), ama önceden sabitlenen kelime listesinden (0,833) anlamlı biçimde iyi değil (+0,020 [−0,036, +0,076]). Bulgu: BERT genel puandan çok metindeki şikâyeti yakalıyor (4★ yorumların %79'u şikâyetli). Web'de genel duygu puandan, şikâyet işareti ve konu BERT'ten; gerçekte en sık şikâyet beden/kalıp (56) ve kumaş/kalite (47).
- **Doğrulama raporu (F2-12 ✅, [02_dogrulama.md](rapor/02_dogrulama.md)):** tüm modeller tek tabloda; web için `docs/rapor/02_dogrulama.json`. `python -m modeller.dogrulama_raporu --yeniden` tüm modelleri baştan çalıştırıp (~3 dk) aynı sayıları üretiyor. Gerçekte başarılı: F2-04C beden önerisi; diğerleri basit referansları geçemedi. **Faz 2'nin P1 görevleri tamamlandı (K1 ✅, plandan 6 gün önce).**
- **Tavsiye motoru (F3-01…03 ✅, [kurallar](TAVSIYE_KURALLARI.md)):** 14 kural; her tavsiyede kanıt, aksiyon, aylık TL etkisi (senaryo simülatörüyle aynı birim modeli) ve doğrulama raporuna bağlı güven. `python -m tavsiye.motor --veri gercek` → gerçekte 36 tavsiye; haftalık planın ilk 10 aksiyonu aylık ~28,7 bin TL (üst sınır). En büyük kalem: beden önerici (~10,4 bin TL/ay), stok tükenmek üzere olan çok satan jean (~6,9 bin TL/ay).
- **Ürün sağlık kartı (F3-05 ✅):** `python -m tavsiye.urun_karti --veri gercek` → 76 ürün: 53 iyi, 8 dikkat, 15 sorunlu. Bulgu: gerçek stokların çoğu temsili (1000, 999 …): 72 aktif ürünün 64'ünde stok süresi hesaplanamaz. Stok tablosu ve stok tavsiyeleri buna göre düzeltildi.
- **Sıradaki adım:** F3-04 soru cevap önerici (LLM); paralel: web iskeleti (F5-01), F4 asistan. Ekip K-14'ü onaylamalı.

## Aktif görevler

Görev üstlenen kişi bir satır ekler, bırakınca siler.

| görev | kim | dal | başladı | son durum (tek cümle) |
|---|---|---|---|---|
| F3-04 | Tahir | `gorev/F3-04-cevap-onerici` | 2026-10-26 | tasarım ve başarı ölçütü önceden yazıldı ([F3-04.md](modeller/F3-04.md)); boy-kilo ve beden çıkarma hazır |

## Gün 1–3 için sıradaki görevler
1. ~~F0-01: GitHub'a push, collaborator'lar~~ ✅
2. ~~F0-02: paket kurulumları~~ ✅
3. ~~F0-03: Anthropic API anahtarı~~ ✅ (26.10, test isteği başarılı)
4. **F0-04:** herkes kurulumu yapar, "Ekip" tablosuna kendini ekler
5. ~~F1-01 → F1-02: metrik sözlüğü ve `analiz/metrikler.py`~~ ✅
6. ~~F1-03, F1-04, F1-05~~ ✅ · Faz 1 tamamlandı
7. **F5-01:** web iskeleti (artık başlayabilir: metrikler hazır)
8. ~~F2-01 model altyapısı~~ ✅ · ~~F2-02 iade riski (GBM)~~ ✅ · ~~F2-03 iade riski (MLP)~~ ✅ · ~~F1-06 sahte veri v2~~ ✅ · ~~F2-04 beden uyumu~~ ✅ · ~~F2-05 talep~~ ✅ · ~~F2-06 BERT duygu~~ ✅ · ~~F2-12 doğrulama raporu~~ ✅ · ~~F3-01…03 tavsiye motoru~~ ✅ · ~~F3-05 ürün kartı~~ ✅ · **F3-04:** cevap önerici

## Ara kontroller
| kontrol | gün | ölçüt | durum |
|---|---|---|---|
| K1 | Gün 7 (01.11) | P1 modelleri gerçek veride test edildi, doğrulama tablosu hazır | ✅ 26.10 |
| K2 | Gün 10 (04.11) | tavsiyeler, aksiyon planı ve asistan çalışıyor | ⬜ |
| K3 | Gün 12 (06.11) | 10 web sayfası çalışıyor | ⬜ |
| K4 | Gün 14 (08.11) | teslim: rapor, sunum, demo | ⬜ |

## Devredilebilir görevler
Yarım bırakılıp devralınmayı bekleyen görevler (devir notu bağlantısıyla).

| görev | bırakan | devir notu |
|---|---|---|
| — | | |

## Engeller ve açık sorular
- ~~Anthropic API anahtarı (F0-03)~~ ✅ 26.10: `.env` → `ANTHROPIC_API_KEY` (yalnızca proje sahibinde). Bütçe takibi: tahmini toplam ~20–30 $; F4-05'te ölçülecek. Anahtarı olmayan ekip üyeleri asistanın araç ve arama kısmını anahtarsız geliştirebilir.
- **Ürün maliyeti (isteğe bağlı, F1-05):** Senaryo simülatörü maliyetsiz de çalışır; satıcı `barkod, birim_maliyet` listesi verirse gerçek kâr hesaplanır.

## Ekip
| isim | GitHub | iz (plan §6) | kurulum (F0-04) |
|---|---|---|---|
| Tahir | [TahirAytekin](https://github.com/TahirAytekin) | proje sahibi, gerçek veri | ✅ |
| — | [cgnarsln-arch](https://github.com/cgnarsln-arch) | — | ⬜ |
| Deha Furkan Sarıer | [dehasarier2005](https://github.com/dehasarier2005) | — | ⬜ |
| Selim | [selimmoroglu](https://github.com/selimmoroglu) | — | ⬜ |
| Yakup | [yakup-ayata](https://github.com/yakup-ayata) | — | ⬜ |

## Son devir notları
- 2026-10-24 — Tahir — [Başlangıç: veri altyapısı ve proje planı](devir/2026-10-24-tahir-baslangic.md)

## Ölçümler
| ölçüm | değer | tarih |
|---|---|---|
| Gerçek veri: sipariş paketi | 3.266 (16.07–23.10.2026) | 2026-10-24 |
| Gerçek veri: iade talebi / finans hareketi | 6.350 / 65.055 | 2026-10-24 |
| Asistan: soru başı maliyet | ölçülmedi (F4-05) | — |
