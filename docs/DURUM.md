# Durum — Kaldığımız Yer

Projeye dönen ya da yeni katılan herkesin ilk okuyacağı sayfa. **Her devirde ve her PR birleştirmesinde güncellenir.**

**Son güncelleme:** 2026-10-24 · **Güncelleyen:** Tahir
**Güncel faz:** Faz 0 — Ekip ve altyapı ([plan](PROJE_PLANI.md#faz-0--ekip-ve-altyapı-hafta-1))

---

## Şu an
- Veri altyapısı tamamlandı: çekim, temizleme, sahte veri, analiz tabloları, doğrulama araçları ([plan §2](PROJE_PLANI.md#2-mevcut-durum-tamamlanan-temel)).
- Proje planı ve çalışma rehberi yazıldı.
- **Sıradaki adım:** depoyu GitHub'a yüklemek ve ekibi eklemek (F0-01).

## Aktif görevler

Görev üstlenen kişi bir satır ekler, bırakınca siler.

| görev | kim | dal | başladı | son durum (tek cümle) |
|---|---|---|---|---|
| F0-01 | Tahir | `main` | 2026-10-24 | depo yerelde hazır, GitHub'a push bekleniyor |

## Sıradaki önerilen görevler
1. **F0-01:** GitHub deposu, ilk push, collaborator'lar, `main` koruması (Tahir)
2. **F0-02:** herkes kurulumu yapar ve aşağıdaki "Ekip" tablosuna kendini ekler
3. **F0-03:** ortak Python sürümü ve `requirements-dev.txt`
4. **F0-04:** GitHub Actions kontrolleri
5. **F1-01 → F1-02:** metrik sözlüğü ve `analiz/metrikler.py` (Faz 1'in temeli; web, tavsiye ve asistan buna bağlı)

## Devredilebilir görevler
Yarım bırakılıp devralınmayı bekleyen görevler (devir notu bağlantısıyla).

| görev | bırakan | devir notu |
|---|---|---|
| — | | |

## Engeller ve açık sorular
- **Web teknolojisi (F6-01):** Streamlit öneriliyor; ekip onayı bekleniyor.
- **LLM API anahtarı ve bütçesi (F5-01):** asistan için Anthropic API anahtarını kim alacak, aylık bütçe ne olacak?
- **Ürün maliyeti verisi (F2-12):** gerçek kârlılık için satıcıdan `barkod, birim_maliyet` listesi alınmalı (Tahir).

## Ekip
| isim | GitHub | alan | kurulum (F0-02) |
|---|---|---|---|
| Tahir | — | proje sahibi, gerçek veri | ✅ |

## Son devir notları
- 2026-10-24 — Tahir — [Başlangıç: veri altyapısı ve proje planı](devir/2026-10-24-tahir-baslangic.md)

## Ölçümler (güncellendikçe)
| ölçüm | değer | tarih |
|---|---|---|
| Gerçek veri: sipariş paketi | 3.266 (Temmuz 2026'dan beri, birikiyor) | 2026-10-24 |
| Gerçek veri: iade talebi / finans hareketi | 6.350 / 65.055 | 2026-10-24 |
| Asistan: soru başı maliyet | ölçülmedi (F5-04) | — |
