"""Sahte veri v1 ile v2'nin model üzerindeki etkisi (F1-06, başarı ölçütü B). F2-02 kodu ve seçim kuralı değişmez.

    python hazirlama/sahte_veri_uret.py --v1 [--tohum 1|2]   # gerekli veri setleri (v2: --tohum 1|2)
    python -m modeller.surum_karsilastirma

Her sahte veri setinde F2-02 aynı kuralla seçilip eğitilir ve gerçek test penceresinde ölçülür.
Çıktı: ciktilar/modeller/F1-06_surum_karsilastirma.json (git'e girmez)
"""
import json

import pandas as pd

from hazirlama.ortak import VERI
from modeller import iade_riski as gbm
from modeller.ortak.degerlendir import CIKTILAR, bootstrap_auc_farki, grup_ici_auc, sahte_bol, siniflandirma_olcutleri
from modeller.ortak.ozellikler import iade_veri_seti

VERI_SETLERI = {("v1", 42): "sahte_v1", ("v1", 1): "sahte_v1_t1", ("v1", 2): "sahte_v1_t2",
                ("v2", 42): "sahte", ("v2", 1): "sahte_t1", ("v2", 2): "sahte_t2"}


def f202_egit(sahte_veri):
    """F2-02'nin tam yolu: varyant seçimi (yalnızca sahte doğrulama) + seçilenin tüm sahte veride yeniden eğitimi."""
    sahte = gbm.goreli_ekle(iade_veri_seti(sahte_veri))
    egitim, dogrulama = sahte_bol(sahte)
    karsilastirma, secilen_ad, paketler = gbm.varyant_sec(egitim, dogrulama)
    en_iyi_tur = int(paketler[secilen_ad]["model"].best_iteration_)
    son = gbm.yeniden_egit(sahte, gbm.varyantlar()[secilen_ad], en_iyi_tur)
    sahte_auc = karsilastirma.set_index("varyant").sahte_dogrulama_auc[secilen_ad]
    return son, secilen_ad, float(sahte_auc)


def calistir():
    gercek = gbm.goreli_ekle(iade_veri_seti("gercek"))
    satirlar, tahminler = [], {}
    for (surum, tohum), ad in VERI_SETLERI.items():
        if not (VERI / ad / "siparisler.csv").exists():
            print(f"atlandı (veri yok): {ad}")
            continue
        son, secilen, sahte_auc = f202_egit(ad)
        p = gbm.tahmin(son, gercek)
        tahminler[(surum, tohum)] = p
        gercek_auc = siniflandirma_olcutleri(gercek.iade, p)["roc_auc"]
        fark = bootstrap_auc_farki(gercek.iade, p, gercek.model_onceki_iade_orani)
        satirlar.append({"surum": surum, "tohum": tohum, "secilen": secilen, "sahte_dogrulama_auc": sahte_auc,
                         "gercek_auc": gercek_auc, "aktarim_acigi": sahte_auc - gercek_auc,
                         "fark_urun_gecmisi": fark["ortalama"], "fark_alt": fark["alt"], "fark_ust": fark["ust"],
                         "urun_ici_auc": grup_ici_auc(gercek, p)["auc"],
                         "ortalama_tahmin": float(p.mean())})
    tablo = pd.DataFrame(satirlar)
    eslesmis = None
    if ("v1", 42) in tahminler and ("v2", 42) in tahminler:
        eslesmis = bootstrap_auc_farki(gercek.iade, tahminler[("v2", 42)], tahminler[("v1", 42)])
    sonuc = {"tablo": tablo.to_dict("records"), "eslesmis_v2_eksi_v1_tohum42": eslesmis,
             "gercek_pozitif_orani": float(gercek.iade.mean()),
             "urun_gecmisi_auc": siniflandirma_olcutleri(gercek.iade, gercek.model_onceki_iade_orani)["roc_auc"]}
    (CIKTILAR / "modeller").mkdir(parents=True, exist_ok=True)
    (CIKTILAR / "modeller" / "F1-06_surum_karsilastirma.json").write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    return tablo, sonuc


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 200)
    tablo, sonuc = calistir()
    print(tablo.round(4).to_string(index=False))
    print("\nSürüm ortalamaları (3 tohum):")
    print(tablo.groupby("surum")[["sahte_dogrulama_auc", "gercek_auc", "aktarim_acigi", "fark_urun_gecmisi",
                                  "urun_ici_auc"]].agg(["mean", "min", "max"]).round(4).T.to_string())
    e = sonuc["eslesmis_v2_eksi_v1_tohum42"]
    if e:
        print(f"\nEşleştirilmiş (tohum 42) AUC(v2) − AUC(v1): {e['ortalama']:+.4f} [{e['alt']:+.4f}, {e['ust']:+.4f}]")
    print(f"Ürün geçmişi AUC: {sonuc['urun_gecmisi_auc']:.4f} · gerçek iade oranı: {sonuc['gercek_pozitif_orani']:.4f}")
