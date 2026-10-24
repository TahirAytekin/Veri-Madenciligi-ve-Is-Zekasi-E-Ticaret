"""Gerçek veriyle BİREBİR aynı şemada, tamamen sahte bir Trendyol mağaza veri seti üretir.

Çıktı: veri/sahte/*.csv  (kişisel veri içermez; paylaşılabilir)

Dağılımlar gerçek verinin özetlerinden ayarlandı (kategori karışımı, fiyat aralıkları, saat/gün
deseni, il dağılımı, indirim türleri, kargo süreleri, puan dağılımı, soru konuları). Hiçbir gerçek
müşteri, ürün adı, yorum veya soru metni kopyalanmadı.

Modellerin öğrenebilmesi için veriye bilinçli olarak şu ilişkiler gömüldü:
  - Kategoriye göre mevsimsellik (şort yazın, bot kışın), haftanın günü ve saat etkisi
  - Kampanya günleri (Efsane Kasım, 11.11, Black Friday, bayram öncesi ...) talep artışı
  - Ürüne özel kupon dönemlerinde fiyat esnekliğine göre talep artışı
  - Pahalı ürünün daha az satması, kalitesi düşük ürünün daha az satıp düşük puan alması
  - Kalıbı dar/bol ürünlerde daha çok beden sorusu ve "dar geldi / bol geldi" yorumu
  - Müşterinin boy-kilosuna göre beden seçimi, birlikte alınan tamamlayıcı ürünler
  - Enflasyon kaynaklı kademeli fiyat artışları, mağazanın zamanla büyümesi
"""
import hashlib
import sys
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from ortak import VERI, iade_neden_grubu, indirim_turu, kaydet, kesinti_grubu, ozel_gunler

sys.stdout.reconfigure(encoding="utf-8")

# ====================================================
# 1) AYARLAR
# ====================================================

TOHUM = 42
BASLANGIC = date(2024, 10, 17)
BITIS = datetime(2026, 10, 16, 18, 0)   # veri çekim anı
HEDEF_GUNLUK_SATIR = 36                 # son 90 günde günlük ortalama satış satırı (gerçekte ~36)
MAGAZA = "DEMOSTORE"
CIKTI = VERI / "sahte"

rng = np.random.default_rng(TOHUM)

# ====================================================
# 2) SABİTLER
# ====================================================

# ad, iş birimi, komisyon %, beden seti, güncel fiyat aralığı, göreli talep, mevsim, model sayısı, kod
KATEGORILER = [
    ("Eşofman Altı", "Women B", 21.5, "harf7", (449, 849), 600, "tum", 16, "esf"),
    ("Kemer", "Accessories Textile", 22.5, "kemer", (399, 549), 560, "tum", 6, "kmr"),
    ("Şort & Bermuda", "Women B", 20.4, "jean", (749, 1499), 420, "yaz", 10, "srt"),
    ("Bluz", "Women B", 21.5, "harf5", (449, 899), 380, "tum", 12, "blz"),
    ("Spor T-Shirt", "Sports Textile", 21.5, "harf5", (549, 799), 120, "yaz", 6, "sts"),
    ("T-Shirt", "Women B", 21.5, "harf5", (449, 799), 190, "yaz", 7, "tst"),
    ("Body", "Women B", 21.5, "harf5", (549, 999), 135, "tum", 6, "bdy"),
    ("Alt - Üst Takım", "Women B", 17.7, "harf5", (1299, 1999), 107, "tum", 6, "tkm"),
    ("Jeans", "Women B", 21.5, "jean", (899, 1999), 90, "tum", 10, "jns"),
    ("Pantolon", "Women B", 21.5, "harf6", (649, 1299), 50, "tum", 7, "pnt"),
    ("Ceket", "Women B", 19.95, "harf4", (999, 2499), 120, "kis", 5, "ckt"),
    ("Sweatshirt", "Women B", 18.5, "harf4", (899, 1499), 65, "kis", 5, "swt"),
    ("Hırka", "Women B", 18.5, "harf4", (899, 1499), 30, "kis", 3, "hrk"),
    ("Etek", "Women B", 16.0, "harf6", (699, 1299), 30, "yaz", 4, "etk"),
    ("Gömlek", "Women B", 21.5, "harf3", (649, 999), 10, "tum", 2, "gml"),
    ("Spor Eşofman Takımı", "Sports Textile", 21.5, "harf4", (1299, 1999), 50, "kis", 3, "set"),
    ("Oxford Ayakkabı", "Shoes B", 16.6, "ayakkabi", (1299, 1799), 85, "kis", 4, "oxf"),
    ("Kar Botu", "Shoes B", 16.6, "ayakkabi", (1999, 2999), 30, "kis", 2, "bot"),
    ("Sneaker", "Shoes B", 16.6, "ayakkabi", (999, 1799), 20, "tum", 2, "snk"),
    ("Yağmurluk & Rüzgarlık", "Women B", 21.5, "harf4", (999, 1999), 20, "kis", 2, "ygm"),
    ("Pijama Altı", "Underwear", 21.5, "harf4", (449, 699), 8, "tum", 2, "pjm"),
    ("Çorap", "Underwear", 21.5, "corap", (99, 199), 4, "tum", 1, "crp"),
]
KAT = {k[0]: dict(zip(["ad", "is_birimi", "komisyon", "beden_seti", "fiyat", "talep", "mevsim",
                       "model_sayisi", "kod"], k)) for k in KATEGORILER}

# Aylık mevsim çarpanları (Ocak..Aralık)
MEVSIM = {
    "yaz": [0.30, 0.35, 0.50, 0.80, 1.20, 1.60, 1.70, 1.50, 1.00, 0.60, 0.40, 0.35],
    "kis": [1.50, 1.20, 0.80, 0.50, 0.30, 0.20, 0.20, 0.35, 0.70, 1.30, 1.70, 1.70],
    "tum": [0.90, 0.85, 0.95, 1.00, 1.05, 1.00, 1.00, 1.05, 1.10, 1.05, 1.10, 1.00],
}

HARFLER = ["2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL"]
BEDEN_SETLERI = {
    "harf3": ["S", "M", "L"],
    "harf4": ["S", "M", "L", "XL"],
    "harf5": ["XS", "S", "M", "L", "XL"],
    "harf6": ["2XS", "XS", "S", "M", "L", "XL"],
    "harf7": ["XS", "S", "M", "L", "XL", "2XL", "3XL"],
    "jean": ["26", "27", "28", "29", "30", "31", "32", "33", "34"],
    "ayakkabi": ["36", "37", "38", "39", "40"],
    "kemer": ["110 CM"],
    "corap": ["36 - 40"],
}

# renk: (seçilme ağırlığı, talep çarpanı)
RENKLER = {
    "Siyah": (0.22, 1.40), "Gri": (0.08, 0.95), "Beyaz": (0.07, 1.05), "Pembe": (0.06, 1.10),
    "Lacivert": (0.05, 0.90), "Mavi": (0.05, 1.00), "Kahverengi": (0.05, 0.85), "Bordo": (0.05, 0.90),
    "Yeşil": (0.04, 0.80), "Bej": (0.04, 0.90), "Ekru": (0.03, 0.85), "Kırmızı": (0.03, 0.80),
    "Haki": (0.03, 0.75), "Füme": (0.03, 0.85), "Mor": (0.02, 0.70), "Sarı": (0.02, 0.65),
    "Çok Renkli": (0.02, 0.75), "Antrasit": (0.03, 0.85), "Krem": (0.03, 0.85), "Lila": (0.02, 0.75),
    "Gümüş": (0.02, 0.80), "Açık Mavi": (0.03, 0.95), "Koyu Mavi": (0.02, 0.90),
}

STIL = ["Oversize", "Baggy", "Y2K", "Streetwear", "Gothic", "Harajuku", "Vintage", "Basic", "Crop",
        "Yüksek Bel", "Bol Kesim", "Slim Fit", "Unisex", "Retro", "Grunge", "Kolej", "Minimal",
        "Premium", "Loose Fit", "Wide Leg"]
OZELLIK = {
    "Eşofman Altı": ["Çift Çizgili", "Paraşüt", "Kargo Cepli", "Örme", "Şardonlu", "Lastik Paçalı", "Yan Şeritli", "Yıldız Baskılı"],
    "Kemer": ["Kuşgözü", "Zımbalı", "Çift Sıra Kuşgözlü", "Zincirli", "Metal Tokalı", "Halkalı", "Perçinli"],
    "Şort & Bermuda": ["Kot", "Yırtık Detaylı", "Kargo Cepli", "Paraşüt", "Denim", "Kemerli"],
    "Bluz": ["Dantel Detaylı", "Fırfırlı", "Bağcıklı", "Kare Yaka", "Askılı", "Fiyonklu", "Balon Kollu"],
    "Spor T-Shirt": ["Forma Detaylı", "Nefes Alan", "Numara Baskılı", "File", "Çizgili"],
    "T-Shirt": ["Baskılı", "Yıkamalı", "Anime Baskılı", "Nakışlı", "Pamuklu", "Grafik Baskılı"],
    "Body": ["Kare Yaka", "Uzun Kollu", "Askılı", "Fitilli", "Halter Yaka", "Dekolteli"],
    "Alt - Üst Takım": ["Eşofman", "Kadife", "Şardonlu", "Çizgili", "Fermuarlı"],
    "Jeans": ["Mom Fit", "Yırtık", "Taşlamalı", "Kargo", "Bol Paça", "Düz Kesim"],
    "Pantolon": ["Kumaş", "Kargo", "Paraşüt", "Palazzo", "Pileli", "Keten Görünümlü"],
    "Ceket": ["Fermuarlı", "Nakış Şerit Detaylı", "Varsity", "Bomber", "Kot", "Suni Deri"],
    "Sweatshirt": ["Kapüşonlu", "Baskılı", "Fermuarlı", "Yarım Fermuarlı", "Nakışlı"],
    "Hırka": ["Örgü", "Triko", "Düğmeli", "Tüylü"],
    "Etek": ["Pileli", "Mini", "Kot", "Tül", "Kargo Cepli"],
    "Gömlek": ["Çizgili", "Ekose", "Saten", "Cepli"],
    "Spor Eşofman Takımı": ["Çift Çizgili", "Fermuarlı", "Şeritli", "Kapüşonlu"],
    "Oxford Ayakkabı": ["Kalın Taban", "Rugan", "Tokalı", "Bağcıklı", "Loafer"],
    "Kar Botu": ["Kürklü", "Su Geçirmez", "Bağcıklı", "Kalın Taban"],
    "Sneaker": ["Kalın Taban", "Deri", "Süet Detaylı", "Platform"],
    "Yağmurluk & Rüzgarlık": ["Kapüşonlu", "Su İtici", "Fermuarlı", "Parçalı"],
    "Pijama Altı": ["Ekose", "Pamuklu", "Desenli", "Polar"],
    "Çorap": ["Desenli", "Kolej", "Soket", "Çizgili"],
}
ISIM = {
    "Şort & Bermuda": "Şort", "Spor T-Shirt": "Spor Tişört", "T-Shirt": "Tişört",
    "Alt - Üst Takım": "Alt Üst Takım", "Jeans": "Jean", "Spor Eşofman Takımı": "Eşofman Takımı",
    "Yağmurluk & Rüzgarlık": "Yağmurluk", "Çorap": "Çorap Seti",
}
KUMASLAR = {
    "Kemer": ["suni deri", "hakiki deri"],
    "Oxford Ayakkabı": ["suni deri", "rugan"], "Kar Botu": ["su geçirmez suni deri, içi kürklü"],
    "Sneaker": ["suni deri", "süet ve file"],
    "Jeans": ["%98 pamuk %2 elastan denim", "%100 pamuk denim"],
    "Şort & Bermuda": ["%98 pamuk %2 elastan denim", "%100 pamuk denim"],
    "Yağmurluk & Rüzgarlık": ["%100 polyester su itici kumaş"],
}
VARSAYILAN_KUMAS = ["%100 pamuk", "%70 pamuk %30 polyester", "%95 pamuk %5 elastan",
                    "%65 polyester %35 viskon", "%100 polyester", "%50 pamuk %50 polyester"]

# Birlikte alınan tamamlayıcı kategoriler
TAMAMLAYICI = {
    "Eşofman Altı": ["Spor T-Shirt", "T-Shirt", "Sweatshirt", "Kemer"],
    "Kemer": ["Jeans", "Pantolon", "Şort & Bermuda", "Eşofman Altı"],
    "Şort & Bermuda": ["Kemer", "Bluz", "T-Shirt"],
    "Bluz": ["Şort & Bermuda", "Etek", "Jeans", "Pantolon"],
    "Spor T-Shirt": ["Eşofman Altı", "Şort & Bermuda"],
    "T-Shirt": ["Eşofman Altı", "Şort & Bermuda", "Jeans"],
    "Body": ["Jeans", "Etek", "Pantolon", "Kemer"],
    "Jeans": ["Kemer", "Bluz", "Body", "T-Shirt"],
    "Pantolon": ["Kemer", "Bluz", "Gömlek"],
    "Ceket": ["Jeans", "Sweatshirt", "Eşofman Altı"],
    "Sweatshirt": ["Eşofman Altı", "Jeans"],
    "Etek": ["Bluz", "Body", "Oxford Ayakkabı"],
    "Oxford Ayakkabı": ["Etek", "Çorap", "Pantolon"],
    "Kar Botu": ["Çorap", "Ceket"],
}

# Gerçek siparişlerdeki il payları (ilk 30) + kalan iller
SEHIRLER = {
    "İstanbul": .194, "Ankara": .089, "İzmir": .064, "Antalya": .059, "Kocaeli": .031, "Bursa": .028,
    "Konya": .027, "Muğla": .025, "Mersin": .024, "Adana": .023, "Diyarbakır": .019, "Kayseri": .018,
    "Aydın": .017, "Balıkesir": .017, "Gaziantep": .016, "Hatay": .015, "Tekirdağ": .014, "Samsun": .014,
    "Sakarya": .013, "Trabzon": .012, "Kahramanmaraş": .012, "Eskişehir": .011, "Manisa": .011,
    "Denizli": .010, "Mardin": .010, "Elazığ": .009, "Çanakkale": .009, "Malatya": .008,
    "Zonguldak": .008, "Şanlıurfa": .008,
}
for _il in ["Afyonkarahisar", "Van", "Ordu", "Batman", "Sivas", "Tokat", "Nevşehir", "Erzurum", "Edirne",
            "Aksaray", "Isparta", "Bolu", "Kırıkkale", "Rize", "Şırnak", "Kastamonu", "Adıyaman", "Burdur",
            "Uşak", "Kütahya", "Yalova", "Düzce", "Bitlis", "Ağrı", "Kırklareli", "Niğde", "Kars", "Karabük",
            "Yozgat", "Artvin", "Osmaniye", "Karaman", "Çorum", "Bayburt", "Sinop", "Tunceli", "Ardahan",
            "Iğdır", "Siirt", "Erzincan", "Amasya", "Giresun", "Gümüşhane", "Bilecik", "Hakkari", "Kırşehir",
            "Bartın", "Bingöl", "Kilis", "Muş", "Çankırı"]:
    SEHIRLER[_il] = 0.004
ILCELER = {
    "İstanbul": ["Esenyurt", "Küçükçekmece", "Pendik", "Ümraniye", "Bağcılar", "Bahçelievler", "Kadıköy",
                 "Üsküdar", "Kartal", "Maltepe", "Ataşehir", "Beylikdüzü", "Başakşehir", "Sultangazi",
                 "Esenler", "Kağıthane", "Şişli", "Beşiktaş", "Fatih", "Sarıyer", "Avcılar", "Tuzla"],
    "Ankara": ["Çankaya", "Keçiören", "Yenimahalle", "Mamak", "Etimesgut", "Sincan", "Altındağ", "Gölbaşı"],
    "İzmir": ["Karşıyaka", "Bornova", "Buca", "Konak", "Çiğli", "Bayraklı", "Karabağlar", "Menemen"],
    "Antalya": ["Muratpaşa", "Kepez", "Konyaaltı", "Alanya", "Manavgat"],
    "Bursa": ["Osmangazi", "Nilüfer", "Yıldırım", "İnegöl"],
    "Kocaeli": ["İzmit", "Gebze", "Darıca", "Körfez", "Gölcük"],
    "Konya": ["Selçuklu", "Meram", "Karatay"],
    "Adana": ["Seyhan", "Çukurova", "Yüreğir"],
    "Mersin": ["Yenişehir", "Mezitli", "Toroslar", "Tarsus"],
    "Gaziantep": ["Şahinbey", "Şehitkamil"],
}
UZAK_ILLER = {"Van", "Hakkari", "Şırnak", "Ağrı", "Kars", "Ardahan", "Iğdır", "Muş", "Bitlis", "Siirt",
              "Batman", "Mardin", "Diyarbakır", "Şanlıurfa", "Bingöl", "Tunceli", "Erzurum", "Erzincan",
              "Bayburt", "Gümüşhane", "Artvin", "Rize", "Trabzon", "Hatay", "Kilis", "Adıyaman",
              "Malatya", "Elazığ"}

# Gerçek siparişlerin saat dağılımı (00..23)
SAAT = np.array([258, 231, 147, 111, 71, 36, 25, 12, 17, 28, 42, 81, 110, 134, 167, 180, 179, 184,
                 174, 206, 205, 225, 251, 265], float)
SAAT /= SAAT.sum()
HAFTA_GUNU = np.array([1.12, 1.02, 1.10, 1.08, 0.85, 0.93, 0.96])

KARGO = {"Trendyol Express": .907, "Sürat Kargo": .074, "DHL eCommerce": .018, "Aras Kargo": .001}
HIZLI = {"FastDelivery": .875, "SameDayShipping": .028, "Yok": .097}
# Trendyol ~8 haftadan eski siparişlerde ödeme yöntemini gizliyor (gerçek veride boş geliyor)
ODEME = {"Banka Kartı": .50, "Kredi Kartı": .499, "Alışveriş Kredisi": .001}
ODEME_GIZLI_SINIR = pd.Timestamp(BITIS) - pd.Timedelta(days=55)
PLATFORM = {"android": .52, "ios": .36, "web": .07, "mweb": .05}

# Kargo desisi (kategori başına tipik) ve 1 desi kargo tarifesinin zamanla artışı (gerçek faturalardan)
DESI = {"Kemer": 1, "Çorap": 1, "T-Shirt": 1, "Spor T-Shirt": 1, "Body": 1, "Bluz": 1, "Etek": 1, "Gömlek": 1,
        "Pijama Altı": 1, "Şort & Bermuda": 1, "Eşofman Altı": 2, "Pantolon": 2, "Jeans": 2, "Sweatshirt": 2,
        "Hırka": 2, "Alt - Üst Takım": 2, "Spor Eşofman Takımı": 2, "Ceket": 3, "Yağmurluk & Rüzgarlık": 2,
        "Oxford Ayakkabı": 3, "Sneaker": 3, "Kar Botu": 4}
DESI_CARPANI = {0: 1.0, 1: 1.0, 2: 0.93, 3: 1.21, 4: 1.30, 5: 1.39, 6: 1.35}
KARGO_TARIFE = [("2024-01-01", 58.40), ("2025-02-01", 66.10), ("2025-09-01", 73.25), ("2026-02-01", 93.05),
                ("2026-09-01", 98.34)]
IADE_KARGO_CARPANI = 1.16      # iade kargosu ~108 TL (gönderiden biraz pahalı)
PLATFORM_BEDELI = [("2024-01-01", 7.5), ("2025-06-01", 10.0), ("2026-01-01", 13.0)]  # gönderi başına


def tarifeden(tarife, zaman):
    deger = tarife[0][1]
    for bas, d in tarife:
        if zaman >= pd.Timestamp(bas):
            deger = d
    return deger


def sec(sozluk, n=None):
    anahtarlar = list(sozluk)
    p = np.array(list(sozluk.values()), float)
    i = rng.choice(len(anahtarlar), size=n, p=p / p.sum())
    return anahtarlar[i] if n is None else [anahtarlar[j] for j in i]


def guzel_fiyat(x):
    """Fiyatı 549, 699, 1.299 gibi mağaza fiyatına yuvarlar."""
    return max(49.0, round(x / 50) * 50 - 1)


def ozet_id(on_ek, n):
    return "M" + hashlib.sha256(f"{on_ek}{n}".encode()).hexdigest()[:10]


GUNLER = pd.date_range(BASLANGIC, BITIS.date(), freq="D")
D = len(GUNLER)


def gun_no(tarih):
    return (pd.Timestamp(tarih).normalize() - GUNLER[0]).days


# ====================================================
# 3) ÜRÜN KATALOĞU
# ====================================================

def lansman_tarihi(mevsim):
    if rng.random() < 0.55:
        return BASLANGIC - timedelta(int(rng.integers(30, 700)))
    if mevsim == "tum":
        return BASLANGIC + timedelta(int(rng.integers(0, D - 20)))
    # Mevsimlik ürün sezondan önce eklenir (yazlık mart, kışlık ağustos ortasından itibaren)
    adaylar = [date(y, 3, 1) if mevsim == "yaz" else date(y, 8, 15) for y in (2025, 2026)]
    adaylar = [a for a in adaylar if a + timedelta(60) < BITIS.date()]
    bas = adaylar[rng.integers(len(adaylar))]
    return bas + timedelta(int(rng.integers(0, 75)))


modeller, icerikler, varyantlar = [], [], []
kullanilan_adlar = set()
urun_kodu = iter(rng.choice(np.arange(1_100_000_000, 1_800_000_000), 6000, replace=False))
icerik_kodu = iter(rng.choice(np.arange(800_000_000, 1_250_000_000), 1500, replace=False))

for k in KAT.values():
    for i in range(k["model_sayisi"]):
        while True:
            ad = f"{rng.choice(STIL)} {rng.choice(OZELLIK[k['ad']])} {ISIM.get(k['ad'], k['ad'])}"
            if ad not in kullanilan_adlar:
                break
        kullanilan_adlar.add(ad)
        lansman = lansman_tarihi(k["mevsim"])
        lo, hi = k["fiyat"]
        m = {
            "m": len(modeller),
            "model_kodu": f"{k['kod']}{i + 1:02d}",
            "ad": ad,
            "kategori": k["ad"],
            "lansman": lansman,
            "populerlik": rng.lognormal(0, 0.8),
            "kalite": rng.beta(6, 2.2),
            "kalip": rng.choice([-1, 0, 1], p=[0.2, 0.65, 0.15]) if k["beden_seti"] not in ("kemer", "corap") else 0,
            "kumas": rng.choice(KUMASLAR.get(k["ad"], VARSAYILAN_KUMAS)),
            "fiyat": guzel_fiyat(rng.uniform(lo, hi)),
            "elastisite": rng.uniform(1.2, 2.2),
            "arsiv": None,
        }
        # Eski ve az satan modeller arşive alınır
        yas = (BITIS.date() - lansman).days
        if yas > 400 and (m["populerlik"] < 0.8 or m["kalite"] < 0.55) and rng.random() < 0.35:
            m["arsiv"] = lansman + timedelta(int(rng.integers(200, yas - 20)))
        modeller.append(m)

        renk_sayisi = int(np.clip(1 + rng.poisson(2.8), 1, 10))
        agirlik = np.array([v[0] for v in RENKLER.values()])
        secilen = rng.choice(list(RENKLER), size=min(renk_sayisi, len(RENKLER)), replace=False,
                             p=agirlik / agirlik.sum())
        payi = np.array([RENKLER[r][1] for r in secilen]) * rng.lognormal(0, 0.35, len(secilen))
        payi = payi / payi.sum() * (1 + 0.15 * (len(secilen) - 1))
        for renk, pay in zip(secilen, payi):
            c = {"c": len(icerikler), "m": m["m"], "icerik_id": int(next(icerik_kodu)), "renk": renk, "pay": pay}
            bedenler = list(BEDEN_SETLERI[k["beden_seti"]])
            if len(bedenler) > 3 and rng.random() < 0.2:
                bedenler = bedenler[1:] if rng.random() < 0.5 else bedenler[:-1]
            c["bedenler"] = bedenler
            icerikler.append(c)
            for b in bedenler:
                varyantlar.append({"c": c["c"], "beden": b, "barkod": f"DMO{len(varyantlar) + 10_000_001}",
                                   "urun_kodu": int(next(urun_kodu))})

M, C = len(modeller), len(icerikler)
c_model = np.array([c["m"] for c in icerikler])
barkod_bul = {(v["c"], v["beden"]): v for v in varyantlar}
print(f"Katalog: {M} model, {C} renk (ürün sayfası), {len(varyantlar)} varyant")

# ====================================================
# 4) FİYAT GEÇMİŞİ, KUPONLAR, TALEP
# ====================================================

# Enflasyon: fiyat geriye doğru her 3-5 ayda bir %6-15 düşürülerek kurulur
FIYAT = np.zeros((M, D))
for m in modeller:
    fiyat, gun = m["fiyat"], D
    while gun > 0:
        bas = max(0, gun - int(rng.integers(90, 160)))
        FIYAT[m["m"], bas:gun] = fiyat
        fiyat = guzel_fiyat(fiyat / (1 + rng.uniform(0.06, 0.15)))
        gun = bas

# Ürüne özel kupon dönemleri (indirim oranı)
KUPON = np.zeros((M, D))
for m in range(M):
    gun = int(rng.integers(0, 40))
    while gun < D:
        sure = int(rng.integers(4, 15))
        KUPON[m, gun:gun + sure] = rng.choice([0.04, 0.06, 0.08, 0.10, 0.12])
        gun += sure + int(rng.exponential(25))

takvim = ozel_gunler(BASLANGIC, BITIS.date())
OZEL = np.array([takvim.get(g.date(), ("", 1.0))[1] for g in GUNLER])
OZEL_AD = [takvim.get(g.date(), ("", 1.0))[0] for g in GUNLER]
# Kampanya günlerinde mağaza geneli sepet indirimi
SEPET = np.array([0.10 if a in ("11.11", "Black Friday") else 0.05 if a == "Efsane Kasım" else 0.0 for a in OZEL_AD])

doy = GUNLER.dayofyear.values
ay_ortasi = np.array([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349])
mevsim = {ad: np.interp(doy, np.r_[ay_ortasi - 365, ay_ortasi, ay_ortasi + 365], np.tile(v, 3))
          for ad, v in MEVSIM.items()}
trend = 0.45 + 0.55 * (np.arange(D) / (D - 1)) ** 1.3
trend *= np.exp(np.cumsum(rng.normal(0, 0.015, D)) * 0.5)
maas = np.where(np.isin(GUNLER.day, [1, 2, 15, 16]), 1.06, 1.0)
gunluk = trend * HAFTA_GUNU[GUNLER.dayofweek] * OZEL * maas

# Reklam bakiyesi alımları (çoğunlukla çarşamba, mağaza büyüdükçe sıklaşır, kampanya öncesi iki katı).
# Harcanan tutar sonraki 7 günde talebi artırır -> reklam getirisi (ROAS) analiz edilebilir.
REKLAM = np.zeros(D)
for gun in range(D):
    if GUNLER[gun].dayofweek == 2 and rng.random() < 0.3 + 0.6 * gun / D:
        REKLAM[gun] = rng.choice([500, 500, 1000, 1000, 1500, 3000]) * (2 if OZEL[min(gun + 5, D - 1)] > 1.3 else 1)
reklam_7g = np.convolve(REKLAM, np.ones(7))[:D]
gunluk *= 1 + 0.06 * (reklam_7g / 1000) ** 0.8

kategori_ort_fiyat = {k: np.mean([m["fiyat"] for m in modeller if m["kategori"] == k]) for k in KAT}
TALEP = np.zeros((C, D))
gun_index = np.arange(D)
for c in icerikler:
    m = modeller[c["m"]]
    k = KAT[m["kategori"]]
    agirlik = (k["talep"] / k["model_sayisi"] * m["populerlik"] * c["pay"]
               * (0.5 + m["kalite"]) * (m["fiyat"] / kategori_ort_fiyat[m["kategori"]]) ** -1.0)
    yas = gun_index - gun_no(m["lansman"])
    omur = np.where(yas < 0, 0, (1 - np.exp(-(yas + 1) / 12)) * np.exp(-np.maximum(yas - 300, 0) / 500))
    if m["arsiv"]:
        omur[gun_index >= gun_no(m["arsiv"])] = 0
    indirim = (1 - KUPON[m["m"]]) * (1 - SEPET)
    TALEP[c["c"]] = agirlik * mevsim[k["mevsim"]] * omur * indirim ** -m["elastisite"]

kategori_sok = {k: rng.lognormal(0, 0.15, D) for k in KAT}
for c in icerikler:
    TALEP[c["c"]] *= gunluk * kategori_sok[modeller[c["m"]]["kategori"]]
TALEP[:, -1] *= SAAT[:BITIS.hour].sum()   # son gün yarım
TALEP *= HEDEF_GUNLUK_SATIR / 1.1 / (TALEP[:, -90:].sum() / 90)

adet_matrisi = rng.poisson(TALEP)
print(f"Birincil satış adedi: {adet_matrisi.sum():,}")

# ====================================================
# 5) MÜŞTERİLER VE SİPARİŞLER
# ====================================================

musteriler = []          # dict listesi
kategori_alicilari = {k: [] for k in KAT}
son_alicilar = []


def yeni_musteri():
    erkek = rng.random() < 0.15
    boy = float(np.clip(rng.normal(177, 7) if erkek else rng.normal(163.5, 6), 145, 198))
    kilo = float(np.clip(rng.normal(78, 12) if erkek else rng.lognormal(np.log(60), 0.17), 38, 130))
    sehir = sec(SEHIRLER)
    mu = {
        "i": len(musteriler),
        "musteri_id": ozet_id("sahte-musteri", len(musteriler)),
        "sehir": sehir,
        "ilce": rng.choice(ILCELER[sehir]) if sehir in ILCELER else "Merkez",
        "boy": round(boy), "kilo": round(kilo),
        "ayak": int(np.clip(round(36 + (boy - 152) / 5 + rng.normal(0, 0.6)), 35, 44)),
    }
    musteriler.append(mu)
    return mu


def ideal_konum(mu, beden_seti):
    """Müşterinin bu beden setindeki ideal konumu (set dışına taşabilir)."""
    bedenler = BEDEN_SETLERI[beden_seti]
    skor = mu["kilo"] + (mu["boy"] - 165) * 0.35
    if beden_seti == "ayakkabi":
        return mu["ayak"] - 36
    if beden_seti == "jean":
        return round((skor - 46) / 3.2)
    if beden_seti in ("kemer", "corap"):
        return 0
    harf = int(np.searchsorted([44, 49, 55, 62, 70, 79, 88], skor))
    return harf - HARFLER.index(bedenler[0])


def beden_sec(mu, c):
    """(seçilen beden, uyum) döndürür. uyum < 0 dar, > 0 bol."""
    m = modeller[c["m"]]
    seti = KAT[m["kategori"]]["beden_seti"]
    tam = BEDEN_SETLERI[seti]
    ideal = ideal_konum(mu, seti)
    secim = ideal + (rng.choice([0, 1, -1], p=[0.75, 0.15, 0.10]) if len(tam) > 1 else 0)
    mevcut = [tam.index(b) for b in c["bedenler"]]
    secim = min(mevcut, key=lambda x: abs(x - secim))
    return tam[secim], (secim - ideal + m["kalip"]) if len(tam) > 1 else 0


def tamamlayici_sec(c, gun):
    m = modeller[c["m"]]
    if rng.random() < 0.45 and m["kategori"] not in ("Kemer", "Çorap"):
        adaylar = [x for x in range(C) if c_model[x] == m["m"] and x != c["c"]]
    else:
        hedef = rng.choice(TAMAMLAYICI.get(m["kategori"], ["Kemer", "T-Shirt"]))
        adaylar = [x for x in range(C) if modeller[c_model[x]]["kategori"] == hedef]
    if not adaylar:
        return None
    p = TALEP[adaylar, gun]
    if p.sum() == 0:
        return None
    return icerikler[rng.choice(adaylar, p=p / p.sum())]


def saat_sec(gun):
    t = GUNLER[gun] + pd.Timedelta(hours=int(rng.choice(24, p=SAAT)), seconds=int(rng.integers(3600)))
    if t >= BITIS:
        t = GUNLER[gun] + pd.Timedelta(seconds=int(rng.integers(BITIS.hour * 3600)))
    return t


def is_saatine(t, en_erken=9):
    """Gece/pazar gelen işi bir sonraki iş saati başına öteler."""
    if t.dayofweek == 6:
        t = (t + pd.Timedelta(days=1)).normalize() + pd.Timedelta(hours=en_erken)
    elif t.hour < en_erken:
        t = t.normalize() + pd.Timedelta(hours=en_erken)
    elif t.hour >= 18:
        t = (t + pd.Timedelta(days=1)).normalize() + pd.Timedelta(hours=en_erken)
        if t.dayofweek == 6:
            t += pd.Timedelta(days=1)
    return t


def saat(x):
    return pd.Timedelta(hours=float(x))


birincil = [(int(c), int(g)) for c, g in zip(*np.nonzero(adet_matrisi)) for _ in range(adet_matrisi[c, g])]
birincil = sorted(((saat_sec(g), c, g) for c, g in birincil), key=lambda x: x[0])

paketler, satirlar, gecmis, indirimler = [], [], [], []
siparis_no = 10_480_000_000
paket_id = 2_910_000_000
satir_id = 4_870_000_000
kalem_id = 5_310_000_000

for t, c, gun in birincil:
    # --- Müşteri: tekrar alan müşteri aynı kategoriden almaya yatkın
    kategori = modeller[icerikler[c]["m"]]["kategori"]
    if musteriler and rng.random() < 0.13:
        r = rng.random()
        if r < 0.45 and kategori_alicilari[kategori]:
            havuz = kategori_alicilari[kategori]
        elif r < 0.8:
            havuz = son_alicilar[-1500:]   # yakın zamanda alan müşteri tekrar gelir
        else:
            havuz = range(len(musteriler))
        mu = musteriler[rng.choice(havuz)]
    else:
        mu = yeni_musteri()
    son_alicilar.append(mu["i"])

    # --- Sepet
    sepet = [icerikler[c]]
    while len(sepet) < 4 and rng.random() < (0.075 if len(sepet) == 1 else 0.12):
        ek = tamamlayici_sec(sepet[0], gun)
        if ek is None:
            break
        sepet.append(ek)

    siparis_no += int(rng.integers(20_000, 130_000))
    paket_id += int(rng.integers(40_000, 130_000))
    pid = paket_id

    kalemler = []
    for ic in sepet:
        m = modeller[ic["m"]]
        beden, uyum = beden_sec(mu, ic)
        v = barkod_bul[(ic["c"], beden)]
        kalemler.append({"ic": ic, "m": m, "v": v, "beden": beden, "uyum": uyum,
                         "adet": 2 if rng.random() < 0.007 else 1,
                         "fiyat": FIYAT[m["m"], gun]})
        kategori_alicilari[m["kategori"]].append(mu["i"])

    # --- İndirimler (paket düzeyinde, gerçekteki adlarla)
    brut = sum(k["fiyat"] * k["adet"] for k in kalemler)
    toplam_adet = sum(k["adet"] for k in kalemler)
    ind = []
    kupon = sum(round(KUPON[k["m"]["m"], gun] * k["fiyat"] / 10) * 10 * k["adet"] for k in kalemler)
    if kupon > 0:
        ind.append((f"{MAGAZA} - Ürüne Özel Kupon 🏷️", kupon))
    if SEPET[gun] > 0:
        ind.append((f"Sepette %{int(SEPET[gun] * 100)} İndirim", brut * SEPET[gun]))
    olasi = [
        (0.43, True, "Sepette %1 İndirim", brut * 0.01),
        (0.15, True, "Sepette %2 İndirim", brut * 0.02),
        (0.06, True, "Sepette %5 İndirim", brut * 0.05),
        (0.04, True, "Sepette %10 İndirim", brut * 0.10),
        (0.30, brut >= 500, "500 TL'ye 10 TL İndirim", 10),
        (0.08, brut >= 400, "400 TL'ye %1 İndirim", brut * 0.01),
        (0.35, brut >= 1200, "1.200 TL'ye %3 İndirim", brut * 0.03),
        (0.35, True, "Trendyol Plus'a Özel Fiyat", brut * rng.uniform(0.05, 0.10)),
        (0.11, True, f"{MAGAZA} - Sepetine Özel Kupon! 🛍️", 30),
        (0.085, True, f"{MAGAZA} - Takip Et Kazan", 30),
        (0.08, True, f"{MAGAZA} Ürününe Göz Attın, Şimdi Alma Zamanı! 👀", 50),
        (0.055, True, f"{MAGAZA} - Favorine Özel Kupon! 🧡", 40),
        (0.02, True, f"{MAGAZA} - Plus'a Özel Kupon 💎", 50),
        (0.50, toplam_adet >= 2, "2 Adet ve Üzeri %5 İndirim", brut * 0.05),
        (0.30, toplam_adet >= 2, "2. Ürüne %10 İndirim", min(k["fiyat"] for k in kalemler) * 0.10),
    ]
    for p, kosul, ad, tutar in olasi:
        if kosul and rng.random() < p:
            ind.append((ad, tutar))
    toplam_ind = sum(x[1] for x in ind)
    if toplam_ind > brut * 0.4:   # aşırı indirimi sınırla
        ind = [(a, x * brut * 0.4 / toplam_ind) for a, x in ind]
        toplam_ind = brut * 0.4
    for ad, tutar in ind:
        indirimler.append({"paket_id": pid, "indirim_adi": ad, "indirim_turu": indirim_turu(ad),
                           "tutar": round(tutar, 2)})
    ty_ind = round(rng.uniform(1, 6), 2) if rng.random() < 0.0012 else 0.0
    # Finans kayıtlarında mağaza kuponları "Kupon", diğerleri "İndirim" olarak ayrı düşer
    kupon_ind = sum(x for a, x in ind if indirim_turu(a) == "magaza_kuponu")

    # --- Durum geçmişi
    kalite = np.mean([k["m"]["kalite"] for k in kalemler])
    olaylar = [("Awaiting", t), ("Created", t + pd.Timedelta(seconds=int(rng.integers(1, 5))))]
    hizli = sec(HIZLI)
    kargo = sec(KARGO)
    if rng.random() < 0.018 + 0.04 * (1 - kalite):
        if rng.random() < 0.5:
            olaylar.append(("Picking", is_saatine(t) + saat(rng.lognormal(0.3, 0.8))))
        olaylar.append(("Cancelled", olaylar[-1][1] + saat(rng.lognormal(1.0, 1.0))))
    else:
        toplama = is_saatine(t) + saat(rng.lognormal(0.3, 0.8))
        son_saat = 14 if hizli == "SameDayShipping" else 16
        cikis = toplama.normalize() + pd.Timedelta(hours=17, minutes=int(rng.integers(150)))
        if toplama.hour >= son_saat:
            cikis += pd.Timedelta(days=1)
        if cikis.dayofweek == 6:
            cikis += pd.Timedelta(days=1)
        sure = rng.lognormal(np.log(42), 0.35) * (1.4 if mu["sehir"] in UZAK_ILLER else 1.0)
        sure *= {"Sürat Kargo": 1.25, "DHL eCommerce": 1.1}.get(kargo, 1.0)
        olaylar += [("Picking", toplama), ("Shipped", cikis)]
        teslim = cikis + saat(max(sure, 8))
        if rng.random() < 0.042:
            olaylar.append(("UnDelivered", cikis + saat(max(sure * 0.8, 6))))
            if rng.random() < 0.065:
                olaylar.append(("Returned", olaylar[-1][1] + saat(rng.uniform(48, 120))))
                teslim = None
            else:
                teslim += saat(rng.uniform(20, 60))
        if teslim is not None:
            olaylar.append(("Delivered", teslim))

    olaylar = [(d, z) for d, z in olaylar if z <= BITIS]
    son = olaylar[-1][0]
    paket_durumu = {"Awaiting": "ReadyToShip", "Created": "ReadyToShip", "Picking": "ReadyToShip",
                    "Shipped": "Shipped", "UnDelivered": "Shipped", "Delivered": "Delivered",
                    "Cancelled": "Cancelled", "Returned": "UnDeliveredAndReturned"}[son]
    zaman = dict((d, z) for d, z in olaylar)
    for d, z in olaylar:
        gecmis.append({"paket_id": pid, "durum": d, "tarih": z})

    # --- Satırlar: paket indirimi brüt tutara göre dağıtılır
    net_toplam = 0.0
    for k in kalemler:
        satir_id += int(rng.integers(30_000, 110_000))
        pay = k["fiyat"] * k["adet"] / brut
        birim_ind = round(toplam_ind * pay / k["adet"], 2)
        birim_ty = round(ty_ind * pay / k["adet"], 2)
        birim_net = round(k["fiyat"] - birim_ind - birim_ty, 2)
        birim_kupon = min(round(kupon_ind * pay / k["adet"], 2), birim_ind)
        kalem_ids = list(range(kalem_id + 1, kalem_id + 1 + k["adet"]))
        kalem_id += k["adet"] + int(rng.integers(0, 3))
        net_toplam += birim_net * k["adet"]
        satirlar.append({
            "satir_id": satir_id, "paket_id": pid, "barkod": k["v"]["barkod"], "urun_kodu": k["v"]["urun_kodu"],
            "adet": k["adet"], "beden": k["beden"], "renk": k["ic"]["renk"],
            "birim_brut_fiyat": k["fiyat"], "birim_satici_indirimi": birim_ind,
            "birim_trendyol_indirimi": birim_ty, "birim_net_fiyat": birim_net,
            "satir_net_tutar": round(birim_net * k["adet"], 2),
            "komisyon_orani": KAT[k["m"]["kategori"]]["komisyon"], "kdv_orani": 10.0,
            "is_birimi": KAT[k["m"]["kategori"]]["is_birimi"], "satir_durumu": paket_durumu,
            # yorum üretimi için gizli alanlar (kaydedilmez)
            "g_icerik": k["ic"]["c"], "g_model": k["m"]["m"], "g_uyum": k["uyum"], "g_musteri": mu["i"],
            # defolu / yanlış ürün: kalitesi düşük üründe daha sık
            "g_sorun": rng.random() < 0.035 * (1.6 - k["m"]["kalite"]),
            "g_kupon": birim_kupon, "g_kalemler": kalem_ids, "g_desi": DESI.get(k["m"]["kategori"], 1),
        })

    paketler.append({
        "paket_id": pid, "siparis_no": siparis_no, "musteri_id": mu["musteri_id"], "siparis_tarihi": t,
        "sehir": mu["sehir"], "ilce": mu["ilce"], "odeme_yontemi": sec(ODEME) if t >= ODEME_GIZLI_SINIR else None, "kargo_firmasi": kargo,
        "hizli_teslimat": hizli, "paket_durumu": paket_durumu,
        "brut_tutar": round(brut, 2), "satici_indirimi": round(toplam_ind, 2), "trendyol_indirimi": ty_ind,
        "net_tutar": round(net_toplam, 2),
        "tahmini_teslim_bas": t + pd.Timedelta(days=1),
        "tahmini_teslim_bit": t + pd.Timedelta(days=int(rng.integers(2, 4))),
        "kargoya_verilis_tarihi": zaman.get("Shipped"), "teslim_tarihi": zaman.get("Delivered"),
        "iptal": "Cancelled" in zaman, "teslim_edilemedi": "UnDelivered" in zaman, "iade_dondu": "Returned" in zaman,
    })

siparisler = pd.DataFrame(paketler)
satirlar = pd.DataFrame(satirlar)
print(f"Siparişler: {len(siparisler):,} paket, {len(satirlar):,} satır, {len(musteriler):,} müşteri")

# ====================================================
# 6) METİN PARÇALARI
# ====================================================

ASCII = str.maketrans("ıİşŞğĞçÇöÖüÜ", "iIsSgGcCoOuU")


def gunluk_dil(metin):
    """Gerçek kullanıcı yazımına benzesin diye küçük harf / Türkçe karaktersiz yazım."""
    r = rng.random()
    if r < 0.15:
        metin = metin.lower().translate(ASCII)
    elif r < 0.55:
        metin = metin.lower()
    return metin


def parca(liste):
    return liste[rng.integers(len(liste))]


YORUM = {
    "iyi": ["ürün çok güzel", "kumaşı kaliteli", "fotoğraftaki gibi geldi", "rengi çok güzel",
            "fiyatına göre gayet iyi", "tam beklediğim gibi", "dikişleri sağlam", "kumaşı yumuşacık",
            "çok tatlı duruyor", "herkes nereden aldın diye soruyor", "görseldekinin aynısı",
            "kaliteli ve şık", "bayıldım", "ikinci rengini de alacağım", "çok rahat"],
    "orta": ["idare eder", "fiyatına göre normal", "beklediğim kadar kaliteli değil ama giyilir",
             "rengi fotoğraftan biraz farklı", "kumaşı biraz ince", "fena değil", "ortalama bir ürün"],
    "kotu": ["kumaşı çok kötü", "fotoğraftakiyle alakası yok", "tek yıkamada tüylendi",
             "dikişleri sökük geldi", "rengi soluk", "kalitesiz bir ürün", "parasına değmez",
             "defolu geldi", "iade edeceğim", "ipliği çıkmış geldi", "çok ince bir kumaş"],
    "dar": ["kalıbı dar, bir beden büyük alın", "bana dar geldi", "beli dar geldi",
            "bir beden büyük almanızı öneririm", "kalıbı küçük"],
    "bol": ["kalıbı bol, bir beden küçük alın", "biraz bol geldi", "beklediğimden bol",
            "bir beden küçük alabilirsiniz"],
    "tam": ["tam oturdu", "bedeni tam oldu", "kendi bedeninizi alın", "kalıbı tam"],
    "kargo_iyi": ["kargo çok hızlıydı", "ertesi gün elimdeydi", "paketleme özenliydi", "hızlı geldi"],
    "kargo_kotu": ["kargo geç geldi", "paket ezik geldi", "kargo çok gecikti"],
    "sorun": ["defolu geldi", "yanlış renk gönderilmiş", "ürün eksik geldi", "lekeli geldi",
              "görseldeki ürün gelmedi", "fermuarı bozuk geldi", "yırtık geldi"],
    "acilis": ["", "", "", "merhaba ", "aldım ", "kızıma aldım ", "kendime aldım ", "ikinci kez alıyorum ",
               "eşime aldım ", "yorumlara güvenip aldım "],
    "kapanis_iyi": ["", "", "", " tavsiye ederim", " teşekkürler", " herkese öneririm", " 👍", " ❤️"],
    "kapanis_kotu": ["", "", "", " bir daha almam", " pişman oldum", " iade ettim", " hiç memnun kalmadım"],
}


def urun_yorumu(puan, uyum, hizli_geldi, bedenli, sorun):
    kalite = "iyi" if puan >= 4 else "orta" if puan == 3 else "kotu"
    cumle = [parca(YORUM["sorun"])] if sorun else []
    cumle += list(rng.choice(YORUM[kalite], size=2 if puan >= 4 and rng.random() < 0.3 else 1, replace=False))
    if bedenli and (uyum != 0 or rng.random() < 0.4):
        cumle.append(parca(YORUM["dar" if uyum < 0 else "bol" if uyum > 0 else "tam"]))
    if rng.random() < 0.3:
        cumle.append(parca(YORUM["kargo_iyi" if hizli_geldi else "kargo_kotu"]))
    kapanis = parca(YORUM["kapanis_iyi" if puan >= 3 else "kapanis_kotu"])
    return gunluk_dil(parca(YORUM["acilis"]) + rng.choice([", ", ". ", " "]).join(cumle) + kapanis)


SATICI_NEDEN = {
    "olumlu": ["DELIVERY_TIME_POSITIVE", "COMPLETE_DELIVERY_POSITIVE", "PRODUCT_QUALITY_POSITIVE",
               "MATCHING_PRODUCT_POSITIVE", "PRODUCT_PRICE_POSITIVE"],
    "olumsuz": ["MATCHING_PRODUCT_NEGATIVE", "PRODUCT_QUALITY_NEGATIVE", "DEFECTIVE_PRODUCT_NEGATIVE",
                "DELIVERY_TIME_NEGATIVE", "PRODUCT_PRICE_NEGATIVE", "COMPLETE_DELIVERY_NEGATIVE"],
}
KARGO_NEDEN = {
    "olumlu": ["DELIVERY_TIME_POSITIVE", "UNDAMAGED_DELIVERY_POSITIVE", "DELIVERY_INFO_POSITIVE",
               "COURIER_COMMUNICATION_POSITIVE"],
    "olumsuz": ["DELIVERY_TIME_NEGATIVE", "DELIVERY_TO_ADRESS_NEGATIVE", "UNDAMAGED_DELIVERY_NEGATIVE"],
}
SATICI_YORUM = {
    5: ["teslimat iyi ve hızlıydı", "satıcı çok ilgili teşekkürler", "her şey yolundaydı",
        "ürün eksiksiz ve hızlı geldi", "paketleme çok özenliydi", "güvenilir satıcı"],
    4: ["genel olarak memnunum", "ürün güzel kargo biraz geç geldi", "fiyat performans iyi"],
    3: ["idare eder", "ürün fotoğraftan biraz farklı", "kargo yavaştı"],
    2: ["beklediğim gibi değil", "ürün açıklamadaki gibi değil", "geç gönderildi"],
    1: ["ürünün görselle alakası yok", "defolu ürün gönderildi", "iletişime dönüş yok",
        "yanlış renk gönderilmiş", "kesinlikle tavsiye etmiyorum"],
}


def nedenler(puan, havuz):
    if rng.random() < 0.3:
        return None
    if puan >= 4:
        secim = rng.choice(havuz["olumlu"], size=int(rng.integers(1, 4)), replace=False)
    elif puan <= 2:
        secim = rng.choice(havuz["olumsuz"], size=int(rng.integers(1, 3)), replace=False)
    else:
        secim = [parca(havuz["olumlu"]), parca(havuz["olumsuz"])]
    return ", ".join(secim)


def puana_cevir(skor):
    return int(np.searchsorted([0.40, 0.47, 0.54, 0.62], skor) + 1)


# ====================================================
# 7) ÜRÜN VE SATICI YORUMLARI
# ====================================================

teslim = siparisler.set_index("paket_id")
teslim_suresi = (teslim.teslim_tarihi - teslim.kargoya_verilis_tarihi).dt.total_seconds() / 3600

urun_yorumlari = []
for s in satirlar[satirlar.satir_durumu == "Delivered"].itertuples():
    m = modeller[s.g_model]
    uyum, mu = s.g_uyum, musteriler[s.g_musteri]
    sure = teslim_suresi[s.paket_id]
    # Sorun yaşayan veya bedeni uymayan müşteri daha çok yorum yazar
    olasilik = 0.018 * (1.6 if uyum != 0 or m["kalite"] < 0.55 else 1.0) * (5 if s.g_sorun else 1)
    if rng.random() >= olasilik:
        continue
    zaman = teslim.at[s.paket_id, "teslim_tarihi"] + pd.Timedelta(days=float(np.clip(rng.lognormal(1.8, 0.8), 0.1, 60)))
    if zaman > BITIS:
        continue
    skor = m["kalite"] + rng.normal(0, 0.12) - 0.12 * abs(uyum) - (0.1 if sure > 72 else 0)
    puan = int(rng.choice([1, 2], p=[0.85, 0.15])) if s.g_sorun else puana_cevir(skor)
    seti = KAT[m["kategori"]]["beden_seti"]
    bedenli = seti not in ("kemer", "corap")
    olcu_paylasir = seti not in ("kemer", "corap", "ayakkabi") and rng.random() < 0.42
    urun_yorumlari.append({
        "yorum_id": 0, "icerik_id": icerikler[s.g_icerik]["icerik_id"], "yorum_tarihi": zaman.floor("min"),
        "puan": puan, "yorum": urun_yorumu(puan, uyum, sure < 48, bedenli, s.g_sorun), "beden": s.beden,
        "boy": mu["boy"] if olcu_paylasir else None, "kilo": mu["kilo"] if olcu_paylasir else None,
        "begeni": int(rng.geometric(0.5) - 1) if rng.random() < 0.15 else 0,
        "fotografli": bool(rng.random() < (0.30 if puan <= 2 else 0.17)),
    })
urun_yorumlari = pd.DataFrame(urun_yorumlari).sort_values("yorum_tarihi")
urun_yorumlari["yorum_id"] = 600_000_000 + np.cumsum(rng.integers(50_000, 150_000, len(urun_yorumlari)))
urun_yorumlari[["boy", "kilo"]] = urun_yorumlari[["boy", "kilo"]].astype("Int64")

satici_yorumlari = []
paket_kalite = satirlar.groupby("paket_id").g_model.agg(lambda x: np.mean([modeller[i]["kalite"] for i in x]))
paket_sorun = satirlar.groupby("paket_id").g_sorun.any()
for p in siparisler[siparisler.paket_durumu == "Delivered"].itertuples():
    sorun = paket_sorun[p.paket_id]
    if rng.random() >= 0.0065 * (8 if sorun else 1):
        continue
    zaman = p.teslim_tarihi + pd.Timedelta(days=float(np.clip(rng.lognormal(1.0, 0.8), 0.05, 30)))
    if zaman > BITIS:
        continue
    sure = teslim_suresi[p.paket_id]
    satici = 1 if sorun and rng.random() < 0.85 else puana_cevir(paket_kalite[p.paket_id] + rng.normal(0, 0.22))
    kargo = int(np.clip(round(5.3 - max(sure - 30, 0) / 22 + rng.normal(0, 0.6)), 1, 5))
    satici_yorumlari.append({
        "yorum_id": 0, "yorum_tarihi": zaman.floor("min"), "satici_puani": satici, "kargo_puani": kargo,
        "yorum": gunluk_dil(parca(SATICI_YORUM[satici])),
        "satici_nedenleri": nedenler(satici, SATICI_NEDEN), "kargo_nedenleri": nedenler(kargo, KARGO_NEDEN),
        "platform": sec(PLATFORM),
    })
satici_yorumlari = pd.DataFrame(satici_yorumlari).sort_values("yorum_tarihi")
satici_yorumlari["yorum_id"] = 10_000_000_000 + np.cumsum(rng.integers(5_000_000, 20_000_000, len(satici_yorumlari)))

# ====================================================
# 8) MÜŞTERİ SORULARI
# ====================================================

SORU_KONU = {"beden": .80, "diger": .05, "kargo": .064, "renk": .039, "olcu": .035, "kumas": .033,
             "iade_degisim": .024, "stok": .013}
SORU = {
    "beden": ["{boy} boy {kilo} kilo hangi beden olur", "merhaba {boy} boyum {kilo} kiloyum hangi bedeni almalıyım",
              "1.{boy2} boy {kilo} kg hangi beden", "{boy}/{kilo} hangi beden önerirsiniz",
              "{kilo} kilo için {beden} olur mu", "boyum {boy} kilom {kilo} bol durmasını istiyorum hangi beden",
              "kalıbı dar mı {boy} {kilo} kg", "{boy} cm {kilo} kg tam olması için hangi beden",
              "merhabalar {boy} boy {kilo} kiloyum {beden} uygun mu"],
    "beden_ayakkabi": ["normalde {ayak} giyiyorum hangi numarayı almalıyım", "kalıbı dar mı ayağım geniş",
                       "{ayak} numara giyiyorum olur mu", "kalıbı standart mı"],
    "stok": ["{beden} beden ne zaman gelir", "{renk} rengi tekrar gelecek mi", "{beden} bedeni kalmamış stok gelecek mi"],
    "kargo": ["bugün sipariş versem ne zaman gelir", "ne zaman kargoya verilir", "siparişim ne zaman gelir",
              "kargo hangi firma ile gönderiliyor", "siparişim hala hazırlanıyor neden"],
    "kumas": ["kumaşı nedir", "terletir mi", "yıkayınca çeker mi", "kumaşı ince mi kalın mı", "esnek mi",
              "kışın giyilir mi", "tüylenme yapar mı"],
    "renk": ["rengi fotoğraftaki gibi mi", "{renk} rengi açık mı koyu mu", "görseldeki ürünün aynısı mı geliyor",
             "{renk} mi daha güzel siyah mı"],
    "olcu": ["{beden} bedenin boyu kaç cm", "bel ölçüsü kaç cm", "paça genişliği ne kadar",
             "{beden} bedenin eni kaç cm", "mankenin üzerindeki kaç beden"],
    "iade_degisim": ["beden değişimi yapabiliyor muyuz", "ürün defolu geldi ne yapmalıyım",
                     "yanlış renk gönderilmiş değişim istiyorum", "iade nasıl yapılıyor"],
    "diger": ["hediye paketi yapıyor musunuz", "takım mı tek alt mı geliyor", "orijinal mi",
              "kombin önerir misiniz", "fatura çıkıyor mu", "içini gösterir mi", "ayarlanabilir mi"],
}
CEVAP = {
    "beden": "Değerli Müşterimiz, Vermiş olduğunuz bilgiler doğrultusunda sizin için {oneri} beden uygundur 🙏 Keyifli alışverişler dileriz 🤗",
    "beden_yok": "Değerli Müşterimiz, Vermiş olduğunuz bilgiler doğrultusunda sizin için {oneri} beden uygundur ama maalesef stoklarımızda mevcut değildir 🙏",
    "beden_ayakkabi": ["Kalıbı standarttır, kendi numaranızı alabilirsiniz efendim 🙏",
                       "Kalıbı biraz dardır, bir numara büyük almanızı öneririz efendim 🙏",
                       "Kalıbı biraz geniştir, kendi numaranız veya bir küçüğü uygundur efendim 🙏"],
    "stok": ["{beden} beden önümüzdeki hafta stoklarımıza eklenecektir efendim 🙏",
             "Maalesef bu ürünün yeni üretimi planlanmamaktadır efendim 🙏"],
    "kargo": ["Vereceğiniz siparişler yarın kargoya teslim edilecektir efendim 🤗",
              "Siparişleriniz 1-2 iş günü içinde kargoya verilmektedir efendim 🙏",
              "Trendyol Express ile gönderim yapılmaktadır efendim 🙏"],
    "kumas": "{kumas} kumaştan üretilmiştir efendim 🙏",
    "renk": ["Evet efendim 🙏 Birebir aynı ürün gönderilecektir 🤗", "{renk} rengi görseldeki gibidir efendim 🙏"],
    "olcu": ["{beden} beden ölçüleri ürün açıklamasındaki beden tablosunda yer almaktadır efendim 🙏",
             "Mankenin üzerindeki ürün S bedendir efendim 🙏"],
    "iade_degisim": ["Ürününüzü 15 gün içinde Trendyol üzerinden iade edip yeniden sipariş verebilirsiniz efendim 🙏",
                     "Yaşadığınız sorun için özür dileriz, iade talebi oluşturmanız yeterlidir efendim 🙏"],
    "diger": ["Evet efendim 🙏", "Hayır efendim 🙏", "Ürün açıklamasında detaylı bilgi yer almaktadır efendim 🙏"],
}

# Soru sayısı model talebiyle orantılı; yeni ve kalıbı sorunlu ürüne daha çok soru gelir
model_talep = np.zeros((M, D))
np.add.at(model_talep, c_model, TALEP)
sorular = []
for m in modeller:
    yas = gun_index - gun_no(m["lansman"])
    carpan = 0.17 * np.where(yas < 30, 1.5, 1.0) * (1.3 if m["kalip"] != 0 else 1.0)
    seti = KAT[m["kategori"]]["beden_seti"]
    tam = BEDEN_SETLERI[seti]
    renkler = [c["renk"] for c in icerikler if c["m"] == m["m"]]
    sayilar = rng.poisson(model_talep[m["m"]] * carpan)
    for gun in np.nonzero(sayilar)[0]:
        for _ in range(sayilar[gun]):
            konu = sec(SORU_KONU)
            soran = {"boy": int(np.clip(rng.normal(164, 7), 148, 192)), "kilo": int(np.clip(rng.lognormal(np.log(61), 0.2), 38, 130))}
            soran["ayak"] = int(np.clip(round(36 + (soran["boy"] - 152) / 5 + rng.normal(0, 0.6)), 35, 42))
            ideal = ideal_konum(soran, seti)
            alan = {"boy": soran["boy"], "boy2": str(soran["boy"])[1:], "kilo": soran["kilo"],
                    "ayak": soran["ayak"], "beden": parca(tam), "renk": parca(renkler).lower(),
                    "kumas": m["kumas"].capitalize()}
            if konu == "beden" and seti in ("kemer", "corap"):
                konu = "diger"
            if konu == "beden" and seti == "ayakkabi":
                soru = parca(SORU["beden_ayakkabi"]).format(**alan)
                cevap = CEVAP["beden_ayakkabi"][{0: 0, -1: 1, 1: 2}[m["kalip"]]]
            elif konu == "beden":
                soru = parca(SORU["beden"]).format(**alan)
                oneri = ideal - m["kalip"]   # dar kalıpta bir büyük önerilir
                if 0 <= oneri < len(tam):
                    cevap = CEVAP["beden"].format(oneri=tam[oneri])
                else:
                    if seti.startswith("harf"):
                        ad = HARFLER[int(np.clip(oneri + HARFLER.index(tam[0]), 0, 7))]
                    else:
                        ad = tam[0] if oneri < 0 else tam[-1]
                    cevap = CEVAP["beden_yok"].format(oneri=ad)
            else:
                soru = parca(SORU[konu]).format(**alan)
                sablon = CEVAP[konu]
                cevap = (parca(sablon) if isinstance(sablon, list) else sablon).format(**alan)
            zaman = saat_sec(gun)
            bekleme = rng.lognormal(np.log(16), 1.1)
            if zaman.hour < 9:
                bekleme += (9 - zaman.hour) * 60 + rng.uniform(0, 90)
            cevap_zamani = zaman + pd.Timedelta(minutes=float(min(bekleme, 1400)))
            cevaplandi = cevap_zamani <= BITIS
            sorular.append({
                "soru_id": 0, "model_kodu": m["model_kodu"], "soru_tarihi": zaman.floor("min"),
                "soru": gunluk_dil(soru), "konu": konu, "durum": "ANSWERED" if cevaplandi else "UNANSWERED",
                "cevap": cevap if cevaplandi else None,
                "cevap_tarihi": cevap_zamani.floor("min") if cevaplandi else pd.NaT,
            })
sorular = pd.DataFrame(sorular).sort_values("soru_tarihi")
sorular["soru_id"] = 300_000_000 + np.cumsum(rng.integers(20_000, 60_000, len(sorular)))
sorular["cevap_suresi_dk"] = (sorular.cevap_tarihi - sorular.soru_tarihi).dt.total_seconds() / 60

# ====================================================
# 9) İADELER
# ====================================================
# İade olasılığı birim başına: kalıp/beden uyumsuzluğu, kusurlu ürün ve düşük kalite artırır.
# Ortalama, gerçek veriye göre ayarlanır (HEDEF_IADE_ORANI: teslim edilen birimlere göre iade talebi).

HEDEF_IADE_ORANI = 0.163   # gerçekte: talep %16,3, kabul edilen %12,2
IADE_NEDENI = {
    "SMALLSIZE": "Bedeni/Ebatı Küçük Geldi", "BIGSIZE": "Bedeni/Ebatı Büyük Geldi", "DISLIKE": "Beğenmedim",
    "DAMAGEDITEM": "Kusurlu ürün gönderildi", "WRONGITEM": "Yanlış ürün gönderildi",
    "MISSINGPART": "Ürünün parçası eksik geldi", "WRONGORDER": "Yanlış sipariş verdim", "ABANDON": "Vazgeçtim",
    "UNDELIVERED": "Teslim edilemeyen gönderi",
}
IADE_NOTU = {
    "SMALLSIZE": ["bir beden büyüğünü alacağım", "kalıbı çok dar", "belden olmadı", "boyu kısa geldi", "dar geldi"],
    "BIGSIZE": ["çok bol geldi", "bir beden küçüğünü alacağım", "boyu uzun", "kalıbı büyük"],
    "DISLIKE": ["kumaşı beklediğim gibi değil", "rengi fotoğraftan farklı", "üzerimde güzel durmadı",
                "kalitesini beğenmedim", "çok ince"],
    "DAMAGEDITEM": ["dikişi sökük geldi", "lekeli geldi", "fermuarı bozuk", "yırtık geldi"],
    "WRONGITEM": ["farklı renk gönderilmiş", "farklı beden gönderilmiş", "başka ürün geldi"],
    "MISSINGPART": ["takımın üstü gelmedi", "ürün eksik geldi"],
    "WRONGORDER": ["yanlış beden seçmişim", "yanlışlıkla sipariş verdim"],
    "ABANDON": ["vazgeçtim", "ihtiyacım kalmadı"],
}


IADE_KARGO = {"Sürat Kargo": 0.92, "DHL eCommerce": 0.04, "PTT Kargo": 0.03, "Yurtiçi Kargo": 0.01}


def iade_notu(kod):
    """Müşterilerin ~%59'u not yazar; çoğu nedenin kendisini tekrarlar."""
    if kod not in IADE_NOTU or rng.random() >= 0.59:
        return None
    return IADE_NEDENI[kod] if rng.random() < 0.4 else gunluk_dil(parca(IADE_NOTU[kod]))


def uuid_sec():
    h = rng.bytes(16).hex()
    return f"{h[:8]}-{h[8:12]}-4{h[13:16]}-{h[16:20]}-{h[20:]}"


teslim_edilen = satirlar[siparisler.set_index("paket_id").loc[satirlar.paket_id, "teslim_tarihi"].notna().values]
kalite_dizi = np.array([modeller[m]["kalite"] for m in teslim_edilen.g_model])
uyum_dizi = teslim_edilen.g_uyum.values
ham_olasilik = (0.04 + 0.08 * (1 - kalite_dizi) + 0.30 * np.maximum(-uyum_dizi, 0)
                + 0.32 * np.maximum(uyum_dizi, 0))
ham_olasilik = np.where(teslim_edilen.g_sorun.values, 0.40, ham_olasilik)
olcek = HEDEF_IADE_ORANI / np.average(ham_olasilik, weights=teslim_edilen.adet)
iade_olasiligi = np.clip(ham_olasilik * olcek, 0, 0.9)


def iade_nedeni_sec(uyum, kalite, sorun):
    if sorun:
        return str(rng.choice(["DAMAGEDITEM", "WRONGITEM", "MISSINGPART"], p=[0.48, 0.47, 0.05]))
    agirlik = {"SMALLSIZE": 3.0 * max(-uyum, 0), "BIGSIZE": 3.0 * max(uyum, 0),
               "DISLIKE": 0.6 + 2.0 * (1 - kalite), "WRONGORDER": 0.13, "ABANDON": 0.10}
    return sec(agirlik)


paket_bilgi = siparisler.set_index("paket_id")
iadeler = []
for (pid, satir), p in zip(teslim_edilen.iterrows(), iade_olasiligi):
    for kalem in satir.g_kalemler:
        if rng.random() >= p:
            continue
        kod = iade_nedeni_sec(satir.g_uyum, modeller[satir.g_model]["kalite"], satir.g_sorun)
        iadeler.append({"satir": satir, "kalem_id": kalem, "kod": kod})

# Teslim edilemeyip dönen paketler de iade kaydı oluşturur
for satir in satirlar[satirlar.satir_durumu == "UnDeliveredAndReturned"].itertuples():
    for kalem in satir.g_kalemler:
        iadeler.append({"satir": satirlar.loc[satir.Index], "kalem_id": kalem, "kod": "UNDELIVERED"})

iade_satirlari = []
paket_iade = {}   # aynı paketteki iadeler tek talepte toplanır
for x in iadeler:
    s, kod = x["satir"], x["kod"]
    pb = paket_bilgi.loc[s.paket_id]
    if kod == "UNDELIVERED":
        donus = pd.Timestamp(next(g["tarih"] for g in reversed(gecmis) if g["paket_id"] == s.paket_id and g["durum"] == "Returned"))
        zaman = donus
    else:
        zaman = pb.teslim_tarihi + pd.Timedelta(days=float(np.clip(rng.lognormal(0, 1.3), 0.05, 15)))
    if zaman > BITIS:
        continue
    if s.paket_id not in paket_iade:
        paket_iade[s.paket_id] = (uuid_sec(), zaman)
    iade_id, zaman = paket_iade[s.paket_id]
    yas = (BITIS - zaman).days
    if kod == "UNDELIVERED" or s.g_sorun:
        durum = "Accepted"
    elif yas < 4:
        durum = sec({"Created": 0.5, "WaitingInAction": 0.5})
    else:
        durum = sec({"Accepted": 0.73, "Cancelled": 0.265, "Rejected": 0.005})
    karar = sec({"SUPPLIER": 0.96, "SYSTEM": 0.04}) if durum == "Accepted" else None
    son = min(zaman + pd.Timedelta(days=float(np.clip(rng.lognormal(np.log(3.5), 0.6), 0.5, 20))), pd.Timestamp(BITIS))
    iade_satirlari.append({
        "iade_kalem_id": uuid_sec(), "iade_id": iade_id, "siparis_no": pb.siparis_no, "paket_id": s.paket_id,
        "satir_id": s.satir_id, "kalem_id": x["kalem_id"], "barkod": s.barkod, "siparis_tarihi": pb.siparis_tarihi,
        "iade_tarihi": zaman, "neden_kodu": kod, "neden": IADE_NEDENI[kod], "neden_grubu": iade_neden_grubu(kod),
        "musteri_notu": iade_notu(kod), "durum": durum, "karar_veren": karar,
        "kargo_firmasi": sec(IADE_KARGO), "son_guncelleme": son,
        "g_desi": s.g_desi,
    })
iadeler = pd.DataFrame(iade_satirlari).sort_values("iade_tarihi")
print(f"İadeler: {len(iadeler):,} birim, {iadeler.iade_id.nunique():,} talep "
      f"(teslim edilen birimlerin %{len(iadeler) / teslim_edilen.adet.sum() * 100:.1f}'i)")

# ====================================================
# 10) FİNANS HAREKETLERİ (cari hesap, birim bazında)
# ====================================================

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
         "Kasım", "Aralık"]
VADE = 28


def odeme_gunu(t):
    """Vade sonrası ilk pazartesi akşamı ödenir."""
    t = pd.Timestamp(t) + pd.Timedelta(days=VADE)
    return t.normalize() + pd.Timedelta(days=(7 - t.dayofweek) % 7, hours=20)


def hareket(t, tur, s, pb, kalem, borc=0.0, alacak=0.0):
    tutar = borc or alacak
    komisyon = round(tutar * s.komisyon_orani / 100, 2)
    return {"hareket_id": rng.bytes(12).hex(), "islem_tarihi": t, "islem_turu": tur, "barkod": s.barkod,
            "siparis_no": pb.siparis_no, "paket_id": s.paket_id, "satir_id": s.satir_id, "kalem_id": kalem,
            "siparis_tarihi": pb.siparis_tarihi, "borc": round(borc, 2), "alacak": round(alacak, 2),
            "komisyon_orani": s.komisyon_orani, "komisyon_tutari": komisyon,
            "satici_hakedisi": round(tutar - komisyon, 2), "vade_gun": VADE, "odeme_tarihi": odeme_gunu(t),
            "ulke": "Türkiye"}


kabul_iade = iadeler[(iadeler.durum == "Accepted") & (iadeler.neden_kodu != "UNDELIVERED")].set_index("kalem_id")
finans = []
for s in satirlar.itertuples():
    pb = paket_bilgi.loc[s.paket_id]
    if pd.isna(pb.teslim_tarihi):
        continue
    indirim = round(s.birim_satici_indirimi - s.g_kupon, 2)
    for kalem in s.g_kalemler:
        t = pb.teslim_tarihi
        finans.append(hareket(t, "Satış", s, pb, kalem, alacak=s.birim_brut_fiyat))
        if indirim > 0:
            finans.append(hareket(t, "İndirim", s, pb, kalem, borc=indirim))
        if s.g_kupon > 0:
            finans.append(hareket(t, "Kupon", s, pb, kalem, borc=s.g_kupon))
        if kalem in kabul_iade.index:
            t = kabul_iade.at[kalem, "son_guncelleme"]
            finans.append(hareket(t, "İade", s, pb, kalem, borc=s.birim_brut_fiyat))
            if indirim > 0:
                finans.append(hareket(t, "İndirim İptal", s, pb, kalem, alacak=indirim))
            if s.g_kupon > 0:
                finans.append(hareket(t, "Kupon İptal", s, pb, kalem, alacak=s.g_kupon))
finans_hareketleri = pd.DataFrame(finans).sort_values("islem_tarihi")
print(f"Finans hareketleri: {len(finans_hareketleri):,}")

# ====================================================
# 11) KARGO FATURALARI VE KESİNTİLER
# ====================================================

fatura_sira = iter(range(20_000_000, 99_999_999, 7))


def fatura_no(on_ek, t):
    return f"{on_ek}{t.year}{next(fatura_sira):08d}"[:16]


kargo_kalemleri = []
paket_desi = satirlar.groupby("paket_id").agg(desi=("g_desi", "max"), adet=("adet", "sum"))
for p in siparisler[siparisler.kargoya_verilis_tarihi.notna()].itertuples():
    desi = int(min(paket_desi.at[p.paket_id, "desi"] + (paket_desi.at[p.paket_id, "adet"] > 1), 6))
    t = p.kargoya_verilis_tarihi.normalize() + pd.Timedelta(days=int(rng.integers(12, 36)), hours=10)
    kargo_kalemleri.append({"t": t, "siparis_no": p.siparis_no, "paket_id": p.paket_id, "gonderi_turu": "Gönderi Kargo Bedeli",
                            "desi": desi, "tutar": round(tarifeden(KARGO_TARIFE, p.kargoya_verilis_tarihi) * DESI_CARPANI[desi], 2)})
for i in iadeler[(iadeler.durum == "Accepted") & (iadeler.neden_kodu != "UNDELIVERED")].drop_duplicates("iade_id").itertuples():
    t = i.iade_tarihi.normalize() + pd.Timedelta(days=int(rng.integers(10, 31)), hours=10)
    kargo_kalemleri.append({"t": t, "siparis_no": i.siparis_no, "paket_id": i.paket_id, "gonderi_turu": "İade Kargo Bedeli",
                            "desi": i.g_desi, "tutar": round(tarifeden(KARGO_TARIFE, i.iade_tarihi) * IADE_KARGO_CARPANI * DESI_CARPANI[i.g_desi], 2)})
kargo = pd.DataFrame(kargo_kalemleri)
kargo = kargo[kargo.t <= BITIS].sort_values("t")   # henüz faturalanmamışlar düşer

# Aynı gün kesilen kalemler birkaç faturaya bölünür
kargo_faturalari, kesintiler = [], []
for t, grup in kargo.groupby("t"):
    for indeksler in np.array_split(np.arange(len(grup)), max(1, len(grup) // int(rng.integers(4, 15)))):
        parca_df = grup.iloc[indeksler]
        no = fatura_no("DDF", t)
        kargo_faturalari += [{"fatura_no": no, "fatura_tarihi": t, **r} for r in
                             parca_df.drop(columns="t").to_dict("records")]
        kesintiler.append({"kesinti_id": no, "islem_tarihi": t, "tur": "Kargo Fatura", "borc": round(parca_df.tutar.sum(), 2),
                           "aciklama": "Kargo taşıma işlemini kargo firmaları yaptığından/yaptırdığından dolayı KDV tevkifat uygulaması yapılmamıştır."})
        gonderi = (parca_df.gonderi_turu == "Gönderi Kargo Bedeli").sum()
        if gonderi:
            kesintiler.append({"kesinti_id": fatura_no("DDF", t), "islem_tarihi": t + pd.Timedelta(minutes=5),
                               "tur": "Platform Hizmet Bedeli", "borc": round(gonderi * tarifeden(PLATFORM_BEDELI, t), 2),
                               "aciklama": "Teknolojik altyapı giderleri ve sistem işletimi için her bir gönderinize yansıtılan Platform Hizmet Bedeli faturasıdır."})
kargo_faturalari = pd.DataFrame(kargo_faturalari)

# Reklam bakiyesi alımları (talebe etkisi bölüm 4'te)
for gun in np.nonzero(REKLAM)[0]:
    t = GUNLER[gun] + pd.Timedelta(hours=float(rng.uniform(10, 23)))
    kesintiler.append({"kesinti_id": fatura_no("DDF", t), "islem_tarihi": t, "tur": "Reklam Bedeli", "borc": REKLAM[gun],
                       "aciklama": f"Satıcı Reklamı Satın Alma ({REKLAM[gun]:.2f} TL karşılığında, {t:%Y-%m-%dT%H:%M:%S}+03:00 tarihinde)"})

# Müşteri duyuruları (bazı pazar günleri)
for g in GUNLER[(GUNLER.dayofweek == 6)]:
    if rng.random() < 0.4:
        t = g + pd.Timedelta(hours=12)
        kesintiler.append({"kesinti_id": fatura_no("DDF", t), "islem_tarihi": t, "tur": "Müşteri Duyuruları Faturası",
                           "borc": float(rng.choice([50, 75, 75, 100, 150])), "aciklama": "Müşteri Duyuruları Faturası"})

# Tazminler: kusurlu / yanlış / eksik ürün iadeleri ve geç kargolama
TAZMIN = {"DAMAGEDITEM": ("Kusurlu Ürün Faturası", 0.35, [150, 150, 300]),
          "WRONGITEM": ("Yanlış Ürün Faturası", 0.5, [250, 250, 400]),
          "MISSINGPART": ("Eksik Ürün Faturası", 0.5, [150, 300])}
for i in iadeler[(iadeler.durum == "Accepted") & iadeler.neden_kodu.isin(list(TAZMIN))].drop_duplicates("iade_id").itertuples():
    tur, olasilik, tutarlar = TAZMIN[i.neden_kodu]
    t = i.son_guncelleme + pd.Timedelta(days=float(rng.uniform(7, 20)))
    if rng.random() < olasilik and t <= BITIS:
        kesintiler.append({"kesinti_id": fatura_no("DDF", t), "islem_tarihi": t, "tur": tur,
                           "borc": float(rng.choice(tutarlar)), "aciklama": "Tazmin bedelidir."})
gec = siparisler[(siparisler.kargoya_verilis_tarihi - siparisler.siparis_tarihi) > pd.Timedelta(hours=72)]
for p in gec.itertuples():
    t = p.kargoya_verilis_tarihi + pd.Timedelta(days=float(rng.uniform(7, 20)))
    if rng.random() < 0.3 and t <= BITIS:
        kesintiler.append({"kesinti_id": fatura_no("DDF", t), "islem_tarihi": t, "tur": "Termin Gecikme Bedeli",
                           "borc": 150.0, "aciklama": "Tazmin bedelidir."})

# Haftalık komisyon faturası (çarşamba 03:00, önceki 7 gün) — satır bazındaki komisyonla mükerrerdir
isaret = finans_hareketleri.islem_turu.map({"Satış": 1, "İndirim": -1, "Kupon": -1, "İade": -1,
                                            "İndirim İptal": 1, "Kupon İptal": 1})
net_komisyon = (finans_hareketleri.komisyon_tutari * isaret).groupby(finans_hareketleri.islem_tarihi.dt.normalize()).sum()
for g in GUNLER[GUNLER.dayofweek == 2]:
    bas, bit = g - pd.Timedelta(days=7), g - pd.Timedelta(days=1)
    tutar = net_komisyon[(net_komisyon.index >= bas) & (net_komisyon.index <= bit)].sum()
    t = g + pd.Timedelta(hours=3)
    if tutar > 0 and t <= BITIS:
        kesintiler.append({"kesinti_id": fatura_no("DCF", t), "islem_tarihi": t, "tur": "Komisyon Faturası",
                           "borc": round(tutar, 2),
                           "aciklama": f"{bas.day:02d} {AYLAR[bas.month - 1]} - {bit.day:02d} {AYLAR[bit.month - 1]} arası Trendyol hakediş tutarı"})

kesintiler = pd.DataFrame(kesintiler)

# Haftalık ödeme (pazartesi 20:00): vadesi gelen net hakediş - geçen haftanın giderleri
hakedis = (finans_hareketleri.satici_hakedisi * isaret).groupby(finans_hareketleri.odeme_tarihi).sum()
gider = kesintiler[~kesintiler.tur.isin(["Komisyon Faturası"])]
odemeler = []
for g in GUNLER[GUNLER.dayofweek == 0]:
    t = g + pd.Timedelta(hours=20)
    if t > BITIS:
        break
    tutar = hakedis[(hakedis.index > t - pd.Timedelta(days=7)) & (hakedis.index <= t)].sum()
    tutar -= gider[(gider.islem_tarihi > t - pd.Timedelta(days=7)) & (gider.islem_tarihi <= t)].borc.sum()
    if tutar > 0:
        odemeler.append({"kesinti_id": fatura_no("PAY", t), "islem_tarihi": t, "tur": "Ödeme", "borc": round(tutar, 2),
                         "aciklama": f"900001 - {next(fatura_sira)} - TRENDYOL Marketplace Ödeme"})
kesintiler = pd.concat([kesintiler, pd.DataFrame(odemeler)], ignore_index=True).sort_values("islem_tarihi")
kesintiler["alacak"] = 0.0
kesintiler["grup"] = kesintiler.tur.map(kesinti_grubu)
kesintiler["odeme_tarihi"] = kesintiler.islem_tarihi.map(lambda t: t.normalize() + pd.Timedelta(days=(7 - t.dayofweek) % 7 or 7, hours=20))
print(f"Kesintiler: {len(kesintiler):,}, kargo fatura kalemi: {len(kargo_faturalari):,}")

# ====================================================
# 12) ÜRÜN TABLOSU (bugünkü durum)
# ====================================================

urunler = []
for v in varyantlar:
    c = icerikler[v["c"]]
    m = modeller[c["m"]]
    arsivde = m["arsiv"] is not None
    if arsivde:
        stok = 0
    else:
        r = rng.random()
        stok = int(rng.integers(940, 1001)) if r < 0.45 else int(rng.lognormal(np.log(60), 1.0)) if r < 0.8 else 0
    fiyat = FIYAT[m["m"], -1]
    urunler.append({
        "barkod": v["barkod"], "urun_kodu": v["urun_kodu"], "icerik_id": c["icerik_id"],
        "model_kodu": m["model_kodu"], "urun_adi": m["ad"], "kategori": m["kategori"],
        "is_birimi": KAT[m["kategori"]]["is_birimi"], "renk": c["renk"], "beden": v["beden"],
        "liste_fiyati": guzel_fiyat(fiyat * rng.uniform(1.2, 1.5)) if rng.random() < 0.12 else fiyat,
        "satis_fiyati": fiyat, "stok": stok,
        "satista": (not arsivde) and stok > 0 and rng.random() > 0.08,
        "arsivde": arsivde,
        # uzun süre önce arşivlenen modellerin bir kısmı katalogdan silinmiştir
        "katalogda": not (arsivde and (BITIS.date() - m["arsiv"]).days > 250 and m["m"] % 3 == 0),
        "olusturma_tarihi": pd.Timestamp(m["lansman"]) + pd.Timedelta(hours=float(rng.uniform(9, 18))),
    })
urunler = pd.DataFrame(urunler)

# ====================================================
# 13) KAYDET
# ====================================================

print(f"\nKaydediliyor: {CIKTI}")
kaydet(urunler, CIKTI, "urunler")
kaydet(siparisler, CIKTI, "siparisler")
kaydet(satirlar, CIKTI, "siparis_satirlari")
kaydet(pd.DataFrame(gecmis), CIKTI, "siparis_durum_gecmisi")
kaydet(pd.DataFrame(indirimler), CIKTI, "siparis_indirimleri")
kaydet(sorular, CIKTI, "sorular")
kaydet(urun_yorumlari, CIKTI, "urun_yorumlari")
kaydet(satici_yorumlari, CIKTI, "satici_yorumlari")
kaydet(iadeler, CIKTI, "iadeler")
kaydet(finans_hareketleri, CIKTI, "finans_hareketleri")
kaydet(kesintiler, CIKTI, "kesintiler")
kaydet(kargo_faturalari, CIKTI, "kargo_faturalari")

# ====================================================
# 14) DOĞRU CEVAPLAR (gizli parametreler — modele VERİLMEZ, yalnızca doğrulama içindir)
# ====================================================
# Modelin veriden bulması gereken gerçek değerler. Bkz. veri/sahte/dogru_cevaplar/README.md

DOGRU = CIKTI / "dogru_cevaplar"
DOGRU.mkdir(exist_ok=True)


def dogru_kaydet(df, ad):
    df.to_csv(DOGRU / f"{ad}.csv", index=False, encoding="utf-8-sig")
    print(f"  dogru_cevaplar/{ad}.csv: {len(df):,} satır")


dogru_kaydet(pd.DataFrame([{
    "model_kodu": m["model_kodu"], "kategori": m["kategori"], "mevsim": KAT[m["kategori"]]["mevsim"],
    "kalip": m["kalip"], "kalip_etiketi": {-1: "dar", 0: "normal", 1: "bol"}[m["kalip"]],
    "kalite": round(m["kalite"], 4), "populerlik": round(m["populerlik"], 4),
    "fiyat_esnekligi": round(m["elastisite"], 4),
    "fiyat_endeksi": round(m["fiyat"] / kategori_ort_fiyat[m["kategori"]], 4),
    "lansman": m["lansman"], "arsiv_tarihi": m["arsiv"],
} for m in modeller]), "modeller")

dogru_kaydet(pd.DataFrame([{
    "icerik_id": c["icerik_id"], "model_kodu": modeller[c["m"]]["model_kodu"], "renk": c["renk"],
    "renk_talep_payi": round(c["pay"], 4),
} for c in icerikler]), "icerikler")

dogru_kaydet(pd.DataFrame([{
    "musteri_id": mu["musteri_id"], "boy": mu["boy"], "kilo": mu["kilo"], "ayak_numarasi": mu["ayak"],
} for mu in musteriler]), "musteriler")

dogru_kaydet(pd.DataFrame({
    "satir_id": satirlar.satir_id, "beden_uyumu": satirlar.g_uyum, "sorunlu_urun": satirlar.g_sorun,
}), "satirlar")

dogru_kaydet(pd.DataFrame({
    "tarih": GUNLER.date, "trend": trend.round(4), "haftanin_gunu_carpani": HAFTA_GUNU[GUNLER.dayofweek],
    "ozel_gun": OZEL_AD, "ozel_gun_carpani": OZEL, "maas_carpani": maas, "sepet_indirimi": SEPET,
    "reklam_harcamasi": REKLAM, "reklam_7g_toplam": reklam_7g,
    "reklam_carpani": (1 + 0.06 * (reklam_7g / 1000) ** 0.8).round(4),
    **{f"mevsim_{ad}": v.round(4) for ad, v in mevsim.items()},
}), "gunluk_carpanlar")

fk = pd.DataFrame({
    "model_kodu": np.repeat([m["model_kodu"] for m in modeller], D),
    "tarih": np.tile(GUNLER.date, M),
    "liste_fiyati": FIYAT.ravel(),
    "kupon_orani": KUPON.ravel(),
})
dogru_kaydet(fk[(fk.kupon_orani > 0) | (fk.groupby("model_kodu").liste_fiyati.diff().fillna(1) != 0)], "fiyat_kupon_degisimleri")
