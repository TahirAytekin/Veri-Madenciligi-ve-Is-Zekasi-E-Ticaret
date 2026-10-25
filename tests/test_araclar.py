"""Asistan araçları testleri (F4-03): şemalar, doğrulama, araç sonuçlarının metriklerle tutarlılığı."""
import json

import pytest

from analiz import metrikler as m
from asistan import araclar as a


def _c(ad, **girdi):
    return json.loads(a.calistir(ad, girdi, "sahte"))


def test_semalar_strict_ve_tam():
    adlar = [s["name"] for s in a.semalar()]
    assert len(adlar) == len(set(adlar)) >= 8
    for s in a.semalar():
        g = s["input_schema"]
        assert s["strict"] and g["additionalProperties"] is False
        assert set(g["required"]) == set(g["properties"])                    # strict: tüm alanlar listede
        assert s["description"] and all(p["description"] for p in g["properties"].values())


def test_dogrulama():
    assert "bilinmeyen alan" in _c("metrik_hesapla", metrik="iade_orani", fazla=1)["hata"]
    assert "zorunlu alan" in _c("metrik_hesapla")["hata"]
    assert "bekleniyordu" in _c("beden_oner", boy="165", kilo=58)["hata"]
    assert "izin verilen" in _c("tahmin_getir", tur="hepsi")["hata"]
    assert "bilinmeyen araç" in json.loads(a.calistir("dosya_sil", {}, "sahte"))["hata"]


def test_metrik_hesapla_metriklerle_ayni():
    bit = m.veri_araligi("sahte")[1]
    r = _c("metrik_hesapla", metrik="ciro_net", baslangic="2026-01-01", bitis=str(bit.date()))
    assert r["deger"] == pytest.approx(m.hesapla("ciro_net", "sahte", "2026-01-01", bit), rel=1e-6)
    t = _c("metrik_hesapla", metrik="satilan_adet", kirilim="kategori", siralama="azalan", ilk_n=3)["tablo"]
    assert len(t) == 3 and t[0]["deger"] >= t[1]["deger"] >= t[2]["deger"]


def test_metrik_hatalari_yonlendirici():
    assert "iade_orani" in _c("metrik_hesapla", metrik="iade oranı")["hata"]
    assert "kırılım" in _c("metrik_hesapla", metrik="ciro_net", kirilim="gezegen")["hata"]


def test_sql_ve_sema():
    r = _c("sql_sorgula", sorgu="select count(*) as n from urunler")
    assert r["satirlar"][0][0] == len(m.tablolar("sahte")["urunler"])
    assert "urunler" in _c("tablo_semasi")["tablolar"]


def test_sql_satir_siniri():
    r = _c("sql_sorgula", sorgu="select hareket_id from finans_hareketleri")
    assert r["satir_sayisi"] == a.SQL_SATIR and r["kesildi"]
    genis = a.calistir("sql_sorgula", {"sorgu": "select * from finans_hareketleri"}, "sahte")
    assert len(genis) <= a.EN_UZUN_SONUC and json.loads(genis)["kesildi"]       # uzun sonuç geçerli JSON kalır


def test_diger_araclar():
    assert _c("tahmin_getir", tur="dogrulama")["modeller"]
    assert "adaylar" in _c("urun_karti", urun="eşofman") or "kart" in _c("urun_karti", urun="eşofman")
    assert "kart" in _c("urun_karti", urun="esf01")
    assert _c("tavsiyeleri_getir", plan=True)["plan"]["aksiyonlar"]
    s = _c("senaryo_calistir", beden_iade_azalis=0.3)
    assert s["aylik_katki_farki"] > 0 and s["varsayimlar"]
    assert _c("beden_oner", boy=165, kilo=58)["beden"] in {"S", "M", "L"}
    assert "aralığında" in _c("beden_oner", boy=300, kilo=58)["hata"]
    assert "hata" in _c("senaryo_calistir", ek_indirim=2.0)


def test_urun_bul():
    assert a.urun_bul("sahte", "esf01") == ["esf01"]
    assert all(k.startswith("esf") for k in a.urun_bul("sahte", "Eşofman Altı"))
