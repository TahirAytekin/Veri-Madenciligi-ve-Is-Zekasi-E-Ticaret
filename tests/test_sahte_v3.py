"""Sahte veri v3 deneyi testleri (F1-07): talep dinamiği istatistikleri ve yan etkisiz talep değerlendirmesi."""
import pandas as pd

from hazirlama import kalibrasyon_talep as k
from modeller import talep
from modeller.ortak.degerlendir import CIKTILAR


def test_haftalik_seri_tam_haftalar():
    d = k.haftalik("sahte")
    assert (d.hafta.dt.dayofweek == 0).all()
    bas, bit = (pd.Timestamp(x) for x in k.PENCERE)
    assert d.hafta.min() >= bas and d.hafta.max() + pd.Timedelta(days=6) < bit
    assert (d.adet >= 0).all()


def test_istatistikler_ve_karsilastirma():
    s = k.istatistikler("sahte")
    assert 0 < s["D1_naif_ort4_orani"] < 3 and -1 <= s["D2_otokorelasyon"] <= 1
    assert 0 < s["D3_ilk10_payi"] <= 1 and s["D4_iade_egilimi"] > 0
    t = k.karsilastir(s, s)
    assert t.tutuyor.all() and len(t) == len(k.TOLERANS)


def test_talep_degerlendir_dosya_yazmaz():
    yollar = list(CIKTILAR.rglob("*F2-05*"))
    once = {p: p.stat().st_mtime_ns for p in yollar}
    sonuc, modeller, _ = talep.degerlendir({42: "sahte"}, test=None)
    assert 42 in sonuc["seviye1"] and 42 in modeller
    assert {p: p.stat().st_mtime_ns for p in yollar} == once
