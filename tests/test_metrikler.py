"""analiz/metrikler.py testleri: her metrik hesaplanıyor mu, bağımsız hesapla tutuyor mu, kurallar uygulanıyor mu?"""
import re

import numpy as np
import pandas as pd
import pytest
from ortak import PROJE, VERI

from analiz import metrikler as m

VERILER = ["sahte"] + (["gercek"] if (VERI / "gercek" / "siparisler.csv").exists() else [])
TOPLANABILIR = ["ciro_brut", "ciro_net", "satilan_adet", "teslim_edilen_adet", "iade_adet", "iade_tutari",
                "komisyon_tutari", "kargo_gideri", "katki_payi"]


@pytest.mark.parametrize("veri", VERILER)
@pytest.mark.parametrize("ad", list(m.METRIKLER))
def test_metrik_hesaplanir(veri, ad):
    assert np.isfinite(m.hesapla(ad, veri)), f"{veri}: {ad}"


@pytest.mark.parametrize("veri", VERILER)
def test_oranlar_0_ile_1_arasinda(veri):
    for ad, metrik in m.METRIKLER.items():
        if metrik.birim == "oran":
            assert 0 <= m.hesapla(ad, veri) <= 1, ad


@pytest.mark.parametrize("veri", VERILER)
def test_ciro_net_bagimsiz_hesapla_ayni(veri):
    t = m.tablolar(veri)
    s = t["siparisler"]
    gecerli = s[~s.iptal & (s.paket_durumu != "UnPacked")].paket_id
    satirlar = t["siparis_satirlari"]
    beklenen = satirlar[satirlar.paket_id.isin(gecerli)].satir_net_tutar.sum()
    assert m.hesapla("ciro_net", veri) == pytest.approx(beklenen)


@pytest.mark.parametrize("ad", TOPLANABILIR)
def test_kirilim_toplami_toplama_esit(ad):
    toplam = m.hesapla(ad, "sahte")
    assert m.hesapla(ad, "sahte", kirilim="ay").sum() == pytest.approx(toplam)
    assert m.hesapla(ad, "sahte", kirilim="kategori").sum() == pytest.approx(toplam)


def test_tarih_filtresi_parcalari_toplami():
    bas, bit = m.veri_araligi("sahte")
    orta = bas + (bit - bas) / 2
    ilk = m.hesapla("ciro_net", "sahte", bas, orta.normalize())
    son = m.hesapla("ciro_net", "sahte", orta.normalize() + pd.Timedelta(days=1), bit)
    assert ilk + son == pytest.approx(m.hesapla("ciro_net", "sahte"))


def test_iade_orani_olgunlasmamis_satirlari_saymaz():
    d = m.cerceveler("sahte")["satis"]
    sinir = d.siparis_tarihi.max() - pd.Timedelta(days=m.OLGUNLASMA_GUN)
    olgun = d[d.teslim_tarihi <= sinir]
    beklenen = olgun.iade_adet.sum() / olgun.teslim_adet.sum()
    assert m.hesapla("iade_orani", "sahte") == pytest.approx(beklenen)


def test_az_ornekte_oran_hesaplanmaz():
    # Verinin son günü: teslimi olgunlaşmış satır yok -> iade oranı NaN
    son = m.veri_araligi("sahte")[1]
    assert np.isnan(m.hesapla("iade_orani", "sahte", son, son))


def test_sahte_iade_orani_uretici_ayariyla_tutarli():
    # Üretici talep oranını %16,3'e ayarlıyor; ~%72'si kabul ediliyor -> kabul edilen iade oranı ~%11-12
    assert 0.09 < m.hesapla("iade_orani", "sahte") < 0.15


def test_donem_karsilastir_onceki_donem():
    k = m.donem_karsilastir("ciro_net", "sahte", "2026-09-01", "2026-09-30")
    assert k["onceki"] == pytest.approx(m.hesapla("ciro_net", "sahte", "2026-08-02", "2026-08-31"))
    assert k["degisim"] == pytest.approx((k["deger"] - k["onceki"]) / k["onceki"])


def test_hatali_metrik_ve_kirilim():
    with pytest.raises(ValueError):
        m.hesapla("olmayan_metrik", "sahte")
    with pytest.raises(ValueError):
        m.hesapla("ciro_net", "sahte", kirilim="olmayan_kirilim")


def test_ozet_ana_kpilar():
    o = m.ozet("sahte")
    assert list(o.ad) == m.ANA_KPILAR
    assert o.deger.notna().all()


@pytest.mark.skipif("gercek" not in VERILER, reason="gerçek veri yok")
def test_bolunmus_paket_cift_sayilmaz():
    d = m.cerceveler("gercek")["satis"]
    assert not d[~d.iptal].satir_id.duplicated().any()


def test_metrik_sozlugu_kodla_senkron():
    sozluk = (PROJE / "docs" / "METRIKLER.md").read_text(encoding="utf-8")
    belgelenen = set(re.findall(r"^\| `([a-z_]+)` \|", sozluk, flags=re.M))
    assert belgelenen == set(m.METRIKLER), (
        f"sözlükte eksik: {set(m.METRIKLER) - belgelenen}, kodda olmayan: {belgelenen - set(m.METRIKLER)}")
