"""Üretim hattı testleri (F6-01): çıktılar üretilir, doğrulama dosyalarına dokunulmaz, hatalı adım diğerlerini
durdurmaz, panel yeni veriyi görür."""
import json

import calistir
from hazirlama.ortak import PROJE
from modeller.ortak.degerlendir import CIKTILAR

HIZLI = ["kalip", "stok", "durum", "tavsiye", "kart"]          # yorum (BERT) ve bilgi (embedding) ağır


def _dogrulama_dosyalari():
    yollar = list((CIKTILAR / "sahte" / "dogrulama").glob("*.json")) + list((PROJE / "docs" / "rapor").glob("*"))
    return {p: p.stat().st_mtime_ns for p in yollar}


def test_hat_ciktilari_uretir_dogrulamaya_dokunmaz():
    once = _dogrulama_dosyalari()
    ozet = calistir.calistir("sahte", HIZLI)
    assert ozet["basarili"], [s for s in ozet["adimlar"] if s["durum"] != "tamam"]
    assert [s["adim"] for s in ozet["adimlar"]] == HIZLI
    for ad in ("F2-04_kalip", "F2-05_stok"):
        assert (CIKTILAR / "sahte" / "tahminler" / f"{ad}.csv").exists()
    for ad in ("durum_raporu.json", "tavsiyeler.json", "aksiyon_plani.json", "urun_kartlari.json", "uretim.json"):
        assert (CIKTILAR / "sahte" / ad).exists(), ad
    assert _dogrulama_dosyalari() == once                       # dondurulmuş doğrulama sonuçları değişmedi
    kayit = json.loads((CIKTILAR / "sahte" / "uretim.json").read_text(encoding="utf-8"))
    assert kayit["veri"] == "sahte" and kayit["veri_araligi"]["bitis"]


def test_hatali_adim_digerlerini_durdurmaz(monkeypatch):
    def bozuk(veri):
        raise RuntimeError("deneme")

    monkeypatch.setitem(calistir.ADIMLAR, "bozuk", bozuk)
    ozet = calistir.calistir("sahte", ["bozuk", "durum"])
    assert not ozet["basarili"]
    assert ozet["adimlar"][0]["durum"] == "hata" and "deneme" in ozet["adimlar"][0]["bilgi"]
    assert ozet["adimlar"][1]["durum"] == "tamam"


def test_panel_veri_degisince_onbellegi_temizler(monkeypatch):
    from web import ortak
    temizlendi = []
    monkeypatch.setattr(ortak, "sureci_tazele", lambda: temizlendi.append(1))
    ortak._SON_SURUM.clear()
    ortak._surum("sahte")
    assert not temizlendi                                       # ilk okumada temizleme yok
    ortak._SON_SURUM["sahte"] = -1                              # dosyalar değişmiş gibi
    ortak._surum("sahte")
    assert temizlendi == [1]


def test_sureci_tazele_calisir():
    from web import ortak
    ortak.sureci_tazele()
