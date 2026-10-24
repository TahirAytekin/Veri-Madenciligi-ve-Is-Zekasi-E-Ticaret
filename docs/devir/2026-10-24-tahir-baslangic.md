# Devir Notu — Başlangıç (Faz 0 öncesi) — 2026-10-24

**Yazan:** Tahir (Claude Code ile) · **Dal:** `main` · **Görev durumu:** ✅ veri altyapısı bitti, Faz 0 başlıyor

## Ne yapıldı
- **Veri çekimi (`cekim/`):** Trendyol API'sinden sipariş, ürün, soru, iade ve finans; mağaza sayfasından yorumlar.
  - Artımlı çekim: iade ve finansta son 45 gün, sorularda 4 hafta.
  - `guncelle.py` ile tek komut; çekim → temizleme → analiz.
- **Kişisel veri:** Ad, adres, telefon, e-posta, TC gibi alanlar daha diske yazılmadan siliniyor (`cekim/anonim.py`). Müşteri ID'si ve kargo takip no tek yönlü özetleniyor.
- **Şema:** 12 temel tablo ([VERI_SOZLUGU.md](../VERI_SOZLUGU.md)). Gerçek ve sahte veri birebir aynı sütunlara sahip.
- **Sahte veri:** 2 yıllık, gerçek verinin dağılımlarına göre ayarlandı. Modellerin bulması için gerçekçi ilişkiler gömüldü (mevsim, kampanya, indirim esnekliği, kalıp → iade, reklam etkisi).
  - Gizli doğru cevaplar `veri/sahte/dogru_cevaplar/` klasöründe.
- **Analiz tabloları:** 9 tablo (`hazirlama/ozellik_cikar.py`). `--kesim` ile sızıntısız sürüm üretiliyor.
- **Dokümanlar:** README, VERI_SOZLUGU, MODEL_DOGRULAMA, PROJE_PLANI, CONTRIBUTING, DURUM.

## Nerede kaldım
- Depo yerelde hazır ve ilk commit'ler atıldı; GitHub'a henüz push edilmedi (F0-01).

## Devralan buradan başlasın
1. [CONTRIBUTING.md](../../CONTRIBUTING.md) §1'deki kurulumu yap ve `python guncelle.py --sahte` çalıştır.
2. [VERI_SOZLUGU.md](../VERI_SOZLUGU.md) dosyasını oku. Aşağıdaki örnekle tabloları yükle:
   ```python
   import sys; sys.path.insert(0, "hazirlama")
   from ortak import VERI, hepsini_oku
   t = hepsini_oku(VERI / "sahte")
   ```
3. [PROJE_PLANI.md](../PROJE_PLANI.md) bölüm 4'teki gün sırasına göre F0-02 (ortam) veya F1-01'i (metrik sözlüğü) üstlen.

## Nasıl çalıştırılır
```bash
python guncelle.py --sahte                                    # sahte veri analiz tabloları
python hazirlama/ozellik_cikar.py sahte --kesim 2026-06-30    # sızıntısız (model eğitimi için)
python hazirlama/sahte_veri_uret.py                           # sahte veriyi baştan üret (~15 sn)
```

## Bilinen sorunlar / dikkat edilecekler
- **Gerçek veri kısa:** Siparişler Temmuz 2026'dan beri var ve her gün birikiyor. Finans tablosunda 1 yıllık satış kaydı, iade tablosunda 2024'ten beri iadeler var.
- **Doğrulama yöntemi:** Modeller sahte veriyle eğitilir, gerçek verinin son 3 ayıyla test edilir ([MODEL_DOGRULAMA.md](../MODEL_DOGRULAMA.md)). `analiz/` tablolarının tüm dönemi kapsayan özetlerini özellik olarak kullanma.
- **`urunler` bugünün durumu:** Stok, fiyat ve satışta bilgisi bugüne ait, geçmişi yok. Fiyat ve stok geçmişi `veri/ham/urun_gecmisi/` altında yeni birikmeye başladı.
- **Sahte metinler şablondan üretildi:** Duygu analizi hazır eğitilmiş Türkçe BERT ile doğrudan gerçek yorumlarda ölçülür (F2-06).
- **Python sürümü:** Proje şu an Python 3.14 ile çalışıyor. Derin öğrenme paketlerinin kurulumu F0-02'de doğrulanacak.

## Açık sorular ve bekleyen kararlar
- Web teknolojisi: Streamlit (karar K-05).
- Asistan için Anthropic API anahtarı ve bütçe (F0-03).
- Satıcıdan ürün maliyet listesi (isteğe bağlı; senaryo simülatöründe F1-05).
