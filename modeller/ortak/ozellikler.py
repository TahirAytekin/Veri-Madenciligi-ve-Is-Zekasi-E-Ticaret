"""Aktarılabilir özellikler (F2-01): sahte ve gerçek veride AYNI fonksiyonla, AYNI anlamda üretilir.

Modeller sahte veriyle eğitilip gerçek veride test edildiği için (docs/MODEL_DOGRULAMA.md):
  - ID kullanılmaz (sahte ve gerçek ürün/müşteri ID'leri farklıdır),
  - ürün adı, mutlak tarih gibi veri setine özgü alanlar kullanılmaz,
  - geçmiş özellikleri (ürünün o güne kadarki iade oranı vb.) yalnızca SİPARİŞ ANINDAN ÖNCEKİ olaylardan hesaplanır.

    from modeller.ortak.ozellikler import iade_veri_seti, KATEGORIK, SAYISAL
    df = iade_veri_seti("sahte")          # satır başına özellikler + etiketler
"""
import re
from functools import lru_cache

import numpy as np
import pandas as pd

from analiz import metrikler as m

# ====================================================
# 1) SABİTLER
# ====================================================

HARF_SIRASI = {"3XS": 0, "2XS": 1, "XXS": 1, "XS": 2, "S": 3, "M": 4, "L": 5, "XL": 6, "2XL": 7, "XXL": 7,
               "3XL": 8, "4XL": 9, "5XL": 10}
RENK_GRUPLARI = [   # (grup, anahtar kelimeler) — sıra önemli: ilk eşleşen kazanır
    ("siyah_koyu", ["siyah", "black", "füme", "fume", "antrasit", "koyu gri"]),
    ("beyaz_acik", ["beyaz", "white", "ekru", "krem", "şeffaf", "seffaf"]),
    ("gri", ["gri", "gray", "grey", "gümüş", "gumus", "metalik"]),
    ("mavi", ["mavi", "lacivert", "blue", "denim", "indigo"]),
    ("pembe_kirmizi", ["pembe", "pink", "kırmızı", "kirmizi", "red", "bordo", "lila", "mor", "fuşya"]),
    ("toprak_yesil", ["kahve", "bej", "camel", "haki", "yeşil", "yesil", "green", "kamuflaj", "sarı", "sari"]),
]
BUYUK_ILLER = ["İstanbul", "Ankara", "İzmir", "Antalya", "Bursa", "Kocaeli", "Konya", "Adana", "Mersin", "Muğla"]
DOGU_ILLER = {"Van", "Hakkari", "Şırnak", "Ağrı", "Kars", "Ardahan", "Iğdır", "Muş", "Bitlis", "Siirt", "Batman",
              "Mardin", "Diyarbakır", "Şanlıurfa", "Bingöl", "Tunceli", "Erzurum", "Erzincan", "Bayburt", "Gümüşhane",
              "Artvin", "Rize", "Trabzon", "Hatay", "Kilis", "Adıyaman", "Malatya", "Elazığ"}

# Geçmiş oranlarında az gözlemi olan ürünler önceye (prior) doğru çekilir (Bayes düzeltmesi)
ONSEL_IADE = 0.10          # hiç geçmişi olmayan kategori için varsayılan iade oranı (veriden değil, sabit kabul)
KATEGORI_GUCU = 50         # kategori oranının önsele karşı "sanal gözlem" sayısı
MODEL_GUCU = 20            # model oranının kategori oranına karşı "sanal gözlem" sayısı

KATEGORIK = ["kategori", "is_birimi", "renk_grubu", "beden_tipi", "il_grubu", "kargo_firmasi", "hizli_teslimat"]
SAYISAL = ["beden_konum", "beden_sinirda", "fiyat_endeksi", "indirim_orani", "kuponlu", "adet", "sepet_satir_sayisi",
           "sepet_tutari_endeksi", "hafta_gunu", "saat", "ay", "dogu_ili",
           "musteri_onceki_siparis", "musteri_onceki_iade_orani",
           "kategori_onceki_iade_orani", "model_onceki_iade_orani", "model_onceki_satis_log",
           "model_onceki_kucuk_orani", "model_onceki_buyuk_orani", "model_onceki_puan", "model_onceki_yorum_log"]
ETIKETLER = ["iade", "iade_nedeni"]

# F1-04 (docs/rapor/01_gercek_sahte.md): sahtedeki ilişkisi gerçekte TERS yönde olan özellikler; modellerde kullanılmaz.
#   ay: sahte 2 yıl, gerçek yalnızca Temmuz–Ekim · saat, indirim_orani: sahte üretici iadeyle ilişkilendirmedi
#   model_onceki_puan: gerçekte yorum az, ilişki gürültülü ve ters
AKTARILAMAZ = ["ay", "saat", "indirim_orani", "model_onceki_puan"]
MODEL_KATEGORIK = [c for c in KATEGORIK if c not in AKTARILAMAZ]
MODEL_SAYISAL = [c for c in SAYISAL if c not in AKTARILAMAZ]


# ====================================================
# 2) BEDEN VE RENK
# ====================================================

def beden_degeri(beden):
    """Bedeni sıralanabilir sayıya çevirir: (tip, değer). Harf: XS=2 ... ; sayı: 28, 38 ... ; diğer: (None, NaN)."""
    b = str(beden).strip().upper().replace(" ", "")
    b = b.split("/")[0]                       # "XXS/26", "M/38" -> ilk kısım
    if b in HARF_SIRASI:
        return "harf", float(HARF_SIRASI[b])
    if re.fullmatch(r"\d{2}", b):
        return "sayi", float(b)
    return "diger", np.nan                    # "110 CM", "36-40", "14-15YAŞ", "STANDART"


def renk_grubu(renk):
    r = str(renk).lower()
    for grup, kelimeler in RENK_GRUPLARI:
        if any(k in r for k in kelimeler):
            return grup
    return "desenli_diger"


def _beden_konumu(df, katalog):
    """Bedenin kendi kategorisi ve tipindeki göreli konumu: 0 = en küçük, 1 = en büyük (katalogdaki bedenlere göre)."""
    k = katalog.dropna(subset=["kategori"])[["kategori", "beden"]].drop_duplicates()
    k[["tip", "deger"]] = k.beden.map(beden_degeri).tolist()
    sinir = k.dropna(subset=["deger"]).groupby(["kategori", "tip"]).deger.agg(["min", "max"])
    tip_deger = df.beden.map(beden_degeri)
    df["beden_tipi"] = [t for t, _ in tip_deger]
    deger = np.array([v for _, v in tip_deger], dtype=float)
    idx = pd.MultiIndex.from_arrays([df.kategori, df.beden_tipi])
    alt = sinir["min"].reindex(idx).to_numpy(dtype=float)
    ust = sinir["max"].reindex(idx).to_numpy(dtype=float)
    with np.errstate(invalid="ignore"):
        aralik = np.where(ust > alt, ust - alt, np.nan)          # tek bedenli ürünlerde konum tanımsız (NaN)
        df["beden_konum"] = np.clip((deger - alt) / aralik, 0, 1)
    df["beden_sinirda"] = ((df.beden_konum == 0) | (df.beden_konum == 1)).astype(float)
    df.loc[df.beden_konum.isna(), "beden_sinirda"] = np.nan


# ====================================================
# 3) GEÇMİŞ (AS-OF) SAYAÇLARI
# ====================================================

def _onceki_sayi(olay_anahtar, olay_zaman, olay_agirlik, sorgu_anahtar, sorgu_zaman):
    """Her sorgu (anahtar, zaman) için aynı anahtarlı ve zamanı KESİNLİKLE ÖNCE olan olayların ağırlık toplamı."""
    sonuc = np.zeros(len(sorgu_anahtar))
    olaylar = pd.DataFrame({"a": olay_anahtar, "z": olay_zaman, "w": olay_agirlik}).dropna(subset=["a", "z"])
    sorgular = pd.DataFrame({"a": sorgu_anahtar, "z": sorgu_zaman, "i": np.arange(len(sorgu_anahtar))})
    gruplar = {a: g.sort_values("z") for a, g in olaylar.groupby("a")}
    for a, s in sorgular.dropna(subset=["a"]).groupby("a"):
        g = gruplar.get(a)
        if g is None:
            continue
        kumulatif = np.concatenate([[0.0], g.w.cumsum().to_numpy()])
        konum = np.searchsorted(g.z.to_numpy(), s.z.to_numpy(), side="left")   # eşit zaman dahil değil
        sonuc[s.i.to_numpy()] = kumulatif[konum]
    return sonuc


def _gecmis_ozellikleri(veri, df):
    """Ürün, kategori ve müşteri geçmişi — yalnızca sipariş anından önceki olaylar.

    Ürün satış/iade geçmişi cari hesaptan (finans_hareketleri: teslimde Satış, kabulde İade) alınır; gerçek veride
    siparişlerden 9 ay daha eskiye gider. İade nedeni geçmişi iade taleplerinden (kabul edilenler, kabul anında).
    """
    t = m.tablolar(veri)
    u = t["urunler"].drop_duplicates("barkod").set_index("barkod")
    zaman = df.siparis_tarihi

    f = t["finans_hareketleri"]
    f = f.assign(model_kodu=f.barkod.map(u.model_kodu), kategori=f.barkod.map(u.kategori))
    satis, iade = f[f.islem_turu == "Satış"], f[f.islem_turu == "İade"]
    for seviye in ["kategori", "model_kodu"]:
        df[f"_{seviye}_satis"] = _onceki_sayi(satis[seviye], satis.islem_tarihi, 1.0, df[seviye], zaman)
        df[f"_{seviye}_iade"] = _onceki_sayi(iade[seviye], iade.islem_tarihi, 1.0, df[seviye], zaman)

    df["kategori_onceki_iade_orani"] = ((df._kategori_iade + KATEGORI_GUCU * ONSEL_IADE)
                                        / (df._kategori_satis + KATEGORI_GUCU))
    df["model_onceki_iade_orani"] = ((df._model_kodu_iade + MODEL_GUCU * df.kategori_onceki_iade_orani)
                                     / (df._model_kodu_satis + MODEL_GUCU))
    df["model_onceki_satis_log"] = np.log1p(df._model_kodu_satis)

    i = t["iadeler"]
    # Payda (satış) finans kayıtlarından geldiği için iadeler de yalnızca finansın kapsadığı dönemden sayılır;
    # yoksa gerçek veride 2024'ten beri gelen iadeler 2025 sonrası satışlara bölünüp oranı şişirir.
    kabul = i[(i.durum == "Accepted") & (i.neden_grubu != "teslim_edilemedi")
              & (i.son_guncelleme >= f.islem_tarihi.min())]
    kabul = kabul.assign(model_kodu=kabul.barkod.map(u.model_kodu))
    for neden, ad in [("beden_kucuk", "kucuk"), ("beden_buyuk", "buyuk")]:
        k = kabul[kabul.neden_grubu == neden]
        say = _onceki_sayi(k.model_kodu, k.son_guncelleme, 1.0, df.model_kodu, zaman)
        df[f"model_onceki_{ad}_orani"] = say / (df._model_kodu_satis + MODEL_GUCU)

    y = t["urun_yorumlari"].assign(model_kodu=lambda x: x.icerik_id.map(
        u.dropna(subset=["icerik_id"]).drop_duplicates("icerik_id").set_index("icerik_id").model_kodu))
    yorum_say = _onceki_sayi(y.model_kodu, y.yorum_tarihi, 1.0, df.model_kodu, zaman)
    puan_top = _onceki_sayi(y.model_kodu, y.yorum_tarihi, y.puan.astype(float), df.model_kodu, zaman)
    df["model_onceki_puan"] = (puan_top + 5 * 4.0) / (yorum_say + 5)      # 4,0 puana doğru düzeltilmiş ortalama
    df["model_onceki_yorum_log"] = np.log1p(yorum_say)

    # Müşteri geçmişi siparişlerden (gerçek veride Temmuz 2026'dan beri)
    s = m.cerceveler(veri)["satis"]
    gecerli = s[~s.iptal].drop_duplicates("paket_id")
    df["musteri_onceki_siparis"] = _onceki_sayi(gecerli.musteri_id, gecerli.siparis_tarihi, 1.0, df.musteri_id, zaman)
    teslim = s[s.teslim_tarihi.notna()]
    m_teslim = _onceki_sayi(teslim.musteri_id, teslim.teslim_tarihi, teslim.adet.astype(float), df.musteri_id, zaman)
    kabul_m = kabul.merge(s[["satir_id", "musteri_id"]].drop_duplicates("satir_id"), on="satir_id")
    m_iade = _onceki_sayi(kabul_m.musteri_id, kabul_m.son_guncelleme, 1.0, df.musteri_id, zaman)
    df["musteri_onceki_iade_orani"] = (m_iade + 2 * ONSEL_IADE) / (m_teslim + 2)
    return df.drop(columns=[c for c in df.columns if c.startswith("_")])


# ====================================================
# 4) İADE VERİ SETİ (satır başına)
# ====================================================

@lru_cache(maxsize=2)
def iade_veri_seti(veri="sahte"):
    """Teslim edilmiş ve iadesi kesinleşmiş (teslimden OLGUNLASMA_GUN geçmiş) sipariş satırları; özellikler + etiket.

    iade         : satırda kabul edilmiş müşteri iadesi var mı (0/1)
    iade_nedeni  : yok, beden_kucuk, beden_buyuk, diger
    Önbellektedir: dönen tabloyu değiştirmeyin (kopya alın).
    """
    d = m.cerceveler(veri)["satis"]
    son = d.siparis_tarihi.max() - pd.Timedelta(days=m.OLGUNLASMA_GUN)
    df = d[~d.iptal & d.teslim_tarihi.notna() & (d.teslim_tarihi <= son)].copy()

    t = m.tablolar(veri)
    _beden_konumu(df, t["urunler"])
    df["renk_grubu"] = df.renk.map(renk_grubu)
    df["il_grubu"] = df.sehir.where(df.sehir.isin(BUYUK_ILLER), "Diğer")
    df["dogu_ili"] = df.sehir.isin(DOGU_ILLER).astype(float)
    df["fiyat_endeksi"] = df.birim_brut_fiyat / df.groupby("kategori").birim_brut_fiyat.transform("median")
    df["indirim_orani"] = 1 - df.birim_net_fiyat / df.birim_brut_fiyat
    kuponlu = t["siparis_indirimleri"].query("indirim_turu == 'magaza_kuponu'").paket_id
    df["kuponlu"] = df.paket_id.isin(kuponlu).astype(float)
    paket = d[~d.iptal].groupby("paket_id").agg(sepet_satir_sayisi=("satir_id", "size"),
                                                 _sepet_tutari=("satir_net_tutar", "sum"))
    df = df.join(paket, on="paket_id")
    df["sepet_tutari_endeksi"] = df._sepet_tutari / df._sepet_tutari.median()
    z = df.siparis_tarihi.dt
    df["hafta_gunu"], df["saat"], df["ay"] = z.dayofweek, z.hour, z.month
    df = _gecmis_ozellikleri(veri, df)

    kabul = t["iadeler"].query("durum == 'Accepted' and neden_grubu != 'teslim_edilemedi'")
    neden = kabul.groupby("satir_id").neden_grubu.agg(lambda s: s.mode().iat[0])
    df["iade"] = (df.iade_adet > 0).astype(int)
    df["iade_nedeni"] = np.where(df.iade == 0, "yok",
                                 df.satir_id.map(neden).replace({"begenmedim": "diger", "kusurlu": "diger",
                                                                 "yanlis_eksik_urun": "diger", "vazgecti": "diger"})
                                 .fillna("diger"))
    df.loc[~df.iade_nedeni.isin(["yok", "beden_kucuk", "beden_buyuk"]), "iade_nedeni"] = "diger"

    kimlik = ["satir_id", "paket_id", "musteri_id", "model_kodu", "icerik_id", "barkod", "beden", "renk",
              "siparis_tarihi", "teslim_tarihi"]
    return df[kimlik + KATEGORIK + SAYISAL + ETIKETLER].reset_index(drop=True)
