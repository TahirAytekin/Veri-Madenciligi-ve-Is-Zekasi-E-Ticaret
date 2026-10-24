# CLAUDE.md

Trendyol satıcı verisiyle analiz, ML/derin öğrenme tahminleri, tavsiye motoru, RAG asistanı ve web uygulaması
geliştiren ekip projesi. Yapay zekâ asistanları ve yeni ekip üyeleri için kısa bağlam.

## Önce bunları oku
- `docs/DURUM.md` — şu an neredeyiz, aktif görevler, son devir notları
- `docs/PROJE_PLANI.md` — görevler (ID'ler: F0-01 ...), mimari, kararlar
- `CONTRIBUTING.md` — dal/commit/PR kuralları, devir protokolü, bitti tanımı
- `docs/VERI_SOZLUGU.md`, `docs/MODEL_DOGRULAMA.md` — veri ve doğrulama

## Kesin kurallar
- `.env`, `veri/ham/`, `veri/gercek/`, `ciktilar/gercek/` asla commitlenmez veya okunup dışarı aktarılmaz.
- Geliştirme `veri/sahte/` ile yapılır; kod `sahte` ve `gercek` için aynı şekilde çalışmalı.
- Model eğitiminde kesimli tablolar kullanılır (`hazirlama/ozellik_cikar.py --kesim`, `ortak.kesim_uygula`); `analiz/` tabloları tüm dönemi kapsar ve sızıntı yapar.
- `veri/sahte/dogru_cevaplar/` yalnızca doğrulama içindir; modele özellik olarak verilmez.
- Metrikler tek yerde hesaplanır (`analiz/metrikler.py`, Faz 1'de oluşturulacak).
- Sistem Trendyol'a yazmaz; yalnızca okur ve önerir.
- İş bitince planı, DURUM.md'yi güncelle; yarım kalan iş için `docs/devir/` altına not yaz.

## Kod stili
- Türkçe isimlendirme (`siparisler`, `iade_orani`); bölüm başlıkları `# ====` bloklarıyla; modül başında kısa docstring.
- Yollar `hazirlama/ortak.py` içindeki `VERI` / `HAM` sabitlerinden; sabit `C:\...` yolu yok.
- Commit: `<ID>: <ne yapıldı>`, dal: `gorev/<ID>-<konu>`.

## Komutlar
```bash
python guncelle.py --sahte                              # sahte veri analiz tabloları
python hazirlama/ozellik_cikar.py sahte --kesim 2026-06-30
python hazirlama/sahte_veri_uret.py                     # sahte veriyi yeniden üret
python guncelle.py                                      # (yalnızca proje sahibi) gerçek veriyi çek + hazırla
```
