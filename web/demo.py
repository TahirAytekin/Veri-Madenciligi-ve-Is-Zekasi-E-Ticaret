"""İnternet demosu (F5-12): yalnızca sahte veriyle, hafif paketlerle (web/requirements.txt), API anahtarı olmadan.

Demo modu: gerçek veri klasörü yoksa ya da DEMO=1 ise. Sunucuda ciktilar/ olmadığı için panel çıktıları ilk açılışta
bir kez üretilir (~20 sn): analiz tabloları, kalıp, stok, durum, tavsiye, ürün kartı ve haftalık rapor. Yorum analizi
BERT gerektirdiği için sahte sonuçları depoda hazır gelir (web/demo_ciktilar/). Asistan ve Claude ile cevap taslağı
kapalıdır: sunucuya API anahtarı konmaz (anahtar konulursa herkes onu kullanır).
"""
import os
import shutil
import subprocess
import sys

import streamlit as st

from hazirlama.ortak import PROJE, VERI
from modeller.ortak.degerlendir import CIKTILAR

HAZIR_CIKTILAR = PROJE / "web" / "demo_ciktilar"
DEMO_ADIMLARI = ["kalip", "stok", "durum", "tavsiye", "kart", "rapor"]


def demo_mu():
    """Gerçek veri yok (internet demosu veya gerçek verisi olmayan ekip üyesi): sahte çıktılar gerekirse üretilir."""
    return internet_demosu() or not (VERI / "gercek" / "siparisler.csv").exists()


def internet_demosu():
    """Streamlit Cloud'da DEMO=1 (secrets). Asistan ve Claude ile cevap, anahtar olsa bile kapalıdır."""
    return os.environ.get("DEMO") == "1"


def _eksik():
    gerekli = [CIKTILAR / "sahte" / "tahminler" / f"{ad}.csv" for ad in ("F2-04_kalip", "F2-05_stok", "F2-06")]
    return not all(p.exists() for p in gerekli) or not (VERI / "sahte" / "analiz").exists()


@st.cache_resource(show_spinner="Demo hazırlanıyor (ilk açılışta bir kez, ~20 sn)…")
def hazirla():
    """Sahte veri çıktıları yoksa üretir. Süreç başına bir kez; sonucu (başarılı mı, mesaj) döner."""
    if not _eksik():
        return True, "hazır"
    hedef = CIKTILAR / "sahte" / "tahminler"
    hedef.mkdir(parents=True, exist_ok=True)
    for dosya in HAZIR_CIKTILAR.glob("*.csv"):
        shutil.copy2(dosya, hedef / dosya.name)
    subprocess.run([sys.executable, "hazirlama/ozellik_cikar.py", "sahte"], cwd=PROJE, check=True,
                   capture_output=True)
    import calistir
    ozet = calistir.calistir("sahte", DEMO_ADIMLARI)
    hatalar = [s["adim"] for s in ozet["adimlar"] if s["durum"] != "tamam"]
    return not hatalar, ("hazır" if not hatalar else f"bazı adımlar hata verdi: {', '.join(hatalar)}")


def baslat():
    """app.py en başta çağırır: demo modunda çıktıları hazırlar ve kenar çubuğuna not düşer."""
    if not demo_mu():
        return
    tamam, mesaj = hazirla()
    if internet_demosu():
        st.sidebar.info("**Demo:** tamamen sahte bir mağazanın verisi. Asistan ve Claude ile cevap taslağı bu "
                        "demoda kapalı.")
    if not tamam:
        st.sidebar.warning(f"Demo hazırlığı: {mesaj}")
