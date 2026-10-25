# Durum — Kaldığımız Yer

Projeye dönen ya da yeni katılan herkesin ilk okuyacağı sayfa. **Her devirde ve her PR birleştirmesinde güncellenir.**

**Son güncelleme:** 2026-10-25 · **Güncelleyen:** Tahir
**Takvim:** 14 gün, Gün 1 = 26.10.2026 Pzt, teslim = 08.11.2026 Paz ([plan §4](PROJE_PLANI.md#4-takvim-14-gün))
**Bugün:** Gün 0 (hazırlık) · **Güncel faz:** F0 — Altyapı
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
- **Sıradaki adım:** F2-04 beden uyumu ve kalıp; paralel: web iskeleti (F5-01), API anahtarı (F0-03). Ekip K-14'ü onaylamalı.

## Aktif görevler

Görev üstlenen kişi bir satır ekler, bırakınca siler.

| görev | kim | dal | başladı | son durum (tek cümle) |
|---|---|---|---|---|
| — | | | | |

## Gün 1–3 için sıradaki görevler
1. ~~F0-01: GitHub'a push, collaborator'lar~~ ✅
2. ~~F0-02: paket kurulumları~~ ✅
3. **F0-03:** Anthropic API anahtarı (Tahir)
4. **F0-04:** herkes kurulumu yapar, "Ekip" tablosuna kendini ekler
5. ~~F1-01 → F1-02: metrik sözlüğü ve `analiz/metrikler.py`~~ ✅
6. ~~F1-03, F1-04, F1-05~~ ✅ · Faz 1 tamamlandı
7. **F5-01:** web iskeleti (artık başlayabilir: metrikler hazır)
8. ~~F2-01 model altyapısı~~ ✅ · ~~F2-02 iade riski (GBM)~~ ✅ · ~~F2-03 iade riski (MLP)~~ ✅ · **F2-04:** beden uyumu

## Ara kontroller
| kontrol | gün | ölçüt | durum |
|---|---|---|---|
| K1 | Gün 7 (01.11) | P1 modelleri gerçek veride test edildi, doğrulama tablosu hazır | ⬜ |
| K2 | Gün 10 (04.11) | tavsiyeler, aksiyon planı ve asistan çalışıyor | ⬜ |
| K3 | Gün 12 (06.11) | 10 web sayfası çalışıyor | ⬜ |
| K4 | Gün 14 (08.11) | teslim: rapor, sunum, demo | ⬜ |

## Devredilebilir görevler
Yarım bırakılıp devralınmayı bekleyen görevler (devir notu bağlantısıyla).

| görev | bırakan | devir notu |
|---|---|---|
| — | | |

## Engeller ve açık sorular
- **Anthropic API anahtarı ve bütçe (F0-03):** Asistan ve cevap önerici için gerekli; tahmini toplam ~20–30 $. Anahtar gelene kadar araçlar ve arama anahtarsız geliştirilebilir.
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
