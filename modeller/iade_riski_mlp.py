"""İade riski, derin öğrenme (F2-03): F2-02 ile aynı problem ve özellikler, PyTorch MLP. Yalnızca sahte veriyle
eğitilir.

    python -m modeller.iade_riski_mlp

Kurallar eğitimden önce docs/modeller/F2-03.md'ye yazıldı: varyant ve epoch seçimi yalnızca SAHTE doğrulama AUC'siyle;
her varyant 5 tohumlu topluluk; başarı = gerçekte ürün geçmişine göre AUC farkının %95 güven aralığı 0'ın üstünde.

Çıktılar (ciktilar/, git'e girmez):
    modeller/F2-03.joblib                     ağırlıklar + ölçekleme + kategori sözlükleri
    <veri>/tahminler/F2-03.csv                satır başına iade olasılığı
    <veri>/dogrulama/F2-03.json               model, F2-02 ve eğitimsiz referansların ölçütleri
"""
import copy
import json

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score
from torch import nn

from hazirlama.ortak import VERI
from modeller import iade_riski as gbm
from modeller.iade_riski import GORELI, MONOTON_ARTAN, goreli_ekle, kahin_skoru
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
from modeller.ortak.kayit import model_kaydet, model_yukle, tahmin_kaydet
from modeller.ortak.ozellikler import MODEL_KATEGORIK, MODEL_SAYISAL, iade_veri_seti

MODEL_ID = "F2-03"
TOHUMLAR = [0, 1, 2, 3, 4]
SAYISAL = MODEL_SAYISAL + GORELI
AYARLAR = dict(gizli=(64, 32), dropout=0.2, ogrenme_orani=1e-3, agirlik_azaltma=1e-4, yigin=256, en_cok_epoch=200,
               sabir=15)
VARYANTLAR = {"mlp": False, "mlp_genis_derin": True}   # ad -> geçmiş oranları monoton (geniş) kısımda mı


# ====================================================
# 1) GİRDİ HAZIRLAMA
# ====================================================

def hazirlayici(egitim):
    """Ölçekleme, eksik göstergeleri ve kategori sözlükleri yalnızca eğitim kümesinden öğrenilir."""
    X = egitim[SAYISAL].astype(float).replace([np.inf, -np.inf], np.nan)
    return {"ortalama": X.mean(), "sapma": X.std().replace(0, 1).fillna(1),
            "eksik": [c for c in SAYISAL if X[c].isna().any()],
            "sozluk": {c: {d: i + 1 for i, d in enumerate(sorted(egitim[c].dropna().astype(str).unique()))}
                       for c in MODEL_KATEGORIK}}   # 0 = görülmemiş / eksik


def tensorler(df, h):
    X = df[SAYISAL].astype(float).replace([np.inf, -np.inf], np.nan)
    z = ((X - h["ortalama"]) / h["sapma"]).fillna(0)
    gosterge = X[h["eksik"]].isna().astype(float).add_suffix("_eksik")
    sayisal = pd.concat([z, gosterge], axis=1).to_numpy(np.float32)
    kat = np.stack([df[c].astype(str).map(h["sozluk"][c]).fillna(0).astype(int).to_numpy()
                    for c in MODEL_KATEGORIK], axis=1)
    return torch.tensor(sayisal), torch.tensor(kat)


def sayisal_adlari(h):
    return SAYISAL + [f"{c}_eksik" for c in h["eksik"]]


# ====================================================
# 2) AĞ
# ====================================================

class IadeAgi(nn.Module):
    """Kategorik gömmeli MLP. genis_derin=True: geçmiş iade oranları yalnızca pozitif ağırlıklı doğrusal kısma girer
    (softplus), böylece model bu oranlarda artan monotondur (F2-02'deki monotonluk kısıtının karşılığı)."""

    def __init__(self, adlar, kategori_sayilari, genis_derin):
        super().__init__()
        self.gomme = nn.ModuleList(nn.Embedding(n + 1, min(8, (n + 2) // 2)) for n in kategori_sayilari)
        self.genis = [i for i, c in enumerate(adlar) if genis_derin and c in MONOTON_ARTAN]
        self.derin_sayisal = [i for i in range(len(adlar)) if i not in self.genis]
        girdi = len(self.derin_sayisal) + sum(g.embedding_dim for g in self.gomme)
        katmanlar = []
        for k in AYARLAR["gizli"]:
            katmanlar += [nn.Linear(girdi, k), nn.ReLU(), nn.Dropout(AYARLAR["dropout"])]
            girdi = k
        self.derin = nn.Sequential(*katmanlar, nn.Linear(girdi, 1))
        self.genis_agirlik = nn.Parameter(torch.zeros(len(self.genis)))

    def forward(self, sayisal, kat):
        girdi = torch.cat([sayisal[:, self.derin_sayisal]] + [g(kat[:, i]) for i, g in enumerate(self.gomme)], dim=1)
        logit = self.derin(girdi).squeeze(1)
        if self.genis:
            logit = logit + (sayisal[:, self.genis] * nn.functional.softplus(self.genis_agirlik)).sum(1)
        return logit


# ====================================================
# 3) EĞİTİM VE TAHMİN
# ====================================================

def _olasilik(ag, sayisal, kat):
    ag.eval()
    with torch.no_grad():
        return torch.sigmoid(ag(sayisal, kat)).numpy()


def egit_tek(h, egitim, genis_derin, tohum, dogrulama=None, epoch=None):
    """Tek tohumla eğitim. dogrulama verilirse erken durdurma (en iyi epoch'un ağırlıkları); yoksa sabit `epoch`."""
    torch.manual_seed(tohum)
    uretec = torch.Generator().manual_seed(tohum)
    s, k = tensorler(egitim, h)
    y = torch.tensor(egitim.iade.to_numpy(np.float32))
    ag = IadeAgi(sayisal_adlari(h), [len(h["sozluk"][c]) for c in MODEL_KATEGORIK], genis_derin)
    opt = torch.optim.AdamW(ag.parameters(), lr=AYARLAR["ogrenme_orani"], weight_decay=AYARLAR["agirlik_azaltma"])
    kayip = nn.BCEWithLogitsLoss()
    if dogrulama is not None:
        s_d, k_d = tensorler(dogrulama, h)
    en_iyi_auc, en_iyi_epoch, en_iyi_durum = -1.0, 0, None
    for e in range(1, (epoch or AYARLAR["en_cok_epoch"]) + 1):
        ag.train()
        sira = torch.randperm(len(y), generator=uretec)
        for b in range(0, len(y), AYARLAR["yigin"]):
            i = sira[b:b + AYARLAR["yigin"]]
            opt.zero_grad()
            kayip(ag(s[i], k[i]), y[i]).backward()
            opt.step()
        if dogrulama is not None:
            auc = roc_auc_score(dogrulama.iade, _olasilik(ag, s_d, k_d))
            if auc > en_iyi_auc:
                en_iyi_auc, en_iyi_epoch, en_iyi_durum = auc, e, copy.deepcopy(ag.state_dict())
            elif e - en_iyi_epoch >= AYARLAR["sabir"]:
                break
    if dogrulama is not None:
        ag.load_state_dict(en_iyi_durum)
        return ag, en_iyi_epoch
    return ag, epoch


def egit_topluluk(egitim, genis_derin, dogrulama=None, epoch=None):
    h = hazirlayici(egitim)
    aglar, epochlar = [], []
    for t in TOHUMLAR:
        ag, e = egit_tek(h, egitim, genis_derin, t, dogrulama, epoch)
        aglar.append(ag)
        epochlar.append(e)
    return {"hazirlayici": h, "genis_derin": genis_derin, "aglar": aglar, "epochlar": epochlar}


def tahmin(paket, df):
    s, k = tensorler(df, paket["hazirlayici"])
    return np.mean([_olasilik(ag, s, k) for ag in paket["aglar"]], axis=0)


def kaydedilebilir(paket):
    """joblib için ağların yerine ağırlıklar (state_dict) saklanır; `yukle` ağları yeniden kurar."""
    return {**{a: v for a, v in paket.items() if a != "aglar"}, "durumlar": [ag.state_dict() for ag in paket["aglar"]]}


def yukle(kayit=None):
    kayit = kayit or model_yukle(MODEL_ID)
    h = kayit["hazirlayici"]
    aglar = []
    for durum in kayit["durumlar"]:
        ag = IadeAgi(sayisal_adlari(h), [len(h["sozluk"][c]) for c in MODEL_KATEGORIK], kayit["genis_derin"])
        ag.load_state_dict(durum)
        aglar.append(ag)
    return {**{a: v for a, v in kayit.items() if a != "durumlar"}, "aglar": aglar}


# ====================================================
# 4) ÇALIŞTIR
# ====================================================

def _f202_gercek_tahmini(df):
    """Karşılaştırma için kayıtlı F2-02 modeli (tüm sahte veriyle eğitilmiş); yoksa önce F2-02 çalıştırılır."""
    if not (CIKTILAR / "modeller" / f"{gbm.MODEL_ID}.joblib").exists():
        gbm.calistir()
    return gbm.tahmin(model_yukle(gbm.MODEL_ID), df)


def _ek_olcutler(df, p, p_f202):
    return {"auc_farki_model_eksi_urun_gecmisi": bootstrap_auc_farki(df.iade, p, df.model_onceki_iade_orani),
            "auc_farki_model_eksi_f202": bootstrap_auc_farki(df.iade, p, p_f202),
            "urun_ici_auc_model": grup_ici_auc(df, p), "urun_ici_auc_f202": grup_ici_auc(df, p_f202)}


def calistir():
    sahte = goreli_ekle(iade_veri_seti("sahte"))
    gercek = goreli_ekle(iade_veri_seti("gercek")) if (VERI / "gercek" / "siparisler.csv").exists() else None
    egitim, dogrulama = sahte_bol(sahte)

    # Varyantlar yalnızca sahte doğrulamada karşılaştırılır (gerçek AUC yalnızca şeffaflık için)
    sonuclar, paketler = [], {}
    for ad, genis_derin in VARYANTLAR.items():
        paket = egit_topluluk(egitim, genis_derin, dogrulama=dogrulama)
        paketler[ad] = paket
        satir = {"varyant": ad, "epochlar": paket["epochlar"],
                 "sahte_dogrulama_auc": siniflandirma_olcutleri(dogrulama.iade, tahmin(paket, dogrulama))["roc_auc"]}
        if gercek is not None:
            satir["gercek_test_auc"] = siniflandirma_olcutleri(gercek.iade, tahmin(paket, gercek))["roc_auc"]
        sonuclar.append(satir)
    karsilastirma = pd.DataFrame(sonuclar)
    secilen_ad = karsilastirma.sort_values("sahte_dogrulama_auc", ascending=False).varyant.iloc[0]
    epoch = int(round(np.mean(paketler[secilen_ad]["epochlar"])))

    # Seviye 1: sahte doğrulama; F2-02 de aynı eğitim kümesiyle eğitilip aynı doğrulamada ölçülür
    p_dogrulama = tahmin(paketler[secilen_ad], dogrulama)
    v = gbm.varyantlar()["gbm_monoton_goreli"]
    p_f202_dogrulama = gbm.tahmin(gbm.egit(egitim, dogrulama, v["ozellikler"], v["monoton"]), dogrulama)
    seviye1 = degerlendir(MODEL_ID, dogrulama, {"model": p_dogrulama, "f2_02_gbm": p_f202_dogrulama,
                                                **baseline_skorlari(dogrulama),
                                                "kahin_ust_sinir": kahin_skoru(dogrulama)}, veri="sahte",
                          notlar=[f"seçilen varyant: {secilen_ad}"])
    ek = {"sahte": _ek_olcutler(dogrulama, p_dogrulama, p_f202_dogrulama)}

    # Son model: tüm sahte veri, sabit epoch; gerçek veri yalnızca test
    son = egit_topluluk(sahte, VARYANTLAR[secilen_ad], epoch=epoch)
    model_kaydet(kaydedilebilir(son), MODEL_ID)

    seviye2, kalibrasyon = None, None
    for veri, df in [("sahte", sahte), ("gercek", gercek)]:
        if df is None:
            continue
        p = tahmin(son, df)
        tahmin_kaydet(df[["satir_id", "model_kodu", "kategori", "beden", "siparis_tarihi"]].assign(
            iade_olasiligi=p.round(4), gerceklesen_iade=df.iade), MODEL_ID, veri)
        if veri == "gercek":
            p_f202 = _f202_gercek_tahmini(df)
            seviye2 = degerlendir(MODEL_ID, df, {"model": p, "f2_02_gbm": p_f202, **baseline_skorlari(df)},
                                  veri="gercek", notlar=[f"seçilen varyant: {secilen_ad}", f"epoch: {epoch}"])
            kalibrasyon = kalibrasyon_tablosu(df.iade, p, dilim=5)
            ek["gercek"] = _ek_olcutler(df, p, p_f202)

    ozet = {"secilen_varyant": secilen_ad, "epoch": epoch, "varyantlar": karsilastirma.to_dict("records"),
            "ek_olcutler": ek}
    (CIKTILAR / "modeller").mkdir(parents=True, exist_ok=True)
    (CIKTILAR / "modeller" / f"{MODEL_ID}_ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2),
                                                                encoding="utf-8")
    return {"karsilastirma": karsilastirma, "secilen": secilen_ad, "epoch": epoch, "seviye1": seviye1,
            "seviye2": seviye2, "kalibrasyon": kalibrasyon, "ek": ek, "son": son}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 160)
    r = calistir()
    print("Varyantlar (seçim yalnızca sahte doğrulama AUC'sine göre):")
    print(r["karsilastirma"].round(4).to_string(index=False))
    print(f"\nSeçilen: {r['secilen']} · son model epoch: {r['epoch']}\n\nSeviye 1 — sahte doğrulama:")
    print(r["seviye1"][["roc_auc", "pr_auc", "brier", "ortalama_tahmin", "pozitif_orani"]].round(4).to_string())
    if r["seviye2"] is not None:
        print("\nSeviye 2 — gerçek test:")
        print(r["seviye2"][["roc_auc", "pr_auc", "brier", "ortalama_tahmin", "pozitif_orani"]].round(4).to_string())
        print("\nKalibrasyon (gerçek, 5 dilim):")
        print(r["kalibrasyon"].round(4).to_string())
    print("\nEk ölçütler (%95 güven aralığı):")
    for veri, e in r["ek"].items():
        f, g = e["auc_farki_model_eksi_urun_gecmisi"], e["auc_farki_model_eksi_f202"]
        print(f"  {veri}: model − ürün geçmişi {f['ortalama']:+.3f} [{f['alt']:+.3f}, {f['ust']:+.3f}] | "
              f"model − F2-02 {g['ortalama']:+.3f} [{g['alt']:+.3f}, {g['ust']:+.3f}] | "
              f"ürün içi AUC model {e['urun_ici_auc_model']['auc']:.3f}, F2-02 {e['urun_ici_auc_f202']['auc']:.3f}")
