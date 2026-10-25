"""Haftalık talep tahmini ve stok tükenme (F2-05). Ürün × hafta, LightGBM (Poisson), yalnızca sahte v2 ile eğitilir.

    python -m modeller.talep

Tasarım ve başarı ölçütü eğitimden önce docs/modeller/F2-05.md'ye yazıldı: hedef gelecek haftanın teslim edilen satış
adedi (finans 'Satış' kayıtları); referanslar naif (geçen hafta) ve ort4; ölçüt WAPE, ürün düzeyinde kümeli bootstrap;
3 sahte tohumun en az 2'sinde model en iyi referanstan anlamlı biçimde iyi olmalı.

Çıktılar (ciktilar/, git'e girmez):
    modeller/F2-05.joblib                     model (tohum 42)
    <veri>/tahminler/F2-05.csv                test haftalarında ürün başına tahmin ve gerçekleşen
    <veri>/tahminler/F2-05_stok.csv           ürün başına haftalık satış hızı, stok ve tükenme tarihi
    <veri>/dogrulama/F2-05.json               ölçütler
"""
import json

import lightgbm as lgb
import numpy as np
import pandas as pd

from analiz import metrikler as m
from hazirlama.ortak import VERI, ozel_gunler
from modeller import iade_riski as gbm
from modeller.ortak.degerlendir import CIKTILAR
from modeller.ortak.kayit import model_kaydet, tahmin_kaydet

MODEL_ID = "F2-05"
SAHTE_TOHUMLAR = {42: "sahte", 1: "sahte_t1", 2: "sahte_t2"}
DOGRULAMA_HAFTA = 13
TEST_HAFTA = 6
AKTIF_HAFTA = 12
TEMSILI_STOK = 900          # varyant stoğu bu ve üstüyse sembolik kabul edilir (bkz. stok_tablosu)
GECMIS = ["gecen_hafta", "iki_hafta_once", "uc_hafta_once", "dort_hafta_once", "ort4", "ort8", "ort12"]
OZELLIKLER = GECMIS + ["hafta_sayisi", "fiyat_endeksi", "magaza_payi", "ozel_gun"]
PARAMETRELER = dict(gbm.PARAMETRELER, objective="poisson", metric="poisson")


# ====================================================
# 1) HAFTALIK SERİ VE ÖZELLİKLER
# ====================================================

def haftalik_seri(veri):
    """Ürün × tam hafta teslim edilen satış adedi ve ortalama birim tutar (finans 'Satış'); satışsız haftalar 0."""
    t = m.tablolar(veri)
    urun = t["urunler"].drop_duplicates("barkod").set_index("barkod").model_kodu
    f = t["finans_hareketleri"]
    son_an = f.islem_tarihi.max()
    s = f[f.islem_turu == "Satış"].assign(model_kodu=lambda x: x.barkod.map(urun)).dropna(subset=["model_kodu"])
    s = s.assign(hafta=s.islem_tarihi.dt.to_period("W-SUN").dt.start_time)
    son_tam = son_an.to_period("W-SUN").start_time                  # son kaydın bulunduğu hafta
    if son_an < son_tam + pd.Timedelta(days=7) - pd.Timedelta(seconds=1):   # o hafta bitmeden veri kesildiyse
        son_tam -= pd.Timedelta(weeks=1)
    s = s[s.hafta <= son_tam]
    w = s.groupby(["model_kodu", "hafta"]).agg(adet=("alacak", "size"), tutar=("alacak", "mean")).reset_index()
    ilk = w.groupby("model_kodu").hafta.min()
    izgara = pd.concat([pd.DataFrame({"model_kodu": k, "hafta": pd.date_range(h, son_tam, freq="7D")})
                        for k, h in ilk.items()])
    return izgara.merge(w, on=["model_kodu", "hafta"], how="left").fillna({"adet": 0}).sort_values(
        ["model_kodu", "hafta"]).reset_index(drop=True)


def _ozel_gun_sayisi(haftalar):
    gunler = ozel_gunler(haftalar.min().date(), (haftalar.max() + pd.Timedelta(days=6)).date())
    return haftalar.map(lambda h: sum((h + pd.Timedelta(days=i)).date() in gunler for i in range(7)))


def ozellik_ekle(d):
    """Her satır (ürün, hedef hafta T) için yalnızca T'den önceki haftalardan özellikler; aktif olmayanlar çıkarılır."""
    d = d.sort_values(["model_kodu", "hafta"]).reset_index(drop=True)
    g = d.groupby("model_kodu")
    gecmis = g.adet.shift(1)
    d["gecen_hafta"] = gecmis
    d["iki_hafta_once"], d["uc_hafta_once"], d["dort_hafta_once"] = (g.adet.shift(k) for k in (2, 3, 4))
    for n in (4, 8, 12):
        d[f"ort{n}"] = gecmis.groupby(d.model_kodu).transform(lambda x, n=n: x.rolling(n, min_periods=1).mean())
    d["hafta_sayisi"] = np.minimum(g.cumcount(), 52)
    onceki_tutar = g.tutar.shift(1)
    d["fiyat_endeksi"] = onceki_tutar / onceki_tutar.groupby(d.model_kodu).transform(
        lambda x: x.shift(1).rolling(12, min_periods=1).mean())
    magaza = d.groupby("hafta").adet.sum().sort_index()
    d["magaza_payi"] = d.ort4 / d.hafta.map(magaza.shift(1).rolling(4, min_periods=1).mean())
    d["ozel_gun"] = _ozel_gun_sayisi(d.hafta)
    son12 = gecmis.groupby(d.model_kodu).transform(lambda x: x.rolling(AKTIF_HAFTA, min_periods=1).sum())
    return d[d.gecen_hafta.notna() & (son12 > 0)].reset_index(drop=True)   # en az bir hafta geçmiş, aktif ürün


def talep_veri_seti(veri):
    return ozellik_ekle(haftalik_seri(veri))


def son_haftalar(d, n):
    sinir = d.hafta.max() - pd.Timedelta(weeks=n - 1)
    return d[d.hafta < sinir], d[d.hafta >= sinir]


# ====================================================
# 2) MODEL VE REFERANSLAR
# ====================================================

def varyantlar():
    return {"gbm": False, "gbm_monoton": True}


def egit(egitim, dogrulama, monoton):
    params = dict(PARAMETRELER)
    if monoton:
        params["monotone_constraints"] = [1 if c in GECMIS else 0 for c in OZELLIKLER]
        params["monotone_constraints_method"] = "advanced"
    model = lgb.LGBMRegressor(**params)
    model.fit(egitim[OZELLIKLER], egitim.adet, eval_set=[(dogrulama[OZELLIKLER], dogrulama.adet)],
              callbacks=[lgb.early_stopping(100, verbose=False)])
    return model, params


def tahmin(model, df):
    return model.predict(df[OZELLIKLER])


def referanslar(df):
    return {"naif": df.gecen_hafta.to_numpy(), "ort4": df.ort4.to_numpy()}


def wape(y, p):
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    return float(np.abs(y - p).sum() / y.sum())


def kumeli_wape_farki(df, p1, p2, tekrar=1000, tohum=0):
    """WAPE(p1) − WAPE(p2); ürünler yeniden örneklenir (aynı ürünün haftaları birlikte)."""
    t = pd.DataFrame({"k": df.model_kodu.to_numpy(), "y": df.adet.to_numpy(dtype=float),
                      "h1": np.abs(df.adet.to_numpy() - p1), "h2": np.abs(df.adet.to_numpy() - p2)})
    u = t.groupby("k")[["y", "h1", "h2"]].sum()
    rng = np.random.default_rng(tohum)
    farklar = []
    for _ in range(tekrar):
        o = u.iloc[rng.integers(0, len(u), len(u))]
        farklar.append((o.h1.sum() - o.h2.sum()) / o.y.sum())
    return {"fark": float((u.h1.sum() - u.h2.sum()) / u.y.sum()), "alt": float(np.percentile(farklar, 2.5)),
            "ust": float(np.percentile(farklar, 97.5))}


def magaza_wape(df, p):
    t = pd.DataFrame({"hafta": df.hafta.to_numpy(), "y": df.adet.to_numpy(dtype=float), "p": p})
    h = t.groupby("hafta")[["y", "p"]].sum()
    return wape(h.y, h.p)


def kahin(veri, df, egitim):
    """Seviye 1: üreticinin gizli beklenen talebi; medyan teslimat gecikmesi kadar kaydırılır ve sahte eğitim
    döneminde ölçülen tek bir oranla ölçeklenir (tamamlayıcı ürünler, iptaller)."""
    t = m.tablolar(veri)["siparisler"]
    gecikme = int(round((t.teslim_tarihi - t.siparis_tarihi).dt.total_seconds().dropna().median() / 86400))
    g = pd.read_csv(VERI / veri / "dogru_cevaplar" / "gunluk_talep.csv", encoding="utf-8-sig", parse_dates=["tarih"])
    g["hafta"] = (g.tarih + pd.Timedelta(days=gecikme)).dt.to_period("W-SUN").dt.start_time
    h = g.groupby(["model_kodu", "hafta"]).beklenen_adet.sum()
    def eslestir(x):
        return pd.MultiIndex.from_arrays([x.model_kodu, x.hafta]).map(h).fillna(0).to_numpy()
    oran = egitim.adet.sum() / eslestir(egitim).sum()
    return eslestir(df) * oran, gecikme


# ====================================================
# 3) ÇALIŞTIR
# ====================================================

def _olc(df, p, ref):
    en_iyi = min(ref, key=lambda r: wape(df.adet, ref[r]))
    return {"wape": wape(df.adet, p), **{f"wape_{r}": wape(df.adet, v) for r, v in ref.items()},
            "en_iyi_referans": en_iyi, "fark_en_iyi_referans": kumeli_wape_farki(df, p, ref[en_iyi]),
            "magaza_wape": magaza_wape(df, p), **{f"magaza_wape_{r}": magaza_wape(df, v) for r, v in ref.items()},
            "satir": int(len(df)), "urun": int(df.model_kodu.nunique()), "toplam_adet": float(df.adet.sum()),
            "toplam_tahmin": float(np.sum(p))}


def _ilk10(df, p):
    t = df.assign(p=p)
    ust = t.groupby("model_kodu").adet.sum().nlargest(10).index
    s = t[t.model_kodu.isin(ust)]
    return {"wape": wape(s.adet, s.p), "wape_naif": wape(s.adet, s.gecen_hafta), "wape_ort4": wape(s.adet, s.ort4)}


def stok_tablosu(veri, model):
    """Son tam haftadan sonraki hafta için tahmin ve stokun kaç hafta yeteceği (doğrulanmaz; bkz. model kartı)."""
    d = haftalik_seri(veri)
    gelecek = d.hafta.max() + pd.Timedelta(weeks=1)
    # Gelecek haftanın satırı: adedi bilinmez (0 yazılır); özellikler yalnızca önceki haftalardan hesaplandığı için
    # tahmini etkilemez
    d = ozellik_ekle(pd.concat([d, d[["model_kodu"]].drop_duplicates().assign(hafta=gelecek, adet=0.0)]))
    d = d[d.hafta == gelecek].copy()
    d["tahmin_model"] = tahmin(model, d)
    # Stok hızı: gerçek testte en iyi çıkan referans (geçen haftanın satışı; o hafta satış yoksa son 4 hafta
    # ortalaması). Model gerçekte bu referanstan kötü olduğu için stok kararında kullanılmaz (bkz. model kartı).
    d["haftalik_hiz"] = np.where(d.gecen_hafta > 0, d.gecen_hafta, d.ort4)
    # Temsili stok: satıcıların tedarik ettikçe gönderdiği ürünlere yazdığı sembolik stok (gerçekte varyantların
    # çoğu 1000, 999, 998 ...). Böyle bir varyantı olan üründe stok süresi hesaplanmaz.
    u = m.tablolar(veri)["urunler"].assign(temsili=lambda x: x.stok >= TEMSILI_STOK)
    u = u.groupby("model_kodu").agg(stok=("stok", "sum"), temsili_stok=("temsili", "any"),
                                    kategori=("kategori", "first"))
    d = d.join(u, on="model_kodu")
    d["stok_hafta"] = (d.stok / np.maximum(d.haftalik_hiz, 0.01)).where(~d.temsili_stok.fillna(False))
    d["tukenme_tarihi"] = (d.hafta + pd.to_timedelta(d.stok_hafta.clip(upper=520) * 7, unit="D")).dt.date
    return d[["model_kodu", "kategori", "hafta", "haftalik_hiz", "gecen_hafta", "ort4", "tahmin_model", "stok",
              "temsili_stok", "stok_hafta", "tukenme_tarihi"]].sort_values("stok_hafta").round(3)


def calistir():
    gercek_var = (VERI / "gercek" / "siparisler.csv").exists()
    test = son_haftalar(talep_veri_seti("gercek"), TEST_HAFTA)[1] if gercek_var else None
    sonuc = {"seviye1": {}, "gercek": {}}
    son_modeller = {}
    for tohum, veri in SAHTE_TOHUMLAR.items():
        if not (VERI / veri / "siparisler.csv").exists():
            print(f"atlandı (veri yok): {veri}")
            continue
        sahte = talep_veri_seti(veri)
        egitim, dogrulama = son_haftalar(sahte, DOGRULAMA_HAFTA)
        adaylar = {}
        for ad, monoton in varyantlar().items():
            model, params = egit(egitim, dogrulama, monoton)
            adaylar[ad] = (model, params, wape(dogrulama.adet, tahmin(model, dogrulama)))
        secilen = min(adaylar, key=lambda a: adaylar[a][2])       # yalnızca sahte doğrulama WAPE'si
        model, params, _ = adaylar[secilen]
        p_kahin, gecikme = kahin(veri, dogrulama, egitim)
        s1 = _olc(dogrulama, tahmin(model, dogrulama), referanslar(dogrulama))
        s1.update({"secilen": secilen, "varyant_wape": {a: v[2] for a, v in adaylar.items()},
                   "kahin_wape": wape(dogrulama.adet, p_kahin), "teslim_gecikmesi_gun": gecikme,
                   "agac": int(model.best_iteration_)})
        sonuc["seviye1"][tohum] = s1
        son = lgb.LGBMRegressor(**dict(params, n_estimators=max(int(model.best_iteration_), 1)))
        son.fit(sahte[OZELLIKLER], sahte.adet)
        son_modeller[tohum] = son
        if test is not None:
            p = tahmin(son, test)
            sonuc["gercek"][tohum] = {**_olc(test, p, referanslar(test)), "secilen": secilen, "ilk10": _ilk10(test, p),
                                      "varyantlar_gercek_wape": {   # şeffaflık: seçimde kullanılmadı
                                          a: wape(test.adet, tahmin(v[0], test)) for a, v in adaylar.items()}}
            if tohum == 42:
                tahmin_kaydet(test[["model_kodu", "hafta", "adet", "gecen_hafta", "ort4"]].assign(
                    tahmin=p.round(3)), MODEL_ID, "gercek")

    if test is not None:
        sonuc["karar"] = sum(v["fark_en_iyi_referans"]["ust"] < 0 for v in sonuc["gercek"].values()) >= 2
        sonuc["test_haftalari"] = [str(h.date()) for h in sorted(test.hafta.unique())]

    model_kaydet({"model": son_modeller[42], "ozellikler": OZELLIKLER}, MODEL_ID)
    for veri in ["sahte"] + (["gercek"] if gercek_var else []):
        tahmin_kaydet(stok_tablosu(veri, son_modeller[42]), f"{MODEL_ID}_stok", veri)
    klasor = CIKTILAR / ("gercek" if gercek_var else "sahte") / "dogrulama"
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / f"{MODEL_ID}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2, default=float),
                                              encoding="utf-8")
    return sonuc


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(calistir(), ensure_ascii=False, indent=1, default=lambda x: round(float(x), 4)))
