"""Sahte veri kalibrasyonu testleri (F1-06): K1–K6 istatistikleri, tohum ortalaması, karşılaştırma."""
import pytest
from ortak import VERI

from hazirlama import kalibrasyon as k

GERCEK_VAR = (VERI / "gercek" / "siparisler.csv").exists()


@pytest.fixture(scope="module")
def sahte():
    return k.istatistikler("sahte")


def test_istatistikler_tam(sahte):
    for anahtar in ["K1_iade_orani", "K2_kategori", "K3_urun_std", "K3_yari_donem_korelasyonu", "K4_beden_konumu",
                    "K5_neden_paylari", "K6_kalip"]:
        assert anahtar in sahte
    assert 0 < sahte["K1_iade_orani"] < 1
    assert sum(sahte["K5_neden_paylari"].values()) == pytest.approx(1)
    assert sum(sahte["K6_kalip"].values()) == pytest.approx(1)
    assert all(v["satis"] >= k.MIN_KATEGORI_SATIS for v in sahte["K2_kategori"].values())


def test_pencere_disi_kullanilmaz():
    # Pencere dışındaki bir aralıkta hiç satış yoksa istatistik de yok: pencere gerçekten uygulanıyor
    f, talepler = k._birimler("sahte", ("2024-01-01", "2024-02-01"))
    assert len(f) == 0 and len(talepler) == 0


def test_ortalama_ic_ice():
    a = {"veri": "a", "x": 1.0, "d": {"p": 0.2, "q": 0.4}}
    b = {"veri": "b", "x": 3.0, "d": {"p": 0.4}}
    o = k.ortalama([a, b])
    assert o["x"] == 2.0 and o["d"]["p"] == pytest.approx(0.3) and o["d"]["q"] == 0.4 and o["veri"] == "a+b"


def test_kendisiyle_karsilastirma_hepsi_tutar(sahte):
    t = k.karsilastir(sahte, sahte)
    assert t.tutuyor.all()
    assert (t[t.tolerans.notna()].fark.abs() < 1e-12).all()


@pytest.mark.skipif(not GERCEK_VAR, reason="gerçek veri yalnızca proje sahibinde")
def test_v2_genel_ve_kategori_kalibre(sahte):
    # Regresyon: sahte v2 genel iade oranı ve kategori düzeyi test öncesi gerçeğe uymaya devam etmeli
    t = k.karsilastir(k.istatistikler("gercek"), sahte).set_index("istatistik")
    assert t.loc["iade oranı"].tutuyor
    assert t.filter(like="sıralama korelasyonu", axis=0).tutuyor.all()
