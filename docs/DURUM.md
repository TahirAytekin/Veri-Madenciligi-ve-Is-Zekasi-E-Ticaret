# Durum — Kaldığımız Yer

Projeye dönen ya da yeni katılan herkesin ilk okuyacağı sayfa. **Her devirde ve her PR birleştirmesinde güncellenir.**

**Son güncelleme:** 2026-10-24 · **Güncelleyen:** Tahir
**Takvim:** 14 gün, Gün 1 = 26.10.2026 Pzt, teslim = 08.11.2026 Paz ([plan §4](PROJE_PLANI.md#4-takvim-14-gün))
**Bugün:** Gün 0 (hazırlık) · **Güncel faz:** F0 — Altyapı
**Depo:** https://github.com/TahirAytekin/Veri-Madenciligi-ve-Is-Zekasi-E-Ticaret

---

## Şu an
- Veri altyapısı hazır: gerçek veri (son 3 ay, kişisel veri yok), 2 yıllık sahte veri, analiz tabloları.
- Plan 2 haftaya göre yeniden yazıldı. Yöntem: modeller sahte veriyle eğitilir, gerçek verinin son 3 ayıyla doğrulanır ([MODEL_DOGRULAMA.md](MODEL_DOGRULAMA.md)).
- Depo GitHub'a yüklendi (2026-10-24).
- `main` dalı korumada: silinemez, `--force` push yapılamaz (doğrudan push serbest).
- **Sıradaki adım:** collaborator'ları eklemek (F0-01), ortamı doğrulamak (F0-02), API anahtarı (F0-03).

## Aktif görevler

Görev üstlenen kişi bir satır ekler, bırakınca siler.

| görev | kim | dal | başladı | son durum (tek cümle) |
|---|---|---|---|---|
| F0-01 | Tahir | `main` | 2026-10-24 | push edildi, `main-koruma` kuralı aktif; collaborator davetleri bekleniyor |

## Gün 1–3 için sıradaki görevler
1. **F0-01:** GitHub'a push, collaborator'lar (Tahir)
2. **F0-02:** paket kurulumlarını doğrula, `requirements.txt` güncelle
3. **F0-03:** Anthropic API anahtarı (Tahir)
4. **F0-04:** herkes kurulumu yapar, "Ekip" tablosuna kendini ekler
5. **F1-01 → F1-02:** metrik sözlüğü ve `analiz/metrikler.py` (web, tavsiye ve asistan buna bağlı)
6. **F5-01:** web iskeleti (F1-02 ile paralel)
7. **F2-01:** model altyapısı: aktarılabilir özellikler, sahte → gerçek değerlendirme

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
- **Paket uyumluluğu (F0-02):** Python 3.14'te torch, lightgbm ve sentence-transformers kurulumu doğrulanmalı.
- **Ürün maliyeti (isteğe bağlı, F1-05):** Senaryo simülatörü maliyetsiz de çalışır; satıcı `barkod, birim_maliyet` listesi verirse gerçek kâr hesaplanır.

## Ekip
| isim | GitHub | iz (plan §6) | kurulum (F0-04) |
|---|---|---|---|
| Tahir | [TahirAytekin](https://github.com/TahirAytekin) | proje sahibi, gerçek veri | ✅ |

## Son devir notları
- 2026-10-24 — Tahir — [Başlangıç: veri altyapısı ve proje planı](devir/2026-10-24-tahir-baslangic.md)

## Ölçümler
| ölçüm | değer | tarih |
|---|---|---|
| Gerçek veri: sipariş paketi | 3.266 (16.07–23.10.2026) | 2026-10-24 |
| Gerçek veri: iade talebi / finans hareketi | 6.350 / 65.055 | 2026-10-24 |
| Asistan: soru başı maliyet | ölçülmedi (F4-05) | — |
