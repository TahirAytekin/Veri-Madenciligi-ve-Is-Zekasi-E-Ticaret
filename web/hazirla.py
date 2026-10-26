"""Web uygulaması için model çıktılarını ve bilgi tabanını hazırlar (F5-01).

    python -m web.hazirla              # mevcut veri setleri (sahte ve varsa gercek)

Sırayla: beden uyumu (kalıp tablosu), talep (stok tablosu), yorum duygusu, asistan bilgi tabanı. Gerçek veri
yoksa modeller yalnızca sahte çıktıları üretir.
"""
import subprocess
import sys

from hazirlama.ortak import PROJE, VERI

ADIMLAR = ["modeller.beden_uyumu", "modeller.talep", "modeller.duygu"]


def calistir():
    for modul in ADIMLAR:
        print(f"→ {modul}", flush=True)
        subprocess.run([sys.executable, "-m", modul], cwd=PROJE, check=True, capture_output=True)
    for veri in ("sahte", "gercek"):
        if (VERI / veri / "siparisler.csv").exists():
            print(f"→ asistan.bilgi_tabani --veri {veri}", flush=True)
            subprocess.run([sys.executable, "-m", "asistan.bilgi_tabani", "--veri", veri], cwd=PROJE, check=True,
                           capture_output=True)
    print("hazır: streamlit run web/app.py")


if __name__ == "__main__":
    calistir()
