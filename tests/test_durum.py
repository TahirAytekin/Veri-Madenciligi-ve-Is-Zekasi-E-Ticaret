"""analiz/durum.py testleri: rapor yapısı, içgörü alanları, sayıların metriklerle tutarlılığı, Türkçe yazım."""
import json
import re

import pandas as pd
import pytest
from ortak import VERI

from analiz import durum
from analiz import metrikler as m

VERILER = ["sahte"] + (["gercek"] if (VERI / "gercek" / "siparisler.csv").exists() else [])
ALANLAR = {"satis", "urun", "iade", "karlilik", "musteri", "operasyon", "musteri_sesi", "stok"}


@pytest.fixture(scope="module", params=VERILER)
def rapor(request):
    return durum.durum_raporu(request.param)


def test_rapor_yapisi(rapor):
    assert {"veri", "donem", "saglik_skoru", "kpi", "icgoruler"} <= set(rapor)
    json.dumps(rapor)   # JSON'a çevrilebilmeli (NaN yok)
    assert len(rapor["icgoruler"]) >= 8


def test_saglik_skoru_0_100(rapor):
    skor = rapor["saglik_skoru"]
    assert 0 <= skor["skor"] <= 100
    for b in skor["bilesenler"]:
        assert b["puan"] is None or 0 <= b["puan"] <= 100


def test_icgoru_alanlari(rapor):
    ids = [i["id"] for i in rapor["icgoruler"]]
    assert len(ids) == len(set(ids)), "içgörü id'leri tekil olmalı"
    for i in rapor["icgoruler"]:
        assert i["alan"] in ALANLAR
        assert i["onem"] in durum.ONEM_SIRASI
        assert i["yon"] in {"olumlu", "olumsuz", "notr"}
        assert i["kanit"]["metrik"] in m.METRIKLER, "her içgörü bir metriğe dayanmalı"
        assert i["baslik"] and i["aciklama"]


def test_onem_sirasi(rapor):
    sira = [durum.ONEM_SIRASI[i["onem"]] for i in rapor["icgoruler"]]
    assert sira == sorted(sira)


def test_sayilar_metriklerle_ayni(rapor):
    donem = rapor["donem"]
    for i in rapor["icgoruler"]:
        if i["id"] == "satis_ciro_net":
            beklenen = m.hesapla("ciro_net", rapor["veri"], donem["baslangic"], donem["bitis"])
            assert i["kanit"]["deger"] == pytest.approx(beklenen)


def test_ilgili_kategoriler_veride_var(rapor):
    kategoriler = set(m.tablolar(rapor["veri"])["urunler"].kategori.dropna())
    for i in rapor["icgoruler"]:
        assert set(i["ilgili"].get("kategori", [])) <= kategoriler


def test_sayidan_sonra_ek_yok(rapor):
    # "%66'i", "16'i" gibi yanlış ekler üretilmemeli (yalnızca sabit "%80'i" / "%80'ini" serbest)
    for i in rapor["icgoruler"]:
        metin = (i["baslik"] + " " + i["aciklama"]).replace("%80'ini", "").replace("%80'i", "")
        assert not re.search(r"\d'(i|ı|u|ü|si|sı|su|sü|ini|ını)\b", metin), metin


def test_markdown_uretilir(rapor):
    md = durum.markdown(rapor)
    assert md.startswith("# Mağaza durum raporu") and "Sağlık skoru" in md


def test_donem_son_30_gun(rapor):
    bas, bit = pd.Timestamp(rapor["donem"]["baslangic"]), pd.Timestamp(rapor["donem"]["bitis"])
    assert (bit - bas).days == durum.DONEM_GUN - 1
    assert bit == m.veri_araligi(rapor["veri"])[1]
