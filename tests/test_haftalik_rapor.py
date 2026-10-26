"""Haftalık PDF rapor testleri (adım 5): içerik ve PDF üretimi (sahte veri)."""
import pandas as pd

from tavsiye import haftalik_rapor as hr


def test_icerik_ve_pdf():
    c = hr.icerik("sahte")
    assert c["bit"] - c["bas"] == pd.Timedelta(days=6)
    assert [k["baslik"] for k in c["haftalik"]] and c["plan"]["aksiyonlar"]
    pdf = hr.pdf_uret("sahte", c)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 10_000


def test_bicim_ve_temizleme():
    assert hr._bicim(None, "TL") == "—" and hr._bicim(4.0, "puan") == "4,0"
    assert hr._temiz("Sepetine Özel Kupon! 🛍️") == "Sepetine Özel Kupon!"
