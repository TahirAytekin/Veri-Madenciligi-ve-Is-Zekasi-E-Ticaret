"""Gerçek–sahte karşılaştırma (F1-04): sahtede öğrenilen gerçeğe aktarılabilir mi?

Her özellik için iki soru:
  1. Dağılım benziyor mu?  sayısal: PSI (dilimler sahteden), kategorik: toplam varyasyon mesafesi (TVD)
  2. Hedefle ilişkisi aynı mı?  özellik dilimlerinde iade oranının sıralaması iki veride ne kadar benziyor (Spearman)

    python -m modeller.ortak.aktarim        # -> docs/rapor/01_gercek_sahte.md (yalnızca toplulaştırılmış oranlar)
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from hazirlama.ortak import PROJE
from modeller.ortak.degerlendir import baseline_skorlari, siniflandirma_olcutleri
from modeller.ortak.ozellikler import KATEGORIK, SAYISAL, iade_veri_seti

RAPOR = PROJE / "docs" / "rapor" / "01_gercek_sahte.md"
MIN_DILIM = 30          # ilişki karşılaştırmasında her iki veride de en az bu kadar satırı olan dilimler


def _dilimler(seri_sahte, seri_gercek, sayisal):
    if not sayisal:
        return seri_sahte.fillna("(boş)").astype(str), seri_gercek.fillna("(boş)").astype(str)
    sinirlar = np.unique(np.nanquantile(seri_sahte, np.linspace(0, 1, 11)))
    if len(sinirlar) < 3:                        # neredeyse sabit veya ikili özellik: değerin kendisi
        return seri_sahte.round(3).astype(str), seri_gercek.round(3).astype(str)
    sinirlar[0], sinirlar[-1] = -np.inf, np.inf

    def kes(s):
        return pd.cut(s, sinirlar, duplicates="drop").astype(str).where(s.notna(), "(boş)")
    return kes(seri_sahte), kes(seri_gercek)


def _psi(p, q, eps=1e-4):
    p, q = p + eps, q + eps
    return float(((q - p) * np.log(q / p)).sum())


def ozellik_karsilastirmasi(sahte, gercek, hedef="iade"):
    satirlar = []
    for ozellik in SAYISAL + KATEGORIK:
        sayisal = ozellik in SAYISAL
        ds, dg = _dilimler(sahte[ozellik], gercek[ozellik], sayisal)
        ps, pg = ds.value_counts(normalize=True), dg.value_counts(normalize=True)
        tum = ps.index.union(pg.index)
        ps, pg = ps.reindex(tum, fill_value=0), pg.reindex(tum, fill_value=0)
        mesafe = _psi(ps, pg) if sayisal else float(0.5 * (ps - pg).abs().sum())

        oran = pd.DataFrame({
            "s": sahte[hedef].groupby(ds).mean(), "ns": sahte[hedef].groupby(ds).size(),
            "g": gercek[hedef].groupby(dg).mean(), "ng": gercek[hedef].groupby(dg).size(),
        }).dropna()
        oran = oran[(oran.ns >= MIN_DILIM) & (oran.ng >= MIN_DILIM)]
        iliski = float(spearmanr(oran.s, oran.g).statistic) if len(oran) >= 3 else np.nan
        satirlar.append({"ozellik": ozellik, "tur": "sayısal" if sayisal else "kategorik",
                         "olcu": "PSI" if sayisal else "TVD", "dagilim_farki": mesafe,
                         "iliski_benzerligi": iliski, "karsilastirilan_dilim": len(oran)})
    tablo = pd.DataFrame(satirlar)
    tablo["degerlendirme"] = tablo.apply(_degerlendir, axis=1)
    return tablo


def _degerlendir(r):
    esik_orta, esik_yuksek = (0.10, 0.25) if r.olcu == "PSI" else (0.10, 0.30)
    dagilim = "düşük" if r.dagilim_farki < esik_orta else "orta" if r.dagilim_farki < esik_yuksek else "yüksek"
    if np.isnan(r.iliski_benzerligi):
        iliski = "ölçülemedi"
    else:
        iliski = "aynı yön" if r.iliski_benzerligi >= 0.5 else "zayıf" if r.iliski_benzerligi >= 0 else "ters yön"
    if iliski == "ters yön" or (dagilim == "yüksek" and iliski != "aynı yön"):
        return f"riskli (dağılım farkı {dagilim}, ilişki {iliski})"
    if dagilim == "yüksek" or iliski == "zayıf":
        return f"dikkat (dağılım farkı {dagilim}, ilişki {iliski})"
    return f"uygun (dağılım farkı {dagilim}, ilişki {iliski})"


def beden_iliskisi(sahte, gercek):
    """Beden konumu dilimlerinde 'küçük geldi' ve 'büyük geldi' oranları (beden modelinin temel varsayımı)."""
    satirlar = []
    for ad, df in [("sahte", sahte), ("gerçek", gercek)]:
        d = df.dropna(subset=["beden_konum"])
        dilim = pd.cut(d.beden_konum, [-0.01, 0.2, 0.4, 0.6, 0.8, 1.0],
                       labels=["en küçük", "küçük", "orta", "büyük", "en büyük"])
        g = d.groupby(dilim, observed=True)
        satirlar.append(pd.DataFrame({
            "veri": ad, "n": g.size(),
            "kucuk_geldi": g.iade_nedeni.apply(lambda s: (s == "beden_kucuk").mean()),
            "buyuk_geldi": g.iade_nedeni.apply(lambda s: (s == "beden_buyuk").mean())}))
    return pd.concat(satirlar).reset_index(names="beden_konum")


def _yuzde(x):
    return "—" if pd.isna(x) else f"%{x * 100:.1f}".replace(".", ",")


def _sayi(x, b=3):
    return "—" if pd.isna(x) else f"{x:.{b}f}".replace(".", ",")


def rapor_yaz():
    sahte, gercek = iade_veri_seti("sahte"), iade_veri_seti("gercek")
    tablo = ozellik_karsilastirmasi(sahte, gercek)
    beden = beden_iliskisi(sahte, gercek)
    temel = pd.DataFrame({ad: [_yuzde(df.iade.mean()), f"{len(df):,}".replace(",", "."),
                               f"{df.siparis_tarihi.min().date()} – {df.siparis_tarihi.max().date()}"]
                          for ad, df in [("sahte (eğitim)", sahte), ("gerçek (test)", gercek)]},
                         index=["iade oranı", "satır", "dönem"])
    baz = {ad: {k: siniflandirma_olcutleri(df.iade, v)["roc_auc"] for k, v in baseline_skorlari(df).items()}
           for ad, df in [("sahte", sahte), ("gerçek", gercek)]}

    s = ["# Gerçek–sahte karşılaştırma (F1-04)", "",
         "Modeller sahte veriyle eğitilip gerçek verinin son 3 ayında test edilecek. Bu rapor, iade riski ve beden",
         "modellerinin kullanacağı her özelliğin iki veride **benzer dağılıp dağılmadığını** ve **iade ile ilişkisinin",
         "aynı yönde olup olmadığını** gösterir. Üretim: `python -m modeller.ortak.aktarim` (yalnızca toplulaştırılmış",
         "oranlar içerir).", "", "## Veri", "", "| | " + " | ".join(temel.columns) + " |",
         "|---|" + "---|" * len(temel.columns),
         *[f"| {i} | " + " | ".join(r) + " |" for i, r in zip(temel.index, temel.values.tolist())], "",
         "## Eğitimsiz referans (baseline) AUC", "",
         "Mağazanın kendi geçmişinden hesaplanan oranların iadeyi ne kadar ayırt ettiği.",
         "Modellerin geçmesi gereken çıta.", "",
         "| skor | sahte | gerçek |", "|---|---|---|"]
    for k in baz["sahte"]:
        s.append(f"| {k} | {_sayi(baz['sahte'][k])} | {_sayi(baz['gerçek'][k])} |")
    s += ["", "## Özellik karşılaştırması", "",
          "- **Dağılım farkı:** sayısal özelliklerde PSI (<0,10 düşük, 0,10–0,25 orta, >0,25 yüksek),",
          "  kategoriklerde TVD (<0,10 düşük, 0,10–0,30 orta, >0,30 yüksek).",
          "- **İlişki benzerliği:** özellik dilimlerindeki iade oranlarının iki veri arasındaki Spearman",
          f"  korelasyonu (her iki veride de en az {MIN_DILIM} satırı olan dilimler). 1'e yakın: sahtedeki ilişki",
          "  gerçekte de var.", "",
          "| özellik | tür | ölçü | dağılım farkı | ilişki benzerliği | dilim | değerlendirme |",
          "|---|---|---|---|---|---|---|"]
    for r in tablo.sort_values(["degerlendirme", "dagilim_farki"], ascending=[False, False]).itertuples():
        s.append(f"| `{r.ozellik}` | {r.tur} | {r.olcu} | {_sayi(r.dagilim_farki)} | {_sayi(r.iliski_benzerligi, 2)} | "
                 f"{r.karsilastirilan_dilim} | {r.degerlendirme} |")
    s += ["", "## Beden konumu ve beden kaynaklı iade", "",
          "Beden modelinin temel varsayımı: küçük bedenlerde 'küçük geldi', büyük bedenlerde 'büyük geldi'",
          "daha sık.", "",
          "| beden konumu | veri | satır | küçük geldi | büyük geldi |", "|---|---|---|---|---|"]
    for r in beden.sort_values(["beden_konum", "veri"]).itertuples():
        s.append(f"| {r.beden_konum} | {r.veri} | {r.n} | {_yuzde(r.kucuk_geldi)} | {_yuzde(r.buyuk_geldi)} |")
    s += ["", "## Sonuç", "", "<!-- SONUC -->", ""]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    eski = RAPOR.read_text(encoding="utf-8") if RAPOR.exists() else ""
    sonuc = eski.split("<!-- SONUC -->")[1].strip() if "<!-- SONUC -->" in eski else "_Yorum eklenecek._"
    RAPOR.write_text("\n".join(s).replace("<!-- SONUC -->", "<!-- SONUC -->\n" + sonuc), encoding="utf-8")
    return tablo, beden


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    tablo, beden = rapor_yaz()
    print(tablo.round(3).to_string(index=False))
    print(beden.round(3).to_string(index=False))
    print(f"\n-> {RAPOR.relative_to(PROJE).as_posix()}")
