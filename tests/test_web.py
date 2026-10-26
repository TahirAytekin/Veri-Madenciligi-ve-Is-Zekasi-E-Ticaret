"""Web uygulaması testleri (F5): her sayfa uygulamanın gezinmesi içinde, sahte veriyle hatasız açılmalı.

Streamlit AppTest tarayıcı açmadan çalıştırır. Sayfalar durum raporu ve tavsiyeleri hesapladığı için ilk açılış
birkaç saniye sürer.
"""
import json

import pytest
from streamlit.testing.v1 import AppTest

from modeller.ortak.degerlendir import CIKTILAR
from web import ortak

SAYFALAR = ["genel_bakis", "aksiyon_plani", "urunler", "model_dogrulama"]


@pytest.fixture(scope="module")
def uygulama():
    at = AppTest.from_file("web/app.py", default_timeout=300)
    at.session_state["veri"] = "sahte"
    at.run()
    assert not at.exception
    return at


@pytest.mark.parametrize("sayfa", SAYFALAR)
def test_sayfa_acilir(uygulama, sayfa):
    uygulama.switch_page(f"sayfalar/{sayfa}.py").run()
    assert not uygulama.exception, [str(e.value) for e in uygulama.exception]
    assert uygulama.title and uygulama.metric


def test_yapildi_isareti_kaydedilir(uygulama):
    yol = CIKTILAR / "sahte" / "yapilanlar.json"
    once = yol.read_text(encoding="utf-8") if yol.exists() else None
    try:
        uygulama.switch_page("sayfalar/aksiyon_plani.py").run()
        kutu = uygulama.checkbox[0]
        kutu.check().run() if not kutu.value else kutu.uncheck().run()
        assert not uygulama.exception
        assert yol.exists() and isinstance(json.loads(yol.read_text(encoding="utf-8")), list)
    finally:                                                    # testin izini bırakma
        if once is None:
            yol.unlink(missing_ok=True)
        else:
            yol.write_text(once, encoding="utf-8")


def test_urun_filtresi_ve_karti(uygulama):
    uygulama.switch_page("sayfalar/urunler.py").run()
    uygulama.multiselect[0].select("sorunlu").run()
    assert not uygulama.exception
    urun = uygulama.selectbox[-1]
    urun.select_index(len(urun.options) - 1).run()
    assert not uygulama.exception


def test_filtre_bos_secimde_hepsi():
    import pandas as pd
    s = pd.Series(["a", "b"])
    assert ortak.filtre(s, []).all() and ortak.filtre(s, ["a"]).tolist() == [True, False]
