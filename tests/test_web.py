"""Web uygulaması testleri (F5): her sayfa uygulamanın gezinmesi içinde, sahte veriyle hatasız açılmalı.

Streamlit AppTest tarayıcı açmadan çalıştırır. Sayfalar durum raporu ve tavsiyeleri hesapladığı için ilk açılış
birkaç saniye sürer.
"""
import json

import pytest
from streamlit.testing.v1 import AppTest

from hazirlama.ortak import PROJE
from modeller.ortak.degerlendir import CIKTILAR
from web import ortak

UYGULAMA = PROJE / "web" / "app.py"          # mutlak yol: Streamlit ≥ 1.6x göreli yolu test dosyasına göre çözer
SAYFALAR = ["genel_bakis", "aksiyon_plani", "urunler", "iade_beden", "talep_stok", "finans_senaryo", "musteri_sesi",
            "model_dogrulama"]


@pytest.fixture(scope="module")
def uygulama():
    at = AppTest.from_file(str(UYGULAMA), default_timeout=300)
    at.session_state["veri"] = "sahte"
    at.run()
    assert not at.exception
    return at


@pytest.mark.parametrize("sayfa", SAYFALAR)
def test_sayfa_acilir(uygulama, sayfa):
    uygulama.switch_page(f"sayfalar/{sayfa}.py").run()
    assert not uygulama.exception, [str(e.value) for e in uygulama.exception]
    assert uygulama.title and (uygulama.metric or uygulama.info)      # çıktı yoksa gösterge yerine bilgi notu


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


def test_beden_onerici(uygulama):
    uygulama.switch_page("sayfalar/iade_beden.py").run()
    uygulama.number_input[0].set_value(175).run()
    uygulama.number_input[1].set_value(80).run()
    assert not uygulama.exception
    assert any("Önerilen beden" in x.value for x in uygulama.markdown)


def test_senaryo_kaydiricisi(uygulama):
    uygulama.switch_page("sayfalar/finans_senaryo.py").run()
    uygulama.slider[0].set_value(30).run()                         # beden iadeleri %30 azalırsa
    assert not uygulama.exception
    assert any("artar" in x.value for x in uygulama.success)
    uygulama.slider[2].set_value(10).run()                         # %10 ek indirim → başa baş
    assert any("Başa baş" in x.value for x in uygulama.info)


def test_cevap_onerici_sablon(uygulama):
    uygulama.switch_page("sayfalar/musteri_sesi.py").run()
    uygulama.text_area[0].input("165 boy 58 kilo hangi beden olur").run()
    if not uygulama.toggle[0].disabled:                           # anahtar yoksa düğme zaten kapalı (CI)
        uygulama.toggle[0].set_value(False).run()                  # API kullanma
    uygulama.button[0].click().run()
    assert not uygulama.exception
    assert uygulama.code and "beden" in uygulama.code[0].value


def test_asistan_sohbeti(monkeypatch):
    """API'ye istek atmadan: sor() yerine sahte cevap; her tur bir kez sorulmalı, mesajlar çoğalmamalı."""
    from asistan import sohbet
    sorulan = []

    def sahte_sor(self, soru, gecmis=None, akis=None):
        sorulan.append((soru, gecmis))
        if akis:
            akis("cevap ")
        return {"cevap": f"cevap: {soru}", "araclar": [{"ad": "metrik_hesapla", "girdi": {"metrik": "iade_orani"},
                                                        "hata": False}],
                "durum": "end_turn", "kullanim": {}, "maliyet_usd": 0.001, "sure_sn": 0.1, "model": self.model,
                "mesajlar": [{"role": "user", "content": soru}]}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(sohbet.Asistan, "sor", sahte_sor)
    at = AppTest.from_file(str(UYGULAMA), default_timeout=300)
    at.session_state["veri"] = "sahte"
    at.run()
    at.switch_page("sayfalar/asistan.py").run()
    at.chat_input[0].set_value("soru 1").run()
    assert not at.exception and len(at.chat_message) == 2
    at.chat_input[0].set_value("soru 2").run()
    assert len(at.chat_message) == 4 and len(sorulan) == 2
    assert sorulan[1][1] == [{"role": "user", "content": "soru 1"}]      # çok turlu: önceki mesajlar gider
