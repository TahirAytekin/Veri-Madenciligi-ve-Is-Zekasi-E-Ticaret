"""Temizleme, sahte veri üretimi ve özellik çıkarma betiklerinin ortak tanımları.

Gerçek (temizlenmiş) veri ile sahte veri AYNI şemayı kullanır; böylece sahte veri
üzerinde geliştirilen her analiz/model gerçek veride de değişiklik yapmadan çalışır.
"""
import os
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJE = Path(__file__).resolve().parent.parent
VERI = PROJE / "veri"
HAM = VERI / "ham"          # cekim/ betiklerinin çıktıları


def env_degeri(ad, varsayilan=None):
    """Önce ortam değişkenine, yoksa proje kökündeki .env dosyasına bakar."""
    if ad in os.environ:
        return os.environ[ad]
    yol = PROJE / ".env"
    if yol.exists():
        for satir in yol.read_text(encoding="utf-8").splitlines():
            anahtar, _, deger = satir.strip().partition("=")
            if anahtar.strip() == ad and not satir.strip().startswith("#"):
                return deger.strip().strip("\"'")
    return varsayilan

# ====================================================
# TABLO ŞEMALARI (sütun sırası dahil)
# ====================================================

TABLOLAR = {
    # Ürün varyantı (beden + renk) başına bir satır
    "urunler": [
        "barkod", "urun_kodu", "icerik_id", "model_kodu", "urun_adi", "kategori", "is_birimi",
        "renk", "beden", "liste_fiyati", "satis_fiyati", "stok", "satista", "arsivde",
        "katalogda", "olusturma_tarihi",
    ],
    # Kargo paketi başına bir satır (bir sipariş nadiren birden fazla pakete bölünür)
    "siparisler": [
        "paket_id", "siparis_no", "musteri_id", "siparis_tarihi", "sehir", "ilce",
        "odeme_yontemi", "kargo_firmasi", "hizli_teslimat", "paket_durumu",
        "brut_tutar", "satici_indirimi", "trendyol_indirimi", "net_tutar",
        "tahmini_teslim_bas", "tahmini_teslim_bit", "kargoya_verilis_tarihi", "teslim_tarihi",
        "iptal", "teslim_edilemedi", "iade_dondu",
    ],
    # Paketteki her ürün satırı (fiyatlar BİRİM fiyattır)
    "siparis_satirlari": [
        "satir_id", "paket_id", "barkod", "urun_kodu", "adet", "beden", "renk",
        "birim_brut_fiyat", "birim_satici_indirimi", "birim_trendyol_indirimi", "birim_net_fiyat",
        "satir_net_tutar", "komisyon_orani", "kdv_orani", "is_birimi", "satir_durumu",
    ],
    "siparis_durum_gecmisi": ["paket_id", "durum", "tarih"],
    "siparis_indirimleri": ["paket_id", "indirim_adi", "indirim_turu", "tutar"],
    "sorular": [
        "soru_id", "model_kodu", "soru_tarihi", "soru", "konu", "durum", "cevap",
        "cevap_tarihi", "cevap_suresi_dk",
    ],
    "urun_yorumlari": [
        "yorum_id", "icerik_id", "yorum_tarihi", "puan", "yorum", "beden", "boy", "kilo",
        "begeni", "fotografli",
    ],
    "satici_yorumlari": [
        "yorum_id", "yorum_tarihi", "satici_puani", "kargo_puani", "yorum",
        "satici_nedenleri", "kargo_nedenleri", "platform",
    ],
    # İade talebindeki her ürün birimi (claim item). satir_id -> siparis_satirlari, barkod -> urunler
    "iadeler": [
        "iade_kalem_id", "iade_id", "siparis_no", "paket_id", "satir_id", "kalem_id", "barkod",
        "siparis_tarihi", "iade_tarihi", "neden_kodu", "neden", "neden_grubu", "musteri_notu",
        "durum", "karar_veren", "kargo_firmasi", "son_guncelleme",
    ],
    # Cari hesap: sipariş kalemine bağlı para hareketleri (satış, iade, indirim, kupon ...)
    "finans_hareketleri": [
        "hareket_id", "islem_tarihi", "islem_turu", "barkod", "siparis_no", "paket_id", "satir_id",
        "kalem_id", "siparis_tarihi", "borc", "alacak", "komisyon_orani", "komisyon_tutari",
        "satici_hakedisi", "vade_gun", "odeme_tarihi", "ulke",
    ],
    # Cari hesap: siparişe bağlı olmayan kesinti/gider ve ödemeler (kargo, reklam, platform bedeli ...)
    "kesintiler": [
        "kesinti_id", "islem_tarihi", "tur", "grup", "borc", "alacak", "aciklama", "odeme_tarihi",
    ],
    # Kargo faturalarının gönderi bazlı detayı
    "kargo_faturalari": [
        "fatura_no", "fatura_tarihi", "siparis_no", "paket_id", "gonderi_turu", "desi", "tutar",
    ],
}

TARIH_SUTUNLARI = {
    "urunler": ["olusturma_tarihi"],
    "siparisler": ["siparis_tarihi", "tahmini_teslim_bas", "tahmini_teslim_bit",
                   "kargoya_verilis_tarihi", "teslim_tarihi"],
    "siparis_durum_gecmisi": ["tarih"],
    "sorular": ["soru_tarihi", "cevap_tarihi"],
    "urun_yorumlari": ["yorum_tarihi"],
    "satici_yorumlari": ["yorum_tarihi"],
    "iadeler": ["siparis_tarihi", "iade_tarihi", "son_guncelleme"],
    "finans_hareketleri": ["islem_tarihi", "siparis_tarihi", "odeme_tarihi"],
    "kesintiler": ["islem_tarihi", "odeme_tarihi"],
    "kargo_faturalari": ["fatura_tarihi"],
}

TARIH_FORMATI = "%Y-%m-%d %H:%M:%S"


def kaydet(df, klasor, ad):
    eksik = set(TABLOLAR[ad]) - set(df.columns)
    if eksik:
        raise ValueError(f"{ad}: eksik sütunlar {eksik}")
    df = df[TABLOLAR[ad]].copy()
    for s in TARIH_SUTUNLARI.get(ad, []):
        df[s] = pd.to_datetime(df[s]).dt.strftime(TARIH_FORMATI)
    klasor = Path(klasor)
    klasor.mkdir(parents=True, exist_ok=True)
    df.to_csv(klasor / f"{ad}.csv", index=False, encoding="utf-8-sig")
    print(f"  {ad}.csv: {len(df):,} satır")


def oku(klasor, ad):
    df = pd.read_csv(Path(klasor) / f"{ad}.csv", encoding="utf-8-sig", low_memory=False)
    for s in TARIH_SUTUNLARI.get(ad, []):
        df[s] = pd.to_datetime(df[s])
    return df


def hepsini_oku(klasor):
    return {ad: oku(klasor, ad) for ad in TABLOLAR}


# ====================================================
# KESİM TARİHİ (sızıntısız model eğitimi için)
# ====================================================

_PAKET_DURUMU = {"Awaiting": "ReadyToShip", "Created": "ReadyToShip", "Picking": "ReadyToShip",
                 "Shipped": "Shipped", "UnDelivered": "Shipped", "Delivered": "Delivered",
                 "Cancelled": "Cancelled", "Returned": "UnDeliveredAndReturned", "UnPacked": "UnPacked"}


def kesim_uygula(t, kesim):
    """Tabloları `kesim` gününün sonunda BİLİNEN hale getirir; sonrası hiç olmamış gibi davranılır.

    Özellikleri kesime kadar, hedefi (gelecek satış, iade, tekrar alım ...) kesimden sonraki dönemden
    hesaplayarak modeli geleceği görmeden eğitmek için:
        gecmis = kesim_uygula(hepsini_oku(VERI / "sahte"), "2026-06-30")
    Kesimden önce verilip sonra teslim edilen paket "Shipped", sonra kabul edilen iade "WaitingInAction",
    sonra cevaplanan soru "UNANSWERED" görünür.
    DİKKAT: urunler tablosundaki stok/fiyat/satışta bilgisi BUGÜNÜN durumudur (geçmişi yok);
    model özelliği olarak kullanmayın, fiyatı satış satırlarından alın.
    """
    k = pd.Timestamp(kesim).normalize() + pd.Timedelta(days=1)   # kesim günü dahil
    t = {ad: df.copy() for ad, df in t.items()}

    g = t["siparis_durum_gecmisi"] = t["siparis_durum_gecmisi"][lambda d: d.tarih < k]
    s = t["siparisler"][lambda d: d.siparis_tarihi < k].copy()
    for sutun in ["kargoya_verilis_tarihi", "teslim_tarihi"]:
        s.loc[s[sutun] >= k, sutun] = pd.NaT
    son = g.sort_values("tarih").groupby("paket_id").durum.last().map(_PAKET_DURUMU)
    s["paket_durumu"] = s.paket_id.map(son).fillna("ReadyToShip")
    olan = g.groupby("paket_id").durum.agg(set)
    for sutun, durum in [("iptal", "Cancelled"), ("teslim_edilemedi", "UnDelivered"), ("iade_dondu", "Returned")]:
        s[sutun] = s.paket_id.map(lambda p: durum in olan.get(p, ()))
    t["siparisler"] = s

    satir = t["siparis_satirlari"][lambda d: d.paket_id.isin(s.paket_id)].copy()
    satir["satir_durumu"] = satir.paket_id.map(s.set_index("paket_id").paket_durumu)
    t["siparis_satirlari"] = satir
    t["siparis_indirimleri"] = t["siparis_indirimleri"][lambda d: d.paket_id.isin(s.paket_id)]

    i = t["iadeler"][lambda d: d.iade_tarihi < k].copy()
    karar_sonra = i.son_guncelleme >= k
    i.loc[karar_sonra, "durum"] = "WaitingInAction"
    i.loc[karar_sonra, "karar_veren"] = None
    i.loc[karar_sonra, "son_guncelleme"] = i.loc[karar_sonra, "iade_tarihi"]
    t["iadeler"] = i

    t["finans_hareketleri"] = t["finans_hareketleri"][lambda d: d.islem_tarihi < k]
    t["kesintiler"] = t["kesintiler"][lambda d: d.islem_tarihi < k]
    t["kargo_faturalari"] = t["kargo_faturalari"][lambda d: d.fatura_tarihi < k]

    q = t["sorular"][lambda d: d.soru_tarihi < k].copy()
    sonra = q.cevap_tarihi >= k
    q.loc[sonra, ["cevap", "cevap_suresi_dk"]] = np.nan
    q.loc[sonra, "cevap_tarihi"] = pd.NaT
    q.loc[sonra, "durum"] = "UNANSWERED"
    t["sorular"] = q

    t["urun_yorumlari"] = t["urun_yorumlari"][lambda d: d.yorum_tarihi < k]
    t["satici_yorumlari"] = t["satici_yorumlari"][lambda d: d.yorum_tarihi < k]
    t["urunler"] = t["urunler"][lambda d: d.olusturma_tarihi.isna() | (d.olusturma_tarihi < k)]
    return t


# ====================================================
# ÖZEL GÜNLER / KAMPANYA TAKVİMİ
# ====================================================
# Herkese açık takvim bilgisi; sahte veride talep çarpanı, analizde özellik olarak kullanılır.

BAYRAMLAR = {
    "Ramazan Bayramı": ["2024-04-10", "2025-03-30", "2026-03-20", "2027-03-09"],
    "Kurban Bayramı": ["2024-06-16", "2025-06-06", "2026-05-27", "2027-05-16"],
}


def _ayin_ilk_gunu(yil, ay, hafta_gunu):
    d = date(yil, ay, 1)
    return d + timedelta((hafta_gunu - d.weekday()) % 7)


def ozel_gunler(baslangic, bitis):
    """{tarih: (ad, talep_carpani)} döndürür. Çakışmada çarpanı büyük olan kazanır."""
    gunler = {}

    def ekle(ad, bas, bit, carpan):
        d = bas
        while d <= bit:
            if d not in gunler or gunler[d][1] < carpan:
                gunler[d] = (ad, carpan)
            d += timedelta(1)

    for y in range(baslangic.year, bitis.year + 1):
        ekle("Ocak İndirimi", date(y, 1, 2), date(y, 1, 15), 1.15)
        ekle("Sevgililer Günü", date(y, 2, 7), date(y, 2, 14), 1.15)
        ekle("Kadınlar Günü", date(y, 3, 4), date(y, 3, 8), 1.10)
        anneler = _ayin_ilk_gunu(y, 5, 6) + timedelta(7)
        ekle("Anneler Günü", anneler - timedelta(7), anneler, 1.25)
        ekle("Yaz İndirimi", date(y, 7, 1), date(y, 7, 15), 1.15)
        ekle("Okula Dönüş", date(y, 8, 25), date(y, 9, 15), 1.20)
        ekle("Efsane Kasım", date(y, 11, 1), date(y, 11, 30), 1.35)
        ekle("11.11", date(y, 11, 10), date(y, 11, 12), 1.90)
        black_friday = _ayin_ilk_gunu(y, 11, 4) + timedelta(21)
        if (black_friday + timedelta(7)).month == 11:
            black_friday += timedelta(7)
        ekle("Black Friday", black_friday - timedelta(1), black_friday + timedelta(3), 2.00)
        ekle("Yılbaşı", date(y, 12, 15), date(y, 12, 31), 1.20)
    for ad, tarihler in BAYRAMLAR.items():
        for t in tarihler:
            t = date.fromisoformat(t)
            ekle(f"{ad} Öncesi", t - timedelta(7), t - timedelta(1), 1.20)

    return {d: v for d, v in gunler.items() if baslangic <= d <= bitis}


# ====================================================
# METİN SINIFLANDIRMA (gerçek veride kural tabanlı)
# ====================================================

SORU_KONULARI = [
    ("iade_degisim", r"iade|değişim|degisim|defolu|yanlış ürün|eksik geldi|göndermişsiniz"),
    ("kargo", r"kargo|sipariş|siparis|teslim|gönderi|ne zaman (hazırlan|gel|çık|kargo)"),
    ("stok", r"stok|tekrar gel|gelecek m|gelir m|ne zaman gel|tüken|kalmamış|kalmadı"),
    ("beden", r"beden|\bboy|kilo|\bkg\b|\bkl\b|numara|giyiyorum|olur ?mu|uygun ?mu|\d{3}\s*[/,-]?\s*\d{2}\b"),
    ("olcu", r"\bcm\b|santim|\beni\b|ölçü|uzunluğ|genişliğ|yüksekliğ|boyu kaç|paça"),
    ("kumas", r"kumaş|pamuk|terlet|yıka|kalın|ince|esnek|likra|malzeme|astar|deri|tüyl|şardon|yumuşak|sıcak tut|kışın"),
    ("renk", r"renk|rengi|görsel|fotoğraf|foto|aynısı|\b(siyah|beyaz|gri|yeşil|mavi|lacivert|bordo|pembe|kahve)\w* m[ıi]\b"),
]


def soru_konusu(metin):
    metin = str(metin).lower()
    for konu, desen in SORU_KONULARI:
        if re.search(desen, metin):
            return konu
    return "diger"


IADE_NEDEN_GRUPLARI = {
    "beden_kucuk": ["SMALLSIZE"],
    "beden_buyuk": ["BIGSIZE"],
    "begenmedim": ["DISLIKE"],
    "kusurlu": ["DAMAGEDITEM", "CHANGEREQUEST", "DEFECTIVE"],
    "yanlis_eksik_urun": ["WRONGITEM", "MISSINGITEM", "MISSINGPART"],
    "vazgecti": ["ABANDON", "WRONGORDER", "BETTERPRICE"],
    "teslim_edilemedi": ["UNDELIVERED", "UNDELIVEREDINT", "CANNOTBEDISPATCHED"],
}
_IADE_KOD_GRUP = {kod: grup for grup, kodlar in IADE_NEDEN_GRUPLARI.items() for kod in kodlar}


def iade_neden_grubu(kod):
    return _IADE_KOD_GRUP.get(str(kod), "diger")


def kesinti_grubu(tur):
    """Cari hesap 'diğer hareket' türünü analiz grubuna çevirir.

    Gider hesabında 'odeme' (Trendyol'un satıcıya ödemesi / tahsilat) ve 'komisyon_faturasi'
    (satır bazındaki komisyonun haftalık faturası, mükerrer) gruplarını toplama katmayın.
    """
    tur = str(tur)
    kurallar = [
        ("kargo", r"Kargo"),
        ("reklam", r"Reklam|Duyuru"),
        ("komisyon_faturasi", r"Komisyon"),
        ("uluslararasi", r"Uluslararası|ULUSLARARASI|Yurt ?d[ıi][sş][ıi]|YURT ?DISI|^AZ-"),
        ("platform_hizmet", r"Platform Hizmet"),
        ("ceza_tazmin", r"Kusurlu|KUSURLU|Yanlış|Eksik|Termin|Gecikme|Tazmin|Ceza"),
        ("finansman", r"Erken Ödeme"),
        ("odeme", r"Ödeme|Virman|Transfer|Avans|Tahsilat"),
    ]
    for grup, desen in kurallar:
        if re.search(desen, tur, flags=re.I):
            return grup
    return "diger"


def indirim_turu(ad):
    ad = str(ad)
    if re.search(r"Plus", ad) and "Kupon" not in ad:
        return "plus_fiyat"
    if re.search(r"Kupon|Takip Et|Göz Attın", ad):
        return "magaza_kuponu"
    if re.search(r"Adet|\d\. Ürüne", ad):
        return "coklu_alim"
    if re.search(r"Sepette|TL'ye", ad):
        return "sepet_indirimi"
    return "diger"
