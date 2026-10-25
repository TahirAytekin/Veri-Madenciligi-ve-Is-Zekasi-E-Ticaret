"""Tavsiye motoru testleri (F3-01…03): şema, birim ekonomisi (senaryo ile tutarlılık), kurallar, aksiyon planı."""
import json

import pandas as pd
import pytest

from analiz import senaryo
from tavsiye import kurallar as k
from tavsiye import motor
from tavsiye.sema import GUVEN_PUANI, Tavsiye


def _t(etki=None, guven="orta", onem="orta", id_="x"):
    return Tavsiye(id_, "deneme", "urun", "b", "a", "ak", {}, guven, "g", onem, etki)


@pytest.fixture(scope="module")
def sahte():
    return motor.tavsiyeler("sahte")


def test_sema_dogrulama_ve_oncelik():
    with pytest.raises(AssertionError):
        _t(guven="cok")
    assert _t(etki=1000, guven="yuksek").oncelik == pytest.approx(1000 * GUVEN_PUANI["yuksek"])
    assert _t().oncelik is None


def test_birim_katki_senaryo_ile_ayni():
    b = {"iade_orani": 0.12, "komisyon_orani": 0.21, "birim_kargo": 40.0, "birim_platform": 10.0,
         "iade_basi_kargo": 45.0}
    assert k.birim_katki(500, 0.12, 0.21, 50.0, 45.0) == pytest.approx(senaryo._birim_katki(b, 500))


def test_onlenen_iade_degeri_turev():
    # İade oranı δ azalınca birim katkı δ × (P(1−k) + ik) artar
    P, kom, c, ik, d = 600.0, 0.2, 55.0, 40.0, 0.01
    artis = k.birim_katki(P, 0.15 - d, kom, c, ik) - k.birim_katki(P, 0.15, kom, c, ik)
    assert artis == pytest.approx(d * k.onlenen_iade_degeri(P, kom, ik))


def test_fiyat_etkisi():
    r = pd.Series({"adet": 100, "P": 500.0, "r": 0.1, "k": 0.2, "c": 50.0})
    assert k.fiyat_etkisi(r, 1.0, 40.0, 1.5) == pytest.approx(0)
    assert k.fiyat_etkisi(r, 1.1, 40.0, 0.0) > 0                      # esneklik 0: fiyat artışı katkıyı artırır


def test_kurallar_hatasiz_ve_tekil(sahte):
    liste, hatalar, _ = sahte
    assert hatalar == [], hatalar
    ids = [t.id for t in liste]
    assert len(ids) == len(set(ids))
    assert len(k.KURALLAR) >= 12


def test_tavsiye_alanlari(sahte):
    for t in sahte[0]:
        assert t.baslik and t.aksiyon and t.guven_gerekcesi and t.kanit.get("kaynak"), t.id
        assert t.etki_tl is None or t.etki_aciklama, t.id
        json.dumps(t.sozluk(), ensure_ascii=False, default=float)


def test_siralama_ve_plan(sahte):
    liste = sahte[0]
    olculen = [t.oncelik for t in liste if t.etki_tl is not None]
    assert olculen == sorted(olculen, reverse=True)
    ilk_olculmeyen = next((i for i, t in enumerate(liste) if t.etki_tl is None), len(liste))
    assert all(t.etki_tl is None for t in liste[ilk_olculmeyen:])
    plan = motor.aksiyon_plani(liste)
    assert len(plan["aksiyonlar"]) <= motor.PLAN_TL + motor.PLAN_DIGER
    assert plan["toplam_aylik_etki_tl"] == pytest.approx(
        sum(x["etki_tl"] for x in plan["aksiyonlar"] if x["etki_tl"] is not None))


def test_zarar_eden_urun_basa_bas():
    # Önerilen fiyat artışıyla gözlenen birim katkı (−500 / 20 = −25 TL) sıfıra çıkmalı
    b = k.Baglam.__new__(k.Baglam)
    b.gun, b.ik, b.model_adi = 90, 40.0, {}
    b.ekonomi = pd.DataFrame({"kategori": ["X"], "adet": [20], "P": [200.0], "r": [0.3], "k": [0.2], "c": [90.0],
                              "katki_payi": [-500.0]}, index=pd.Index(["m1"], name="model_kodu"))
    t = k.zarar_eden_urun(b)[0]
    artis = t.kanit["basa_bas_fiyat_artisi"]
    assert -25 + (1 - 0.3) * (1 - 0.2) * artis == pytest.approx(0, abs=1e-9)
    assert t.etki_tl == pytest.approx(500 * 30 / 90)
