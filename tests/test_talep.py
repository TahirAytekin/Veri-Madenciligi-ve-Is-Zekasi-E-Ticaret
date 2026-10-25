"""Talep tahmini testleri (F2-05): tam haftalar, sızıntısız özellikler, WAPE, kümeli bootstrap, stok tablosu."""
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from analiz import metrikler as m
from modeller import talep as t


@pytest.fixture(scope="module")
def seri():
    return t.haftalik_seri("sahte")


def test_yalnizca_tam_haftalar(seri):
    son_kayit = m.tablolar("sahte")["finans_hareketleri"].islem_tarihi.max()
    assert seri.hafta.max() + pd.Timedelta(days=7) <= son_kayit + pd.Timedelta(seconds=1)
    assert (seri.hafta.dt.dayofweek == 0).all()                       # haftalar pazartesi başlar


def test_seri_bosluksuz(seri):
    # Her ürün ilk satış haftasından son tam haftaya kadar her haftada bir satır
    for _, g in list(seri.groupby("model_kodu"))[:10]:
        assert (g.hafta.diff().dropna() == pd.Timedelta(weeks=1)).all()
    assert (seri.adet >= 0).all()


def test_ozellikler_gelecegi_gormez(seri):
    # Hedef haftanın ve sonrasının satışları değişse de o haftanın özellikleri değişmemeli
    once = t.ozellik_ekle(seri)
    hedef = once.hafta.sort_values().unique()[len(once.hafta.unique()) // 2]
    bozuk = seri.copy()
    bozuk.loc[bozuk.hafta >= hedef, "adet"] = 999
    sonra = t.ozellik_ekle(bozuk)
    a = once[once.hafta == hedef].set_index("model_kodu")[t.OZELLIKLER]
    b = sonra[sonra.hafta == hedef].set_index("model_kodu")[t.OZELLIKLER].loc[a.index]
    pd.testing.assert_frame_equal(a, b)


def test_ozellik_degerleri(seri):
    d = t.ozellik_ekle(seri)
    r = d.iloc[len(d) // 2]
    g = seri[seri.model_kodu == r.model_kodu].set_index("hafta").adet
    gecmis = g[g.index < r.hafta]
    assert r.gecen_hafta == gecmis.iloc[-1]
    assert r.ort4 == pytest.approx(gecmis.iloc[-4:].mean())
    assert gecmis.iloc[-12:].sum() > 0                                   # yalnızca aktif ürünler


def test_wape_ve_bootstrap():
    assert t.wape([10, 10], [5, 15]) == pytest.approx(0.5)
    df = pd.DataFrame({"model_kodu": list("aabbcc") * 10, "adet": [4, 6] * 30})
    y = df.adet.to_numpy(dtype=float)
    f = t.kumeli_wape_farki(df, y, y + 2, tekrar=200)
    assert f["fark"] == pytest.approx(-0.4) and f["ust"] < 0


def test_stok_tablosu_gelecek_hafta(seri):
    d = t.ozellik_ekle(seri)
    model = lgb.LGBMRegressor(**dict(t.PARAMETRELER, n_estimators=20)).fit(d[t.OZELLIKLER], d.adet)
    s = t.stok_tablosu("sahte", model)
    assert (s.hafta == seri.hafta.max() + pd.Timedelta(weeks=1)).all()
    assert (s.haftalik_hiz >= 0).all() and (s.stok_hafta >= 0).all()
    assert np.allclose(s.stok_hafta, s.stok / np.maximum(s.haftalik_hiz, 0.01), atol=1e-3)
