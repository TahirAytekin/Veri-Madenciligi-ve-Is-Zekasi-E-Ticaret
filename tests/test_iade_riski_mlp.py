"""İade riski MLP testleri (F2-03): girdi hazırlama, monotonluk, kaydet/yükle, tekrarlanabilirlik."""
import numpy as np
import pandas as pd
import pytest
import torch

from modeller import iade_riski_mlp as m
from modeller.iade_riski import MONOTON_ARTAN, goreli_ekle
from modeller.ortak.degerlendir import sahte_bol
from modeller.ortak.ozellikler import MODEL_KATEGORIK, iade_veri_seti


@pytest.fixture(scope="module")
def veri():
    egitim, dogrulama = sahte_bol(goreli_ekle(iade_veri_seti("sahte")))
    return egitim, dogrulama


@pytest.fixture(scope="module")
def genis_derin(veri):
    egitim, _ = veri
    h = m.hazirlayici(egitim)
    ag, _ = m.egit_tek(h, egitim, genis_derin=True, tohum=0, epoch=3)
    return {"hazirlayici": h, "genis_derin": True, "aglar": [ag], "epochlar": [3]}


def test_olcekleme_yalnizca_egitimden(veri):
    egitim, dogrulama = veri
    h = m.hazirlayici(egitim)
    s, k = m.tensorler(dogrulama, h)
    assert torch.isfinite(s).all()
    assert s.shape == (len(dogrulama), len(m.sayisal_adlari(h)))
    assert k.shape == (len(dogrulama), len(MODEL_KATEGORIK))
    assert h["ortalama"]["fiyat_endeksi"] == pytest.approx(egitim.fiyat_endeksi.mean())


def test_gorulmemis_kategori_sifir(veri):
    egitim, dogrulama = veri
    h = m.hazirlayici(egitim)
    _, k = m.tensorler(dogrulama.head(3).assign(kategori="Uzay Giysisi"), h)
    assert (k[:, MODEL_KATEGORIK.index("kategori")] == 0).all()


def test_olasiliklar_aralikta(veri, genis_derin):
    p = m.tahmin(genis_derin, veri[1])
    assert len(p) == len(veri[1]) and ((p > 0) & (p < 1)).all()


def test_genis_derin_monoton(veri, genis_derin):
    # Geçmiş iade oranları yalnızca pozitif ağırlıklı doğrusal kısımda: her biri artarken tahmin azalamaz
    oranlar = np.linspace(0.0, 0.6, 13)
    for i in range(5):
        satir = veri[1].iloc[[i * 100]]
        for ozellik in MONOTON_ARTAN:
            p = m.tahmin(genis_derin, pd.concat([satir] * len(oranlar)).assign(**{ozellik: oranlar}))
            assert (np.diff(p) >= -1e-7).all(), ozellik


def test_kaydet_yukle_ayni_tahmin(veri, genis_derin):
    yuklenen = m.yukle(m.kaydedilebilir(genis_derin))
    assert np.allclose(m.tahmin(yuklenen, veri[1]), m.tahmin(genis_derin, veri[1]))


def test_ayni_tohum_ayni_sonuc(veri):
    egitim, dogrulama = veri
    h = m.hazirlayici(egitim)
    p1 = m.tahmin({"hazirlayici": h, "aglar": [m.egit_tek(h, egitim, False, tohum=3, epoch=1)[0]]}, dogrulama)
    p2 = m.tahmin({"hazirlayici": h, "aglar": [m.egit_tek(h, egitim, False, tohum=3, epoch=1)[0]]}, dogrulama)
    assert np.allclose(p1, p2)


def test_erken_durdurma_en_iyi_epoch(veri):
    egitim, dogrulama = veri
    h = m.hazirlayici(egitim)
    _, epoch = m.egit_tek(h, egitim, False, tohum=0, dogrulama=dogrulama)
    assert 1 <= epoch <= m.AYARLAR["en_cok_epoch"]
