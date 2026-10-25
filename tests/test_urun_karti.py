"""Ürün sağlık kartı testleri (F3-05): bölümler, tavsiye motoruyla tutarlılık, etiket ve durum kuralları."""
import json

import pytest

from tavsiye import motor
from tavsiye import urun_karti as u


@pytest.fixture(scope="module")
def sahte():
    liste, _, b = motor.tavsiyeler("sahte")
    kartlar, bilgi = u.kartlar("sahte", liste)
    return kartlar, bilgi, liste, b


def test_kart_bolumleri(sahte):
    kartlar = sahte[0]
    assert kartlar
    for k in kartlar.values():
        assert {"model_kodu", "ad", "satis", "karlilik", "iade", "kalip", "musteri_sesi", "stok", "tavsiyeler",
                "etiketler", "durum"} <= set(k)
        assert k["durum"] in {"iyi", "dikkat", "sorunlu"}
        assert len(k["satis"]["haftalik_adet"]) in (0, u.HAFTA_SAYISI)
        json.dumps(k, ensure_ascii=False, default=float)


def test_ekonomi_tavsiye_motoruyla_ayni(sahte):
    kartlar, _, _, b = sahte
    for kod, r in b.ekonomi.head(20).iterrows():
        assert kartlar[kod]["satis"]["ciro_90"] == pytest.approx(round(r.ciro_net), abs=1)
        assert kartlar[kod]["karlilik"]["katki_payi_90"] == pytest.approx(round(r.katki_payi), abs=1)


def test_tavsiyeler_dogru_urunde(sahte):
    kartlar, _, liste, _ = sahte
    for t in liste:
        for kod in t.ilgili.get("model_kodu", []):
            if kod in kartlar:
                assert t.id in {x["id"] for x in kartlar[kod]["tavsiyeler"]}


def _kart(**kw):
    k = {"model_kodu": "m", "satis": {"adet_90": 50, "adet_onceki_30": 0, "ciro_degisimi": None,
                                      "haftalik_adet": [1] * 12},
         "karlilik": {"katki_payi_90": 100}, "iade": {"oran": 0.05}, "kalip": {}, "musteri_sesi": {}, "stok": {}}
    for bolum, deger in kw.items():
        k[bolum] = {**k[bolum], **deger}
    return k


def test_etiketler_ve_durum():
    assert u._etiketler(_kart(), 0.1, set()) == []
    assert u.genel_durum([]) == "iyi"
    assert "zarar" in u._etiketler(_kart(karlilik={"katki_payi_90": -10}), 0.1, set())
    assert "yuksek_iade" in u._etiketler(_kart(iade={"oran": 0.2}), 0.1, set())
    assert "kalip_dar" in u._etiketler(_kart(kalip={"etiket": "dar"}), 0.1, set())
    assert u.genel_durum(["kalip_dar"]) == "dikkat" and u.genel_durum(["kalip_dar", "zarar"]) == "sorunlu"


def test_stok_etiketleri_temsili_ve_satmayan():
    olu = _kart(stok={"stok": 30, "haftalik_hiz": 0, "stok_hafta": None},
                satis={"haftalik_adet": [1] * 8 + [0] * 4})
    assert "olu_stok" in u._etiketler(olu, 0.1, set())
    temsili = _kart(stok={"stok": 3000, "temsili": True, "haftalik_hiz": 0, "stok_hafta": None},
                    satis={"haftalik_adet": [0] * 12})
    assert u._etiketler(temsili, 0.1, set()) == []                  # sembolik stokta stok etiketi yok
    satmayan_bitmis = _kart(stok={"stok": 0, "haftalik_hiz": 0, "stok_hafta": 0.0})
    assert "stok_kritik" not in u._etiketler(satmayan_bitmis, 0.1, set())
    kritik = _kart(stok={"stok": 2, "haftalik_hiz": 5, "stok_hafta": 0.4})
    assert "stok_kritik" in u._etiketler(kritik, 0.1, set())
