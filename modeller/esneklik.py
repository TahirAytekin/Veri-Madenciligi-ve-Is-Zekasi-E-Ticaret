"""İndirim (kupon) esnekliği (F2-10): ürün × hafta panelinde iki yönlü sabit etkili Poisson regresyonu.

    python -m modeller.esneklik

    log E[adet_it] = ürün_i + hafta_t + e · x_it,   x = −log(1 − indirim payı)

e: %10 ek indirim satışı (0,9)^−e katına çıkarır (senaryo simülatörüyle aynı tanım). Yöntem sahtede doğrulanır
(Seviye 1); gerçekte yalnızca test öncesi pencerede ölçülür ve sonraki haftalarda sınanır (Seviye 2). Kurallar:
docs/modeller/F2-10.md (önceden kayıt). Çıktı: ciktilar/<veri>/dogrulama/F2-10.json, ciktilar/<veri>/esneklik.json
"""
import json

import numpy as np
import pandas as pd

from analiz import metrikler as m
from hazirlama.kalibrasyon import PENCERE
from hazirlama.ortak import VERI
from modeller.ortak.degerlendir import CIKTILAR

MODEL_ID = "F2-10"
MIN_SATIS = 30
TASIMA_HAFTA = 4
BOOTSTRAP = 300
VARSAYIM = 1.5                      # bugünkü tavsiye ve senaryo varsayımı
SAHTE_TOHUMLAR = {42: "sahte", 1: "sahte_t1", 2: "sahte_t2"}


# ====================================================
# 1) PANEL
# ====================================================

def panel(veri, bas, bit):
    """Ürün × tam hafta: adet, kupon_payi, indirim_payi. Satışsız haftada pay en fazla TASIMA_HAFTA taşınır."""
    t = m.tablolar(veri)
    model = t["urunler"].drop_duplicates("barkod").set_index("barkod").model_kodu
    f = t["finans_hareketleri"]
    f = f[(f.islem_tarihi >= bas) & (f.islem_tarihi < bit) & f.kalem_id.notna()]
    satis = f[f.islem_turu == "Satış"].drop_duplicates("kalem_id").set_index("kalem_id")
    tutar = f[f.islem_turu.isin(["Kupon", "İndirim"])].pivot_table(index="kalem_id", columns="islem_turu",
                                                                   values="borc", aggfunc="sum")
    s = pd.DataFrame({"model_kodu": satis.barkod.map(model), "tarih": satis.islem_tarihi,
                      "liste": satis.alacak}).join(tutar).fillna({"Kupon": 0.0, "İndirim": 0.0})
    s = s[s.model_kodu.notna() & (s.liste > 0)]
    s["kupon_payi"] = (s.Kupon / s.liste).clip(0, 0.9)
    s["indirim_payi"] = ((s.Kupon + s["İndirim"]) / s.liste).clip(0, 0.9)
    s["hafta"] = s.tarih.dt.to_period("W-SUN").dt.start_time
    ilk = (bas + pd.Timedelta(days=(7 - bas.dayofweek) % 7)).normalize()
    son = (bit - pd.Timedelta(days=bit.dayofweek + 7)).normalize()
    s = s[(s.hafta >= ilk) & (s.hafta <= son)]
    w = s.groupby(["model_kodu", "hafta"]).agg(adet=("liste", "size"), kupon_payi=("kupon_payi", "mean"),
                                                indirim_payi=("indirim_payi", "mean")).reset_index()
    toplam = w.groupby("model_kodu").adet.sum()
    w = w[w.model_kodu.isin(toplam[toplam >= MIN_SATIS].index)]
    izgara = pd.MultiIndex.from_product([w.model_kodu.unique(), pd.date_range(ilk, son, freq="7D")],
                                        names=["model_kodu", "hafta"])
    p = w.set_index(["model_kodu", "hafta"]).reindex(izgara).reset_index()
    p["adet"] = p.adet.fillna(0)
    for c in ("kupon_payi", "indirim_payi"):
        p[c] = p.groupby("model_kodu")[c].ffill(limit=TASIMA_HAFTA)
    ilk_satis = p[p.adet > 0].groupby("model_kodu").hafta.min()
    p = p[p.hafta >= p.model_kodu.map(ilk_satis)]                         # ürün satışa girmeden önceki haftalar yok
    return p.dropna(subset=["kupon_payi"]).reset_index(drop=True)


# ====================================================
# 2) İKİ YÖNLÜ SABİT ETKİLİ POISSON
# ====================================================

def poisson_fe(y, urun, hafta, x, e=None, tur=500, tol=1e-9):
    """Ürün ve hafta sabit etkileri sırayla (kapalı form), e serbestse Newton adımıyla güncellenir.
    e verilirse sabit tutulur. (e, sapma) döner."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    ui, ni = np.unique(urun, return_inverse=True)[1], len(np.unique(urun))
    ti, nt = np.unique(hafta, return_inverse=True)[1], len(np.unique(hafta))
    a, d, e_ = np.zeros(ni), np.zeros(nt), (0.0 if e is None else float(e))
    for _ in range(tur):
        once = e_
        mu_a = np.exp(d[ti] + e_ * x)
        a = np.log(np.maximum(np.bincount(ui, y, ni), 1e-12) / np.bincount(ui, mu_a, ni))
        mu_d = np.exp(a[ui] + e_ * x)
        d = np.log(np.maximum(np.bincount(ti, y, nt), 1e-12) / np.bincount(ti, mu_d, nt))
        if e is None:
            mu = np.exp(a[ui] + d[ti] + e_ * x)
            e_ += np.sum((y - mu) * x) / max(np.sum(mu * x * x), 1e-12)
            if abs(e_ - once) < tol:
                break
    mu = np.exp(a[ui] + d[ti] + e_ * x)
    sapma = 2 * np.sum(np.where(y > 0, y * np.log(np.where(y > 0, y, 1) / mu), 0) - (y - mu))
    return e_, float(sapma)


def _x(p, sutun):
    return -np.log(1 - p[sutun].to_numpy())


def tahmin_et(p, sutun="kupon_payi"):
    return poisson_fe(p.adet, p.model_kodu, p.hafta, _x(p, sutun))[0]


def _yeniden_ornekle(p, rng):
    """Ürün kümeli bootstrap: ürünler yerine koyarak seçilir, tekrar eden ürün ayrı kimlik alır."""
    urunler = p.model_kodu.unique()
    secim = rng.choice(urunler, len(urunler))
    gruplar = dict(tuple(p.groupby("model_kodu")))
    return pd.concat([gruplar[u].assign(model_kodu=f"{u}#{k}") for k, u in enumerate(secim)], ignore_index=True)


def guven_araligi(p, sutun="kupon_payi", tekrar=BOOTSTRAP, tohum=0):
    rng = np.random.default_rng(tohum)
    degerler = [tahmin_et(_yeniden_ornekle(p, rng), sutun) for _ in range(tekrar)]
    return {"alt": float(np.percentile(degerler, 2.5)), "ust": float(np.percentile(degerler, 97.5))}


def olcum(p):
    sonuc = {"urun": int(p.model_kodu.nunique()), "hafta": int(p.hafta.nunique()), "satir": int(len(p)),
             "satis": float(p.adet.sum()),
             "ortalama_kupon_payi": float(np.average(p.kupon_payi, weights=p.adet + 1e-9)),
             "kupon_payi_std_urun_ici": float(p.groupby("model_kodu").kupon_payi.std().median())}
    for sutun in ("kupon_payi", "indirim_payi"):
        sonuc[sutun] = {"esneklik": tahmin_et(p, sutun), **guven_araligi(p, sutun)}
    return sonuc


# ====================================================
# 3) SEVİYE 1 VE 2
# ====================================================

def dogru_cevap(veri, p):
    """Panele giren ürünlerin gizli esnekliklerinin satış ağırlıklı ortalaması (sahte)."""
    g = pd.read_csv(VERI / veri / "dogru_cevaplar" / "modeller.csv", encoding="utf-8-sig").set_index("model_kodu")
    w = p.groupby("model_kodu").adet.sum()
    return float(np.average(g.fiyat_esnekligi.reindex(w.index), weights=w))


def sapma_testi(p, e_olculen, tekrar=BOOTSTRAP, tohum=0, sutun="kupon_payi"):
    """Test haftalarında: esneklik sabit (ölçülen / 0 / varsayım), ürün ve hafta etkileri yeniden kurulur."""
    adaylar = {"olculen": e_olculen, "sifir": 0.0, "varsayim": VARSAYIM}

    def sapmalar(q):
        x = _x(q, sutun)
        return {k: poisson_fe(q.adet, q.model_kodu, q.hafta, x, e=v)[1] for k, v in adaylar.items()}

    temel = sapmalar(p)
    rng = np.random.default_rng(tohum)
    farklar = {"olculen_eksi_sifir": [], "olculen_eksi_varsayim": []}
    for _ in range(tekrar):
        s = sapmalar(_yeniden_ornekle(p, rng))
        farklar["olculen_eksi_sifir"].append(s["olculen"] - s["sifir"])
        farklar["olculen_eksi_varsayim"].append(s["olculen"] - s["varsayim"])
    return {"sapma": temel, **{k: {"fark": temel["olculen"] - temel[k.split("_eksi_")[1]],
                                   "alt": float(np.percentile(v, 2.5)), "ust": float(np.percentile(v, 97.5))}
                               for k, v in farklar.items()},
            "urun": int(p.model_kodu.nunique()), "hafta": int(p.hafta.nunique()), "satis": float(p.adet.sum())}


def calistir():
    pb, pson = (pd.Timestamp(x) for x in PENCERE)
    sonuc = {"pencere": list(PENCERE), "seviye1": {}}
    for tohum, veri in SAHTE_TOHUMLAR.items():
        if not (VERI / veri / "siparisler.csv").exists():
            continue
        p = panel(veri, pb, pson)
        o = olcum(p)
        dogru = dogru_cevap(veri, p)
        k = o["kupon_payi"]
        o.update({"dogru_cevap": dogru, "aralikta": k["alt"] <= dogru <= k["ust"],
                  "yakin": abs(k["esneklik"] - dogru) <= 0.3})
        sonuc["seviye1"][tohum] = o
    sonuc["karar_seviye1"] = sum(v["aralikta"] or v["yakin"] for v in sonuc["seviye1"].values()) >= 2

    if (VERI / "gercek" / "siparisler.csv").exists():
        pencere = panel("gercek", pb, pson)
        g = olcum(pencere)
        bit = m.veri_araligi("gercek")[1] + pd.Timedelta(days=1)
        test = panel("gercek", pson, bit)
        t = sapma_testi(test, g["kupon_payi"]["esneklik"])
        sonuc["gercek"] = {"pencere": g, "test": t,
                           "test_donemi": [str(test.hafta.min().date()), str(test.hafta.max().date())]}
        sonuc["karar_seviye2"] = (t["olculen_eksi_sifir"]["ust"] < 0) and (g["kupon_payi"]["alt"] > 0)
        sonuc["karar"] = sonuc["karar_seviye1"] and sonuc["karar_seviye2"]
    klasor = CIKTILAR / ("gercek" if "gercek" in sonuc else "sahte") / "dogrulama"
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / f"{MODEL_ID}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2, default=float),
                                              encoding="utf-8")
    return sonuc


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(calistir(), ensure_ascii=False, indent=1, default=lambda x: round(float(x), 4)))
