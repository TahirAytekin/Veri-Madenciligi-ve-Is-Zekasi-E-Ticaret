"""Yasaklı dosya kontrolü testleri (F0-05): kalıplar yakalanır, depo temizdir."""
import importlib.util

from hazirlama.ortak import PROJE

_spec = importlib.util.spec_from_file_location("kontrol", PROJE / ".github" / "kontrol.py")
kontrol = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kontrol)


def _yasakli_mi(yol):
    import re
    return any(re.search(d, yol) for d, _ in kontrol.YASAKLI_YOL)


def test_yasakli_yollar():
    for yol in (".env", "veri/gercek/siparisler.csv", "veri/ham/x.json", "ciktilar/gercek/a.csv",
                "veri/sahte_v3/urunler.csv", "ciktilar/modeller/F2-02.joblib", "loglar/a.log"):
        assert _yasakli_mi(yol), yol
    for yol in (".env.example", "veri/sahte/urunler.csv", "docs/rapor/02_dogrulama.json", "web/app.py"):
        assert not _yasakli_mi(yol), yol


def test_icerik_kaliplari():
    anahtar = "sk-" + "ant-" + "a" * 30                    # testin kendisi kontrole takılmasın
    metinler = {anahtar: True, "ANTHROPIC_API_KEY=" + "x" * 8: True, "TRENDYOL_API_SECRET = abc": True,
                "ANTHROPIC_API_KEY=": False, "MUSTERI_ID_TUZ=": False, "env_degeri('ANTHROPIC_API_KEY')": False}
    for metin, beklenen in metinler.items():
        assert any(d.search(metin) for d, _ in kontrol.ICERIK) == beklenen, metin


def test_depo_temiz():
    sorunlar, _ = kontrol.kontrol()
    assert sorunlar == []
