"""Metrikler: projenin tek doğruluk kaynağı (F1-02).

Web sayfaları, tavsiye motoru ve asistan bir sayıya ihtiyaç duyduğunda buradaki fonksiyonları çağırır;
böylece aynı soru her yerde aynı sayıyı verir. Tanımlar ve hesaplama kuralları: docs/METRIKLER.md

    from analiz import metrikler as m
    m.hesapla("iade_orani", veri="gercek")                                         # tek sayı
    m.hesapla("ciro_net", veri="sahte", baslangic="2026-09-01", bitis="2026-09-30")
    m.hesapla("iade_orani", veri="gercek", kirilim="kategori")                     # kategori bazında Series
    m.donem_karsilastir("ciro_net", "gercek", "2026-10-01", "2026-10-23")          # önceki dönemle
    m.ozet("gercek")                                                               # son 30 günün ana KPI'ları

Tarih kuralı: satış, müşteri, iade ve kârlılık metrikleri SİPARİŞ tarihine göre (bir dönemin iade oranı, o dönemde
verilen siparişlerin iade oranıdır); finans ve gider metrikleri İŞLEM tarihine; yorum, soru ve iade talebi
metrikleri kendi tarihlerine göre filtrelenir.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import numpy as np
import pandas as pd

from hazirlama.ortak import VERI, hepsini_oku

# Finans hareketlerinin satıcı açısından işareti: + gelir, - geri alınan
ISARET = {"Satış": 1, "İndirim": -1, "Kupon": -1, "İade": -1, "İndirim İptal": 1, "Kupon İptal": 1,
          "ProvisionPositive": 1, "ProvisionNegative": -1, "ManualRefund": -1}
# Gider sayılmayanlar: Trendyol'un satıcıya ödemesi ve satır komisyonlarının mükerrer haftalık faturası
GIDER_DISI = {"odeme", "komisyon_faturasi"}
BEDEN_IADESI = {"beden_kucuk", "beden_buyuk"}
# Müşteri iadesi sayılmayan neden: kargo teslim edemeyip geri döndü
MUSTERI_IADESI_DISI = {"teslim_edilemedi"}
# İadeler teslimden sonraki günlerde açılıp kabul edilir. İade oranı yalnızca teslimi üzerinden bu kadar gün geçmiş
# ("olgun") satırlarla hesaplanır; yoksa son günlerin iade oranı yapay olarak düşük görünür.
OLGUNLASMA_GUN = 21   # gerçek veride iadelerin %99'u teslimden sonraki 21 gün içinde kabul ediliyor
# Trendyol bir paketi bölünce eski paket "UnPacked" olur ve satırları yeni paketlerde tekrar yer alır;
# bölünmüş paketler satış sayılmaz (yoksa aynı satır iki kez sayılır).
BOLUNMUS_PAKET = "UnPacked"
# Oran metriklerinde paydası bundan küçük kırılımlar "hesaplanamadı" (NaN) döner: 3 birimin 0'ı iade edildi diye
# "iade oranı %0" göstermek yanıltıcıdır.
MIN_ORNEK = 30

ZAMAN_KIRILIMLARI = ("gun", "hafta", "ay", "hafta_gunu", "saat")
KIRILIMLAR = {
    "satis": ("kategori", "model_kodu", "icerik_id", "beden", "renk", "is_birimi", "sehir", "kargo_firmasi",
              "hizli_teslimat", "odeme_yontemi"),
    "paket": ("sehir", "kargo_firmasi", "hizli_teslimat", "odeme_yontemi"),
    "finans": ("islem_turu", "ulke", "kategori"),
    "gider": ("grup", "tur"),
    "urun_yorum": ("kategori", "model_kodu", "icerik_id", "beden"),
    "satici_yorum": ("platform",),
    "soru": ("kategori", "model_kodu", "konu"),
    "iade": ("neden_grubu", "durum", "kategori", "model_kodu", "beden"),
}


# ====================================================
# 1) ÇERÇEVELER (veri seti başına bir kez hesaplanır)
# ====================================================

@lru_cache(maxsize=2)
def tablolar(veri="sahte"):
    """12 temel tablo. Önbellektedir: dönen tabloları değiştirmeyin."""
    return hepsini_oku(VERI / veri)


def yenile():
    """Veri dosyaları yeniden üretildiğinde önbelleği temizler."""
    tablolar.cache_clear()
    cerceveler.cache_clear()


def _satis_cercevesi(t):
    """Sipariş satırı başına satış, iade, kargo/komisyon/platform payı ve katkı (ozellik_cikar.py ile aynı kurallar)."""
    s, u = t["siparisler"], t["urunler"]
    s = s[s.paket_durumu != BOLUNMUS_PAKET]
    urun = u.drop_duplicates("barkod").set_index("barkod")[["icerik_id", "model_kodu", "kategori"]]
    d = (t["siparis_satirlari"]
         .merge(s[["paket_id", "siparis_no", "musteri_id", "siparis_tarihi", "sehir", "odeme_yontemi", "kargo_firmasi",
                   "hizli_teslimat", "kargoya_verilis_tarihi", "teslim_tarihi", "iptal"]], on="paket_id", how="inner")
         .join(urun, on="barkod"))
    d["brut_tutar"] = d.birim_brut_fiyat * d.adet
    d["teslim_adet"] = np.where(d.teslim_tarihi.notna(), d.adet, 0)

    i = t["iadeler"]
    kabul = i[(i.durum == "Accepted") & ~i.neden_grubu.isin(MUSTERI_IADESI_DISI)]
    d["iade_adet"] = np.minimum(d.satir_id.map(kabul.groupby("satir_id").size()).fillna(0), d.teslim_adet)
    beden = kabul[kabul.neden_grubu.isin(BEDEN_IADESI)].groupby("satir_id").size()
    d["beden_iade_adet"] = np.minimum(d.satir_id.map(beden).fillna(0), d.iade_adet)
    d["iade_tutari"] = d.iade_adet * d.birim_net_fiyat
    olgun = d.teslim_tarihi <= d.siparis_tarihi.max() - pd.Timedelta(days=OLGUNLASMA_GUN)
    d["olgun_teslim_adet"] = d.teslim_adet.where(olgun, 0)
    d["olgun_iade_adet"] = d.iade_adet.where(olgun, 0)
    d["olgun_beden_iade_adet"] = d.beden_iade_adet.where(olgun, 0)

    # Kargo: paketin gönderi bedeli satırlara brüt tutara göre dağıtılır; faturası henüz gelmemiş paketlerde
    # son 90 günün paket başı ortalaması kullanılır (kargo_tahmini = True)
    k = t["kargo_faturalari"]
    gonderi_k = k[k.gonderi_turu == "Gönderi Kargo Bedeli"]
    gonderi = gonderi_k.groupby("paket_id").tutar.sum()
    iade_kargo = k[k.gonderi_turu == "İade Kargo Bedeli"].groupby("paket_id").tutar.sum()
    son90 = gonderi_k[gonderi_k.fatura_tarihi > gonderi_k.fatura_tarihi.max() - pd.Timedelta(days=90)]
    pay = d.brut_tutar / d.groupby("paket_id").brut_tutar.transform("sum").replace(0, np.nan)
    gonderildi = d.kargoya_verilis_tarihi.notna()
    d["kargo_tahmini"] = gonderildi & ~d.paket_id.isin(gonderi.index)
    d["kargo_payi"] = (d.paket_id.map(gonderi).fillna(son90.tutar.mean()) * pay).where(gonderildi, 0).fillna(0)
    iade_agirlik = d.iade_adet * d.birim_brut_fiyat
    d["iade_kargo_payi"] = (d.paket_id.map(iade_kargo).fillna(0) * iade_agirlik
                            / iade_agirlik.groupby(d.paket_id).transform("sum").replace(0, np.nan)).fillna(0)

    g = t["kesintiler"]
    platform = g[(g.grup == "platform_hizmet") & (g.islem_tarihi > g.islem_tarihi.max() - pd.Timedelta(days=90))]
    paket_basi_platform = platform.borc.sum() / max(len(son90), 1)
    d["platform_payi"] = (paket_basi_platform * pay).where(gonderildi, 0).fillna(0)

    d["kalan_adet"] = (d.adet - d.iade_adet).clip(lower=0).where(~d.iptal, 0)
    kalan_net = d.kalan_adet * d.birim_net_fiyat
    d["komisyon_tutari"] = kalan_net * d.komisyon_orani / 100
    d["katki_payi"] = kalan_net - d.komisyon_tutari - d.kargo_payi - d.iade_kargo_payi - d.platform_payi

    ilk = s[~s.iptal].groupby("musteri_id").siparis_tarihi.min()
    d["ilk_siparis_mi"] = d.siparis_tarihi.eq(d.musteri_id.map(ilk))
    return d


@lru_cache(maxsize=2)
def cerceveler(veri="sahte"):
    """Metriklerin hesaplandığı çerçeveler. Önbellektedir: değiştirmeyin."""
    t = tablolar(veri)
    s, u = t["siparisler"], t["urunler"]
    model_kat = u.dropna(subset=["model_kodu"]).groupby("model_kodu").kategori.first()
    icerik = (u.dropna(subset=["icerik_id"]).drop_duplicates("icerik_id")
              .set_index("icerik_id")[["model_kodu", "kategori"]])
    barkod = u.drop_duplicates("barkod").set_index("barkod")[["model_kodu", "kategori", "beden"]]

    paket = s[s.paket_durumu != BOLUNMUS_PAKET].copy()
    paket["kargoya_verilis_saat"] = (paket.kargoya_verilis_tarihi - paket.siparis_tarihi).dt.total_seconds() / 3600
    paket["teslim_suresi_saat"] = (paket.teslim_tarihi - paket.siparis_tarihi).dt.total_seconds() / 3600

    finans = t["finans_hareketleri"].copy()
    finans["isaret"] = finans.islem_turu.map(ISARET).fillna(0)
    finans["tutar"] = finans.borc + finans.alacak
    finans["kategori"] = finans.barkod.map(barkod.kategori)

    return {
        "satis": _satis_cercevesi(t),
        "paket": paket,
        "finans": finans,
        "gider": t["kesintiler"][~t["kesintiler"].grup.isin(GIDER_DISI)],
        "urun_yorum": t["urun_yorumlari"].join(icerik, on="icerik_id"),
        "satici_yorum": t["satici_yorumlari"],
        "soru": t["sorular"].assign(kategori=t["sorular"].model_kodu.map(model_kat)),
        "iade": t["iadeler"].drop(columns=["siparis_tarihi"]).join(barkod, on="barkod"),
    }


TARIH = {"satis": "siparis_tarihi", "paket": "siparis_tarihi", "finans": "islem_tarihi", "gider": "islem_tarihi",
         "urun_yorum": "yorum_tarihi", "satici_yorum": "yorum_tarihi", "soru": "soru_tarihi", "iade": "iade_tarihi"}


# ====================================================
# 2) METRİK TANIMLARI
# ====================================================

@dataclass(frozen=True)
class Metrik:
    ad: str
    baslik: str
    birim: str                       # TL, adet, oran, saat, dk, puan
    cerceve: str
    hesapla: Callable[[pd.DataFrame], float]
    aciklama: str
    iyi_yon: int = 1                 # +1: yüksek iyi, -1: düşük iyi, 0: nötr (uyarı ve tavsiyeler için)


def _oran(pay, payda, min_ornek=1):
    return float(pay) / float(payda) if payda and payda >= min_ornek else np.nan


def _gecerli(d):
    return d[~d.iptal]


def _ciro_net(d):
    return float(_gecerli(d).satir_net_tutar.sum())


def _ciro_brut(d):
    return float(_gecerli(d).brut_tutar.sum())


def _tekrar_eden(d):
    g = _gecerli(d)
    return _oran(g.loc[~g.ilk_siparis_mi, "musteri_id"].nunique(), g.musteri_id.nunique())


_LISTE = [
    # --- Satış
    Metrik("ciro_brut", "Brüt ciro", "TL", "satis", _ciro_brut, "İndirim öncesi satış tutarı (iptaller hariç)"),
    Metrik("ciro_net", "Net satış", "TL", "satis", _ciro_net,
           "Müşterinin ödediği tutar (iptaller hariç, iadeler dahil)"),
    Metrik("indirim_tutari", "İndirim tutarı", "TL", "satis", lambda d: _ciro_brut(d) - _ciro_net(d),
           "Satıcı ve Trendyol indirimlerinin toplamı", -1),
    Metrik("indirim_orani", "İndirim oranı", "oran", "satis",
           lambda d: _oran(_ciro_brut(d) - _ciro_net(d), _ciro_brut(d)),
           "İndirim tutarı / brüt ciro", -1),
    Metrik("siparis_sayisi", "Sipariş sayısı", "adet", "satis", lambda d: _gecerli(d).paket_id.nunique(),
           "İptal edilmemiş paket sayısı"),
    Metrik("satilan_adet", "Satılan adet", "adet", "satis", lambda d: float(_gecerli(d).adet.sum()),
           "İptal edilmemiş satırlardaki ürün birimi"),
    Metrik("ortalama_sepet", "Ortalama sepet", "TL", "satis",
           lambda d: _oran(_ciro_net(d), _gecerli(d).paket_id.nunique()),
           "Net satış / sipariş sayısı"),
    Metrik("ortalama_birim_fiyat", "Ortalama birim fiyat", "TL", "satis",
           lambda d: _oran(_ciro_net(d), _gecerli(d).adet.sum()), "Net satış / satılan adet"),
    Metrik("iptal_orani", "İptal oranı", "oran", "paket", lambda d: _oran(d.iptal.sum(), len(d)),
           "İptal edilen paket / tüm paketler", -1),
    # --- Müşteri
    Metrik("musteri_sayisi", "Müşteri sayısı", "adet", "satis", lambda d: _gecerli(d).musteri_id.nunique(),
           "Dönemde sipariş veren tekil müşteri"),
    Metrik("yeni_musteri_sayisi", "Yeni müşteri", "adet", "satis",
           lambda d: _gecerli(d).loc[lambda g: g.ilk_siparis_mi, "musteri_id"].nunique(),
           "İlk siparişini bu dönemde veren müşteri"),
    Metrik("tekrar_eden_musteri_orani", "Tekrar eden müşteri oranı", "oran", "satis", _tekrar_eden,
           "Dönemde ilk siparişi dışında da siparişi olan müşteri / dönemdeki müşteriler"),
    # --- İade
    Metrik("teslim_edilen_adet", "Teslim edilen adet", "adet", "satis", lambda d: float(d.teslim_adet.sum()),
           "Teslim edilmiş satırlardaki ürün birimi"),
    Metrik("iade_adet", "İade adedi", "adet", "satis", lambda d: float(d.iade_adet.sum()),
           "Kabul edilen müşteri iadesi (birim); teslim edilemeyip dönenler hariç", -1),
    Metrik("iade_orani", "İade oranı", "oran", "satis",
           lambda d: _oran(d.olgun_iade_adet.sum(), d.olgun_teslim_adet.sum(), MIN_ORNEK),
           f"İade adedi / teslim edilen adet; yalnızca teslimi üzerinden {OLGUNLASMA_GUN} gün geçmiş satırlar", -1),
    Metrik("iade_tutari", "İade tutarı", "TL", "satis", lambda d: float(d.iade_tutari.sum()),
           "İade edilen birimlerin net fiyatı", -1),
    Metrik("beden_kaynakli_iade_payi", "Beden kaynaklı iade payı", "oran", "satis",
           lambda d: _oran(d.olgun_beden_iade_adet.sum(), d.olgun_iade_adet.sum(), MIN_ORNEK),
           f"Küçük/büyük geldi iadeleri / tüm iadeler (teslimi üzerinden {OLGUNLASMA_GUN} gün geçmiş satırlar)", -1),
    # --- Kârlılık (ürün maliyeti hariç)
    Metrik("komisyon_tutari", "Komisyon", "TL", "satis", lambda d: float(d.komisyon_tutari.sum()),
           "Elde kalan (iade düşülmüş) net satış × komisyon oranı", -1),
    Metrik("kargo_gideri", "Kargo gideri", "TL", "satis", lambda d: float(d.kargo_payi.sum()),
           "Gönderi kargo bedeli (faturası yoksa son 90 günün ortalaması)", -1),
    Metrik("iade_kargo_gideri", "İade kargo gideri", "TL", "satis", lambda d: float(d.iade_kargo_payi.sum()),
           "İade kargo bedeli", -1),
    Metrik("platform_gideri", "Platform hizmet bedeli", "TL", "satis", lambda d: float(d.platform_payi.sum()),
           "Gönderi başına platform hizmet bedeli (son 90 gün ortalaması)", -1),
    Metrik("katki_payi", "Katkı payı", "TL", "satis", lambda d: float(d.katki_payi.sum()),
           "Elde kalan net satış − komisyon − kargo − iade kargo − platform (ürün maliyeti hariç)"),
    Metrik("katki_marji", "Katkı marjı", "oran", "satis", lambda d: _oran(d.katki_payi.sum(), _ciro_net(d)),
           "Katkı payı / net satış"),
    # --- Operasyon
    Metrik("kargoya_verilis_suresi_saat", "Kargoya veriliş süresi", "saat", "paket",
           lambda d: float(d.kargoya_verilis_saat.median()), "Siparişten kargoya verilişe medyan süre", -1),
    Metrik("teslim_suresi_saat", "Teslim süresi", "saat", "paket", lambda d: float(d.teslim_suresi_saat.median()),
           "Siparişten teslime medyan süre", -1),
    # --- Finans (cari hesap, işlem tarihine göre)
    Metrik("net_hakedis", "Net hakediş", "TL", "finans", lambda d: float((d.satici_hakedisi * d.isaret).sum()),
           "Trendyol'un satıcıya ödeyeceği net tutar (satış − indirim − kupon − iade, komisyon düşülmüş)"),
    Metrik("finans_iade_orani", "İade oranı (finans)", "oran", "finans",
           lambda d: _oran((d.islem_turu == "İade").sum(), (d.islem_turu == "Satış").sum()),
           "Cari hesaptaki iade kaydı / satış kaydı (birim). Gerçek veride 1 yıl ve yurt dışını kapsar", -1),
    Metrik("gider_toplam", "Toplam gider", "TL", "gider", lambda d: float(d.borc.sum()),
           "Kargo, platform, reklam, ceza ve diğer kesintiler (ödemeler ve komisyon faturası hariç)", -1),
    Metrik("reklam_gideri", "Reklam gideri", "TL", "gider", lambda d: float(d.loc[d.grup == "reklam", "borc"].sum()),
           "Reklam bakiyesi alımları ve müşteri duyuruları", 0),
    # --- Müşteri sesi
    Metrik("yorum_sayisi", "Ürün yorumu", "adet", "urun_yorum", lambda d: len(d), "Ürün değerlendirmesi sayısı"),
    Metrik("ortalama_puan", "Ortalama ürün puanı", "puan", "urun_yorum", lambda d: float(d.puan.mean()),
           "Ürün yorumlarının ortalama puanı (1–5)"),
    Metrik("olumsuz_yorum_orani", "Olumsuz yorum oranı", "oran", "urun_yorum",
           lambda d: _oran((d.puan <= 2).sum(), len(d)),
           "1–2 puanlı yorum / tüm yorumlar", -1),
    Metrik("satici_puani", "Satıcı puanı", "puan", "satici_yorum", lambda d: float(d.satici_puani.mean()),
           "Satıcı değerlendirmelerinin ortalaması (1–5)"),
    Metrik("kargo_puani", "Kargo puanı", "puan", "satici_yorum", lambda d: float(d.kargo_puani.mean()),
           "Satıcı değerlendirmelerindeki kargo puanı ortalaması (1–5)"),
    Metrik("soru_sayisi", "Müşteri sorusu", "adet", "soru", lambda d: len(d), "Ürün soruları", 0),
    Metrik("medyan_cevap_suresi_dk", "Cevap süresi", "dk", "soru", lambda d: float(d.cevap_suresi_dk.median()),
           "Sorudan cevaba medyan süre", -1),
    Metrik("cevaplanmamis_soru_orani", "Cevaplanmamış soru oranı", "oran", "soru",
           lambda d: _oran((d.durum != "ANSWERED").sum(), len(d)), "Cevaplanmamış soru / tüm sorular", -1),
    Metrik("beden_sorusu_orani", "Beden sorusu oranı", "oran", "soru",
           lambda d: _oran((d.konu == "beden").sum(), len(d)),
           "Beden soruları / tüm sorular", -1),
    Metrik("iade_talebi_sayisi", "İade talebi", "adet", "iade", lambda d: len(d),
           "Açılan iade talebi birimleri (tüm durumlar, iade tarihine göre)", -1),
]
METRIKLER = {m.ad: m for m in _LISTE}

ANA_KPILAR = ["ciro_net", "siparis_sayisi", "ortalama_sepet", "musteri_sayisi", "iade_orani", "iptal_orani",
              "indirim_orani", "katki_payi", "katki_marji", "ortalama_puan", "medyan_cevap_suresi_dk"]


# ====================================================
# 3) HESAPLAMA
# ====================================================

def _metrik(ad):
    if ad not in METRIKLER:
        raise ValueError(f"Bilinmeyen metrik: {ad}. Geçerli metrikler: {', '.join(METRIKLER)}")
    return METRIKLER[ad]


def kirilimlar(ad):
    """Metriğin kırılabileceği alanlar."""
    return ZAMAN_KIRILIMLARI + KIRILIMLAR[_metrik(ad).cerceve]


def _filtrele(d, tarih, baslangic, bitis):
    if baslangic is not None:
        d = d[d[tarih] >= pd.Timestamp(baslangic)]
    if bitis is not None:
        d = d[d[tarih] < pd.Timestamp(bitis).normalize() + pd.Timedelta(days=1)]
    return d


def _kirilim_anahtari(d, tarih, kirilim):
    z = d[tarih].dt
    return {"gun": lambda: z.normalize(),
            "hafta": lambda: z.to_period("W-SUN").dt.start_time,
            "ay": lambda: z.to_period("M").astype(str),
            "hafta_gunu": lambda: z.dayofweek,
            "saat": lambda: z.hour}.get(kirilim, lambda: d[kirilim])()


def hesapla(ad, veri="sahte", baslangic=None, bitis=None, kirilim=None):
    """Metriği hesaplar. kirilim verilirse kırılım değerine göre bir pandas Series döner.

    baslangic / bitis: 'YYYY-AA-GG' (bitis günü dahil). Verilmezse tüm veri kullanılır.
    """
    m = _metrik(ad)
    tarih = TARIH[m.cerceve]
    d = _filtrele(cerceveler(veri)[m.cerceve], tarih, baslangic, bitis)
    if kirilim is None:
        return m.hesapla(d)
    if kirilim not in kirilimlar(ad):
        raise ValueError(f"'{ad}' için geçersiz kırılım: {kirilim}. Geçerli: {', '.join(kirilimlar(ad))}")
    anahtar = _kirilim_anahtari(d, tarih, kirilim)
    sonuc = pd.Series({k: m.hesapla(g) for k, g in d.groupby(anahtar, sort=True)}, name=ad, dtype=float)
    sonuc.index.name = kirilim
    return sonuc if kirilim in ZAMAN_KIRILIMLARI else sonuc.sort_values(ascending=False)


def veri_araligi(veri="sahte"):
    """Sipariş verisinin ilk ve son günü."""
    tarih = cerceveler(veri)["satis"].siparis_tarihi
    return tarih.min().normalize(), tarih.max().normalize()


def donem_karsilastir(ad, veri, baslangic, bitis):
    """Metriği verilen dönem ve hemen önceki eşit uzunluktaki dönem için hesaplar."""
    bas, bit = pd.Timestamp(baslangic).normalize(), pd.Timestamp(bitis).normalize()
    uzunluk = bit - bas + pd.Timedelta(days=1)
    deger = hesapla(ad, veri, bas, bit)
    onceki = hesapla(ad, veri, bas - uzunluk, bas - pd.Timedelta(days=1))
    # Önceki dönem veri aralığının dışındaysa karşılaştırma yapılmaz
    if bas - uzunluk < veri_araligi(veri)[0]:
        onceki = np.nan
    degisim = (deger - onceki) / abs(onceki) if onceki and not np.isnan(onceki) else np.nan
    return {"ad": ad, "deger": deger, "onceki": onceki, "degisim": degisim,
            "onceki_baslangic": bas - uzunluk, "onceki_bitis": bas - pd.Timedelta(days=1)}


def ozet(veri="sahte", baslangic=None, bitis=None, metrikler=ANA_KPILAR):
    """Ana KPI'lar ve önceki döneme göre değişim. Tarih verilmezse verinin son 30 günü."""
    if bitis is None:
        bitis = veri_araligi(veri)[1]
    if baslangic is None:
        baslangic = pd.Timestamp(bitis) - pd.Timedelta(days=29)
    satirlar = []
    for ad in metrikler:
        m = METRIKLER[ad]
        k = donem_karsilastir(ad, veri, baslangic, bitis)
        iyilesme = np.sign(k["degisim"]) * m.iyi_yon if not np.isnan(k["degisim"]) else np.nan
        satirlar.append({"ad": ad, "baslik": m.baslik, "birim": m.birim, "deger": k["deger"], "onceki": k["onceki"],
                         "degisim": k["degisim"], "iyilesme": iyilesme})
    return pd.DataFrame(satirlar)


def metrik_listesi():
    """Tüm metriklerin tanımı (asistan araçları ve dokümantasyon için)."""
    return pd.DataFrame([{"ad": m.ad, "baslik": m.baslik, "birim": m.birim, "aciklama": m.aciklama,
                          "tarih": TARIH[m.cerceve], "kirilimlar": ", ".join(kirilimlar(m.ad)),
                          "iyi_yon": {1: "yüksek", -1: "düşük", 0: "nötr"}[m.iyi_yon]} for m in _LISTE])
