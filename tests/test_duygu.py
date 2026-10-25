"""Duygu analizi testleri (F2-06): kelime listesi, konu kuralları, yorum tablosu, BERT (ağır)."""
import numpy as np
import pytest

from modeller import duygu as d
from modeller.duygu_sozlugu import kucult, sozluk_skoru


def test_kucult_turkce():
    assert kucult("IŞIK İyi") == "ışık iyi"


@pytest.mark.parametrize("metin,isaret", [
    ("Çok güzel, tam oldu, teşekkürler", 1),
    ("Berbat, kalitesiz, iade ettim", -1),
    ("güzel değil", -1),                      # "olumlu + değil" olumsuz sayılır
    ("tavsiye etmem", -1),                    # çok kelimeli olumsuz ifade "tavsiye"den önce yakalanır
    ("aldım", 0),
])
def test_sozluk_skoru_isaret(metin, isaret):
    assert np.sign(sozluk_skoru(metin)) == isaret


def test_sozluk_skoru_aralik():
    assert -1 < sozluk_skoru("kötü kötü kötü kötü") < 0 < sozluk_skoru("harika harika") < 1


def test_konular():
    assert d.konular("Kalıbı çok dar, kumaşı da ince") == "beden_kalip,kumas_kalite"
    assert d.konular("Kargo geç geldi") == "kargo_paket"
    assert d.konular("aldım") == ""


def test_yorum_tablosu_etiket():
    y = d.yorum_tablosu("sahte")
    assert set(y.kaynak) == {"urun", "satici"}
    assert (y.yorum.str.strip().str.len() > 0).all()
    assert (y.loc[y.puan <= 2, "etiket"] == 0).all() and (y.loc[y.puan >= 4, "etiket"] == 1).all()
    assert y.loc[y.puan == 3, "etiket"].isna().all()


@pytest.mark.agir
def test_bert_skoru():
    p = d.bert_skoru(["kumaşı çok kaliteli, tam beklediğim gibi", "defolu geldi, bir daha almam"])
    assert p[0] > 0.5 > p[1]
