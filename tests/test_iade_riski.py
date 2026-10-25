"""İade riski modeli testleri (F2-02): seçim kuralı, olasılık aralığı, sahtede referansı geçme, yardımcı ölçütler."""
import numpy as np
import pandas as pd
import pytest

from modeller import iade_riski as ir
from modeller.ortak.degerlendir import bootstrap_auc_farki, grup_ici_auc, sahte_bol, siniflandirma_olcutleri
from modeller.ortak.ozellikler import iade_veri_seti

KIMLIKLER = {"satir_id", "paket_id", "musteri_id", "model_kodu", "icerik_id", "barkod"}


@pytest.fixture(scope="module")
def sahte_egitilmis():
    sahte = ir.goreli_ekle(iade_veri_seti("sahte"))
    egitim, dogrulama = sahte_bol(sahte)
    v = ir.varyantlar()["gbm_monoton_goreli"]
    return ir.egit(egitim, dogrulama, v["ozellikler"], v["monoton"]), dogrulama


def test_varyantlarda_kimlik_ve_aktarilamaz_yok():
    for v in ir.varyantlar().values():
        assert not set(v["ozellikler"]) & KIMLIKLER
        assert not set(v["ozellikler"]) & {"ay", "saat", "indirim_orani", "model_onceki_puan"}


def test_monoton_ozellikler_listede():
    for v in ir.varyantlar().values():
        assert set(ir.MONOTON_ARTAN) <= set(v["ozellikler"])


def test_goreli_ozellikler():
    df = pd.DataFrame({"model_onceki_iade_orani": [0.2], "kategori_onceki_iade_orani": [0.1],
                       "model_onceki_kucuk_orani": [0.05], "model_onceki_buyuk_orani": [0.1]})
    d = ir.goreli_ekle(df)
    assert d.model_iade_goreli[0] == pytest.approx(2.0)
    assert d.model_kucuk_goreli[0] == pytest.approx(0.25)
    assert d.model_buyuk_goreli[0] == pytest.approx(0.5)


def test_gorulmemis_kategori_nan():
    X = ir.matris(pd.DataFrame({"kategori": ["Bluz", "Uzay Giysisi"]}), ["kategori"], {"kategori": ["Bluz"]})
    assert X.kategori.isna().tolist() == [False, True]


def test_olasiliklar_aralikta(sahte_egitilmis):
    paket, dogrulama = sahte_egitilmis
    p = ir.tahmin(paket, dogrulama)
    assert len(p) == len(dogrulama) and ((p >= 0) & (p <= 1)).all()


def test_sahtede_referanslari_gecer(sahte_egitilmis):
    # Sahte doğrulamada model, eğitimsiz referansların ikisini de geçmeli (gerçekte geçemiyor; bkz. model kartı)
    paket, dogrulama = sahte_egitilmis
    auc = siniflandirma_olcutleri(dogrulama.iade, ir.tahmin(paket, dogrulama))["roc_auc"]
    assert auc > siniflandirma_olcutleri(dogrulama.iade, dogrulama.model_onceki_iade_orani)["roc_auc"]
    assert auc > siniflandirma_olcutleri(dogrulama.iade, dogrulama.kategori_onceki_iade_orani)["roc_auc"]


def test_monotonluk_kisiti(sahte_egitilmis):
    # Kısıtlı her geçmiş oranı artarken (göreli özellikler dahil diğer her şey sabit) tahmin azalmamalı
    paket, dogrulama = sahte_egitilmis
    oranlar = np.linspace(0.0, 0.6, 13)
    for i in range(5):
        satir = dogrulama.iloc[[i * 100]]
        for ozellik in ir.MONOTON_ARTAN:
            p = ir.tahmin(paket, pd.concat([satir] * len(oranlar)).assign(**{ozellik: oranlar}))
            assert (np.diff(p) >= -1e-9).all(), ozellik


def test_kahin_skoru_formulu():
    df = iade_veri_seti("sahte").head(200)
    k = ir.kahin_skoru(df)
    # Ölçeklenmemiş ham olasılık (üretici sonra ortalamaya ölçekler); yalnızca sıralaması anlamlı
    assert (k >= 0.04).all() and k.std() > 0.05


def test_bootstrap_auc_farki():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 400)
    iyi, kotu = y + rng.normal(0, 0.5, 400), rng.normal(0, 1, 400)
    f = bootstrap_auc_farki(y, iyi, kotu, tekrar=200)
    assert f["alt"] > 0 and f["alt"] <= f["ortalama"] <= f["ust"]
    ayni = bootstrap_auc_farki(y, iyi, iyi, tekrar=50)
    assert ayni["alt"] == ayni["ust"] == 0


def test_grup_ici_auc_urun_duzeyinde_sabit_skor():
    df = pd.DataFrame({"model_kodu": ["A"] * 30 + ["B"] * 30, "iade": [0, 1] * 30})
    sabit = np.where(df.model_kodu == "A", 0.1, 0.3)
    assert grup_ici_auc(df, sabit)["auc"] == pytest.approx(0.5)
    assert grup_ici_auc(df, df.iade.to_numpy())["auc"] == pytest.approx(1.0)
    assert grup_ici_auc(df.head(10), df.iade.head(10).to_numpy())["auc"] is None
