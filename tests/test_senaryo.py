"""analiz/senaryo.py testleri: değişiklik yokken gerçekle tutarlılık, senaryoların yönü, başa baş noktası."""
import math

import pandas as pd
import pytest
from ortak import VERI

from analiz import metrikler as m
from analiz import senaryo as s

VERILER = ["sahte"] + (["gercek"] if (VERI / "gercek" / "siparisler.csv").exists() else [])


@pytest.fixture(scope="module", params=VERILER)
def veri(request):
    return request.param


def test_degisiklik_yoksa_senaryo_bazla_ayni(veri):
    r = s.simule(veri)
    for k, v in r["fark"].items():
        assert v == pytest.approx(0, abs=1e-6), k


def test_model_gercek_katki_payini_tutturur(veri):
    # İadelerin kesinleştiği bir dönemde (son 21 gün hariç) model katkısı ile metrik katkısı yakın olmalı
    bit = m.veri_araligi(veri)[1] - pd.Timedelta(days=m.OLGUNLASMA_GUN + 1)
    bas = bit - pd.Timedelta(days=59)
    model = s.simule(veri, bas, bit)["baz"]["katki_payi"]
    gercek = m.hesapla("katki_payi", veri, bas, bit)
    assert model == pytest.approx(gercek, rel=0.05)


def test_iade_azalisi_katkiyi_artirir(veri):
    katkilar = [s.simule(veri, iade_azalis=x)["senaryo"]["katki_payi"] for x in (0, 0.2, 0.5)]
    assert katkilar[0] < katkilar[1] < katkilar[2]


def test_beden_iadesi_tamamen_onlenirse(veri):
    r = s.simule(veri, beden_iade_azalis=1.0)
    b = r["baz_degerler"]
    assert r["senaryo_iade_orani"] == pytest.approx(b["iade_orani"] * (1 - b["beden_payi"]))


def test_esnekliksiz_indirim_katkiyi_dusurur(veri):
    r = s.simule(veri, ek_indirim=0.1)
    assert r["fark"]["katki_payi"] < 0
    assert r["basa_bas"]["carpan"] > 1


def test_basa_bas_esnekliginde_katki_degismez(veri):
    # Başa baş esnekliğiyle satış artışı, indirimin kaybını tam karşılamalı
    e = s.simule(veri, ek_indirim=0.1)["basa_bas"]["gerekli_esneklik"]
    r = s.simule(veri, ek_indirim=0.1, esneklik=e)
    assert r["fark"]["katki_payi"] == pytest.approx(0, abs=1)


def test_komisyon_farki(veri):
    r = s.simule(veri, komisyon_farki=1)
    assert r["fark"]["komisyon"] == pytest.approx(r["baz"]["elde_kalan_satis"] * 0.01)


def test_desi_azalisi_kargoyu_artirmaz(veri):
    for d in (1, 2, 3):
        assert s.simule(veri, desi_azalis=d)["fark"]["kargo"] <= 0


def test_urun_maliyeti(veri):
    r = s.simule(veri, maliyet_orani=0.4)
    t = r["baz"]
    assert t["net_kar"] == pytest.approx(t["katki_payi"] - t["elde_kalan_satis"] * 0.4)


def test_indirimde_urun_maliyeti_tl_olarak_sabit(veri):
    # İndirim fiyatı düşürür ama ürünün maliyeti değişmez
    r = s.simule(veri, ek_indirim=0.2, maliyet_orani=0.4)
    assert r["senaryo"]["urun_maliyeti"] == pytest.approx(r["baz"]["urun_maliyeti"])


def test_hatali_parametre():
    with pytest.raises(ValueError):
        s.simule("sahte", iade_azalis=1.5)
    with pytest.raises(ValueError):
        s.simule("sahte", ek_indirim=-0.1)


def test_ozet_ve_varsayimlar(veri):
    r = s.simule(veri, beden_iade_azalis=0.5, ek_indirim=0.05, desi_azalis=1, maliyet_orani=0.4)
    assert "katkı payı" in r["ozet"] and "→" in r["ozet"]
    assert len(r["varsayimlar"]) >= 6
    assert math.isfinite(r["aylik_katki_farki"])
