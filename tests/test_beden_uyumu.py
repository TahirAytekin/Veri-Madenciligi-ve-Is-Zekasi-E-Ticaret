"""Beden uyumu testleri (F2-04): kalıp skoru, kalıp etiketi, yön modeli, beden önerisi."""
import numpy as np
import pandas as pd
import pytest

from modeller import beden_uyumu as b
from modeller.ortak.degerlendir import sahte_bol

ONERI = {"katsayi": [0.0, 0.1], "sabit": -2.0, "en_sik": 4.0, "alt": 1.0, "ust": 9.0, "n": 0, "kalip_duzeltmesi": True}


@pytest.fixture(scope="module")
def yon():
    return b.yon_veri_seti("sahte")


def test_kalip_skoru_onsel_ve_aralik():
    olaylar, _ = b._beden_olaylari("sahte")
    urun = olaylar.model_kodu.value_counts().index[0]
    ilk = olaylar[olaylar.model_kodu == urun].son_guncelleme.min()
    k = b.kalip_ozellikleri("sahte", [urun, urun], [ilk, ilk + pd.Timedelta(days=400)])
    assert k.beden_iadesi[0] == 0                          # ilk iadeden önce: geçmiş yok, skor önsel
    assert k.beden_iadesi[1] > 0
    assert k.kalip_skoru.between(0, 1).all() and k.beden_iade_orani.between(0, 1).all()


def test_kalip_skoru_yalnizca_onceki_olaylar():
    olaylar, _ = b._beden_olaylari("sahte")
    urun = olaylar.model_kodu.value_counts().index[0]
    o = olaylar[olaylar.model_kodu == urun].sort_values("son_guncelleme")
    zaman = o.son_guncelleme.iloc[5]
    k = b.kalip_ozellikleri("sahte", [urun], [zaman])
    assert k.beden_iadesi[0] == (o.son_guncelleme < zaman).sum()


def test_kalip_etiketi():
    e = b.kalip_etiketi(np.array([0.9, 0.9, 0.2, 0.5]), np.array([10, 2, 10, 10]))
    assert e.tolist() == ["dar", "belirsiz", "bol", "belirsiz"]


def test_beden_oner():
    assert b.beden_oner(165, 60, oneri=ONERI) == "M"                     # -2 + 6 = 4 -> M
    assert b.beden_oner(165, 70, oneri=ONERI) == "L"
    assert b.beden_oner(165, 60, kalip_skoru=0.9, kalip_iadesi=10, oneri=ONERI) == "L"   # dar: bir büyük
    assert b.beden_oner(165, 60, kalip_skoru=0.1, kalip_iadesi=10, oneri=ONERI) == "S"   # bol: bir küçük
    assert b.beden_oner(165, 60, kalip_skoru=0.9, kalip_iadesi=2, oneri=ONERI) == "M"    # az kanıt: düzeltme yok
    assert b.beden_oner(165, 300, oneri=ONERI) == b.HARF_ADI[9]          # sınırda kalır


def test_ideal_harf_degeri_uretici_kurali():
    # skor = kilo + (boy − 165) × 0,35; eşikler 44, 49, 55, 62, 70, 79, 88 (2XS ... 3XL)
    assert b.HARF_ADI[int(b.ideal_harf_degeri([165], [58])[0])] == "M"
    assert b.HARF_ADI[int(b.ideal_harf_degeri([165], [40])[0])] == "2XS"
    assert b.HARF_ADI[int(b.ideal_harf_degeri([165], [95])[0])] == "3XL"


def test_yon_veri_seti(yon):
    assert set(yon.iade_nedeni.unique()) <= {"beden_kucuk", "beden_buyuk"}
    assert ((yon.kucuk == 1) == (yon.iade_nedeni == "beden_kucuk")).all()
    assert yon[b.YON_SAYISAL].kalip_skoru.notna().all()


def test_yon_modeli_kalip_skorunda_monoton(yon):
    egitim, dogrulama = sahte_bol(yon)
    paket, p = b.yon_egit(egitim, dogrulama)
    assert ((p > 0) & (p < 1)).all()
    skorlar = np.linspace(0, 1, 11)
    for i in range(3):
        satir = dogrulama.iloc[[i * 20]]
        t = b.yon_tahmin(paket, pd.concat([satir] * len(skorlar)).assign(kalip_skoru=skorlar))
        assert (np.diff(t) >= -1e-9).all()


def test_isabet_farki():
    f = b._isabet_farki([1, 1, 1, 0] * 25, [0, 0, 1, 0] * 25, tekrar=200)
    assert f["fark"] == pytest.approx(0.5) and f["alt"] > 0
