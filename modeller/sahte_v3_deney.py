"""Sahte veri v3 deneyi (F1-07, ölçüt B ve C): F2-05 (talep) ve F2-02 (iade riski), kod ve seçim kuralları değişmeden,
v2 ve v3'ün 3'er tohumuyla eğitilip aynı gerçek test penceresinde ölçülür.

    python hazirlama/sahte_veri_uret.py --v3 [--tohum 1|2]     # gerekli veri setleri (v2 zaten var)
    python -m modeller.sahte_v3_deney

Hiçbir model, tahmin ya da doğrulama dosyasının üzerine yazmaz (talep.degerlendir yan etkisizdir).
Çıktı: ciktilar/modeller/F1-07_sahte_v3.json (git'e girmez). Önceden kayıt: docs/rapor/sahte_v3_talep.md
"""
import json

import pandas as pd

from modeller import iade_riski as gbm
from modeller import talep
from modeller.ortak.degerlendir import CIKTILAR, bootstrap_auc_farki, siniflandirma_olcutleri
from modeller.ortak.ozellikler import iade_veri_seti
from modeller.surum_karsilastirma import f202_egit

SURUMLER = {"v2": {42: "sahte", 1: "sahte_t1", 2: "sahte_t2"},
            "v3": {42: "sahte_v3", 1: "sahte_v3_t1", 2: "sahte_v3_t2"}}
TEST_HAFTALARI = ("2026-09-07", "2026-10-12")      # F2-05'in dondurulmuş test haftaları (önceden kayıt)


def talep_testi():
    d = talep.talep_veri_seti("gercek")
    test = d[(d.hafta >= TEST_HAFTALARI[0]) & (d.hafta <= TEST_HAFTALARI[1])]
    sonuc = {}
    for surum, sahteler in SURUMLER.items():
        s, _, _ = talep.degerlendir(sahteler, test)
        sonuc[surum] = s
    return sonuc


def iade_testi():
    gercek = gbm.goreli_ekle(iade_veri_seti("gercek"))
    satirlar = []
    for surum, sahteler in SURUMLER.items():
        for tohum, ad in sahteler.items():
            son, secilen, sahte_auc = f202_egit(ad)
            p = gbm.tahmin(son, gercek)
            fark = bootstrap_auc_farki(gercek.iade, p, gercek.model_onceki_iade_orani)
            satirlar.append({"surum": surum, "tohum": tohum, "secilen": secilen, "sahte_dogrulama_auc": sahte_auc,
                             "gercek_auc": siniflandirma_olcutleri(gercek.iade, p)["roc_auc"],
                             "fark_urun_gecmisi": fark["ortalama"], "fark_alt": fark["alt"], "fark_ust": fark["ust"],
                             "ortalama_tahmin": float(p.mean()), "gerceklesen": float(gercek.iade.mean())})
    return pd.DataFrame(satirlar)


def calistir():
    t = talep_testi()
    i = iade_testi()
    sonuc = {"talep": t, "iade": i.to_dict("records")}
    (CIKTILAR / "modeller").mkdir(parents=True, exist_ok=True)
    (CIKTILAR / "modeller" / "F1-07_sahte_v3.json").write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    return t, i


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 200)
    t, i = calistir()
    print("B. Talep (F2-05), gerçek test, WAPE (düşük iyi):")
    for surum, s in t.items():
        for tohum, g in s["gercek"].items():
            f = g["fark_en_iyi_referans"]
            print(f"  {surum} tohum {tohum:>2}: model {g['wape']:.3f} · naif {g['wape_naif']:.3f}"
                  f" · ort4 {g['wape_ort4']:.3f}"
                  f" · fark {f['fark']:+.3f} [{f['alt']:+.3f}, {f['ust']:+.3f}] · mağaza {g['magaza_wape']:.3f}"
                  f" · toplam {g['toplam_tahmin']:.0f}/{g['toplam_adet']:.0f} · seçilen {g['secilen']}")
        print(f"  {surum} karar (≥2/3 tohumda anlamlı iyi): {s['karar']}")
        for tohum, g in s["seviye1"].items():
            print(f"    sahte doğrulama {tohum:>2}: model {g['wape']:.3f}, ort4 {g['wape_ort4']:.3f}, "
                  f"kâhin {g['kahin_wape']:.3f}")
    print("\nC. İade riski (F2-02), gerçek test:")
    print(i.round(4).to_string(index=False))
    print(i.groupby("surum")[["gercek_auc", "fark_urun_gecmisi", "ortalama_tahmin"]].mean().round(4).to_string())
