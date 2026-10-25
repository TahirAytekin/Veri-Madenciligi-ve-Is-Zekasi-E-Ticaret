"""Beden uyumu (F2-04): kalıp skoru, beden iadesinin yönü ve boy-kiloya göre beden önerisi. Sahte v2 ile eğitilir.

    python -m modeller.beden_uyumu

Tasarım ve başarı ölçütleri eğitimden önce docs/modeller/F2-04.md'ye yazıldı:
    A  kalip_skoru      ürünün o güne kadarki beden iadelerinde "küçük geldi" payı (Beta yumuşatma; eğitimsiz)
    B  yön modeli       P(küçük geldi | beden iadesi), LightGBM, kalıp skorunda artan monoton
    C  beden_oner()     boy + kilo -> harf beden (doğrusal regresyon, en yakın bedene yuvarlanır)
Her eğitimli parça sahte v2'nin 3 tohumuyla ayrı ayrı eğitilir ve gerçek test penceresinde ölçülür.

Çıktılar (ciktilar/, git'e girmez):
    modeller/F2-04.joblib                     yön modeli + beden önerisi katsayıları (tohum 42)
    <veri>/tahminler/F2-04_kalip.csv          ürün başına güncel kalıp skoru ve kalıp etiketi
    <veri>/dogrulama/F2-04.json               A, B, C ölçütleri
"""
import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from analiz import metrikler as m
from hazirlama.ortak import VERI
from modeller import iade_riski as gbm
from modeller.ortak.degerlendir import CIKTILAR, bootstrap_auc_farki, sahte_bol, siniflandirma_olcutleri
from modeller.ortak.kayit import model_kaydet, model_yukle, tahmin_kaydet
from modeller.ortak.ozellikler import HARF_SIRASI, _onceki_sayi, beden_degeri, iade_veri_seti

MODEL_ID = "F2-04"
SAHTE_TOHUMLAR = {42: "sahte", 1: "sahte_t1", 2: "sahte_t2"}
TEST_BASLANGIC = pd.Timestamp("2026-07-16")       # gerçek test penceresinin başı (F2-02 ile aynı)
ONSEL_GUCU = 5             # kalıp skoru: mağaza payına doğru kaç iadelik çekim
ORAN_GUCU = 20             # beden iadesi oranı: mağaza oranına doğru kaç satışlık çekim
VARSAYILAN_KUCUK_PAYI = 0.65
MIN_KALIP_IADESI = 3       # Seviye 1: skoru değerlendirilen ürünlerde en az bu kadar beden iadesi
DAR_ESIGI, BOL_ESIGI, ETIKET_MIN_IADE = 0.80, 0.30, 5   # kalıp etiketi ve öneri düzeltmesi (eğitimden önce sabit)
MAKUL_BOY, MAKUL_KILO = (140, 210), (35, 200)
HARF_ADI = {v: k for k, v in reversed(list(HARF_SIRASI.items()))}   # 7 -> "2XL" (ilk yazım tercih edilir)

YON_KATEGORIK = ["kategori", "beden_tipi"]
YON_SAYISAL = ["kalip_skoru", "beden_iade_orani", "beden_konum", "beden_sinirda", "fiyat_endeksi"]
YON_MONOTON = ["kalip_skoru"]


# ====================================================
# 1) A — KALIP SKORU (sipariş anına kadarki beden iadeleri)
# ====================================================

def _beden_olaylari(veri):
    """Kabul edilen beden iadeleri (kabul anında) ve satışlar; finansın kapsadığı dönemle sınırlı (ozellikler.py
    ile aynı)."""
    t = m.tablolar(veri)
    model = t["urunler"].drop_duplicates("barkod").set_index("barkod").model_kodu
    f = t["finans_hareketleri"]
    satis = f[f.islem_turu == "Satış"].assign(model_kodu=lambda x: x.barkod.map(model))
    i = t["iadeler"]
    beden = i[(i.durum == "Accepted") & i.neden_grubu.isin(["beden_kucuk", "beden_buyuk"])
              & (i.son_guncelleme >= f.islem_tarihi.min())]
    beden = beden.assign(model_kodu=beden.barkod.map(model), kucuk=(beden.neden_grubu == "beden_kucuk").astype(float))
    return beden.dropna(subset=["model_kodu"]), satis.dropna(subset=["model_kodu"])


def kalip_ozellikleri(veri, model_kodu, zaman):
    """Her (ürün, zaman) için kalıp skoru, beden iadesi oranı ve sayısı; yalnızca o andan önceki olaylar."""
    beden, satis = _beden_olaylari(veri)
    model_kodu, zaman = pd.Series(model_kodu).reset_index(drop=True), pd.Series(zaman).reset_index(drop=True)
    k = _onceki_sayi(beden.model_kodu, beden.son_guncelleme, beden.kucuk, model_kodu, zaman)
    n = _onceki_sayi(beden.model_kodu, beden.son_guncelleme, 1.0, model_kodu, zaman)
    s = _onceki_sayi(satis.model_kodu, satis.islem_tarihi, 1.0, model_kodu, zaman)
    tum = pd.Series("tum", index=zaman.index)
    k0 = _onceki_sayi(pd.Series("tum", index=beden.index), beden.son_guncelleme, beden.kucuk, tum, zaman)
    n0 = _onceki_sayi(pd.Series("tum", index=beden.index), beden.son_guncelleme, 1.0, tum, zaman)
    s0 = _onceki_sayi(pd.Series("tum", index=satis.index), satis.islem_tarihi, 1.0, tum, zaman)
    pay0 = np.where(n0 > 0, k0 / np.maximum(n0, 1), VARSAYILAN_KUCUK_PAYI)
    oran0 = np.where(s0 > 0, n0 / np.maximum(s0, 1), 0.05)
    return pd.DataFrame({"kalip_skoru": (k + ONSEL_GUCU * pay0) / (n + ONSEL_GUCU),
                         "beden_iade_orani": (n + ORAN_GUCU * oran0) / (s + ORAN_GUCU),
                         "beden_iadesi": n})


def kalip_etiketi(skor, iade_sayisi):
    return np.select([(iade_sayisi >= ETIKET_MIN_IADE) & (skor >= DAR_ESIGI),
                      (iade_sayisi >= ETIKET_MIN_IADE) & (skor <= BOL_ESIGI)], ["dar", "bol"], "belirsiz")


def kalip_tablosu(veri, zaman=None):
    """Ürün başına kalıp skoru (varsayılan: verinin son anı). Web ve tavsiye motoru bunu okur."""
    urunler = m.tablolar(veri)["urunler"].dropna(subset=["model_kodu"]).drop_duplicates("model_kodu")
    zaman = zaman or m.veri_araligi(veri)[1] + pd.Timedelta(days=1)
    k = kalip_ozellikleri(veri, urunler.model_kodu, pd.Series(zaman, index=urunler.index))
    t = urunler[["model_kodu", "kategori"]].reset_index(drop=True).join(k)
    t["kalip"] = kalip_etiketi(t.kalip_skoru, t.beden_iadesi)
    return t


# ====================================================
# 2) B — YÖN MODELİ (beden iadesinde küçük mü büyük mü)
# ====================================================

def yon_veri_seti(veri):
    """Beden iadesi olan satırlar + sipariş anındaki kalıp özellikleri. hedef: 1 = küçük geldi."""
    d = iade_veri_seti(veri)
    d = d[d.iade_nedeni.isin(["beden_kucuk", "beden_buyuk"])].reset_index(drop=True)
    d = d.join(kalip_ozellikleri(veri, d.model_kodu, d.siparis_tarihi))
    return d.assign(kucuk=(d.iade_nedeni == "beden_kucuk").astype(int))


def yon_egit(egitim, dogrulama):
    ozellikler = YON_SAYISAL + YON_KATEGORIK
    kategoriler = {c: sorted(egitim[c].dropna().unique()) for c in YON_KATEGORIK}
    params = dict(gbm.PARAMETRELER, monotone_constraints=[1 if c in YON_MONOTON else 0 for c in ozellikler],
                  monotone_constraints_method="advanced")
    model = lgb.LGBMClassifier(**params)
    model.fit(gbm.matris(egitim, ozellikler, kategoriler), egitim.kucuk,
              eval_set=[(gbm.matris(dogrulama, ozellikler, kategoriler), dogrulama.kucuk)], eval_metric="auc",
              callbacks=[lgb.early_stopping(100, verbose=False)])
    tur = max(int(model.best_iteration_), 1)
    tum = pd.concat([egitim, dogrulama])
    son = lgb.LGBMClassifier(**dict(params, n_estimators=tur)).fit(gbm.matris(tum, ozellikler, kategoriler), tum.kucuk)
    p_dogrulama = model.predict_proba(gbm.matris(dogrulama, ozellikler, kategoriler))[:, 1]
    return {"model": son, "ozellikler": ozellikler, "kategoriler": kategoriler, "agac": tur}, p_dogrulama


def yon_tahmin(paket, df):
    return paket["model"].predict_proba(gbm.matris(df, paket["ozellikler"], paket["kategoriler"]))[:, 1]


# ====================================================
# 3) C — BEDEN ÖNERİSİ
# ====================================================

def _harf_yorumlari(veri):
    y = m.tablolar(veri)["urun_yorumlari"]
    y = y[y.boy.between(*MAKUL_BOY) & y.kilo.between(*MAKUL_KILO)].copy()
    tip_deger = y.beden.map(beden_degeri)
    y["beden_degeri"] = [d for _, d in tip_deger]
    return y[[t == "harf" for t, _ in tip_deger]].reset_index(drop=True)


def oneri_egit(veri):
    y = _harf_yorumlari(veri)
    r = LinearRegression().fit(y[["boy", "kilo"]].to_numpy(dtype=float), y.beden_degeri)
    return {"katsayi": r.coef_.tolist(), "sabit": float(r.intercept_), "en_sik": float(y.beden_degeri.mode()[0]),
            "alt": float(y.beden_degeri.min()), "ust": float(y.beden_degeri.max()), "n": int(len(y))}


def _oneri_degeri(oneri, boy, kilo, kalip_skoru=None, kalip_iadesi=None):
    deger = np.rint(oneri["sabit"] + oneri["katsayi"][0] * np.asarray(boy, dtype=float)
                    + oneri["katsayi"][1] * np.asarray(kilo, dtype=float))
    if kalip_skoru is not None:
        etiket = kalip_etiketi(np.asarray(kalip_skoru, dtype=float), np.asarray(kalip_iadesi, dtype=float))
        deger = deger + np.select([etiket == "dar", etiket == "bol"], [1, -1], 0)
    return np.clip(deger, oneri["alt"], oneri["ust"])


def beden_oner(boy, kilo, kalip_skoru=None, kalip_iadesi=None, oneri=None):
    """Boy (cm) ve kilodan harf beden önerisi ("M", "L" ...). Kalıp skoru verilirse dar üründe bir büyük, bol üründe
    bir küçük beden önerir (en az ETIKET_MIN_IADE beden iadesi olan ürünlerde)."""
    oneri = oneri or model_yukle(MODEL_ID)["oneri"]
    duzelt = kalip_skoru is not None and oneri.get("kalip_duzeltmesi", True)
    d = _oneri_degeri(oneri, [boy], [kilo], [kalip_skoru] if duzelt else None, [kalip_iadesi] if duzelt else None)
    return HARF_ADI[int(d[0])]


def ideal_harf_degeri(boy, kilo):
    """Seviye 1 kâhini: sahte üreticinin harf bedenlerde ideal beden kuralı (hazirlama/sahte_veri_uret.py,
    ideal_konum). Yalnızca doğrulama içindir."""
    skor = np.asarray(kilo, dtype=float) + (np.asarray(boy, dtype=float) - 165) * 0.35
    sira = np.searchsorted([44, 49, 55, 62, 70, 79, 88], skor)       # 2XS, XS, S, M, L, XL, 2XL, 3XL
    return np.array([HARF_SIRASI[h] for h in ["2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL"]])[sira]


# ====================================================
# 4) DOĞRULAMA
# ====================================================

def _auc_ci(y, p, tekrar=1000):
    """AUC ve %95 güven aralığı (AUC − 0,5 farkının bootstrap'ı; sabit referans 0,5)."""
    f = bootstrap_auc_farki(y, p, np.zeros(len(y)), tekrar=tekrar)
    return {"auc": siniflandirma_olcutleri(y, p)["roc_auc"], "alt": f["alt"] + 0.5, "ust": f["ust"] + 0.5}


def _isabet_farki(dogru_a, dogru_b, tekrar=1000, tohum=0):
    """Eşleştirilmiş bootstrap: isabet(a) − isabet(b), %95 güven aralığı."""
    a, b = np.asarray(dogru_a, dtype=float), np.asarray(dogru_b, dtype=float)
    rng = np.random.default_rng(tohum)
    farklar = [(a[i] - b[i]).mean() for i in (rng.integers(0, len(a), len(a)) for _ in range(tekrar))]
    return {"fark": float((a - b).mean()), "alt": float(np.percentile(farklar, 2.5)),
            "ust": float(np.percentile(farklar, 97.5))}


def seviye1_kalip(veri):
    """Sahte: test penceresinin başındaki kalıp skoru, gizli kalıbı ayırt ediyor mu?"""
    gizli = pd.read_csv(VERI / veri / "dogru_cevaplar" / "modeller.csv", encoding="utf-8-sig")
    gizli = gizli[gizli.kalip.notna()]
    k = kalip_ozellikleri(veri, gizli.model_kodu, pd.Series(TEST_BASLANGIC, index=gizli.index))
    d = gizli[["model_kodu", "kalip"]].reset_index(drop=True).join(k)
    d = d[d.beden_iadesi >= MIN_KALIP_IADESI]
    return {"urun": int(len(d)), "dar_auc": siniflandirma_olcutleri(d.kalip == -1, d.kalip_skoru)["roc_auc"],
            "bol_auc": siniflandirma_olcutleri(d.kalip == 1, 1 - d.kalip_skoru)["roc_auc"],
            "dar_sayisi": int((d.kalip == -1).sum()), "bol_sayisi": int((d.kalip == 1).sum())}


def seviye1_oneri(veri, oneri):
    """Sahte: gizli boy-kilodan üreticinin ideal bedeni; öneri onunla ne sıklıkla aynı (en sık bedenle kıyas)."""
    mu = pd.read_csv(VERI / veri / "dogru_cevaplar" / "musteriler.csv", encoding="utf-8-sig")
    ideal = ideal_harf_degeri(mu.boy, mu.kilo)
    tahmin = _oneri_degeri(oneri, mu.boy, mu.kilo)
    return {"musteri": int(len(mu)), "tam_isabet": float((tahmin == ideal).mean()),
            "bir_beden_isabet": float((np.abs(tahmin - ideal) <= 1).mean()),
            "en_sik_isabet": float((oneri["en_sik"] == ideal).mean())}


def seviye1_duzeltme(veri, oneri):
    """Sahte: kalıp düzeltmesi seçimi. Hedef, ÜRÜN İÇİN doğru beden = ideal − kalıp (dar üründe bir büyük; üreticide
    uyum = seçilen − ideal + kalıp = 0). Düzeltme, sipariş anındaki kalıp skoruyla yapılır."""
    t = m.tablolar(veri)
    dc = VERI / veri / "dogru_cevaplar"
    mu = pd.read_csv(dc / "musteriler.csv", encoding="utf-8-sig").set_index("musteri_id")
    kalip = pd.read_csv(dc / "modeller.csv", encoding="utf-8-sig").set_index("model_kodu").kalip
    urun = t["urunler"].drop_duplicates("barkod").set_index("barkod").model_kodu
    s = t["siparis_satirlari"].merge(t["siparisler"][["paket_id", "musteri_id", "siparis_tarihi"]], on="paket_id")
    s = s.assign(model_kodu=s.barkod.map(urun), boy=s.musteri_id.map(mu.boy), kilo=s.musteri_id.map(mu.kilo))
    s = s[[beden_degeri(b)[0] == "harf" for b in s.beden]].dropna(subset=["model_kodu", "boy"]).reset_index(drop=True)
    s["kalip"] = s.model_kodu.map(kalip)
    s = s.join(kalip_ozellikleri(veri, s.model_kodu, s.siparis_tarihi))
    hedef = ideal_harf_degeri(s.boy, s.kilo) - s.kalip.to_numpy()
    duz = _oneri_degeri(oneri, s.boy, s.kilo)
    ayarli = _oneri_degeri(oneri, s.boy, s.kilo, s.kalip_skoru, s.beden_iadesi)
    return {"satir": int(len(s)), "duzeltmesiz": float((duz == hedef).mean()),
            "duzeltmeli": float((ayarli == hedef).mean()),
            "duzeltilen_satir_payi": float((duz != ayarli).mean())}


def _yorum_kalibi(veri, y):
    """Yorumun ürününe ait, yorum tarihindeki kalıp skoru."""
    u = m.tablolar(veri)["urunler"].dropna(subset=["icerik_id"]).drop_duplicates("icerik_id").set_index("icerik_id")
    return kalip_ozellikleri(veri, y.icerik_id.map(u.model_kodu), y.yorum_tarihi)


def gercek_yon_verisi():
    g = yon_veri_seti("gercek")
    return g[g.siparis_tarihi >= TEST_BASLANGIC]


def calistir():
    gercek_var = (VERI / "gercek" / "siparisler.csv").exists()
    g_yon = gercek_yon_verisi() if gercek_var else None
    g_yorum = _harf_yorumlari("gercek") if gercek_var else None
    g_kalip = _yorum_kalibi("gercek", g_yorum) if gercek_var else None
    sonuc = {"A": {}, "B": {}, "C": {}, "seviye1": {}}

    # A: kalıp skoru (eğitimsiz) -> gerçek test penceresindeki beden iadelerinin yönü
    if g_yon is not None:
        sonuc["A"] = {"n": int(len(g_yon)), "kucuk_payi": float(g_yon.kucuk.mean()),
                      **_auc_ci(g_yon.kucuk, g_yon.kalip_skoru)}

    son_paketler = {}
    for tohum, veri in SAHTE_TOHUMLAR.items():
        if not (VERI / veri / "siparisler.csv").exists():
            print(f"atlandı (veri yok): {veri}")
            continue
        # B: yön modeli
        yon = yon_veri_seti(veri)
        egitim, dogrulama = sahte_bol(yon)
        paket, p_dogrulama = yon_egit(egitim, dogrulama)
        s1 = {"kalip": seviye1_kalip(veri),
              "yon_sahte_dogrulama": {"model": siniflandirma_olcutleri(dogrulama.kucuk, p_dogrulama)["roc_auc"],
                                      "kalip_skoru": siniflandirma_olcutleri(dogrulama.kucuk,
                                                                             dogrulama.kalip_skoru)["roc_auc"],
                                      "n": int(len(dogrulama))}}
        oneri = oneri_egit(veri)
        s1["oneri"] = seviye1_oneri(veri, oneri)
        s1["duzeltme"] = seviye1_duzeltme(veri, oneri)
        # Kalıp düzeltmesi yalnızca sahtedeki etkisine göre seçilir
        oneri["kalip_duzeltmesi"] = s1["duzeltme"]["duzeltmeli"] > s1["duzeltme"]["duzeltmesiz"]
        sonuc["seviye1"][tohum] = s1
        son_paketler[tohum] = {"yon": paket, "oneri": oneri}

        if g_yon is not None:
            p = yon_tahmin(paket, g_yon)
            sonuc["B"][tohum] = {"agac": paket["agac"], **_auc_ci(g_yon.kucuk, p),
                                 "fark_kalip_skoru": bootstrap_auc_farki(g_yon.kucuk, p, g_yon.kalip_skoru),
                                 "ortalama_tahmin": float(p.mean())}
            duz = _oneri_degeri(oneri, g_yorum.boy, g_yorum.kilo)
            ayarli = _oneri_degeri(oneri, g_yorum.boy, g_yorum.kilo, g_kalip.kalip_skoru, g_kalip.beden_iadesi)
            t = ayarli if oneri["kalip_duzeltmesi"] else duz
            sonuc["C"][tohum] = {"n": int(len(g_yorum)), "egitim_yorumu": oneri["n"],
                                 "kalip_duzeltmesi": bool(oneri["kalip_duzeltmesi"]),
                                 "tam_isabet_duzeltmesiz": float((duz == g_yorum.beden_degeri).mean()),
                                 "tam_isabet_duzeltmeli": float((ayarli == g_yorum.beden_degeri).mean()),
                                 "tam_isabet": float((t == g_yorum.beden_degeri).mean()),
                                 "bir_beden_isabet": float((np.abs(t - g_yorum.beden_degeri) <= 1).mean()),
                                 "en_sik_isabet": float((oneri["en_sik"] == g_yorum.beden_degeri).mean()),
                                 "fark_en_sik": _isabet_farki(t == g_yorum.beden_degeri,
                                                              oneri["en_sik"] == g_yorum.beden_degeri)}

    # Karar: B ve C, 3 tohumun en az 2'sinde alt sınır > 0 (önceden belirlendi)
    if g_yon is not None:
        sonuc["karar"] = {
            "A": sonuc["A"]["alt"] > 0.5,
            "B": sum(v["fark_kalip_skoru"]["alt"] > 0 for v in sonuc["B"].values()) >= 2,
            "C": sum(v["fark_en_sik"]["alt"] > 0 for v in sonuc["C"].values()) >= 2}

    # Kaydet: model (tohum 42), ürün kalıp tabloları, doğrulama
    model_kaydet(son_paketler[42], MODEL_ID)
    for veri in ["sahte"] + (["gercek"] if gercek_var else []):
        tahmin_kaydet(kalip_tablosu(veri), f"{MODEL_ID}_kalip", veri)
    klasor = CIKTILAR / "gercek" / "dogrulama" if gercek_var else CIKTILAR / "sahte" / "dogrulama"
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / f"{MODEL_ID}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2, default=float),
                                              encoding="utf-8")
    return sonuc


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(calistir(), ensure_ascii=False, indent=1, default=lambda x: round(float(x), 4)))
