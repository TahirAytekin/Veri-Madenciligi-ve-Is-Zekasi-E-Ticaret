"""Veri sözleşmesi: sahte ve gerçek veri aynı şemada mı, kesim sızıntı yapıyor mu?

Gerçek veri (veri/gercek) yalnızca proje sahibinde bulunur; yoksa ilgili testler atlanır.
"""
import pandas as pd
import pytest
from ortak import TABLOLAR, TARIH_SUTUNLARI, VERI, hepsini_oku, kesim_uygula

GERCEK_VAR = (VERI / "gercek" / "siparisler.csv").exists()


@pytest.fixture(scope="module")
def sahte():
    return hepsini_oku(VERI / "sahte")


def test_sahte_sema(sahte):
    for ad, sutunlar in TABLOLAR.items():
        assert list(sahte[ad].columns) == sutunlar, ad


@pytest.mark.skipif(not GERCEK_VAR, reason="gerçek veri yok (yalnızca proje sahibinde)")
def test_gercek_sema():
    gercek = hepsini_oku(VERI / "gercek")
    for ad, sutunlar in TABLOLAR.items():
        assert list(gercek[ad].columns) == sutunlar, ad


def test_sahte_baglantilar(sahte):
    assert sahte["siparis_satirlari"].barkod.isin(sahte["urunler"].barkod).all()
    assert sahte["siparis_satirlari"].paket_id.isin(sahte["siparisler"].paket_id).all()
    assert sahte["iadeler"].satir_id.isin(sahte["siparis_satirlari"].satir_id).all()


def test_kesim_sizinti_yok(sahte):
    kesim = "2026-06-30"
    sinir = pd.Timestamp(kesim) + pd.Timedelta(days=1)
    planli = {("siparisler", "tahmini_teslim_bas"), ("siparisler", "tahmini_teslim_bit"),
              ("finans_hareketleri", "odeme_tarihi"), ("kesintiler", "odeme_tarihi")}
    t = kesim_uygula(sahte, kesim)
    for ad, sutunlar in TARIH_SUTUNLARI.items():
        for s in sutunlar:
            if (ad, s) in planli:   # planlanmış tarihler sızıntı değildir
                continue
            assert not (t[ad][s] >= sinir).any(), f"{ad}.{s} kesimden sonrasını içeriyor"
