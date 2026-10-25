"""Sahte -> gerçek değerlendirme (F2-01).

Kural (docs/MODEL_DOGRULAMA.md): model yalnızca sahte veriyle eğitilir; hiperparametre seçimi sahtenin son
DOGRULAMA_GUN gününde yapılır; gerçek veri yalnızca son testte kullanılır.

    from modeller.ortak.degerlendir import sahte_bol, siniflandirma_olcutleri, degerlendir
    egitim, dogrulama = sahte_bol(iade_veri_seti("sahte"))
    sonuc = degerlendir("F2-02", gercek_df, {"model": p_model, **baseline_skorlari(gercek_df)}, hedef="iade")
"""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

from hazirlama.ortak import PROJE

DOGRULAMA_GUN = 90
CIKTILAR = PROJE / "ciktilar"


def sahte_bol(df, gun=DOGRULAMA_GUN, tarih="siparis_tarihi"):
    """Sahte veriyi zamana göre böler: eğitim = son `gun` öncesi, doğrulama = son `gun` (hiperparametre seçimi için)."""
    sinir = df[tarih].max() - pd.Timedelta(days=gun)
    return df[df[tarih] <= sinir], df[df[tarih] > sinir]


def baseline_skorlari(df):
    """Eğitim gerektirmeyen referanslar: mağazanın kendi geçmişinden o güne kadarki iade oranları."""
    return {"baseline_kategori_gecmisi": df.kategori_onceki_iade_orani.to_numpy(),
            "baseline_model_gecmisi": df.model_onceki_iade_orani.to_numpy()}


def siniflandirma_olcutleri(y, p):
    y, p = np.asarray(y, dtype=float), np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    tek_sinif = len(np.unique(y)) < 2
    return {
        "n": int(len(y)), "pozitif_orani": float(y.mean()),
        "roc_auc": None if tek_sinif else float(roc_auc_score(y, p)),
        "pr_auc": None if tek_sinif else float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": None if tek_sinif else float(log_loss(y, p)),
        "ortalama_tahmin": float(p.mean()),
    }


def kalibrasyon_tablosu(y, p, dilim=10):
    """Tahminler dilimlere ayrılır; her dilimde ortalama tahmin ile gerçekleşen oran karşılaştırılır."""
    t = pd.DataFrame({"y": np.asarray(y, dtype=float), "p": np.asarray(p, dtype=float)})
    t["dilim"] = pd.qcut(t.p.rank(method="first"), dilim, labels=False)
    return t.groupby("dilim").agg(ortalama_tahmin=("p", "mean"), gerceklesen=("y", "mean"), n=("y", "size"))


def degerlendir(model_id, df, skorlar, hedef="iade", veri="gercek", notlar=None):
    """Her skoru (model + baseline'lar) aynı test kümesinde ölçer; ciktilar/<veri>/dogrulama/<id>.json'a yazar."""
    y = df[hedef].to_numpy()
    satirlar = []
    for ad, p in skorlar.items():
        satirlar.append({"skor": ad, **siniflandirma_olcutleri(y, p)})
    tablo = pd.DataFrame(satirlar).set_index("skor")
    sonuc = {
        "model_id": model_id, "veri": veri, "hedef": hedef,
        "test_donemi": {"baslangic": str(df.siparis_tarihi.min().date()), "bitis": str(df.siparis_tarihi.max().date())},
        "olcutler": tablo.reset_index().to_dict("records"),
        "notlar": notlar or [],
    }
    klasor = CIKTILAR / veri / "dogrulama"
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / f"{model_id}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
    return tablo
