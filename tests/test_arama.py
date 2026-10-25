"""Bilgi tabanı ve arama testleri (F4-01, F4-02). Embedding modeli gerektiren test ağırdır (AGIR_TESTLER=1)."""
import json

import pytest

from asistan import arama, bilgi_tabani


@pytest.fixture(scope="module")
def parcalar():
    return bilgi_tabani.kaydet("sahte")


def test_bilgi_tabani_kaynaklari(parcalar):
    turler = {p["tur"] for p in parcalar}
    assert {"metrik", "belge", "icgoru", "urun", "kategori", "ay"} <= turler
    assert len({p["id"] for p in parcalar}) == len(parcalar)
    assert all(p["metin"] and p["baslik"] and p["kaynak"] for p in parcalar)
    assert sum(p["tur"] == "metrik" for p in parcalar) == 39


def test_belge_bolme_basliklari():
    b = bilgi_tabani.belge_parcalari("docs/VERI_SOZLUGU.md")
    assert any("siparisler" in p["baslik"] for p in b)
    assert all(len(p["metin"]) <= bilgi_tabani.EN_UZUN * 1.5 for p in b)


def test_kokler_turkce():
    assert arama.kokler("İadelerin ORANI") == ["iadel", "oranı"]


def test_bm25_ilgili_belgeyi_one_alir():
    b = arama.BM25(["kargo gideri ve kargo faturası", "iade oranı tanımı", "müşteri puanı"])
    s = b.skorlar("iade oranları")
    assert s.argmax() == 1 and s[2] == 0


def test_eslesir():
    p = {"id": "belge:docs/X.md#3", "kaynak": "docs/X.md", "baslik": "Sözlük › Siparisler tablosu"}
    assert arama.eslesir(p, {"kaynak": "docs/X.md", "baslik_icerir": "SİPARİSLER"})
    assert arama.eslesir(p, {"id_onek": "belge:docs/X"}) and not arama.eslesir(p, {"id": "belge:docs/X.md#4"})


def test_bm25_ile_arama_ve_tur_filtresi(parcalar):
    d = arama.Dizin("sahte")
    r = d.ara("katkı payı", k=3, yontem="bm25", tur="metrik")
    assert len(r) == 3 and all(x["tur"] == "metrik" for x in r)
    assert r[0]["skor"] >= r[-1]["skor"]


def test_test_seti_gecerli():
    sorular = json.loads(arama.TEST_SETI.read_text(encoding="utf-8"))["sorular"]
    assert len(sorular) == 30 and all(q["soru"] and q["hedef"] for q in sorular)


@pytest.mark.agir
def test_secilen_yontem_arama(parcalar):
    r = arama.ara("iade oranı nasıl hesaplanıyor", "sahte", k=5)
    assert any(x["id"] == "metrik:iade_orani" for x in r)
