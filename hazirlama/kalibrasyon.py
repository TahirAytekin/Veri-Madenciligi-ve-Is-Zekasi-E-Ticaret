"""Sahte veri kalibrasyonu (F1-06): iade yapısını özetleyen istatistikler (K1–K6), iki veride aynı kodla.

    python -m hazirlama.kalibrasyon            # gerçek (test öncesi pencere) ve sahte yan yana
    python -m hazirlama.kalibrasyon --tohumlar # sahte = sahte, sahte_t1, sahte_t2 ortalaması (gürültüyü azaltır)

Kural (docs/rapor/sahte_v2_kalibrasyon.md): gerçek veride yalnızca test öncesi pencere (PENCERE) kullanılır; test
penceresindeki siparişlere ait hiçbir istatistik sahte üreticiye girmez. Yalnızca toplu oranlar üretilir.
"""
import numpy as np
import pandas as pd

from analiz import metrikler as m
from modeller.ortak.ozellikler import _beden_konumu

PENCERE = ("2025-10-23", "2026-07-16")   # [başlangıç, bitiş): finans kayıtlarının başı – gerçek test penceresinin başı
MIN_KATEGORI_SATIS = 200
MIN_URUN_SATIS = 100
MIN_YARI_SATIS = 50
MIN_BEDEN_IADESI = 10
NEDEN_DORTLU = {"beden_kucuk": "beden_kucuk", "beden_buyuk": "beden_buyuk", "kusurlu": "urun_sorunu",
                "yanlis_eksik_urun": "urun_sorunu", "begenmedim": "diger", "vazgecti": "diger", "diger": "diger"}
KONUM_DILIMLERI = ["en_kucuk", "alt_yari", "ust_yari", "en_buyuk"]


# ====================================================
# 1) PENCEREDEKİ SATIŞ VE İADE BİRİMLERİ
# ====================================================

def _birimler(veri, pencere=PENCERE):
    """Pencerede satış ve iade birimleri (finans kayıtları) + kabul edilen iade talepleri; ürün bilgileriyle."""
    t = m.tablolar(veri)
    u = t["urunler"].drop_duplicates("barkod")
    katalog = u[["barkod", "kategori", "beden", "model_kodu"]].copy()
    _beden_konumu(katalog, u)
    katalog = katalog.set_index("barkod")

    bas, bit = (pd.Timestamp(x) for x in pencere)
    f = t["finans_hareketleri"]
    f = f[(f.islem_tarihi >= bas) & (f.islem_tarihi < bit) & f.islem_turu.isin(["Satış", "İade"])]
    f = f[["barkod", "islem_turu", "islem_tarihi"]].join(katalog, on="barkod").dropna(subset=["model_kodu"])

    i = t["iadeler"]
    i = i[(i.durum == "Accepted") & (i.neden_grubu != "teslim_edilemedi")
          & (i.son_guncelleme >= bas) & (i.son_guncelleme < bit)]
    i = i[["barkod", "neden_grubu"]].join(katalog, on="barkod").dropna(subset=["model_kodu"])
    return f.assign(iade=(f.islem_turu == "İade").astype(int), satis=(f.islem_turu == "Satış").astype(int)), i


def _oran(g):
    return g.iade.sum() / g.satis.sum() if g.satis.sum() else np.nan


# ====================================================
# 2) K1–K6
# ====================================================

def istatistikler(veri, pencere=PENCERE):
    f, talepler = _birimler(veri, pencere)
    sonuc = {"veri": veri, "pencere": list(pencere), "satis": int(f.satis.sum()), "iade": int(f.iade.sum())}

    # K1: genel iade oranı
    sonuc["K1_iade_orani"] = _oran(f)

    # K2: kategori iade oranları
    kat = f.groupby("kategori").agg(satis=("satis", "sum"), iade=("iade", "sum"))
    kat = kat[kat.satis >= MIN_KATEGORI_SATIS]
    sonuc["K2_kategori"] = {k: {"oran": r.iade / r.satis, "satis": int(r.satis)} for k, r in kat.iterrows()}

    # K3: ürünler arası gerçek fark (binom gürültüsü çıkarılmış std) ve iki yarı dönem arasındaki kalıcılık
    urun = f.groupby("model_kodu").agg(satis=("satis", "sum"), iade=("iade", "sum"))
    urun = urun[urun.satis >= MIN_URUN_SATIS]
    r = urun.iade / urun.satis
    gurultu = (r.mean() * (1 - r.mean()) / urun.satis).mean()
    sonuc["K3_urun_std"] = float(np.sqrt(max(r.var() - gurultu, 0)))
    sonuc["K3_urun_sayisi"] = int(len(urun))
    orta = pd.Timestamp(pencere[0]) + (pd.Timestamp(pencere[1]) - pd.Timestamp(pencere[0])) / 2
    yarilar = [f[f.islem_tarihi < orta], f[f.islem_tarihi >= orta]]
    y = pd.concat([g.groupby("model_kodu").agg(satis=("satis", "sum"), iade=("iade", "sum"))
                   .add_suffix(f"_{n}") for n, g in enumerate(yarilar)], axis=1).dropna()
    y = y[(y.satis_0 >= MIN_YARI_SATIS) & (y.satis_1 >= MIN_YARI_SATIS)]
    sonuc["K3_yari_donem_korelasyonu"] = float(np.corrcoef(y.iade_0 / y.satis_0, y.iade_1 / y.satis_1)[0, 1])
    sonuc["K3_yari_donem_urun"] = int(len(y))

    # K4: beden konumuna göre iade oranı
    k = f.dropna(subset=["beden_konum"])
    dilim = np.select([k.beden_konum == 0, k.beden_konum <= 0.5, k.beden_konum < 1], KONUM_DILIMLERI[:3],
                      KONUM_DILIMLERI[3])
    sonuc["K4_beden_konumu"] = {d: {"oran": _oran(g), "satis": int(g.satis.sum())}
                                for d, g in k.groupby(dilim) if d in KONUM_DILIMLERI}

    # K5: iade nedeni payları (kabul edilen talepler)
    dortlu = talepler.neden_grubu.map(NEDEN_DORTLU).fillna("diger")
    sonuc["K5_neden_paylari"] = dortlu.value_counts(normalize=True).reindex(
        ["beden_kucuk", "beden_buyuk", "diger", "urun_sorunu"], fill_value=0).to_dict()

    # K6: kalıp — beden iadesi yeterli ürünlerde "küçük geldi" payı
    b = talepler[talepler.neden_grubu.isin(["beden_kucuk", "beden_buyuk"])]
    pay = b.groupby("model_kodu").neden_grubu.agg(lambda x: (x == "beden_kucuk").mean())
    adet = b.groupby("model_kodu").size()
    pay = pay[adet >= MIN_BEDEN_IADESI]
    grup = np.select([pay >= 0.7, pay <= 0.3], ["cogunlukla_kucuk", "cogunlukla_buyuk"], "karisik")
    sonuc["K6_kalip"] = pd.Series(grup).value_counts(normalize=True).reindex(
        ["cogunlukla_kucuk", "karisik", "cogunlukla_buyuk"], fill_value=0).to_dict()
    sonuc["K6_urun_sayisi"] = int(len(pay))
    return sonuc


def ortalama(sonuclar):
    """Birden çok tohumla üretilmiş sahte verinin istatistiklerinin ortalaması (iç içe sözlüklerde de)."""
    def birlestir(degerler):
        if isinstance(degerler[0], dict):
            anahtarlar = set().union(*degerler)
            return {a: birlestir([d[a] for d in degerler if a in d]) for a in anahtarlar}
        if isinstance(degerler[0], (int, float, np.floating, np.integer)):
            return float(np.mean(degerler))
        return degerler[0]
    sonuc = birlestir(sonuclar)
    sonuc["veri"] = "+".join(s["veri"] for s in sonuclar)
    return sonuc


# ====================================================
# 3) KARŞILAŞTIRMA (başarı ölçütü A)
# ====================================================

def karsilastir(gercek, sahte):
    """Ölçüt A: her hedef için fark ve tolerans içinde mi (docs/rapor/sahte_v2_kalibrasyon.md)."""
    satirlar = [("K1", "iade oranı", sahte["K1_iade_orani"] - gercek["K1_iade_orani"], 0.01)]

    ortak = sorted(set(gercek["K2_kategori"]) & set(sahte["K2_kategori"]))
    g = pd.Series({k: gercek["K2_kategori"][k]["oran"] for k in ortak})
    s = pd.Series({k: sahte["K2_kategori"][k]["oran"] for k in ortak})
    w = pd.Series({k: gercek["K2_kategori"][k]["satis"] for k in ortak})
    satirlar.append(("K2", f"kategori ağırlıklı ort. mutlak fark ({len(ortak)} kategori)",
                     float(np.average((s - g).abs(), weights=w)), 0.02))
    satirlar.append(("K2", "kategori sıralama korelasyonu (alt sınır 0,7)", float(g.corr(s, method="spearman")),
                     None))

    satirlar.append(("K3", "ürünler arası std (göreli fark)", sahte["K3_urun_std"] / gercek["K3_urun_std"] - 1, 0.25))
    satirlar.append(("K3", "yarı dönem korelasyonu",
                     sahte["K3_yari_donem_korelasyonu"] - gercek["K3_yari_donem_korelasyonu"], 0.15))
    for d in KONUM_DILIMLERI:
        if d in gercek["K4_beden_konumu"] and d in sahte["K4_beden_konumu"]:
            satirlar.append(("K4", f"beden konumu: {d}",
                             sahte["K4_beden_konumu"][d]["oran"] - gercek["K4_beden_konumu"][d]["oran"], 0.02))
    for n, v in gercek["K5_neden_paylari"].items():
        satirlar.append(("K5", f"neden payı: {n}", sahte["K5_neden_paylari"][n] - v, 0.05))
    for n, v in gercek["K6_kalip"].items():
        satirlar.append(("K6", f"kalıp: {n}", sahte["K6_kalip"][n] - v, 0.10))

    t = pd.DataFrame(satirlar, columns=["hedef", "istatistik", "fark", "tolerans"])
    t["tutuyor"] = np.where(t.tolerans.isna(), t.fark >= 0.7, t.fark.abs() <= t.tolerans)
    return t


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 160)
    from hazirlama.ortak import VERI
    sahteler = ["sahte"] + ([f"sahte_t{t}" for t in (1, 2) if (VERI / f"sahte_t{t}").exists()]
                            if "--tohumlar" in sys.argv else [])
    sonuclar = {"gercek": istatistikler("gercek"), "sahte": ortalama([istatistikler(v) for v in sahteler])}
    print(json.dumps(sonuclar, ensure_ascii=False, indent=1, default=float))
    print(karsilastir(sonuclar["gercek"], sonuclar["sahte"]).round(4).to_string(index=False))
