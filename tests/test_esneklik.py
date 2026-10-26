"""İndirim esnekliği testleri (F2-10): yöntem bilinen esnekliği bulur, sabit esneklikte sapma doğru, panel yapısı."""
import numpy as np
import pandas as pd
import pytest

from hazirlama.kalibrasyon import PENCERE
from modeller import esneklik as es


@pytest.mark.parametrize("dogru", [0.0, 1.0, 2.0])
def test_bilinen_esnekligi_bulur(dogru):
    rng = np.random.default_rng(7)
    u, h = np.repeat(np.arange(80), 40), np.tile(np.arange(40), 80)
    a, d = rng.normal(2, 0.7, 80), rng.normal(0, 0.3, 40)
    pay = np.where(rng.random(len(u)) < 0.5, rng.choice([0.05, 0.15, 0.30], len(u)), 0.0)
    x = -np.log(1 - pay)
    y = rng.poisson(np.exp(a[u] + d[h] + dogru * x))
    assert es.poisson_fe(y, u, h, x)[0] == pytest.approx(dogru, abs=0.15)


def test_sabit_esneklikte_sapma_en_iyi_degerde_en_dusuk():
    rng = np.random.default_rng(1)
    u, h = np.repeat(np.arange(50), 30), np.tile(np.arange(30), 50)
    x = -np.log(1 - np.where(rng.random(len(u)) < 0.5, 0.2, 0.0))
    y = rng.poisson(np.exp(1.5 + 1.2 * x), len(u))
    e, sapma = es.poisson_fe(y, u, h, x)
    assert sapma <= es.poisson_fe(y, u, h, x, e=0.0)[1] and sapma <= es.poisson_fe(y, u, h, x, e=3.0)[1]


def test_panel_yapisi():
    p = es.panel("sahte", *(pd.Timestamp(x) for x in PENCERE))
    assert (p.hafta.dt.dayofweek == 0).all() and (p.adet >= 0).all()
    assert p.kupon_payi.between(0, 0.9).all() and (p.indirim_payi >= p.kupon_payi - 1e-9).all()
    assert (p.groupby("model_kodu").adet.sum() >= es.MIN_SATIS).all()
