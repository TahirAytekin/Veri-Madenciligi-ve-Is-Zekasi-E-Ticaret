# Trendyol Satıcı Karar Destek Sistemi

Bir Trendyol satıcısının sipariş, ürün, iade, finans, soru ve yorum verilerinden:
- mağazanın **bugünkü durumunu** gösteren analizler,
- **geleceğe** dönük makine öğrenimi ve derin öğrenme tahminleri,
- **ne yapması gerektiğini** söyleyen önceliklendirilmiş tavsiyeler,
- satıcının **verisiyle konuşabildiği** RAG tabanlı bir asistan

üreten ve bunları bir web uygulamasında sunan ekip projesi.

| | |
|---|---|
| **Şu an neredeyiz?** | [docs/DURUM.md](docs/DURUM.md) |
| **Yol haritası ve görevler** | [docs/PROJE_PLANI.md](docs/PROJE_PLANI.md) |
| **Nasıl çalışıyoruz?** | [CONTRIBUTING.md](CONTRIBUTING.md) |
| **Veri** | [docs/VERI_SOZLUGU.md](docs/VERI_SOZLUGU.md) · [docs/MODEL_DOGRULAMA.md](docs/MODEL_DOGRULAMA.md) |

## Hızlı başlangıç (ekip üyeleri)

```bash
git clone <depo-adresi> && cd trendyoll
python -m venv .venv && .venv\Scripts\activate     # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python guncelle.py --sahte                           # sahte veri analiz tablolarını üretir
```

Ekip üyeleri **sahte veriyle** çalışır; `.env` gerekmez. Gerçek veri ve API anahtarı yalnızca proje sahibindedir.

## Kurulum (gerçek veri, yalnızca proje sahibi)

```bash
pip install -r requirements.txt
cp .env.example .env        # sonra .env içine kendi API bilgilerinizi yazın
```

API bilgileri: Trendyol satıcı paneli → Hesap Bilgilerim → Entegrasyon Bilgileri.

## Klasör yapısı

```
trendyoll/
├── .env                     gizli ayarlar (API anahtarı, satıcı ID, anonimleştirme tuzu) — PAYLAŞMAYIN
├── .env.example             .env şablonu
├── CONTRIBUTING.md          çalışma kuralları, devir protokolü, bitti tanımı
├── CLAUDE.md                yapay zekâ asistanları için proje özeti
├── .github/                 PR ve görev (issue) şablonları
├── guncelle.py              tek komutla: çekim → temizleme → analiz tabloları
├── cekim/                   Trendyol'dan ham veri çeken betikler (artımlı)
│   ├── ayarlar.py           .env okuma, kimlik doğrulama, dayanıklı istek, güvenli dosya yazma
│   ├── siparisler.py        günlük   — kargo paketleri (API son ~3 ayı verir, geçmiş dosyada birikir)
│   ├── urunler.py           günlük   — katalog + o günün fiyat/stok kaydı
│   ├── sorular.py           günlük   — müşteri soruları ve cevapları
│   ├── iadeler.py           günlük   — iade talepleri ve nedenleri
│   ├── finans.py            günlük   — cari hesap: satış/iade/komisyon, kargo/reklam kesintileri
│   └── yorumlar.py          haftalık — ürün ve satıcı yorumları (resmi olmayan uç nokta)
├── hazirlama/
│   ├── ortak.py             tablo şemaları, kampanya takvimi, sınıflandırma kuralları
│   ├── temizle.py           veri/ham → veri/gercek (kişisel veriler atılır)
│   ├── sahte_veri_uret.py   aynı şemada sahte veri → veri/sahte
│   └── ozellik_cikar.py     temel tablolar → analiz tabloları
├── veri/
│   ├── ham/                 API çıktıları + urun_gecmisi/ (günlük fiyat/stok) — PAYLAŞMAYIN
│   ├── gercek/              temizlenmiş gerçek veri + analiz/ — PAYLAŞMAYIN
│   └── sahte/               sahte veri + analiz/ — paylaşılabilir, geliştirme için bunu kullanın
│       └── dogru_cevaplar/  sahte veriyi üreten gizli parametreler (yalnızca model doğrulama için)
├── docs/
│   ├── DURUM.md             kaldığımız yer: aktif görevler, son devir notları
│   ├── PROJE_PLANI.md       amaç, mimari, fazlar ve görevler, takvim, kararlar, riskler
│   ├── devir/               devir notları (her devir ayrı dosya)
│   ├── VERI_SOZLUGU.md      tüm tablolar, sütunlar ve aralarındaki bağlantılar
│   └── MODEL_DOGRULAMA.md   tahminlerin doğruluğu nasıl kontrol edilir (sızıntısız test, baseline, metrikler)
└── loglar/                  güncelleme logları
```

## Kullanım

```bash
python guncelle.py                       # günlük güncelleme (pazartesileri yorumlar da çekilir)
python guncelle.py --haftalik            # yorumlar dahil
python guncelle.py --sadece finans       # tek kaynak
python guncelle.py --cekmeden            # API'ye istek atmadan yalnızca temizleme + analiz
python guncelle.py --sahte               # yalnızca sahte veri analiz tabloları (ekip üyeleri)

python -m cekim.siparisler               # tek bir çekim betiği
python hazirlama/sahte_veri_uret.py      # sahte veriyi yeniden üret (ayarlar dosyanın başında)
python hazirlama/ozellik_cikar.py sahte  # sahte veri için analiz tabloları
python hazirlama/ozellik_cikar.py sahte --kesim 2026-06-30   # sızıntısız: yalnızca kesime kadar bilinenler
```

Çekimler **artımlıdır**: ilk çalıştırmada geçmiş alınır, sonrakilerde yalnızca son dönem (iade ve finans
için 45 gün, sorular için 4 hafta) çekilip mevcut dosyayla birleştirilir. Bir çekim yarıda kesilirse
önceki dosya bozulmaz. Günlük bir güncelleme birkaç yüz istek atar; Trendyol'un istek sınırına yaklaşmaz,
sınır aşılırsa (HTTP 429) betikler bekleyip yeniden dener.

### Her gün otomatik çalıştırma (Windows Görev Zamanlayıcı)

Komut isteminde (proje yolunu kendi yolunuzla değiştirin):

```bat
schtasks /Create /SC DAILY /ST 07:00 /TN "Trendyol Veri Guncelleme" ^
  /TR "\"C:\Program Files\Python314\python.exe\" \"C:\Users\PC\Desktop\trenyol dosyaları\trendyoll\guncelle.py\""
```

Kaldırmak için: `schtasks /Delete /TN "Trendyol Veri Guncelleme"`. Sonuçlar `loglar/` klasöründedir.

## Veriyle çalışmak

```python
import sys; sys.path.insert(0, "hazirlama")
from ortak import VERI, hepsini_oku
import pandas as pd

t = hepsini_oku(VERI / "sahte")                                  # 12 temel tablo, tarihler hazır
urun = pd.read_csv(VERI / "sahte" / "analiz" / "urun_ozet.csv")  # analiz tabloları
```

Model ve analizleri `sahte` üzerinde geliştirin; hazır olduğunda klasör adını `gercek` yaparak aynı kodu gerçek
veride çalıştırın. Tabloların ayrıntısı: [docs/VERI_SOZLUGU.md](docs/VERI_SOZLUGU.md).

Modeller sahte veriyle eğitilir ve gerçek verinin son 3 ayıyla doğrulanır (gerçek veri eğitimde kullanılmaz):
[docs/MODEL_DOGRULAMA.md](docs/MODEL_DOGRULAMA.md).

## Kişisel veriler (KVKK)

Analizde kullanılmayan kişisel veriler **diske hiç yazılmaz**: çekim betikleri her kaydı
[cekim/anonim.py](cekim/anonim.py) üzerinden geçirir.

| | alanlar |
|---|---|
| silinir | ad-soyad, açık adres, mahalle, posta kodu, telefon, e-posta, TC/vergi no, fatura adresi ve linki, kargo takip linki, teslimat kodu |
| tek yönlü özetlenir | müşteri ID (`M…`, tekrar alan müşteri analizi için), kargo takip no (`K…`, kargo faturasını pakete bağlamak için) |
| tutulur | il, ilçe; ürün, tutar, tarih, durum; yorumlardaki boy-kilo (kişiye bağlanamaz, beden önerisi için) |
| serbest metin | soru, yorum ve iade notlarında geçen telefon, e-posta ve TC numaraları `[gizlendi]` ile değiştirilir |

Özetler `.env` içindeki `MUSTERI_ID_TUZ` ile üretilir; tuz değişirse aynı müşteri farklı ID alır.

## Güvenlik

- `.env`, `veri/ham/` ve `veri/gercek/` gerçek ve gizli bilgi içerir; `.gitignore` bunları sürüm kontrolünden
  hariç tutar. Projeyi paylaşırken bu üçünü dahil etmeyin; `veri/sahte/` paylaşılabilir.
- API anahtarı geçmişte betiklerin içinde açık yazılıydı. Kod veya dosyalar bir yerle paylaşıldıysa satıcı
  panelinden **yeni bir API anahtarı oluşturup** `.env` dosyasını güncelleyin.
