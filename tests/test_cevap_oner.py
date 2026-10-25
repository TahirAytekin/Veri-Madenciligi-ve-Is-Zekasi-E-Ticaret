"""Cevap önerici testleri (F3-04): boy-kilo ve beden çıkarma, bilgiler, şablon, LLM güvenlik kontrolü (API'siz)."""
import json
from types import SimpleNamespace

import pytest

from tavsiye import cevap_oner as c


@pytest.mark.parametrize("metin,beklenen", [
    ("165 boy 58 kilo hangi beden olur", (165, 58)),
    ("merhaba 170 boyum 70 kiloyum hangi bedeni almalıyım", (170, 70)),
    ("1.65 boy 58 kg hangi beden", (165, 58)),
    ("165/58 hangi beden önerirsiniz", (165, 58)),
    ("boyum 160 kilom 52 bol durmasını istiyorum", (160, 52)),
    ("65 kilo 160 boy", (160, 65)),
    ("boy 165 kilo 60", (165, 60)),
    ("kalıbı dar mı 168 62 kg", (168, 62)),
    ("Boyum 1.58 kilom 50", (158, 50)),
    ("58 kilo için M olur mu", (None, 58)),
    ("kargo ne zaman gelir", (None, None)),
])
def test_boy_kilo(metin, beklenen):
    assert c.boy_kilo(metin) == beklenen


@pytest.mark.parametrize("cevap,beklenen", [
    ("Değerli Müşterimiz, sizin için M beden uygundur 🙏", ["M"]),     # "Müşterimiz"deki M sayılmaz
    ("S veya M olabilir", ["S", "M"]),
    ("xl beden öneririz", ["XL"]),
    ("XXL uygundur", ["2XL"]),
    ("Merhaba, stokta yok", []),
])
def test_cevaptaki_bedenler(cevap, beklenen):
    assert c.cevaptaki_bedenler(cevap) == beklenen


ONERI = {"katsayi": [0.0, 0.1], "sabit": -2.0, "en_sik": 4.0, "alt": 1.0, "ust": 9.0, "n": 0, "kalip_duzeltmesi": True}


@pytest.fixture(scope="module")
def harf_urun():
    t = c.m.tablolar("sahte")["urunler"]
    return t[[c.beden_degeri(b)[0] == "harf" for b in t.beden]].model_kodu.value_counts().index[0]


def test_bilgiler_ve_sablon(harf_urun):
    b = c.bilgiler("165 boy 60 kilo hangi beden olur", harf_urun, "sahte", oneri=ONERI)
    assert b["konu"] == "beden" and (b["boy"], b["kilo"]) == (165, 60)
    assert b["setteki_en_yakin"] in b["urun"]["harf_bedenler"]
    assert b["setteki_en_yakin"] in c.sablon_cevap(b)
    eksik = c.bilgiler("hangi bedeni almalıyım", harf_urun, "sahte", oneri=ONERI)
    assert set(eksik["eksik"]) == {"boy", "kilo"} and eksik["setteki_en_yakin"] is None
    assert "boy ve kilo" in c.sablon_cevap(eksik)


class _SahteIstemci:
    """messages.create'i taklit eder; verilen cevabı döndürür."""

    def __init__(self, cevap):
        metin = json.dumps({"cevap": cevap, "emin_degil": False, "kullanilan_bilgiler": ["onerilen_beden"]})
        yanit = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=metin)],
                                usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0))
        self.messages = SimpleNamespace(create=lambda **kw: yanit)


def test_llm_dogru_beden_kabul_edilir(harf_urun):
    b = c.bilgiler("165 boy 60 kilo", harf_urun, "sahte", oneri=ONERI)
    dogru = f"Değerli Müşterimiz, sizin için {b['setteki_en_yakin']} beden uygundur."
    s = c.cevap_oner("165 boy 60 kilo", harf_urun, "sahte", istemci=_SahteIstemci(dogru), oneri=ONERI)
    assert s["kaynak"] == "llm" and s["cevap"] == dogru
    assert s["maliyet_usd"] == pytest.approx((100 * 0.10 + 20 * 0.50) / 1e6)


def test_llm_yanlis_beden_sablona_doner(harf_urun):
    b = c.bilgiler("165 boy 60 kilo", harf_urun, "sahte", oneri=ONERI)
    yanlis = next(x for x in ["XS", "3XL", "S"] if x != b["setteki_en_yakin"])
    s = c.cevap_oner("165 boy 60 kilo", harf_urun, "sahte", istemci=_SahteIstemci(f"{yanlis} beden olur"),
                     oneri=ONERI)
    assert s["kaynak"] == "sablon_llm_reddedildi" and b["setteki_en_yakin"] in s["cevap"]


def test_kontroller():
    b = {"urun": {"harf_bedenler": ["S", "M", "L"]}, "setteki_en_yakin": "M", "konu": "beden", "eksik": []}
    k = c._kontroller({"bilgiler": b, "cevap": "M beden uygundur", "kaynak": "llm", "emin_degil": False})
    assert all(k.values())
    k = c._kontroller({"bilgiler": b, "cevap": "XL beden uygundur", "kaynak": "llm", "emin_degil": False})
    assert not k["onerilen_beden"] and not k["set_disi_beden_yok"]
