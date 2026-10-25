"""Doğrulama raporu testleri (F2-12): depodaki tablo şeması, sayı biçimi, yorum bölümünün korunması."""
import json

import pytest

from modeller import dogrulama_raporu as r

ALANLAR = {"id", "ad", "soru", "yontem", "metrik", "yon", "gercek_model", "referans_adi", "gercek_referans", "fark",
           "alt", "ust", "karar", "seviye1", "tohumlar", "not", "web", "kart"}


@pytest.fixture(scope="module")
def tablo():
    return json.loads(r.RAPOR_JSON.read_text(encoding="utf-8"))


def test_depodaki_tablo_semasi(tablo):
    ids = [x["id"] for x in tablo["satirlar"]]
    assert ids[:7] == ["F2-02", "F2-03", "F2-04A", "F2-04B", "F2-04C", "F2-05", "F2-06"]
    assert set(ids[7:]) <= {"F3-04"}
    for x in tablo["satirlar"]:
        assert ALANLAR <= set(x), x["id"]
        assert x["karar"] in {"basarili", "basarisiz"} and x["yon"] in {"yuksek_iyi", "dusuk_iyi"}
        assert x["alt"] <= x["fark"] <= x["ust"], x["id"]
        assert (r.PROJE / x["kart"]).exists(), x["kart"]


def test_karar_guven_araligiyla_tutarli(tablo):
    # Tohumsuz satırlarda karar doğrudan güven aralığından; tohumlularda en az 2/3 tohum
    for x in tablo["satirlar"]:
        if x["tohumlar"]:
            iyi = sum((v["alt"] > 0) if x["yon"] == "yuksek_iyi" else (v["ust"] < 0) for v in x["tohumlar"].values())
            assert (x["karar"] == "basarili") == (iyi >= 2), x["id"]
        else:
            iyi = x["alt"] > 0 if x["yon"] == "yuksek_iyi" else x["ust"] < 0
            assert (x["karar"] == "basarili") == iyi, x["id"]


def test_sayi_bicimi():
    assert r._s(0.12345) == "0,123"
    assert r._s(0.01, isaret=True) == "+0,010"
    assert r._s(None) == "—"


def test_yorum_korunur(tablo):
    metin = r.markdown(tablo, "elle yazılmış yorum")
    assert f"{r.YORUM_BAS}\nelle yazılmış yorum\n{r.YORUM_SON}" in metin
    assert "## Sonuç tablosu" in metin and "F2-04C" in metin
