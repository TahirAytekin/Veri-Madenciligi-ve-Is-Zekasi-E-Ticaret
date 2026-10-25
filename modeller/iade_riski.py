"""İade riski (F2-02): bir sipariş satırının iade edilme olasılığı. LightGBM, yalnızca sahte veriyle eğitilir.

    python -m modeller.iade_riski

Seçim kuralı (önceden belirlendi): varyantlar yalnızca SAHTE doğrulama döneminde (son 90 gün) karşılaştırılır ve
en yüksek AUC'li olan seçilir. Gerçek veri seçimde kullanılmaz; tüm varyantların gerçek sonuçları şeffaflık için
raporlanır.

Çıktılar (ciktilar/, git'e girmez):
    modeller/F2-02.joblib                     eğitilmiş model + özellik listesi
    <veri>/tahminler/F2-02.csv                satır başına iade olasılığı
    <veri>/dogrulama/F2-02.json               model ve eğitimsiz referansların ölçütleri
"""
import json

import lightgbm as lgb
import numpy as np
import pandas as pd

from hazirlama.ortak import VERI
from modeller.ortak.degerlendir import (
    CIKTILAR,
    baseline_skorlari,
    bootstrap_auc_farki,
    degerlendir,
    grup_ici_auc,
    kalibrasyon_tablosu,
    sahte_bol,
    siniflandirma_olcutleri,
)
from modeller.ortak.kayit import model_kaydet, tahmin_kaydet
from modeller.ortak.ozellikler import MODEL_KATEGORIK, MODEL_SAYISAL, iade_veri_seti

MODEL_ID = "F2-02"
TOHUM = 42

# Alan bilgisi: geçmişte çok iade edilen ürün/kategori/müşterinin riski DAHA DÜŞÜK olamaz (artan monoton)
MONOTON_ARTAN = ["kategori_onceki_iade_orani", "model_onceki_iade_orani", "model_onceki_kucuk_orani",
                 "model_onceki_buyuk_orani", "musteri_onceki_iade_orani"]
GORELI = ["model_iade_goreli", "model_kucuk_goreli", "model_buyuk_goreli"]

PARAMETRELER = dict(objective="binary", learning_rate=0.03, n_estimators=2000, num_leaves=15, min_child_samples=60,
                    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, random_state=TOHUM,
                    verbose=-1)


# ====================================================
# 1) ÖZELLİK MATRİSİ
# ====================================================

def goreli_ekle(df):
    """Ölçeği veri setine göre değişen geçmiş oranlarının göreli hali (F1-04 önerisi)."""
    d = df.copy()
    d["model_iade_goreli"] = d.model_onceki_iade_orani / d.kategori_onceki_iade_orani
    d["model_kucuk_goreli"] = d.model_onceki_kucuk_orani / d.model_onceki_iade_orani
    d["model_buyuk_goreli"] = d.model_onceki_buyuk_orani / d.model_onceki_iade_orani
    return d


def matris(df, ozellikler, kategoriler):
    """LightGBM girdisi. Kategorik değerler eğitimdeki kategori listesine sabitlenir; görülmemiş değer -> NaN."""
    X = df[ozellikler].copy()
    for c in X.columns.intersection(list(kategoriler)):
        X[c] = pd.Categorical(X[c], categories=kategoriler[c])
    return X


def varyantlar():
    temel = MODEL_SAYISAL + MODEL_KATEGORIK
    return {
        "gbm": {"ozellikler": temel, "monoton": False},
        "gbm_monoton": {"ozellikler": temel, "monoton": True},
        "gbm_monoton_goreli": {"ozellikler": temel + GORELI, "monoton": True},
    }


# ====================================================
# 2) EĞİTİM
# ====================================================

def egit(egitim, dogrulama, ozellikler, monoton):
    kategoriler = {c: sorted(egitim[c].dropna().unique()) for c in ozellikler if c in MODEL_KATEGORIK}
    params = dict(PARAMETRELER)
    if monoton:
        params["monotone_constraints"] = [1 if c in MONOTON_ARTAN else 0 for c in ozellikler]
        params["monotone_constraints_method"] = "advanced"
    model = lgb.LGBMClassifier(**params)
    model.fit(matris(egitim, ozellikler, kategoriler), egitim.iade,
              eval_set=[(matris(dogrulama, ozellikler, kategoriler), dogrulama.iade)], eval_metric="auc",
              callbacks=[lgb.early_stopping(100, verbose=False)])
    return {"model": model, "ozellikler": ozellikler, "kategoriler": kategoriler}


def tahmin(paket, df):
    return paket["model"].predict_proba(matris(df, paket["ozellikler"], paket["kategoriler"]))[:, 1]


def yeniden_egit(sahte, secilen, en_iyi_tur):
    """Seçilen varyant, doğrulamada bulunan ağaç sayısıyla tüm sahte veride yeniden eğitilir."""
    ozellikler, monoton = secilen["ozellikler"], secilen["monoton"]
    kategoriler = {c: sorted(sahte[c].dropna().unique()) for c in ozellikler if c in MODEL_KATEGORIK}
    params = dict(PARAMETRELER, n_estimators=en_iyi_tur)
    if monoton:
        params["monotone_constraints"] = [1 if c in MONOTON_ARTAN else 0 for c in ozellikler]
        params["monotone_constraints_method"] = "advanced"
    model = lgb.LGBMClassifier(**params).fit(matris(sahte, ozellikler, kategoriler), sahte.iade)
    return {"model": model, "ozellikler": ozellikler, "kategoriler": kategoriler}


# ====================================================
# 3) SEVİYE 1: SAHTE VERİDE DOĞRU CEVAP
# ====================================================

def kahin_skoru(df, veri="sahte"):
    """Sahte veriyi üreten gizli iade olasılığı. Sahtede ulaşılabilecek tavan.

    Üretici olasılığı kaydettiyse (sahte v2, F1-06) doğrudan o kullanılır; yoksa v1 formülü (dogru_cevaplar/README.md).
    """
    dc = VERI / veri / "dogru_cevaplar"
    satir = pd.read_csv(dc / "satirlar.csv", encoding="utf-8-sig").set_index("satir_id")
    if "iade_olasiligi" in satir:
        return df.satir_id.map(satir.iade_olasiligi).to_numpy(dtype=float)
    kalite = pd.read_csv(dc / "modeller.csv", encoding="utf-8-sig").set_index("model_kodu").kalite
    uyum = df.satir_id.map(satir.beden_uyumu).to_numpy(dtype=float)
    sorunlu = df.satir_id.map(satir.sorunlu_urun).fillna(False).to_numpy(dtype=bool)
    k = df.model_kodu.map(kalite).to_numpy(dtype=float)
    ham = 0.04 + 0.08 * (1 - k) + 0.30 * np.maximum(-uyum, 0) + 0.32 * np.maximum(uyum, 0)
    return np.where(sorunlu, 0.40, ham)


# ====================================================
# 4) ÇALIŞTIR
# ====================================================

def varyant_sec(egitim, dogrulama, gercek=None):
    """Varyantlar yalnızca sahte doğrulamada karşılaştırılır; gerçek AUC (verilirse) yalnızca şeffaflık içindir."""
    sonuclar, paketler = [], {}
    for ad, v in varyantlar().items():
        paket = egit(egitim, dogrulama, v["ozellikler"], v["monoton"])
        paketler[ad] = paket
        satir = {"varyant": ad, "agac": paket["model"].best_iteration_,
                 "sahte_dogrulama_auc": siniflandirma_olcutleri(dogrulama.iade, tahmin(paket, dogrulama))["roc_auc"]}
        if gercek is not None:
            satir["gercek_test_auc"] = siniflandirma_olcutleri(gercek.iade, tahmin(paket, gercek))["roc_auc"]
        sonuclar.append(satir)
    karsilastirma = pd.DataFrame(sonuclar)
    secilen_ad = karsilastirma.sort_values("sahte_dogrulama_auc", ascending=False).varyant.iloc[0]
    return karsilastirma, secilen_ad, paketler


def calistir():
    sahte = goreli_ekle(iade_veri_seti("sahte"))
    gercek = goreli_ekle(iade_veri_seti("gercek")) if (VERI / "gercek" / "siparisler.csv").exists() else None
    egitim, dogrulama = sahte_bol(sahte)
    karsilastirma, secilen_ad, paketler = varyant_sec(egitim, dogrulama, gercek)
    secilen = varyantlar()[secilen_ad]
    en_iyi_tur = int(paketler[secilen_ad]["model"].best_iteration_)

    # Seviye 1: sahte doğrulamada model (doğrulamayı görmemiş), eğitimsiz referanslar ve kâhin
    p_dogrulama = tahmin(paketler[secilen_ad], dogrulama)
    ek = {"sahte": _ek_olcutler(dogrulama, p_dogrulama)}
    seviye1 = degerlendir(MODEL_ID, dogrulama, {"model": p_dogrulama, **baseline_skorlari(dogrulama),
                                                "kahin_ust_sinir": kahin_skoru(dogrulama)}, veri="sahte",
                          notlar=[f"seçilen varyant: {secilen_ad}"])

    # Son model: tüm sahte veri; gerçek veri yalnızca test
    son = yeniden_egit(sahte, secilen, en_iyi_tur)
    model_kaydet(son, MODEL_ID)
    onem = (pd.Series(son["model"].booster_.feature_importance("gain"), index=son["ozellikler"])
            .sort_values(ascending=False) / son["model"].booster_.feature_importance("gain").sum())

    seviye2, kalibrasyon = None, None
    for veri, df in [("sahte", sahte), ("gercek", gercek)]:
        if df is None:
            continue
        p = tahmin(son, df)
        tahmin_kaydet(df[["satir_id", "model_kodu", "kategori", "beden", "siparis_tarihi"]].assign(
            iade_olasiligi=p.round(4), gerceklesen_iade=df.iade), MODEL_ID, veri)
        if veri == "gercek":
            seviye2 = degerlendir(MODEL_ID, df, {"model": p, **baseline_skorlari(df)}, veri="gercek",
                                  notlar=[f"seçilen varyant: {secilen_ad}", f"ağaç sayısı: {en_iyi_tur}"])
            kalibrasyon = kalibrasyon_tablosu(df.iade, p, dilim=5)
            ek["gercek"] = _ek_olcutler(df, p)

    ozet = {"secilen_varyant": secilen_ad, "agac": en_iyi_tur, "varyantlar": karsilastirma.to_dict("records"),
            "ek_olcutler": ek, "ozellik_onemi": onem.round(4).to_dict()}
    (CIKTILAR / "modeller").mkdir(parents=True, exist_ok=True)
    (CIKTILAR / "modeller" / f"{MODEL_ID}_ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2),
                                                                encoding="utf-8")
    return {"karsilastirma": karsilastirma, "secilen": secilen_ad, "seviye1": seviye1, "seviye2": seviye2,
            "kalibrasyon": kalibrasyon, "onem": onem, "ek": ek}


def _ek_olcutler(df, p):
    """Model en güçlü eğitimsiz referansı (ürün geçmişi) geçiyor mu; aynı ürünün satırlarını ayırt ediyor mu?"""
    return {"auc_farki_model_eksi_urun_gecmisi": bootstrap_auc_farki(df.iade, p, df.model_onceki_iade_orani),
            "urun_ici_auc_model": grup_ici_auc(df, p)}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 160)
    r = calistir()
    print("Varyantlar (seçim yalnızca sahte doğrulama AUC'sine göre):")
    print(r["karsilastirma"].round(4).to_string(index=False))
    print(f"\nSeçilen: {r['secilen']}\n\nSeviye 1 — sahte doğrulama:")
    print(r["seviye1"][["roc_auc", "pr_auc", "brier", "ortalama_tahmin", "pozitif_orani"]].round(4).to_string())
    if r["seviye2"] is not None:
        print("\nSeviye 2 — gerçek test:")
        print(r["seviye2"][["roc_auc", "pr_auc", "brier", "ortalama_tahmin", "pozitif_orani"]].round(4).to_string())
        print("\nKalibrasyon (gerçek, 5 dilim):")
        print(r["kalibrasyon"].round(4).to_string())
    print("\nEk ölçütler (AUC farkı: model − ürün geçmişi, %95 güven aralığı; ürün içi AUC):")
    for veri, e in r["ek"].items():
        f, u = e["auc_farki_model_eksi_urun_gecmisi"], e["urun_ici_auc_model"]
        print(f"  {veri}: fark {f['ortalama']:+.3f} [{f['alt']:+.3f}, {f['ust']:+.3f}] | ürün içi AUC {u['auc']:.3f} "
              f"({u['satir']} satır)")
    print("\nÖzellik önemi (ilk 12):")
    print(r["onem"].head(12).round(3).to_string())
