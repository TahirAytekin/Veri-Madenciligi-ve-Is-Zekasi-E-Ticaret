"""Sahte veri v3 kalibrasyonu (geliştirme turu 2): talep dinamiği ve iade eğilimi istatistikleri (D1–D5).

    python -m hazirlama.kalibrasyon_talep                    # gerçek (test öncesi pencere) ve sahte yan yana
    python -m hazirlama.kalibrasyon_talep --sahte sahte_v3   # başka bir sahte klasörü (tohum ortalaması: --tohumlar)

F1-06 ile aynı kural: gerçek veride yalnızca test öncesi pencere (kalibrasyon.PENCERE) kullanılır; yalnızca toplu
sayılar üretilir. Satış = teslim edilen birim (finans 'Satış' kayıtları), ürün × tam hafta. Tasarım ve toleranslar:
docs/rapor/sahte_v3_talep.md (önceden kayıt).

    D1  WAPE(geçen hafta) / WAPE(son 4 hafta ort.)   < 1: talep kalıcı sıçrar (geçen hafta daha iyi tahmin)
    D2  ürün içi haftalık satışın 1 gecikmeli otokorelasyonu (medyan)
    D3  satış yoğunlaşması: en çok satan %10 ürünün payı; ürün-hafta satışının 99. yüzdeliği
    D4  iade oranı eğilimi: pencerenin son 3 ayı / ilk 3 ayı (finans İade / Satış)
    D5  mağaza haftalık satışının değişkenlik katsayısı
"""
import numpy as np
import pandas as pd

from analiz import metrikler as m
from hazirlama.kalibrasyon import PENCERE, ortalama

MIN_URUN_SATIS = 30            # D1, D2: pencerede en az bu kadar satışı olan ürünler
MIN_HAFTA = 12                 # D2: en az bu kadar haftalık gözlemi olan ürünler


# ====================================================
# 1) HAFTALIK SERİ (pencere içinde)
# ====================================================

def _finans(veri, pencere=PENCERE):
    t = m.tablolar(veri)
    model = t["urunler"].drop_duplicates("barkod").set_index("barkod").model_kodu
    bas, bit = (pd.Timestamp(x) for x in pencere)
    f = t["finans_hareketleri"]
    f = f[(f.islem_tarihi >= bas) & (f.islem_tarihi < bit) & f.islem_turu.isin(["Satış", "İade"])]
    return f.assign(model_kodu=f.barkod.map(model)).dropna(subset=["model_kodu"]), bas, bit


def haftalik(veri, pencere=PENCERE):
    """Ürün × tam hafta satış adedi; satışsız haftalar 0 (ürünün penceredeki ilk satışından itibaren)."""
    f, bas, bit = _finans(veri, pencere)
    s = f[f.islem_turu == "Satış"]
    ilk_hafta = (bas + pd.Timedelta(days=(7 - bas.dayofweek) % 7)).normalize()          # ilk tam pazartesi
    son_hafta = (bit - pd.Timedelta(days=bit.dayofweek + 7)).normalize()                # son tam hafta
    s = s.assign(hafta=s.islem_tarihi.dt.to_period("W-SUN").dt.start_time)
    s = s[(s.hafta >= ilk_hafta) & (s.hafta <= son_hafta)]
    w = s.groupby(["model_kodu", "hafta"]).size().rename("adet").reset_index()
    ilk = w.groupby("model_kodu").hafta.min()
    izgara = pd.concat([pd.DataFrame({"model_kodu": k, "hafta": pd.date_range(h, son_hafta, freq="7D")})
                        for k, h in ilk.items()])
    return izgara.merge(w, on=["model_kodu", "hafta"], how="left").fillna({"adet": 0}).sort_values(
        ["model_kodu", "hafta"]).reset_index(drop=True)


# ====================================================
# 2) D1–D5
# ====================================================

def _wape(y, p):
    return float(np.abs(y - p).sum() / y.sum())


def istatistikler(veri, pencere=PENCERE):
    d = haftalik(veri, pencere)
    toplam = d.groupby("model_kodu").adet.sum()
    secili = d[d.model_kodu.isin(toplam[toplam >= MIN_URUN_SATIS].index)].copy()
    g = secili.groupby("model_kodu").adet
    secili["naif"] = g.shift(1)
    secili["ort4"] = g.transform(lambda x: x.shift(1).rolling(4, min_periods=4).mean())
    t = secili.dropna(subset=["naif", "ort4"])
    t = t[t.ort4 > 0]                                              # aktif ürün-haftaları

    otokor = []
    for _, x in secili.groupby("model_kodu").adet:
        if len(x) >= MIN_HAFTA and x.std() > 0:
            otokor.append(x.autocorr(1))
    pay = toplam.sort_values(ascending=False)
    ilk10 = pay.head(max(1, int(np.ceil(len(pay) * 0.10)))).sum() / pay.sum()

    f, bas, bit = _finans(veri, pencere)
    ilk3 = f[f.islem_tarihi < bas + pd.DateOffset(months=3)]
    son3 = f[f.islem_tarihi >= bit - pd.DateOffset(months=3)]

    def iade_orani(x):
        satis = (x.islem_turu == "Satış").sum()
        return (x.islem_turu == "İade").sum() / satis if satis else np.nan

    magaza = d.groupby("hafta").adet.sum()
    return {
        "veri": veri, "pencere": list(pencere), "urun": int(len(toplam)), "urun_d1": int(t.model_kodu.nunique()),
        "urun_hafta": int(len(t)),
        "D1_naif_ort4_orani": _wape(t.adet, t.naif) / _wape(t.adet, t.ort4),
        "D1_wape_naif": _wape(t.adet, t.naif), "D1_wape_ort4": _wape(t.adet, t.ort4),
        "D2_otokorelasyon": float(np.nanmedian(otokor)) if otokor else None, "D2_urun": len(otokor),
        "D3_ilk10_payi": float(ilk10), "D3_p99_urun_hafta": float(d[d.adet > 0].adet.quantile(0.99)),
        "D3_magaza_haftalik_medyan": float(magaza.median()),
        "D4_iade_egilimi": float(iade_orani(son3) / iade_orani(ilk3)),
        "D4_iade_ilk3": float(iade_orani(ilk3)), "D4_iade_son3": float(iade_orani(son3)),
        "D5_magaza_cv": float(magaza.std() / magaza.mean()),
    }


# ====================================================
# 3) KARŞILAŞTIRMA (ölçüt A, docs/rapor/sahte_v3_talep.md)
# ====================================================

TOLERANS = {   # (istatistik, açıklama, tür, tolerans): "goreli" → |s/g − 1| ≤ t, "mutlak" → |s − g| ≤ t
    "D1_naif_ort4_orani": ("geçen hafta / 4 hafta ort. WAPE oranı", "mutlak", 0.05),
    "D2_otokorelasyon": ("haftalık otokorelasyon (medyan)", "mutlak", 0.10),
    "D3_ilk10_payi": ("en çok satan %10 ürünün payı", "mutlak", 0.08),
    "D3_p99_urun_hafta": ("ürün-hafta satışı 99. yüzdelik", "goreli", 0.30),
    "D3_magaza_haftalik_medyan": ("mağaza haftalık satış medyanı", "goreli", 0.25),
    "D4_iade_egilimi": ("iade oranı: son 3 ay / ilk 3 ay", "goreli", 0.25),
    "D5_magaza_cv": ("mağaza haftalık satış değişkenliği", "mutlak", 0.10),
}


def karsilastir(gercek, sahte):
    satirlar = []
    for k, (aciklama, tur, tol) in TOLERANS.items():
        g, s = gercek[k], sahte[k]
        fark = s / g - 1 if tur == "goreli" else s - g
        satirlar.append({"hedef": k.split("_")[0], "istatistik": aciklama, "gercek": g, "sahte": s, "fark": fark,
                         "tolerans": tol, "tutuyor": abs(fark) <= tol})
    return pd.DataFrame(satirlar)


if __name__ == "__main__":
    import json
    import sys

    from hazirlama.ortak import VERI
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 180)
    taban = sys.argv[sys.argv.index("--sahte") + 1] if "--sahte" in sys.argv else "sahte"
    sahteler = [taban] + ([f"{taban}_t{t}" for t in (1, 2) if (VERI / f"{taban}_t{t}").exists()]
                          if "--tohumlar" in sys.argv else [])
    g = istatistikler("gercek")
    s = ortalama([istatistikler(v) for v in sahteler])
    print(json.dumps({"gercek": g, "sahte": s}, ensure_ascii=False, default=float))
    print(karsilastir(g, s).round(4).to_string(index=False))
