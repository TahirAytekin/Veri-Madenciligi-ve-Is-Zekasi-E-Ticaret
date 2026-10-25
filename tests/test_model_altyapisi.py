"""Model altyapısı testleri (F2-01, F1-04): aktarılabilir özellikler, sızıntı, etiketler, değerlendirme."""
import numpy as np
import pandas as pd
import pytest
from ortak import VERI

from analiz import metrikler as m
from modeller.ortak import aktarim, degerlendir, ozellikler
from modeller.ortak.ozellikler import beden_degeri, iade_veri_seti, renk_grubu

VERILER = ["sahte"] + (["gercek"] if (VERI / "gercek" / "siparisler.csv").exists() else [])
KIMLIKLER = {"satir_id", "paket_id", "musteri_id", "model_kodu", "icerik_id", "barkod"}


@pytest.fixture(scope="module", params=VERILER)
def veri(request):
    return request.param


def test_iki_veride_ayni_sutunlar():
    sutunlar = [list(iade_veri_seti(v).columns) for v in VERILER]
    assert all(s == sutunlar[0] for s in sutunlar)


def test_ozellik_listelerinde_kimlik_yok():
    tum = set(ozellikler.SAYISAL + ozellikler.KATEGORIK + ozellikler.MODEL_SAYISAL + ozellikler.MODEL_KATEGORIK)
    assert not tum & KIMLIKLER
    assert not set(ozellikler.AKTARILAMAZ) & set(ozellikler.MODEL_SAYISAL + ozellikler.MODEL_KATEGORIK)


def test_sayisal_ozellikler_sayi(veri):
    df = iade_veri_seti(veri)
    for c in ozellikler.SAYISAL:
        assert pd.api.types.is_numeric_dtype(df[c]), c


def test_etiketler_olgun(veri):
    df = iade_veri_seti(veri)
    sinir = m.veri_araligi(veri)[1] + pd.Timedelta(days=1) - pd.Timedelta(days=m.OLGUNLASMA_GUN)
    assert (df.teslim_tarihi <= sinir).all()
    assert set(df.iade.unique()) <= {0, 1}
    assert set(df.iade_nedeni.unique()) <= {"yok", "beden_kucuk", "beden_buyuk", "diger"}
    assert ((df.iade == 0) == (df.iade_nedeni == "yok")).all()


def test_gecmis_ozellikleri_yalnizca_onceki_olaylar(veri):
    # model_onceki_satis_log, siparişten KESİNLİKLE ÖNCEKİ finans 'Satış' kayıtlarından hesaplanmalı
    df = iade_veri_seti(veri).sample(40, random_state=0)
    t = m.tablolar(veri)
    model = t["urunler"].drop_duplicates("barkod").set_index("barkod").model_kodu
    f = t["finans_hareketleri"]
    satis = f[f.islem_turu == "Satış"].assign(model_kodu=lambda x: x.barkod.map(model))
    for r in df.itertuples():
        beklenen = ((satis.model_kodu == r.model_kodu) & (satis.islem_tarihi < r.siparis_tarihi)).sum()
        assert np.expm1(r.model_onceki_satis_log) == pytest.approx(beklenen)


def test_beden_konum_araligi(veri):
    k = iade_veri_seti(veri).beden_konum.dropna()
    assert k.between(0, 1).all() and k.nunique() > 3


@pytest.mark.parametrize("beden,beklenen", [
    ("M", ("harf", 4.0)), ("xs", ("harf", 2.0)), ("XXS/26", ("harf", 1.0)), ("2XL", ("harf", 7.0)),
    ("38", ("sayi", 38.0)), ("110 CM", ("diger", None)), ("14-15 Yaş", ("diger", None)), ("36 - 40", ("diger", None)),
])
def test_beden_degeri(beden, beklenen):
    tip, deger = beden_degeri(beden)
    assert tip == beklenen[0]
    assert (np.isnan(deger) if beklenen[1] is None else deger == beklenen[1])


@pytest.mark.parametrize("renk,grup", [("Siyah", "siyah_koyu"), ("BlackStar", "siyah_koyu"), ("White", "beyaz_acik"),
                                       ("GrayStar", "gri"), ("Lacivert", "mavi"), ("Bordoo", "pembe_kirmizi"),
                                       ("Kamuflaj", "toprak_yesil"), ("Logo", "desenli_diger")])
def test_renk_grubu(renk, grup):
    assert renk_grubu(renk) == grup


def test_sahte_bol_zamana_gore():
    df = iade_veri_seti("sahte")
    egitim, dogrulama = degerlendir.sahte_bol(df)
    assert egitim.siparis_tarihi.max() < dogrulama.siparis_tarihi.min()
    assert len(egitim) + len(dogrulama) == len(df)


def test_siniflandirma_olcutleri():
    y = np.array([0, 0, 1, 1])
    assert degerlendir.siniflandirma_olcutleri(y, [0.1, 0.2, 0.8, 0.9])["roc_auc"] == 1.0
    assert degerlendir.siniflandirma_olcutleri(y, [0.9, 0.8, 0.2, 0.1])["roc_auc"] == 0.0
    assert degerlendir.siniflandirma_olcutleri([0, 0], [0.1, 0.2])["roc_auc"] is None


def test_psi_ayni_dagilimda_sifir():
    p = pd.Series([0.2, 0.3, 0.5])
    assert aktarim._psi(p, p) == pytest.approx(0, abs=1e-9)
    assert aktarim._psi(p, pd.Series([0.5, 0.3, 0.2])) > 0.1
